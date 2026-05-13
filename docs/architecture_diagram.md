# Singapore Health Policy Navigator Architecture

```mermaid
flowchart LR
    User["User"] --> UI["Streamlit UI<br/>Chat + Premium Explorer + Benefit Explorer"]
    UI --> Health["GET /health"]
    UI --> Chat["POST /chat"]
    UI --> Premium["POST /premium/quote"]
    UI --> Benefit["POST /benefit/search"]

    subgraph API["FastAPI Service"]
        Health --> Status["Startup + health validation"]
        Chat --> Extract["LLM Call 1:<br/>Route + structured extraction"]
        Extract --> Route{"Intent route"}

        Route --> PremiumTools["Deterministic premium path<br/>resolve_plan / lookup_cpf_limit / calculate_premium"]
        Route --> BenefitTools["Deterministic benefit path<br/>resolve_plan / lookup_benefit"]
        Route --> RecCheck{"Recommendation<br/>context complete?"}
        Route --> Unsupported["Unsupported / missing-field response"]

        RecCheck -->|No| RecIntake["LLM-guided recommendation intake<br/>collect age / budget / ward / coverage style"]
        RecCheck -->|Yes| RecCandidates["Deterministic recommendation candidate builder<br/>premium rows / cash payable / heuristic scoring"]
        RecCandidates --> RecReason["LLM recommendation reasoner<br/>top-3 shortlist explanation"]

        PremiumTools --> Synthesize["LLM Call 2:<br/>Premium / benefit synthesis"]
        BenefitTools --> Synthesize
        RecIntake --> ChatResponse["Structured chat payload"]
        RecReason --> ChatResponse
        Unsupported --> ChatResponse
        Synthesize --> ChatResponse

        ChatResponse -.-> ChatState["conversation_state<br/>recommendation_context"]
        ChatState -.-> Chat

        Premium --> PremiumTools
        Benefit --> BenefitTools
    end

    PremiumTools --> Data["Master CSV data layer<br/>plan_catalog.csv<br/>benefits_master.csv<br/>premiums_master.csv<br/>cpf_limits_master.csv"]
    BenefitTools --> Data
    RecCandidates --> Data

    Human["Human oversight<br/>query phrasing, citation review,<br/>architecture validation, governance review"] -.-> UI
    Human -.-> API
    Human -.-> Data
```

## Human-in-the-loop checkpoints
- User reviews citations shown in chat and explorer tabs before relying on the answer.
- User provides recommendation preferences during in-chat intake before the shortlist is produced.
- Developer validates normalized data outputs, recommendation behavior, and smoke tests before submission.
- Report writer documents governance, risks, and economic value assumptions outside the runtime flow.
