import psycopg2
from app.core.config import settings

def create_tables():
    conn = psycopg2.connect(settings.DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_balances (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(36) UNIQUE NOT NULL,
            telegram_chat_id VARCHAR(50) UNIQUE,
            unallocated_cash NUMERIC(12, 2) DEFAULT 0.00,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_ledger (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            asset_class VARCHAR(10) CHECK (asset_class IN ('STOCK', 'OPTION', 'CRYPTO')) DEFAULT 'STOCK',
            ticker VARCHAR(10) NOT NULL,
            transaction_type VARCHAR(4) CHECK (transaction_type IN ('BUY', 'SELL')) NOT NULL,
            execution_price NUMERIC(12, 4) NOT NULL,
            quantity NUMERIC(18, 9) NOT NULL,
            fee_applied NUMERIC(6, 2) DEFAULT 0.99,
            total_cost_basis NUMERIC(12, 2) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Database tables verified.")