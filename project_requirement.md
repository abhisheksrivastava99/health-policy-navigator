# Project Requirements: Singapore Health Policy Navigator

## 1. Project Overview
The **Singapore Health Policy Navigator** is a local, agentic AI application that helps users compare Singapore Integrated Shield Plan premiums, inspect benefit schedules, and explore recommendation-style shortlists with source-backed answers.

The system uses a **LangGraph-based chat flow** for natural-language interaction:
- **Call 1:** route + structured extraction
- **Deterministic tool layer:** plan resolution, premium math, CPF lookup, benefit retrieval, and recommendation candidate generation
- **Recommendation path:** LLM-guided intake plus LLM explanation over deterministic candidates
- **Premium / benefit path:** concise synthesis from tool outputs only

For form-based lookups, the application also exposes deterministic API endpoints that bypass the LLM completely.

## 2. Technology Stack
* **Frontend UI:** Streamlit
* **Backend API:** FastAPI
* **Agent Orchestration:** LangGraph
* **LLM Provider:** OpenAI API (`gpt-4o-mini` by default)
* **Data Processing:** Python + Pandas
* **Data Storage:** Local master CSV files

## 3. Runtime Data Layer
The application uses normalized runtime tables under `ip_plan_tables/master/`. Cleaned MOH tables under `ip_plan_tables/cleaned_csv/` remain the source-preparation and audit layer.

* **`plan_catalog.csv`**
  * Canonical plan/entity list across all 5 tiers
  * Includes baseline entities such as `MediShield Life` and `Standard IP`
* **`benefits_master.csv`**
  * One row per `plan_id x source benefit row`
  * Supports deterministic keyword lookup using normalized text fields
* **`premiums_master.csv`**
  * One row per `plan_id x age band`
  * Supports scalar and range premium handling
* **`cpf_limits_master.csv`**
  * Age-banded CPF MediSave Additional Withdrawal Limits

## 4. Architecture

### 4.1 Chat Flow (`POST /chat`)
The chat route uses LangGraph to prevent hallucinated math or policy answers.

* **Node 1 - Route + Extract**
  * Input: raw user message
  * Output: structured intent + parameters (`age`, `insurer`, `tier`, `plan_name`, `benefit_keyword`, recommendation preferences)
* **Node 2A - Deterministic Tool Layer**
  * Premium flow: `resolve_plan -> lookup_cpf_limit -> calculate_premium`
  * Benefit flow: `resolve_plan -> lookup_benefit`
* **Node 2B - Recommendation Intake / Reasoning**
  * Recommendation intake collects `age`, `budget_preference`, `ward_preference`, and `coverage_style`
  * Recommendation reasoning ranks a deterministic candidate set and explains the shortlist
* **Node 3 - Final Response**
  * Input: tool payload only
  * Output: concise user-facing answer with citations or a structured recommendation payload

### 4.2 Structured API Endpoints
The Streamlit explorer tabs use deterministic endpoints directly:

* **`GET /health`**
  * Returns backend status, selected model, and master-table row counts
* **`POST /premium/quote`**
  * Request: `age` required; `insurer`, `tier`, and `plan_name` optional
  * Response: `response`, `plan_resolution`, `cpf_limit`, `premium_result`, `error`
* **`POST /benefit/search`**
  * Request: `benefit_keyword` required; `insurer`, `tier`, and `plan_name` optional
  * Response: `response`, `plan_resolution`, `benefit_result`, `error`
* **`POST /chat`**
  * Request: `message` required; `conversation_state` optional for recommendation follow-ups
  * Response: `response`, `tool_used`, `extracted_data`

## 5. Core Functional Requirements
* **Natural-language chat:** route between premium, benefit, and recommendation questions accurately
* **Deterministic premium math:** the LLM never computes premiums or cash payable itself
* **Deterministic benefit lookup:** return exact source-backed coverage text and notes
* **Recommendation shortlist:** use deterministic plan candidates with LLM-guided intake and explanation
* **Graceful errors:** handle ambiguous plan matches, unavailable premium bands, missing fields, and unsupported queries clearly
* **Citation visibility:** show source PDF, page, and table in chat and explorer views
* **Standard-plan fallback:** insurer-branded standard plan benefit lookups may use the shared `Standard IP` baseline schedule

## 6. Frontend Requirements
The Streamlit app should expose 3 user-facing surfaces:

* **Chat**
  * natural-language interface
  * session-state chat history
  * example prompts
  * recommendation follow-up flow
  * backend status banner
* **Premium Explorer**
  * form-driven premium lookup
  * age, insurer, tier, optional plan name
  * scalar/range premium presentation
* **Benefit Explorer**
  * form-driven benefit lookup
  * insurer, tier, optional plan name, benefit keyword
  * best match + supporting matches

## 7. Implementation Status
* **[x] Phase 1: Data Preparation**
  * Extracted MOH PDF tables
  * Cleaned into `cleaned_csv/`
  * Normalized into runtime master tables
* **[x] Phase 2: Core Logic & Tools**
  * Implemented cached data loader
  * Implemented premium and benefit tools
* **[x] Phase 3: Backend API**
  * Implemented FastAPI
  * Implemented LangGraph chat flow
  * Added `GET /health`, `POST /premium/quote`, `POST /benefit/search`, and `POST /chat`
* **[x] Phase 4: Frontend UI**
  * Implemented Streamlit app with chat and explorer tabs
  * Added in-chat recommendation intake and shortlist rendering
* **[x] Phase 5: Assignment Assets**
  * Added Mermaid architecture diagram
  * Added report outline/checklist

## 8. Local Run Flow
Run the project in two terminals:

```bash
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```bash
python3 -m streamlit run app.py
```

## 9. Success Criteria
* The application runs locally with Streamlit + FastAPI
* Premium calculations match the source tables and respect CPF withdrawal limits
* Benefit answers return exact source-backed coverage text
* Recommendation chat can collect preferences and return a citation-backed shortlist
* Chat uses the 2-call grounded architecture without hallucinating tool facts
* Explorer tabs work without invoking the LLM
