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
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS misc_expenses (
                    id INTEGER NOT NULL PRIMARY KEY,
                    head VARCHAR(80) NOT NULL,
                    expense_date DATE NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS misc_expense_entries (
                    id INTEGER NOT NULL PRIMARY KEY,
                    expense_id INTEGER NOT NULL REFERENCES misc_expenses(id),
                    entry_date DATE NOT NULL,
                    particular VARCHAR(240) NOT NULL,
                    amount REAL NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME
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
        if "gender" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN gender VARCHAR(20) NOT NULL DEFAULT ''")
            )
        if "father_name" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN father_name VARCHAR(120) NOT NULL DEFAULT ''")
            )
        if "mother_name" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN mother_name VARCHAR(120) NOT NULL DEFAULT ''")
            )
        if "mobile_number_1" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN mobile_number_1 VARCHAR(20) NOT NULL DEFAULT ''")
            )
        if "mobile_number_2" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN mobile_number_2 VARCHAR(20) NOT NULL DEFAULT ''")
            )
        if "date_of_birth" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN date_of_birth DATE")
            )
        if "caste" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN caste VARCHAR(80) NOT NULL DEFAULT ''")
            )
        if "aadhaar" not in col_names:
            conn.execute(
                text("ALTER TABLE students ADD COLUMN aadhaar VARCHAR(20) NOT NULL DEFAULT ''")
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
            if "reference_no" not in exp_cols:
                conn.execute(text("ALTER TABLE expenses ADD COLUMN reference_no VARCHAR(16)"))
            if "operator_name" not in exp_cols:
                conn.execute(
                    text(
                        "ALTER TABLE expenses ADD COLUMN operator_name VARCHAR(80) NOT NULL DEFAULT ''"
                    )
                )
            if "is_reverted" not in exp_cols:
                conn.execute(
                    text("ALTER TABLE expenses ADD COLUMN is_reverted BOOLEAN NOT NULL DEFAULT 0")
                )
            if "reverted_at" not in exp_cols:
                conn.execute(text("ALTER TABLE expenses ADD COLUMN reverted_at DATETIME"))
            if "faculty_type" not in exp_cols:
                conn.execute(
                    text(
                        "ALTER TABLE expenses ADD COLUMN faculty_type VARCHAR(20) NOT NULL DEFAULT ''"
                    )
                )
        _backfill_salary_expense_references(engine)
        _backfill_salary_expense_faculty_type(engine)
        _dedupe_salary_expenses_per_faculty_month(engine)
        if insp.has_table("student_academic_year_fees"):
            sy_cols = {c["name"] for c in insp.get_columns("student_academic_year_fees")}
            if "opening_pending_fees" not in sy_cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE student_academic_year_fees "
                            "ADD COLUMN opening_pending_fees REAL NOT NULL DEFAULT 0.0"
                        )
                    )
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_expenses_salary_reference_no "
                    "ON expenses(reference_no) WHERE reference_no IS NOT NULL "
                    "AND TRIM(reference_no) != ''"
                )
            )

    _migrate_misc_expenses_remove_categories(engine)
    _dedupe_misc_expenses_same_identity(engine)
    _dedupe_misc_expenses_by_head(engine)
    _backfill_misc_expense_entry_dates(engine)
    _migrate_misc_expense_entry_revert_columns(engine)
    _backfill_payment_split_amounts(engine)
    _migrate_class_school_fees_per_year(engine)


def _migrate_class_school_fees_per_year(engine) -> None:
    """Scope class_school_fees by academic_year_id (one tariff matrix per year)."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("class_school_fees"):
        return
    cols = {c["name"] for c in insp.get_columns("class_school_fees")}
    if "academic_year_id" in cols:
        return

    from backend.core.fee_control_constants import FIXED_CLASS_KEYS

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        if conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "class_school_fees_per_year_v1"},
        ).fetchone():
            return

        conn.execute(text("CREATE TABLE IF NOT EXISTS class_school_fees_backup_mig AS SELECT * FROM class_school_fees"))
        old_rows = conn.execute(text("SELECT class_key, amount FROM class_school_fees_backup_mig")).fetchall()
        old_map = {str(k): float(a) for k, a in old_rows}

        conn.execute(text("DROP TABLE class_school_fees"))
        conn.execute(
            text(
                """
                CREATE TABLE class_school_fees (
                    class_key VARCHAR(30) NOT NULL,
                    academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
                    amount REAL NOT NULL,
                    PRIMARY KEY (class_key, academic_year_id)
                )
                """
            )
        )

        year_ids = [
            int(r[0])
            for r in conn.execute(text("SELECT id FROM academic_years ORDER BY start_date ASC")).fetchall()
        ]
        if not year_ids:
            from datetime import date

            start, end = _default_academic_year_bounds(date.today())
            conn.execute(
                text(
                    "INSERT INTO academic_years (start_date, end_date, label) "
                    "VALUES (:s, :e, :l)"
                ),
                {"s": start.isoformat(), "e": end.isoformat(), "l": ""},
            )
            year_ids = [int(conn.execute(text("SELECT last_insert_rowid()")).scalar())]

        for year_id in year_ids:
            for class_key in FIXED_CLASS_KEYS:
                amount = old_map.get(class_key, 20000.0)
                conn.execute(
                    text(
                        "INSERT INTO class_school_fees (class_key, academic_year_id, amount) "
                        "VALUES (:k, :y, :a)"
                    ),
                    {"k": class_key, "y": year_id, "a": amount},
                )

        conn.execute(text("DROP TABLE class_school_fees_backup_mig"))
        conn.execute(text("INSERT INTO app_migrations (name) VALUES ('class_school_fees_per_year_v1')"))


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
                        UPDATE students SET village = CASE (ABS(length(COALESCE(student_id, '')) + length(COALESCE(full_name, ''))) % 16)
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
                        UPDATE students SET village = CASE (ABS(length(COALESCE(student_id, '')) + length(COALESCE(full_name, ''))) % 15)
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

            row_gender = conn.execute(
                text("SELECT 1 FROM app_migrations WHERE name = :n"),
                {"n": "normalize_student_gender_male_female_v1"},
            ).fetchone()
            if not row_gender and "gender" in col_now:
                conn.execute(
                    text(
                        """
                        UPDATE students
                        SET gender = CASE lower(trim(COALESCE(gender, '')))
                            WHEN 'boy' THEN 'Male'
                            WHEN 'male' THEN 'Male'
                            WHEN 'girl' THEN 'Female'
                            WHEN 'female' THEN 'Female'
                            ELSE gender
                        END
                        """
                    )
                )
                conn.execute(
                    text("INSERT INTO app_migrations (name) VALUES ('normalize_student_gender_male_female_v1')")
                )

            row_student_pk = conn.execute(
                text("SELECT 1 FROM app_migrations WHERE name = :n"),
                {"n": "students_student_id_primary_v1"},
            ).fetchone()
            if not row_student_pk:
                col_after = {c[1] for c in conn.execute(text("PRAGMA table_info(students)")).fetchall()}
                if "id" in col_after:
                    _migrate_students_student_id_primary_sqlite(conn)
                conn.execute(
                    text("INSERT INTO app_migrations (name) VALUES ('students_student_id_primary_v1')")
                )

    finally:
        _migrate_payments_receipt_to_uuid_reference(engine)


def _migrate_students_student_id_primary_sqlite(conn) -> None:
    """Rebuild student-linked tables to use students.student_id as the primary key."""
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(text("DROP TABLE IF EXISTS students_backup_mig"))
    conn.execute(text("DROP TABLE IF EXISTS student_id_map_mig"))
    conn.execute(text("DROP TABLE IF EXISTS invoices_backup_mig"))
    conn.execute(text("DROP TABLE IF EXISTS payments_backup_sid_mig"))
    conn.execute(text("DROP TABLE IF EXISTS fee_plans_backup_mig"))
    conn.execute(text("DROP TABLE IF EXISTS student_year_fees_backup_mig"))

    conn.execute(text("CREATE TABLE students_backup_mig AS SELECT * FROM students"))
    conn.execute(
        text(
            "CREATE TABLE student_id_map_mig AS "
            "SELECT id AS old_id, student_id FROM students_backup_mig"
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE students_new (
                student_id VARCHAR(20) NOT NULL PRIMARY KEY,
                full_name VARCHAR(120) NOT NULL,
                gender VARCHAR(20) NOT NULL DEFAULT '',
                father_name VARCHAR(120) NOT NULL DEFAULT '',
                mother_name VARCHAR(120) NOT NULL DEFAULT '',
                class_name VARCHAR(20) NOT NULL,
                section VARCHAR(10) DEFAULT '',
                phone VARCHAR(20) NOT NULL,
                mobile_number_1 VARCHAR(20) NOT NULL DEFAULT '',
                mobile_number_2 VARCHAR(20) NOT NULL DEFAULT '',
                date_of_birth DATE,
                caste VARCHAR(80) NOT NULL DEFAULT '',
                aadhaar VARCHAR(20) NOT NULL DEFAULT '',
                village VARCHAR(80) NOT NULL DEFAULT '',
                guardian_name VARCHAR(120) DEFAULT '',
                status VARCHAR(20) DEFAULT 'active',
                transport_mode VARCHAR(20) NOT NULL DEFAULT 'van',
                van_fees REAL NOT NULL DEFAULT 0.0,
                school_fees REAL NOT NULL DEFAULT 20000.0,
                created_at DATETIME
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO students_new (
                student_id, full_name, gender, father_name, mother_name,
                class_name, section, phone, mobile_number_1, mobile_number_2,
                date_of_birth, caste, aadhaar, village, guardian_name, status,
                transport_mode, van_fees, school_fees, created_at
            )
            SELECT
                student_id,
                full_name,
                COALESCE(gender, ''),
                COALESCE(father_name, ''),
                COALESCE(mother_name, ''),
                class_name,
                COALESCE(section, ''),
                COALESCE(phone, ''),
                COALESCE(mobile_number_1, COALESCE(phone, '')),
                COALESCE(mobile_number_2, ''),
                date_of_birth,
                COALESCE(caste, ''),
                COALESCE(aadhaar, ''),
                COALESCE(village, ''),
                COALESCE(guardian_name, ''),
                COALESCE(status, 'active'),
                COALESCE(transport_mode, 'van'),
                COALESCE(van_fees, 0.0),
                COALESCE(school_fees, 20000.0),
                created_at
            FROM students_backup_mig
            """
        )
    )
    conn.execute(text("DROP TABLE students"))
    conn.execute(text("ALTER TABLE students_new RENAME TO students"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_students_name ON students(full_name)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_students_phone ON students(phone)"))

    has_invoices = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='invoices'")
    ).fetchone()
    if has_invoices:
        conn.execute(text("CREATE TABLE invoices_backup_mig AS SELECT * FROM invoices"))
        conn.execute(text("DROP TABLE invoices"))
        conn.execute(
            text(
                """
                CREATE TABLE invoices (
                    id INTEGER NOT NULL PRIMARY KEY,
                    student_id_fk VARCHAR(20) NOT NULL REFERENCES students(student_id),
                    academic_year_id INTEGER REFERENCES academic_years(id),
                    fee_head_id INTEGER NOT NULL REFERENCES fee_heads(id),
                    period_label VARCHAR(20) NOT NULL,
                    due_date DATE NOT NULL,
                    amount_due FLOAT NOT NULL,
                    amount_paid FLOAT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO invoices
                (id, student_id_fk, academic_year_id, fee_head_id, period_label, due_date, amount_due, amount_paid)
                SELECT
                    i.id, m.student_id, i.academic_year_id, i.fee_head_id, i.period_label,
                    i.due_date, i.amount_due, i.amount_paid
                FROM invoices_backup_mig i
                JOIN student_id_map_mig m ON m.old_id = i.student_id_fk
                """
            )
        )
        conn.execute(text("DROP TABLE invoices_backup_mig"))

    has_payments = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payments'")
    ).fetchone()
    if has_payments:
        conn.execute(text("CREATE TABLE payments_backup_sid_mig AS SELECT * FROM payments"))
        conn.execute(text("DROP TABLE payments"))
        conn.execute(
            text(
                """
                CREATE TABLE payments (
                    id INTEGER NOT NULL PRIMARY KEY,
                    student_id_fk VARCHAR(20) NOT NULL REFERENCES students(student_id),
                    payment_date DATE NOT NULL,
                    amount FLOAT NOT NULL,
                    school_amount REAL NOT NULL DEFAULT 0.0,
                    van_amount REAL NOT NULL DEFAULT 0.0,
                    discount_amount REAL NOT NULL DEFAULT 0.0,
                    mode VARCHAR(20) NOT NULL,
                    reference_no VARCHAR(16),
                    operator_name VARCHAR(60) NOT NULL,
                    is_reverted BOOLEAN NOT NULL DEFAULT 0,
                    reverted_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO payments
                (id, student_id_fk, payment_date, amount, school_amount, van_amount, discount_amount, mode, reference_no, operator_name, is_reverted, reverted_at)
                SELECT
                    p.id, m.student_id, p.payment_date, p.amount,
                    COALESCE(p.school_amount, 0.0), COALESCE(p.van_amount, 0.0), COALESCE(p.discount_amount, 0.0),
                    p.mode, p.reference_no, p.operator_name, COALESCE(p.is_reverted, 0), p.reverted_at
                FROM payments_backup_sid_mig p
                JOIN student_id_map_mig m ON m.old_id = p.student_id_fk
                """
            )
        )
        conn.execute(text("DROP TABLE payments_backup_sid_mig"))

    has_fee_plans = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fee_plans'")
    ).fetchone()
    if has_fee_plans:
        conn.execute(text("CREATE TABLE fee_plans_backup_mig AS SELECT * FROM fee_plans"))
        conn.execute(text("DROP TABLE fee_plans"))
        conn.execute(
            text(
                """
                CREATE TABLE fee_plans (
                    id INTEGER NOT NULL PRIMARY KEY,
                    student_id_fk VARCHAR(20) NOT NULL REFERENCES students(student_id),
                    fee_head_id INTEGER NOT NULL REFERENCES fee_heads(id),
                    amount FLOAT NOT NULL,
                    concession_amount FLOAT,
                    effective_from DATE,
                    CONSTRAINT uq_student_fee_head UNIQUE (student_id_fk, fee_head_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO fee_plans
                (id, student_id_fk, fee_head_id, amount, concession_amount, effective_from)
                SELECT fp.id, m.student_id, fp.fee_head_id, fp.amount, fp.concession_amount, fp.effective_from
                FROM fee_plans_backup_mig fp
                JOIN student_id_map_mig m ON m.old_id = fp.student_id_fk
                """
            )
        )
        conn.execute(text("DROP TABLE fee_plans_backup_mig"))

    has_year_fees = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='student_academic_year_fees'")
    ).fetchone()
    if has_year_fees:
        conn.execute(text("CREATE TABLE student_year_fees_backup_mig AS SELECT * FROM student_academic_year_fees"))
        conn.execute(text("DROP TABLE student_academic_year_fees"))
        conn.execute(
            text(
                """
                CREATE TABLE student_academic_year_fees (
                    id INTEGER NOT NULL PRIMARY KEY,
                    student_id_fk VARCHAR(20) NOT NULL REFERENCES students(student_id),
                    academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
                    school_fees REAL NOT NULL DEFAULT 0.0,
                    van_fees REAL NOT NULL DEFAULT 0.0,
                    CONSTRAINT uq_student_academic_year UNIQUE (student_id_fk, academic_year_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO student_academic_year_fees
                (id, student_id_fk, academic_year_id, school_fees, van_fees)
                SELECT sy.id, m.student_id, sy.academic_year_id, sy.school_fees, sy.van_fees
                FROM student_year_fees_backup_mig sy
                JOIN student_id_map_mig m ON m.old_id = sy.student_id_fk
                """
            )
        )
        conn.execute(text("DROP TABLE student_year_fees_backup_mig"))

    conn.execute(text("DROP TABLE student_id_map_mig"))
    conn.execute(text("DROP TABLE students_backup_mig"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


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
                student_id_fk VARCHAR(20) NOT NULL,
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
                FOREIGN KEY (student_id_fk) REFERENCES students (student_id)
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
                student_id_fk VARCHAR(20) NOT NULL REFERENCES students(student_id),
                academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
                school_fees REAL NOT NULL DEFAULT 0.0,
                van_fees REAL NOT NULL DEFAULT 0.0,
                opening_pending_fees REAL NOT NULL DEFAULT 0.0,
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
        text("SELECT student_id, school_fees, van_fees FROM students")
    ).fetchall()
    years = conn.execute(text("SELECT id FROM academic_years ORDER BY start_date ASC")).fetchall()
    for st_id, school_fees, van_fees in students:
        for (yid,) in years:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM student_academic_year_fees "
                    "WHERE student_id_fk = :sid AND academic_year_id = :yid"
                ),
                {"sid": str(st_id), "yid": int(yid)},
            ).fetchone()
            if not exists:
                conn.execute(
                    text(
                        "INSERT INTO student_academic_year_fees "
                        "(student_id_fk, academic_year_id, school_fees, van_fees) "
                        "VALUES (:sid, :yid, :sf, :vf)"
                    ),
                    {
                        "sid": str(st_id),
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


def _backfill_salary_expense_references(engine) -> None:
    """Assign reference_no to existing salary expense rows."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("expenses"):
        return
    from backend.core.salary_reference import allocate_unique_salary_reference

    with engine.begin() as conn:
        exp_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(expenses)")).fetchall()}
        if "reference_no" not in exp_cols:
            return
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row_done = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "salary_expense_reference_v1"},
        ).fetchone()
        if row_done:
            return
        rows = conn.execute(
            text(
                "SELECT id FROM expenses WHERE expense_type = 'salary' "
                "AND (reference_no IS NULL OR TRIM(COALESCE(reference_no, '')) = '')"
            )
        ).fetchall()
        reserved = {
            (r[0] or "").strip()
            for r in conn.execute(
                text(
                    "SELECT reference_no FROM expenses "
                    "WHERE reference_no IS NOT NULL AND TRIM(reference_no) != ''"
                )
            ).fetchall()
            if r[0]
        }

        def _exists(c: str, _conn=conn, _res=reserved) -> bool:
            if c in _res:
                return True
            return (
                _conn.execute(
                    text("SELECT 1 FROM expenses WHERE reference_no = :c"), {"c": c}
                ).fetchone()
                is not None
            )

        for (eid,) in rows:
            cand = allocate_unique_salary_reference(_exists)
            conn.execute(
                text("UPDATE expenses SET reference_no = :c WHERE id = :id"),
                {"c": cand, "id": int(eid)},
            )
            reserved.add(cand)
        conn.execute(text("INSERT INTO app_migrations (name) VALUES ('salary_expense_reference_v1')"))


def _backfill_salary_expense_faculty_type(engine) -> None:
    """Copy faculty category onto salary expense rows for reliable history display."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("expenses") or not insp.has_table("faculty_salaries"):
        return
    with engine.begin() as conn:
        exp_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(expenses)")).fetchall()}
        if "faculty_type" not in exp_cols:
            return
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row_done = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "salary_expense_faculty_type_v1"},
        ).fetchone()
        if row_done:
            return
        conn.execute(
            text(
                """
                UPDATE expenses
                SET faculty_type = (
                    SELECT fs.faculty_type
                    FROM faculty_salaries fs
                    WHERE lower(trim(fs.faculty_name)) = lower(trim(expenses.person_name))
                    LIMIT 1
                )
                WHERE expense_type = 'salary'
                  AND (faculty_type IS NULL OR trim(faculty_type) = '')
                  AND EXISTS (
                    SELECT 1 FROM faculty_salaries fs
                    WHERE lower(trim(fs.faculty_name)) = lower(trim(expenses.person_name))
                  )
                """
            )
        )
        conn.execute(text("INSERT INTO app_migrations (name) VALUES ('salary_expense_faculty_type_v1')"))


def _dedupe_salary_expenses_per_faculty_month(engine) -> None:
    """Keep only the latest salary payout per faculty name and month (permanent delete older rows)."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    if not insp.has_table("expenses"):
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "salary_expense_dedupe_faculty_month_v1"},
        ).fetchone()
        if row:
            return
        conn.execute(
            text(
                """
                DELETE FROM expenses
                WHERE expense_type = 'salary'
                  AND id NOT IN (
                    SELECT MAX(id)
                    FROM expenses
                    WHERE expense_type = 'salary'
                      AND TRIM(COALESCE(month_label, '')) != ''
                    GROUP BY lower(trim(person_name)), trim(month_label)
                  )
                """
            )
        )
        conn.execute(
            text("INSERT INTO app_migrations (name) VALUES ('salary_expense_dedupe_faculty_month_v1')")
        )


def _migrate_misc_expenses_remove_categories(engine) -> None:
    """Replace category-linked misc expenses with head + date expenses."""
    from sqlalchemy import inspect

    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("misc_expenses"):
        return
    exp_cols = {c["name"] for c in insp.get_columns("misc_expenses")}
    if "category_id" not in exp_cols:
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "misc_expenses_remove_categories_v1"},
        ).fetchone()
        if row:
            return
        conn.execute(
            text(
                """
                CREATE TABLE misc_expenses_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    head VARCHAR(80) NOT NULL,
                    expense_date DATE NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at DATETIME
                )
                """
            )
        )
        if insp.has_table("misc_expense_categories"):
            conn.execute(
                text(
                    """
                    INSERT INTO misc_expenses_new (id, head, expense_date, notes, created_at)
                    SELECT
                        e.id,
                        trim(
                            c.name ||
                            CASE
                                WHEN trim(COALESCE(e.title, '')) != '' THEN ' - ' || trim(e.title)
                                ELSE ''
                            END
                        ),
                        e.expense_date,
                        COALESCE(e.notes, ''),
                        e.created_at
                    FROM misc_expenses e
                    JOIN misc_expense_categories c ON c.id = e.category_id
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO misc_expenses_new (id, head, expense_date, notes, created_at)
                    SELECT
                        id,
                        trim(COALESCE(title, 'Miscellaneous')),
                        expense_date,
                        COALESCE(notes, ''),
                        created_at
                    FROM misc_expenses
                    """
                )
            )
        conn.execute(text("DROP TABLE misc_expenses"))
        conn.execute(text("ALTER TABLE misc_expenses_new RENAME TO misc_expenses"))
        if insp.has_table("misc_expense_categories"):
            conn.execute(text("DROP TABLE misc_expense_categories"))
        conn.execute(
            text("INSERT INTO app_migrations (name) VALUES ('misc_expenses_remove_categories_v1')")
        )


def _dedupe_misc_expenses_same_identity(engine) -> None:
    """Merge duplicate misc expenses that share head, date, and particulars."""
    from sqlalchemy import inspect

    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("misc_expenses") or not insp.has_table("misc_expense_entries"):
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "misc_expenses_dedupe_identity_v1"},
        ).fetchone()
        if row:
            return
        groups = conn.execute(
            text(
                """
                SELECT
                    lower(trim(head)) AS head_key,
                    expense_date,
                    lower(trim(COALESCE(notes, ''))) AS notes_key,
                    MIN(id) AS keep_id
                FROM misc_expenses
                GROUP BY head_key, expense_date, notes_key
                HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        for group in groups:
            keep_id = int(group[3])
            dupes = conn.execute(
                text(
                    """
                    SELECT id FROM misc_expenses
                    WHERE lower(trim(head)) = :head_key
                      AND expense_date = :expense_date
                      AND lower(trim(COALESCE(notes, ''))) = :notes_key
                      AND id != :keep_id
                    """
                ),
                {
                    "head_key": group[0],
                    "expense_date": group[1],
                    "notes_key": group[2],
                    "keep_id": keep_id,
                },
            ).fetchall()
            for (dupe_id,) in dupes:
                conn.execute(
                    text(
                        "UPDATE misc_expense_entries SET expense_id = :keep_id WHERE expense_id = :dupe_id"
                    ),
                    {"keep_id": keep_id, "dupe_id": int(dupe_id)},
                )
                conn.execute(text("DELETE FROM misc_expenses WHERE id = :id"), {"id": int(dupe_id)})
        conn.execute(
            text("INSERT INTO app_migrations (name) VALUES ('misc_expenses_dedupe_identity_v1')")
        )


def _dedupe_misc_expenses_by_head(engine) -> None:
    """Keep one misc expense per head name and merge duplicate rows."""
    from sqlalchemy import inspect

    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("misc_expenses") or not insp.has_table("misc_expense_entries"):
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        row = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "misc_expenses_dedupe_head_v1"},
        ).fetchone()
        if row:
            return
        groups = conn.execute(
            text(
                """
                SELECT lower(trim(head)) AS head_key, MIN(id) AS keep_id
                FROM misc_expenses
                GROUP BY head_key
                HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        for group in groups:
            keep_id = int(group[1])
            dupes = conn.execute(
                text(
                    """
                    SELECT id FROM misc_expenses
                    WHERE lower(trim(head)) = :head_key
                      AND id != :keep_id
                    """
                ),
                {"head_key": group[0], "keep_id": keep_id},
            ).fetchall()
            for (dupe_id,) in dupes:
                conn.execute(
                    text(
                        "UPDATE misc_expense_entries SET expense_id = :keep_id WHERE expense_id = :dupe_id"
                    ),
                    {"keep_id": keep_id, "dupe_id": int(dupe_id)},
                )
                conn.execute(text("DELETE FROM misc_expenses WHERE id = :id"), {"id": int(dupe_id)})
        conn.execute(
            text("INSERT INTO app_migrations (name) VALUES ('misc_expenses_dedupe_head_v1')")
        )


def _backfill_misc_expense_entry_dates(engine) -> None:
    from sqlalchemy import inspect

    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("misc_expense_entries") or not insp.has_table("misc_expenses"):
        return
    entry_cols = {c["name"] for c in insp.get_columns("misc_expense_entries")}
    if "entry_date" in entry_cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE misc_expense_entries ADD COLUMN entry_date DATE"))
        conn.execute(
            text(
                """
                UPDATE misc_expense_entries
                SET entry_date = (
                    SELECT expense_date FROM misc_expenses
                    WHERE misc_expenses.id = misc_expense_entries.expense_id
                )
                WHERE entry_date IS NULL
                """
            )
        )


def _migrate_misc_expense_entry_revert_columns(engine) -> None:
    from sqlalchemy import inspect

    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("misc_expense_entries"):
        return
    entry_cols = {c["name"] for c in insp.get_columns("misc_expense_entries")}
    with engine.begin() as conn:
        if "is_reverted" not in entry_cols:
            conn.execute(
                text(
                    "ALTER TABLE misc_expense_entries ADD COLUMN is_reverted BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        if "reverted_at" not in entry_cols:
            conn.execute(text("ALTER TABLE misc_expense_entries ADD COLUMN reverted_at DATETIME"))


def _backfill_payment_split_amounts(engine) -> None:
    """Populate school_amount/van_amount on payments saved before split columns existed."""
    from sqlalchemy import inspect

    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("payments"):
        return
    pay_cols = {c["name"] for c in insp.get_columns("payments")}
    if "school_amount" not in pay_cols or "van_amount" not in pay_cols:
        return

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY)"))
        if conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :n"),
            {"n": "backfill_payment_split_amounts_v1"},
        ).fetchone():
            return

    from backend.core.database import SessionLocal
    from backend.repositories.payment_repository import PaymentRepository

    session = SessionLocal()
    try:
        PaymentRepository(session).backfill_legacy_payment_splits()
    finally:
        session.close()

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app_migrations (name) VALUES ('backfill_payment_split_amounts_v1')")
        )
