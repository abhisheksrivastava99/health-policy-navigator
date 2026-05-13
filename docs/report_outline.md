# Assignment Report Outline and Checklist

## 1. Focus Area and Problem Statement
- State the focus area: insurance.
- Describe the current Integrated Shield Plan comparison workflow in Singapore.
- Explain the pain points: fragmented premium tables, hard-to-find benefit clauses, and manual CPF cash-payable calculations.
- Explain why an agentic AI approach is appropriate for routing user intent while keeping calculations deterministic.

## 2. Proposed Agentic System Architecture
- Insert the Mermaid architecture diagram from [architecture_diagram.md](/Users/abhishek/Desktop/Assignments/FinTech%20A2/docs/architecture_diagram.md:1).
- Describe the Streamlit UI, FastAPI backend, LangGraph flow, deterministic tool layer, and master CSV data layer.
- Explain the 2-call LLM design:
  - Call 1: route + structured extraction
  - Deterministic execution gap: tool layer and CSV lookups
  - Call 2: grounded synthesis from tool output only
- Explain why structured endpoints for premium and benefit tabs bypass the LLM entirely.

## 3. Agent Reasoning, Task Execution, and Human Oversight
- Explain how the route-and-extract node decides between premium, benefit, and unsupported intents.
- Explain how the synthesis node is constrained to tool outputs only.
- Explain how deterministic tools handle plan resolution, CPF lookup, premium math, and benefit retrieval.
- Identify human-in-the-loop checkpoints:
  - validating master table normalization
  - reviewing citations shown by the app
  - reviewing ambiguous or unsupported cases

## 4. Data Requirements and Preparation
- Describe the original MOH PDF tables as the source.
- Explain the cleaning step into `ip_plan_tables/cleaned_csv/`.
- Explain the normalization step into `ip_plan_tables/master/`.
- Describe each runtime dataset:
  - `plan_catalog.csv`
  - `benefits_master.csv`
  - `premiums_master.csv`
  - `cpf_limits_master.csv`
- Explain how the agents and tools access these datasets at runtime through the cached loader layer.

## 5. Risk, Governance, and Monitoring
- Risk: incorrect plan resolution for ambiguous user wording.
  - Mitigation: deterministic alias mapping, ambiguity errors, and visible matched-plan output.
- Risk: hallucinated answers.
  - Mitigation: LLM never performs premium math or invents benefits; answers are grounded in tool payloads only.
- Risk: stale or malformed source data.
  - Mitigation: reproducible normalization pipeline, row-count checks, and startup validation.
- Monitoring ideas:
  - log endpoint usage by query type
  - track ambiguous/error cases
  - track benefit keywords that frequently fail to match

## 6. Economic Value Measurement
- Define baseline manual workflow time for a premium or benefit lookup.
- Measure time saved per query using the prototype.
- Estimate reduction in advisor or support effort for repeated plan questions.
- Track quality signals:
  - successful lookup rate
  - ambiguity rate
  - unsupported query rate
- Convert usage and time savings into cost savings assumptions.

## 7. Assumptions
- The app is a local prototype and not a regulated production advice engine.
- MOH source tables are treated as the factual baseline.
- Users still verify citations before making financial decisions.
- No database or persistent identity layer is included in this prototype.

## Final Submission Checklist
- Problem statement clearly tied to insurance workflow pain points.
- Architecture diagram included and matches the implemented code.
- Reasoning and human oversight explained clearly.
- Data preparation and retrieval path documented end to end.
- Governance and monitoring section is explicit.
- Economic value methodology is practical and measurable.
- Assumptions are stated clearly.
