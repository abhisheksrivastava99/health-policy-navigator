# Health Policy Navigator

Health Policy Navigator is a Streamlit + FastAPI application for exploring Singapore Integrated Shield Plan data through a chat-first interface and two deterministic explorer tools.

It is designed to answer:
- premium and cash-payable questions
- source-backed benefit and coverage questions
- guided recommendation-style questions inside chat

The app uses local normalized master tables for plan, premium, benefit, and CPF-limit data, and uses OpenAI + LangGraph in the chat flow for routing, intake, and recommendation reasoning.

## What The App Does

### Chat

Chat supports three main question types:

- `Premium`
  - Example: `I am 45, how much cash do I pay for Prudential Class A?`
- `Benefit`
  - Example: `What does the Standard plan cover for ICU?`
- `Recommendation`
  - Example: `I am 26 years old, what insurance should I buy?`

Recommendation handling stays inside chat. The app can ask follow-up questions, collect missing preferences, and return a structured shortlist with rationale and disclaimer.

### Premium Explorer

Premium Explorer is a deterministic route for age-based premium lookups. It uses guided plan narrowing instead of free-text guessing.

### Benefit Explorer

Benefit Explorer supports exact benefit lookups and full benefit schedule browsing for the selected plan. The keyword is optional.

## Product Stack

- Frontend: Streamlit
- Backend: FastAPI
- Orchestration: LangGraph
- LLM provider: OpenAI
- Default model: `gpt-4o-mini`
- Data source: normalized CSV master tables in `ip_plan_tables/master/`

## Architecture

### Frontend

[app.py](./app.py)

- renders the Streamlit UI
- manages chat session state
- renders structured answer cards
- calls the FastAPI backend using `API_BASE_URL`

### Backend

[main.py](./main.py)

- exposes:
  - `GET /health`
  - `POST /chat`
  - `POST /premium/quote`
  - `POST /benefit/search`
- runs the LangGraph chat flow
- uses deterministic lookup helpers for premium, benefit, and recommendation candidate generation

### Data + Helper Modules

- [tools.py](./tools.py)
- [data_loader.py](./data_loader.py)

### Architecture Diagram

- [architecture_diagram.md](./architecture_diagram.md)

## Repository Structure

```text
app.py
main.py
tools.py
data_loader.py
requirements.txt
render.yaml
.python-version
.streamlit/secrets.toml.example
ip_plan_tables/master/
tests/smoke/
DEMO_QUESTIONS.md
```

## Local Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a local env file

Copy [.env.example](./.env.example) to `.env` and set:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
API_BASE_URL=http://127.0.0.1:8000
SHOW_DEBUG_PAYLOADS=false
```

### 3. Run the backend

```bash
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### 4. Run the Streamlit app

```bash
python3 -m streamlit run app.py
```

## Environment Variables

### Backend

- `OPENAI_API_KEY`
- `OPENAI_MODEL`

### Frontend

- `API_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SHOW_DEBUG_PAYLOADS`

Notes:

- `API_BASE_URL` should point Streamlit to the FastAPI backend.
- `SHOW_DEBUG_PAYLOADS` is off by default and should stay off for normal demos/submission use.
- Streamlit Community Cloud can provide values through `st.secrets`.

## Deployment

This repo is set up for a two-service deployment:

- Streamlit Community Cloud for the frontend
- Render for the backend

### Render Backend

This repo includes [render.yaml](./render.yaml) with:

- `plan: free`
- `buildCommand: pip install -r requirements.txt`
- `startCommand: python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT`
- `healthCheckPath: /health`

Python is pinned using [.python-version](./.python-version).

Set these Render environment variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-4o-mini`

After deploy, verify:

```text
https://<your-render-service>.onrender.com/health
```

### Streamlit Community Cloud Frontend

Use:

- repo: `abhisheksrivastava99/health-policy-navigator`
- branch: `main`
- main file: `app.py`
- Python version: `3.12`

Set Streamlit secrets using [.streamlit/secrets.toml.example](./.streamlit/secrets.toml.example) as the template:

```toml
API_BASE_URL = "https://<your-render-service>.onrender.com"
OPENAI_API_KEY = "your_openai_api_key"
OPENAI_MODEL = "gpt-4o-mini"
SHOW_DEBUG_PAYLOADS = "false"
```

## Live Repository

- [abhisheksrivastava99/health-policy-navigator](https://github.com/abhisheksrivastava99/health-policy-navigator)

## Verification Checklist

### Local

```bash
python3 tests/smoke/run_smoke_tests.py
```

Expected result:

- smoke tests pass

### Deployed

Verify all of the following:

1. `GET /health` returns a healthy response from Render.
2. The Streamlit `Control Room` shows the backend as online.
3. A premium chat question works.
4. A benefit chat question works.
5. A recommendation question works end-to-end.
6. Premium Explorer works.
7. Benefit Explorer works.

## Demo Prompts

See:

- [DEMO_QUESTIONS.md](./DEMO_QUESTIONS.md)

Good quick demos:

- `What does the Standard plan cover for ICU?`
- `I am 45, how much cash do I pay for Prudential Class A?`
- `I am 26 years old, what insurance should I buy?`

## Data Files

Runtime app data is loaded from:

- `ip_plan_tables/master/plan_catalog.csv`
- `ip_plan_tables/master/benefits_master.csv`
- `ip_plan_tables/master/premiums_master.csv`
- `ip_plan_tables/master/cpf_limits_master.csv`

These files should remain committed for local runs and cloud deployment.
