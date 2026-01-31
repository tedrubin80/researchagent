"""OpenAI Agent Implementation.

Handles multimodal processing, validation, and large context tasks
using the OpenAI GPT API.
"""

import json
import logging
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI

from src.a2a.protocol import AgentCard
from src.a2a.messages import (
    A2AMessage,
    Artifact,
    TaskResponse,
    TextPart,
)
from src.a2a.task_manager import Task
from .base import BaseAgent
from .cards import OPENAI_CARD

logger = logging.getLogger(__name__)


class OpenAIAgent(BaseAgent):
    """OpenAI GPT agent for multimodal and validation tasks.

    Uses OpenAI's GPT API for:
    - Image analysis
    - Cross-validation
    - Large document processing
    - Video analysis (via frame extraction)
    """

    DEFAULT_MODEL = "gpt-4o"
    MAX_TOKENS = 4096

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(agent_id="openai", api_key=api_key)
        self._client: Optional[AsyncOpenAI] = None
        self._model = model or self.DEFAULT_MODEL

    @property
    def card(self) -> AgentCard:
        return OPENAI_CARD

    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self._client = AsyncOpenAI(api_key=self.api_key)
        self._initialized = True
        logger.info(f"OpenAI agent initialized with model: {self._model}")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.close()
        self._initialized = False

    async def execute(self, task: Task) -> TaskResponse:
        """Execute a task using OpenAI."""
        if not self._initialized or not self._client:
            return self._create_error_response(
                task.id,
                "OpenAI agent not initialized"
            )

        try:
            message_text = task.request.message.get_text()
            skill_id = task.request.skill_id
            metadata = task.request.metadata

            # Route to appropriate handler
            if skill_id == "image-analysis":
                return await self._image_analysis(task.id, message_text, metadata)
            elif skill_id == "cross-validate":
                return await self._cross_validate(task.id, message_text, metadata)
            elif skill_id == "large-context":
                return await self._large_context(task.id, message_text, metadata)
            elif skill_id == "video-analysis":
                return await self._video_analysis(task.id, message_text, metadata)
            else:
                # Default to general query
                return await self._general_query(task.id, message_text)

        except Exception as e:
            logger.error(f"OpenAI execution error: {e}")
            return self._create_error_response(task.id, str(e))

    async def execute_streaming(self, task: Task) -> AsyncIterator[TaskResponse]:
        """Execute with streaming responses."""
        if not self._initialized or not self._client:
            yield self._create_error_response(
                task.id,
                "OpenAI agent not initialized"
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
            logger.error(f"OpenAI streaming error: {e}")
            yield self._create_error_response(task.id, str(e))

    async def _image_analysis(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Analyze an image using GPT-4 Vision."""
        image_url = metadata.get("image_url")
        image_data = metadata.get("image_data")
        analysis_type = metadata.get("analysis_type", "general")
        questions = metadata.get("questions", [])

        # Build messages with image
        messages = []
        content_parts = []

        # Add the analysis prompt
        analysis_prompts = {
            "general": "Analyze this image in detail. Describe what you see, identify key elements, and provide any relevant insights.",
            "chart": "Analyze this chart/graph. Extract all data points, identify trends, and summarize the key findings.",
            "diagram": "Analyze this diagram. Explain its structure, components, and the relationships between elements.",
            "text_extraction": "Extract all visible text from this image, maintaining the original structure where possible.",
            "medical": "Provide a detailed analysis of this medical image, noting any significant findings (disclaimer: this is not medical advice)."
        }

        prompt = analysis_prompts.get(analysis_type, analysis_prompts["general"])
        if questions:
            prompt += f"\n\nAlso answer these specific questions:\n" + "\n".join(f"- {q}" for q in questions)
        if content:
            prompt += f"\n\nAdditional context: {content}"

        content_parts.append({"type": "text", "text": prompt})

        # Add image
        if image_url:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
        elif image_data:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
            })
        else:
            return self._create_error_response(task_id, "No image provided (need image_url or image_data)")

        messages.append({"role": "user", "content": content_parts})

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=messages
        )

        result_text = response.choices[0].message.content

        artifacts = [
            Artifact.json_data(
                data={
                    "analysis_type": analysis_type,
                    "questions": questions,
                    "model": self._model
                },
                name="image_analysis_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _cross_validate(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Cross-validate claims against multiple sources."""
        claims = metadata.get("claims", [])
        reference_sources = metadata.get("reference_sources", [])

        # Build claims text
        claims_text = content
        if claims:
            claims_text = "\n".join([
                f"Claim {i+1}: \"{c.get('claim', c)}\" (Source: {c.get('source', 'Unknown')})"
                for i, c in enumerate(claims)
            ])

        references_text = ""
        if reference_sources:
            references_text = f"\n\nReference sources to check against:\n" + "\n".join(f"- {s}" for s in reference_sources)

        prompt = f"""Cross-validate the following claims for accuracy and consistency:

{claims_text}
{references_text}

For each claim, provide:
1. **Verdict**: True / Partially True / False / Unverifiable
2. **Confidence**: High / Medium / Low
3. **Evidence**: Supporting or contradicting information
4. **Sources**: Where the claim can be verified
5. **Notes**: Any caveats or nuances

Finally, provide an overall assessment of the information quality."""

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content

        artifacts = [
            Artifact.json_data(
                data={
                    "claims_count": len(claims) if claims else 1,
                    "reference_sources": reference_sources
                },
                name="validation_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _large_context(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Process large documents."""
        documents = metadata.get("documents", [])
        task_description = metadata.get("task", "Analyze and summarize")

        # Build document content
        docs_text = content
        if documents:
            docs_text = "\n\n".join([
                f"=== Document: {d.get('name', f'Document {i+1}')} ===\n{d.get('content', '')}"
                for i, d in enumerate(documents)
            ])

        prompt = f"""Task: {task_description}

Documents:
{docs_text}

Provide a comprehensive response addressing the task."""

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content

        artifacts = [
            Artifact.json_data(
                data={
                    "documents_count": len(documents) if documents else 1,
                    "task": task_description,
                    "total_length": len(docs_text)
                },
                name="large_context_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _video_analysis(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Analyze video content (limited - requires frame extraction)."""
        video_url = metadata.get("video_url")
        timestamps = metadata.get("timestamps", [])
        task_description = metadata.get("task", "Describe the video content")

        # Note: Full video analysis would require extracting frames
        # For now, provide guidance on what's needed
        prompt = f"""Video Analysis Request:
URL: {video_url}
Timestamps of interest: {timestamps if timestamps else 'Full video'}
Task: {task_description}

Additional context: {content}

Note: For full video analysis, please provide extracted frames as images.
If you have a transcript or description of the video content, I can analyze that."""

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content
        return self._create_text_response(task_id, result_text)

    async def _general_query(
        self,
        task_id: str,
        content: str
    ) -> TaskResponse:
        """Handle general queries."""
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": content}]
        )

        result_text = response.choices[0].message.content
        return self._create_text_response(task_id, result_text)

    async def health_check(self) -> dict[str, Any]:
        """Check OpenAI API connectivity."""
        base = await super().health_check()

        if self._initialized and self._client:
            try:
                response = await self._client.chat.completions.create(
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
