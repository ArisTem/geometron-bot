"""Admission and lifecycle of background image generation jobs."""

from collections.abc import Callable, Coroutine
from enum import Enum, auto
from typing import Any

from telegram import Update
from telegram.ext import Application

GENERATION_JOBS_KEY = "generation_jobs"


class GenerationRejection(Enum):
    USER_BUSY = auto()
    CAPACITY_REACHED = auto()


class GenerationJobs:
    """Limit jobs in one application, with no waiting queue.

    Admission and release run on the application's event loop, never in workers.
    """

    def __init__(self, max_concurrent: int) -> None:
        if max_concurrent < 1:
            raise ValueError("Maximum concurrent generations must be positive")
        self._max_concurrent = max_concurrent
        self._active: dict[int, object] = {}

    def submit(
        self,
        user_id: int,
        application: Application,
        update: Update,
        work: Callable[[], Coroutine[Any, Any, None]],
    ) -> GenerationRejection | None:
        """Reserve capacity before scheduling; return a rejection if unavailable."""
        if user_id in self._active:
            return GenerationRejection.USER_BUSY
        if len(self._active) >= self._max_concurrent:
            return GenerationRejection.CAPACITY_REACHED

        reservation = object()
        self._active[user_id] = reservation

        def release() -> None:
            # A delayed callback must not release a newer job for this user.
            if self._active.get(user_id) is reservation:
                del self._active[user_id]

        async def run() -> None:
            await work()

        coroutine = run()
        try:
            task = application.create_task(coroutine, update=update)
        except BaseException:
            coroutine.close()
            release()
            raise

        def completed(_task: object) -> None:
            # Close run() even if it was cancelled before its first execution.
            coroutine.close()
            release()

        task.add_done_callback(completed)
        return None
