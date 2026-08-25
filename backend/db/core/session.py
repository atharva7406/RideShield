import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_backend_dir, "env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Ensure postgresql:// scheme is used (replace postgres:// if present)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Run simple dynamic migration check for is_phone_verified column
from sqlalchemy import text
try:
    with engine.connect() as conn:
        res = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='users' AND column_name='is_phone_verified'"
        ))
        if not res.fetchone():
            conn.execute(text("ALTER TABLE users ADD COLUMN is_phone_verified BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.commit()
            print("[Migration] Added column is_phone_verified to users table.")
except Exception as e:
    print(f"[Migration] Auto-migration check failed: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency helper for FastAPI route handlers to obtain a DB session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
