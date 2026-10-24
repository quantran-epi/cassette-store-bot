import aiosqlite


async def init_db(db: aiosqlite.Connection) -> None:
    """Initialize database tables and indices."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phones TEXT NOT NULL DEFAULT '[]',
            addresses TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
        """
    )
    await db.commit()
