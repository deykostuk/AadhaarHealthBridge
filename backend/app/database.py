import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
engine_kwargs = {}

if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
    # Enterprise PostgreSQL Connection Pooling Configuration
    engine_kwargs = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    }
    logger.info("Initializing SQLAlchemy with PostgreSQL connection pool.")
elif db_url.startswith("sqlite"):
    engine_kwargs = {
        "connect_args": {"check_same_thread": False}
    }
    logger.info("Initializing SQLAlchemy with local SQLite database.")

engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI database session generator dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
