from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from data_loader import get_master_data_store, normalize_key
from tools import (
    RecommendationCandidateSet,
    ToolExecutionError,
    build_recommendation_candidates,
    calculate_premium,
    lookup_benefit,
    lookup_cpf_limit,
    resolve_plan,
)


ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"
DEFAULT_MODEL = "gpt-4o-mini"

load_dotenv(ENV_PATH)

RecommendationBudgetPreference = Literal["low_cost", "balanced", "coverage_flexible"]
RecommendationWardPreference = Literal["basic", "standard", "class_b1", "class_a", "private", "unsure"]
RecommendationCoverageStyle = Literal["lowest_cost", "balanced", "strongest_coverage"]
RecommendationField = Literal["age", "budget_preference", "ward_preference", "coverage_style"]
RecommendationTier = Literal["basic", "standard", "class_b1", "class_a", "private"]

RECOMMENDATION_REQUIRED_FIELDS: List[RecommendationField] = [
    "age",
    "budget_preference",
    "ward_preference",
    "coverage_style",
]

RECOMMENDATION_OPTION_MAP: Dict[RecommendationField, List[Dict[str, str]]] = {
    "budget_preference": [
        {
            "value": "low_cost",
            "label": "Keep premiums low",
            "reply_text": "I want to keep premiums low.",
        },
        {
            "value": "balanced",
            "label": "Balanced cost and coverage",
            "reply_text": "I want a balanced option.",
        },
        {
            "value": "coverage_flexible",
            "label": "Coverage matters more",
            "reply_text": "I am flexible on cost if coverage is better.",
        },
    ],
    "ward_preference": [
        {"value": "basic", "label": "Basic / Plan C", "reply_text": "I prefer basic coverage."},
        {"value": "standard", "label": "Standard", "reply_text": "I prefer Standard coverage."},
        {"value": "class_b1", "label": "Class B1", "reply_text": "I prefer Class B1 coverage."},
        {"value": "class_a", "label": "Class A", "reply_text": "I prefer Class A coverage."},
        {"value": "private", "label": "Private hospital", "reply_text": "I prefer private hospital coverage."},
        {"value": "unsure", "label": "Not sure yet", "reply_text": "I am not sure about the ward tier yet."},
    ],
    "coverage_style": [
        {
            "value": "lowest_cost",
            "label": "Lowest cost",
            "reply_text": "I want the lowest-cost option.",
        },
        {
            "value": "balanced",
            "label": "Balanced",
            "reply_text": "I want a balanced tradeoff.",
        },
        {
            "value": "strongest_coverage",
            "label": "Strongest coverage",
            "reply_text": "I want the strongest coverage.",
        },
    ],
}

RECOMMENDATION_DEFAULT_DISCLAIMER = (
    "This shortlist is informational only and is based on your age, stated preferences, and the plan premium tables in this project. "
    "It is not formal financial advice or a personalized suitability assessment."
)

RECOMMENDATION_FOLLOW_UP_TERMS = {
    "low cost",
    "low-cost",
    "keep premiums low",
    "balanced",
    "coverage",
    "private hospital",
    "class b1",
    "class a",
    "standard",
    "basic",
    "unsure",
    "strongest",
}


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_state: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str
    tool_used: Optional[str] = None
    extracted_data: Dict[str, Any]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model: str
    master_data: Dict[str, Any]


class PremiumQuoteRequest(BaseModel):
    age: int = Field(ge=1, le=120)
    insurer: Optional[str] = None
    tier: Optional[str] = None
    plan_name: Optional[str] = None


class PremiumQuoteResponse(BaseModel):
    response: str
    plan_resolution: Optional[Dict[str, Any]] = None
    cpf_limit: Optional[Dict[str, Any]] = None
    premium_result: Optional[Dict[str, Any]] = None
    error: Optional[ErrorPayload] = None


class BenefitSearchRequest(BaseModel):
    benefit_keyword: str = Field(min_length=1)
    insurer: Optional[str] = None
    tier: Optional[str] = None
    plan_name: Optional[str] = None


class BenefitSearchResponse(BaseModel):
    response: str
    plan_resolution: Optional[Dict[str, Any]] = None
    benefit_result: Optional[Dict[str, Any]] = None
    error: Optional[ErrorPayload] = None


class RecommendationContextModel(BaseModel):
    age: Optional[int] = Field(default=None, ge=1, le=120)
    budget_preference: Optional[RecommendationBudgetPreference] = None
    ward_preference: Optional[RecommendationWardPreference] = None
    coverage_style: Optional[RecommendationCoverageStyle] = None


class RouteExtraction(BaseModel):
    intent: Literal["premium", "benefit", "recommendation", "unsupported"]
    age: Optional[int] = None
    insurer: Optional[str] = None
    tier: Optional[str] = None
    plan_name: Optional[str] = None
    benefit_keyword: Optional[str] = None
    budget_preference: Optional[RecommendationBudgetPreference] = None
    ward_preference: Optional[RecommendationWardPreference] = None
    coverage_style: Optional[RecommendationCoverageStyle] = None


class RecommendationIntakeQuestion(BaseModel):
    next_field: RecommendationField
    missing_fields: List[RecommendationField]
    next_question: str


class RecommendationPlanChoice(BaseModel):
    plan_id: str
    rationale: str


class RecommendationDecision(BaseModel):
    recommended_tier: RecommendationTier
    summary: str
    decision_factors: List[str]
    plan_choices: List[RecommendationPlanChoice]
    disclaimer: str


class ChatState(TypedDict, total=False):
    message: str
    conversation_state: Dict[str, Any]
    conversation_state_out: Dict[str, Any]
    extraction: Dict[str, Any]
    recommendation_context: Dict[str, Any]
    recommendation_missing_fields: List[str]
    tool_used: Optional[str]
    tool_payload: Dict[str, Any]
    response: str


EXTRACTION_SYSTEM_PROMPT = """You are the routing and extraction engine for a Singapore health policy assistant.

Your job:
1. Determine whether the user is asking for a premium/cash-payable calculation, a benefit/coverage lookup, a recommendation request, or something unsupported.
2. Extract only the structured fields requested by the schema.

Rules:
- Do not answer the user's question.
- For premium requests, extract age when present and insurer/tier/plan hints when present.
- For benefit requests, extract insurer/tier/plan hints and a concise benefit keyword.
- For recommendation requests, extract age and any stated preferences:
  - budget_preference: low_cost | balanced | coverage_flexible
  - ward_preference: basic | standard | class_b1 | class_a | private | unsure
  - coverage_style: lowest_cost | balanced | strongest_coverage
- If the current conversation_state shows a pending recommendation intake, treat short follow-up answers as part of the same recommendation flow unless the user clearly starts a new premium or benefit question.
- If the query is not about Singapore Integrated Shield Plan premiums, benefits, or recommendation support, set intent to unsupported.
- If the user asks about "standard plan" coverage, keep tier as standard even if insurer is not specified.
- Leave uncertain fields as null rather than guessing.
"""

RECOMMENDATION_INTAKE_SYSTEM_PROMPT = """You are the intake planner for a Singapore health policy recommendation assistant.

Your job:
1. Look at the current recommendation context.
2. Identify which required fields are still missing.
3. Ask exactly one natural follow-up question that will help fill the next best missing field.

Rules:
- Required fields are: age, budget_preference, ward_preference, coverage_style.
- Keep the question short and conversational.
- Ask for only one field at a time.
- Do not recommend any plans yet.
- If age is missing, ask for age first.
- Otherwise prefer this order: budget_preference, ward_preference, coverage_style.
"""

RECOMMENDATION_REASONER_SYSTEM_PROMPT = """You are the final recommendation reasoner for a Singapore health policy assistant.

You will receive:
- the user's structured recommendation context
- a deterministic candidate list with real plan_ids, tiers, premiums, cash-payable ranges, and heuristic scores

Your job:
1. Choose the best top 3 plans from the provided candidates only.
2. Recommend a tier.
3. Explain the tradeoffs clearly and concisely.

Rules:
- You must only use plan_ids that appear in the candidate list.
- Do not invent plans, insurers, premiums, benefit facts, or citations.
- Prefer a shortlist with insurer diversity when the candidates are close.
- Use the heuristic scores and decision factors as strong evidence, but you may reorder close candidates if your explanation is consistent with the payload.
- The summary should read like a helpful recommendation, not a disclaimer.
- The disclaimer must clearly say this is informational and not formal financial advice.
"""

SYNTHESIS_SYSTEM_PROMPT = """You are the final reply layer for a Singapore health policy assistant.

Rules:
- Use only the structured facts provided in the tool payload.
- Never invent premiums, benefits, age bands, insurers, or citations.
- If tool_used is null, explain clearly what went wrong or what information is missing.
- For premium replies:
  - mention the matched plan
  - mention the matched age band
  - say whether the premium is a scalar or a range
  - mention CPF withdrawal limit
  - mention cash payable min/max when available
  - cite source_pdf, source_page, and source_table
- For benefit replies:
  - answer using the exact coverage_value_raw
  - include notes if useful
  - cite source_pdf, source_page, and source_table
  - if shared Standard IP benefits were used, say so
- Keep the response concise, clear, and factual.
"""


def _model_dump(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return value
    raise TypeError(f"Cannot dump value of type {type(value)}")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_ready(inner) for inner in value]
    if isinstance(value, tuple):
        return [_json_ready(inner) for inner in value]
    if isinstance(value, BaseModel):
        return _json_ready(_model_dump(value))
    if hasattr(value, "to_dict"):
        return _json_ready(value.to_dict())
    return value


def _json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(_json_ready(payload), indent=2, ensure_ascii=True)


def _openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            f"OPENAI_API_KEY is missing. Add it to {ENV_PATH} or export it in your shell."
        )
    return api_key


def _openai_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


@lru_cache(maxsize=1)
def _chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=_openai_model(),
        temperature=0,
        api_key=_openai_api_key(),
    )


@lru_cache(maxsize=1)
def _structured_extractor():
    return _chat_model().with_structured_output(RouteExtraction)


@lru_cache(maxsize=1)
def _recommendation_intake_model():
    return _chat_model().with_structured_output(RecommendationIntakeQuestion)


@lru_cache(maxsize=1)
def _recommendation_reasoner_model():
    return _chat_model().with_structured_output(RecommendationDecision)


def _currency(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    rounded = int(value)
    if float(value) == float(rounded):
        return f"${rounded:,}"
    return f"${value:,.2f}"


def _currency_span(min_value: Optional[float], max_value: Optional[float]) -> str:
    if min_value is None or max_value is None:
        return "N/A"
    if min_value == max_value:
        return _currency(min_value)
    return f"{_currency(min_value)} to {_currency(max_value)}"


def _source_text(source_pdf: str, source_page: int, source_table: int) -> str:
    return f"{source_pdf}, Page {source_page}, Table {source_table}"


def _error_payload(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> ErrorPayload:
    return ErrorPayload(code=code, message=message, details=details or {})


def _tool_error_payload(
    *,
    message: str,
    code: str,
    extraction: Dict[str, Any],
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "kind": "error",
        "code": code,
        "message": message,
        "details": details or {},
        "extraction": extraction,
    }


def _master_data_status() -> Dict[str, Any]:
    store = get_master_data_store()
    return {
        "loaded": True,
        "plan_catalog_rows": int(store.plan_catalog.shape[0]),
        "benefits_master_rows": int(store.benefits_master.shape[0]),
        "premiums_master_rows": int(store.premiums_master.shape[0]),
        "cpf_limits_master_rows": int(store.cpf_limits_master.shape[0]),
    }


def _normalize_recommendation_context(context: Dict[str, Any]) -> Dict[str, Any]:
    if not context:
        return {}
    try:
        return _json_ready(RecommendationContextModel(**context).model_dump(exclude_none=True))
    except Exception:
        return {}


def _merge_recommendation_context(
    current_context: Dict[str, Any],
    extraction: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(current_context)
    for field in RECOMMENDATION_REQUIRED_FIELDS:
        value = extraction.get(field)
        if value is not None:
            merged[field] = value
    return merged


def _recommendation_missing_fields(context: Dict[str, Any]) -> List[str]:
    return [field for field in RECOMMENDATION_REQUIRED_FIELDS if context.get(field) is None]


def _recommendation_options(field: str) -> List[Dict[str, str]]:
    return RECOMMENDATION_OPTION_MAP.get(field, [])


def _recommendation_context_payload(context: Dict[str, Any], pending: bool) -> Dict[str, Any]:
    payload = _normalize_recommendation_context(context)
    payload["pending"] = pending
    return payload


def _should_continue_recommendation_intake(message: str) -> bool:
    normalized = normalize_key(message)
    if not normalized:
        return False
    if any(term in normalized for term in RECOMMENDATION_FOLLOW_UP_TERMS):
        return True
    if re.search(r"\b\d{1,3}\b", normalized):
        return True
    return len(normalized.split()) <= 8


def _run_premium_lookup(
    *,
    age: int,
    insurer: Optional[str],
    tier: Optional[str],
    plan_name: Optional[str],
) -> Dict[str, Any]:
    resolution = resolve_plan(
        insurer=insurer,
        tier=tier,
        plan_name=plan_name,
        capability="premium",
    )
    cpf_result = lookup_cpf_limit(age)
    premium_result = calculate_premium(
        age=age,
        plan_id=resolution.effective_plan_id,
    )
    return {
        "kind": "premium",
        "plan_resolution": resolution.to_dict(),
        "cpf_limit": cpf_result.to_dict(),
        "premium_result": premium_result.to_dict(),
    }


def _run_benefit_lookup(
    *,
    benefit_keyword: str,
    insurer: Optional[str],
    tier: Optional[str],
    plan_name: Optional[str],
) -> Dict[str, Any]:
    resolution = resolve_plan(
        insurer=insurer,
        tier=tier,
        plan_name=plan_name,
        capability="benefit",
    )
    benefit_result = lookup_benefit(
        plan_id=resolution.effective_plan_id,
        keyword=benefit_keyword,
    )
    return {
        "kind": "benefit",
        "plan_resolution": resolution.to_dict(),
        "benefit_result": benefit_result.to_dict(),
    }


def _format_premium_response(payload: Dict[str, Any]) -> str:
    resolution = payload["plan_resolution"]
    cpf_limit = payload["cpf_limit"]
    premium_result = payload["premium_result"]
    source_text = _source_text(
        premium_result["source_pdf"],
        premium_result["source_page"],
        premium_result["source_table"],
    )

    if not premium_result["premium_available"]:
        note = premium_result["availability_note"] or "The source table marks this premium as unavailable."
        return (
            f"For {resolution['requested_display_name']} at age {premium_result['age']} "
            f"(age band {premium_result['age_band_raw']}), the premium is unavailable in the "
            f"source table. {note} Source: {source_text}."
        )

    total_text = _currency_span(
        premium_result["premium_total_min"],
        premium_result["premium_total_max"],
    )
    cash_text = _currency_span(
        premium_result["cash_payable_min"],
        premium_result["cash_payable_max"],
    )
    if premium_result["premium_shape"] == "scalar":
        premium_line = f"the total premium is {total_text}"
        cash_line = f"the cash payable is {cash_text}"
    else:
        premium_line = f"the total premium ranges from {total_text}"
        cash_line = f"the cash payable ranges from {cash_text}"

    return (
        f"For {resolution['requested_display_name']} at age {premium_result['age']} "
        f"(age band {premium_result['age_band_raw']}), {premium_line}. "
        f"CPF withdrawal limit is {_currency(cpf_limit['max_withdrawal_limit'])}, so {cash_line}. "
        f"Source: {source_text}."
    )


def _format_benefit_response(payload: Dict[str, Any]) -> str:
    resolution = payload["plan_resolution"]
    benefit_result = payload["benefit_result"]
    best_match = benefit_result["best_match"]
    source_text = _source_text(
        best_match["source_pdf"],
        best_match["source_page"],
        best_match["source_table"],
    )

    if resolution["used_fallback"]:
        intro = (
            f"Using the shared {resolution['effective_display_name']} benefit schedule for "
            f"{resolution['requested_display_name']}, the matched benefit is "
            f"{best_match['coverage_value_raw']} for {best_match['benefit_raw']}."
        )
    else:
        intro = (
            f"For {resolution['requested_display_name']}, the matched benefit is "
            f"{best_match['coverage_value_raw']} for {best_match['benefit_raw']}."
        )

    notes = best_match["notes_raw"]
    notes_text = f" Note: {notes}." if notes else ""
    return f"{intro}{notes_text} Source: {source_text}."


def _extract_node(state: ChatState) -> ChatState:
    raw_recommendation_context = state.get("conversation_state", {}).get("recommendation_context", {})
    current_context = _normalize_recommendation_context(raw_recommendation_context)
    recommendation_pending = bool(raw_recommendation_context.get("pending"))
    result = _structured_extractor().invoke(
        [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(
                content=_json_dumps(
                    {
                        "message": state["message"],
                        "conversation_state": state.get("conversation_state", {}),
                    }
                )
            ),
        ]
    )
    extraction = _json_ready(_model_dump(result))
    if recommendation_pending and extraction["intent"] == "unsupported" and _should_continue_recommendation_intake(state["message"]):
        extraction["intent"] = "recommendation"

    recommendation_context: Dict[str, Any] = {}
    recommendation_missing_fields: List[str] = []
    if extraction["intent"] == "recommendation":
        recommendation_context = _merge_recommendation_context(current_context, extraction)
        recommendation_missing_fields = _recommendation_missing_fields(recommendation_context)

    return {
        "extraction": extraction,
        "recommendation_context": recommendation_context,
        "recommendation_missing_fields": recommendation_missing_fields,
    }


def _route_after_extract(state: ChatState) -> str:
    extraction = RouteExtraction(**state["extraction"])
    if extraction.intent == "recommendation":
        if state.get("recommendation_missing_fields"):
            return "recommendation_intake"
        return "recommendation_reasoner"
    return "tool"


def _tool_node(state: ChatState) -> ChatState:
    extraction_data = RouteExtraction(**state["extraction"])

    if extraction_data.intent == "unsupported":
        return {
            "tool_used": None,
            "tool_payload": {
                "kind": "unsupported",
                "code": "unsupported_intent",
                "message": (
                    "This assistant currently supports only Integrated Shield Plan premium, benefit, "
                    "and recommendation questions."
                ),
                "details": {},
                "extraction": _json_ready(_model_dump(extraction_data)),
            },
            "conversation_state_out": {},
        }

    try:
        if extraction_data.intent == "premium":
            if extraction_data.age is None:
                return {
                    "tool_used": None,
                    "tool_payload": _tool_error_payload(
                        message="I need the user's age to calculate premiums.",
                        code="missing_age",
                        extraction=_json_ready(_model_dump(extraction_data)),
                    ),
                    "conversation_state_out": {},
                }

            tool_payload = _run_premium_lookup(
                age=extraction_data.age,
                insurer=extraction_data.insurer,
                tier=extraction_data.tier,
                plan_name=extraction_data.plan_name,
            )
            tool_payload["extraction"] = _json_ready(_model_dump(extraction_data))
            return {
                "tool_used": "premium_calculator",
                "tool_payload": tool_payload,
                "conversation_state_out": {},
            }

        if extraction_data.benefit_keyword is None:
            return {
                "tool_used": None,
                "tool_payload": _tool_error_payload(
                    message="Add a benefit keyword such as ICU, psychiatric, ward, or cancer so I can run the coverage lookup.",
                    code="missing_benefit_keyword",
                    extraction=_json_ready(_model_dump(extraction_data)),
                ),
                "conversation_state_out": {},
            }

        tool_payload = _run_benefit_lookup(
            benefit_keyword=extraction_data.benefit_keyword,
            insurer=extraction_data.insurer,
            tier=extraction_data.tier,
            plan_name=extraction_data.plan_name,
        )
        tool_payload["extraction"] = _json_ready(_model_dump(extraction_data))
        return {
            "tool_used": "benefit_lookup",
            "tool_payload": tool_payload,
            "conversation_state_out": {},
        }
    except ToolExecutionError as error:
        return {
            "tool_used": None,
            "tool_payload": _tool_error_payload(
                message=error.message,
                code=error.code,
                extraction=_json_ready(_model_dump(extraction_data)),
                details=error.details,
            ),
            "conversation_state_out": {},
        }


def _recommendation_intake_node(state: ChatState) -> ChatState:
    extraction_data = _json_ready(state["extraction"])
    recommendation_context = _normalize_recommendation_context(state.get("recommendation_context", {}))
    intake = _recommendation_intake_model().invoke(
        [
            SystemMessage(content=RECOMMENDATION_INTAKE_SYSTEM_PROMPT),
            HumanMessage(
                content=_json_dumps(
                    {
                        "user_message": state["message"],
                        "recommendation_context": recommendation_context,
                    }
                )
            ),
        ]
    )
    intake_payload = _json_ready(_model_dump(intake))
    missing_fields = intake_payload.get("missing_fields") or _recommendation_missing_fields(recommendation_context)
    next_field = intake_payload.get("next_field")
    if next_field not in RECOMMENDATION_REQUIRED_FIELDS:
        next_field = missing_fields[0]

    message = intake_payload.get("next_question") or "I need one more detail before I can recommend a shortlist."
    tool_payload = {
        "kind": "recommendation_intake",
        "code": "recommendation_intake",
        "message": message,
        "next_question": message,
        "next_field": next_field,
        "missing_fields": missing_fields,
        "options": _recommendation_options(next_field),
        "recommendation_context": _recommendation_context_payload(recommendation_context, pending=True),
        "extraction": extraction_data,
    }
    return {
        "tool_used": "recommendation_intake",
        "tool_payload": tool_payload,
        "conversation_state_out": {
            "recommendation_context": _recommendation_context_payload(recommendation_context, pending=True)
        },
    }


def _select_diverse_recommendations(
    candidate_set: RecommendationCandidateSet,
    plan_choices: List[RecommendationPlanChoice],
) -> List[Dict[str, Any]]:
    candidate_lookup = {candidate.plan_id: candidate.to_dict() for candidate in candidate_set.candidates}
    selected: List[Dict[str, Any]] = []
    seen_plan_ids = set()
    seen_insurers = set()

    def _append_candidate(candidate: Dict[str, Any], rationale: str, *, allow_duplicate_insurer: bool) -> bool:
        plan_id = candidate["plan_id"]
        insurer = candidate["insurer_name"] or candidate["display_name"]
        if plan_id in seen_plan_ids:
            return False
        if (not allow_duplicate_insurer) and insurer in seen_insurers:
            return False
        selected.append({**candidate, "rationale": rationale})
        seen_plan_ids.add(plan_id)
        seen_insurers.add(insurer)
        return True

    for choice in plan_choices:
        candidate = candidate_lookup.get(choice.plan_id)
        if candidate is None:
            continue
        _append_candidate(candidate, choice.rationale, allow_duplicate_insurer=False)
        if len(selected) == 3:
            return selected

    for candidate in candidate_set.candidates:
        _append_candidate(
            candidate.to_dict(),
            "This plan scored strongly on tier fit, affordability, and coverage tradeoffs for your stated preferences.",
            allow_duplicate_insurer=False,
        )
        if len(selected) == 3:
            return selected

    for choice in plan_choices:
        candidate = candidate_lookup.get(choice.plan_id)
        if candidate is None:
            continue
        _append_candidate(candidate, choice.rationale, allow_duplicate_insurer=True)
        if len(selected) == 3:
            return selected

    for candidate in candidate_set.candidates:
        _append_candidate(
            candidate.to_dict(),
            "This plan remains a strong fallback option within the deterministic shortlist.",
            allow_duplicate_insurer=True,
        )
        if len(selected) == 3:
            break

    return selected


def _recommendation_reasoner_node(state: ChatState) -> ChatState:
    extraction_data = _json_ready(state["extraction"])
    recommendation_context = RecommendationContextModel(**state["recommendation_context"])
    candidate_set = build_recommendation_candidates(
        age=recommendation_context.age,
        budget_preference=recommendation_context.budget_preference,
        ward_preference=recommendation_context.ward_preference,
        coverage_style=recommendation_context.coverage_style,
    )

    candidates_for_llm = [candidate.to_dict() for candidate in candidate_set.candidates[:8]]
    decision = _recommendation_reasoner_model().invoke(
        [
            SystemMessage(content=RECOMMENDATION_REASONER_SYSTEM_PROMPT),
            HumanMessage(
                content=_json_dumps(
                    {
                        "user_message": state["message"],
                        "recommendation_context": recommendation_context.model_dump(),
                        "decision_factors": candidate_set.decision_factors,
                        "candidates": candidates_for_llm,
                    }
                )
            ),
        ]
    )

    structured_decision = _json_ready(_model_dump(decision))
    selected_recommendations = _select_diverse_recommendations(
        candidate_set,
        decision.plan_choices,
    )
    if not selected_recommendations:
        raise ToolExecutionError(
            "recommendation_not_available",
            "I couldn't build a recommendation shortlist from the available plan data.",
            {"age": recommendation_context.age},
        )

    for index, recommendation in enumerate(selected_recommendations, start=1):
        recommendation["rank"] = index

    tool_payload = {
        "kind": "recommendation",
        "message": structured_decision.get("summary") or "Here are three grounded plan options to consider.",
        "recommended_tier": structured_decision.get("recommended_tier") or selected_recommendations[0]["tier_code"],
        "recommendations": selected_recommendations,
        "decision_factors": structured_decision.get("decision_factors") or candidate_set.decision_factors,
        "disclaimer": structured_decision.get("disclaimer") or RECOMMENDATION_DEFAULT_DISCLAIMER,
        "recommendation_context": _recommendation_context_payload(
            recommendation_context.model_dump(exclude_none=True),
            pending=False,
        ),
        "extraction": extraction_data,
    }
    return {
        "tool_used": "recommendation_reasoner",
        "tool_payload": tool_payload,
        "conversation_state_out": {"recommendation_context": _recommendation_context_payload(
            recommendation_context.model_dump(exclude_none=True),
            pending=False,
        )},
    }


def _synthesize_node(state: ChatState) -> ChatState:
    tool_payload = state["tool_payload"]
    kind = tool_payload.get("kind")
    if kind in {"unsupported", "error", "recommendation_intake", "recommendation"}:
        return {"response": tool_payload.get("message", "")}

    synthesis_input = {
        "user_message": state["message"],
        "tool_used": state.get("tool_used"),
        "tool_payload": tool_payload,
    }
    response = _chat_model().invoke(
        [
            SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
            HumanMessage(content=_json_dumps(synthesis_input)),
        ]
    )
    return {"response": response.content}


@lru_cache(maxsize=1)
def _chat_graph():
    workflow: StateGraph = StateGraph(ChatState)
    workflow.add_node("extract", _extract_node)
    workflow.add_node("tool", _tool_node)
    workflow.add_node("recommendation_intake", _recommendation_intake_node)
    workflow.add_node("recommendation_reasoner", _recommendation_reasoner_node)
    workflow.add_node("synthesize", _synthesize_node)
    workflow.add_edge(START, "extract")
    workflow.add_conditional_edges(
        "extract",
        _route_after_extract,
        {
            "tool": "tool",
            "recommendation_intake": "recommendation_intake",
            "recommendation_reasoner": "recommendation_reasoner",
        },
    )
    workflow.add_edge("tool", "synthesize")
    workflow.add_edge("recommendation_intake", "synthesize")
    workflow.add_edge("recommendation_reasoner", "synthesize")
    workflow.add_edge("synthesize", END)
    return workflow.compile()


app = FastAPI(title="Singapore Health Policy Navigator")


@app.on_event("startup")
def _startup_validation() -> None:
    get_master_data_store()
    _openai_api_key()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=_openai_model(),
        master_data=_master_data_status(),
    )


@app.post("/premium/quote", response_model=PremiumQuoteResponse)
def premium_quote(request: PremiumQuoteRequest) -> PremiumQuoteResponse:
    try:
        payload = _run_premium_lookup(
            age=request.age,
            insurer=request.insurer,
            tier=request.tier,
            plan_name=request.plan_name,
        )
    except ToolExecutionError as error:
        return PremiumQuoteResponse(
            response=error.message,
            error=_error_payload(error.code, error.message, error.details),
        )
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - runtime safety for API layer
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {error}") from error

    return PremiumQuoteResponse(
        response=_format_premium_response(payload),
        plan_resolution=payload["plan_resolution"],
        cpf_limit=payload["cpf_limit"],
        premium_result=payload["premium_result"],
        error=None,
    )


@app.post("/benefit/search", response_model=BenefitSearchResponse)
def benefit_search(request: BenefitSearchRequest) -> BenefitSearchResponse:
    try:
        payload = _run_benefit_lookup(
            benefit_keyword=request.benefit_keyword,
            insurer=request.insurer,
            tier=request.tier,
            plan_name=request.plan_name,
        )
    except ToolExecutionError as error:
        return BenefitSearchResponse(
            response=error.message,
            error=_error_payload(error.code, error.message, error.details),
        )
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - runtime safety for API layer
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {error}") from error

    return BenefitSearchResponse(
        response=_format_benefit_response(payload),
        plan_resolution=payload["plan_resolution"],
        benefit_result=payload["benefit_result"],
        error=None,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        state = _chat_graph().invoke(
            {
                "message": request.message,
                "conversation_state": request.conversation_state or {},
            }
        )
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - runtime safety for API layer
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {error}") from error

    return ChatResponse(
        response=state["response"],
        tool_used=state.get("tool_used"),
        extracted_data={
            "extraction": state.get("extraction", {}),
            "result": _json_ready(state.get("tool_payload", {})),
            "conversation_state": _json_ready(state.get("conversation_state_out", {})),
        },
    )
