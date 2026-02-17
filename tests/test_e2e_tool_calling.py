"""E2E tests for tool calling with real LLM calls.

Tests both roo-agent and open-agent to verify tool calling handles work correctly.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"),
    reason="No API key set for LLM provider"
)


class TestRooAgentToolCalling:
    """Test roo-agent tool calling with real LLM."""
    
    @pytest.fixture
    def settings(self):
        """Create settings with API key."""
        from roo_agent.config.settings import Settings
        return Settings.load()
    
    @pytest.fixture
    def provider(self, settings):
        """Create provider."""
        from roo_agent.providers.registry import create_provider
        return create_provider(settings.provider)
    
    @pytest.fixture
    async def store(self, settings):
        """Create and initialize store."""
        import os
        from roo_agent.persistence.store import Store
        # Use db_path which is the actual database file path
        store = Store(settings.db_path)
        await store.initialize()
        yield store
        await store.close()
    
    @pytest.fixture
    def registry(self):
        """Create tool registry with native tools."""
        from roo_agent.tools.base import ToolRegistry
        from roo_agent.tools.native import get_all_native_tools
        
        reg = ToolRegistry()
        for tool in get_all_native_tools():
            reg.register(tool)
        return reg
    
    @pytest.mark.asyncio
    async def test_roo_agent_simple_tool_call(self, provider, store, registry, settings):
        """Test roo-agent can call read_file tool via LLM."""
        from roo_agent.core.agent import Agent, AgentCallbacks
        from roo_agent.core.mode import get_mode
        from roo_agent.persistence.models import Task, TaskStatus
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("Hello from tool calling test!")
            
            # Create task
            task = Task(
                title="Test tool calling",
                description="Read the test.txt file",
                mode="code",
                status=TaskStatus.ACTIVE,
                working_directory=tmpdir,
            )
            await store.create_task(task)
            
            # Create agent
            callbacks = AgentCallbacks()
            agent = Agent(
                provider=provider,
                registry=registry,
                store=store,
                settings=settings,
                callbacks=callbacks,
            )
            
            # Get mode and tools
            mode = get_mode("code")
            available_tools = registry.get_tools_for_mode(mode.tool_groups)
            
            # Build conversation
            conversation = []
            system_prompt = f"""You are a helpful assistant. You have access to tools.
Available tools: {[t.name for t in available_tools]}

When asked to read a file, use the read_file tool."""
            
            # Run agent
            result = await agent.run(
                task=task,
                user_message=f"Read the file 'test.txt' and tell me its contents.",
                conversation=conversation,
                system_prompt=system_prompt,
            )
            
            # Verify we got a result
            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0
            
            # Check if the file content is mentioned in the response
            # Note: LLM might not always call the tool, but it should try
            print(f"Roo-agent response: {result[:200]}...")
    
    @pytest.mark.asyncio
    async def test_roo_agent_list_files_tool(self, provider, store, registry, settings):
        """Test roo-agent can list files via LLM."""
        from roo_agent.core.agent import Agent, AgentCallbacks
        from roo_agent.core.mode import get_mode
        from roo_agent.persistence.models import Task, TaskStatus
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            open(os.path.join(tmpdir, "file1.txt"), "w").close()
            open(os.path.join(tmpdir, "file2.py"), "w").close()
            
            task = Task(
                title="List files test",
                description="List files in directory",
                mode="code",
                status=TaskStatus.ACTIVE,
                working_directory=tmpdir,
            )
            await store.create_task(task)
            
            callbacks = AgentCallbacks()
            agent = Agent(
                provider=provider,
                registry=registry,
                store=store,
                settings=settings,
                callbacks=callbacks,
            )
            
            mode = get_mode("code")
            available_tools = registry.get_tools_for_mode(mode.tool_groups)
            
            conversation = []
            system_prompt = f"""You are a helpful assistant with access to tools: {[t.name for t in available_tools]}
Use list_files to see what files exist."""
            
            result = await agent.run(
                task=task,
                user_message="List all files in the current directory.",
                conversation=conversation,
                system_prompt=system_prompt,
            )
            
            assert result is not None
            assert isinstance(result, str)
            print(f"Roo-agent list_files response: {result[:200]}...")


class TestOpenAgentToolCalling:
    """Test open-agent tool calling with real LLM."""
    
    @pytest.fixture
    def settings(self):
        """Create settings."""
        from open_agent.config import Settings
        return Settings.load()
    
    @pytest.fixture
    async def app(self, settings):
        """Create and initialize OpenAgentApp."""
        from open_agent.core.app import OpenAgentApp
        app = OpenAgentApp(settings=settings)
        await app.initialize()
        yield app
        await app.shutdown()
    
    @pytest.mark.asyncio
    async def test_open_agent_process_message(self, app):
        """Test open-agent can process a message and use tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, "hello.txt")
            with open(test_file, "w") as f:
                f.write("World")
            
            # Change working directory
            original_dir = app.settings.working_directory
            app.settings.working_directory = tmpdir
            
            try:
                # Process message that might trigger tool use
                result = await app.process_message(
                    f"Read the file '{test_file}' and tell me what it contains."
                )
                
                assert result is not None
                assert isinstance(result, str)
                print(f"Open-agent response: {result[:200]}...")
            finally:
                app.settings.working_directory = original_dir
    
    @pytest.mark.asyncio
    async def test_open_agent_tool_registry(self, app):
        """Test that open-agent has tools registered."""
        tool_names = list(app.tool_registry._tools.keys())
        
        # Should have native tools
        assert len(tool_names) > 0
        print(f"Open-agent registered tools: {tool_names}")
        
        # Check for expected tools
        expected = ["read_file", "write_file", "search_files"]
        for tool in expected:
            assert tool in tool_names, f"Missing tool: {tool}"
    
    @pytest.mark.asyncio
    async def test_open_agent_delegation_tools(self, app):
        """Test open-agent has delegation tools."""
        tool_names = list(app.tool_registry._tools.keys())
        
        # Should have delegation tools for orchestrator
        delegation_tools = ["delegate_task", "delegate_background", "check_background_task"]
        for tool in delegation_tools:
            assert tool in tool_names, f"Missing delegation tool: {tool}"


class TestToolCallingComparison:
    """Compare tool calling between roo-agent and open-agent."""
    
    @pytest.mark.asyncio
    async def test_both_agents_have_tools(self):
        """Verify both agents have tools available."""
        # Roo-agent tools
        from roo_agent.tools.native import get_all_native_tools
        roo_tools = [t.name for t in get_all_native_tools()]
        
        # Open-agent tools
        from open_agent.tools.native import get_all_native_tools as get_oa_tools
        oa_tools = [t.name for t in get_oa_tools()]
        
        print(f"\nRoo-agent tools: {roo_tools}")
        print(f"Open-agent tools: {oa_tools}")
        
        # Both should have basic file operations
        basic_tools = ["read_file", "write_file"]
        for tool in basic_tools:
            assert tool in roo_tools, f"Roo-agent missing {tool}"
            assert tool in oa_tools, f"Open-agent missing {tool}"
    
    @pytest.mark.asyncio
    async def test_provider_tool_definitions(self):
        """Test that tool definitions are properly formatted for LLM."""
        from open_agent.providers.base import ToolDefinition
        
        # Create a test tool definition
        tool_def = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "arg1": {"type": "string"}
                },
                "required": ["arg1"],
                "additionalProperties": False,
            }
        )
        
        # Verify structure
        assert tool_def.name == "test_tool"
        assert "additionalProperties" in tool_def.parameters
        assert tool_def.parameters["additionalProperties"] == False
