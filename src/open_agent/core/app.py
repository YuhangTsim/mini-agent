"""OpenAgentApp: wires all subsystems together and manages lifecycle."""

from __future__ import annotations


from open_agent.agents.base import BaseAgent
from open_agent.agents.registry import AgentRegistry
from open_agent.bus import EventBus
from open_agent.config import AgentConfig, Settings
from open_agent.core.background import BackgroundTaskManager
from open_agent.core.delegation import DelegationManager
from open_agent.core.session import SessionCallbacks, SessionProcessor
from open_agent.hooks import HookRegistry
from open_agent.persistence.models import AgentRun, AgentRunStatus, Session
from open_agent.persistence.store import Store
from open_agent.prompts.builder import PromptBuilder
from open_agent.providers.registry import ProviderRegistry
from open_agent.tools.base import ToolRegistry
from open_agent.tools.native import get_all_native_tools
from open_agent.tools.agent import get_all_delegation_tools
from open_agent.tools.permissions import PermissionChecker


class OpenAgentApp:
    """Top-level application that wires all subsystems together.

    Usage::

        app = OpenAgentApp(settings)
        await app.initialize()
        result = await app.process_message("Read the file main.py")
        await app.shutdown()
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()

        # Core subsystems
        self.bus = EventBus()
        self.store = Store(self.settings.db_path)
        self.hook_registry = HookRegistry()

        # Tools
        self.tool_registry = ToolRegistry()
        self.permission_checker = PermissionChecker(self.settings.permissions)

        # Providers
        self.provider_registry = ProviderRegistry(self.settings.provider)

        # Agents
        self.agent_registry = AgentRegistry()
        self.prompt_builder = PromptBuilder()

        # Orchestration
        self.delegation_manager = DelegationManager(
            agent_registry=self.agent_registry,
            bus=self.bus,
            store=self.store,
            max_depth=self.settings.max_delegation_depth,
        )
        self.background_manager = BackgroundTaskManager(
            bus=self.bus,
            store=self.store,
            delegation_manager=self.delegation_manager,
            max_concurrent=self.settings.background_max_concurrent,
        )

        # Current session
        self._session: Session | None = None
        self._callbacks: SessionCallbacks | None = None

    async def initialize(self) -> None:
        """Initialize all subsystems."""
        self.settings.ensure_dirs()
        await self.store.initialize()

        # Register all tools
        for tool in get_all_native_tools():
            self.tool_registry.register(tool)
        for tool in get_all_delegation_tools():
            self.tool_registry.register(tool)

        # Register all agents from config
        self._register_agents()

        # Wire the delegation manager's processor factory
        self.delegation_manager.set_processor_factory(self._create_child_processor)

    def set_callbacks(self, callbacks: SessionCallbacks) -> None:
        """Set UI callbacks for session processing."""
        self._callbacks = callbacks

    def _register_agents(self) -> None:
        """Register agents from settings using simple concrete implementations."""
        for role, agent_config in self.settings.agents.items():
            agent = _SimpleAgent(agent_config, self.prompt_builder)
            self.agent_registry.register(agent)

    def _create_child_processor(
        self,
        agent: BaseAgent,
        parent_run: AgentRun,
    ) -> SessionProcessor:
        """Factory for creating child SessionProcessors during delegation."""
        provider = self.provider_registry.get_provider(agent.config)

        return SessionProcessor(
            agent=agent,
            provider=provider,
            tool_registry=self.tool_registry,
            permission_checker=self.permission_checker,
            hook_registry=self.hook_registry,
            bus=self.bus,
            store=self.store,
            working_directory=self.settings.working_directory,
            callbacks=self._callbacks,
            delegation_handler=self.delegation_manager.delegate,
            background_handler=self.background_manager.submit,
            background_status_handler=self.background_manager.get_status,
        )

    async def process_message(
        self,
        user_message: str,
        agent_role: str | None = None,
    ) -> str:
        """Process a user message through the agent system.

        Creates a session if needed, routes to the appropriate agent,
        and returns the final response.
        """
        # Ensure session exists
        if self._session is None:
            self._session = Session(
                title=user_message[:100],
                working_directory=self.settings.working_directory,
            )
            await self.store.create_session(self._session)

        # Determine which agent to use
        role = agent_role or self.settings.default_agent
        agent = self.agent_registry.get_required(role)
        provider = self.provider_registry.get_provider(agent.config)

        # Create agent run
        run = AgentRun(
            session_id=self._session.id,
            agent_role=role,
            status=AgentRunStatus.RUNNING,
            description=user_message[:200],
        )
        await self.store.create_agent_run(run)

        # Create processor
        processor = SessionProcessor(
            agent=agent,
            provider=provider,
            tool_registry=self.tool_registry,
            permission_checker=self.permission_checker,
            hook_registry=self.hook_registry,
            bus=self.bus,
            store=self.store,
            working_directory=self.settings.working_directory,
            callbacks=self._callbacks,
            delegation_handler=self.delegation_manager.delegate,
            background_handler=self.background_manager.submit,
            background_status_handler=self.background_manager.get_status,
        )

        # Process
        result = await processor.process(
            agent_run=run,
            user_message=user_message,
        )

        return result

    async def shutdown(self) -> None:
        """Clean up resources."""
        await self.store.close()
        self.bus.clear()


class _SimpleAgent(BaseAgent):
    """Simple agent implementation that uses PromptBuilder for system prompts."""

    def __init__(self, config: AgentConfig, prompt_builder: PromptBuilder) -> None:
        super().__init__(config)
        self._prompt_builder = prompt_builder

    def get_system_prompt(self, context: dict | None = None) -> str:
        working_dir = (context or {}).get("working_directory", "")
        tools = []  # Tools are handled separately via tool_definitions
        return self._prompt_builder.build(
            agent_config=self.config,
            working_directory=working_dir,
            tools=tools,
        )
