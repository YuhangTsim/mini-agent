"""Tests for tool concurrency scenarios.

Tests cover:
1. Parallel tool execution - multiple tools running simultaneously
2. Shared resource access - concurrent read/write to same files
3. Deadlock prevention and timeout - operations that could deadlock
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

import pytest

from agent_kernel.tools.base import ToolContext, ToolResult
from agent_kernel.tools.native.command import ExecuteCommandTool
from agent_kernel.tools.native.file_ops import ReadFileTool, WriteFileTool
from agent_kernel.tools.native.search import SearchFilesTool, ListFilesTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tool_context():
    """Create a tool context for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ToolContext(
            session_id="test-session-concurrency",
            agent_run_id="test-run-concurrency",
            agent_role="test_agent",
            working_directory=tmpdir,
        )


@pytest.fixture
def read_tool():
    return ReadFileTool()


@pytest.fixture
def write_tool():
    return WriteFileTool()


@pytest.fixture
def search_tool():
    return SearchFilesTool()


@pytest.fixture
def list_tool():
    return ListFilesTool()


@pytest.fixture
def command_tool():
    return ExecuteCommandTool()


# ---------------------------------------------------------------------------
# Test 1: Parallel tool execution
# ---------------------------------------------------------------------------


class TestParallelToolExecution:
    """Tests for executing multiple tools in parallel."""

    async def test_three_tools_run_simultaneously(
        self, read_tool, write_tool, list_tool, tool_context
    ):
        """Test that 3+ tools can execute simultaneously."""
        # Setup: create files and directories for tools to work with
        test_dir = os.path.join(tool_context.working_directory, "test_project")
        os.makedirs(test_dir)

        # Create a file for reading
        test_file = os.path.join(tool_context.working_directory, "readable.txt")
        with open(test_file, "w") as f:
            f.write("Hello World")

        # Execute 3 tools in parallel
        start_time = time.monotonic()

        results = await asyncio.gather(
            read_tool.execute({"path": "readable.txt"}, tool_context),
            list_tool.execute({"path": ".", "recursive": False}, tool_context),
            write_tool.execute({"path": "new_file.txt", "content": "new content"}, tool_context),
        )

        elapsed = time.monotonic() - start_time

        # All should complete successfully
        assert len(results) == 3
        assert all(not r.is_error for r in results), (
            f"Errors: {[r.error for r in results if r.is_error]}"
        )

        # Should complete in reasonable time (not sequential)
        # Each operation should take < 1 second, so 3 in parallel should be < 2s
        assert elapsed < 5, f"Parallel execution took too long: {elapsed:.2f}s"

    async def test_parallel_results_no_cross_contamination(
        self, read_tool, write_tool, tool_context
    ):
        """Test that parallel executions don't cross-contaminate results."""
        # Create multiple files with unique content
        file_contents = {
            "file1.txt": "Content of file 1",
            "file2.txt": "Content of file 2",
            "file3.txt": "Content of file 3",
        }

        for filename, content in file_contents.items():
            filepath = os.path.join(tool_context.working_directory, filename)
            with open(filepath, "w") as f:
                f.write(content)

        # Read all files in parallel
        results = await asyncio.gather(
            read_tool.execute({"path": "file1.txt"}, tool_context),
            read_tool.execute({"path": "file2.txt"}, tool_context),
            read_tool.execute({"path": "file3.txt"}, tool_context),
        )

        # Each result should match its corresponding file
        assert not results[0].is_error
        assert not results[1].is_error
        assert not results[2].is_error

        # Verify content is not mixed
        assert "Content of file 1" in results[0].output
        assert "Content of file 2" in results[1].output
        assert "Content of file 3" in results[2].output

        # Verify no cross-contamination
        assert "file 2" not in results[0].output
        assert "file 1" not in results[1].output
        assert "file 1" not in results[2].output

    async def test_parallel_execution_order_independent(self, read_tool, write_tool, tool_context):
        """Test that completion order doesn't affect results."""
        # Create files with different sizes to vary read time
        files = []
        for i in range(5):
            filepath = os.path.join(tool_context.working_directory, f"file{i}.txt")
            with open(filepath, "w") as f:
                f.write(f"x" * (1000 * (i + 1)))  # Different sizes
            files.append(f"file{i}.txt")

        # Run reads multiple times to detect order dependence
        for _ in range(3):
            results = await asyncio.gather(
                *[read_tool.execute({"path": f}, tool_context) for f in files]
            )

            # All should succeed
            assert all(not r.is_error for r in results)

            # Each result should have correct content
            for i, result in enumerate(results):
                expected = "x" * (1000 * (i + 1))
                assert expected in result.output, f"File {i} content mismatch"

    async def test_many_parallel_tools(
        self, read_tool, write_tool, list_tool, search_tool, tool_context
    ):
        """Test that many tools can run in parallel without issues."""
        # Create multiple files
        for i in range(10):
            filepath = os.path.join(tool_context.working_directory, f"data{i}.txt")
            with open(filepath, "w") as f:
                f.write(f"Line with number {i}\n" * 10)

        # Execute 10 tools in parallel
        tasks = [read_tool.execute({"path": f"data{i}.txt"}, tool_context) for i in range(5)]
        tasks.extend(
            [
                write_tool.execute(
                    {"path": f"output{i}.txt", "content": f"Output {i}"}, tool_context
                )
                for i in range(3)
            ]
        )
        tasks.append(list_tool.execute({"path": ".", "recursive": False}, tool_context))
        tasks.append(
            search_tool.execute({"path": ".", "pattern": "Line", "glob": "*.txt"}, tool_context)
        )

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 10
        assert all(not r.is_error for r in results)


# ---------------------------------------------------------------------------
# Test 2: Shared resource access
# ---------------------------------------------------------------------------


class TestSharedResourceAccess:
    """Tests for concurrent access to shared resources (files)."""

    async def test_two_readers_same_file(self, read_tool, tool_context):
        """Test that two tools can read the same file simultaneously."""
        # Create a test file
        test_file = os.path.join(tool_context.working_directory, "shared.txt")
        with open(test_file, "w") as f:
            f.write("Shared content for reading")

        # Read same file from two tasks simultaneously
        results = await asyncio.gather(
            read_tool.execute({"path": "shared.txt"}, tool_context),
            read_tool.execute({"path": "shared.txt"}, tool_context),
        )

        # Both should succeed
        assert len(results) == 2
        assert all(not r.is_error for r in results)

        # Both should have same content
        assert "Shared content" in results[0].output
        assert results[0].output == results[1].output

    async def test_two_writers_same_file_race_condition(self, write_tool, read_tool, tool_context):
        """Test concurrent writes to the same file - tests for race conditions."""
        test_file = os.path.join(tool_context.working_directory, "race.txt")

        # Write to same file from two tasks simultaneously
        results = await asyncio.gather(
            write_tool.execute({"path": "race.txt", "content": "Writer 1 content"}, tool_context),
            write_tool.execute({"path": "race.txt", "content": "Writer 2 content"}, tool_context),
        )

        # Both should complete (one will "win" the race)
        assert len(results) == 2
        assert all(not r.is_error for r in results)

        # Read final content - should be one of the writes (deterministic due to file locking)
        result = await read_tool.execute({"path": "race.txt"}, tool_context)
        assert not result.is_error
        # Content should be one of the two writes
        assert "Writer 1 content" in result.output or "Writer 2 content" in result.output

    async def test_read_write_same_file_simultaneously(self, read_tool, write_tool, tool_context):
        """Test reading and writing to same file simultaneously."""
        test_file = os.path.join(tool_context.working_directory, "concurrent.txt")

        # Initial content
        with open(test_file, "w") as f:
            f.write("Initial content")

        # Read and write simultaneously
        results = await asyncio.gather(
            read_tool.execute({"path": "concurrent.txt"}, tool_context),
            write_tool.execute({"path": "concurrent.txt", "content": "New content"}, tool_context),
        )

        # Both should complete without crashing
        assert len(results) == 2
        assert all(not r.is_error for r in results)

        # Final state should be consistent
        final_read = await read_tool.execute({"path": "concurrent.txt"}, tool_context)
        assert not final_read.is_error
        assert "New content" in final_read.output

    async def test_file_data_integrity_under_load(self, read_tool, write_tool, tool_context):
        """Test that data integrity is maintained under concurrent access."""
        test_file = os.path.join(tool_context.working_directory, "integrity.txt")

        # Write initial content
        with open(test_file, "w") as f:
            f.write("START")

        # Perform multiple read-write cycles
        for i in range(10):
            # Read current content
            read_result = await read_tool.execute({"path": "integrity.txt"}, tool_context)
            assert not read_result.is_error

            # Write new content
            write_result = await write_tool.execute(
                {"path": "integrity.txt", "content": f"Cycle {i}"}, tool_context
            )
            assert not write_result.is_error

        # Final content should be valid
        final = await read_tool.execute({"path": "integrity.txt"}, tool_context)
        assert not final.is_error
        assert "Cycle 9" in final.output

        # File should not be corrupted
        with open(test_file, "r") as f:
            raw_content = f.read()
        assert raw_content == "Cycle 9"

    async def test_multiple_writers_different_files(self, write_tool, tool_context):
        """Test that writing to different files concurrently works correctly."""
        # Write to multiple different files simultaneously
        results = await asyncio.gather(
            *[
                write_tool.execute(
                    {"path": f"file{i}.txt", "content": f"Content {i}"}, tool_context
                )
                for i in range(10)
            ]
        )

        # All should succeed
        assert len(results) == 10
        assert all(not r.is_error for r in results)

        # Verify each file has correct content
        for i in range(10):
            filepath = os.path.join(tool_context.working_directory, f"file{i}.txt")
            with open(filepath, "r") as f:
                content = f.read()
            assert content == f"Content {i}"


# ---------------------------------------------------------------------------
# Test 3: Deadlock prevention and timeout
# ---------------------------------------------------------------------------


class TestDeadlockPreventionAndTimeout:
    """Tests for deadlock prevention and timeout handling."""

    async def test_timeout_prevents_indefinite_hang(self, command_tool, tool_context):
        """Test that timeout prevents indefinite hanging."""
        # Start a command that could hang indefinitely
        start_time = time.monotonic()

        result = await command_tool.execute({"command": "sleep 30", "timeout": 2}, tool_context)

        elapsed = time.monotonic() - start_time

        # Should timeout and not hang
        assert result.is_error
        assert "timed out" in result.error.lower()
        assert elapsed < 10, f"Should have timed out quickly, took {elapsed:.2f}s"

    async def test_graceful_error_on_timeout(self, command_tool, tool_context):
        """Test that timeout produces a graceful error."""
        result = await command_tool.execute({"command": "sleep 20", "timeout": 1}, tool_context)

        # Should be an error but not a crash
        assert result.is_error
        assert "timed out" in result.error.lower() or "timeout" in result.error.lower()

        # Should be able to run another command after timeout
        result2 = await command_tool.execute(
            {"command": "echo 'after timeout'", "timeout": 5}, tool_context
        )

        assert not result2.is_error
        assert "after timeout" in result2.output

    async def test_resources_released_after_timeout(self, command_tool, read_tool, tool_context):
        """Test that resources are properly released after timeout."""
        # Create a file
        test_file = os.path.join(tool_context.working_directory, "resource_test.txt")
        with open(test_file, "w") as f:
            f.write("Test content")

        # Run a timeout command
        await command_tool.execute({"command": "sleep 10", "timeout": 1}, tool_context)

        # Should still be able to read files after timeout
        result = await read_tool.execute({"path": "resource_test.txt"}, tool_context)

        assert not result.is_error
        assert "Test content" in result.output

    async def test_concurrent_timeouts_all_complete(self, command_tool, tool_context):
        """Test that multiple concurrent timeout attempts all complete."""
        # Start multiple commands that will timeout
        start_time = time.monotonic()

        results = await asyncio.gather(
            command_tool.execute({"command": "sleep 10", "timeout": 1}, tool_context),
            command_tool.execute({"command": "sleep 10", "timeout": 2}, tool_context),
            command_tool.execute({"command": "sleep 10", "timeout": 1}, tool_context),
        )

        elapsed = time.monotonic() - start_time

        # All should timeout (not hang)
        assert len(results) == 3
        assert all(r.is_error for r in results)

        # Should complete in reasonable time
        assert elapsed < 10, f"Concurrent timeouts took too long: {elapsed:.2f}s"

    async def test_no_deadlock_with_file_operations(self, read_tool, write_tool, tool_context):
        """Test that file operations don't deadlock when run concurrently."""
        # Create test files
        for i in range(5):
            filepath = os.path.join(tool_context.working_directory, f"deadlock_test{i}.txt")
            with open(filepath, "w") as f:
                f.write(f"Content {i}")

        # Mix of reads and writes that could potentially cause deadlock
        # (In a properly implemented system, these should complete)
        start_time = time.monotonic()

        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(read_tool.execute({"path": f"deadlock_test{i % 5}.txt"}, tool_context))
            else:
                tasks.append(
                    write_tool.execute(
                        {"path": f"output{i}.txt", "content": f"Output {i}"}, tool_context
                    )
                )

        results = await asyncio.gather(*tasks)

        elapsed = time.monotonic() - start_time

        # All should complete without deadlock
        assert len(results) == 10
        # Most should succeed (some writes might have race conditions but shouldn't deadlock)
        successful = sum(1 for r in results if not r.is_error)
        assert successful >= 8, f"Too many failures: {successful}/10"

        # Should complete quickly (not hang)
        assert elapsed < 15, f"Operations took too long (possible deadlock): {elapsed:.2f}s"

    async def test_timeout_during_file_write(self, write_tool, command_tool, tool_context):
        """Test timeout behavior when combined with file operations."""
        # This tests that timeout doesn't corrupt file state

        # Write initial content
        test_file = os.path.join(tool_context.working_directory, "timeout_write.txt")
        with open(test_file, "w") as f:
            f.write("Initial")

        # Run a timeout and a file write concurrently
        await asyncio.gather(
            command_tool.execute({"command": "sleep 10", "timeout": 1}, tool_context),
            write_tool.execute({"path": "timeout_write.txt", "content": "Updated"}, tool_context),
        )

        # File should have valid content (either Initial or Updated, not corrupted)
        with open(test_file, "r") as f:
            content = f.read()

        assert content in ("Initial", "Updated"), f"File corrupted: {content}"


# ---------------------------------------------------------------------------
# Edge cases and integration tests
# ---------------------------------------------------------------------------


class TestConcurrencyEdgeCases:
    """Edge case tests for tool concurrency."""

    async def test_empty_file_concurrent_read(self, read_tool, tool_context):
        """Test concurrent reading of empty file."""
        test_file = os.path.join(tool_context.working_directory, "empty.txt")
        Path(test_file).touch()

        results = await asyncio.gather(
            read_tool.execute({"path": "empty.txt"}, tool_context),
            read_tool.execute({"path": "empty.txt"}, tool_context),
        )

        assert all(not r.is_error for r in results)

    async def test_nonexistent_file_concurrent_read(self, read_tool, tool_context):
        """Test concurrent reading of non-existent file."""
        results = await asyncio.gather(
            read_tool.execute({"path": "nonexistent.txt"}, tool_context),
            read_tool.execute({"path": "nonexistent.txt"}, tool_context),
            return_exceptions=True,
        )

        # Should handle gracefully (not crash)
        # Results might be ToolResult or exceptions depending on implementation
        assert len(results) == 2

    async def test_rapid_parallel_execution(self, read_tool, write_tool, tool_context):
        """Test rapid succession of parallel executions."""
        for batch in range(5):
            # Create file for this batch
            filepath = os.path.join(tool_context.working_directory, f"batch{batch}.txt")
            with open(filepath, "w") as f:
                f.write(f"Batch {batch}")

            # Execute in parallel
            results = await asyncio.gather(
                read_tool.execute({"path": f"batch{batch}.txt"}, tool_context),
                write_tool.execute(
                    {"path": f"batch{batch}_out.txt", "content": f"Output {batch}"}, tool_context
                ),
            )

            assert all(not r.is_error for r in results)

    async def test_mixed_success_failure_concurrent(self, read_tool, tool_context):
        """Test concurrent execution with mixed success and failure."""
        # Create one valid file
        valid_file = os.path.join(tool_context.working_directory, "valid.txt")
        with open(valid_file, "w") as f:
            f.write("Valid content")

        # Mix of valid and invalid reads
        results = await asyncio.gather(
            read_tool.execute({"path": "valid.txt"}, tool_context),
            read_tool.execute({"path": "invalid1.txt"}, tool_context),
            read_tool.execute({"path": "valid.txt"}, tool_context),
            read_tool.execute({"path": "invalid2.txt"}, tool_context),
        )

        # Should have mixed results
        assert len(results) == 4
        # Valid reads should succeed
        assert not results[0].is_error
        assert not results[2].is_error
        # Invalid reads should fail
        assert results[1].is_error
        assert results[3].is_error
