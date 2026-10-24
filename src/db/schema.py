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
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            items_text TEXT NOT NULL,
            total_amount INTEGER NOT NULL DEFAULT 0,
            cod_amount INTEGER NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'COD',
            status TEXT NOT NULL DEFAULT 'CHO_LAM' CHECK (
                status IN (
                    'CHO_LAM',
                    'DANG_LAM',
                    'DA_DONG_GOI',
                    'DA_TAO_DON',
                    'SHIPPER_DA_LAY',
                    'DA_GIAO',
                    'BOM_HANG',
                    'HUY_DON'
                )
            ),
            tracking_code TEXT,
            photo_file_ids TEXT NOT NULL DEFAULT '[]',
            raw_text TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        );
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
        """
    )
    await db.commit()
