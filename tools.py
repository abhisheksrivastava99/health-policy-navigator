from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple

from data_loader import (
    clean_scalar,
    clean_text,
    get_master_data_store,
    normalize_key,
    text_tokens,
)

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback for environments without rapidfuzz
    from difflib import SequenceMatcher

    class _FuzzFallback:
        @staticmethod
        def token_set_ratio(left: str, right: str) -> float:
            return SequenceMatcher(None, left, right).ratio() * 100

    fuzz = _FuzzFallback()


INSURER_ALIAS_TO_CANONICAL = {
    "income": "income",
    "ntuc": "income",
    "ntuc income": "income",
    "aia": "aia",
    "ge": "great eastern",
    "great eastern": "great eastern",
    "pru": "prudential",
    "prudential": "prudential",
    "singlife": "singlife",
    "hsbc": "hsbc life",
    "hsbc life": "hsbc life",
    "raffles": "raffles health insurance",
    "raffles health insurance": "raffles health insurance",
}

TIER_ALIAS_TO_CODE = {
    "basic": "basic",
    "plan c": "basic",
    "c": "basic",
    "standard": "standard",
    "std": "standard",
    "b1": "class_b1",
    "class b1": "class_b1",
    "class_b1": "class_b1",
    "a": "class_a",
    "class a": "class_a",
    "class_a": "class_a",
    "private": "private",
    "private hospital": "private",
    "private hospital plan": "private",
}

TIER_CORE_TOKENS = {
    "basic": {"c", "plan c"},
    "standard": {"standard"},
    "class_b1": {"b", "plan b"},
    "class_a": {"a", "plan a"},
    "private": {"p", "plan p", "premier"},
}

BENEFIT_SYNONYMS = {
    "mental health": "psychiatric",
    "psych": "psychiatric",
    "psychiatry": "psychiatric",
    "icu": "intensive care unit",
    "ward": "normal ward",
    "room": "normal ward",
}

STANDARD_BASELINE_PLAN_ID = "standard__standard_ip"
MEDISHIELD_LIFE_PLAN_ID = "basic__medishield_life"

RecommendationBudgetPreference = Literal["low_cost", "balanced", "coverage_flexible"]
RecommendationWardPreference = Literal["basic", "standard", "class_b1", "class_a", "private", "unsure"]
RecommendationCoverageStyle = Literal["lowest_cost", "balanced", "strongest_coverage"]

RECOMMENDATION_WEIGHT_MAP: Dict[RecommendationBudgetPreference, Dict[str, float]] = {
    "low_cost": {"affordability": 0.50, "tier": 0.35, "coverage": 0.15},
    "balanced": {"affordability": 0.30, "tier": 0.45, "coverage": 0.25},
    "coverage_flexible": {"affordability": 0.15, "tier": 0.35, "coverage": 0.50},
}

TIER_LEVEL_MAP = {
    "basic": 1,
    "standard": 2,
    "class_b1": 3,
    "class_a": 4,
    "private": 5,
}

WARD_PREFERENCE_DEFAULT_LEVELS = {
    "basic": [1],
    "standard": [2],
    "class_b1": [3],
    "class_a": [4],
    "private": [5],
    "unsure": [2, 3],
}


class ToolExecutionError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class PlanResolutionResult:
    requested_plan_id: str
    effective_plan_id: str
    requested_display_name: str
    effective_display_name: str
    tier_code: str
    tier_slug: str
    insurer_name: str
    product_name: str
    capability: str
    match_reason: str
    used_fallback: bool
    fallback_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CPFWithdrawalLimitResult:
    age: int
    age_start: int
    age_end: int
    max_withdrawal_limit: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PremiumCalculationResult:
    plan_id: str
    age: int
    age_band_raw: str
    premium_available: bool
    premium_shape: str
    premium_total_raw: str
    premium_total_min: Optional[float]
    premium_total_max: Optional[float]
    premium_excl_mshl_raw: str
    premium_excl_mshl_min: Optional[float]
    premium_excl_mshl_max: Optional[float]
    annual_change_raw: str
    annual_change_min_pct: Optional[float]
    annual_change_max_pct: Optional[float]
    cpf_limit: int
    medisave_payable_min: Optional[float]
    medisave_payable_max: Optional[float]
    cash_payable_min: Optional[float]
    cash_payable_max: Optional[float]
    availability_note: str
    source_kind: str
    source_pdf: str
    source_page: int
    source_table: int
    source_slug: str
    repair_flags: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenefitMatchResult:
    plan_id: str
    section_raw: str
    benefit_raw: str
    notes_raw: str
    coverage_value_raw: str
    match_reason: str
    match_score: float
    source_pdf: str
    source_page: int
    source_table: int
    source_slug: str
    repair_flags: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenefitLookupResult:
    plan_id: str
    keyword: str
    normalized_keyword: str
    expanded_terms: List[str]
    best_match: BenefitMatchResult
    top_matches: List[BenefitMatchResult]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["best_match"] = self.best_match.to_dict()
        payload["top_matches"] = [match.to_dict() for match in self.top_matches]
        return payload


@dataclass(frozen=True)
class RecommendationCandidateResult:
    plan_id: str
    display_name: str
    insurer_name: str
    tier_code: str
    age: int
    age_band_raw: str
    premium_total_min: float
    premium_total_max: float
    annual_premium_display: str
    monthly_premium_display: str
    representative_annual_premium: float
    cash_payable_min: Optional[float]
    cash_payable_max: Optional[float]
    cash_payable_display: str
    source_pdf: str
    source_page: int
    source_table: int
    tier_fit: float
    affordability_fit: float
    coverage_fit: float
    heuristic_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecommendationCandidateSet:
    age: int
    budget_preference: RecommendationBudgetPreference
    ward_preference: RecommendationWardPreference
    coverage_style: RecommendationCoverageStyle
    decision_factors: List[str]
    candidates: List[RecommendationCandidateResult]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return payload


def _canonical_insurer(value: Optional[str]) -> str:
    normalized = normalize_key(value)
    return INSURER_ALIAS_TO_CANONICAL.get(normalized, normalized)


def _canonical_tier(*values: Optional[str]) -> Optional[str]:
    for value in values:
        normalized = normalize_key(value)
        if normalized in TIER_ALIAS_TO_CODE:
            return TIER_ALIAS_TO_CODE[normalized]
    return None


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


def _monthly_currency_span(min_value: Optional[float], max_value: Optional[float]) -> str:
    if min_value is None or max_value is None:
        return "N/A"
    return _currency_span(min_value / 12.0, max_value / 12.0)


def _candidate_records(capability: str) -> List[Dict[str, Any]]:
    store = get_master_data_store()
    if capability == "premium":
        return [row for row in store.plan_rows if bool(row.get("has_premium_data"))]
    if capability == "benefit":
        return [
            row
            for row in store.plan_rows
            if bool(row.get("has_benefits")) or clean_text(row.get("tier_code")) == "standard"
        ]
    raise ToolExecutionError("invalid_capability", f"Unsupported capability: {capability}")


def _core_tier_match(row: Dict[str, Any], tier_code: str) -> bool:
    product_tokens = text_tokens(row.get("product_name"))
    core_tokens = TIER_CORE_TOKENS.get(tier_code, set())
    return any(token in product_tokens for token in core_tokens)


def _plan_aliases(row: Dict[str, Any]) -> Set[str]:
    aliases = text_tokens(
        row.get("display_name"),
        row.get("product_name"),
        f"{clean_text(row.get('insurer_name'))} {clean_text(row.get('product_name'))}",
    )
    tier_code = clean_text(row.get("tier_code"))
    if tier_code == "basic":
        aliases.add("plan c")
    elif tier_code == "class_b1":
        aliases.add("plan b")
    elif tier_code == "class_a":
        aliases.add("plan a")
    elif tier_code == "private":
        aliases.add("plan p")
    elif tier_code == "standard":
        aliases.update({"standard", "standard plan", "standard ip"})
    return aliases


def _score_plan_candidate(row: Dict[str, Any], plan_name: str) -> Tuple[int, float]:
    plan_name_norm = normalize_key(plan_name)
    if not plan_name_norm:
        return 0, 0.0

    aliases = _plan_aliases(row)
    display_name = normalize_key(row.get("display_name"))
    product_name = normalize_key(row.get("product_name"))
    searchable = " ".join({alias for alias in aliases if alias})

    if plan_name_norm in {display_name, product_name}:
        return 400, 100.0
    if plan_name_norm in aliases:
        return 360, 100.0
    if plan_name_norm in searchable:
        return 280, 95.0

    plan_tokens = set(plan_name_norm.split())
    if plan_tokens and plan_tokens.issubset(text_tokens(display_name, product_name)):
        return 240, 92.0

    fuzzy_score = max(
        fuzz.token_set_ratio(plan_name_norm, display_name),
        fuzz.token_set_ratio(plan_name_norm, product_name),
    )
    if fuzzy_score >= 70:
        return 120, float(fuzzy_score)
    return 0, float(fuzzy_score)


def resolve_plan(
    insurer: Optional[str],
    tier: Optional[str],
    plan_name: Optional[str],
    capability: str,
) -> PlanResolutionResult:
    store = get_master_data_store()
    candidates = _candidate_records(capability)

    insurer_norm = _canonical_insurer(insurer)
    tier_code = _canonical_tier(tier, plan_name)
    plan_name_norm = normalize_key(plan_name)

    if tier_code:
        tier_filtered = [
            row for row in candidates if clean_text(row.get("tier_code")) == tier_code
        ]
        if not tier_filtered:
            raise ToolExecutionError(
                "tier_not_found",
                f"No plans found for tier '{tier}'.",
                {"tier": tier, "capability": capability},
            )
        candidates = tier_filtered

    if insurer_norm:
        strict_insurer = [
            row
            for row in candidates
            if normalize_key(row.get("insurer_name")) == insurer_norm
        ]
        if strict_insurer:
            candidates = strict_insurer
        else:
            soft_insurer = [
                row
                for row in candidates
                if insurer_norm in text_tokens(row.get("insurer_name"), row.get("display_name"))
            ]
            if soft_insurer:
                candidates = soft_insurer
            else:
                raise ToolExecutionError(
                    "insurer_not_found",
                    f"No plans found for insurer '{insurer}'.",
                    {"insurer": insurer, "capability": capability, "tier": tier_code},
                )

    if not candidates:
        raise ToolExecutionError(
            "plan_not_found",
            "No candidate plans matched the provided criteria.",
            {"insurer": insurer, "tier": tier, "plan_name": plan_name, "capability": capability},
        )

    selected: Optional[Dict[str, Any]] = None
    match_reason = "unique_filter_match"

    if plan_name_norm:
        scored = sorted(
            [
                (_score_plan_candidate(row, plan_name_norm), clean_text(row.get("display_name")), row)
                for row in candidates
            ],
            key=lambda item: (item[0][0], item[0][1], item[1]),
            reverse=True,
        )
        best_score, _, best_row = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else (-1, -1.0)
        if best_score[0] == 0:
            raise ToolExecutionError(
                "plan_not_found",
                f"Unable to match plan name '{plan_name}'.",
                {"insurer": insurer, "tier": tier_code, "plan_name": plan_name},
            )
        if len(scored) > 1 and best_score == second_score:
            raise ToolExecutionError(
                "ambiguous_plan",
                f"Multiple plans matched '{plan_name}'.",
                {
                    "plan_name": plan_name,
                    "candidates": [clean_text(item[2].get("display_name")) for item in scored[:3]],
                },
            )
        selected = best_row
        match_reason = "plan_name_match"
    elif len(candidates) == 1:
        selected = candidates[0]
    elif capability == "benefit" and tier_code == "standard" and not insurer_norm:
        selected = store.plan_by_id[STANDARD_BASELINE_PLAN_ID]
        match_reason = "shared_standard_benefit_default"
    else:
        core_matches = [
            row for row in candidates if tier_code and _core_tier_match(row, tier_code)
        ]
        if len(core_matches) == 1:
            selected = core_matches[0]
            match_reason = "core_tier_product_default"

    if selected is None:
        raise ToolExecutionError(
            "ambiguous_plan",
            "Multiple plans matched; please specify the plan name more clearly.",
            {
                "insurer": insurer,
                "tier": tier_code,
                "capability": capability,
                "candidates": [clean_text(row.get("display_name")) for row in candidates[:5]],
            },
        )

    requested_plan_id = clean_text(selected.get("plan_id"))
    effective_plan_id = requested_plan_id
    used_fallback = False
    fallback_reason = ""

    if (
        capability == "benefit"
        and clean_text(selected.get("tier_code")) == "standard"
        and not bool(selected.get("has_benefits"))
    ):
        effective_plan_id = STANDARD_BASELINE_PLAN_ID
        used_fallback = True
        fallback_reason = (
            "Standard-tier insurer plans share the Standard IP benefit schedule, so benefit "
            "lookups use the baseline Standard IP rows."
        )

    effective_plan = store.plan_by_id[effective_plan_id]
    return PlanResolutionResult(
        requested_plan_id=requested_plan_id,
        effective_plan_id=effective_plan_id,
        requested_display_name=clean_text(selected.get("display_name")),
        effective_display_name=clean_text(effective_plan.get("display_name")),
        tier_code=clean_text(selected.get("tier_code")),
        tier_slug=clean_text(selected.get("tier_slug")),
        insurer_name=clean_text(selected.get("insurer_name")),
        product_name=clean_text(selected.get("product_name")),
        capability=capability,
        match_reason=match_reason,
        used_fallback=used_fallback,
        fallback_reason=fallback_reason,
    )


def lookup_cpf_limit(age: int) -> CPFWithdrawalLimitResult:
    store = get_master_data_store()
    if age < 1 or age > 120:
        raise ToolExecutionError(
            "age_out_of_range",
            "Age must be between 1 and 120.",
            {"age": age},
        )

    for row in store.cpf_limits_sorted:
        age_start = int(row["age_start"])
        age_end = int(row["age_end"])
        if age_start <= age <= age_end:
            return CPFWithdrawalLimitResult(
                age=age,
                age_start=age_start,
                age_end=age_end,
                max_withdrawal_limit=int(row["max_withdrawal_limit"]),
            )

    raise ToolExecutionError(
        "cpf_limit_not_found",
        f"No CPF withdrawal limit found for age {age}.",
        {"age": age},
    )


def calculate_premium(age: int, plan_id: str) -> PremiumCalculationResult:
    store = get_master_data_store()
    plan = store.plan_by_id.get(plan_id)
    if plan is None:
        raise ToolExecutionError(
            "plan_not_found",
            f"Unknown plan_id '{plan_id}'.",
            {"plan_id": plan_id},
        )

    if not bool(plan.get("has_premium_data")):
        raise ToolExecutionError(
            "premium_not_available",
            f"Plan '{plan_id}' does not have premium data.",
            {"plan_id": plan_id},
        )

    cpf_result = lookup_cpf_limit(age)
    premium_rows = [
        row for row in store.premium_rows if clean_text(row.get("plan_id")) == plan_id
    ]
    matched_row: Optional[Dict[str, Any]] = None
    for row in premium_rows:
        age_start = int(row["age_start"])
        age_end = clean_scalar(row.get("age_end"))
        age_open_ended = bool(row.get("age_open_ended"))
        if age_open_ended and age >= age_start:
            matched_row = row
            break
        if age_end is not None and age_start <= age <= int(age_end):
            matched_row = row
            break

    if matched_row is None:
        raise ToolExecutionError(
            "premium_band_not_found",
            f"No premium band found for age {age}.",
            {"plan_id": plan_id, "age": age},
        )

    premium_available = bool(matched_row.get("premium_available"))
    premium_total_min = clean_scalar(matched_row.get("premium_total_min"))
    premium_total_max = clean_scalar(matched_row.get("premium_total_max"))
    premium_excl_min = clean_scalar(matched_row.get("premium_excl_mshl_min"))
    premium_excl_max = clean_scalar(matched_row.get("premium_excl_mshl_max"))
    annual_change_min = clean_scalar(matched_row.get("annual_change_min_pct"))
    annual_change_max = clean_scalar(matched_row.get("annual_change_max_pct"))

    medisave_payable_min: Optional[float] = None
    medisave_payable_max: Optional[float] = None
    cash_payable_min: Optional[float] = None
    cash_payable_max: Optional[float] = None
    premium_shape = "unavailable"

    if premium_available and premium_total_min is not None and premium_total_max is not None:
        premium_shape = "scalar" if premium_total_min == premium_total_max else "range"
        medisave_payable_min = min(float(premium_total_min), cpf_result.max_withdrawal_limit)
        medisave_payable_max = min(float(premium_total_max), cpf_result.max_withdrawal_limit)
        cash_payable_min = float(premium_total_min) - medisave_payable_min
        cash_payable_max = float(premium_total_max) - medisave_payable_max

    return PremiumCalculationResult(
        plan_id=plan_id,
        age=age,
        age_band_raw=clean_text(matched_row.get("age_band_raw")),
        premium_available=premium_available,
        premium_shape=premium_shape,
        premium_total_raw=clean_text(matched_row.get("premium_total_raw")),
        premium_total_min=clean_scalar(premium_total_min),
        premium_total_max=clean_scalar(premium_total_max),
        premium_excl_mshl_raw=clean_text(matched_row.get("premium_excl_mshl_raw")),
        premium_excl_mshl_min=clean_scalar(premium_excl_min),
        premium_excl_mshl_max=clean_scalar(premium_excl_max),
        annual_change_raw=clean_text(matched_row.get("annual_change_raw")),
        annual_change_min_pct=clean_scalar(annual_change_min),
        annual_change_max_pct=clean_scalar(annual_change_max),
        cpf_limit=cpf_result.max_withdrawal_limit,
        medisave_payable_min=clean_scalar(medisave_payable_min),
        medisave_payable_max=clean_scalar(medisave_payable_max),
        cash_payable_min=clean_scalar(cash_payable_min),
        cash_payable_max=clean_scalar(cash_payable_max),
        availability_note=clean_text(matched_row.get("availability_note")),
        source_kind=clean_text(matched_row.get("source_kind")),
        source_pdf=clean_text(matched_row.get("source_pdf")),
        source_page=int(matched_row["source_page"]),
        source_table=int(matched_row["source_table"]),
        source_slug=clean_text(matched_row.get("source_slug")),
        repair_flags=clean_text(matched_row.get("repair_flags")),
    )


def _expand_benefit_terms(keyword: str) -> List[str]:
    normalized = normalize_key(keyword)
    expanded_terms: Set[str] = {normalized} if normalized else set()

    for alias, canonical in BENEFIT_SYNONYMS.items():
        alias_norm = normalize_key(alias)
        canonical_norm = normalize_key(canonical)
        if alias_norm == normalized or alias_norm in normalized:
            expanded_terms.add(canonical_norm)
        if canonical_norm == normalized or canonical_norm in normalized:
            expanded_terms.add(canonical_norm)

    return sorted(term for term in expanded_terms if term)


def lookup_benefit(plan_id: str, keyword: str) -> BenefitLookupResult:
    store = get_master_data_store()
    if plan_id not in store.plan_by_id:
        raise ToolExecutionError(
            "plan_not_found",
            f"Unknown plan_id '{plan_id}'.",
            {"plan_id": plan_id},
        )

    keyword_norm = normalize_key(keyword)
    if not keyword_norm:
        raise ToolExecutionError(
            "missing_benefit_keyword",
            "A benefit keyword is required for benefit lookup.",
            {"keyword": keyword},
        )

    expanded_terms = _expand_benefit_terms(keyword_norm)
    candidate_rows = [
        row
        for row in store.benefit_rows
        if clean_text(row.get("plan_id")) == plan_id and not bool(row.get("is_blank_value"))
    ]

    scored_matches: List[Tuple[Tuple[int, int, int, float, float], BenefitMatchResult]] = []
    for row in candidate_rows:
        benefit_norm = normalize_key(row.get("benefit_norm") or row.get("benefit_raw"))
        search_text_norm = normalize_key(row.get("search_text_norm"))

        exact_match = int(any(term == benefit_norm for term in expanded_terms))
        benefit_contains = int(any(term and term in benefit_norm for term in expanded_terms))
        search_contains = int(any(term and term in search_text_norm for term in expanded_terms))
        fuzzy_score = max(
            [fuzz.token_set_ratio(keyword_norm, benefit_norm)]
            + [fuzz.token_set_ratio(term, benefit_norm) for term in expanded_terms]
        )

        if not (exact_match or benefit_contains or search_contains or fuzzy_score >= 45):
            continue

        if exact_match:
            match_reason = "exact_benefit_match"
        elif benefit_contains:
            match_reason = "benefit_contains_keyword"
        elif search_contains:
            match_reason = "search_text_contains_keyword"
        else:
            match_reason = "fuzzy_match"

        match = BenefitMatchResult(
            plan_id=plan_id,
            section_raw=clean_text(row.get("section_raw")),
            benefit_raw=clean_text(row.get("benefit_raw")),
            notes_raw=clean_text(row.get("notes_raw")),
            coverage_value_raw=clean_text(row.get("coverage_value_raw")),
            match_reason=match_reason,
            match_score=float(fuzzy_score),
            source_pdf=clean_text(row.get("source_pdf")),
            source_page=int(row["source_page"]),
            source_table=int(row["source_table"]),
            source_slug=clean_text(row.get("source_slug")),
            repair_flags=clean_text(row.get("repair_flags")),
        )
        tie_breaker = -len(clean_text(row.get("benefit_raw")))
        scored_matches.append(
            ((exact_match, benefit_contains, search_contains, float(fuzzy_score), tie_breaker), match)
        )

    if not scored_matches:
        raise ToolExecutionError(
            "benefit_not_found",
            f"No benefit match found for keyword '{keyword}'.",
            {"plan_id": plan_id, "keyword": keyword},
        )

    scored_matches.sort(key=lambda item: item[0], reverse=True)
    top_matches = [match for _, match in scored_matches[:3]]
    return BenefitLookupResult(
        plan_id=plan_id,
        keyword=keyword,
        normalized_keyword=keyword_norm,
        expanded_terms=expanded_terms,
        best_match=top_matches[0],
        top_matches=top_matches,
    )


def _tier_fit_score(tier_code: str, ward_preference: RecommendationWardPreference) -> float:
    tier_level = TIER_LEVEL_MAP[tier_code]
    preferred_levels = WARD_PREFERENCE_DEFAULT_LEVELS[ward_preference]
    distances = [abs(tier_level - level) for level in preferred_levels]
    nearest_distance = min(distances)
    return max(0.0, 1.0 - (nearest_distance / 4.0))


def _affordability_scores(representative_costs: List[float]) -> Dict[float, float]:
    if not representative_costs:
        return {}
    min_cost = min(representative_costs)
    max_cost = max(representative_costs)
    if min_cost == max_cost:
        return {cost: 1.0 for cost in representative_costs}
    return {
        cost: max(0.0, min(1.0, 1.0 - ((cost - min_cost) / (max_cost - min_cost))))
        for cost in representative_costs
    }


def _coverage_fit_score(
    tier_code: str,
    ward_preference: RecommendationWardPreference,
    coverage_style: RecommendationCoverageStyle,
) -> float:
    tier_level = TIER_LEVEL_MAP[tier_code]
    preferred_levels = WARD_PREFERENCE_DEFAULT_LEVELS[ward_preference]
    nearest_preference = min(preferred_levels, key=lambda level: abs(level - tier_level))
    distance = abs(tier_level - nearest_preference)

    if coverage_style == "lowest_cost":
        if tier_level <= nearest_preference:
            return max(0.35, 1.0 - (distance / 4.0))
        return max(0.0, 0.7 - (distance * 0.2))

    if coverage_style == "strongest_coverage":
        if tier_level >= nearest_preference:
            overshoot = tier_level - nearest_preference
            return max(0.45, 1.0 - (overshoot * 0.12))
        return max(0.0, 0.65 - (distance * 0.22))

    return max(0.0, 1.0 - (distance / 3.5))


def _recommendation_decision_factors(
    budget_preference: RecommendationBudgetPreference,
    ward_preference: RecommendationWardPreference,
    coverage_style: RecommendationCoverageStyle,
) -> List[str]:
    ward_copy = {
        "basic": "You prefer basic / Plan C style coverage.",
        "standard": "You prefer Standard-tier coverage.",
        "class_b1": "You prefer Class B1 level coverage.",
        "class_a": "You prefer Class A level coverage.",
        "private": "You prefer private hospital coverage.",
        "unsure": "You are open to a balanced middle tier, so the ranking leans toward Standard and Class B1 plans.",
    }[ward_preference]
    budget_copy = {
        "low_cost": "The ranking gives strong weight to affordability and lower annual premiums.",
        "balanced": "The ranking balances affordability with fit to your preferred hospitalization tier.",
        "coverage_flexible": "The ranking allows higher premiums when the plan offers stronger coverage fit.",
    }[budget_preference]
    style_copy = {
        "lowest_cost": "Lower-cost options are favored when coverage differences are modest.",
        "balanced": "The ranking prefers plans that balance stronger coverage with manageable cost.",
        "strongest_coverage": "Higher-coverage options are favored when they remain a reasonable fit for your preferred tier.",
    }[coverage_style]
    return [budget_copy, ward_copy, style_copy]


def build_recommendation_candidates(
    *,
    age: int,
    budget_preference: RecommendationBudgetPreference,
    ward_preference: RecommendationWardPreference,
    coverage_style: RecommendationCoverageStyle,
) -> RecommendationCandidateSet:
    store = get_master_data_store()
    cpf_result = lookup_cpf_limit(age)

    raw_candidates: List[Tuple[Dict[str, Any], PremiumCalculationResult]] = []
    for row in store.plan_rows:
        plan_id = clean_text(row.get("plan_id"))
        tier_code = clean_text(row.get("tier_code"))
        if plan_id == MEDISHIELD_LIFE_PLAN_ID:
            continue
        if not bool(row.get("has_premium_data")):
            continue
        if tier_code not in TIER_LEVEL_MAP:
            continue

        try:
            premium_result = calculate_premium(age=age, plan_id=plan_id)
        except ToolExecutionError:
            continue

        if (
            not premium_result.premium_available
            or premium_result.premium_total_min is None
            or premium_result.premium_total_max is None
        ):
            continue
        raw_candidates.append((row, premium_result))

    if not raw_candidates:
        raise ToolExecutionError(
            "recommendation_candidates_not_found",
            f"No recommendation candidates were available for age {age}.",
            {"age": age},
        )

    representative_costs = [
        float((premium_result.premium_total_min + premium_result.premium_total_max) / 2.0)
        for _, premium_result in raw_candidates
    ]
    affordability_lookup = _affordability_scores(representative_costs)
    weights = RECOMMENDATION_WEIGHT_MAP[budget_preference]

    candidates: List[RecommendationCandidateResult] = []
    for row, premium_result in raw_candidates:
        representative_cost = float(
            (premium_result.premium_total_min + premium_result.premium_total_max) / 2.0
        )
        tier_code = clean_text(row.get("tier_code"))
        tier_fit = _tier_fit_score(tier_code, ward_preference)
        affordability_fit = affordability_lookup[representative_cost]
        coverage_fit = _coverage_fit_score(tier_code, ward_preference, coverage_style)
        heuristic_score = (
            (tier_fit * weights["tier"])
            + (affordability_fit * weights["affordability"])
            + (coverage_fit * weights["coverage"])
        )

        candidates.append(
            RecommendationCandidateResult(
                plan_id=clean_text(row.get("plan_id")),
                display_name=clean_text(row.get("display_name")),
                insurer_name=clean_text(row.get("insurer_name")),
                tier_code=tier_code,
                age=age,
                age_band_raw=premium_result.age_band_raw,
                premium_total_min=float(premium_result.premium_total_min),
                premium_total_max=float(premium_result.premium_total_max),
                annual_premium_display=_currency_span(
                    premium_result.premium_total_min,
                    premium_result.premium_total_max,
                ),
                monthly_premium_display=_monthly_currency_span(
                    premium_result.premium_total_min,
                    premium_result.premium_total_max,
                ),
                representative_annual_premium=representative_cost,
                cash_payable_min=premium_result.cash_payable_min,
                cash_payable_max=premium_result.cash_payable_max,
                cash_payable_display=_currency_span(
                    premium_result.cash_payable_min,
                    premium_result.cash_payable_max,
                ),
                source_pdf=premium_result.source_pdf,
                source_page=premium_result.source_page,
                source_table=premium_result.source_table,
                tier_fit=round(tier_fit, 4),
                affordability_fit=round(affordability_fit, 4),
                coverage_fit=round(coverage_fit, 4),
                heuristic_score=round(heuristic_score, 4),
            )
        )

    candidates.sort(
        key=lambda candidate: (
            candidate.heuristic_score,
            candidate.tier_fit,
            candidate.coverage_fit,
            -candidate.representative_annual_premium,
            candidate.display_name,
        ),
        reverse=True,
    )

    return RecommendationCandidateSet(
        age=age,
        budget_preference=budget_preference,
        ward_preference=ward_preference,
        coverage_style=coverage_style,
        decision_factors=_recommendation_decision_factors(
            budget_preference,
            ward_preference,
            coverage_style,
        ),
        candidates=candidates,
    )


def result_to_dict(result: Any) -> Dict[str, Any]:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if isinstance(result, dict):
        return result
    raise TypeError(f"Unsupported result type: {type(result)}")
