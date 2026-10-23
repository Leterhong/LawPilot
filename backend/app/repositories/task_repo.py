"""任务与时间线仓储：Task / History。"""
from __future__ import annotations

from app.models.history import History
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task


class HistoryRepository(BaseRepository[History]):
    model = History
