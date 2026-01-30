"""Perplexity Agent Implementation.

Handles web search, source discovery, and fact verification
using the Perplexity API (via OpenAI-compatible interface).
"""

import json
import logging
from typing import Any, AsyncIterator, Optional

import httpx
from openai import AsyncOpenAI

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
from .cards import PERPLEXITY_CARD

logger = logging.getLogger(__name__)


class PerplexityAgent(BaseAgent):
    """Perplexity AI agent for web search and research.

    Uses Perplexity's API (OpenAI-compatible) for:
    - Real-time web search with citations
    - Fact verification
    - Source discovery
    """

    PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
    DEFAULT_MODEL = "llama-3.1-sonar-large-128k-online"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(agent_id="perplexity", api_key=api_key)
        self._client: Optional[AsyncOpenAI] = None
        self._model = self.DEFAULT_MODEL

    @property
    def card(self) -> AgentCard:
        return PERPLEXITY_CARD

    async def initialize(self) -> None:
        """Initialize the Perplexity client."""
        if not self.api_key:
            raise ValueError("Perplexity API key is required")

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.PERPLEXITY_BASE_URL
        )
        self._initialized = True
        logger.info("Perplexity agent initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.close()
        self._initialized = False

    async def execute(self, task: Task) -> TaskResponse:
        """Execute a task using Perplexity."""
        if not self._initialized or not self._client:
            return self._create_error_response(
                task.id,
                "Perplexity agent not initialized"
            )

        try:
            # Get the task message content
            message_text = task.request.message.get_text()
            skill_id = task.request.skill_id

            # Route to appropriate handler
            if skill_id == "web-search":
                return await self._web_search(task.id, message_text, task.request.metadata)
            elif skill_id == "fact-check":
                return await self._fact_check(task.id, message_text, task.request.metadata)
            elif skill_id == "source-discovery":
                return await self._source_discovery(task.id, message_text, task.request.metadata)
            else:
                # Default to web search
                return await self._web_search(task.id, message_text, task.request.metadata)

        except Exception as e:
            logger.error(f"Perplexity execution error: {e}")
            return self._create_error_response(task.id, str(e))

    async def execute_streaming(self, task: Task) -> AsyncIterator[TaskResponse]:
        """Execute with streaming responses."""
        if not self._initialized or not self._client:
            yield self._create_error_response(
                task.id,
                "Perplexity agent not initialized"
            )
            return

        message_text = task.request.message.get_text()

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research assistant. Provide detailed, well-cited responses with sources."
                    },
                    {"role": "user", "content": message_text}
                ],
                stream=True
            )

            accumulated_text = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    accumulated_text += chunk.choices[0].delta.content
                    yield TaskResponse.in_progress(
                        task_id=task.id,
                        progress=0.5,
                        message=accumulated_text
                    )

            # Final response
            yield self._create_text_response(task.id, accumulated_text)

        except Exception as e:
            logger.error(f"Perplexity streaming error: {e}")
            yield self._create_error_response(task.id, str(e))

    async def _web_search(
        self,
        task_id: str,
        query: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Perform a web search."""
        # Build system prompt based on search parameters
        recency = metadata.get("recency", "month")
        max_sources = metadata.get("max_sources", 10)
        focus = metadata.get("focus", "web")

        system_prompt = f"""You are a research assistant performing a {focus} search.
Focus on recent information (within the last {recency}).
Provide up to {max_sources} relevant sources with citations.
Format your response with:
1. A clear summary of findings
2. Key points with inline citations [1], [2], etc.
3. A numbered list of sources at the end"""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Search query: {query}"}
            ]
        )

        result_text = response.choices[0].message.content

        # Extract citations if present (Perplexity typically includes them)
        sources_data = self._extract_sources(result_text)

        artifacts = [
            Artifact.json_data(
                data={
                    "query": query,
                    "sources": sources_data,
                    "model": self._model,
                    "search_focus": focus
                },
                name="search_results"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _fact_check(
        self,
        task_id: str,
        claim: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Verify a claim against sources."""
        context = metadata.get("context", "")

        system_prompt = """You are a fact-checker. Analyze the given claim:
1. Search for authoritative sources
2. Determine if the claim is: TRUE, FALSE, PARTIALLY TRUE, or UNVERIFIABLE
3. Provide supporting evidence with citations
4. Note any nuances or context that affects the claim's accuracy"""

        user_message = f"Claim to verify: {claim}"
        if context:
            user_message += f"\n\nAdditional context: {context}"

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )

        result_text = response.choices[0].message.content

        # Create structured artifact
        artifacts = [
            Artifact.json_data(
                data={
                    "claim": claim,
                    "context": context,
                    "analysis": result_text
                },
                name="fact_check_result"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _source_discovery(
        self,
        task_id: str,
        topic: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Find authoritative sources on a topic."""
        source_types = metadata.get("source_types", ["academic", "news", "official"])

        system_prompt = f"""You are a research librarian. Find authoritative sources on the given topic.
Focus on these source types: {', '.join(source_types)}

For each source, provide:
1. Title and URL
2. Source type (academic, news, official, etc.)
3. Brief description of relevance
4. Publication date if available
5. Credibility assessment"""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Find authoritative sources on: {topic}"}
            ]
        )

        result_text = response.choices[0].message.content
        sources_data = self._extract_sources(result_text)

        artifacts = [
            Artifact.json_data(
                data={
                    "topic": topic,
                    "source_types": source_types,
                    "sources": sources_data
                },
                name="discovered_sources"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    def _extract_sources(self, text: str) -> list[dict[str, str]]:
        """Extract source citations from response text."""
        sources = []
        lines = text.split('\n')

        for line in lines:
            # Look for numbered references like [1] or 1.
            if any(pattern in line for pattern in ['[1]', '[2]', '[3]', '1.', '2.', '3.']):
                # Try to extract URL
                import re
                url_match = re.search(r'https?://[^\s\)]+', line)
                if url_match:
                    sources.append({
                        "text": line.strip(),
                        "url": url_match.group(0)
                    })
                else:
                    sources.append({
                        "text": line.strip(),
                        "url": None
                    })

        return sources

    async def health_check(self) -> dict[str, Any]:
        """Check Perplexity API connectivity."""
        base = await super().health_check()

        if self._initialized and self._client:
            try:
                # Try a minimal API call
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=5
                )
                base["api_status"] = "connected"
                base["model"] = self._model
            except Exception as e:
                base["api_status"] = "error"
                base["error"] = str(e)

        return base
