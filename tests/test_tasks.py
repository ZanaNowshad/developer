import asyncio

from developer.config import AppSettings
from developer.tasks import TaskQueue


def test_task_queue_dispatch_async() -> None:
    async def scenario() -> None:
        queue = TaskQueue(AppSettings())
        queue._celery = None

        @queue.task("echo")
        async def echo(value: str) -> str:
            return value

        result = await queue.dispatch(echo, "payload")
        assert result == "payload"

        future = echo.delay("from-delay")
        assert await future == "from-delay"

    asyncio.run(scenario())


def test_task_queue_dispatch_sync() -> None:
    async def scenario() -> None:
        queue = TaskQueue(AppSettings())
        queue._celery = None

        @queue.task("double")
        def double(value: int) -> int:
            return value * 2

        assert await queue.dispatch(double, 21) == 42

        future = double.delay(3)
        assert await future == 6

    asyncio.run(scenario())
