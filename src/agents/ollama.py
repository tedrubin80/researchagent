"""Ollama Agent Implementation.

Provides local LLM capabilities using Ollama's OpenAI-compatible API.
Acts as a fallback provider when cloud APIs are unavailable.
"""

import logging
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI

from src.a2a.protocol import AgentCard
from src.a2a.messages import (
    A2AMessage,
    Artifact,
    TaskResponse,
)
from src.a2a.task_manager import Task
from .base import BaseAgent
from .cards import OLLAMA_CARD

logger = logging.getLogger(__name__)


class OllamaAgent(BaseAgent):
    """Ollama local LLM agent for offline research.

    Uses Ollama's OpenAI-compatible API endpoint for:
    - Document analysis
    - Research synthesis
    - General queries

    Acts as a fallback when cloud providers are unavailable.
    """

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "llama3.1"
    MAX_TOKENS = 4096

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        super().__init__(agent_id="ollama", api_key="ollama")  # Ollama doesn't need API key
        self._client: Optional[AsyncOpenAI] = None
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._model = model or self.DEFAULT_MODEL

    @property
    def card(self) -> AgentCard:
        return OLLAMA_CARD

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    async def initialize(self) -> None:
        """Initialize the Ollama client."""
        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key="ollama"  # Ollama doesn't validate API key
        )
        self._initialized = True
        logger.info(f"Ollama agent initialized with model: {self._model} at {self._base_url}")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.close()
        self._initialized = False

    async def execute(self, task: Task) -> TaskResponse:
        """Execute a task using Ollama."""
        if not self._initialized or not self._client:
            return self._create_error_response(
                task.id,
                "Ollama agent not initialized"
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
            elif skill_id == "general-query":
                return await self._general_query(task.id, message_text)
            else:
                # Default to general query
                return await self._general_query(task.id, message_text)

        except Exception as e:
            logger.error(f"Ollama execution error: {e}")
            return self._create_error_response(task.id, str(e))

    async def execute_streaming(self, task: Task) -> AsyncIterator[TaskResponse]:
        """Execute with streaming responses."""
        if not self._initialized or not self._client:
            yield self._create_error_response(
                task.id,
                "Ollama agent not initialized"
            )
            return

        message_text = task.request.message.get_text()

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": message_text}],
                stream=True
            )

            accumulated_text = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    accumulated_text += chunk.choices[0].delta.content
                    yield TaskResponse.in_progress(
                        task_id=task.id,
                        progress=0.5,
                        message=accumulated_text
                    )

            # Final response
            yield self._create_text_response(task.id, accumulated_text)

        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
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

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content

        artifacts = [
            Artifact.json_data(
                data={
                    "analysis_type": analysis_type,
                    "focus_areas": focus_areas,
                    "content_length": len(content),
                    "model": self._model,
                    "provider": "ollama"
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

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content

        artifacts = [
            Artifact.markdown_document(result_text, "synthesis_report"),
            Artifact.json_data(
                data={
                    "output_format": output_format,
                    "target_length": target_length,
                    "sources_count": len(sources) if sources else 1,
                    "provider": "ollama"
                },
                name="synthesis_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _general_query(
        self,
        task_id: str,
        content: str
    ) -> TaskResponse:
        """Handle general queries."""
        prompt = f"""Please respond to the following query:

{content}

Provide a helpful, accurate, and well-structured response."""

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content
        return self._create_text_response(task_id, result_text)

    async def health_check(self) -> dict[str, Any]:
        """Check Ollama connectivity."""
        base = await super().health_check()
        base["base_url"] = self._base_url
        base["model"] = self._model

        if self._initialized and self._client:
            try:
                # Try a minimal completion to verify connectivity
                response = await self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "ping"}]
                )
                base["api_status"] = "connected"
                base["ollama_available"] = True
            except Exception as e:
                base["api_status"] = "error"
                base["ollama_available"] = False
                base["error"] = str(e)

        return base
