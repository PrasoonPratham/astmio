
import asyncio
import random
from functools import wraps
from typing import Any, Callable, Type

from ..exceptions import ConnectionError
from ..logging import get_logger

log = get_logger(__name__)


def retry(
    attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: Type[Exception] = ConnectionError,
) -> Callable:
    """
    A decorator for retrying a function with exponential backoff.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal delay
            for attempt in range(attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == attempts - 1:
                        log.error(
                            "Function failed after all retry attempts",
                            func_name=func.__name__,
                            attempt=attempt + 1,
                            error=str(e),
                        )
                        raise
                    log.warning(
                        "Function failed, retrying...",
                        func_name=func.__name__,
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
                    delay += random.uniform(0, jitter)

        return wrapper

    return decorator 