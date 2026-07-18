import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings

def create_connection():
    return psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)

def get_db():
    # creates a connection with db
    conn = create_connection()
    try:
        # returns the connection request
        yield conn
    finally:
        # close the connection request
        conn.close()