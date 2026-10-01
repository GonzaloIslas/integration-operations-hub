from collections.abc import Generator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def apply_schema_compatibility(target_engine: Engine = engine) -> None:
    """Add V7 inspection columns to pre-existing local databases without data loss."""
    inspector = inspect(target_engine)
    if "operation_logs" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("operation_logs")}
    required_columns = {
        "request_headers": "TEXT",
        "request_body": "TEXT",
        "response_status": "INTEGER",
        "response_headers": "TEXT",
        "response_body": "TEXT",
    }
    with target_engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE operation_logs ADD COLUMN {column_name} {column_type}"))
