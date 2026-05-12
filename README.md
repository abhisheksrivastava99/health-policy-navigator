# Health Policy Navigator

Singapore Health Policy Navigator is a Streamlit + FastAPI application for exploring Singapore Integrated Shield Plan premiums, benefit schedules, and recommendation-style shortlists with source-backed answers.

## Stack

- Frontend: Streamlit
- Backend: FastAPI
- Orchestration: LangGraph
- LLM provider: OpenAI (`gpt-4o-mini` by default)
- Data layer: local normalized CSV master tables under `ip_plan_tables/master/`

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` file from `.env.example` and set:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

Run the backend:

```bash
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run the Streamlit app:

```bash
python3 -m streamlit run app.py
```

## Environment Variables

### Backend

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, defaults to `gpt-4o-mini`)

### Frontend

- `API_BASE_URL` points the Streamlit app to the deployed FastAPI backend
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SHOW_DEBUG_PAYLOADS` optional, defaults to off

## Deploy Backend To Render

This repo includes a `render.yaml` blueprint for the FastAPI backend.

Manual service settings if you prefer entering them in the Render UI:

- Service type: Web Service
- Environment: Python
- Root directory: repo root
- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set these Render environment variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-4o-mini`

After deploy, verify:

```text
https://<your-render-service>/health
```

## Deploy Frontend To Streamlit Community Cloud

Use the same GitHub repo and choose:

- Main file path: `app.py`
- Python dependencies: `requirements.txt`

Set these Streamlit secrets or environment values:

- `API_BASE_URL=https://<your-render-service>`
- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-4o-mini`

Leave `SHOW_DEBUG_PAYLOADS` unset unless you intentionally want raw payload panels visible.

## Deployment Verification

After both services are live:

1. Confirm the backend status card shows online.
2. Test one premium question.
3. Test one benefit question.
4. Test one recommendation flow end-to-end.

## Project Data

Runtime app data is loaded from:

- `ip_plan_tables/master/plan_catalog.csv`
- `ip_plan_tables/master/benefits_master.csv`
- `ip_plan_tables/master/premiums_master.csv`
- `ip_plan_tables/master/cpf_limits_master.csv`

These files should stay committed for deployment.
