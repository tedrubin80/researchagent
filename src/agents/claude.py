"""Claude Agent Implementation.

Handles analysis, synthesis, and structured output generation
using the Anthropic Claude API.
"""

import json
import logging
from typing import Any, AsyncIterator, Optional

from anthropic import AsyncAnthropic

from src.a2a.protocol import AgentCard
from src.a2a.messages import (
    A2AMessage,
    Artifact,
    DataPart,
    TaskResponse,
    TextPart,
)
from src.a2a.task_manager import Task
from .base import BaseAgent
from .cards import CLAUDE_CARD

logger = logging.getLogger(__name__)


class ClaudeAgent(BaseAgent):
    """Claude AI agent for analysis and synthesis.

    Uses Anthropic's Claude API for:
    - Document analysis
    - Research synthesis
    - Gap identification
    - Structured output generation
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(agent_id="claude", api_key=api_key)
        self._client: Optional[AsyncAnthropic] = None
        self._model = model or self.DEFAULT_MODEL

    @property
    def card(self) -> AgentCard:
        return CLAUDE_CARD

    async def initialize(self) -> None:
        """Initialize the Claude client."""
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self._client = AsyncAnthropic(api_key=self.api_key)
        self._initialized = True
        logger.info(f"Claude agent initialized with model: {self._model}")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.close()
        self._initialized = False

    async def execute(self, task: Task) -> TaskResponse:
        """Execute a task using Claude."""
        if not self._initialized or not self._client:
            return self._create_error_response(
                task.id,
                "Claude agent not initialized"
            )

        try:
            message_text = task.request.message.get_text()
            skill_id = task.request.skill_id
            metadata = task.request.metadata

            # Route to appropriate handler
            if skill_id == "document-analysis":
                return await self._document_analysis(task.id, message_text, metadata)
            elif skill_id == "synthesis":
                return await self._synthesis(task.id, message_text, metadata)
            elif skill_id == "gap-identification":
                return await self._gap_identification(task.id, message_text, metadata)
            elif skill_id == "structured-output":
                return await self._structured_output(task.id, message_text, metadata)
            else:
                # Default to general analysis
                return await self._general_analysis(task.id, message_text)

        except Exception as e:
            logger.error(f"Claude execution error: {e}")
            return self._create_error_response(task.id, str(e))

    async def execute_streaming(self, task: Task) -> AsyncIterator[TaskResponse]:
        """Execute with streaming responses."""
        if not self._initialized or not self._client:
            yield self._create_error_response(
                task.id,
                "Claude agent not initialized"
            )
            return

        message_text = task.request.message.get_text()

        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": message_text}]
            ) as stream:
                accumulated_text = ""
                async for text in stream.text_stream:
                    accumulated_text += text
                    yield TaskResponse.in_progress(
                        task_id=task.id,
                        progress=0.5,
                        message=accumulated_text
                    )

            # Final response
            yield self._create_text_response(task.id, accumulated_text)

        except Exception as e:
            logger.error(f"Claude streaming error: {e}")
            yield self._create_error_response(task.id, str(e))

    async def _document_analysis(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Analyze a document and extract insights."""
        analysis_type = metadata.get("analysis_type", "detailed")
        focus_areas = metadata.get("focus_areas", [])

        focus_instruction = ""
        if focus_areas:
            focus_instruction = f"\nFocus particularly on: {', '.join(focus_areas)}"

        prompts = {
            "summary": f"Provide a concise summary of the following document:{focus_instruction}\n\n{content}",
            "detailed": f"""Analyze the following document in detail:{focus_instruction}

Provide:
1. Executive Summary
2. Key Findings
3. Important Details
4. Implications
5. Notable Quotes or Data Points

Document:
{content}""",
            "themes": f"""Identify and analyze the main themes in the following document:{focus_instruction}

For each theme:
- Name and description
- Supporting evidence from the text
- Significance

Document:
{content}""",
            "entities": f"""Extract all named entities from the following document:{focus_instruction}

Categories:
- People
- Organizations
- Locations
- Dates/Times
- Technical Terms
- Key Concepts

Document:
{content}"""
        }

        prompt = prompts.get(analysis_type, prompts["detailed"])

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        artifacts = [
            Artifact.json_data(
                data={
                    "analysis_type": analysis_type,
                    "focus_areas": focus_areas,
                    "content_length": len(content),
                    "model": self._model
                },
                name="analysis_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _synthesis(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Synthesize multiple sources into coherent analysis."""
        sources = metadata.get("sources", [])
        output_format = metadata.get("output_format", "report")
        target_length = metadata.get("target_length", "moderate")

        # Build sources content
        sources_text = content
        if sources:
            sources_text = "\n\n".join([
                f"Source {i+1}: {s.get('citation', 'Unknown')}\n{s.get('content', '')}"
                for i, s in enumerate(sources)
            ])

        length_instructions = {
            "brief": "Keep the synthesis concise (300-500 words).",
            "moderate": "Provide a moderate-length synthesis (800-1200 words).",
            "comprehensive": "Provide a comprehensive synthesis (1500-2500 words)."
        }

        format_instructions = {
            "report": """Format as a structured report with:
- Executive Summary
- Introduction
- Main Findings (organized by theme)
- Analysis and Insights
- Conclusions
- References""",
            "summary": "Format as a cohesive summary paragraph with key takeaways.",
            "bullet_points": "Format as organized bullet points grouped by topic.",
            "narrative": "Format as a flowing narrative that tells the story of the research."
        }

        prompt = f"""Synthesize the following sources into a coherent analysis.

{length_instructions.get(target_length, length_instructions['moderate'])}

{format_instructions.get(output_format, format_instructions['report'])}

When synthesizing:
1. Identify common themes across sources
2. Note any contradictions or disagreements
3. Highlight the most significant findings
4. Maintain proper attribution to sources

Sources:
{sources_text}"""

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        artifacts = [
            Artifact.markdown_document(result_text, "synthesis_report"),
            Artifact.json_data(
                data={
                    "output_format": output_format,
                    "target_length": target_length,
                    "sources_count": len(sources) if sources else 1
                },
                name="synthesis_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _gap_identification(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Identify gaps and contradictions in content."""
        expected_coverage = metadata.get("expected_coverage", [])

        coverage_check = ""
        if expected_coverage:
            coverage_check = f"""
Also check if these expected topics are adequately covered:
{chr(10).join(f'- {topic}' for topic in expected_coverage)}
"""

        prompt = f"""Analyze the following content for gaps, contradictions, and areas needing more research.

Provide:
1. **Information Gaps**: Topics mentioned but not fully explored
2. **Missing Perspectives**: Viewpoints or stakeholders not represented
3. **Contradictions**: Conflicting information within the content
4. **Weak Evidence**: Claims that lack sufficient support
5. **Follow-up Questions**: Questions that should be investigated further
{coverage_check}

Content:
{content}"""

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        # Try to extract structured gaps
        gaps_data = {
            "information_gaps": [],
            "missing_perspectives": [],
            "contradictions": [],
            "weak_evidence": [],
            "follow_up_questions": []
        }

        artifacts = [
            Artifact.json_data(
                data={
                    "analysis": result_text,
                    "expected_coverage": expected_coverage,
                    "structured_gaps": gaps_data
                },
                name="gap_analysis"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _structured_output(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Generate structured output in specified format."""
        output_format = metadata.get("output_format", "markdown")
        schema = metadata.get("schema")

        format_instructions = {
            "json": "Output valid JSON that can be parsed programmatically.",
            "markdown": "Output well-formatted Markdown with headers, lists, and emphasis.",
            "html": "Output clean HTML with semantic elements.",
            "csv": "Output CSV format with headers in the first row."
        }

        schema_instruction = ""
        if schema:
            schema_instruction = f"\n\nFollow this JSON schema for structure:\n{json.dumps(schema, indent=2)}"

        prompt = f"""Transform the following content into {output_format} format.

{format_instructions.get(output_format, '')}
{schema_instruction}

Content:
{content}"""

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        mime_types = {
            "json": "application/json",
            "markdown": "text/markdown",
            "html": "text/html",
            "csv": "text/csv"
        }

        artifacts = [
            Artifact(
                name=f"output.{output_format}",
                type=mime_types.get(output_format, "text/plain"),
                parts=[TextPart(text=result_text)]
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _general_analysis(
        self,
        task_id: str,
        content: str
    ) -> TaskResponse:
        """Perform general analysis on content."""
        prompt = f"""Analyze the following and provide insights:

{content}

Provide:
1. Summary of key points
2. Analysis and interpretation
3. Implications or recommendations
4. Any questions or areas for further exploration"""

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text
        return self._create_text_response(task_id, result_text)

    async def health_check(self) -> dict[str, Any]:
        """Check Claude API connectivity."""
        base = await super().health_check()

        if self._initialized and self._client:
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "ping"}]
                )
                base["api_status"] = "connected"
                base["model"] = self._model
            except Exception as e:
                base["api_status"] = "error"
                base["error"] = str(e)

        return base
