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
            notes TEXT NOT NULL DEFAULT '',
            created_by_user_id INTEGER,
            created_by_name TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        );
        """
    )
    async with db.execute("PRAGMA table_info(orders);") as cursor:
        cols = {row[1] for row in await cursor.fetchall()}
        if "created_by_user_id" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN created_by_user_id INTEGER;")
        if "created_by_name" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN created_by_name TEXT;")
        if "notes" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN notes TEXT NOT NULL DEFAULT '';")
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
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            action TEXT NOT NULL CHECK (
                action IN ('CREATE', 'MUTATE', 'STATUS_CHANGE', 'TRACKING_UPDATE')
            ),
            changes_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        );
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_order_history_order_id ON order_history(order_id);
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL CHECK (role IN ('SUPER_ADMIN', 'ADMIN', 'STAFF')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await db.commit()
