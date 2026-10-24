import pytest_asyncio

from src.db.connection import get_db_connection
from src.db.schema import init_db


@pytest_asyncio.fixture
async def test_db():
    """In-memory SQLite connection fixture with initialized schema."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)
        yield db
