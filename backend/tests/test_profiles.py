import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from routes.profiles import router
from services import profile_svc

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestProfileQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_create_and_get_profile(self):
        pid = queries.create_profile(self.conn, "Alice", None)
        row = queries.get_profile(self.conn, pid)
        assert row is not None
        self.assertEqual(row["name"], "Alice")
        self.assertIsNone(row["password_hash"])

    def test_get_profile_nonexistent(self):
        self.assertIsNone(queries.get_profile(self.conn, 999))

    def test_get_profile_by_name(self):
        queries.create_profile(self.conn, "Bob", None)
        self.assertIsNotNone(queries.get_profile_by_name(self.conn, "Bob"))
        self.assertIsNone(queries.get_profile_by_name(self.conn, "Nope"))

    def test_get_all_profiles(self):
        queries.create_profile(self.conn, "A", None)
        queries.create_profile(self.conn, "B", "somehash")
        rows = queries.get_all_profiles(self.conn)
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["name"] for r in rows}, {"A", "B"})

    def test_rename_profile(self):
        pid = queries.create_profile(self.conn, "Old", None)
        self.assertTrue(queries.rename_profile(self.conn, pid, "New"))
        row = queries.get_profile(self.conn, pid)
        assert row is not None
        self.assertEqual(row["name"], "New")

    def test_delete_profile(self):
        pid = queries.create_profile(self.conn, "Gone", None)
        self.assertTrue(queries.delete_profile(self.conn, pid))
        self.assertIsNone(queries.get_profile(self.conn, pid))

    def test_count_profiles(self):
        self.assertEqual(queries.count_profiles(self.conn), 0)
        queries.create_profile(self.conn, "A", None)
        queries.create_profile(self.conn, "B", None)
        self.assertEqual(queries.count_profiles(self.conn), 2)


# ---------------------------------------------------------------------------
# Hashing tests
# ---------------------------------------------------------------------------


class TestProfileHashing(unittest.TestCase):
    def test_hash_format(self):
        h = profile_svc._hash_password("secret")
        parts = h.split("$")
        self.assertEqual(parts[0], "pbkdf2_sha256")
        self.assertEqual(int(parts[1]), profile_svc.PBKDF2_ITERATIONS)
        self.assertEqual(len(parts), 4)
        self.assertNotIn("secret", h)

    def test_verify_correct_and_wrong(self):
        h = profile_svc._hash_password("secret")
        self.assertTrue(profile_svc._verify_password("secret", h))
        self.assertFalse(profile_svc._verify_password("wrong", h))

    def test_salt_unique(self):
        self.assertNotEqual(
            profile_svc._hash_password("same"),
            profile_svc._hash_password("same"),
        )

    def test_verify_malformed(self):
        self.assertFalse(profile_svc._verify_password("x", None))
        self.assertFalse(profile_svc._verify_password("x", ""))
        self.assertFalse(profile_svc._verify_password("x", "garbage"))
        self.assertFalse(profile_svc._verify_password("x", "pbkdf2_sha256$abc$def$ghi"))
        self.assertFalse(profile_svc._verify_password("x", "other$1$YQ==$YQ=="))


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


class TestProfileService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.profile_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_create_passwordless(self):
        p = profile_svc.create(profile_svc.ProfileCreate(name=" Alice ", password=None))
        self.assertEqual(p.name, "Alice")
        self.assertFalse(p.has_password)
        self.assertGreater(p.id, 0)

    def test_create_with_password(self):
        p = profile_svc.create(profile_svc.ProfileCreate(name="Sec", password="hunter2"))
        self.assertTrue(p.has_password)

    def test_create_duplicate(self):
        profile_svc.create(profile_svc.ProfileCreate(name="Alice"))
        with self.assertRaises(profile_svc.ProfileNameTaken):
            profile_svc.create(profile_svc.ProfileCreate(name="Alice"))

    def test_create_empty_name(self):
        with self.assertRaises(profile_svc.InvalidProfileName):
            profile_svc.create(profile_svc.ProfileCreate(name="   "))

    def test_list_profiles_never_exposes_hash(self):
        profile_svc.create(profile_svc.ProfileCreate(name="A", password="pw"))
        profile_svc.create(profile_svc.ProfileCreate(name="B"))
        profiles = profile_svc.list_profiles()
        self.assertEqual(len(profiles), 2)
        for p in profiles:
            self.assertFalse(hasattr(p, "password_hash"))

    def test_get_not_found(self):
        with self.assertRaises(profile_svc.ProfileNotFound):
            profile_svc.get(999)

    def test_rename(self):
        p = profile_svc.create(profile_svc.ProfileCreate(name="Old"))
        renamed = profile_svc.rename(p.id, "New")
        self.assertEqual(renamed.name, "New")

    def test_rename_not_found(self):
        with self.assertRaises(profile_svc.ProfileNotFound):
            profile_svc.rename(999, "X")

    def test_rename_taken(self):
        a = profile_svc.create(profile_svc.ProfileCreate(name="A"))
        profile_svc.create(profile_svc.ProfileCreate(name="B"))
        with self.assertRaises(profile_svc.ProfileNameTaken):
            profile_svc.rename(a.id, "B")

    def test_rename_same_name_ok(self):
        a = profile_svc.create(profile_svc.ProfileCreate(name="A"))
        renamed = profile_svc.rename(a.id, "A")
        self.assertEqual(renamed.name, "A")

    def test_unlock_passwordless_accepts_any(self):
        p = profile_svc.create(profile_svc.ProfileCreate(name="Open"))
        self.assertEqual(profile_svc.unlock(p.id, None).id, p.id)
        self.assertEqual(profile_svc.unlock(p.id, "anything").id, p.id)

    def test_unlock_correct_password(self):
        p = profile_svc.create(profile_svc.ProfileCreate(name="Sec", password="secret"))
        self.assertEqual(profile_svc.unlock(p.id, "secret").id, p.id)

    def test_unlock_wrong_password(self):
        p = profile_svc.create(profile_svc.ProfileCreate(name="Sec", password="secret"))
        with self.assertRaises(profile_svc.InvalidPassword):
            profile_svc.unlock(p.id, "nope")

    def test_unlock_not_found(self):
        with self.assertRaises(profile_svc.ProfileNotFound):
            profile_svc.unlock(999, "x")

    def _seed_profile_rows(self, pid: int, name: str) -> None:
        eid = self.conn.execute(
            "INSERT INTO entities (name, entity_type, profile_id) VALUES (?, 'BROKER', ?)",
            (name, pid),
        ).lastrowid
        txid = self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, profile_id) "
            "VALUES ('2024-01-01T00:00:00', 'MONEY_IN', ?, 'USD', ?)",
            (eid, pid),
        ).lastrowid
        self.conn.execute(
            "INSERT INTO transaction_fees (transaction_id, fee_type, nature, currency, profile_id) "
            "VALUES (?, 'BROKER', 'FIXED', 'USD', ?)",
            (txid, pid),
        )
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_type, currency, profile_id) "
            "VALUES (?, 'WITHHOLDING', 'USD', ?)",
            (txid, pid),
        )
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp, profile_id) "
            "VALUES (?, 'USD', 100, '2024-01-01T00:00:00', ?)",
            (eid, pid),
        )
        self.conn.execute(
            "INSERT INTO schedules (description, start_date, periodicity_type, profile_id) "
            "VALUES ('Sch', '2024-01-01', 'ONE_OFF', ?)",
            (pid,),
        )
        self.conn.execute(
            "INSERT INTO manual_values (portfolio_asset_id, value, effective_date, profile_id) "
            "VALUES (?, 100, '2024-01-01', ?)",
            (pid, pid),
        )

    def test_delete_cascades_only_own_profile(self):
        a = profile_svc.create(profile_svc.ProfileCreate(name="Alice"))
        b = profile_svc.create(profile_svc.ProfileCreate(name="Bob"))
        self._seed_profile_rows(a.id, "Alice")
        self._seed_profile_rows(b.id, "Bob")
        self.conn.commit()

        profile_svc.delete(a.id)

        for table in [
            "entities",
            "transactions",
            "transaction_fees",
            "transaction_taxes",
            "balance_snapshots",
            "schedules",
            "manual_values",
        ]:
            a_count = self.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE profile_id = ?", (a.id,)).fetchone()[0]
            b_count = self.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE profile_id = ?", (b.id,)).fetchone()[0]
            self.assertEqual(a_count, 0, f"{table}: Alice rows not removed")
            self.assertEqual(b_count, 1, f"{table}: Bob rows lost")

        self.assertIsNone(queries.get_profile(self.conn, a.id))
        self.assertIsNotNone(queries.get_profile(self.conn, b.id))

    def test_delete_keeps_shared_data(self):
        a = profile_svc.create(profile_svc.ProfileCreate(name="Alice"))
        profile_svc.create(profile_svc.ProfileCreate(name="Bob"))
        self.conn.execute("INSERT INTO market_assets (market_code, asset_type) VALUES ('AAPL', 'STOCK')")
        self.conn.commit()

        profile_svc.delete(a.id)

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM market_assets").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0], 1)

    def test_delete_not_found(self):
        with self.assertRaises(profile_svc.ProfileNotFound):
            profile_svc.delete(999)

    def test_delete_last_profile_rejected(self):
        profile_svc.create(profile_svc.ProfileCreate(name="Only"))
        with self.assertRaises(profile_svc.LastProfileError):
            profile_svc.delete(1)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------


class TestProfileRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.profile_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/profiles")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post("/api/v1/profiles", json={"name": "Alice"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["name"], "Alice")
        self.assertFalse(data["has_password"])
        self.assertNotIn("password_hash", data)
        self.assertIn("created_at", data)

    def test_create_duplicate_409(self):
        client.post("/api/v1/profiles", json={"name": "Alice"})
        resp = client.post("/api/v1/profiles", json={"name": "Alice"})
        self.assertEqual(resp.status_code, 409)

    def test_get(self):
        pid = client.post("/api/v1/profiles", json={"name": "Alice"}).json()["id"]
        resp = client.get(f"/api/v1/profiles/{pid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Alice")

    def test_get_404(self):
        resp = client.get("/api/v1/profiles/999")
        self.assertEqual(resp.status_code, 404)

    def test_patch_rename(self):
        pid = client.post("/api/v1/profiles", json={"name": "Alice"}).json()["id"]
        resp = client.patch(f"/api/v1/profiles/{pid}", json={"name": "Alicia"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Alicia")

    def test_patch_404(self):
        resp = client.patch("/api/v1/profiles/999", json={"name": "X"})
        self.assertEqual(resp.status_code, 404)

    def test_patch_409(self):
        client.post("/api/v1/profiles", json={"name": "A"})
        pid = client.post("/api/v1/profiles", json={"name": "B"}).json()["id"]
        resp = client.patch(f"/api/v1/profiles/{pid}", json={"name": "A"})
        self.assertEqual(resp.status_code, 409)

    def test_unlock_passwordless_ok(self):
        pid = client.post("/api/v1/profiles", json={"name": "Open"}).json()["id"]
        resp = client.post(f"/api/v1/profiles/{pid}/unlock", json={})
        self.assertEqual(resp.status_code, 200)

    def test_unlock_wrong_password_401(self):
        pid = client.post("/api/v1/profiles", json={"name": "Sec", "password": "pw"}).json()["id"]
        resp = client.post(f"/api/v1/profiles/{pid}/unlock", json={"password": "bad"})
        self.assertEqual(resp.status_code, 401)

    def test_unlock_correct_password(self):
        pid = client.post("/api/v1/profiles", json={"name": "Sec", "password": "pw"}).json()["id"]
        resp = client.post(f"/api/v1/profiles/{pid}/unlock", json={"password": "pw"})
        self.assertEqual(resp.status_code, 200)

    def test_unlock_404(self):
        resp = client.post("/api/v1/profiles/999/unlock", json={})
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        client.post("/api/v1/profiles", json={"name": "A"})
        client.post("/api/v1/profiles", json={"name": "B"})
        resp = client.delete("/api/v1/profiles/1")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(len(client.get("/api/v1/profiles").json()), 1)

    def test_delete_last_409(self):
        client.post("/api/v1/profiles", json={"name": "Only"})
        resp = client.delete("/api/v1/profiles/1")
        self.assertEqual(resp.status_code, 409)

    def test_delete_404(self):
        resp = client.delete("/api/v1/profiles/999")
        self.assertEqual(resp.status_code, 404)
