import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings

def get_db():
    conn = psycopg2.connect(
        settings.DATABASE_URL,
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()