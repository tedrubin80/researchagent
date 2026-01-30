"""Task Manager for A2A Protocol.

Manages task lifecycle, state tracking, and coordination
between multiple agents in a multi-agent workflow.
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional
from pydantic import BaseModel, Field
import uuid

from .protocol import TaskState, TaskStatus
from .messages import A2AMessage, Artifact, TaskRequest, TaskResponse


class Task(BaseModel):
    """A task being processed by an agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request: TaskRequest
    state: TaskState = Field(default_factory=TaskState)
    agent_id: Optional[str] = Field(default=None, description="Assigned agent")
    response: Optional[TaskResponse] = None
    parent_id: Optional[str] = Field(default=None, description="Parent task ID")
    child_ids: list[str] = Field(default_factory=list, description="Child task IDs")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True

    def update_status(
        self,
        status: TaskStatus,
        message: Optional[str] = None,
        progress: Optional[float] = None
    ) -> None:
        """Update task status."""
        self.state.status = status
        self.state.message = message
        if progress is not None:
            self.state.progress = progress
        self.updated_at = datetime.utcnow()

        if status == TaskStatus.IN_PROGRESS and not self.state.started_at:
            self.state.started_at = datetime.utcnow()
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.state.completed_at = datetime.utcnow()

    def set_error(self, error: str) -> None:
        """Mark task as failed with error."""
        self.state.status = TaskStatus.FAILED
        self.state.error = error
        self.state.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def complete(self, response: TaskResponse) -> None:
        """Mark task as completed with response."""
        self.response = response
        self.state.status = TaskStatus.COMPLETED
        self.state.progress = 1.0
        self.state.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @property
    def is_complete(self) -> bool:
        """Check if task has finished (success or failure)."""
        return self.state.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED
        )

    @property
    def is_successful(self) -> bool:
        """Check if task completed successfully."""
        return self.state.status == TaskStatus.COMPLETED


# Type for task execution callback
TaskExecutor = Callable[[Task], Coroutine[Any, Any, TaskResponse]]


class TaskManager:
    """Manages task lifecycle and execution for A2A workflows.

    Features:
    - Task creation and tracking
    - Parent-child task relationships
    - Parallel task execution
    - Task status subscriptions
    - Timeout handling
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._executors: dict[str, TaskExecutor] = {}
        self._subscribers: dict[str, list[Callable[[Task], None]]] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        request: TaskRequest,
        agent_id: Optional[str] = None,
        parent_id: Optional[str] = None
    ) -> Task:
        """Create a new task."""
        task = Task(
            id=request.id,
            request=request,
            agent_id=agent_id,
            parent_id=parent_id
        )

        async with self._lock:
            self._tasks[task.id] = task

            # Update parent's child list
            if parent_id and parent_id in self._tasks:
                self._tasks[parent_id].child_ids.append(task.id)

        await self._notify_subscribers(task)
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        response: Optional[TaskResponse] = None
    ) -> Optional[Task]:
        """Update a task's state."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        async with self._lock:
            if status:
                task.update_status(status, message, progress)
            if response:
                task.complete(response)

        await self._notify_subscribers(task)
        return task

    async def fail_task(self, task_id: str, error: str) -> Optional[Task]:
        """Mark a task as failed."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        async with self._lock:
            task.set_error(error)

        await self._notify_subscribers(task)
        return task

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        async with self._lock:
            task.update_status(TaskStatus.CANCELLED, "Task cancelled by user")

        await self._notify_subscribers(task)
        return task

    async def complete_task(
        self,
        task_id: str,
        response: TaskResponse
    ) -> Optional[Task]:
        """Complete a task with response."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        async with self._lock:
            task.complete(response)

        await self._notify_subscribers(task)
        return task

    def register_executor(self, agent_id: str, executor: TaskExecutor) -> None:
        """Register a task executor for an agent."""
        self._executors[agent_id] = executor

    async def execute_task(
        self,
        task_id: str,
        timeout_seconds: Optional[int] = None
    ) -> TaskResponse:
        """Execute a task using its assigned agent's executor."""
        task = self._tasks.get(task_id)
        if not task:
            return TaskResponse.error(task_id, "Task not found")

        if not task.agent_id:
            return TaskResponse.error(task_id, "No agent assigned to task")

        executor = self._executors.get(task.agent_id)
        if not executor:
            return TaskResponse.error(
                task_id,
                f"No executor registered for agent: {task.agent_id}"
            )

        # Update status to in-progress
        await self.update_task(task_id, status=TaskStatus.IN_PROGRESS)

        try:
            timeout = timeout_seconds or task.request.timeout_seconds or 120

            response = await asyncio.wait_for(
                executor(task),
                timeout=timeout
            )

            await self.complete_task(task_id, response)
            return response

        except asyncio.TimeoutError:
            error_msg = f"Task timed out after {timeout} seconds"
            await self.fail_task(task_id, error_msg)
            return TaskResponse.error(task_id, error_msg)

        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            await self.fail_task(task_id, error_msg)
            return TaskResponse.error(task_id, error_msg)

    async def execute_parallel(
        self,
        task_ids: list[str],
        timeout_seconds: Optional[int] = None
    ) -> list[TaskResponse]:
        """Execute multiple tasks in parallel."""
        coroutines = [
            self.execute_task(tid, timeout_seconds)
            for tid in task_ids
        ]
        return await asyncio.gather(*coroutines, return_exceptions=True)

    def subscribe(
        self,
        task_id: str,
        callback: Callable[[Task], None]
    ) -> Callable[[], None]:
        """Subscribe to task updates. Returns unsubscribe function."""
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []

        self._subscribers[task_id].append(callback)

        def unsubscribe():
            if task_id in self._subscribers:
                self._subscribers[task_id].remove(callback)

        return unsubscribe

    async def _notify_subscribers(self, task: Task) -> None:
        """Notify all subscribers of a task update."""
        subscribers = self._subscribers.get(task.id, [])
        for callback in subscribers:
            try:
                callback(task)
            except Exception:
                pass  # Don't let subscriber errors affect task management

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks."""
        return list(self._tasks.values())

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """Get tasks filtered by status."""
        return [t for t in self._tasks.values() if t.state.status == status]

    def get_child_tasks(self, parent_id: str) -> list[Task]:
        """Get all child tasks of a parent."""
        parent = self._tasks.get(parent_id)
        if not parent:
            return []
        return [self._tasks[cid] for cid in parent.child_ids if cid in self._tasks]

    async def wait_for_completion(
        self,
        task_id: str,
        timeout_seconds: Optional[int] = None
    ) -> Task:
        """Wait for a task to complete."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        start = datetime.utcnow()
        timeout = timeout_seconds or 120

        while not task.is_complete:
            if (datetime.utcnow() - start).total_seconds() > timeout:
                raise asyncio.TimeoutError(f"Timeout waiting for task {task_id}")
            await asyncio.sleep(0.1)
            task = self._tasks.get(task_id)

        return task

    def clear(self) -> None:
        """Clear all tasks."""
        self._tasks.clear()
        self._subscribers.clear()
