"""
Tests for the emergency triage service.

Focus:
- documented urgency criteria (U1-U4) fire on the right evidence
- missing information is reported, never invented
- thin reports fall back to the conservative level (never under-triaged)
- optional AI enrichment can add interpretation but never lower urgency
"""

from app.services import triage_service


def _incident(description: str, people: int = 1, lat: float = 24.86, lng: float = 67.0) -> dict:
    return {
        "incident_id": "RSN-TEST01",
        "description": description,
        "people_affected": people,
        "latitude": lat,
        "longitude": lng,
        "status": "queued",
    }


class TestUrgencyCriteria:
    def test_life_threat_evidence_is_critical(self):
        triage = triage_service.build_triage(
            _incident("Two people trapped under a collapsed wall, cannot move")
        )
        assert triage.urgency_level == "critical"
        u1 = next(c for c in triage.criteria if c.rule_id == "U1")
        assert u1.matched is True
        assert any("trapped" in e for e in u1.evidence)

    def test_hazard_with_many_people_is_critical(self):
        triage = triage_service.build_triage(
            _incident("Fire spreading through the building", people=8)
        )
        assert triage.urgency_level == "critical"

    def test_hazard_alone_is_high(self):
        triage = triage_service.build_triage(
            _incident("Smoke and fire on the ground floor", people=2)
        )
        assert triage.urgency_level == "high"
        u2 = next(c for c in triage.criteria if c.rule_id == "U2")
        assert u2.matched and "hazard(s) present: fire" in " ".join(u2.evidence)

    def test_many_people_without_hazard_is_high(self):
        triage = triage_service.build_triage(
            _incident("Power out across the block, six people affected", people=6)
        )
        assert triage.urgency_level == "high"
        u1 = next(c for c in triage.criteria if c.rule_id == "U1")
        assert u1.matched is False  # no life-threat evidence, no active hazard

    def test_time_critical_language_is_high(self):
        triage = triage_service.build_triage(
            _incident("Please send help immediately, water is rising", people=2)
        )
        assert triage.urgency_level == "high"

    def test_injury_without_life_threat_is_medium(self):
        triage = triage_service.build_triage(
            _incident("My neighbour has a fractured arm after the fall", people=2)
        )
        assert triage.urgency_level == "medium"

    def test_explicitly_non_urgent_is_low(self):
        triage = triage_service.build_triage(
            _incident("Not urgent: we need one blanket, no injuries", people=1)
        )
        assert triage.urgency_level == "low"

    def test_every_rule_is_reported_with_evidence(self):
        triage = triage_service.build_triage(_incident("Nothing much to go on"))
        rule_ids = [c.rule_id for c in triage.criteria]
        assert rule_ids == ["U1", "U2", "U3", "U4"]
        assert all(c.description for c in triage.criteria)

    def test_criteria_version_is_exposed(self):
        triage = triage_service.build_triage(_incident("Fire in the kitchen"))
        assert triage.criteria_version == triage_service.CRITERIA_VERSION


class TestConservativeDefaults:
    def test_thin_report_is_not_under_triaged(self):
        triage = triage_service.build_triage(_incident("Something happened here"))
        assert triage.urgency_level == "medium"
        assert triage.insufficient_evidence is True

    def test_urgency_score_matches_level(self):
        triage = triage_service.build_triage(_incident("Trapped and cannot move"))
        assert triage.urgency_score == triage_service.URGENCY_SCORES[triage.urgency_level]


class TestEvidenceExtraction:
    def test_hazards_are_extracted(self):
        triage = triage_service.build_triage(
            _incident("Gas leak near the school, electrical sparks too")
        )
        assert "gas" in triage.hazards
        assert "electrical" in triage.hazards

    def test_requested_assistance_requires_request_language(self):
        triage = triage_service.build_triage(
            _incident("We need drinking water and food for four people", people=4)
        )
        assert any("food" in a or "water" in a for a in triage.requested_assistance)

    def test_missing_info_is_recorded(self):
        triage = triage_service.build_triage(_incident("Something happened here"))
        assert any("hazard" in m.lower() for m in triage.missing_info)

    def test_people_mentioned_in_text_is_flagged_on_mismatch(self):
        triage = triage_service.build_triage(
            _incident("Rooftop collapse, three people need help", people=9)
        )
        assert triage.people_affected_stated_in_text == 3
        assert any("3 people" in u for u in triage.uncertain)

    def test_location_is_never_invented(self):
        incident = _incident("Fire in the house", lat=24.8615, lng=67.002)
        triage = triage_service.build_triage(incident)
        assert triage.location.latitude == 24.8615
        assert triage.location.longitude == 67.002
        assert triage.location.source == "reported_coordinates"

    def test_zero_coordinates_are_flagged_as_uncertain(self):
        triage = triage_service.build_triage(
            _incident("Fire in the house", lat=0.0, lng=0.0)
        )
        assert any("(0,0)" in u for u in triage.uncertain)


class TestAIEnrichment:
    def test_ai_summary_is_advisory_only(self, monkeypatch):
        """AI interpretation must never lower the rule-derived urgency."""
        def fake_ai(incident):
            return "Report says a minor window is broken. (interpretation)"

        monkeypatch.setattr(triage_service, "_ai_interpret", fake_ai)

        incident = _incident("Person trapped under debris, cannot move")
        triage = triage_service.get_triage(incident, use_ai=True)

        assert triage.urgency_level == "critical"
        assert triage.source == "rules+ai"
        assert "minor window" in triage.ai_summary

    def test_no_ai_keeps_rules_source(self, monkeypatch):
        monkeypatch.setattr(triage_service, "_ai_interpret", lambda incident: None)
        triage = triage_service.get_triage(_incident("Fire in the kitchen"), use_ai=True)
        assert triage.source == "rules"
        assert triage.ai_summary is None


class TestTriageAPI:
    def test_triage_endpoint_returns_criteria(self, client):
        client.post(
            "/api/incidents",
            json={"description": "Trapped under rubble", "people_affected": 2,
                  "latitude": 24.86, "longitude": 67.0},
        )
        res = client.get("/api/incidents/RSN-000001/triage")
        assert res.status_code == 200
        body = res.json()
        assert body["urgency_level"] == "critical"
        assert body["criteria_version"] == triage_service.CRITERIA_VERSION
        assert len(body["criteria"]) == 4

    def test_triage_unknown_incident_404(self, client):
        assert client.get("/api/incidents/RSN-999999/triage").status_code == 404
