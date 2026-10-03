from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/autotube")

# Supabase's copy-paste pooler strings carry Prisma-only query params that
# libpq/psycopg2 rejects ("invalid connection option").
_url = make_url(DATABASE_URL).difference_update_query(
    ["pgbouncer", "connection_limit", "pool_timeout"]
)

engine = create_engine(_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
