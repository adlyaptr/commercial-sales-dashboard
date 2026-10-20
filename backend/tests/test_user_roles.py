import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeRequest:
    def __init__(self, payload=None, username=None, role="admin"):
        self.payload = payload or {}
        self.session = {"username": username or main.APP_USERNAME, "role": role}

    async def json(self):
        return self.payload


class MemoryUsers:
    def __init__(self):
        self.users = {
            main.APP_USERNAME: {
                "username": main.APP_USERNAME,
                "password_hash": main.hashlib.sha256(main.APP_PASSWORD.encode("utf-8")).hexdigest(),
                "role": "admin",
            }
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        parameters = parameters or ()
        if statement.startswith("SELECT password_hash,role FROM app_users"):
            user = self.users.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: user)
        if statement.startswith("SELECT role FROM app_users"):
            user = self.users.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: {"role": user["role"]} if user else None)
        if statement.startswith("SELECT username FROM app_users"):
            user = self.users.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: {"username": user["username"]} if user else None)
        if statement.startswith("SELECT username,role FROM app_users"):
            return SimpleNamespace(
                fetchall=lambda: [
                    {"username": item["username"], "role": item["role"]}
                    for item in self.users.values()
                ]
            )
        if statement.startswith("INSERT INTO app_users"):
            username, password_hash = parameters
            self.users[username] = {
                "username": username,
                "password_hash": password_hash,
                "role": "division",
            }
            return SimpleNamespace(rowcount=1)
        if statement.startswith("UPDATE app_users SET password_hash"):
            password_hash, username = parameters
            self.users[username]["password_hash"] = password_hash
            return SimpleNamespace(rowcount=1)
        if statement.startswith("DELETE FROM app_users"):
            del self.users[parameters[0]]
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"Unexpected SQL in test: {statement}")


class UserRoleTests(unittest.TestCase):
    def setUp(self):
        self.database = MemoryUsers()
        self.db_patch = patch.object(main, "db", return_value=self.database)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_admin_can_create_list_reset_and_delete_division_users(self):
        created = asyncio.run(main.create_user(FakeRequest({
            "username": "sales.team",
            "password": "division-password",
        })))
        self.assertEqual(created, {"username": "sales.team", "role": "division"})
        self.assertTrue(
            self.database.users["sales.team"]["password_hash"].startswith("pbkdf2_sha256$")
        )
        self.assertTrue(
            main.verify_user_password(
                "division-password", self.database.users["sales.team"]["password_hash"]
            )
        )
        self.assertEqual(
            main.list_users(FakeRequest()),
            [
                {"username": main.APP_USERNAME, "role": "admin"},
                {"username": "sales.team", "role": "division"},
            ],
        )

        asyncio.run(main.update_user_password(
            "sales.team",
            FakeRequest({"password": "new-division-password"}),
        ))
        self.assertTrue(
            main.verify_user_password(
                "new-division-password",
                self.database.users["sales.team"]["password_hash"],
            )
        )
        self.assertEqual(
            main.delete_user("sales.team", FakeRequest()),
            {"ok": True},
        )
        self.assertNotIn("sales.team", self.database.users)

    def test_division_role_cannot_use_admin_permissions(self):
        self.database.users["division"] = {
            "username": "division",
            "password_hash": "unused",
            "role": "division",
        }
        request = FakeRequest(username="division", role="division")
        with self.assertRaises(main.HTTPException) as error:
            main.require_login(request)
        self.assertEqual(error.exception.status_code, 403)

        with self.assertRaises(main.HTTPException) as error:
            main.list_users(request)
        self.assertEqual(error.exception.status_code, 403)

    def test_home_access_checks_active_division_account(self):
        self.database.users["division"] = {
            "username": "division",
            "password_hash": "unused",
            "role": "division",
        }
        main.require_home_access(FakeRequest(username="division", role="division"))
        del self.database.users["division"]
        request = FakeRequest(username="division", role="division")
        with self.assertRaises(main.HTTPException) as error:
            main.require_home_access(request)
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(request.session, {})

    def test_login_accepts_admin_legacy_and_division_password_hashes(self):
        admin_request = FakeRequest({
            "username": main.APP_USERNAME,
            "password": main.APP_PASSWORD,
        })
        asyncio.run(main.login(admin_request))
        self.assertEqual(admin_request.session["role"], "admin")

        self.database.users["division"] = {
            "username": "division",
            "password_hash": main.hash_user_password("division-password"),
            "role": "division",
        }
        division_request = FakeRequest(
            {"username": "division", "password": "division-password"},
            username="",
            role="",
        )
        asyncio.run(main.login(division_request))
        self.assertEqual(division_request.session["role"], "division")

    def test_admin_account_cannot_be_deleted_or_modified_as_division(self):
        with self.assertRaises(main.HTTPException) as error:
            main.delete_user(main.APP_USERNAME, FakeRequest())
        self.assertEqual(error.exception.status_code, 400)
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.update_user_password(
                main.APP_USERNAME,
                FakeRequest({"password": "new-admin-password"}),
            ))
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
