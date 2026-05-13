# Singapore Health Policy Navigator Architecture

## Compact Report Diagram

```mermaid
flowchart TB
    U["User"] --> F["Streamlit Frontend<br/>Chat | Premium Explorer | Benefit Explorer"]

    F --> C["POST /chat"]
    F --> P["POST /premium/quote"]
    F --> B["POST /benefit/search"]
    F --> H["GET /health"]

    subgraph API["FastAPI + LangGraph Backend"]
        C --> R["LLM Router Agent<br/>intent + field extraction"]
        R --> T["Deterministic Tool Layer<br/>plan resolution | CPF lookup | premium math | benefit search"]
        T --> S["LLM Response Agent<br/>grounded synthesis only"]

        R --> Q["Recommendation Intake<br/>collect age + preferences"]
        Q --> G["Recommendation Agent<br/>shortlist explanation"]
    end

    T --> D["Master CSV Data<br/>plans | benefits | premiums | CPF limits"]
    G --> D

    S --> F
    P --> T
    B --> T
    H --> F

    O["Human Oversight<br/>citation review | ambiguous cases | data validation"] -.-> F
    O -.-> API
```

## Human-in-the-loop checkpoints
- User reviews citations before relying on an answer.
- User provides recommendation preferences during chat intake.
- Developer validates data normalization and smoke-test results before submission.

## Deployment Diagram

```mermaid
flowchart TB
    U["User Browser"] --> S["Streamlit Cloud Frontend"]
    S --> R["Render Backend<br/>FastAPI + LangGraph"]
    R --> O["OpenAI API"]
    R --> D["Runtime CSV Data<br/>plans | benefits | premiums | CPF limits"]

    S --> X["Chat UI<br/>Premium Explorer<br/>Benefit Explorer"]
    R --> Y["/health | /chat | /premium/quote | /benefit/search"]
```

## High-Level Architecture Diagram

```mermaid
flowchart TB
    U["Users"] --> I["Presentation Layer<br/>Streamlit"]
    I --> A["Application Layer<br/>FastAPI + LangGraph"]
    A --> T["Decision Layer<br/>LLM routing + deterministic tools"]
    T --> D["Data Layer<br/>master CSV tables"]
    A -.-> H["Human Oversight<br/>validation | citation review | governance"]
```

## Which one to use
- `Compact Report Diagram`: best if you want to explain agent flow and recommendation handling.
- `Deployment Diagram`: best if you want to show Streamlit, Render, and OpenAI clearly.
- `High-Level Architecture Diagram`: best if you want a clean one-figure summary in the main report.

## Report tip
- For the smallest Word-friendly version, paste only the Mermaid diagram and omit the bullets below it.
