import asyncio
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class SphRequest:
    def __init__(self, role, payload=None):
        self.payload = payload or {}
        self.session = {
            "username": "reviewer",
            "role": "user",
            "application": "sph",
            "sph_role": role,
        }

    async def json(self):
        return self.payload


class MemorySphDatabase:
    def __init__(self):
        self.user = {"role": "user", "sph_role": "commercial_head"}
        self.row = {
            "id": 7,
            "number": "SPH-2026-11-MKT-001",
            "customer_key": "customer-a",
            "customerName": "Customer A",
            "addressLine1": "",
            "addressLine2": "",
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

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        parameters = parameters or ()
        if statement.startswith("SELECT role,sph_role FROM app_users"):
            return SimpleNamespace(fetchone=lambda: self.user)
        if statement.startswith("SELECT role FROM app_users"):
            return SimpleNamespace(fetchone=lambda: {"role": self.user["role"]})
        if statement.startswith("SELECT p.id,p.proposal_number"):
            return SimpleNamespace(fetchone=lambda: dict(self.row))
        if statement.startswith("SELECT id FROM sph_proposals WHERE proposal_number"):
            return SimpleNamespace(fetchone=lambda: None)
        if statement.startswith("SELECT actor_username AS actor"):
            return SimpleNamespace(fetchall=lambda: list(reversed(self.logs)))
        if statement.startswith("INSERT INTO sph_customers"):
            return SimpleNamespace(rowcount=1)
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
            self.row["contractYears"] = parameters[10]
            self.row["reethauObligations"] = parameters[11]
            self.row["customerObligations"] = parameters[12]
            self.row["version"] += parameters[13]
            self.row["updatedAt"] = parameters[14]
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

    def test_all_proposals_require_only_commercial_head_approval(self):
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
            "contractYears": 2,
            "exchangeClause": False,
        }
        validated = main._sph_validate_proposal(proposal)
        self.assertEqual(validated["proposal_number"], "SPH-2026-11-MKT-002")
        self.assertEqual(validated["price_usd"], 14.5)

        proposal["proposalNumber"] = ""
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

        proposal["proposalNumber"] = "SPH-2026-11-MKT-002"
        proposal["priceUsd"] = 14.499
        with self.assertRaises(main.HTTPException) as error:
            main._sph_validate_proposal(proposal)
        self.assertEqual(error.exception.status_code, 400)

    def test_only_commercial_head_can_approve_and_approval_finishes_in_one_stage(self):
        self.database.user["sph_role"] = "sales"
        request = SphRequest("sales", {"action": "approve"})
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, request))
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.database.row["approvals"], "[]")
        self.assertEqual(self.database.logs, [])

        self.database.user["sph_role"] = "director"
        director_request = SphRequest("director", {"action": "approve"})
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, director_request))
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.database.row["approvals"], "[]")

        self.database.user["sph_role"] = "commercial_head"
        head_request = SphRequest("commercial_head", {"action": "approve"})
        result = asyncio.run(main.sph_proposal_action(7, head_request))
        self.assertEqual(result["status"], "approved")
        self.assertEqual(
            result["approvals"],
            ["commercial_head"],
        )
        self.assertEqual(len(self.database.logs), 1)

    def test_sales_can_edit_submitted_proposal_and_reset_it_to_a_new_draft_version(self):
        self.database.user["sph_role"] = "sales"
        self.database.row.update({
            "status": "sent",
            "approvals": '["commercial_head"]',
            "approvedAt": date(2026, 11, 2),
            "sentDate": date(2026, 11, 3),
        })
        proposal = {
            "proposalNumber": "SPH-2026-11-MKT-003",
            "customerName": "Customer A Revised",
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
            "contractYears": 3,
            "reethauObligations": "New obligations",
            "customerObligations": "",
        }

        updated = asyncio.run(main.sph_update_proposal(
            7,
            SphRequest("sales", proposal),
        ))

        self.assertEqual(updated["status"], "draft")
        self.assertEqual(updated["version"], 1)
        self.assertEqual(updated["approvals"], [])
        self.assertIsNone(updated["approvedAt"])
        self.assertIsNone(updated["sentDate"])
        self.assertEqual(updated["priceUsd"], 15)
        self.assertEqual(updated["reethauObligations"], "New obligations")
        self.assertIn("versi baru", self.database.logs[-1]["message"])

    def test_active_proposal_cannot_be_edited(self):
        self.database.user["sph_role"] = "sales"
        self.database.row["status"] = "active"
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_update_proposal(
                7,
                SphRequest("sales", {
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
                    "exchangeClause": False,
                }),
            ))
        self.assertEqual(error.exception.status_code, 409)

    def test_only_admin_can_activate_proposal_after_legal_handoff(self):
        self.database.row["status"] = "pjbg"
        self.database.user["sph_role"] = "legal"
        legal_request = SphRequest("legal", {"action": "activate"})
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, legal_request))
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.database.row["status"], "pjbg")

        self.database.user.update({"role": "admin", "sph_role": None})
        admin_request = SphRequest("admin", {"action": "activate"})
        admin_request.session.update({
            "username": "admin",
            "role": "admin",
            "sph_role": None,
        })
        result = asyncio.run(main.sph_proposal_action(7, admin_request))
        self.assertEqual(result["status"], "active")
        self.assertEqual(self.database.logs[-1]["actorRole"], "admin")

    def test_sph_pdf_endpoint_returns_a_downloadable_pdf(self):
        response = main.sph_proposal_pdf(7, SphRequest("commercial_head"))

        async def read_response():
            return b"".join([chunk async for chunk in response.body_iterator])

        content = asyncio.run(read_response())
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertIn("attachment;", response.headers["content-disposition"])

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
            main.sph_proposal_pdf(7, SphRequest("commercial_head"))

        self.assertIn(
            "Jalan Akses Tol Cibitung No.82, Gandasari,"
            "<br/>Kecamatan Cikarang Barat, Kabupaten Bekasi, Jawa Barat 17530",
            paragraph_texts,
        )
        self.assertIn("Approval Penawaran", paragraph_texts)
        self.assertIn("PT Green Pulse Dynamics", paragraph_texts)
        self.assertIn(
            "<u><b>Sahrul Asturrachman</b></u><br/><i>Commercial Head</i>",
            paragraph_texts,
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
            main.sph_proposal_pdf(7, SphRequest("commercial_head"))

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
