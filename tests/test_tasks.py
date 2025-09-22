import asyncio

from developer.config import AppSettings
from developer.stubs.celery import Celery as StubCelery
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


def test_task_queue_with_celery_stub() -> None:
    celery_app = StubCelery("developer")
    queue = TaskQueue(AppSettings(), celery_app=celery_app)

    async def scenario() -> None:
        @queue.task("upper")
        async def upper(value: str) -> str:
            return value.upper()

        @queue.task("double_sync")
        def double_sync(value: int) -> int:
            return value * 2

        assert await queue.dispatch(upper, "payload") == "PAYLOAD"
        assert await queue.dispatch(double_sync, 10) == 20

        eager_async = upper.delay("async")
        eager_sync = double_sync.delay(4)

        assert await eager_async.aget() == "ASYNC"
        assert await eager_sync.aget() == 8

    asyncio.run(scenario())
