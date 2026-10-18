"""Database setup and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from models import (
    Base,
    ProductType,
    LotSizingMethod,
    InventoryTransactionType,
)
import logging
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mrp.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger("mrp.database")

# (table, column, enum) pairs that were previously persisted using member *names*.
_LEGACY_ENUM_COLUMNS = (
    ("products", "product_type", ProductType),
    ("products", "lot_sizing_method", LotSizingMethod),
    ("inventory_transactions", "transaction_type", InventoryTransactionType),
)


def init_db():
    """Initialize database with tables."""
    Base.metadata.create_all(bind=engine)
    migrate_legacy_enum_values()


def migrate_legacy_enum_values():
    """Rewrite legacy enum member names ('RAW_MATERIAL') to their values ('raw_material').

    Older releases mapped these columns without ``values_callable``, so SQLite rows
    hold the upper-cased member names. The current mapping only understands values,
    and reading such a row raises ``LookupError``. This is idempotent.
    """
    name_to_value = {}
    for _, _, enum_cls in _LEGACY_ENUM_COLUMNS:
        name_to_value.update({member.name: member.value for member in enum_cls})

    with engine.begin() as conn:
        for table, column, enum_cls in _LEGACY_ENUM_COLUMNS:
            valid_values = {member.value for member in enum_cls}
            try:
                rows = conn.execute(text(f"SELECT DISTINCT {column} FROM {table}")).scalars().all()
            except Exception:  # table may not exist yet
                continue

            for raw in rows:
                if raw is None or raw in valid_values:
                    continue
                new_value = name_to_value.get(str(raw).upper())
                if new_value is None:
                    logger.warning("Unknown value %r in %s.%s; leaving as-is", raw, table, column)
                    continue
                conn.execute(
                    text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old"),
                    {"new": new_value, "old": raw},
                )
                logger.info("Migrated %s.%s: %r -> %r", table, column, raw, new_value)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
