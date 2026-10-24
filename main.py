import asyncio
import logging

from src.bot.app import build_application
from src.config import Settings
from src.db.connection import get_db_connection
from src.db.schema import init_db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def init_database(db_path: str) -> None:
    """Initialize database and ensure tables exist."""
    async with get_db_connection(db_path) as db:
        await init_db(db)
    logger.info("Database schema initialized successfully at %s", db_path)


def main() -> None:
    """Bot entrypoint: initialize database and start polling."""
    settings = Settings()
    logger.info("Starting Cassette Store Bot...")

    # Run database initialization
    asyncio.run(init_database(settings.sqlite_db_path))

    # Build PTB application
    app = build_application(settings)

    # Start long-polling
    logger.info("Bot is ready. Starting polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
