"""Base Agent Interface for A2A Protocol.

Defines the abstract interface that all agent implementations must follow,
ensuring consistent behavior across different AI providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional
import logging

from src.a2a.protocol import AgentCard, TaskStatus
from src.a2a.messages import (
    A2AMessage,
    Artifact,
    TaskRequest,
    TaskResponse,
)
from src.a2a.task_manager import Task, TaskManager

logger = logging.getLogger(__name__)


@dataclass
class ProviderPriority:
    """Priority configuration for a skill's provider fallback chain."""
    skill_id: str
    primary: str  # Primary agent ID
    fallbacks: list[str] = field(default_factory=list)  # Ordered fallback agent IDs

    def get_ordered_agents(self) -> list[str]:
        """Get all agents in priority order (primary first, then fallbacks)."""
        return [self.primary] + self.fallbacks


# Default provider priorities
DEFAULT_PRIORITIES: dict[str, ProviderPriority] = {
    "synthesis": ProviderPriority(
        skill_id="synthesis",
        primary="claude",
        fallbacks=["ollama"]
    ),
    "document-analysis": ProviderPriority(
        skill_id="document-analysis",
        primary="claude",
        fallbacks=["ollama", "gemini"]
    ),
    "web-search": ProviderPriority(
        skill_id="web-search",
        primary="perplexity",
        fallbacks=[]  # No local fallback for web search
    ),
    "cross-validate": ProviderPriority(
        skill_id="cross-validate",
        primary="gemini",
        fallbacks=["claude", "ollama"]
    ),
    "general-query": ProviderPriority(
        skill_id="general-query",
        primary="claude",
        fallbacks=["ollama"]
    ),
}


class BaseAgent(ABC):
    """Abstract base class for all A2A agents.

    Each agent implementation must:
    1. Provide an agent card describing its capabilities
    2. Implement the execute method for processing tasks
    3. Optionally support streaming responses
    """

    def __init__(self, agent_id: str, api_key: Optional[str] = None):
        self.agent_id = agent_id
        self.api_key = api_key
        self._initialized = False

    @property
    @abstractmethod
    def card(self) -> AgentCard:
        """Return the agent's capability card."""
        pass

    @property
    def name(self) -> str:
        """Agent display name."""
        return self.card.name

    async def initialize(self) -> None:
        """Initialize the agent (e.g., validate API key, warm up connections)."""
        self._initialized = True

    async def shutdown(self) -> None:
        """Clean up agent resources."""
        self._initialized = False

    @abstractmethod
    async def execute(self, task: Task) -> TaskResponse:
        """Execute a task and return the response.

        This is the main entry point for task execution.
        Implementations should:
        1. Parse the task request
        2. Call the underlying AI provider
        3. Format the response as TaskResponse

        Args:
            task: The task to execute

        Returns:
            TaskResponse with results or error
        """
        pass

    async def execute_streaming(
        self,
        task: Task
    ) -> AsyncIterator[TaskResponse]:
        """Execute a task with streaming responses.

        Override this method to provide streaming support.
        Default implementation just yields the final result.
        """
        result = await self.execute(task)
        yield result

    def supports_streaming(self) -> bool:
        """Check if this agent supports streaming."""
        return self.card.capabilities.streaming

    def has_skill(self, skill_id: str) -> bool:
        """Check if agent has a specific skill."""
        return self.card.has_skill(skill_id)

    def get_supported_skills(self) -> list[str]:
        """Get list of skill IDs this agent supports."""
        return [skill.id for skill in self.card.skills]

    async def health_check(self) -> dict[str, Any]:
        """Check agent health and connectivity."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "initialized": self._initialized,
            "status": "healthy" if self._initialized else "not_initialized"
        }

    def _create_text_response(
        self,
        task_id: str,
        text: str,
        artifacts: Optional[list[Artifact]] = None
    ) -> TaskResponse:
        """Helper to create a text response."""
        return TaskResponse.success(
            task_id=task_id,
            message=A2AMessage.agent_text(text),
            artifacts=artifacts
        )

    def _create_error_response(
        self,
        task_id: str,
        error: str
    ) -> TaskResponse:
        """Helper to create an error response."""
        return TaskResponse.error(task_id=task_id, error_message=error)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.agent_id} name={self.name}>"


class AgentRegistry:
    """Registry for managing multiple agents in an A2A system.

    Provides:
    - Agent registration and lookup
    - Task routing based on skills
    - Health monitoring
    - Provider priority and fallback support
    """

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}
        self._skill_index: dict[str, list[str]] = {}  # skill_id -> [agent_ids]
        self._priorities: dict[str, ProviderPriority] = DEFAULT_PRIORITIES.copy()

    def register(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[agent.agent_id] = agent

        # Index skills
        for skill in agent.card.skills:
            if skill.id not in self._skill_index:
                self._skill_index[skill.id] = []
            self._skill_index[skill.id].append(agent.agent_id)

        logger.info(f"Registered agent: {agent.agent_id} ({agent.name})")

    def unregister(self, agent_id: str) -> Optional[BaseAgent]:
        """Unregister an agent."""
        agent = self._agents.pop(agent_id, None)
        if agent:
            # Remove from skill index
            for skill in agent.card.skills:
                if skill.id in self._skill_index:
                    self._skill_index[skill.id] = [
                        aid for aid in self._skill_index[skill.id]
                        if aid != agent_id
                    ]
            logger.info(f"Unregistered agent: {agent_id}")
        return agent

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_by_skill(self, skill_id: str) -> list[BaseAgent]:
        """Get all agents that have a specific skill."""
        agent_ids = self._skill_index.get(skill_id, [])
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_best_agent_for_skill(self, skill_id: str) -> Optional[BaseAgent]:
        """Get the best agent for a skill (first registered)."""
        agents = self.get_by_skill(skill_id)
        return agents[0] if agents else None

    def list_agents(self) -> list[BaseAgent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def list_skills(self) -> dict[str, list[str]]:
        """Get all skills and their providing agents."""
        return dict(self._skill_index)

    async def initialize_all(self) -> dict[str, bool]:
        """Initialize all registered agents."""
        results = {}
        for agent_id, agent in self._agents.items():
            try:
                await agent.initialize()
                results[agent_id] = True
            except Exception as e:
                logger.error(f"Failed to initialize {agent_id}: {e}")
                results[agent_id] = False
        return results

    async def shutdown_all(self) -> None:
        """Shutdown all registered agents."""
        for agent in self._agents.values():
            try:
                await agent.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down {agent.agent_id}: {e}")

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """Check health of all agents."""
        results = {}
        for agent_id, agent in self._agents.items():
            try:
                results[agent_id] = await agent.health_check()
            except Exception as e:
                results[agent_id] = {
                    "agent_id": agent_id,
                    "status": "error",
                    "error": str(e)
                }
        return results

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._agents

    # =========================================================================
    # Provider Priority and Fallback Methods
    # =========================================================================

    def set_priorities(self, priorities: dict[str, ProviderPriority]) -> None:
        """Configure provider priorities for skills.

        Args:
            priorities: Dict mapping skill_id to ProviderPriority config
        """
        self._priorities.update(priorities)
        logger.info(f"Updated priorities for skills: {list(priorities.keys())}")

    def get_priorities(self) -> dict[str, ProviderPriority]:
        """Get current priority configuration."""
        return self._priorities.copy()

    def set_priority(
        self,
        skill_id: str,
        primary: str,
        fallbacks: Optional[list[str]] = None
    ) -> None:
        """Set priority for a single skill.

        Args:
            skill_id: The skill to configure
            primary: Primary agent ID
            fallbacks: Ordered list of fallback agent IDs
        """
        self._priorities[skill_id] = ProviderPriority(
            skill_id=skill_id,
            primary=primary,
            fallbacks=fallbacks or []
        )
        logger.info(f"Set priority for {skill_id}: primary={primary}, fallbacks={fallbacks}")

    def get_agent_with_fallback(self, skill_id: str) -> Optional[BaseAgent]:
        """Get the best available agent for a skill, considering priorities and health.

        Returns the primary agent if available and healthy, otherwise tries
        fallbacks in order until one is found.

        Args:
            skill_id: The skill to find an agent for

        Returns:
            The best available agent, or None if no agent can handle the skill
        """
        priority = self._priorities.get(skill_id)

        if priority:
            # Use configured priority order
            agent_order = priority.get_ordered_agents()
        else:
            # No priority configured, use skill index
            agent_order = self._skill_index.get(skill_id, [])

        for agent_id in agent_order:
            agent = self._agents.get(agent_id)
            if agent and agent._initialized and agent.has_skill(skill_id):
                logger.debug(f"Selected agent {agent_id} for skill {skill_id}")
                return agent

        # Fallback to any agent with the skill
        agents = self.get_by_skill(skill_id)
        for agent in agents:
            if agent._initialized:
                logger.debug(f"Using fallback agent {agent.agent_id} for skill {skill_id}")
                return agent

        logger.warning(f"No available agent found for skill: {skill_id}")
        return None

    async def execute_with_fallback(
        self,
        skill_id: str,
        task: Task,
        max_attempts: int = 3
    ) -> TaskResponse:
        """Execute a task with automatic fallback on failure.

        Tries the primary agent first, then falls back to alternatives
        if the primary fails.

        Args:
            skill_id: The skill to use
            task: The task to execute
            max_attempts: Maximum number of agents to try

        Returns:
            TaskResponse from the first successful agent
        """
        priority = self._priorities.get(skill_id)
        if priority:
            agent_order = priority.get_ordered_agents()
        else:
            agent_order = self._skill_index.get(skill_id, [])

        last_error = None
        attempts = 0

        for agent_id in agent_order:
            if attempts >= max_attempts:
                break

            agent = self._agents.get(agent_id)
            if not agent or not agent._initialized:
                continue

            if not agent.has_skill(skill_id):
                continue

            attempts += 1
            try:
                logger.info(f"Attempting execution with agent: {agent_id}")
                response = await agent.execute(task)

                # Check if response indicates an error
                if response.status == "failed":
                    last_error = response.error or "Unknown error"
                    logger.warning(f"Agent {agent_id} failed: {last_error}, trying fallback...")
                    continue

                logger.info(f"Successfully executed task with agent: {agent_id}")
                return response

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Agent {agent_id} raised exception: {e}, trying fallback...")
                continue

        # All attempts failed
        error_msg = f"All {attempts} agents failed for skill {skill_id}. Last error: {last_error}"
        logger.error(error_msg)
        return TaskResponse.error(task_id=task.id, error_message=error_msg)

    async def execute_with_fallback_streaming(
        self,
        skill_id: str,
        task: Task,
        max_attempts: int = 3
    ) -> AsyncIterator[TaskResponse]:
        """Execute a task with streaming and automatic fallback.

        Args:
            skill_id: The skill to use
            task: The task to execute
            max_attempts: Maximum number of agents to try

        Yields:
            TaskResponse objects from the first successful agent
        """
        priority = self._priorities.get(skill_id)
        if priority:
            agent_order = priority.get_ordered_agents()
        else:
            agent_order = self._skill_index.get(skill_id, [])

        last_error = None
        attempts = 0

        for agent_id in agent_order:
            if attempts >= max_attempts:
                break

            agent = self._agents.get(agent_id)
            if not agent or not agent._initialized:
                continue

            if not agent.has_skill(skill_id):
                continue

            attempts += 1
            try:
                logger.info(f"Attempting streaming execution with agent: {agent_id}")
                had_success = False

                async for response in agent.execute_streaming(task):
                    if response.status == "failed":
                        last_error = response.error or "Unknown error"
                        logger.warning(f"Agent {agent_id} streaming failed: {last_error}")
                        break
                    had_success = True
                    yield response

                if had_success:
                    logger.info(f"Successfully executed streaming task with agent: {agent_id}")
                    return

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Agent {agent_id} streaming exception: {e}, trying fallback...")
                continue

        # All attempts failed
        error_msg = f"All {attempts} agents failed for skill {skill_id}. Last error: {last_error}"
        logger.error(error_msg)
        yield TaskResponse.error(task_id=task.id, error_message=error_msg)
