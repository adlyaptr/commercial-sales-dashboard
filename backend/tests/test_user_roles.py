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
        self.session = {
            "username": username if username is not None else main.APP_USERNAME,
            "role": role,
        }

    async def json(self):
        return self.payload


class MemoryUsers:
    def __init__(self):
        self.users = {
            main.APP_USERNAME: {
                "username": main.APP_USERNAME,
                "password_hash": main.hashlib.sha256(main.APP_PASSWORD.encode("utf-8")).hexdigest(),
                "role": "admin",
                "sph_role": None,
            }
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        parameters = parameters or ()
        if statement.startswith("SELECT password_hash,role,sph_role FROM app_users"):
            user = self.users.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: user)
        if statement.startswith("SELECT role,sph_role FROM app_users"):
            user = self.users.get(parameters[0])
            return SimpleNamespace(
                fetchone=lambda: {
                    "role": user["role"],
                    "sph_role": user.get("sph_role"),
                } if user else None
            )
        if statement.startswith("SELECT role FROM app_users"):
            user = self.users.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: {"role": user["role"]} if user else None)
        if statement.startswith("SELECT username FROM app_users"):
            user = self.users.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: {"username": user["username"]} if user else None)
        if statement.startswith("SELECT username,role,sph_role FROM app_users"):
            return SimpleNamespace(
                fetchall=lambda: [
                    {
                        "username": item["username"],
                        "role": item["role"],
                        "sph_role": item.get("sph_role"),
                    }
                    for item in self.users.values()
                ]
            )
        if statement.startswith("UPDATE app_users SET sph_role"):
            sph_role, username = parameters
            self.users[username]["sph_role"] = sph_role
            return SimpleNamespace(rowcount=1)
        if statement.startswith("INSERT INTO app_users"):
            username, password_hash, role, sph_role = parameters
            self.users[username] = {
                "username": username,
                "password_hash": password_hash,
                "role": role,
                "sph_role": sph_role,
            }
            return SimpleNamespace(rowcount=1)
        if statement.startswith("UPDATE app_users SET sph_role"):
            sph_role, username = parameters
            self.users[username]["sph_role"] = sph_role
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

    def test_admin_can_create_list_reset_and_delete_user_accounts(self):
        created = asyncio.run(main.create_user(FakeRequest({
            "username": "sales.team",
            "password": "division-password",
        })))
        self.assertEqual(created, {"username": "sales.team", "role": "user", "sphRole": None})
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
                {"username": main.APP_USERNAME, "role": "admin", "sph_role": None},
                {"username": "sales.team", "role": "user", "sph_role": None},
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

    def test_admin_cannot_create_division_login_accounts(self):
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.create_user(FakeRequest({
                "username": "division.team",
                "password": "division-password",
                "role": "division",
            })))
        self.assertEqual(error.exception.status_code, 400)
        self.assertNotIn("division.team", self.database.users)

    def test_user_passwords_may_be_short_but_not_empty_or_over_256_characters(self):
        created = asyncio.run(main.create_user(FakeRequest({
            "username": "short.pass",
            "password": "a",
            "role": "user",
        })))
        self.assertEqual(created, {
            "username": "short.pass",
            "role": "user",
            "sphRole": None,
        })
        self.assertTrue(main.verify_user_password(
            "a", self.database.users["short.pass"]["password_hash"]
        ))

        asyncio.run(main.update_user_password(
            "short.pass",
            FakeRequest({"password": "xy"}),
        ))
        self.assertTrue(main.verify_user_password(
            "xy", self.database.users["short.pass"]["password_hash"]
        ))

        for password in ("", "x" * 257):
            with self.subTest(password_length=len(password)):
                with self.assertRaises(main.HTTPException) as error:
                    asyncio.run(main.update_user_password(
                        "short.pass",
                        FakeRequest({"password": password}),
                    ))
                self.assertEqual(error.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.create_user(FakeRequest({
                "username": "empty.pass",
                "password": "",
                "role": "user",
            })))
        self.assertEqual(error.exception.status_code, 400)

    def test_admin_can_create_user_role_and_manage_user_accounts(self):
        created = asyncio.run(main.create_user(FakeRequest({
            "username": "report.reader",
            "password": "reader-password",
            "role": "user",
        })))
        self.assertEqual(created, {
            "username": "report.reader",
            "role": "user",
            "sphRole": None,
        })
        self.assertEqual(self.database.users["report.reader"]["role"], "user")

        asyncio.run(main.update_user_password(
            "report.reader",
            FakeRequest({"password": "new-reader-password"}),
        ))
        self.assertTrue(main.verify_user_password(
            "new-reader-password",
            self.database.users["report.reader"]["password_hash"],
        ))
        self.assertEqual(
            main.delete_user("report.reader", FakeRequest()),
            {"ok": True},
        )

    def test_legacy_division_account_cannot_login_or_use_authenticated_features(self):
        self.database.users["division"] = {
            "username": "division",
            "password_hash": "unused",
            "role": "division",
        }
        request = FakeRequest(username="division", role="division")
        with self.assertRaises(main.HTTPException) as error:
            main.require_login(request)
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(request.session, {})

        with self.assertRaises(main.HTTPException) as error:
            main.list_users(FakeRequest(username="division", role="division"))
        self.assertEqual(error.exception.status_code, 401)

    def test_user_role_can_read_features_but_cannot_write_or_manage_users(self):
        self.database.users["reader"] = {
            "username": "reader",
            "password_hash": "unused",
            "role": "user",
        }
        request = FakeRequest(username="reader", role="user")
        self.assertIsNone(main.require_login(request))
        with self.assertRaises(main.HTTPException) as error:
            main.require_admin(request)
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(main.HTTPException) as error:
            main.list_users(request)
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.create_user(request))
        self.assertEqual(error.exception.status_code, 403)

    def test_removed_user_session_is_invalidated(self):
        request = FakeRequest(username="deleted-reader", role="user")
        with self.assertRaises(main.HTTPException) as error:
            main.require_login(request)
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(request.session, {})

    def test_legacy_division_session_is_cleared_and_public_home_remains_available(self):
        request = FakeRequest(username="division", role="division")
        self.assertIsNone(main.require_home_access(request))
        self.assertEqual(request.session, {})

    def test_home_access_checks_active_user_account(self):
        self.database.users["reader"] = {
            "username": "reader",
            "password_hash": "unused",
            "role": "user",
        }
        request = FakeRequest(username="reader", role="user")
        main.require_home_access(request)
        self.assertEqual(request.session["role"], "user")
        del self.database.users["reader"]
        with self.assertRaises(main.HTTPException) as error:
            main.require_home_access(request)
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(request.session, {})

    def test_home_access_is_public_without_a_session(self):
        self.assertIsNone(main.require_home_access(SimpleNamespace(session={})))

    def test_user_can_read_average_price_apis(self):
        self.database.users["reader"] = {
            "username": "reader",
            "password_hash": "unused",
            "role": "user",
        }
        request = FakeRequest(username="reader", role="user")
        main.require_login(request)
        self.assertEqual(request.session["role"], "user")

    def test_login_accepts_admin_and_user_but_rejects_division(self):
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
        response = asyncio.run(main.login(division_request))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(division_request.session, {"username": "", "role": ""})

        with self.assertRaises(main.HTTPException) as error:
            main.me(FakeRequest(username="division", role="division"))
        self.assertEqual(error.exception.status_code, 401)

        self.database.users["reader"] = {
            "username": "reader",
            "password_hash": main.hash_user_password("reader-password"),
            "role": "user",
        }
        user_request = FakeRequest(
            {"username": "reader", "password": "reader-password"},
            username="",
            role="",
        )
        asyncio.run(main.login(user_request))
        self.assertEqual(user_request.session["role"], "user")

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

    def test_sph_role_assignment_endpoint_is_available_to_admin(self):
        routes = {route.path for route in main.app.routes}
        self.assertIn("/api/users/{username}/sph-role", routes)

    def test_admin_can_assign_and_revoke_commercial_head_access(self):
        asyncio.run(main.create_user(FakeRequest({
            "username": "contract.head",
            "password": "head-password",
        })))

        updated = asyncio.run(main.update_user_sph_role(
            "contract.head",
            FakeRequest({"sphRole": "commercial_head"}),
        ))
        self.assertEqual(updated["sphRole"], "commercial_head")
        self.assertEqual(self.database.users["contract.head"]["sph_role"], "commercial_head")

        revoked = asyncio.run(main.update_user_sph_role(
            "contract.head",
            FakeRequest({"sphRole": None}),
        ))
        self.assertIsNone(revoked["sphRole"])
        self.assertIsNone(self.database.users["contract.head"]["sph_role"])

    def test_commercial_head_login_is_limited_to_sph_approval_app(self):
        self.database.users["contract.head"] = {
            "username": "contract.head",
            "password_hash": main.hash_user_password("head-password"),
            "role": "user",
            "sph_role": "commercial_head",
        }
        sph_request = FakeRequest(
            {
                "username": "contract.head",
                "password": "head-password",
                "application": "sph",
            },
            username="",
            role="",
        )

        asyncio.run(main.login(sph_request))
        profile = main.me(sph_request)

        self.assertEqual(profile["role"], "user")
        self.assertEqual(profile["sphRole"], "commercial_head")
        self.assertEqual(profile["application"], "sph")

        commercial_request = FakeRequest(
            {
                "username": "contract.head",
                "password": "head-password",
                "application": "commercial",
            },
            username="",
            role="",
        )
        response = asyncio.run(main.login(commercial_request))
        self.assertEqual(response.status_code, 403)

    def test_legacy_sph_assignment_does_not_grant_user_access(self):
        self.database.users["reader"] = {
            "username": "reader",
            "password_hash": main.hash_user_password("reader-password"),
            "role": "user",
            "sph_role": "sales",
        }
        request = FakeRequest(
            {
                "username": "reader",
                "password": "reader-password",
                "application": "sph",
            },
            username="",
            role="",
        )
        response = asyncio.run(main.login(request))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(request.session, {"username": "", "role": ""})

        request = FakeRequest(username="reader", role="user")
        request.session["application"] = "sph"
        with self.assertRaises(main.HTTPException) as error:
            main.me(request)
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(request.session, {})

    def test_login_application_selection_requires_admin_for_sph(self):
        self.database.users["reader"] = {
            "username": "reader",
            "password_hash": main.hash_user_password("reader-password"),
            "role": "user",
            "sph_role": None,
        }
        request = FakeRequest(
            {
                "username": "reader",
                "password": "reader-password",
                "application": "sph",
            },
            username="",
            role="",
        )
        response = asyncio.run(main.login(request))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(request.session, {"username": "", "role": ""})


if __name__ == "__main__":
    unittest.main()
