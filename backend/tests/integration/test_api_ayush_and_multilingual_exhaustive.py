"""
Domain 6 Integration Tests: AYUSH Clinical Normalization & Multilingual Language Engine.
Exhaustive coverage:
- AYUSH fuzzy entity normalization to AFI and NAMASTE standards.
- Single string and batch list queries.
- Hindi script and Latin transliteration fuzzy matching.
- Active languages retrieval (/api/languages).
- Interview language updates and code switching.
- Interview mode switching (GENERAL <-> AYUSH).
"""
import pytest
from fastapi.testclient import TestClient

from app.models.interview import InterviewMode


class TestAyushEntityNormalization:
    """Test fuzzy matching to official AFI and NAMASTE pharmacopoeia codes."""

    def test_exact_match_ashwagandha_churna(self, client: TestClient):
        payload = {"query": "Ashwagandha Churna"}
        res = client.post("/api/ayush/normalize", json=payload)
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        assert results[0]["matched"] is True
        assert results[0]["afi_code"] == "AFI:Churna:01"
        assert results[0]["namaste_code"] == "AYU-CH-001"
        assert results[0]["match_score"] >= 80.0

    def test_fuzzy_match_with_dosage_and_instructions(self, client: TestClient):
        payload = {"query": "Avipattikar Churna 3g with lukewarm water"}
        res = client.post("/api/ayush/normalize", json=payload)
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        assert results[0]["matched"] is True
        assert results[0]["afi_code"] == "AFI:Churna:03"
        assert results[0]["namaste_code"] == "AYU-CH-003"

    def test_hindi_devanagari_query_matching(self, client: TestClient):
        payload = {"query": "त्रिफळा चूर्ण"}
        res = client.post("/api/ayush/normalize", json=payload)
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        assert results[0]["matched"] is True
        assert results[0]["afi_code"] == "AFI:Churna:12"
        assert results[0]["namaste_code"] == "AYU-CH-012"

    def test_batch_list_normalization(self, client: TestClient):
        payload = {"query": ["Ashwagandha Churna", "Triphala Churna"]}
        res = client.post("/api/ayush/normalize", json=payload)
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 2
        afi_codes = [r["afi_code"] for r in results if r.get("matched")]
        assert "AFI:Churna:01" in afi_codes
        assert "AFI:Churna:12" in afi_codes

    def test_unrecognized_query_handles_gracefully(self, client: TestClient):
        payload = {"query": "NonexistentRandomChemicalXYZ999"}
        res = client.post("/api/ayush/normalize", json=payload)
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        assert results[0]["matched"] is False
        assert results[0]["match_score"] < 65.0


class TestMultilingualAndModeConfiguration:
    """Test languages listing, language switching, and AYUSH mode switching."""

    def test_get_supported_languages(self, client: TestClient):
        res = client.get("/api/languages")
        assert res.status_code == 200
        languages = res.json()
        assert len(languages) >= 1
        codes = [lang["code"] for lang in languages]
        assert "hi" in codes or "en" in codes

    def test_update_interview_language(self, client: TestClient, create_test_patient):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]

        # Switch language to en
        update_res = client.put(
            f"/api/interviews/{interview_id}/language",
            json={"language_code": "en"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["language_code"] == "en"

    def test_update_interview_mode_between_general_and_ayush(
        self, client: TestClient, create_test_patient
    ):
        patient = create_test_patient()
        interview_res = client.post(
            "/api/interviews",
            json={"patient_id": patient.id, "preferred_language": "hi"},
        )
        interview_id = interview_res.json()["id"]
        assert interview_res.json()["mode"] == InterviewMode.GENERAL.value

        # Switch to AYUSH
        ayush_res = client.put(
            f"/api/interviews/{interview_id}/mode",
            json={"mode": InterviewMode.AYUSH.value},
        )
        assert ayush_res.status_code == 200
        assert ayush_res.json()["mode"] == InterviewMode.AYUSH.value

        # Switch back to GENERAL
        gen_res = client.put(
            f"/api/interviews/{interview_id}/mode",
            json={"mode": InterviewMode.GENERAL.value},
        )
        assert gen_res.status_code == 200
        assert gen_res.json()["mode"] == InterviewMode.GENERAL.value
