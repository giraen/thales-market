import psycopg2
from app.core.config import settings

def create_tables():
    conn = psycopg2.connect(settings.DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_balances (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(128) UNIQUE NOT NULL,
            unallocated_cash NUMERIC(12, 2) DEFAULT 0.00,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_ledger (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(128) NOT NULL,
            asset_class VARCHAR(10) CHECK (asset_class IN ('STOCK', 'OPTION', 'CRYPTO')) DEFAULT 'STOCK',
            ticker VARCHAR(20) NOT NULL,
            transaction_type VARCHAR(4) CHECK (transaction_type IN ('BUY', 'SELL')) NOT NULL,
            execution_price NUMERIC(12, 8) NOT NULL,
            quantity NUMERIC(20, 9) NOT NULL,
            fee_applied NUMERIC(6, 2) DEFAULT 0.99,
            total_cost_basis NUMERIC(12, 2) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(128) UNIQUE NOT NULL,
            telegram_chat_id VARCHAR(128) UNIQUE,
            expo_push_token VARCHAR(255),
            timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Manila',
            theme VARCHAR(10) NOT NULL DEFAULT 'system' CHECK (theme IN ('light', 'dark', 'system')),
            active_indicators JSONB NOT NULL DEFAULT '["VWAP","RSI","BOLLINGER","SMA","OBV","ATR","GARMAN_KLASS","ZSCORE"]',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(128) NOT NULL,
            ticker VARCHAR(20) NOT NULL,
            asset_class VARCHAR(10) CHECK (asset_class IN ('STOCK', 'OPTION', 'CRYPTO')) DEFAULT 'STOCK',
            added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_buy_decision VARCHAR(10),
            last_buy_notified_at TIMESTAMP WITH TIME ZONE,
            last_sell_decision VARCHAR(10),
            last_sell_notified_at TIMESTAMP WITH TIME ZONE,
            cached_peg_ratio NUMERIC(10, 4),
            peg_fetched_at TIMESTAMP WITH TIME ZONE,
            UNIQUE(user_id, ticker)
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Database tables verified.")