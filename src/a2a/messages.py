"""A2A Message Types and Structures.

Defines the message format for A2A agent communication,
supporting text, files, and structured data exchange.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field
import uuid


class MessageRole(str, Enum):
    """Role of the message sender."""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class TextPart(BaseModel):
    """Text content part of a message."""
    type: Literal["text"] = "text"
    text: str = Field(..., description="The text content")


class FilePart(BaseModel):
    """File/binary content part of a message."""
    type: Literal["file"] = "file"
    name: str = Field(..., description="Filename")
    mime_type: str = Field(..., alias="mimeType", description="MIME type of the file")
    data: Optional[str] = Field(default=None, description="Base64 encoded data")
    url: Optional[str] = Field(default=None, description="URL to fetch the file")

    class Config:
        populate_by_name = True


class DataPart(BaseModel):
    """Structured data part of a message (JSON)."""
    type: Literal["data"] = "data"
    data: dict[str, Any] = Field(..., description="Structured JSON data")
    schema_url: Optional[str] = Field(
        default=None,
        alias="schemaUrl",
        description="URL to JSON schema"
    )

    class Config:
        populate_by_name = True


# Union type for all message parts
MessagePart = Union[TextPart, FilePart, DataPart]


class A2AMessage(BaseModel):
    """A2A Message - The core communication unit between agents.

    Messages contain one or more parts (text, files, data) and
    carry context about the sender and conversation.
    """
    role: MessageRole = Field(..., description="Who sent this message")
    parts: list[MessagePart] = Field(..., description="Message content parts")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the message was created"
    )
    context_id: Optional[str] = Field(
        default=None,
        alias="contextId",
        description="Conversation/context identifier"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata"
    )

    class Config:
        populate_by_name = True

    @classmethod
    def user_text(cls, text: str, context_id: Optional[str] = None) -> "A2AMessage":
        """Create a simple user text message."""
        return cls(
            role=MessageRole.USER,
            parts=[TextPart(text=text)],
            context_id=context_id
        )

    @classmethod
    def agent_text(cls, text: str, context_id: Optional[str] = None) -> "A2AMessage":
        """Create a simple agent text message."""
        return cls(
            role=MessageRole.AGENT,
            parts=[TextPart(text=text)],
            context_id=context_id
        )

    def get_text(self) -> str:
        """Extract all text content from the message."""
        texts = []
        for part in self.parts:
            if isinstance(part, TextPart):
                texts.append(part.text)
        return "\n".join(texts)

    def get_data(self) -> list[dict[str, Any]]:
        """Extract all data parts from the message."""
        return [part.data for part in self.parts if isinstance(part, DataPart)]


class Artifact(BaseModel):
    """Output artifact from a task - can be a document, data, file, etc."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = Field(default=None, description="Artifact name")
    type: str = Field(..., description="MIME type of the artifact")
    parts: list[MessagePart] = Field(..., description="Artifact content")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        alias="createdAt"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True

    @classmethod
    def json_data(
        cls,
        data: dict[str, Any],
        name: Optional[str] = None
    ) -> "Artifact":
        """Create a JSON data artifact."""
        return cls(
            name=name,
            type="application/json",
            parts=[DataPart(data=data)]
        )

    @classmethod
    def text_document(cls, text: str, name: Optional[str] = None) -> "Artifact":
        """Create a text document artifact."""
        return cls(
            name=name,
            type="text/plain",
            parts=[TextPart(text=text)]
        )

    @classmethod
    def markdown_document(cls, text: str, name: Optional[str] = None) -> "Artifact":
        """Create a markdown document artifact."""
        return cls(
            name=name,
            type="text/markdown",
            parts=[TextPart(text=text)]
        )


class TaskRequest(BaseModel):
    """Request to execute a task on an agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: A2AMessage = Field(..., description="The task instruction")
    skill_id: Optional[str] = Field(
        default=None,
        alias="skillId",
        description="Specific skill to invoke"
    )
    parent_task_id: Optional[str] = Field(
        default=None,
        alias="parentTaskId",
        description="Parent task for hierarchical execution"
    )
    priority: int = Field(default=5, ge=1, le=10, description="1=highest, 10=lowest")
    timeout_seconds: Optional[int] = Field(
        default=None,
        alias="timeoutSeconds",
        description="Task timeout"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True

    @classmethod
    def simple(cls, task_text: str, skill_id: Optional[str] = None) -> "TaskRequest":
        """Create a simple text task request."""
        return cls(
            message=A2AMessage.user_text(task_text),
            skill_id=skill_id
        )


class TaskResponse(BaseModel):
    """Response from a completed/in-progress task."""
    id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    message: Optional[A2AMessage] = Field(
        default=None,
        description="Response message from agent"
    )
    artifacts: list[Artifact] = Field(
        default_factory=list,
        description="Output artifacts"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True

    @classmethod
    def success(
        cls,
        task_id: str,
        message: Optional[A2AMessage] = None,
        artifacts: Optional[list[Artifact]] = None
    ) -> "TaskResponse":
        """Create a successful task response."""
        return cls(
            id=task_id,
            status="completed",
            message=message,
            artifacts=artifacts or [],
            progress=1.0
        )

    @classmethod
    def error(cls, task_id: str, error_message: str) -> "TaskResponse":
        """Create an error task response."""
        return cls(
            id=task_id,
            status="failed",
            error=error_message
        )

    @classmethod
    def in_progress(
        cls,
        task_id: str,
        progress: float = 0.5,
        message: Optional[str] = None
    ) -> "TaskResponse":
        """Create an in-progress task response."""
        return cls(
            id=task_id,
            status="in_progress",
            progress=progress,
            message=A2AMessage.agent_text(message) if message else None
        )
