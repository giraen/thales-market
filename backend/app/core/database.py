import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings

def get_db():
    # creates a connection with db
    conn = psycopg2.connect(
        settings.DATABASE_URL,
        cursor_factory=RealDictCursor
    )
    try:
        # returns the connection request
        yield conn
    finally:
        # close the connection request
        conn.close()