"""A2A Protocol Core Types and Definitions.

This module implements the A2A (Agent-to-Agent) protocol specification,
enabling standardized communication between AI agents from different providers.

Based on the A2A Protocol specification for agent interoperability.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class TaskStatus(str, Enum):
    """Task execution status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"  # Waiting for input or other agents


class TaskState(BaseModel):
    """Current state of a task including status and progress."""
    status: TaskStatus = TaskStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class AgentSkill(BaseModel):
    """Definition of a capability/skill that an agent can perform.

    Skills define what an agent can do and the expected input format.
    """
    id: str = Field(..., description="Unique identifier for this skill")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this skill does")
    input_schema: Optional[dict[str, Any]] = Field(
        default=None,
        alias="inputSchema",
        description="JSON Schema for expected input"
    )
    output_schema: Optional[dict[str, Any]] = Field(
        default=None,
        alias="outputSchema",
        description="JSON Schema for expected output"
    )
    tags: list[str] = Field(default_factory=list, description="Skill categorization tags")

    class Config:
        populate_by_name = True


class AgentCapabilities(BaseModel):
    """Agent capability flags indicating supported features."""
    streaming: bool = Field(default=False, description="Supports streaming responses")
    push_notifications: bool = Field(
        default=False,
        alias="pushNotifications",
        description="Can send push notifications"
    )
    batch_processing: bool = Field(
        default=False,
        alias="batchProcessing",
        description="Can process multiple requests"
    )
    multimodal: bool = Field(default=False, description="Supports images/audio/video")
    long_context: bool = Field(
        default=False,
        alias="longContext",
        description="Supports large context windows"
    )

    class Config:
        populate_by_name = True


class AgentCard(BaseModel):
    """Agent Card - The identity and capability manifest for an A2A agent.

    Agent Cards are discoverable documents that describe what an agent can do,
    how to communicate with it, and what skills it provides.
    """
    name: str = Field(..., description="Display name of the agent")
    description: str = Field(..., description="What this agent does")
    version: str = Field(default="1.0.0", description="Agent version")
    url: HttpUrl = Field(..., description="Base URL for A2A communication")
    provider: Optional[str] = Field(default=None, description="Agent provider/creator")
    documentation_url: Optional[HttpUrl] = Field(
        default=None,
        alias="documentationUrl",
        description="Link to documentation"
    )
    capabilities: AgentCapabilities = Field(
        default_factory=AgentCapabilities,
        description="Supported features"
    )
    skills: list[AgentSkill] = Field(
        default_factory=list,
        description="Available skills/capabilities"
    )
    authentication: Optional[dict[str, Any]] = Field(
        default=None,
        description="Authentication requirements"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional agent metadata"
    )

    class Config:
        populate_by_name = True

    def has_skill(self, skill_id: str) -> bool:
        """Check if agent has a specific skill."""
        return any(s.id == skill_id for s in self.skills)

    def get_skill(self, skill_id: str) -> Optional[AgentSkill]:
        """Get skill by ID."""
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None


class A2AProtocol:
    """A2A Protocol handler for JSON-RPC based agent communication.

    Implements the core A2A protocol methods:
    - tasks/send: Create a new task for an agent
    - tasks/get: Get task status and results
    - tasks/cancel: Cancel a running task
    - tasks/subscribe: Subscribe to task updates (streaming)
    - agent/card: Get agent's capability card
    """

    VERSION = "1.0"

    # JSON-RPC Methods
    METHOD_TASK_SEND = "tasks/send"
    METHOD_TASK_GET = "tasks/get"
    METHOD_TASK_CANCEL = "tasks/cancel"
    METHOD_TASK_SUBSCRIBE = "tasks/subscribe"
    METHOD_AGENT_CARD = "agent/card"

    # Error Codes (JSON-RPC standard + A2A specific)
    ERROR_PARSE = -32700
    ERROR_INVALID_REQUEST = -32600
    ERROR_METHOD_NOT_FOUND = -32601
    ERROR_INVALID_PARAMS = -32602
    ERROR_INTERNAL = -32603
    ERROR_TASK_NOT_FOUND = -32001
    ERROR_SKILL_NOT_FOUND = -32002
    ERROR_UNAUTHORIZED = -32003
    ERROR_RATE_LIMITED = -32004
    ERROR_TASK_CANCELLED = -32005

    @staticmethod
    def create_request(
        method: str,
        params: dict[str, Any],
        request_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Create a JSON-RPC 2.0 request."""
        import uuid
        return {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id or str(uuid.uuid4())
        }

    @staticmethod
    def create_response(
        request_id: str,
        result: Any
    ) -> dict[str, Any]:
        """Create a JSON-RPC 2.0 success response."""
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        }

    @staticmethod
    def create_error(
        request_id: Optional[str],
        code: int,
        message: str,
        data: Optional[Any] = None
    ) -> dict[str, Any]:
        """Create a JSON-RPC 2.0 error response."""
        error = {
            "code": code,
            "message": message
        }
        if data is not None:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "error": error,
            "id": request_id
        }

    @staticmethod
    def create_task_send_params(
        task_id: str,
        message: dict[str, Any],
        skill_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Create parameters for tasks/send method."""
        params = {
            "id": task_id,
            "message": message
        }
        if skill_id:
            params["skillId"] = skill_id
        if metadata:
            params["metadata"] = metadata
        return params

    @staticmethod
    def validate_request(request: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate a JSON-RPC request structure."""
        if not isinstance(request, dict):
            return False, "Request must be a JSON object"

        if request.get("jsonrpc") != "2.0":
            return False, "Invalid or missing jsonrpc version"

        if "method" not in request:
            return False, "Missing method field"

        if not isinstance(request.get("method"), str):
            return False, "Method must be a string"

        if "params" in request and not isinstance(request["params"], (dict, list)):
            return False, "Params must be an object or array"

        return True, None
