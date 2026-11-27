import asyncio
import json
import re
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class SphRequest:
    def __init__(self, role="admin", payload=None, system_role="admin"):
        self.payload = payload or {}
        self.session = {
            "username": "admin" if system_role == "admin" else "reviewer",
            "role": system_role,
            "application": "sph",
            "sph_role": role,
        }

    async def json(self):
        return self.payload


class MemorySphDatabase:
    def __init__(self):
        self.user = {"role": "admin", "sph_role": None}
        self.row = {
            "id": 7,
            "number": "SPH-2026-11-MKT-001",
            "customer_key": "customer-a",
            "customerName": "Customer A",
            "addressLine1": "",
            "addressLine2": "",
            "templateKey": "standard",
            "proposalDate": date(2026, 11, 1),
            "volumeMin": 100.0,
            "volumeMax": 200.0,
            "priceUsd": 14.0,
            "status": "review",
            "version": 0,
            "topPercent": 90.0,
            "guarantee": "Cash Deposit",
            "dueDay": 20,
            "exchangeClause": False,
            "contractYears": 2,
            "contractDuration": 2,
            "contractDurationUnit": "year",
            "durationDetails": "",
            "attentionTo": "",
            "supplyPattern": "",
            "deliveryPoint": "",
            "startDate": None,
            "endDate": None,
            "volumeDetails": "",
            "priceDetails": "",
            "paymentTerms": "",
            "advantages": "",
            "otherTerms": "",
            "preparation": "",
            "offerDetails": "",
            "reethauObligations": "",
            "customerObligations": "",
            "approvals": "[]",
            "sentDate": None,
            "approvedAt": None,
            "actualVolume": None,
            "createdBy": "seller",
            "updatedAt": datetime(2026, 11, 1, 10, 0),
        }
        self.logs = []
        self.list_rows = []
        self.list_query = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        parameters = parameters or ()
        if statement.startswith("SELECT password_hash,role"):
            return SimpleNamespace(fetchone=lambda: {
                "password_hash": "hashed-password",
                "role": self.user["role"],
                "sph_role": self.user.get("sph_role"),
            })
        if statement.startswith("SELECT role,sph_role FROM app_users"):
            return SimpleNamespace(fetchone=lambda: self.user)
        if statement.startswith("SELECT role FROM app_users"):
            return SimpleNamespace(fetchone=lambda: {"role": self.user["role"]})
        if statement.startswith(
            "SELECT p.id,p.proposal_number AS number,c.customer_name AS customerName,"
        ):
            self.list_query = statement
            return SimpleNamespace(fetchall=lambda: list(self.list_rows))
        if statement.startswith("SELECT p.id,p.proposal_number"):
            return SimpleNamespace(fetchone=lambda: dict(self.row))
        if statement.startswith("SELECT id FROM sph_proposals WHERE proposal_number"):
            return SimpleNamespace(fetchone=lambda: None)
        if statement.startswith("SELECT actor_username AS actor"):
            return SimpleNamespace(fetchall=lambda: list(reversed(self.logs)))
        if statement.startswith("INSERT INTO sph_customers"):
            return SimpleNamespace(rowcount=1)
        if statement.startswith("INSERT INTO sph_proposals("):
            if statement.count("%s") != len(parameters):
                raise AssertionError("SPH proposal insert placeholder mismatch")
            self.row["number"] = parameters[0]
            self.row["status"] = "draft"
            self.row["offerDetails"] = parameters[-1]
            return SimpleNamespace(lastrowid=7)
        if statement.startswith("UPDATE sph_proposals SET proposal_number=%s"):
            if self.row["status"] == "active":
                return SimpleNamespace(rowcount=0)
            self.row["number"] = parameters[0]
            self.row["proposalDate"] = parameters[2]
            self.row["volumeMin"] = parameters[3]
            self.row["volumeMax"] = parameters[4]
            self.row["priceUsd"] = parameters[5]
            self.row["topPercent"] = parameters[6]
            self.row["guarantee"] = parameters[7]
            self.row["dueDay"] = parameters[8]
            self.row["exchangeClause"] = parameters[9]
            self.row["contractDuration"] = parameters[10]
            self.row["contractDurationUnit"] = parameters[11]
            self.row["durationDetails"] = parameters[12]
            self.row["attentionTo"] = parameters[13]
            self.row["supplyPattern"] = parameters[14]
            self.row["deliveryPoint"] = parameters[15]
            self.row["startDate"] = parameters[16]
            self.row["endDate"] = parameters[17]
            self.row["volumeDetails"] = parameters[18]
            self.row["priceDetails"] = parameters[19]
            self.row["paymentTerms"] = parameters[20]
            self.row["advantages"] = parameters[21]
            self.row["otherTerms"] = parameters[22]
            self.row["preparation"] = parameters[23]
            self.row["reethauObligations"] = parameters[24]
            self.row["customerObligations"] = parameters[25]
            self.row["templateKey"] = parameters[26]
            self.row["version"] += parameters[27]
            self.row["updatedAt"] = parameters[28]
            self.row["offerDetails"] = parameters[29]
            self.row["status"] = "draft"
            self.row["approvals"] = "[]"
            self.row["approvedAt"] = None
            self.row["sentDate"] = None
            return SimpleNamespace(rowcount=1)
        if statement.startswith("UPDATE sph_proposals SET status=%s,approvals=%s"):
            self.row["status"] = parameters[0]
            self.row["approvals"] = parameters[1]
            if "approved_at=%s" in statement:
                self.row["approvedAt"] = parameters[2]
                self.row["updatedAt"] = parameters[3]
            else:
                self.row["updatedAt"] = parameters[2]
            return SimpleNamespace(rowcount=1)
        if statement.startswith("UPDATE sph_proposals SET status=%s,start_date=%s"):
            self.row["status"] = parameters[0]
            self.row["startDate"] = parameters[1]
            self.row["endDate"] = parameters[2]
            self.row["updatedAt"] = parameters[3]
            return SimpleNamespace(rowcount=1)
        if statement.startswith("UPDATE sph_proposals SET start_date=%s,end_date=%s"):
            self.row["startDate"] = parameters[0]
            self.row["endDate"] = parameters[1]
            if "contract_duration_value=%s" in statement:
                self.row["contractDuration"] = parameters[2]
                self.row["contractDurationUnit"] = parameters[3]
                self.row["updatedAt"] = parameters[4]
            else:
                self.row["updatedAt"] = parameters[2]
            return SimpleNamespace(rowcount=1)
        if statement.startswith("UPDATE sph_proposals SET status=%s,updated_at=%s"):
            self.row["status"] = parameters[0]
            self.row["updatedAt"] = parameters[1]
            return SimpleNamespace(rowcount=1)
        if statement.startswith("INSERT INTO sph_proposal_logs"):
            proposal_id, actor, role, message, created_at = parameters
            self.logs.append({
                "actor": actor,
                "actorRole": role,
                "message": message,
                "createdAt": created_at,
            })
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"Unexpected SQL in test: {statement}")


class SphWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.database = MemorySphDatabase()
        self.db_patch = patch.object(main, "db", return_value=self.database)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_all_proposals_require_commercial_head_approval(self):
        for proposal in (
            {"priceUsd": 14.49, "topPercent": 90},
            {"priceUsd": 14.5, "topPercent": 89.99},
            {"priceUsd": 14.5, "topPercent": 90},
        ):
            with self.subTest(proposal=proposal):
                self.assertEqual(main._sph_approval_route(), ["commercial_head"])

    def test_application_session_prevents_cross_app_api_access(self):
        sph_session = SphRequest("sales")
        with self.assertRaises(main.HTTPException) as error:
            main.require_login(sph_session)
        self.assertEqual(error.exception.status_code, 403)

        commercial_session = SphRequest("sales")
        commercial_session.session["application"] = "commercial"
        with self.assertRaises(main.HTTPException) as error:
            main.require_sph_access(commercial_session)
        self.assertEqual(error.exception.status_code, 403)

    def test_only_assigned_commercial_head_can_access_head_approval(self):
        self.database.user.update({"role": "user", "sph_role": "sales"})
        request = SphRequest("sales", {"action": "approve"}, system_role="user")
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, request))
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.database.row["approvals"], "[]")
        self.assertEqual(self.database.logs, [])

        self.database.user.update({"role": "user", "sph_role": "commercial_head"})
        request = SphRequest(
            "commercial_head",
            {"action": "approve"},
            system_role="user",
        )
        result = asyncio.run(main.sph_proposal_action(7, request))
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["approvals"], ["commercial_head"])
        self.assertEqual(self.database.logs[-1]["actorRole"], "commercial_head")

        self.database.user.update({"role": "user", "sph_role": "sales"})
        with self.assertRaises(main.HTTPException) as error:
            main.require_sph_access(SphRequest("admin"))
        self.assertEqual(error.exception.status_code, 403)

        with patch.object(main, "verify_user_password", return_value=True):
            login_result = asyncio.run(main.login(SphRequest(
                "sales",
                {
                    "username": "reviewer",
                    "password": "password",
                    "application": "sph",
                },
                system_role="user",
            )))
        self.assertEqual(login_result.status_code, 403)

    def test_admin_can_approve_head_stage_without_head_login(self):
        request = SphRequest("admin", {"action": "approve_as_admin"})
        result = asyncio.run(main.sph_proposal_action(7, request))

        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["approvals"], ["commercial_head"])
        self.assertEqual(self.database.logs[-1]["actorRole"], "admin")
        self.assertIn("pengganti Commercial Head", self.database.logs[-1]["message"])

    def test_commercial_head_cannot_perform_admin_workflow_actions(self):
        self.database.user.update({"role": "user", "sph_role": "commercial_head"})

        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, SphRequest(
                "commercial_head",
                {"action": "submit"},
                system_role="user",
            )))

        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.database.row["status"], "review")

    def test_commercial_head_can_read_all_proposals_and_their_details(self):
        self.database.user.update({"role": "user", "sph_role": "commercial_head"})
        request = SphRequest("commercial_head", system_role="user")
        request.session.pop("sph_role", None)

        self.database.list_rows = [
            {
                "id": 7,
                "number": "SPH-2026-11-MKT-001",
                "customerName": "Customer A",
                "proposalDate": date(2026, 11, 1),
                "volumeMin": 100,
                "volumeMax": 200,
                "priceUsd": 14,
                "topPercent": 90,
                "status": "review",
                "version": 0,
                "startDate": None,
                "endDate": None,
                "actualVolume": None,
                "updatedAt": datetime(2026, 11, 1, 10, 0),
            },
            {
                "id": 8,
                "number": "SPH-2026-10-MKT-002",
                "customerName": "Customer B",
                "proposalDate": date(2026, 10, 1),
                "volumeMin": 120,
                "volumeMax": 220,
                "priceUsd": 15,
                "topPercent": 90,
                "status": "active",
                "version": 1,
                "startDate": None,
                "endDate": None,
                "actualVolume": None,
                "updatedAt": datetime(2026, 10, 1, 10, 0),
            },
        ]
        proposals = main.sph_list_proposals(request)
        self.assertEqual([proposal["status"] for proposal in proposals], ["review", "active"])
        self.assertNotIn("WHERE p.status='review'", self.database.list_query)

        proposal = main.sph_get_proposal(7, request)
        self.assertEqual(proposal["approvalRoute"], ["commercial_head"])

        self.database.row["status"] = "approved"
        proposal = main.sph_get_proposal(7, request)
        self.assertEqual(proposal["status"], "approved")

    def test_commercial_head_can_download_pdf_for_non_pending_proposals(self):
        self.database.user.update({"role": "user", "sph_role": "commercial_head"})
        self.database.row["status"] = "active"
        request = SphRequest("commercial_head", system_role="user")

        with patch.object(main, "_sph_generate_proposal_pdf", return_value="pdf") as generate:
            response = main.sph_proposal_pdf(7, request)

        self.assertEqual(response, "pdf")
        generate.assert_called_once()

    def test_commercial_head_cannot_create_or_edit_proposals(self):
        self.database.user.update({"role": "user", "sph_role": "commercial_head"})
        request = SphRequest("commercial_head", {}, system_role="user")

        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_create_proposal(request))
        self.assertEqual(error.exception.status_code, 403)

        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_update_proposal(7, request))
        self.assertEqual(error.exception.status_code, 403)
    def test_proposal_validation_rejects_noncanonical_price_precision(self):
        proposal = {
            "proposalNumber": "  SPH-2026-11-MKT-002  ",
            "customerName": "Customer A",
            "proposalDate": "2026-11-06",
            "volumeMin": 100,
            "volumeMax": 200,
            "priceUsd": 14.5,
            "topPercent": 90,
            "guarantee": "Cash Deposit",
            "dueDay": 20,
            "contractDuration": 2,
            "contractDurationUnit": "year",
            "exchangeClause": False,
        }
        validated = main._sph_validate_proposal(proposal)
        self.assertEqual(validated["proposal_number"], "SPH-2026-11-MKT-002")
        self.assertEqual(validated["price_usd"], 14.5)
        self.assertEqual(validated["template_key"], "standard")

        proposal["startDate"] = "2026-11-10"
        proposal["endDate"] = "2026-11-09"
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

        proposal["endDate"] = "2026-11-11"
        self.assertEqual(
            main._sph_validate_proposal(proposal)["end_date"],
            date(2026, 11, 11),
        )

        proposal.pop("startDate")
        proposal.pop("endDate")
        proposal["proposalNumber"] = ""
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

        proposal["proposalNumber"] = "SPH-2026-11-MKT-002"
        proposal["priceUsd"] = 14.499
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

    def test_create_proposal_persists_edited_offer_details(self):
        offer_details = json.dumps([
            {
                "id": item_id,
                "checked": True,
                "text": "Poin penawaran yang telah diedit." if index == 0 else None,
            }
            for index, item_id in enumerate(main.SPH_OFFER_DETAIL_IDS)
        ])
        proposal = {
            "proposalNumber": "SPH-2026-11-MKT-010",
            "customerName": "Customer A",
            "proposalDate": "2026-11-06",
            "volumeMin": 100,
            "volumeMax": 200,
            "priceUsd": 14.5,
            "topPercent": 90,
            "guarantee": "Cash Deposit",
            "dueDay": 20,
            "contractDuration": 2,
            "contractDurationUnit": "year",
            "offerDetails": offer_details,
        }

        created = asyncio.run(main.sph_create_proposal(
            SphRequest("admin", proposal),
        ))

        self.assertEqual(created["status"], "draft")
        self.assertEqual(
            json.loads(created["offerDetails"])[0]["text"],
            "Poin penawaran yang telah diedit.",
        )

    def test_existing_commercial_head_approval_is_not_replaced_by_admin(self):
        self.database.row["approvals"] = '["commercial_head"]'
        admin_request = SphRequest("admin", {"action": "approve_as_admin"})
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, admin_request))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.database.row["approvals"], '["commercial_head"]')
        self.assertEqual(self.database.logs, [])

    def test_admin_can_edit_submitted_proposal_and_reset_it_to_a_new_draft_version(self):
        self.database.row.update({
            "status": "sent",
            "approvals": '["commercial_head"]',
            "approvedAt": date(2026, 11, 2),
            "sentDate": date(2026, 11, 3),
        })
        proposal = {
            "proposalNumber": "SPH-2026-11-MKT-003",
            "customerName": "Customer A Revised",
            "templateKey": "term_description",
            "addressLine1": "New address",
            "addressLine2": "",
            "proposalDate": "2026-11-06",
            "volumeMin": 120,
            "volumeMax": 240,
            "priceUsd": 15,
            "topPercent": 95,
            "guarantee": "Bank Guarantee",
            "dueDay": 25,
            "exchangeClause": False,
            "contractDuration": 45,
            "contractDurationUnit": "day",
            "durationDetails": "Evaluasi supply setiap tahun.",
            "attentionTo": "Bapak Setiadi",
            "motherStation": "Wunut - Sidoarjo, Jawa Timur",
            "plantName": "Plant Gresik",
            "plantAddress": "Jl. Raya Wringinanom Selatan,\nKab. Gresik",
            "supplyPattern": "Pengiriman sesuai jadwal operasional.",
            "deliveryPoint": "Lokasi pabrik customer.",
            "startDate": "2026-12-01",
            "volumeDetails": "10.000 SM3 per hari.",
            "priceDetails": "Termasuk delivery CNG.",
            "paymentTerms": "Pembayaran maksimal 14 hari setelah tagihan.",
            "advantages": "Pasokan dan layanan monitoring.",
            "otherTerms": "Evaluasi setiap tahun.",
            "preparation": "30 hari setelah penawaran disetujui.",
            "offerDetails": json.dumps([
                {
                    "id": item_id,
                    "checked": index != 1,
                    "text": "Durasi yang sudah diedit." if index == 0 else None,
                }
                for index, item_id in enumerate(main.SPH_OFFER_DETAIL_IDS)
            ]),
            "reethauObligations": "New obligations",
            "customerObligations": "",
        }

        updated = asyncio.run(main.sph_update_proposal(
            7,
            SphRequest("admin", proposal),
        ))

        self.assertEqual(updated["status"], "draft")
        self.assertEqual(updated["version"], 1)
        self.assertEqual(updated["approvals"], [])
        self.assertIsNone(updated["approvedAt"])
        self.assertIsNone(updated["sentDate"])
        self.assertEqual(updated["priceUsd"], 15)
        self.assertEqual(updated["contractDuration"], 45)
        self.assertEqual(updated["contractDurationUnit"], "day")
        self.assertEqual(updated["durationDetails"], "Evaluasi supply setiap tahun.")
        self.assertEqual(
            json.loads(updated["offerDetails"])[0]["text"],
            "Durasi yang sudah diedit.",
        )
        self.assertEqual(updated["attentionTo"], "Bapak Setiadi")
        self.assertEqual(updated["motherStation"], "Wunut - Sidoarjo, Jawa Timur")
        self.assertEqual(updated["plantName"], "Plant Gresik")
        self.assertEqual(updated["plantAddress"], "Jl. Raya Wringinanom Selatan,\nKab. Gresik")
        self.assertEqual(updated["supplyPattern"], "Pengiriman sesuai jadwal operasional.")
        self.assertEqual(updated["deliveryPoint"], "Lokasi pabrik customer.")
        self.assertEqual(updated["startDate"], "2026-12-01")
        self.assertEqual(updated["volumeDetails"], "10.000 SM3 per hari.")
        self.assertEqual(updated["paymentTerms"], "Pembayaran maksimal 14 hari setelah tagihan.")
        self.assertEqual(updated["preparation"], "30 hari setelah penawaran disetujui.")
        self.assertEqual(updated["templateKey"], "term_description")
        self.assertEqual(updated["reethauObligations"], "New obligations")
        self.assertIn("versi baru", self.database.logs[-1]["message"])

    def test_proposal_validation_accepts_term_description_template_and_rejects_unknown(self):
        proposal = {
            "proposalNumber": "SPH-2026-11-MKT-002",
            "customerName": "Customer A",
            "proposalDate": "2026-11-06",
            "volumeMin": 100,
            "volumeMax": 200,
            "priceUsd": 14.5,
            "topPercent": 90,
            "guarantee": "Cash Deposit",
            "dueDay": 20,
            "contractDuration": 45,
            "contractDurationUnit": "day",
            "durationDetails": "Evaluasi setiap tahun.",
            "exchangeClause": False,
            "templateKey": "term_description",
            "motherStation": "Wunut - Sidoarjo, Jawa Timur",
            "plantName": "Plant Gresik",
            "plantAddress": "Jl. Raya Wringinanom Selatan, Kab. Gresik",
        }
        validated = main._sph_validate_proposal(proposal)
        self.assertEqual(validated["template_key"], "term_description")
        self.assertEqual(validated["mother_station"], "Wunut - Sidoarjo, Jawa Timur")
        self.assertEqual(validated["plant_name"], "Plant Gresik")
        self.assertEqual(
            validated["plant_address"],
            "Jl. Raya Wringinanom Selatan, Kab. Gresik",
        )
        proposal["templateKey"] = "unknown"
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

    def test_term_checklist_accepts_structured_and_legacy_text_values(self):
        structured = '[{"label":"Tunai","checked":true},{"label":"Transfer","checked":false}]'
        self.assertEqual(
            main._sph_parse_term_checklist(structured),
            [
                {"label": "Tunai", "checked": True},
                {"label": "Transfer", "checked": False},
            ],
        )
        self.assertEqual(
            main._sph_parse_term_checklist("Maksimal 14 hari.\nDibayar melalui transfer."),
            [
                {"label": "Maksimal 14 hari.", "checked": True},
                {"label": "Dibayar melalui transfer.", "checked": True},
            ],
        )
        self.assertEqual(
            main._sph_parse_term_checklist("Lainnya: Syarat tambahan."),
            [{"label": "Syarat tambahan.", "checked": True}],
        )
        self.assertEqual(
            main._sph_parse_term_checklist(
                "Reethau memiliki banyak armada:\n- Tube Skid 40 ft\n- Head Truck 40 ft"
            ),
            [{
                "label": (
                    "Reethau memiliki banyak armada:\n"
                    "- Tube Skid 40 ft\n"
                    "- Head Truck 40 ft"
                ),
                "checked": True,
            }],
        )

    def test_proposal_validation_accepts_duration_in_days_and_enforces_unit_limits(self):
        proposal = {
            "proposalNumber": "SPH-2026-11-MKT-020",
            "customerName": "Customer A",
            "proposalDate": "2026-11-06",
            "volumeMin": 100,
            "volumeMax": 200,
            "priceUsd": 14.5,
            "dueDay": 20,
            "contractDuration": 30,
            "contractDurationUnit": "day",
        }
        validated = main._sph_validate_proposal(proposal)
        self.assertEqual(validated["contract_duration_value"], 30)
        self.assertEqual(validated["contract_duration_unit"], "day")

        proposal["contractDuration"] = 5476
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

        proposal["contractDuration"] = 16
        proposal["contractDurationUnit"] = "year"
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

    def test_active_proposal_cannot_be_edited(self):
        self.database.row["status"] = "active"
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_update_proposal(
                7,
                SphRequest("admin", {
                    "proposalNumber": "SPH-2026-11-MKT-001",
                    "customerName": "Customer A",
                    "proposalDate": "2026-11-06",
                    "volumeMin": 100,
                    "volumeMax": 200,
                    "priceUsd": 14.5,
                    "topPercent": 90,
                    "guarantee": "Cash Deposit",
                    "dueDay": 20,
                    "contractYears": 2,
                    "contractDuration": 45,
                    "contractDurationUnit": "day",
                    "exchangeClause": False,
                }),
            ))
        self.assertEqual(error.exception.status_code, 409)

    def test_only_admin_can_activate_customer_approved_proposal(self):
        self.database.row["status"] = "customer_approved"
        self.database.user.update({"role": "user", "sph_role": "sales"})
        sales_request = SphRequest(
            "sales",
            {"action": "activate"},
            system_role="user",
        )
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, sales_request))
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.database.row["status"], "customer_approved")

        self.database.user.update({"role": "admin", "sph_role": None})
        admin_request = SphRequest("admin", {
            "action": "activate",
            "startDate": "2026-11-01",
            "endDate": "2028-10-31",
        })
        result = asyncio.run(main.sph_proposal_action(7, admin_request))
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["startDate"], "2026-11-01")
        self.assertEqual(result["endDate"], "2028-10-31")
        self.assertEqual(self.database.logs[-1]["actorRole"], "admin")
        self.assertEqual(
            self.database.logs[-1]["message"],
            "Pelanggan diaktifkan setelah persetujuan SPH untuk periode 2026-11-01 sampai 2028-10-31.",
        )

    def test_activation_rejects_end_date_without_a_start_date(self):
        self.database.row["status"] = "customer_approved"
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, SphRequest(
                "admin",
                {"action": "activate", "endDate": "2027-10-31"},
            )))
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.database.row["status"], "customer_approved")

    def test_activation_allows_start_date_without_expiration_monitoring(self):
        self.database.row["status"] = "customer_approved"

        result = asyncio.run(main.sph_proposal_action(7, SphRequest(
            "admin",
            {"action": "activate", "startDate": "2026-11-01"},
        )))

        self.assertEqual(result["status"], "active")
        self.assertEqual(result["startDate"], "2026-11-01")
        self.assertIsNone(result["endDate"])
        self.assertFalse(result["contractDatesMissing"])
        self.assertFalse(result["contractExpired"])

    def test_activation_allows_contracts_without_date_periods(self):
        self.database.row["status"] = "customer_approved"

        result = asyncio.run(main.sph_proposal_action(7, SphRequest(
            "admin",
            {"action": "activate"},
        )))

        self.assertEqual(result["status"], "active")
        self.assertIsNone(result["startDate"])
        self.assertIsNone(result["endDate"])
        self.assertFalse(result["contractDatesMissing"])
        self.assertFalse(result["contractExpired"])
        self.assertIn("tanpa tanggal selesai", self.database.logs[-1]["message"])

    def test_expired_contract_can_be_renewed_with_new_dates_and_duration(self):
        today = main._sph_now().date()
        self.database.row.update({
            "status": "active",
            "startDate": today - timedelta(days=365),
            "endDate": today - timedelta(days=1),
        })
        renewal_start = today.isoformat()
        renewal_end = (today + timedelta(days=730)).isoformat()
        result = asyncio.run(main.sph_proposal_action(7, SphRequest(
            "admin",
            {
                "action": "renew_contract",
                "startDate": renewal_start,
                "endDate": renewal_end,
                "contractDuration": 2,
                "contractDurationUnit": "year",
            },
        )))
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["startDate"], renewal_start)
        self.assertEqual(result["endDate"], renewal_end)
        self.assertEqual(result["contractDuration"], 2)
        self.assertFalse(result["contractExpired"])
        self.assertIn("Memperpanjang kontrak", self.database.logs[-1]["message"])

    def test_active_contract_cannot_be_deactivated_before_end_date(self):
        self.database.row.update({
            "status": "active",
            "startDate": date(2026, 11, 1),
            "endDate": main._sph_now().date() + timedelta(days=1),
        })
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, SphRequest(
                "admin",
                {"action": "deactivate_contract"},
            )))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.database.row["status"], "active")

    def test_expired_contract_can_be_marked_inactive_by_admin(self):
        today = main._sph_now().date()
        self.database.row.update({
            "status": "active",
            "startDate": today - timedelta(days=365),
            "endDate": today - timedelta(days=1),
        })

        result = asyncio.run(main.sph_proposal_action(7, SphRequest(
            "admin",
            {"action": "deactivate_contract"},
        )))

        self.assertEqual(result["status"], "inactive")
        self.assertFalse(result["contractExpired"])
        self.assertIn("Tidak Aktif", self.database.logs[-1]["message"])

    def test_admin_can_complete_dates_for_an_existing_active_contract(self):
        self.database.row["status"] = "active"

        result = asyncio.run(main.sph_proposal_action(7, SphRequest(
            "admin",
            {
                "action": "record_contract_dates",
                "startDate": "2026-11-01",
                "endDate": "2027-10-31",
            },
        )))

        self.assertEqual(result["startDate"], "2026-11-01")
        self.assertEqual(result["endDate"], "2027-10-31")
        self.assertFalse(result["contractDatesMissing"])

    def test_legal_handoff_action_is_no_longer_valid(self):
        self.database.row["status"] = "customer_approved"
        request = SphRequest("admin", {"action": "handoff_legal"})
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, request))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.database.row["status"], "customer_approved")

    def test_legacy_pjbg_proposal_can_be_activated_by_admin(self):
        self.database.row["status"] = "pjbg"
        self.database.user.update({"role": "admin", "sph_role": None})
        request = SphRequest("admin", {
            "action": "activate",
            "startDate": "2026-11-01",
            "endDate": "2028-10-31",
        })
        proposal = asyncio.run(main.sph_proposal_action(7, request))
        self.assertEqual(proposal["status"], "active")

    def test_sph_pdf_endpoint_returns_a_downloadable_pdf(self):
        response = main.sph_proposal_pdf(7, SphRequest("admin"))

        async def read_response():
            return b"".join([chunk async for chunk in response.body_iterator])

        content = asyncio.run(read_response())
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertIn("attachment;", response.headers["content-disposition"])

    def test_sph_pdf_preview_uses_unsaved_input_without_logging_or_mutating_proposal(self):
        original_row = dict(self.database.row)
        original_logs = list(self.database.logs)
        request = SphRequest("commercial_head", {
            "proposalNumber": "SPH-2026-11-MKT-009",
            "customerName": "Preview Customer",
            "templateKey": "term_description",
            "addressLine1": "Preview Street 10",
            "addressLine2": "Preview City",
            "attentionTo": "Bapak Setiadi",
            "motherStation": "Wunut - Sidoarjo, Jawa Timur",
            "supplyPattern": "Pasokan mengikuti jadwal operasional.",
            "deliveryPoint": "Plant customer.",
            "startDate": "2026-12-01",
            "volumeDetails": "10.000 SM3 per hari.",
            "priceDetails": "Harga belum termasuk pajak.",
            "paymentTerms": "Maksimal 14 hari setelah tagihan.\nDibayar melalui transfer.",
            "advantages": "Layanan pasokan CNG.\nFasilitas armada tersedia.",
            "otherTerms": "Evaluasi dilakukan setiap tahun.\nLainnya: Syarat tambahan.",
            "preparation": "30 hari setelah penawaran disetujui.",
            "proposalDate": "2026-11-13",
            "volumeMin": 8000,
            "volumeMax": 10000,
            "priceUsd": 15,
            "topPercent": 90,
            "guarantee": "Cash Deposit",
            "dueDay": 20,
            "contractDuration": 45,
            "contractDurationUnit": "day",
            "exchangeClause": False,
            "reethauObligations": "Mengirim CNG.",
            "customerObligations": "Menyediakan area.",
            "offerDetails": json.dumps([
                {
                    "id": item_id,
                    "checked": True,
                    "text": "Poin pratinjau yang telah diedit." if index == 0 else None,
                }
                for index, item_id in enumerate(main.SPH_OFFER_DETAIL_IDS)
            ]),
        })
        with patch.object(
            main,
            "_sph_generate_proposal_pdf",
            wraps=main._sph_generate_proposal_pdf,
        ) as generate_pdf:
            response = asyncio.run(main.sph_proposal_pdf_preview(request))

        async def read_response():
            return b"".join([chunk async for chunk in response.body_iterator])

        content = asyncio.run(read_response())
        self.assertEqual(response.media_type, "application/pdf")
        self.assertIn("inline;", response.headers["content-disposition"])
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertEqual(
            main._sph_validate_proposal(request.payload)["template_key"],
            "term_description",
        )
        self.assertEqual(
            json.loads(generate_pdf.call_args.args[0]["offerDetails"])[0]["text"],
            "Poin pratinjau yang telah diedit.",
        )
        self.assertEqual(self.database.row, original_row)
        self.assertEqual(self.database.logs, original_logs)

    def test_sph_pdf_formats_address_and_approval_page_like_template(self):
        from reportlab.platypus import Paragraph

        self.database.row.update({
            "addressLine1": "Jalan Akses Tol Cibitung No.82, Gandasari,",
            "addressLine2": "Kecamatan Cikarang Barat, Kabupaten Bekasi, Jawa Barat 17530",
        })
        paragraph_texts = []

        def capture_paragraph(text, style=None, bulletText=None, *args, **kwargs):
            paragraph_texts.append(text)
            return Paragraph(text, style, bulletText, *args, **kwargs)

        with patch("reportlab.platypus.Paragraph", side_effect=capture_paragraph):
            main.sph_proposal_pdf(7, SphRequest("admin"))

        self.assertIn(
            "Jalan Akses Tol Cibitung No.82, Gandasari,"
            "<br/>Kecamatan Cikarang Barat, Kabupaten Bekasi, Jawa Barat 17530",
            paragraph_texts,
        )
        self.assertIn("Masa kontrak 2 (Dua) tahun.", paragraph_texts)
        self.assertIn("Approval Penawaran", paragraph_texts)
        self.assertIn("PT Green Pulse Dynamics", paragraph_texts)
        self.assertIn(
            "<u><b>Sahrul Astrurrachman</b></u><br/>"
            "<i>Commercial &amp; Marketing Head</i>",
            paragraph_texts,
        )

    def test_sph_pdf_uses_checked_and_edited_offer_details(self):
        from reportlab.platypus import Paragraph

        self.database.row["offerDetails"] = json.dumps([
            {
                "id": item_id,
                "checked": index in {0, 2},
                "text": (
                    "Masa kontrak yang telah disesuaikan."
                    if index == 0
                    else None
                ),
            }
            for index, item_id in enumerate(main.SPH_OFFER_DETAIL_IDS)
        ])
        detail_items = []

        def capture_paragraph(text, style=None, bulletText=None, *args, **kwargs):
            if bulletText is not None and style.name == "SphListB":
                detail_items.append((bulletText, text))
            return Paragraph(text, style, bulletText, *args, **kwargs)

        with patch("reportlab.platypus.Paragraph", side_effect=capture_paragraph):
            main.sph_proposal_pdf(7, SphRequest("admin"))

        self.assertEqual(detail_items, [
            ("1.", "Masa kontrak yang telah disesuaikan."),
            (
                "2.",
                "Perhitungan pemakaian CNG menggunakan metering milik "
                "PT Reethau Cipta Energi.",
            ),
        ])

    def test_sph_offer_details_validation_requires_nine_valid_items(self):
        valid_items = [
            {"id": item_id, "checked": True, "text": None}
            for item_id in main.SPH_OFFER_DETAIL_IDS
        ]
        self.assertEqual(
            json.loads(main._sph_validate_offer_details(json.dumps(valid_items))),
            valid_items,
        )

        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_offer_details("[]")
        self.assertEqual(error.exception.status_code, 400)

    def test_term_description_pdf_uses_the_selected_templates_structure_and_data(self):
        from reportlab.platypus import Paragraph
        from reportlab.pdfgen.canvas import Canvas

        proposal = {
            "number": "SPH-2026-11-MKT-010",
            "templateKey": "term_description",
            "customerName": "Preview Customer",
            "addressLine1": "Preview Street 10",
            "addressLine2": "Preview City",
            "proposalDate": "2026-11-13",
            "volumeMin": 8000,
            "volumeMax": 10000,
            "priceUsd": 15,
            "topPercent": 90,
            "guarantee": "Cash Deposit",
            "dueDay": 20,
            "exchangeClause": False,
            "contractDuration": 30,
            "contractDurationUnit": "day",
            "durationDetails": "Evaluasi supply setiap tahun.",
            "attentionTo": "Bapak Setiadi",
            "motherStation": "MS Wunut - Sidoarjo, Jawa Timur",
            "plantName": "Plant Gresik",
            "plantAddress": "Jl. Raya Wringinanom Selatan,\nKab. Gresik",
            "supplyPattern": "Pasokan mengikuti jadwal operasional.",
            "deliveryPoint": "Plant customer.",
            "startDate": "2026-12-01",
            "volumeDetails": "10.000 SM3 per hari.",
            "priceDetails": "Harga belum termasuk pajak.",
            "paymentTerms": "Maksimal 14 hari setelah tagihan.\nDibayar melalui transfer.",
            "advantages": (
                "Keunggulan pertama.\n- Rincian armada A\n"
                "- Rincian armada B\nKeunggulan kedua."
            ),
            "otherTerms": "Evaluasi dilakukan setiap tahun.\nLainnya: Syarat tambahan.",
            "preparation": "30 hari setelah penawaran disetujui.",
            "reethauObligations": "Mengirim CNG.",
            "customerObligations": "Menyediakan area.",
            "status": "draft",
        }
        paragraph_texts = []

        def capture_paragraph(text, style=None, *args, **kwargs):
            paragraph_texts.append(text)
            return Paragraph(text, style, *args, **kwargs)

        font_calls = []
        original_set_font = Canvas.setFont

        def capture_font(canvas, font_name, font_size, *args, **kwargs):
            font_calls.append((font_name, font_size))
            return original_set_font(canvas, font_name, font_size, *args, **kwargs)

        with (
            patch("reportlab.platypus.Paragraph", side_effect=capture_paragraph),
            patch.object(Canvas, "setFont", autospec=True, side_effect=capture_font),
        ):
            response = main._sph_generate_proposal_pdf(proposal, inline=True)

        async def read_response():
            return b"".join([chunk async for chunk in response.body_iterator])

        content = asyncio.run(read_response())
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertIn(b"/MediaBox [ 0 0 612 792 ]", content)
        font_resources = re.findall(rb"/BaseFont /([^\s/]+)", content)
        self.assertTrue(any(
            b"ArialNarrow" in name
            or b"LiberationSansNarrow" in name
            or b"RobotoCondensed" in name
            for name in font_resources
        ))
        self.assertTrue(any(
            b"Narrow-Bold" in name or b"RobotoCondensed-Bold" in name
            for name in font_resources
        ))
        for expected in (
            "TERM",
            "DESKRIPSI",
            "Penjual",
            "Preview Customer",
            "Preview Street 10<br/>Preview City",
            "Wunut - Sidoarjo, Jawa Timur",
            "Supply Gas By MS Wunut - Sidoarjo, Jawa Timur",
            "Plant Gresik",
            "Jl. Raya Wringinanom Selatan,<br/>Kab. Gresik",
            "USD 15,00 / MMBTU",
            "30 hari.",
            "Evaluasi supply setiap tahun.",
            "Bapak Setiadi",
            "Plant customer.",
            "10.000 SM3 per hari.",
            "Harga belum termasuk pajak.",
            "Maksimal 14 hari setelah tagihan.",
            "Dibayar melalui transfer.",
            "Keunggulan pertama.",
            "Rincian armada A",
            "Rincian armada B",
            "Keunggulan kedua.",
            "Evaluasi dilakukan setiap tahun.",
            "Syarat tambahan.",
            "30 hari setelah penawaran disetujui.",
            "Approval Customer",
            "Sahrul Astrurrachman",
            "Commercial &amp; Marketing Head",
        ):
            with self.subTest(expected=expected):
                self.assertTrue(
                    any(expected in text for text in paragraph_texts),
                    f"{expected!r} was not rendered in the terms template",
                )
        self.assertFalse(any("TOP" in text for text in paragraph_texts))
        self.assertFalse(any(
            "Klausul tukar-menukar tidak berlaku" in text
            for text in paragraph_texts
        ))
        self.assertTrue(any(
            "Pola Supply<br/>Titik Penyerahan" in text
            for text in paragraph_texts
        ))
        self.assertNotIn(("Helvetica-Bold", 34), font_calls)
        self.assertTrue(any(
            "<b>1.</b> Maksimal 14 hari" in text for text in paragraph_texts
        ))
        self.assertTrue(any(
            "<b>2.</b> Dibayar melalui transfer." in text
            for text in paragraph_texts
        ))
        self.assertTrue(any(
            "<b>1.</b> Keunggulan pertama.<br/>- Rincian armada A<br/>- Rincian armada B"
            in text
            for text in paragraph_texts
        ))
        self.assertTrue(any(
            "<b>2.</b> Keunggulan kedua." in text for text in paragraph_texts
        ))

        proposal["priceDetails"] = "Plant Gresik Harga USD: 15,00 / MMBTU"
        paragraph_texts.clear()
        with patch("reportlab.platypus.Paragraph", side_effect=capture_paragraph):
            main._sph_generate_proposal_pdf(proposal, inline=True)
        self.assertTrue(any(
            "Plant Gresik Harga USD: 15,00 / MMBTU" in text
            for text in paragraph_texts
        ))
        self.assertFalse(any(
            text.strip() == "USD 15,00 / MMBTU"
            for text in paragraph_texts
        ))

    def test_supply_pattern_packing_reads_legacy_and_plant_details(self):
        legacy = (
            '{"format":"rce_supply_details_v1",'
            '"motherStation":"MS Wunut","pattern":"Jadwal operasional."}'
        )
        self.assertEqual(
            main._sph_unpack_supply_pattern(legacy),
            ("MS Wunut", "Jadwal operasional.", "", ""),
        )
        packed = main._sph_pack_supply_pattern(
            "Setiap hari.",
            "MS Wunut",
            "Plant Gresik",
            "Jl. Raya Wringinanom",
        )
        self.assertEqual(
            main._sph_unpack_supply_pattern(packed),
            (
                "MS Wunut",
                "Setiap hari.",
                "Plant Gresik",
                "Jl. Raya Wringinanom",
            ),
        )

    def test_sph_pdf_list_numbers_match_body_font_and_indentation(self):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph

        self.database.row["reethauObligations"] = "Pengiriman CNG."
        self.database.row["customerObligations"] = "Menyediakan area parkir."
        list_styles = []

        def capture_paragraph(text, style=None, bulletText=None, *args, **kwargs):
            if bulletText is not None:
                list_styles.append(style)
            return Paragraph(text, style, bulletText, *args, **kwargs)

        with patch("reportlab.platypus.Paragraph", side_effect=capture_paragraph):
            main.sph_proposal_pdf(7, SphRequest("admin"))

        self.assertTrue(list_styles)
        self.assertEqual({style.name for style in list_styles}, {"SphListB", "SphListC", "SphListD"})
        for style in list_styles:
            with self.subTest(bullet_font=style.bulletFontName):
                self.assertEqual(style.fontName, "Times-Roman")
                self.assertEqual(style.bulletFontName, style.fontName)
                self.assertEqual(style.bulletFontSize, style.fontSize)
                section = style.name[-1]
                expected_indent = 4.2 * mm + stringWidth(f"{section}. ", "Times-Bold", 10)
                self.assertEqual(style.bulletIndent, expected_indent)
                self.assertEqual(style.leftIndent, expected_indent + 6 * mm)


if __name__ == "__main__":
    unittest.main()
