"""Lightweight SQLite column migrations for existing databases."""

from sqlalchemy import inspect, text


def apply_sqlite_column_migrations(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("students"):
        return
    col_names = {c["name"] for c in insp.get_columns("students")}
    with engine.begin() as conn:
        if "van_fees" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN van_fees REAL NOT NULL DEFAULT 0.0")
            )
        if "school_fees" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN school_fees REAL NOT NULL DEFAULT 20000.0")
            )
        if "village" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN village VARCHAR(80) NOT NULL DEFAULT ''")
            )

    if insp.has_table("payments"):
        pay_cols = {c["name"] for c in insp.get_columns("payments")}
        with engine.begin() as conn:
            if "discount_amount" not in pay_cols:
                conn.execute(
                    text("ALTER TABLE payments ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0.0")
                )
            if "reference_no" in pay_cols:
                conn.execute(text("ALTER TABLE payments DROP COLUMN reference_no"))


def apply_sqlite_data_migrations(engine) -> None:
    """One-time data fixes for existing SQLite databases (tracked in app_migrations)."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("students"):
        return
    col_names = {c["name"] for c in insp.get_columns("students")}
    if "school_fees" not in col_names:
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "backfill_school_fees_zero_to_20000_v1"},
        ).fetchone()
        if not row:
            conn.execute(
                text(
                    "UPDATE students SET school_fees = 20000.0 "
                    "WHERE school_fees IS NULL OR ABS(COALESCE(school_fees, 0)) < 1e-6"
                )
            )
            conn.execute(
                text("INSERT INTO app_migrations (name) VALUES ('backfill_school_fees_zero_to_20000_v1')")
            )

        col_now = {c["name"] for c in inspect(engine).get_columns("students")}
        if "village" not in col_now:
            return
        row_v = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "backfill_village_sample_v1"},
        ).fetchone()
        if not row_v:
            conn.execute(
                text(
                    """
                    UPDATE students SET village = CASE (ABS(id) % 16)
                        WHEN 0 THEN 'Rampur'
                        WHEN 1 THEN 'Bisrakh'
                        WHEN 2 THEN 'Dadri'
                        WHEN 3 THEN 'Muradnagar'
                        WHEN 4 THEN 'Modinagar'
                        WHEN 5 THEN 'Hapur'
                        WHEN 6 THEN 'Garhmukteshwar'
                        WHEN 7 THEN 'Simbhawali'
                        WHEN 8 THEN 'Baraut'
                        WHEN 9 THEN 'Baghpat'
                        WHEN 10 THEN 'Sardhana'
                        WHEN 11 THEN 'Daurala'
                        WHEN 12 THEN 'Partapur'
                        WHEN 13 THEN 'Khekra'
                        WHEN 14 THEN 'Loni'
                        ELSE 'Ghaziabad'
                    END
                    WHERE TRIM(COALESCE(village, '')) = ''
                    """
                )
            )
            conn.execute(
                text("INSERT INTO app_migrations (name) VALUES ('backfill_village_sample_v1')")
            )
