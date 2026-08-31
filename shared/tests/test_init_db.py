import os
import sqlite3
import importlib.util
import pytest
from werkzeug.security import check_password_hash

TEST_DB_DIR = os.path.join(os.path.dirname(__file__), ".test_data")
TEST_DB_PATH = os.path.join(TEST_DB_DIR, "shared.db")


@pytest.fixture
def init_db_module():
    os.environ["DB_DATA_DIR"] = TEST_DB_DIR
    spec = importlib.util.spec_from_file_location(
        "shared_init_db",
        os.path.join(os.path.dirname(__file__), "..", "database", "init_db.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fresh_db(init_db_module):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_db_module.init_db()
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class TestDatabaseCreation:
    def test_database_file_is_created(self, fresh_db):
        assert os.path.exists(fresh_db)

    def test_patients_table_exists(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='patients'"
        )
        assert cursor.fetchone() is not None
        conn.close()


class TestSchema:
    def test_patients_table_has_expected_columns(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute("PRAGMA table_info(patients)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "patient_id",
            "first_name",
            "last_name",
            "address",
            "email_address",
            "password",
            "phone_number",
            "emergency_contact_number",
        }
        assert expected.issubset(columns)
        conn.close()

    def test_patient_id_is_primary_key(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute("PRAGMA table_info(patients)")
        pk_columns = [row["name"] for row in cursor.fetchall() if row["pk"] == 1]
        assert pk_columns == ["patient_id"]
        conn.close()

    def test_email_address_has_unique_constraint(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute("SELECT email_address FROM patients LIMIT 1")
        existing_email = cursor.fetchone()["email_address"]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO patients
                (first_name, last_name, address, email_address, password,
                 phone_number, emergency_contact_number)
                VALUES ('Test', 'User', '1 Test St', ?, 'hashed', '0000000000', '0000000000')
                """,
                (existing_email,),
            )
            conn.commit()
        conn.close()

    def test_required_fields_reject_null(self, fresh_db):
        conn = get_connection(fresh_db)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO patients
                (first_name, last_name, address, email_address, password,
                 phone_number, emergency_contact_number)
                VALUES (NULL, 'User', '1 Test St', 'unique@test.com', 'hashed', '0000000000', '0000000000')
                """
            )
            conn.commit()
        conn.close()


class TestSeedData:
    def test_at_least_ten_patients_seeded(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute("SELECT COUNT(*) as count FROM patients")
        assert cursor.fetchone()["count"] >= 10
        conn.close()

    def test_all_seeded_emails_are_unique(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute("SELECT email_address FROM patients")
        emails = [row["email_address"] for row in cursor.fetchall()]
        assert len(emails) == len(set(emails))
        conn.close()

    def test_at_least_one_admin_email_seeded(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM patients WHERE email_address LIKE '%@admin.com'"
        )
        assert cursor.fetchone()["count"] >= 1
        conn.close()

    def test_at_least_one_non_admin_email_seeded(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM patients WHERE email_address NOT LIKE '%@admin.com'"
        )
        assert cursor.fetchone()["count"] >= 1
        conn.close()

    def test_seeded_passwords_are_hashed_not_plaintext(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute("SELECT password FROM patients")
        for row in cursor.fetchall():
            stored = row["password"]
            assert stored != "password123"
            assert stored.startswith("scrypt:") or stored.startswith("pbkdf2:")
        conn.close()

    def test_seeded_password_hash_validates_correctly(self, fresh_db, init_db_module):
        conn = get_connection(fresh_db)
        cursor = conn.execute(
            "SELECT password FROM patients WHERE email_address = ?",
            (init_db_module.SEED_PATIENTS[0]["email_address"],),
        )
        stored_hash = cursor.fetchone()["password"]
        plain_password = init_db_module.SEED_PATIENTS[0]["password"]
        assert check_password_hash(stored_hash, plain_password)
        conn.close()

    def test_all_required_fields_populated_in_seed_data(self, fresh_db):
        conn = get_connection(fresh_db)
        cursor = conn.execute(
            """
            SELECT * FROM patients WHERE
            first_name IS NULL OR first_name = '' OR
            last_name IS NULL OR last_name = '' OR
            address IS NULL OR address = '' OR
            email_address IS NULL OR email_address = '' OR
            password IS NULL OR password = '' OR
            phone_number IS NULL OR phone_number = '' OR
            emergency_contact_number IS NULL OR emergency_contact_number = ''
            """
        )
        assert cursor.fetchall() == []
        conn.close()


class TestIdempotency:
    def test_running_init_db_twice_does_not_duplicate_rows(self, fresh_db, init_db_module):
        conn = get_connection(fresh_db)
        before_count = conn.execute("SELECT COUNT(*) as c FROM patients").fetchone()["c"]
        conn.close()

        init_db_module.init_db()

        conn = get_connection(fresh_db)
        after_count = conn.execute("SELECT COUNT(*) as c FROM patients").fetchone()["c"]
        conn.close()

        assert before_count == after_count

    def test_running_init_db_twice_does_not_error(self, fresh_db, init_db_module):
        init_db_module.init_db()
        init_db_module.init_db()