"""Lightweight SQLite column migrations for existing databases."""

from sqlalchemy import inspect, text

from backend.core.payment_reference import allocate_unique_payment_reference, is_compact_payment_reference


def apply_sqlite_column_migrations(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS class_school_fees (
                    class_key VARCHAR(30) NOT NULL PRIMARY KEY,
                    amount REAL NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS village_van_fees (
                    village_key VARCHAR(80) NOT NULL PRIMARY KEY,
                    amount REAL NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS faculty_salaries (
                    id INTEGER NOT NULL PRIMARY KEY,
                    faculty_name VARCHAR(120) NOT NULL UNIQUE,
                    faculty_type VARCHAR(20) NOT NULL DEFAULT 'Teaching',
                    role VARCHAR(80) NOT NULL DEFAULT '',
                    monthly_salary REAL NOT NULL,
                    default_working_days INTEGER NOT NULL DEFAULT 26,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER NOT NULL PRIMARY KEY,
                    expense_type VARCHAR(20) NOT NULL,
                    category VARCHAR(80) NOT NULL,
                    person_name VARCHAR(120) NOT NULL DEFAULT '',
                    description VARCHAR(240) NOT NULL DEFAULT '',
                    amount REAL NOT NULL,
                    expense_date DATE NOT NULL,
                    month_label VARCHAR(20) NOT NULL DEFAULT '',
                    attendance_days REAL NOT NULL DEFAULT 0.0,
                    working_days REAL NOT NULL DEFAULT 0.0,
                    base_amount REAL NOT NULL DEFAULT 0.0,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS faculty_attendance (
                    id INTEGER NOT NULL PRIMARY KEY,
                    faculty_id_fk INTEGER NOT NULL REFERENCES faculty_salaries(id),
                    month_label VARCHAR(20) NOT NULL,
                    marked_days_csv TEXT NOT NULL DEFAULT '',
                    checked_days INTEGER NOT NULL DEFAULT 0,
                    sunday_days INTEGER NOT NULL DEFAULT 0,
                    attendance_days REAL NOT NULL DEFAULT 0.0,
                    working_days REAL NOT NULL DEFAULT 0.0,
                    created_at DATETIME,
                    updated_at DATETIME,
                    CONSTRAINT uq_faculty_attendance_month UNIQUE (faculty_id_fk, month_label)
                )
                """
            )
        )

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
        col_names2 = {c["name"] for c in inspect(engine).get_columns("students")}
        if "transport_mode" not in col_names2:
            conn.execute(
                text(
                    "ALTER TABLE students ADD COLUMN transport_mode VARCHAR(20) NOT NULL DEFAULT 'van'"
                )
            )

    if insp.has_table("payments"):
        pay_cols = {c["name"] for c in insp.get_columns("payments")}
        with engine.begin() as conn:
            if "discount_amount" not in pay_cols:
                conn.execute(
                    text("ALTER TABLE payments ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0.0")
                )
            if "school_amount" not in pay_cols:
                conn.execute(
                    text("ALTER TABLE payments ADD COLUMN school_amount REAL NOT NULL DEFAULT 0.0")
                )
            if "van_amount" not in pay_cols:
                conn.execute(
                    text("ALTER TABLE payments ADD COLUMN van_amount REAL NOT NULL DEFAULT 0.0")
                )
            if "is_reverted" not in pay_cols:
                conn.execute(
                    text("ALTER TABLE payments ADD COLUMN is_reverted BOOLEAN NOT NULL DEFAULT 0")
                )
            if "reverted_at" not in pay_cols:
                conn.execute(
                    text("ALTER TABLE payments ADD COLUMN reverted_at DATETIME")
                )
            if "reference_no" not in pay_cols:
                conn.execute(text("ALTER TABLE payments ADD COLUMN reference_no VARCHAR(16)"))

    if insp.has_table("invoices"):
        inv_cols = {c["name"] for c in insp.get_columns("invoices")}
        with engine.begin() as conn:
            if "academic_year_id" not in inv_cols:
                conn.execute(
                    text("ALTER TABLE invoices ADD COLUMN academic_year_id INTEGER REFERENCES academic_years(id)")
                )

    if insp.has_table("faculty_salaries"):
        fac_cols = {c["name"] for c in insp.get_columns("faculty_salaries")}
        with engine.begin() as conn:
            if "faculty_type" not in fac_cols:
                conn.execute(
                    text(
                        "ALTER TABLE faculty_salaries ADD COLUMN faculty_type VARCHAR(20) NOT NULL DEFAULT 'Teaching'"
                    )
                )

    if insp.has_table("faculty_attendance"):
        att_cols = {c["name"] for c in insp.get_columns("faculty_attendance")}
        with engine.begin() as conn:
            if "marked_days_csv" not in att_cols:
                conn.execute(
                    text("ALTER TABLE faculty_attendance ADD COLUMN marked_days_csv TEXT NOT NULL DEFAULT ''")
                )
            if "checked_days" not in att_cols:
                conn.execute(
                    text("ALTER TABLE faculty_attendance ADD COLUMN checked_days INTEGER NOT NULL DEFAULT 0")
                )
            if "sunday_days" not in att_cols:
                conn.execute(
                    text("ALTER TABLE faculty_attendance ADD COLUMN sunday_days INTEGER NOT NULL DEFAULT 0")
                )
            if "attendance_days" not in att_cols:
                conn.execute(
                    text("ALTER TABLE faculty_attendance ADD COLUMN attendance_days REAL NOT NULL DEFAULT 0.0")
                )
            if "working_days" not in att_cols:
                conn.execute(
                    text("ALTER TABLE faculty_attendance ADD COLUMN working_days REAL NOT NULL DEFAULT 0.0")
                )

    if insp.has_table("expenses"):
        exp_cols = {c["name"] for c in insp.get_columns("expenses")}
        with engine.begin() as conn:
            if "month_label" not in exp_cols:
                conn.execute(
                    text("ALTER TABLE expenses ADD COLUMN month_label VARCHAR(20) NOT NULL DEFAULT ''")
                )
            if "attendance_days" not in exp_cols:
                conn.execute(
                    text("ALTER TABLE expenses ADD COLUMN attendance_days REAL NOT NULL DEFAULT 0.0")
                )
            if "working_days" not in exp_cols:
                conn.execute(
                    text("ALTER TABLE expenses ADD COLUMN working_days REAL NOT NULL DEFAULT 0.0")
                )
            if "base_amount" not in exp_cols:
                conn.execute(
                    text("ALTER TABLE expenses ADD COLUMN base_amount REAL NOT NULL DEFAULT 0.0")
                )


def _default_academic_year_bounds(as_of):
    from datetime import date

    d = as_of or date.today()
    y = d.year
    if d >= date(y, 5, 17):
        return date(y, 5, 17), date(y + 1, 4, 18)
    return date(y - 1, 5, 17), date(y, 4, 18)


def apply_sqlite_data_migrations(engine) -> None:
    """One-time data fixes for existing SQLite databases (tracked in app_migrations)."""
    if engine.dialect.name != "sqlite":
        return
    try:
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

            row_vc = conn.execute(
                text("SELECT 1 FROM app_migrations WHERE name = :n"),
                {"n": "migrate_student_villages_to_fixed_list_v1"},
            ).fetchone()
            if not row_vc:
                fixed_lower = (
                    "nagaram",
                    "kamalapur",
                    "dharmapuri",
                    "thimmapur",
                    "thummenala",
                    "rayapatnam",
                    "rajaram",
                    "damannapet",
                    "jaina",
                    "edapelly",
                    "ramaiahpally",
                    "burugupally",
                    "ln colony",
                    "thenuguwada",
                    "arr colony",
                )
                in_list = ", ".join(f"'{v}'" for v in fixed_lower)
                conn.execute(
                    text(
                        f"""
                        UPDATE students SET village = CASE (ABS(COALESCE(id, 0)) % 15)
                            WHEN 0 THEN 'Nagaram'
                            WHEN 1 THEN 'Kamalapur'
                            WHEN 2 THEN 'Dharmapuri'
                            WHEN 3 THEN 'Thimmapur'
                            WHEN 4 THEN 'Thummenala'
                            WHEN 5 THEN 'Rayapatnam'
                            WHEN 6 THEN 'Rajaram'
                            WHEN 7 THEN 'Damannapet'
                            WHEN 8 THEN 'Jaina'
                            WHEN 9 THEN 'Edapelly'
                            WHEN 10 THEN 'Ramaiahpally'
                            WHEN 11 THEN 'Burugupally'
                            WHEN 12 THEN 'LN Colony'
                            WHEN 13 THEN 'Thenuguwada'
                            ELSE 'ARR Colony'
                        END
                        WHERE lower(trim(COALESCE(village, ''))) NOT IN ({in_list})
                        """
                    )
                )
                conn.execute(
                    text("INSERT INTO app_migrations (name) VALUES ('migrate_student_villages_to_fixed_list_v1')")
                )
    finally:
        _migrate_payments_receipt_to_uuid_reference(engine)


def _sqlite_rebuild_payments_strip_receipt(conn) -> None:
    """SQLite cannot reliably DROP COLUMN receipt_no when UNIQUE(receipt_no) exists; rebuild tables."""
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(text("DROP TABLE IF EXISTS payments_backup_mig"))
    conn.execute(text("DROP TABLE IF EXISTS payment_allocations_backup_mig"))

    has_alloc = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_allocations'")
    ).fetchone()

    if has_alloc:
        conn.execute(text("CREATE TABLE payment_allocations_backup_mig AS SELECT * FROM payment_allocations"))
        conn.execute(text("DROP TABLE payment_allocations"))

    conn.execute(
        text(
            "CREATE TABLE payments_backup_mig AS "
            "SELECT id, student_id_fk, payment_date, amount, COALESCE(discount_amount, 0) AS discount_amount, "
            "mode, operator_name, reference_no, receipt_no FROM payments"
        )
    )
    conn.execute(text("DROP TABLE payments"))

    conn.execute(
        text(
            """
            CREATE TABLE payments (
                id INTEGER NOT NULL,
                student_id_fk INTEGER NOT NULL,
                payment_date DATE NOT NULL,
                amount FLOAT NOT NULL,
                school_amount REAL NOT NULL DEFAULT 0.0,
                van_amount REAL NOT NULL DEFAULT 0.0,
                discount_amount REAL NOT NULL DEFAULT 0.0,
                mode VARCHAR(20) NOT NULL,
                reference_no VARCHAR(16) NOT NULL,
                operator_name VARCHAR(60) NOT NULL,
                is_reverted BOOLEAN NOT NULL DEFAULT 0,
                reverted_at DATETIME,
                PRIMARY KEY (id),
                FOREIGN KEY (student_id_fk) REFERENCES students (id)
            )
            """
        )
    )

    pay_rows = conn.execute(
        text(
            "SELECT id, student_id_fk, payment_date, amount, discount_amount, mode, operator_name, reference_no "
            "FROM payments_backup_mig"
        )
    ).fetchall()

    inserted_refs: set[str] = set()
    for pid, sid, pdate, amt, disc, mode, op, ref in pay_rows:
        r = ((ref or "").strip())
        if is_compact_payment_reference(r) and r not in inserted_refs:
            ref_s = r
        else:

            def _exists_rebuild(c: str, _inserted=inserted_refs) -> bool:
                if c in _inserted:
                    return True
                hit = conn.execute(
                    text("SELECT 1 FROM payments_backup_mig WHERE TRIM(COALESCE(reference_no, '')) = :c"),
                    {"c": c},
                ).fetchone()
                return hit is not None

            ref_s = allocate_unique_payment_reference(_exists_rebuild)
        inserted_refs.add(ref_s)
        conn.execute(
            text(
                "INSERT INTO payments "
                "(id, student_id_fk, payment_date, amount, school_amount, van_amount, discount_amount, mode, reference_no, operator_name, is_reverted, reverted_at) "
                "VALUES (:id, :sid, :pdate, :amt, :school, :van, :disc, :mode, :ref, :op, :reverted, :rev_at)"
            ),
            {
                "id": pid,
                "sid": sid,
                "pdate": pdate,
                "amt": amt,
                "school": 0.0,
                "van": 0.0,
                "disc": disc,
                "mode": mode,
                "ref": ref_s,
                "op": op,
                "reverted": 0,
                "rev_at": None,
            },
        )

    if has_alloc:
        conn.execute(
            text(
                """
                CREATE TABLE payment_allocations (
                    id INTEGER NOT NULL,
                    payment_id INTEGER NOT NULL,
                    invoice_id INTEGER NOT NULL,
                    allocated_amount FLOAT NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY (payment_id) REFERENCES payments (id),
                    FOREIGN KEY (invoice_id) REFERENCES invoices (id)
                )
                """
            )
        )
        conn.execute(text("INSERT INTO payment_allocations SELECT * FROM payment_allocations_backup_mig"))
        conn.execute(text("DROP TABLE payment_allocations_backup_mig"))

    conn.execute(text("DROP TABLE payments_backup_mig"))
    seq = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
    ).fetchone()
    if seq:
        mx = conn.execute(text("SELECT MAX(id) FROM payments")).scalar()
        if mx is not None:
            conn.execute(text("DELETE FROM sqlite_sequence WHERE name = 'payments'"))
            conn.execute(text("INSERT INTO sqlite_sequence (name, seq) VALUES ('payments', :m)"), {"m": int(mx)})
    conn.execute(text("PRAGMA foreign_keys=ON"))


def _migrate_payments_receipt_to_uuid_reference(engine) -> None:
    """Backfill payment reference_no; drop legacy receipt_no; normalize to compact alphanumeric codes."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("payments"):
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row_done = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "payments_uuid_reference_v1"},
        ).fetchone()

        def payment_column_names() -> set[str]:
            return {r[1] for r in conn.execute(text("PRAGMA table_info(payments)")).fetchall()}

        cols = payment_column_names()
        if "reference_no" not in cols:
            conn.execute(text("ALTER TABLE payments ADD COLUMN reference_no VARCHAR(16)"))
            cols = payment_column_names()

        if not row_done:
            rows = conn.execute(
                text("SELECT id FROM payments WHERE reference_no IS NULL OR TRIM(COALESCE(reference_no, '')) = ''")
            ).fetchall()
            for (pid,) in rows:

                def _exists_empty(c: str, _conn=conn) -> bool:
                    return (
                        _conn.execute(text("SELECT 1 FROM payments WHERE reference_no = :c"), {"c": c}).fetchone()
                        is not None
                    )

                cand = allocate_unique_payment_reference(_exists_empty)
                conn.execute(
                    text("UPDATE payments SET reference_no = :ref WHERE id = :id"),
                    {"ref": cand, "id": pid},
                )

        cols = payment_column_names()
        if "receipt_no" in cols:
            _sqlite_rebuild_payments_strip_receipt(conn)

        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_reference_no ON payments(reference_no)"))

        if not row_done:
            conn.execute(text("INSERT INTO app_migrations (name) VALUES ('payments_uuid_reference_v1')"))

        _migrate_payments_to_compact_reference_sqlite(conn)
        _migrate_academic_years_v1(conn)


def _migrate_academic_years_v1(conn) -> None:
    from datetime import date

    row = conn.execute(
        text("SELECT 1 FROM app_migrations WHERE name = :n"),
        {"n": "academic_years_v1"},
    ).fetchone()
    if row:
        return

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS academic_years (
                id INTEGER NOT NULL PRIMARY KEY,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                label VARCHAR(40) NOT NULL DEFAULT ''
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS student_academic_year_fees (
                id INTEGER NOT NULL PRIMARY KEY,
                student_id_fk INTEGER NOT NULL REFERENCES students(id),
                academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
                school_fees REAL NOT NULL DEFAULT 0.0,
                van_fees REAL NOT NULL DEFAULT 0.0,
                CONSTRAINT uq_student_academic_year UNIQUE (student_id_fk, academic_year_id)
            )
            """
        )
    )

    n_years = conn.execute(text("SELECT COUNT(*) FROM academic_years")).scalar() or 0
    if n_years == 0:
        start, end = _default_academic_year_bounds(date.today())
        conn.execute(
            text(
                "INSERT INTO academic_years (start_date, end_date, label) "
                "VALUES (:s, :e, :lbl)"
            ),
            {"s": start.isoformat(), "e": end.isoformat(), "lbl": f"{start.year}-{str(end.year)[-2:]}"},
        )

    year_id = conn.execute(text("SELECT id FROM academic_years ORDER BY start_date ASC LIMIT 1")).scalar()
    if year_id is not None:
        conn.execute(
            text("UPDATE invoices SET academic_year_id = :yid WHERE academic_year_id IS NULL"),
            {"yid": int(year_id)},
        )

    students = conn.execute(
        text("SELECT id, school_fees, van_fees FROM students")
    ).fetchall()
    years = conn.execute(text("SELECT id FROM academic_years ORDER BY start_date ASC")).fetchall()
    for st_id, school_fees, van_fees in students:
        for (yid,) in years:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM student_academic_year_fees "
                    "WHERE student_id_fk = :sid AND academic_year_id = :yid"
                ),
                {"sid": int(st_id), "yid": int(yid)},
            ).fetchone()
            if not exists:
                conn.execute(
                    text(
                        "INSERT INTO student_academic_year_fees "
                        "(student_id_fk, academic_year_id, school_fees, van_fees) "
                        "VALUES (:sid, :yid, :sf, :vf)"
                    ),
                    {
                        "sid": int(st_id),
                        "yid": int(yid),
                        "sf": float(school_fees or 0.0),
                        "vf": float(van_fees or 0.0),
                    },
                )

    conn.execute(text("INSERT INTO app_migrations (name) VALUES ('academic_years_v1')"))


def _migrate_payments_to_compact_reference_sqlite(conn) -> None:
    """Replace UUID / long references with 12-char A-Z0-9 codes. Idempotent."""
    row = conn.execute(
        text("SELECT 1 FROM app_migrations WHERE name = :n"),
        {"n": "payments_alnum_reference_v1"},
    ).fetchone()
    if row:
        return

    rows = conn.execute(text("SELECT id, reference_no FROM payments")).fetchall()
    reserved = set()
    for _pid, ref in rows:
        r = (ref or "").strip()
        if is_compact_payment_reference(r):
            reserved.add(r)

    for pid, ref in rows:
        r = (ref or "").strip()
        if is_compact_payment_reference(r):
            continue

        def _exists_compact(
            c: str,
            _conn=conn,
            _res=reserved,
        ) -> bool:
            if c in _res:
                return True
            return (
                _conn.execute(text("SELECT 1 FROM payments WHERE reference_no = :c"), {"c": c}).fetchone()
                is not None
            )

        cand = allocate_unique_payment_reference(_exists_compact)
        conn.execute(text("UPDATE payments SET reference_no = :c WHERE id = :id"), {"c": cand, "id": pid})
        reserved.add(cand)

    conn.execute(text("INSERT INTO app_migrations (name) VALUES ('payments_alnum_reference_v1')"))
