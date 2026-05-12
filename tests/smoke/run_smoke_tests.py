from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main as app_main


app = app_main.app


client = TestClient(app)


def assert_ok(response):
    assert response.status_code == 200, response.text
    return response.json()


class _FakeStructuredInvoker:
    def __init__(self, factory):
        self.factory = factory

    def invoke(self, messages):
        return self.factory(messages)


def _install_recommendation_test_doubles() -> None:
    def fake_extract(messages):
        payload = json.loads(messages[-1].content)
        message = payload["message"].lower()
        conversation_state = payload.get("conversation_state", {})
        recommendation_context = conversation_state.get("recommendation_context", {})

        extraction = {
            "intent": "unsupported",
            "age": None,
            "insurer": None,
            "tier": None,
            "plan_name": None,
            "benefit_keyword": None,
            "budget_preference": None,
            "ward_preference": None,
            "coverage_style": None,
        }

        if "what is the premium" in message or "cash do i pay" in message or ("how much" in message and "pay" in message):
            extraction["intent"] = "premium"
        elif "cover for" in message or "what does" in message or "does " in message or "icu" in message or "psychiatric" in message or "mental health" in message or "ward" in message:
            extraction["intent"] = "benefit"
        elif "insurance" in message or recommendation_context.get("pending"):
            extraction["intent"] = "recommendation"
        if "26" in message:
            extraction["age"] = 26
        if "62" in message:
            extraction["age"] = 62
        if "45" in message:
            extraction["age"] = 45
        if "singlife" in message:
            extraction["insurer"] = "Singlife"
        if "prudential" in message:
            extraction["insurer"] = "Prudential"
        if "private hospital" in message:
            extraction["tier"] = "private"
        if "class a" in message:
            extraction["tier"] = "class_a"
        if "standard" in message:
            extraction["tier"] = "standard"
        if "shield plan 1" in message:
            extraction["plan_name"] = "Shield Plan 1"
        if "icu" in message:
            extraction["benefit_keyword"] = "icu"
        if "psychiatric" in message:
            extraction["benefit_keyword"] = "psychiatric"
        if "ward" in message and extraction["benefit_keyword"] is None:
            extraction["benefit_keyword"] = "ward"
        if "keep premiums low" in message or "low-cost" in message or "low cost" in message:
            extraction["budget_preference"] = "low_cost"
        if "balanced option" in message or "balanced tradeoff" in message:
            extraction["budget_preference"] = "balanced"
        if "coverage is better" in message:
            extraction["budget_preference"] = "coverage_flexible"
        if "private hospital" in message:
            extraction["ward_preference"] = "private"
        if "class b1" in message:
            extraction["ward_preference"] = "class_b1"
        if "standard coverage" in message:
            extraction["ward_preference"] = "standard"
        if "lowest-cost option" in message:
            extraction["coverage_style"] = "lowest_cost"
        if "balanced tradeoff" in message:
            extraction["coverage_style"] = "balanced"
        if "strongest coverage" in message:
            extraction["coverage_style"] = "strongest_coverage"

        return app_main.RouteExtraction(**extraction)

    def fake_intake(messages):
        payload = json.loads(messages[-1].content)
        recommendation_context = payload.get("recommendation_context", {})
        missing_fields = [
            field
            for field in app_main.RECOMMENDATION_REQUIRED_FIELDS
            if recommendation_context.get(field) is None
        ]
        next_field = missing_fields[0]
        questions = {
            "age": "How old are you?",
            "budget_preference": "Do you want to keep premiums low, stay balanced, or prioritize stronger coverage even if it costs more?",
            "ward_preference": "Which hospital ward level are you aiming for: basic, Standard, Class B1, Class A, private, or are you unsure?",
            "coverage_style": "Do you want the lowest-cost option, a balanced tradeoff, or the strongest coverage?",
        }
        return app_main.RecommendationIntakeQuestion(
            next_field=next_field,
            missing_fields=missing_fields,
            next_question=questions[next_field],
        )

    def fake_reasoner(messages):
        payload = json.loads(messages[-1].content)
        candidates = payload.get("candidates", [])[:3]
        return app_main.RecommendationDecision(
            recommended_tier=candidates[0]["tier_code"] if candidates else "standard",
            summary="Based on your stated preferences, these three plans are the strongest grounded shortlist to compare next.",
            decision_factors=payload.get("decision_factors", []),
            plan_choices=[
                app_main.RecommendationPlanChoice(
                    plan_id=candidate["plan_id"],
                    rationale=f"{candidate['display_name']} fits the requested balance of tier, cost, and coverage.",
                )
                for candidate in candidates
            ],
            disclaimer=app_main.RECOMMENDATION_DEFAULT_DISCLAIMER,
        )

    app_main._structured_extractor = lambda: _FakeStructuredInvoker(fake_extract)
    app_main._recommendation_intake_model = lambda: _FakeStructuredInvoker(fake_intake)
    app_main._recommendation_reasoner_model = lambda: _FakeStructuredInvoker(fake_reasoner)
    app_main._chat_graph.cache_clear()


def main() -> None:
    health = assert_ok(client.get("/health"))
    assert health["status"] == "ok"
    assert health["master_data"]["plan_catalog_rows"] == 39
    assert health["master_data"]["benefits_master_rows"] == 1736
    assert health["master_data"]["premiums_master_rows"] == 570
    assert health["master_data"]["cpf_limits_master_rows"] == 3

    premium_scalar = assert_ok(
        client.post(
            "/premium/quote",
            json={"age": 45, "insurer": "Prudential", "tier": "class_a"},
        )
    )
    assert premium_scalar["error"] is None
    assert premium_scalar["premium_result"]["premium_shape"] == "scalar"
    assert premium_scalar["premium_result"]["cash_payable_min"] == 106
    assert premium_scalar["premium_result"]["cash_payable_max"] == 106

    premium_range = assert_ok(
        client.post(
            "/premium/quote",
            json={"age": 62, "insurer": "Great Eastern", "tier": "class_a"},
        )
    )
    assert premium_range["error"] is None
    assert premium_range["premium_result"]["premium_shape"] == "range"
    assert premium_range["premium_result"]["premium_total_min"] != premium_range["premium_result"]["premium_total_max"]

    premium_unavailable = assert_ok(
        client.post(
            "/premium/quote",
            json={"age": 45, "insurer": "Singlife", "tier": "private", "plan_name": "Shield Starter"},
        )
    )
    assert premium_unavailable["error"] is None
    assert premium_unavailable["premium_result"]["premium_available"] is False
    assert "1-39" in premium_unavailable["premium_result"]["availability_note"]

    premium_ambiguous = assert_ok(
        client.post(
            "/premium/quote",
            json={"age": 45, "tier": "class_a"},
        )
    )
    assert premium_ambiguous["error"]["code"] == "ambiguous_plan"

    for age in [40, 41, 70, 71, 90, 91]:
        boundary_quote = assert_ok(
            client.post(
                "/premium/quote",
                json={"age": age, "insurer": "Prudential", "tier": "class_a"},
            )
        )
        assert boundary_quote["error"] is None
        assert boundary_quote["premium_result"]["age"] == age

    benefit_direct = assert_ok(
        client.post(
            "/benefit/search",
            json={"insurer": "Income", "tier": "basic", "plan_name": "IncomeShield Plan C", "benefit_keyword": "psychiatric"},
        )
    )
    assert benefit_direct["error"] is None
    assert "Psychiatric" in benefit_direct["benefit_result"]["best_match"]["benefit_raw"]

    benefit_synonym = assert_ok(
        client.post(
            "/benefit/search",
            json={"tier": "standard", "benefit_keyword": "mental health"},
        )
    )
    assert benefit_synonym["error"] is None
    assert "Psychiatric" in benefit_synonym["benefit_result"]["best_match"]["benefit_raw"]

    benefit_standard_fallback = assert_ok(
        client.post(
            "/benefit/search",
            json={"insurer": "Singlife", "tier": "standard", "benefit_keyword": "icu"},
        )
    )
    assert benefit_standard_fallback["error"] is None
    assert benefit_standard_fallback["plan_resolution"]["used_fallback"] is True
    assert benefit_standard_fallback["plan_resolution"]["effective_plan_id"] == "standard__standard_ip"

    benefit_no_match = assert_ok(
        client.post(
            "/benefit/search",
            json={"tier": "standard", "benefit_keyword": "helicopter"},
        )
    )
    assert benefit_no_match["error"]["code"] == "benefit_not_found"

    _install_recommendation_test_doubles()

    recommendation_turn_1 = assert_ok(
        client.post(
            "/chat",
            json={"message": "I am 26 years old, what insurance should I buy?"},
        )
    )
    recommendation_result_1 = recommendation_turn_1["extracted_data"]["result"]
    recommendation_state = recommendation_turn_1["extracted_data"]["conversation_state"]
    assert recommendation_result_1["kind"] == "recommendation_intake"
    assert recommendation_result_1["recommendation_context"]["age"] == 26
    assert recommendation_result_1["next_field"] == "budget_preference"

    recommendation_turn_2 = assert_ok(
        client.post(
            "/chat",
            json={
                "message": "I want to keep premiums low.",
                "conversation_state": recommendation_state,
            },
        )
    )
    recommendation_result_2 = recommendation_turn_2["extracted_data"]["result"]
    recommendation_state = recommendation_turn_2["extracted_data"]["conversation_state"]
    assert recommendation_result_2["kind"] == "recommendation_intake"
    assert recommendation_result_2["recommendation_context"]["budget_preference"] == "low_cost"
    assert recommendation_result_2["next_field"] == "ward_preference"

    recommendation_turn_3 = assert_ok(
        client.post(
            "/chat",
            json={
                "message": "I prefer private hospital coverage.",
                "conversation_state": recommendation_state,
            },
        )
    )
    recommendation_result_3 = recommendation_turn_3["extracted_data"]["result"]
    recommendation_state = recommendation_turn_3["extracted_data"]["conversation_state"]
    assert recommendation_result_3["kind"] == "recommendation_intake"
    assert recommendation_result_3["recommendation_context"]["ward_preference"] == "private"
    assert recommendation_result_3["next_field"] == "coverage_style"

    recommendation_turn_4 = assert_ok(
        client.post(
            "/chat",
            json={
                "message": "I want the strongest coverage.",
                "conversation_state": recommendation_state,
            },
        )
    )
    recommendation_result_4 = recommendation_turn_4["extracted_data"]["result"]
    assert recommendation_result_4["kind"] == "recommendation"
    assert len(recommendation_result_4["recommendations"]) == 3
    assert recommendation_result_4["disclaimer"]
    insurers = {recommendation["insurer_name"] for recommendation in recommendation_result_4["recommendations"]}
    assert len(insurers) == len(recommendation_result_4["recommendations"])
    for recommendation in recommendation_result_4["recommendations"]:
        assert recommendation["plan_id"]
        assert recommendation["display_name"]
        assert recommendation["annual_premium_display"]
        assert recommendation["source_pdf"]
        assert recommendation["source_page"] >= 1
        assert recommendation["source_table"] >= 1

    recommendation_reset_premium = assert_ok(
        client.post(
            "/chat",
            json={
                "message": "What is the premium for Singlife Shield Plan 1 if I am 62?",
                "conversation_state": recommendation_state,
            },
        )
    )
    recommendation_reset_premium_result = recommendation_reset_premium["extracted_data"]["result"]
    assert recommendation_reset_premium_result["kind"] == "premium"
    assert recommendation_reset_premium["extracted_data"]["conversation_state"] == {}

    recommendation_reset_benefit = assert_ok(
        client.post(
            "/chat",
            json={
                "message": "What does the Standard plan cover for ICU?",
                "conversation_state": recommendation_state,
            },
        )
    )
    recommendation_reset_benefit_result = recommendation_reset_benefit["extracted_data"]["result"]
    assert recommendation_reset_benefit_result["kind"] == "benefit"
    assert recommendation_reset_benefit["extracted_data"]["conversation_state"] == {}

    print("Smoke tests passed.")


if __name__ == "__main__":
    main()
