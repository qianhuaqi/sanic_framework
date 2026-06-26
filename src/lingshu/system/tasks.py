from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from itertools import count
from typing import Any

from lingshu.system.execution import current_execution_context
from lingshu.system.errors import NoRequestContextError


@dataclass
class TaskRecord:
    id: str
    name: str
    owner: str
    created_at: float
    state: str
    shutdown_policy: str
    task: asyncio.Task | None
    request_id: str | None = None
    operation_id: str | None = None
    deadline: float | None = None
    raw_request: object | None = None
    result: Any = None
    exception: BaseException | None = None
    cancel_reason: str | None = None


class TaskRegistry:
    def __init__(self):
        self._records: dict[str, TaskRecord] = {}
        self._history: dict[str, TaskRecord] = {}
        self._counter = count(1)
        self._closed = False

    def spawn(self, coro, *, name: str, owner: str, shutdown_policy: str = "wait") -> str:
        if not owner:
            coro.close()
            raise ValueError("Task owner is required")
        if self._closed:
            coro.close()
            raise RuntimeError("TaskRegistry is closed")
        task_id = f"task-{next(self._counter)}"
        request_id = operation_id = None
        deadline = None
        try:
            execution = current_execution_context()
            request_id = execution.request_id
            operation_id = execution.operation_id
            deadline = execution.deadline
        except NoRequestContextError:
            pass
        task = asyncio.create_task(coro, name=name)
        record = TaskRecord(
            id=task_id,
            name=name,
            owner=owner,
            created_at=time.monotonic(),
            state="running",
            shutdown_policy=shutdown_policy,
            task=task,
            request_id=request_id,
            operation_id=operation_id,
            deadline=deadline,
        )
        self._records[task_id] = record
        self._history[task_id] = record
        task.add_done_callback(lambda done_task, record_id=task_id: self._complete(record_id, done_task))
        return task_id

    def _complete(self, task_id: str, task: asyncio.Task):
        record = self._records.pop(task_id, self._history[task_id])
        try:
            record.result = task.result()
            record.state = "done"
        except asyncio.CancelledError as exc:
            record.exception = exc
            record.state = "cancelled"
        except BaseException as exc:  # task exception must be consumed
            record.exception = exc
            record.state = "failed"
        record.task = None

    def list(self) -> list[TaskRecord]:
        return list(self._records.values())

    def get_record(self, task_id: str) -> TaskRecord:
        return self._history[task_id]

    def get_result(self, task_id: str):
        return self._history[task_id].result

    async def cancel(self, task_id: str, reason: str = "manual"):
        record = self._records.get(task_id)
        if record is None or record.task is None:
            return
        record.cancel_reason = reason
        record.task.cancel()
        await asyncio.gather(record.task, return_exceptions=True)

    async def cancel_all(self, reason: str = "manual"):
        await asyncio.gather(*(self.cancel(task_id, reason=reason) for task_id in list(self._records)), return_exceptions=True)

    async def shutdown_and_wait(self, timeout: float):
        self._closed = True
        tasks = [record.task for record in self._records.values() if record.task is not None]
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        return list(self._history.values())
