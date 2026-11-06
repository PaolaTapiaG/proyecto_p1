import json
import threading
from collections.abc import Generator
from contextlib import contextmanager

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


class LockBusy(RuntimeError):
    pass


class RedisGateway:
    def __init__(self) -> None:
        self.client = Redis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None
        self._fallback_locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    @contextmanager
    def conversation_lock(self, conversation_id: str) -> Generator[None, None, None]:
        key = f"conversation:{conversation_id}:generation"
        if self.client:
            lock = self.client.lock(key, timeout=90, blocking_timeout=0)
            try:
                acquired = lock.acquire(blocking=False)
            except RedisError:
                acquired = None
            if acquired is False:
                raise LockBusy("Another response is already being generated")
            if acquired:
                try:
                    yield
                finally:
                    try:
                        lock.release()
                    except RedisError:
                        pass
                return

        with self._guard:
            local_lock = self._fallback_locks.setdefault(key, threading.Lock())
        if not local_lock.acquire(blocking=False):
            raise LockBusy("Another response is already being generated")
        try:
            yield
        finally:
            local_lock.release()

    def cache_get(self, key: str) -> dict | list | str | int | None:
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            return json.loads(value) if value is not None else None
        except (RedisError, json.JSONDecodeError):
            return None

    def cache_set(self, key: str, value: object, ttl_seconds: int = 300) -> bool:
        if not self.client:
            return False
        try:
            return bool(self.client.setex(key, ttl_seconds, json.dumps(value)))
        except RedisError:
            return False

    def enqueue(self, queue: str, payload: dict) -> bool:
        if not self.client:
            return False
        try:
            self.client.rpush(f"queue:{queue}", json.dumps(payload))
            return True
        except RedisError:
            return False


redis_gateway = RedisGateway()
