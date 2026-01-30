"""Tests for A2A Protocol implementation."""

import pytest
from datetime import datetime

from src.a2a.protocol import (
    A2AProtocol,
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    TaskState,
    TaskStatus,
)
from src.a2a.messages import (
    A2AMessage,
    Artifact,
    DataPart,
    FilePart,
    MessageRole,
    TaskRequest,
    TaskResponse,
    TextPart,
)
from src.a2a.task_manager import Task, TaskManager


class TestA2AProtocol:
    """Tests for A2A Protocol utilities."""

    def test_create_request(self):
        """Test JSON-RPC request creation."""
        request = A2AProtocol.create_request(
            method="tasks/send",
            params={"id": "test-1", "message": {"text": "hello"}},
            request_id="req-1"
        )

        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "tasks/send"
        assert request["params"]["id"] == "test-1"
        assert request["id"] == "req-1"

    def test_create_response(self):
        """Test JSON-RPC response creation."""
        response = A2AProtocol.create_response(
            request_id="req-1",
            result={"status": "completed"}
        )

        assert response["jsonrpc"] == "2.0"
        assert response["result"]["status"] == "completed"
        assert response["id"] == "req-1"

    def test_create_error(self):
        """Test JSON-RPC error creation."""
        error = A2AProtocol.create_error(
            request_id="req-1",
            code=A2AProtocol.ERROR_INVALID_PARAMS,
            message="Missing required parameter"
        )

        assert error["jsonrpc"] == "2.0"
        assert error["error"]["code"] == -32602
        assert "Missing required parameter" in error["error"]["message"]
        assert error["id"] == "req-1"

    def test_validate_request_valid(self):
        """Test validation of valid request."""
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {},
            "id": "1"
        }
        valid, error = A2AProtocol.validate_request(request)
        assert valid is True
        assert error is None

    def test_validate_request_invalid_version(self):
        """Test validation with invalid version."""
        request = {
            "jsonrpc": "1.0",
            "method": "tasks/send"
        }
        valid, error = A2AProtocol.validate_request(request)
        assert valid is False
        assert "version" in error.lower()

    def test_validate_request_missing_method(self):
        """Test validation with missing method."""
        request = {
            "jsonrpc": "2.0"
        }
        valid, error = A2AProtocol.validate_request(request)
        assert valid is False
        assert "method" in error.lower()


class TestAgentCard:
    """Tests for Agent Card functionality."""

    def test_agent_card_creation(self):
        """Test creating an agent card."""
        card = AgentCard(
            name="Test Agent",
            description="A test agent",
            url="http://localhost:8000/agents/test",
            capabilities=AgentCapabilities(streaming=True),
            skills=[
                AgentSkill(
                    id="test-skill",
                    name="Test Skill",
                    description="A test skill"
                )
            ]
        )

        assert card.name == "Test Agent"
        assert card.capabilities.streaming is True
        assert len(card.skills) == 1
        assert card.has_skill("test-skill") is True
        assert card.has_skill("unknown") is False

    def test_agent_card_get_skill(self):
        """Test getting a skill from agent card."""
        card = AgentCard(
            name="Test Agent",
            description="A test agent",
            url="http://localhost:8000/agents/test",
            skills=[
                AgentSkill(
                    id="skill-1",
                    name="Skill One",
                    description="First skill"
                ),
                AgentSkill(
                    id="skill-2",
                    name="Skill Two",
                    description="Second skill"
                )
            ]
        )

        skill = card.get_skill("skill-1")
        assert skill is not None
        assert skill.name == "Skill One"

        unknown = card.get_skill("skill-3")
        assert unknown is None


class TestA2AMessages:
    """Tests for A2A message types."""

    def test_text_part(self):
        """Test TextPart creation."""
        part = TextPart(text="Hello, world!")
        assert part.type == "text"
        assert part.text == "Hello, world!"

    def test_data_part(self):
        """Test DataPart creation."""
        part = DataPart(data={"key": "value", "count": 42})
        assert part.type == "data"
        assert part.data["key"] == "value"
        assert part.data["count"] == 42

    def test_a2a_message_user_text(self):
        """Test creating a user text message."""
        msg = A2AMessage.user_text("Hello agent!")
        assert msg.role == MessageRole.USER
        assert len(msg.parts) == 1
        assert msg.get_text() == "Hello agent!"

    def test_a2a_message_agent_text(self):
        """Test creating an agent text message."""
        msg = A2AMessage.agent_text("Here is my response.")
        assert msg.role == MessageRole.AGENT
        assert msg.get_text() == "Here is my response."

    def test_artifact_json_data(self):
        """Test creating a JSON data artifact."""
        artifact = Artifact.json_data(
            data={"sources": ["source1", "source2"]},
            name="search_results"
        )
        assert artifact.type == "application/json"
        assert artifact.name == "search_results"
        assert len(artifact.parts) == 1

    def test_artifact_markdown_document(self):
        """Test creating a markdown document artifact."""
        artifact = Artifact.markdown_document(
            text="# Report\n\nThis is the report.",
            name="report.md"
        )
        assert artifact.type == "text/markdown"
        assert artifact.name == "report.md"

    def test_task_request_simple(self):
        """Test creating a simple task request."""
        request = TaskRequest.simple("Analyze this document", skill_id="analysis")
        assert request.message.get_text() == "Analyze this document"
        assert request.skill_id == "analysis"

    def test_task_response_success(self):
        """Test creating a success response."""
        response = TaskResponse.success(
            task_id="task-1",
            message=A2AMessage.agent_text("Analysis complete.")
        )
        assert response.status == "completed"
        assert response.progress == 1.0
        assert response.error is None

    def test_task_response_error(self):
        """Test creating an error response."""
        response = TaskResponse.error(
            task_id="task-1",
            error_message="Something went wrong"
        )
        assert response.status == "failed"
        assert response.error == "Something went wrong"


class TestTaskManager:
    """Tests for TaskManager functionality."""

    @pytest.fixture
    def task_manager(self):
        """Create a TaskManager instance."""
        return TaskManager()

    @pytest.mark.asyncio
    async def test_create_task(self, task_manager):
        """Test creating a task."""
        request = TaskRequest.simple("Test task")
        task = await task_manager.create_task(request, agent_id="test-agent")

        assert task.id == request.id
        assert task.agent_id == "test-agent"
        assert task.state.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_task(self, task_manager):
        """Test getting a task by ID."""
        request = TaskRequest.simple("Test task")
        created_task = await task_manager.create_task(request)

        retrieved_task = await task_manager.get_task(created_task.id)
        assert retrieved_task is not None
        assert retrieved_task.id == created_task.id

        unknown_task = await task_manager.get_task("unknown-id")
        assert unknown_task is None

    @pytest.mark.asyncio
    async def test_update_task_status(self, task_manager):
        """Test updating task status."""
        request = TaskRequest.simple("Test task")
        task = await task_manager.create_task(request)

        updated = await task_manager.update_task(
            task.id,
            status=TaskStatus.IN_PROGRESS,
            progress=0.5
        )

        assert updated.state.status == TaskStatus.IN_PROGRESS
        assert updated.state.progress == 0.5

    @pytest.mark.asyncio
    async def test_complete_task(self, task_manager):
        """Test completing a task."""
        request = TaskRequest.simple("Test task")
        task = await task_manager.create_task(request)

        response = TaskResponse.success(task.id, A2AMessage.agent_text("Done!"))
        completed = await task_manager.complete_task(task.id, response)

        assert completed.state.status == TaskStatus.COMPLETED
        assert completed.is_complete is True
        assert completed.is_successful is True
        assert completed.response is not None

    @pytest.mark.asyncio
    async def test_fail_task(self, task_manager):
        """Test failing a task."""
        request = TaskRequest.simple("Test task")
        task = await task_manager.create_task(request)

        failed = await task_manager.fail_task(task.id, "Something went wrong")

        assert failed.state.status == TaskStatus.FAILED
        assert failed.state.error == "Something went wrong"
        assert failed.is_complete is True
        assert failed.is_successful is False

    @pytest.mark.asyncio
    async def test_cancel_task(self, task_manager):
        """Test cancelling a task."""
        request = TaskRequest.simple("Test task")
        task = await task_manager.create_task(request)

        cancelled = await task_manager.cancel_task(task.id)

        assert cancelled.state.status == TaskStatus.CANCELLED
        assert cancelled.is_complete is True

    @pytest.mark.asyncio
    async def test_get_tasks_by_status(self, task_manager):
        """Test filtering tasks by status."""
        # Create tasks with different statuses
        task1 = await task_manager.create_task(TaskRequest.simple("Task 1"))
        task2 = await task_manager.create_task(TaskRequest.simple("Task 2"))
        task3 = await task_manager.create_task(TaskRequest.simple("Task 3"))

        await task_manager.update_task(task1.id, status=TaskStatus.COMPLETED)
        await task_manager.update_task(task2.id, status=TaskStatus.IN_PROGRESS)

        pending_tasks = task_manager.get_tasks_by_status(TaskStatus.PENDING)
        assert len(pending_tasks) == 1

        completed_tasks = task_manager.get_tasks_by_status(TaskStatus.COMPLETED)
        assert len(completed_tasks) == 1

    @pytest.mark.asyncio
    async def test_parent_child_relationship(self, task_manager):
        """Test parent-child task relationships."""
        parent_request = TaskRequest.simple("Parent task")
        parent = await task_manager.create_task(parent_request)

        child1_request = TaskRequest.simple("Child task 1")
        child1 = await task_manager.create_task(child1_request, parent_id=parent.id)

        child2_request = TaskRequest.simple("Child task 2")
        child2 = await task_manager.create_task(child2_request, parent_id=parent.id)

        # Check parent has children
        parent_updated = await task_manager.get_task(parent.id)
        assert len(parent_updated.child_ids) == 2

        # Check children reference parent
        assert child1.parent_id == parent.id
        assert child2.parent_id == parent.id

        # Get child tasks
        children = task_manager.get_child_tasks(parent.id)
        assert len(children) == 2


class TestTaskState:
    """Tests for TaskState functionality."""

    def test_task_state_defaults(self):
        """Test TaskState default values."""
        state = TaskState()
        assert state.status == TaskStatus.PENDING
        assert state.progress == 0.0
        assert state.message is None
        assert state.started_at is None
        assert state.completed_at is None
        assert state.error is None

    def test_task_update_status(self):
        """Test Task status updates."""
        task = Task(
            id="test-1",
            request=TaskRequest.simple("Test")
        )

        # Update to in progress
        task.update_status(TaskStatus.IN_PROGRESS, "Working...", 0.5)
        assert task.state.status == TaskStatus.IN_PROGRESS
        assert task.state.message == "Working..."
        assert task.state.progress == 0.5
        assert task.state.started_at is not None

        # Update to completed
        task.update_status(TaskStatus.COMPLETED)
        assert task.state.status == TaskStatus.COMPLETED
        assert task.state.completed_at is not None

    def test_task_is_complete(self):
        """Test Task completion checks."""
        task = Task(
            id="test-1",
            request=TaskRequest.simple("Test")
        )

        assert task.is_complete is False

        task.update_status(TaskStatus.COMPLETED)
        assert task.is_complete is True

        task2 = Task(
            id="test-2",
            request=TaskRequest.simple("Test 2")
        )
        task2.set_error("Failed")
        assert task2.is_complete is True
        assert task2.is_successful is False
