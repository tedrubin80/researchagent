"""Gemini Agent Implementation.

Handles multimodal processing, cross-validation, and large document processing
using the Google Gemini API.
"""

import base64
import logging
from typing import Any, AsyncIterator, Optional

from google import genai
from google.genai import types

from src.a2a.protocol import AgentCard
from src.a2a.messages import (
    A2AMessage,
    Artifact,
    DataPart,
    FilePart,
    TaskResponse,
    TextPart,
)
from src.a2a.task_manager import Task
from .base import BaseAgent
from .cards import GEMINI_CARD

logger = logging.getLogger(__name__)


class GeminiAgent(BaseAgent):
    """Gemini AI agent for multimodal processing and validation.

    Uses Google's Gemini API for:
    - Image and video analysis
    - Cross-validation of claims
    - Large document processing
    """

    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(agent_id="gemini", api_key=api_key)
        self._model_name = model or self.DEFAULT_MODEL
        self._client = None

    @property
    def card(self) -> AgentCard:
        return GEMINI_CARD

    async def initialize(self) -> None:
        """Initialize the Gemini client."""
        if not self.api_key:
            raise ValueError("Google API key is required")

        self._client = genai.Client(api_key=self.api_key)
        self._initialized = True
        logger.info(f"Gemini agent initialized with model: {self._model_name}")

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
        self._initialized = False

    async def execute(self, task: Task) -> TaskResponse:
        """Execute a task using Gemini."""
        if not self._initialized or not self._client:
            return self._create_error_response(
                task.id,
                "Gemini agent not initialized"
            )

        try:
            message_text = task.request.message.get_text()
            skill_id = task.request.skill_id
            metadata = task.request.metadata

            # Check for file parts (images)
            file_parts = [
                part for part in task.request.message.parts
                if isinstance(part, FilePart)
            ]

            # Route to appropriate handler
            if skill_id == "image-analysis" or file_parts:
                return await self._image_analysis(task.id, message_text, metadata, file_parts)
            elif skill_id == "cross-validate":
                return await self._cross_validate(task.id, message_text, metadata)
            elif skill_id == "large-context":
                return await self._large_context(task.id, message_text, metadata)
            elif skill_id == "video-analysis":
                return await self._video_analysis(task.id, message_text, metadata)
            else:
                # Default to general processing
                return await self._general_processing(task.id, message_text)

        except Exception as e:
            logger.error(f"Gemini execution error: {e}")
            return self._create_error_response(task.id, str(e))

    async def execute_streaming(self, task: Task) -> AsyncIterator[TaskResponse]:
        """Execute with streaming responses."""
        if not self._initialized or not self._client:
            yield self._create_error_response(
                task.id,
                "Gemini agent not initialized"
            )
            return

        message_text = task.request.message.get_text()

        try:
            response = self._client.models.generate_content_stream(
                model=self._model_name,
                contents=message_text
            )

            accumulated_text = ""
            for chunk in response:
                if chunk.text:
                    accumulated_text += chunk.text
                    yield TaskResponse.in_progress(
                        task_id=task.id,
                        progress=0.5,
                        message=accumulated_text
                    )

            # Final response
            yield self._create_text_response(task.id, accumulated_text)

        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            yield self._create_error_response(task.id, str(e))

    async def _generate_content(self, contents: Any) -> str:
        """Generate content using the Gemini API."""
        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=contents
        )
        return response.text

    async def _image_analysis(
        self,
        task_id: str,
        text: str,
        metadata: dict[str, Any],
        file_parts: list[FilePart]
    ) -> TaskResponse:
        """Analyze images and extract information."""
        analysis_type = metadata.get("analysis_type", "general")
        questions = metadata.get("questions", [])
        image_url = metadata.get("image_url")
        image_data = metadata.get("image_data")

        # Build prompt based on analysis type
        prompts = {
            "general": "Describe this image in detail, noting all significant elements.",
            "chart": "Analyze this chart/graph. Extract all data points, labels, and trends.",
            "diagram": "Explain this diagram. Identify components and their relationships.",
            "text_extraction": "Extract all text visible in this image, preserving structure.",
            "medical": "Analyze this medical image. Note relevant features (educational purposes only)."
        }

        base_prompt = prompts.get(analysis_type, prompts["general"])

        if questions:
            base_prompt += "\n\nAlso answer these specific questions:\n"
            base_prompt += "\n".join(f"- {q}" for q in questions)

        if text and text != "Image Analysis":
            base_prompt = f"{text}\n\n{base_prompt}"

        # Prepare content parts for the new API
        content_parts = [types.Part.from_text(base_prompt)]

        # Add image from file parts
        for fp in file_parts:
            if fp.data:
                # Base64 encoded data
                image_bytes = base64.b64decode(fp.data)
                content_parts.append(types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=fp.mime_type
                ))

        # Add image from base64 in metadata
        if image_data:
            image_bytes = base64.b64decode(image_data)
            content_parts.append(types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            ))

        # If only URL provided, note limitation
        if image_url and not image_data and not file_parts:
            content_parts[0] = types.Part.from_text(
                base_prompt + f"\n\n[Note: Please analyze the image at: {image_url}]"
            )

        try:
            result_text = await self._generate_content(content_parts)

            artifacts = [
                Artifact.json_data(
                    data={
                        "analysis_type": analysis_type,
                        "questions": questions,
                        "has_image": len(file_parts) > 0 or bool(image_data)
                    },
                    name="image_analysis_metadata"
                )
            ]

            return self._create_text_response(task_id, result_text, artifacts)

        except Exception as e:
            return self._create_error_response(task_id, f"Image analysis failed: {str(e)}")

    async def _cross_validate(
        self,
        task_id: str,
        text: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Cross-validate claims across sources."""
        claims = metadata.get("claims", [])
        reference_sources = metadata.get("reference_sources", [])

        # Build claims text
        claims_text = text
        if claims:
            claims_text = "\n".join([
                f"Claim {i+1}: {c.get('claim', c)}"
                + (f" (Source: {c.get('source', 'Unknown')})" if isinstance(c, dict) else "")
                for i, c in enumerate(claims)
            ])

        references_text = ""
        if reference_sources:
            references_text = f"""
Reference these additional sources for validation:
{chr(10).join(f'- {src}' for src in reference_sources)}
"""

        prompt = f"""You are a fact-checker and validator. Analyze the following claims and validate them.

For each claim:
1. **Verification Status**: VERIFIED / PARTIALLY VERIFIED / UNVERIFIED / FALSE
2. **Confidence Level**: High / Medium / Low
3. **Supporting Evidence**: What supports this claim
4. **Contradicting Evidence**: What contradicts this claim
5. **Sources Agreement**: Do multiple sources agree?
6. **Notes**: Any important context or caveats

Claims to validate:
{claims_text}
{references_text}

Provide a structured validation report."""

        result_text = await self._generate_content(prompt)

        # Create validation summary artifact
        validation_data = {
            "claims_count": len(claims) if claims else 1,
            "reference_sources_count": len(reference_sources),
            "validation_summary": result_text[:500]  # First 500 chars as summary
        }

        artifacts = [
            Artifact.json_data(validation_data, "validation_results"),
            Artifact.markdown_document(result_text, "validation_report")
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _large_context(
        self,
        task_id: str,
        text: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Process large documents using Gemini's long context."""
        documents = metadata.get("documents", [])
        task_instruction = metadata.get("task", "Analyze and summarize")

        # Build document content
        doc_content = text
        if documents:
            doc_parts = []
            for i, doc in enumerate(documents):
                name = doc.get("name", f"Document {i+1}")
                content = doc.get("content", "")
                doc_parts.append(f"=== {name} ===\n{content}")
            doc_content = "\n\n".join(doc_parts)

        prompt = f"""You have access to Gemini's large context window (up to 1 million tokens).

Task: {task_instruction}

Process the following document(s) comprehensively:

{doc_content}

Provide:
1. Comprehensive analysis
2. Key information extracted
3. Cross-references between documents (if multiple)
4. Summary of main points"""

        result_text = await self._generate_content(prompt)

        artifacts = [
            Artifact.json_data(
                data={
                    "documents_count": len(documents) if documents else 1,
                    "task": task_instruction,
                    "total_chars": len(doc_content)
                },
                name="processing_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _video_analysis(
        self,
        task_id: str,
        text: str,
        metadata: dict[str, Any]
    ) -> TaskResponse:
        """Analyze video content."""
        video_url = metadata.get("video_url")
        timestamps = metadata.get("timestamps", [])
        task_instruction = metadata.get("task", "Analyze the video content")

        prompt = f"""Analyze the video content.

Video URL: {video_url or 'Not provided'}
Task: {task_instruction}

"""
        if timestamps:
            prompt += f"Focus on these timestamps: {', '.join(map(str, timestamps))}\n\n"

        prompt += """Provide:
1. Content summary
2. Key moments identified
3. Visual elements described
4. Audio/dialogue summary (if applicable)
5. Insights and observations

Note: If video URL is not directly accessible, provide general guidance on video analysis approach."""

        result_text = await self._generate_content(prompt)

        artifacts = [
            Artifact.json_data(
                data={
                    "video_url": video_url,
                    "timestamps": timestamps,
                    "task": task_instruction
                },
                name="video_analysis_metadata"
            )
        ]

        return self._create_text_response(task_id, result_text, artifacts)

    async def _general_processing(
        self,
        task_id: str,
        content: str
    ) -> TaskResponse:
        """General content processing."""
        prompt = f"""Process the following content and provide comprehensive analysis:

{content}

Provide:
1. Summary of main points
2. Detailed analysis
3. Key insights
4. Recommendations for further investigation"""

        result_text = await self._generate_content(prompt)

        return self._create_text_response(task_id, result_text)

    async def health_check(self) -> dict[str, Any]:
        """Check Gemini API connectivity."""
        base = await super().health_check()

        if self._initialized and self._client:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model_name,
                    contents="ping"
                )
                base["api_status"] = "connected"
                base["model"] = self._model_name
            except Exception as e:
                base["api_status"] = "error"
                base["error"] = str(e)

        return base
