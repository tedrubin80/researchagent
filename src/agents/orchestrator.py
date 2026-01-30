"""Orchestrator Agent Implementation.

Coordinates multi-agent research workflows, managing task distribution,
progress tracking, and result synthesis across Perplexity, Claude, and Gemini.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Optional

from src.a2a.protocol import AgentCard, TaskStatus
from src.a2a.messages import (
    A2AMessage,
    Artifact,
    DataPart,
    TaskRequest,
    TaskResponse,
    TextPart,
)
from src.a2a.task_manager import Task, TaskManager
from .base import BaseAgent, AgentRegistry
from .cards import ORCHESTRATOR_CARD

logger = logging.getLogger(__name__)


class WorkflowPhase(str, Enum):
    """Phases of a research workflow."""
    PLANNING = "planning"
    DISCOVERY = "discovery"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class WorkflowState:
    """State of an ongoing research workflow."""
    workflow_id: str
    query: str
    phase: WorkflowPhase
    started_at: datetime
    tasks: dict[str, Task]
    results: dict[str, Any]
    errors: list[str]
    progress: float = 0.0
    final_output: Optional[str] = None


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent that coordinates multi-agent research workflows.

    Workflow:
    1. Planning: Parse query and create research plan
    2. Discovery: Use Perplexity for web search and source discovery
    3. Analysis: Use Claude to analyze and identify gaps
    4. Validation: Use Gemini to cross-validate findings
    5. Synthesis: Use Claude to create final report

    The orchestrator manages:
    - Task creation and distribution
    - Parallel execution where possible
    - Result aggregation
    - Error handling and retries
    """

    def __init__(
        self,
        registry: AgentRegistry,
        task_manager: TaskManager
    ):
        super().__init__(agent_id="orchestrator")
        self._registry = registry
        self._task_manager = task_manager
        self._workflows: dict[str, WorkflowState] = {}

    @property
    def card(self) -> AgentCard:
        return ORCHESTRATOR_CARD

    async def initialize(self) -> None:
        """Initialize the orchestrator."""
        self._initialized = True
        logger.info("Orchestrator agent initialized")

    async def execute(self, task: Task) -> TaskResponse:
        """Execute an orchestration task."""
        try:
            message_text = task.request.message.get_text()
            skill_id = task.request.skill_id
            metadata = task.request.metadata

            if skill_id == "research-workflow":
                return await self._execute_research_workflow(
                    task.id,
                    message_text,
                    metadata
                )
            elif skill_id == "task-routing":
                return await self._route_task(task.id, message_text, metadata)
            else:
                # Default to research workflow
                return await self._execute_research_workflow(
                    task.id,
                    message_text,
                    metadata
                )

        except Exception as e:
            logger.error(f"Orchestrator execution error: {e}")
            return self._create_error_response(task.id, str(e))

    async def execute_streaming(
        self,
        task: Task
    ) -> AsyncIterator[TaskResponse]:
        """Execute research workflow with streaming progress updates."""
        workflow_id = task.id
        query = task.request.message.get_text()
        metadata = task.request.metadata
        depth = metadata.get("depth", "standard")

        # Initialize workflow state
        workflow = WorkflowState(
            workflow_id=workflow_id,
            query=query,
            phase=WorkflowPhase.PLANNING,
            started_at=datetime.utcnow(),
            tasks={},
            results={},
            errors=[]
        )
        self._workflows[workflow_id] = workflow

        try:
            # Phase 1: Planning
            yield TaskResponse.in_progress(
                workflow_id,
                progress=0.1,
                message="🔍 Planning research approach..."
            )
            research_plan = await self._create_research_plan(query, depth)
            workflow.results["plan"] = research_plan
            workflow.phase = WorkflowPhase.DISCOVERY

            # Phase 2: Discovery (Perplexity)
            yield TaskResponse.in_progress(
                workflow_id,
                progress=0.2,
                message="🌐 Searching web sources (Perplexity)..."
            )
            discovery_results = await self._execute_discovery(workflow, research_plan)
            workflow.results["discovery"] = discovery_results
            workflow.phase = WorkflowPhase.ANALYSIS

            yield TaskResponse.in_progress(
                workflow_id,
                progress=0.4,
                message=f"📚 Found {len(discovery_results.get('sources', []))} sources"
            )

            # Phase 3: Analysis (Claude)
            yield TaskResponse.in_progress(
                workflow_id,
                progress=0.5,
                message="🧠 Analyzing findings (Claude)..."
            )
            analysis_results = await self._execute_analysis(workflow, discovery_results)
            workflow.results["analysis"] = analysis_results
            workflow.phase = WorkflowPhase.VALIDATION

            # Check for gaps and do follow-up if needed
            gaps = analysis_results.get("gaps", [])
            if gaps and depth in ["standard", "deep"]:
                yield TaskResponse.in_progress(
                    workflow_id,
                    progress=0.6,
                    message=f"🔄 Addressing {len(gaps)} identified gaps..."
                )
                followup_results = await self._execute_followup(workflow, gaps)
                workflow.results["followup"] = followup_results

            # Phase 4: Validation (Gemini)
            yield TaskResponse.in_progress(
                workflow_id,
                progress=0.7,
                message="✅ Cross-validating findings (Gemini)..."
            )
            validation_results = await self._execute_validation(workflow)
            workflow.results["validation"] = validation_results
            workflow.phase = WorkflowPhase.SYNTHESIS

            # Phase 5: Synthesis (Claude)
            yield TaskResponse.in_progress(
                workflow_id,
                progress=0.85,
                message="📝 Synthesizing final report (Claude)..."
            )
            final_report = await self._execute_synthesis(workflow)
            workflow.final_output = final_report
            workflow.phase = WorkflowPhase.COMPLETE
            workflow.progress = 1.0

            # Create final response
            artifacts = [
                Artifact.markdown_document(final_report, "research_report"),
                Artifact.json_data(
                    data={
                        "workflow_id": workflow_id,
                        "query": query,
                        "depth": depth,
                        "phases_completed": [
                            "planning", "discovery", "analysis",
                            "validation", "synthesis"
                        ],
                        "sources_found": len(discovery_results.get("sources", [])),
                        "duration_seconds": (
                            datetime.utcnow() - workflow.started_at
                        ).total_seconds()
                    },
                    name="workflow_metadata"
                )
            ]

            yield TaskResponse.success(
                workflow_id,
                message=A2AMessage.agent_text(final_report),
                artifacts=artifacts
            )

        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            workflow.phase = WorkflowPhase.FAILED
            workflow.errors.append(str(e))
            yield self._create_error_response(workflow_id, str(e))

    async def _execute_research_workflow(
        self,
        workflow_id: str,
        query: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Execute complete research workflow synchronously."""
        depth = metadata.get("depth", "standard")
        output_format = metadata.get("output_format", "report")

        # Initialize workflow state
        workflow = WorkflowState(
            workflow_id=workflow_id,
            query=query,
            phase=WorkflowPhase.PLANNING,
            started_at=datetime.utcnow(),
            tasks={},
            results={},
            errors=[]
        )
        self._workflows[workflow_id] = workflow

        try:
            # Phase 1: Planning
            logger.info(f"Workflow {workflow_id}: Planning phase")
            research_plan = await self._create_research_plan(query, depth)
            workflow.results["plan"] = research_plan

            # Phase 2: Discovery
            logger.info(f"Workflow {workflow_id}: Discovery phase")
            workflow.phase = WorkflowPhase.DISCOVERY
            discovery_results = await self._execute_discovery(workflow, research_plan)
            workflow.results["discovery"] = discovery_results

            # Phase 3: Analysis
            logger.info(f"Workflow {workflow_id}: Analysis phase")
            workflow.phase = WorkflowPhase.ANALYSIS
            analysis_results = await self._execute_analysis(workflow, discovery_results)
            workflow.results["analysis"] = analysis_results

            # Phase 3b: Follow-up if gaps found
            gaps = analysis_results.get("gaps", [])
            if gaps and depth in ["standard", "deep"]:
                followup_results = await self._execute_followup(workflow, gaps)
                workflow.results["followup"] = followup_results

            # Phase 4: Validation
            logger.info(f"Workflow {workflow_id}: Validation phase")
            workflow.phase = WorkflowPhase.VALIDATION
            validation_results = await self._execute_validation(workflow)
            workflow.results["validation"] = validation_results

            # Phase 5: Synthesis
            logger.info(f"Workflow {workflow_id}: Synthesis phase")
            workflow.phase = WorkflowPhase.SYNTHESIS
            final_report = await self._execute_synthesis(workflow)
            workflow.final_output = final_report
            workflow.phase = WorkflowPhase.COMPLETE

            # Create artifacts
            artifacts = [
                Artifact.markdown_document(final_report, "research_report"),
                Artifact.json_data(
                    data={
                        "workflow_id": workflow_id,
                        "query": query,
                        "depth": depth,
                        "output_format": output_format,
                        "phases_completed": [
                            "planning", "discovery", "analysis",
                            "validation", "synthesis"
                        ],
                        "sources_found": len(discovery_results.get("sources", [])),
                        "gaps_identified": len(gaps),
                        "duration_seconds": (
                            datetime.utcnow() - workflow.started_at
                        ).total_seconds()
                    },
                    name="workflow_metadata"
                )
            ]

            return self._create_text_response(workflow_id, final_report, artifacts)

        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            workflow.phase = WorkflowPhase.FAILED
            workflow.errors.append(str(e))
            return self._create_error_response(workflow_id, str(e))

    async def _create_research_plan(
        self,
        query: str,
        depth: str
    ) -> dict[str, Any]:
        """Create a research plan based on the query."""
        # Define search queries based on depth
        num_queries = {"quick": 2, "standard": 4, "deep": 6}.get(depth, 4)

        # Basic plan structure
        plan = {
            "original_query": query,
            "depth": depth,
            "search_queries": [query],  # Main query
            "focus_areas": [],
            "expected_sources": num_queries * 3
        }

        # Use Claude to expand search queries if available
        claude = self._registry.get("claude")
        if claude and claude._initialized:
            try:
                task = Task(
                    id=f"plan-{datetime.utcnow().timestamp()}",
                    request=TaskRequest.simple(
                        f"""Given this research query: "{query}"

Generate {num_queries} specific search queries that would help research this topic comprehensively.
Also identify 3-5 key focus areas.

Return as JSON:
{{
    "search_queries": ["query1", "query2", ...],
    "focus_areas": ["area1", "area2", ...]
}}"""
                    )
                )
                response = await claude.execute(task)
                if response.message:
                    text = response.message.get_text()
                    # Try to extract JSON
                    import re
                    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                    if json_match:
                        import json
                        extracted = json.loads(json_match.group())
                        plan["search_queries"] = extracted.get("search_queries", [query])
                        plan["focus_areas"] = extracted.get("focus_areas", [])
            except Exception as e:
                logger.warning(f"Could not expand search queries: {e}")

        return plan

    async def _execute_discovery(
        self,
        workflow: WorkflowState,
        plan: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute discovery phase using Perplexity."""
        perplexity = self._registry.get("perplexity")
        if not perplexity or not perplexity._initialized:
            logger.warning("Perplexity not available, skipping discovery")
            return {"sources": [], "raw_results": []}

        search_queries = plan.get("search_queries", [workflow.query])
        results = []
        sources = []

        # Execute searches in parallel
        tasks = []
        for query in search_queries:
            task = Task(
                id=f"search-{hash(query)}",
                request=TaskRequest(
                    message=A2AMessage.user_text(query),
                    skill_id="web-search",
                    metadata={"max_sources": 5, "recency": "month"}
                )
            )
            tasks.append(perplexity.execute(task))

        # Gather results
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(search_results):
            if isinstance(result, Exception):
                logger.error(f"Search failed: {result}")
                continue
            if isinstance(result, TaskResponse) and result.message:
                results.append({
                    "query": search_queries[i] if i < len(search_queries) else "",
                    "content": result.message.get_text()
                })
                # Extract sources from artifacts
                for artifact in result.artifacts:
                    if artifact.name == "search_results":
                        for part in artifact.parts:
                            if isinstance(part, DataPart):
                                sources.extend(part.data.get("sources", []))

        return {
            "sources": sources,
            "raw_results": results,
            "queries_executed": len(search_queries)
        }

    async def _execute_analysis(
        self,
        workflow: WorkflowState,
        discovery_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute analysis phase using Claude."""
        claude = self._registry.get("claude")
        if not claude or not claude._initialized:
            logger.warning("Claude not available, skipping analysis")
            return {"summary": "", "gaps": [], "themes": []}

        # Combine all discovery content
        content = "\n\n".join([
            f"Query: {r['query']}\nResults: {r['content']}"
            for r in discovery_results.get("raw_results", [])
        ])

        # Analysis task
        task = Task(
            id=f"analysis-{workflow.workflow_id}",
            request=TaskRequest(
                message=A2AMessage.user_text(f"""Analyze the following research findings on: "{workflow.query}"

{content}

Provide:
1. Key themes identified
2. Main findings
3. Contradictions or inconsistencies between sources
4. Information gaps that need more research
5. Questions that remain unanswered"""),
                skill_id="gap-identification",
                metadata={"expected_coverage": workflow.results.get("plan", {}).get("focus_areas", [])}
            )
        )

        response = await claude.execute(task)

        analysis = {
            "summary": response.message.get_text() if response.message else "",
            "gaps": [],
            "themes": []
        }

        # Try to extract structured gaps
        if response.message:
            text = response.message.get_text()
            # Simple extraction of gaps (lines starting with "Gap" or numbered gaps)
            import re
            gap_patterns = re.findall(r'(?:Gap|Missing|Need)[:\s]*([^\n]+)', text, re.I)
            analysis["gaps"] = gap_patterns[:5]  # Limit to 5 gaps

        return analysis

    async def _execute_followup(
        self,
        workflow: WorkflowState,
        gaps: list[str]
    ) -> dict[str, Any]:
        """Execute follow-up searches for identified gaps."""
        perplexity = self._registry.get("perplexity")
        if not perplexity or not perplexity._initialized:
            return {"followup_results": []}

        results = []
        for gap in gaps[:3]:  # Limit follow-ups
            task = Task(
                id=f"followup-{hash(gap)}",
                request=TaskRequest(
                    message=A2AMessage.user_text(
                        f"{workflow.query} - specifically: {gap}"
                    ),
                    skill_id="web-search",
                    metadata={"max_sources": 3}
                )
            )
            try:
                response = await perplexity.execute(task)
                if response.message:
                    results.append({
                        "gap": gap,
                        "content": response.message.get_text()
                    })
            except Exception as e:
                logger.error(f"Follow-up search failed: {e}")

        return {"followup_results": results}

    async def _execute_validation(
        self,
        workflow: WorkflowState
    ) -> dict[str, Any]:
        """Execute validation phase using Gemini."""
        gemini = self._registry.get("gemini")
        if not gemini or not gemini._initialized:
            logger.warning("Gemini not available, skipping validation")
            return {"validated": False, "report": ""}

        # Get analysis results
        analysis = workflow.results.get("analysis", {})
        discovery = workflow.results.get("discovery", {})

        content = f"""Research Query: {workflow.query}

Analysis Summary:
{analysis.get('summary', '')}

Sources Found: {len(discovery.get('sources', []))}
"""

        task = Task(
            id=f"validate-{workflow.workflow_id}",
            request=TaskRequest(
                message=A2AMessage.user_text(content),
                skill_id="cross-validate",
                metadata={
                    "claims": [{"claim": analysis.get("summary", "")[:500]}]
                }
            )
        )

        response = await gemini.execute(task)

        return {
            "validated": True,
            "report": response.message.get_text() if response.message else ""
        }

    async def _execute_synthesis(
        self,
        workflow: WorkflowState
    ) -> str:
        """Execute synthesis phase using Claude to create final report."""
        claude = self._registry.get("claude")
        if not claude or not claude._initialized:
            # Fallback to combining results manually
            return self._manual_synthesis(workflow)

        # Gather all results
        discovery = workflow.results.get("discovery", {})
        analysis = workflow.results.get("analysis", {})
        validation = workflow.results.get("validation", {})
        followup = workflow.results.get("followup", {})

        synthesis_content = f"""Create a comprehensive research report on: "{workflow.query}"

## Research Findings

### Discovery Results
{chr(10).join([r.get('content', '') for r in discovery.get('raw_results', [])])}

### Analysis
{analysis.get('summary', '')}

### Follow-up Research
{chr(10).join([f.get('content', '') for f in followup.get('followup_results', [])])}

### Validation
{validation.get('report', '')}

## Instructions
Create a well-structured research report with:
1. Executive Summary
2. Key Findings (organized by theme)
3. Detailed Analysis
4. Validation Notes
5. Conclusions and Recommendations
6. Sources and Citations

Format in clean Markdown."""

        task = Task(
            id=f"synthesis-{workflow.workflow_id}",
            request=TaskRequest(
                message=A2AMessage.user_text(synthesis_content),
                skill_id="synthesis",
                metadata={
                    "output_format": "report",
                    "target_length": "comprehensive"
                }
            )
        )

        response = await claude.execute(task)
        return response.message.get_text() if response.message else self._manual_synthesis(workflow)

    def _manual_synthesis(self, workflow: WorkflowState) -> str:
        """Create a basic report when Claude isn't available."""
        discovery = workflow.results.get("discovery", {})
        analysis = workflow.results.get("analysis", {})

        report = f"""# Research Report: {workflow.query}

## Summary
This report summarizes research findings on the topic.

## Findings
{analysis.get('summary', 'Analysis not available.')}

## Sources
Found {len(discovery.get('sources', []))} sources.

## Generated
{datetime.utcnow().isoformat()}
"""
        return report

    async def _route_task(
        self,
        task_id: str,
        task_description: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Route a task to the most appropriate agent."""
        requirements = metadata.get("requirements", [])

        # Determine best agent based on requirements
        agent_scores = {
            "perplexity": 0,
            "claude": 0,
            "gemini": 0
        }

        # Score based on keywords
        perplexity_keywords = ["search", "web", "current", "news", "sources", "citations"]
        claude_keywords = ["analyze", "synthesis", "write", "summarize", "reason", "document"]
        gemini_keywords = ["image", "video", "visual", "multimodal", "validate", "large"]

        task_lower = task_description.lower()
        req_lower = " ".join(requirements).lower()
        combined = task_lower + " " + req_lower

        for kw in perplexity_keywords:
            if kw in combined:
                agent_scores["perplexity"] += 1

        for kw in claude_keywords:
            if kw in combined:
                agent_scores["claude"] += 1

        for kw in gemini_keywords:
            if kw in combined:
                agent_scores["gemini"] += 1

        # Select best agent
        best_agent = max(agent_scores, key=agent_scores.get)

        return self._create_text_response(
            task_id,
            f"Recommended agent: {best_agent}",
            artifacts=[
                Artifact.json_data(
                    data={
                        "recommended_agent": best_agent,
                        "scores": agent_scores,
                        "task": task_description,
                        "requirements": requirements
                    },
                    name="routing_decision"
                )
            ]
        )

    def get_workflow_status(self, workflow_id: str) -> Optional[dict[str, Any]]:
        """Get status of a workflow."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None

        return {
            "workflow_id": workflow_id,
            "query": workflow.query,
            "phase": workflow.phase.value,
            "progress": workflow.progress,
            "started_at": workflow.started_at.isoformat(),
            "errors": workflow.errors,
            "has_output": workflow.final_output is not None
        }

    async def health_check(self) -> dict[str, Any]:
        """Check orchestrator and managed agents health."""
        base = await super().health_check()
        base["managed_agents"] = {}

        for agent_id in ["perplexity", "claude", "gemini"]:
            agent = self._registry.get(agent_id)
            if agent:
                try:
                    agent_health = await agent.health_check()
                    base["managed_agents"][agent_id] = agent_health
                except Exception as e:
                    base["managed_agents"][agent_id] = {"status": "error", "error": str(e)}
            else:
                base["managed_agents"][agent_id] = {"status": "not_registered"}

        return base
