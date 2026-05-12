# Demo Questions

This file lists the main kinds of questions the **Chat** experience can answer today in the Singapore Health Policy Navigator.

## What Chat Can Answer

Chat currently supports three broad question types:

1. **Premium questions**
   - Age-based premium lookup
   - CPF withdrawal limit context
   - Cash-payable estimate
   - Plan matching from insurer, tier, or plan name hints

2. **Benefit questions**
   - Exact benefit or coverage lookup from source-backed tables
   - Coverage questions for items like ICU, psychiatric care, ward, cancer, and similar benefit rows
   - Standard-plan fallback where insurer-branded Standard plans share the baseline Standard schedule

3. **Recommendation questions**
   - Guided “what should I buy?” style questions
   - Multi-turn follow-up in chat for:
     - age
     - budget preference
     - ward preference
     - coverage style
   - Final top-3 shortlist with rationale, premium context, and disclaimer

## Premium Question Demos

- I am 45, how much cash do I pay for Prudential Class A?
- What is the premium for Singlife Shield Plan 1 if I am 62?
- If I am 26, what is the annual premium for Great Eastern private hospital coverage?
- What is the cash payable for Income private hospital coverage at age 38?
- At age 70, what does Prudential Class A cost?
- I am 52. Show me the premium for AIA Class B1.
- How much is the premium for Standard IP if I am 31?
- If I am 41, what is the CPF withdrawal limit used for my premium calculation?
- Compare the premium band result for Prudential Class A at age 40.
- What premium range applies to Great Eastern Class A at age 62?
- I am 29, how much do I pay for HSBC Life private hospital coverage?
- Show me the premium for IncomeShield Plan P if I am 55.
- What is the total premium for AIA HealthShield Gold Max A at age 34?
- How much cash would I pay for a Standard-tier plan at age 47?
- What does Singlife Shield Plan 2 cost if I am 66?

## Benefit Question Demos

- What does the Standard plan cover for ICU?
- Does IncomeShield Plan C cover psychiatric care?
- What is the psychiatric benefit for the Standard plan?
- Show me the ICU coverage for Singlife Standard.
- What does Prudential Class A cover for ward charges?
- Does AIA private hospital coverage include ICU?
- What is the cancer-related coverage for Standard IP?
- Show me the normal ward benefit for Income basic coverage.
- Does Great Eastern Class A cover psychiatric treatment?
- What does HSBC Life private hospital coverage say for ICU?
- What is the benefit row for ward coverage in Standard?
- Show me the ICU benefit for Prudential private hospital coverage.
- What does Income Class B1 cover for psychiatric care?
- Does Singlife Plan 1 cover ICU?
- What is the exact coverage text for ward benefits in Standard IP?

## Recommendation Question Demos

- I am 26 years old, what insurance should I buy?
- I am 31 and want something balanced. What kind of coverage should I consider?
- I am 24. I want to keep premiums low. What would you recommend?
- I am 42 and I prefer private hospital coverage. What should I buy?
- I am 35. I care more about coverage than cost. What plan tier should I look at?
- I am 29 and not sure about ward type yet. Recommend something sensible.
- I am 52. I want the strongest coverage. What are my best options?
- I am 38. Give me a shortlist for Integrated Shield Plans.
- I am 27 and want a middle-ground option. What should I consider?
- I am 45 and want private hospital care, but I still care about cost. What would you suggest?

## Natural Follow-Up Replies For Recommendation Chat

These are useful during the multi-turn recommendation flow:

### Budget preference

- I want to keep premiums low.
- I want a balanced option.
- I am flexible on cost if coverage is better.

### Ward preference

- I prefer basic coverage.
- I prefer Standard coverage.
- I prefer Class B1 coverage.
- I prefer Class A coverage.
- I prefer private hospital coverage.
- I am not sure about the ward tier yet.

### Coverage style

- I want the lowest-cost option.
- I want a balanced tradeoff.
- I want the strongest coverage.

## Good Prompt Patterns

These patterns usually work well:

- `I am [age], how much cash do I pay for [insurer] [tier]?`
- `What is the premium for [plan name] if I am [age]?`
- `What does [plan or tier] cover for [benefit keyword]?`
- `Does [plan] cover [benefit keyword]?`
- `I am [age], what insurance should I buy?`
- `I am [age] and I want [budget style]. What do you recommend?`

## Benefit Keywords That Usually Work Well

- ICU
- psychiatric
- mental health
- ward
- room
- cancer

## Not Supported Well In Chat Yet

These are outside the current grounded scope or only partially supported:

- Full free-form comparison across many plans in one answer
- Detailed advice based on income, family dependants, health conditions, or claims history
- Non-Singapore insurance products
- General financial planning beyond Integrated Shield Plan data
- Exact benefit browsing without a plan context
- Questions that require data not present in the normalized premium or benefit tables

## Suggested Demo Sequence

If you want a clean live demo, this order works well:

1. `What does the Standard plan cover for ICU?`
2. `I am 45, how much cash do I pay for Prudential Class A?`
3. `I am 26 years old, what insurance should I buy?`
4. `I want to keep premiums low.`
5. `I prefer private hospital coverage.`
6. `I want the strongest coverage.`
