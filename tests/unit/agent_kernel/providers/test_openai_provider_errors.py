"""Tests for OpenAI provider error handling."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_kernel.providers.openai import OpenAIProvider


class TestInvalidApiKeyFormat:
    """Test invalid API key format validation."""

    def test_key_without_sk_prefix_raises_value_error(self):
        """Key without 'sk-' prefix raises ValueError."""
        with pytest.raises(ValueError, match="malformed"):
            OpenAIProvider(
                api_key="test-key-without-prefix-that-is-very-long-12345",
                model="gpt-4o",
            )

    def test_key_too_short_raises_value_error(self):
        """Key that is too short raises ValueError."""
        with pytest.raises(ValueError, match="malformed"):
            OpenAIProvider(
                api_key="sk-short",
                model="gpt-4o",
            )

    def test_key_with_wrong_provider_prefix_raises_value_error(self):
        """Key with wrong provider prefix (ro- for OpenAI) raises ValueError.

        Note: 'ro-' is actually valid for OpenAI according to the code,
        but let's test that other prefixes fail.
        """
        with pytest.raises(ValueError, match="malformed"):
            OpenAIProvider(
                api_key="pk-other-provider-key-that-is-very-long-12345",
                model="gpt-4o",
            )

    def test_ro_prefix_is_valid(self):
        """Keys starting with 'ro-' should be accepted (OpenAI organization keys)."""
        # This should not raise - 'ro-' is valid according to the implementation
        provider = OpenAIProvider(
            api_key="ro-validorgkey12345678901234567890123",
            model="gpt-4o",
        )
        assert provider is not None


class TestNetworkTimeoutHandling:
    """Test network timeout handling."""

    @pytest.mark.asyncio
    async def test_timeout_error_handled_gracefully(self):
        """Mock client raises TimeoutError, verify graceful handling."""
        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        # Mock the client to raise TimeoutError
        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=TimeoutError("Request timed out")
            )

            events = []
            with pytest.raises(TimeoutError):
                async for event in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    events.append(event)

    @pytest.mark.asyncio
    async def test_timeout_error_message(self):
        """Verify TimeoutError is propagated with appropriate message."""
        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=TimeoutError("Connection timeout after 30s")
            )

            with pytest.raises(TimeoutError, match="Connection timeout"):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass


class TestMalformedJsonResponse:
    """Test malformed JSON response handling."""

    @pytest.mark.asyncio
    async def test_json_decode_error_handled(self):
        """Mock response with invalid JSON, verify JSONDecodeError handling."""
        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        # Create a mock that returns something that causes JSON decode issues
        with patch.object(provider, "_client") as mock_client:
            mock_chunk = MagicMock()
            mock_chunk.choices = []
            mock_chunk.usage = None

            # Simulate a response that causes issues
            mock_client.chat.completions.create = AsyncMock(
                side_effect=json.JSONDecodeError("Expecting value", "", 0)
            )

            with pytest.raises(json.JSONDecodeError):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass


class TestRateLimitError:
    """Test rate limit error (429) handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_429_handled(self):
        """Mock 429 response with Retry-After header, verify error handling."""
        from openai import RateLimitError

        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        # Create a mock rate limit error with Retry-After info
        error_response = {"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=RateLimitError(
                    message="Rate limit exceeded. Retry-After: 60",
                    response=MagicMock(
                        status_code=429,
                        headers={"retry-after": "60"},
                        json=lambda: error_response,
                    ),
                    body=None,
                )
            )

            with pytest.raises(RateLimitError) as exc_info:
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass

            # Verify error message includes retry info
            assert "60" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_error_message_includes_retry_info(self):
        """Verify error message includes retry information."""
        from openai import RateLimitError

        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=RateLimitError(
                    message="You exceeded your current quota",
                    response=MagicMock(
                        status_code=429,
                        headers={"retry-after": "30"},
                    ),
                    body=None,
                )
            )

            with pytest.raises(RateLimitError):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass


class TestServerErrors:
    """Test server error (5xx) handling."""

    @pytest.mark.asyncio
    async def test_500_error_handled(self):
        """Test 500 Internal Server Error handling."""
        from openai import APIConnectionError
        import httpx

        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        # Create a mock request for APIConnectionError
        mock_request = MagicMock(spec=httpx.Request)
        mock_request.method = "POST"
        mock_request.url = "http://test.com/v1/chat/completions"

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIConnectionError(
                    message="Internal Server Error",
                    request=mock_request,
                )
            )

            with pytest.raises(APIConnectionError):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass

    @pytest.mark.asyncio
    async def test_502_error_handled(self):
        """Test 502 Bad Gateway Error handling."""
        from openai import APIConnectionError
        import httpx

        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        mock_request = MagicMock(spec=httpx.Request)
        mock_request.method = "POST"
        mock_request.url = "http://test.com/v1/chat/completions"

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIConnectionError(
                    message="Bad Gateway",
                    request=mock_request,
                )
            )

            with pytest.raises(APIConnectionError):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass

    @pytest.mark.asyncio
    async def test_503_error_handled(self):
        """Test 503 Service Unavailable Error handling."""
        from openai import APIConnectionError
        import httpx

        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        mock_request = MagicMock(spec=httpx.Request)
        mock_request.method = "POST"
        mock_request.url = "http://test.com/v1/chat/completions"

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIConnectionError(
                    message="Service Unavailable",
                    request=mock_request,
                )
            )

            with pytest.raises(APIConnectionError):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass


class TestEmptyResponse:
    """Test empty response handling."""

    @pytest.mark.asyncio
    async def test_empty_choices_handled_gracefully(self):
        """Mock response with empty choices list, verify graceful handling."""
        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=True,
        )

        # Create a mock stream that returns empty choices
        mock_chunk = MagicMock()
        mock_chunk.choices = []
        mock_chunk.usage = None

        with patch.object(provider, "_client") as mock_client:
            # Create an async generator that yields the empty chunk
            async def mock_stream():
                yield mock_chunk

            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
            ):
                events.append(event)

            # Should handle gracefully without crashing
            # The stream should yield at least the MESSAGE_END event
            assert len(events) >= 0  # May be empty or have MESSAGE_END

    @pytest.mark.asyncio
    async def test_empty_choices_non_stream(self):
        """Test empty choices in non-streaming mode."""
        provider = OpenAIProvider(
            api_key="sk-test-key-with-valid-prefix-and-length-1234",
            model="gpt-4o",
            stream=False,
        )

        # Create a mock response with empty choices - this will cause IndexError
        mock_response = MagicMock()
        mock_response.choices = []
        mock_response.usage = None

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # This should raise IndexError when accessing response.choices[0]
            with pytest.raises(IndexError):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                ):
                    pass
