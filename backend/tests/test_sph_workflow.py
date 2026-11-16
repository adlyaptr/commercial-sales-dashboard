import asyncio
import re
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
            "volumeDetails": "",
            "priceDetails": "",
            "paymentTerms": "",
            "advantages": "",
            "otherTerms": "",
            "preparation": "",
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
            self.row["contractDuration"] = parameters[10]
            self.row["contractDurationUnit"] = parameters[11]
            self.row["durationDetails"] = parameters[12]
            self.row["attentionTo"] = parameters[13]
            self.row["supplyPattern"] = parameters[14]
            self.row["deliveryPoint"] = parameters[15]
            self.row["startDate"] = parameters[16]
            self.row["volumeDetails"] = parameters[17]
            self.row["priceDetails"] = parameters[18]
            self.row["paymentTerms"] = parameters[19]
            self.row["advantages"] = parameters[20]
            self.row["otherTerms"] = parameters[21]
            self.row["preparation"] = parameters[22]
            self.row["reethauObligations"] = parameters[23]
            self.row["customerObligations"] = parameters[24]
            self.row["templateKey"] = parameters[25]
            self.row["version"] += parameters[26]
            self.row["updatedAt"] = parameters[27]
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
            "contractDuration": 2,
            "contractDurationUnit": "year",
            "exchangeClause": False,
        }
        validated = main._sph_validate_proposal(proposal)
        self.assertEqual(validated["proposal_number"], "SPH-2026-11-MKT-002")
        self.assertEqual(validated["price_usd"], 14.5)
        self.assertEqual(validated["template_key"], "standard")

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
        self.assertEqual(updated["contractDuration"], 45)
        self.assertEqual(updated["contractDurationUnit"], "day")
        self.assertEqual(updated["durationDetails"], "Evaluasi supply setiap tahun.")
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
                    "contractDuration": 45,
                    "contractDurationUnit": "day",
                    "exchangeClause": False,
                }),
            ))
        self.assertEqual(error.exception.status_code, 409)

    def test_only_admin_can_activate_customer_approved_proposal(self):
        self.database.row["status"] = "customer_approved"
        self.database.user["sph_role"] = "sales"
        sales_request = SphRequest("sales", {"action": "activate"})
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, sales_request))
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.database.row["status"], "customer_approved")

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
        self.assertEqual(
            self.database.logs[-1]["message"],
            "Pelanggan diaktifkan setelah persetujuan SPH.",
        )

    def test_legal_handoff_action_is_no_longer_valid(self):
        self.database.row["status"] = "customer_approved"
        self.database.user["sph_role"] = "sales"
        request = SphRequest("sales", {"action": "handoff_legal"})
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.sph_proposal_action(7, request))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.database.row["status"], "customer_approved")

    def test_legacy_pjbg_proposal_can_be_activated_by_admin(self):
        self.database.row["status"] = "pjbg"
        self.database.user.update({"role": "admin", "sph_role": None})
        request = SphRequest("admin", {"action": "activate"})
        request.session.update({
            "username": "admin",
            "role": "admin",
            "sph_role": None,
        })
        proposal = asyncio.run(main.sph_proposal_action(7, request))
        self.assertEqual(proposal["status"], "active")

    def test_sph_pdf_endpoint_returns_a_downloadable_pdf(self):
        response = main.sph_proposal_pdf(7, SphRequest("commercial_head"))

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
        })
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
            main.sph_proposal_pdf(7, SphRequest("commercial_head"))

        self.assertIn(
            "Jalan Akses Tol Cibitung No.82, Gandasari,"
            "<br/>Kecamatan Cikarang Barat, Kabupaten Bekasi, Jawa Barat 17530",
            paragraph_texts,
        )
        self.assertIn("Masa kontrak 2 (Dua) tahun.", paragraph_texts)
        self.assertIn("Approval Penawaran", paragraph_texts)
        self.assertIn("PT Green Pulse Dynamics", paragraph_texts)
        self.assertIn(
            "<u><b>Sahrul Asturrachman</b></u><br/><i>Commercial Head</i>",
            paragraph_texts,
        )

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
            b"ArialNarrow" in name or b"LiberationSansNarrow" in name
            for name in font_resources
        ))
        self.assertTrue(any(
            b"Narrow-Bold" in name
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
