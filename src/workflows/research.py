"""Research Workflow Implementation.

Provides a high-level interface for executing multi-agent research workflows
with configurable depth, output formats, and agent preferences.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

from src.a2a.messages import A2AMessage, Artifact, TaskRequest, TaskResponse
from src.a2a.task_manager import Task, TaskManager
from src.agents.base import AgentRegistry
from src.agents.orchestrator import OrchestratorAgent, WorkflowPhase

logger = logging.getLogger(__name__)


class ResearchDepth(str, Enum):
    """Depth of research to conduct."""
    QUICK = "quick"       # Fast, 1-2 searches, basic analysis
    STANDARD = "standard"  # Balanced, 3-4 searches, full analysis
    DEEP = "deep"         # Thorough, 5+ searches, extensive validation


class OutputFormat(str, Enum):
    """Format for the research output."""
    REPORT = "report"           # Full structured report
    SUMMARY = "summary"         # Executive summary only
    BULLET_POINTS = "bullets"   # Key points as bullets
    RAW = "raw"                 # Raw findings without synthesis


@dataclass
class ResearchConfig:
    """Configuration for a research workflow."""
    depth: ResearchDepth = ResearchDepth.STANDARD
    output_format: OutputFormat = OutputFormat.REPORT
    max_sources: int = 10
    include_validation: bool = True
    include_followup: bool = True
    timeout_seconds: int = 300
    preferred_agents: dict[str, str] = field(default_factory=dict)
    custom_prompts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth": self.depth.value,
            "output_format": self.output_format.value,
            "max_sources": self.max_sources,
            "include_validation": self.include_validation,
            "include_followup": self.include_followup,
            "timeout_seconds": self.timeout_seconds
        }


@dataclass
class ResearchResult:
    """Result of a research workflow."""
    query: str
    report: str
    sources: list[dict[str, Any]]
    metadata: dict[str, Any]
    artifacts: list[Artifact]
    duration_seconds: float
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "report": self.report,
            "sources_count": len(self.sources),
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "error": self.error
        }


# Type for progress callback
ProgressCallback = Callable[[str, float, str], None]


class ResearchWorkflow:
    """High-level interface for executing research workflows.

    Example usage:
        ```python
        workflow = ResearchWorkflow(registry, task_manager)
        result = await workflow.execute("Impact of AI on healthcare 2024")

        # Or with streaming
        async for update in workflow.execute_streaming(query):
            print(f"Progress: {update.progress} - {update.message}")
        ```
    """

    def __init__(
        self,
        registry: AgentRegistry,
        task_manager: TaskManager,
        default_config: Optional[ResearchConfig] = None
    ):
        self._registry = registry
        self._task_manager = task_manager
        self._default_config = default_config or ResearchConfig()
        self._orchestrator = OrchestratorAgent(registry, task_manager)

    async def initialize(self) -> None:
        """Initialize the workflow and its agents."""
        await self._orchestrator.initialize()
        logger.info("Research workflow initialized")

    async def execute(
        self,
        query: str,
        config: Optional[ResearchConfig] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> ResearchResult:
        """Execute a research workflow and return the result.

        Args:
            query: The research query/topic
            config: Optional configuration overrides
            progress_callback: Optional callback for progress updates

        Returns:
            ResearchResult with the final report and metadata
        """
        config = config or self._default_config
        start_time = datetime.utcnow()
        workflow_id = f"research-{start_time.timestamp()}"

        try:
            # Create task request
            task = Task(
                id=workflow_id,
                request=TaskRequest(
                    message=A2AMessage.user_text(query),
                    skill_id="research-workflow",
                    metadata=config.to_dict()
                )
            )

            # Execute through orchestrator
            response = await self._orchestrator.execute(task)

            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()

            if response.status == "completed":
                return ResearchResult(
                    query=query,
                    report=response.message.get_text() if response.message else "",
                    sources=self._extract_sources(response),
                    metadata={
                        "workflow_id": workflow_id,
                        "config": config.to_dict(),
                        "response_metadata": response.metadata
                    },
                    artifacts=response.artifacts,
                    duration_seconds=duration,
                    success=True
                )
            else:
                return ResearchResult(
                    query=query,
                    report="",
                    sources=[],
                    metadata={"workflow_id": workflow_id},
                    artifacts=[],
                    duration_seconds=duration,
                    success=False,
                    error=response.error
                )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Research workflow failed: {e}")
            return ResearchResult(
                query=query,
                report="",
                sources=[],
                metadata={"workflow_id": workflow_id},
                artifacts=[],
                duration_seconds=duration,
                success=False,
                error=str(e)
            )

    async def execute_streaming(
        self,
        query: str,
        config: Optional[ResearchConfig] = None
    ) -> AsyncIterator[TaskResponse]:
        """Execute a research workflow with streaming progress updates.

        Args:
            query: The research query/topic
            config: Optional configuration overrides

        Yields:
            TaskResponse objects with progress updates and final result
        """
        config = config or self._default_config
        start_time = datetime.utcnow()
        workflow_id = f"research-{start_time.timestamp()}"

        task = Task(
            id=workflow_id,
            request=TaskRequest(
                message=A2AMessage.user_text(query),
                skill_id="research-workflow",
                metadata=config.to_dict()
            )
        )

        async for response in self._orchestrator.execute_streaming(task):
            yield response

    def _extract_sources(self, response: TaskResponse) -> list[dict[str, Any]]:
        """Extract sources from response artifacts."""
        sources = []
        for artifact in response.artifacts:
            if artifact.name == "workflow_metadata":
                for part in artifact.parts:
                    if hasattr(part, 'data'):
                        # This might contain sources info
                        pass
            elif "sources" in (artifact.name or ""):
                for part in artifact.parts:
                    if hasattr(part, 'data') and isinstance(part.data, dict):
                        sources.extend(part.data.get("sources", []))
        return sources

    async def quick_search(self, query: str) -> ResearchResult:
        """Perform a quick search with minimal processing."""
        config = ResearchConfig(
            depth=ResearchDepth.QUICK,
            output_format=OutputFormat.SUMMARY,
            include_validation=False,
            include_followup=False,
            timeout_seconds=60
        )
        return await self.execute(query, config)

    async def deep_research(self, query: str) -> ResearchResult:
        """Perform comprehensive deep research."""
        config = ResearchConfig(
            depth=ResearchDepth.DEEP,
            output_format=OutputFormat.REPORT,
            max_sources=20,
            include_validation=True,
            include_followup=True,
            timeout_seconds=600
        )
        return await self.execute(query, config)

    def get_status(self, workflow_id: str) -> Optional[dict[str, Any]]:
        """Get status of a running workflow."""
        return self._orchestrator.get_workflow_status(workflow_id)


class BatchResearchWorkflow:
    """Execute multiple research queries in batch."""

    def __init__(self, workflow: ResearchWorkflow):
        self._workflow = workflow

    async def execute_batch(
        self,
        queries: list[str],
        config: Optional[ResearchConfig] = None,
        max_parallel: int = 3
    ) -> list[ResearchResult]:
        """Execute multiple research queries with controlled parallelism.

        Args:
            queries: List of research queries
            config: Configuration to use for all queries
            max_parallel: Maximum parallel workflows

        Returns:
            List of ResearchResults in same order as queries
        """
        semaphore = asyncio.Semaphore(max_parallel)

        async def run_with_semaphore(query: str) -> ResearchResult:
            async with semaphore:
                return await self._workflow.execute(query, config)

        tasks = [run_with_semaphore(q) for q in queries]
        return await asyncio.gather(*tasks)

    async def execute_batch_streaming(
        self,
        queries: list[str],
        config: Optional[ResearchConfig] = None
    ) -> AsyncIterator[tuple[int, TaskResponse]]:
        """Execute batch with streaming, yielding (index, response) tuples."""
        for i, query in enumerate(queries):
            async for response in self._workflow.execute_streaming(query, config):
                yield (i, response)
