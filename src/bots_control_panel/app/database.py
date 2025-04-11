# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv() # Load .env file from project root

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

# Check if it's SQLite and adjust connect_args if needed
kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    # Needed for SQLite to allow usage across threads (FastAPI uses threads)
    kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency to get a DB session for a request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    """Creates database tables based on models."""
    # This is a simple way to ensure tables are created.
    # In production, you'd likely use Alembic for migrations.
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created (if they didn't exist).")
