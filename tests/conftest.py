import pytest
from asyncio import get_event_loop


@pytest.fixture(scope="session")
def event_loop():
    """
    Creates an instance of the default event loop for the test session.
    """
    loop = get_event_loop()
    yield loop
    loop.close()
