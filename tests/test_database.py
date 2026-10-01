from sqlalchemy import create_engine, inspect, text

from app.database import apply_schema_compatibility


def test_schema_compatibility_adds_inspection_columns_to_legacy_operation_log_table():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE operation_logs (id TEXT PRIMARY KEY, payment_id TEXT, event_type TEXT, detail TEXT)"))

    apply_schema_compatibility(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("operation_logs")}
    assert {"request_headers", "request_body", "response_status", "response_headers", "response_body"} <= columns
