# Title Page Content

**Assignment Title:** MH6818 FinTech Innovation with AI - Individual Assignment 2  
**Project Title:** Singapore Health Policy Navigator: An Agentic AI Prototype for Integrated Shield Plan Comparison  
**Focus Area:** Insurance  
**Student Name:** SRIVASTAVA ABHISHEK  
**Student ID:** G2505156E  
**Course:** MH6818 FinTech Innovation with AI  
**Submission Date:** 13 May 2026

# Executive Summary

This report presents a deployed prototype in the insurance domain. The chosen use case is the comparison of Singapore Integrated Shield Plans (IPs), with a focus on premium estimation, cash-payable computation after CPF MediSave withdrawal limits, and benefit lookup across plan tiers and insurers. The prototype is called the Singapore Health Policy Navigator.

I chose this problem because IP comparison is still operationally fragmented for customers, advisers, and service teams. Premium schedules are spread across multiple Ministry of Health (MOH) comparison tables, benefit clauses are difficult to search manually, and the cash-payable portion of a premium depends on age-banded withdrawal limits. In practice, this means even straightforward questions can take several steps to answer and are easy to get wrong.

To address this problem, the project uses an agentic AI architecture rather than a simple chatbot. The design combines a lightweight large language model (LLM) orchestration layer with deterministic Python tools. In the chat flow, the first LLM call acts as a Planner/Router Agent that classifies the user request and extracts structured parameters such as age, insurer, plan tier, plan name, and benefit keyword. The request is then passed to deterministic tools that perform plan resolution, premium lookup, CPF limit lookup, and benefit retrieval directly from normalized master tables. A second LLM call then acts as a Response Synthesis Agent and produces a concise reply grounded in tool output only.

The prototype is implemented with a deployed Streamlit frontend, a deployed FastAPI backend, LangGraph for the two-step orchestration flow, and local normalized CSV master tables as the runtime knowledge layer. In addition to open-ended chat, the system includes deterministic premium and benefit explorer interfaces that bypass the LLM completely. I took this hybrid approach because conversational understanding is useful at the front of the workflow, but computation and evidence retrieval should remain rule-based and traceable.

# Focus Area and Problem Statement

The selected focus area for this assignment is insurance. More specifically, the project focuses on the comparison and interpretation of Singapore Integrated Shield Plans, which are private insurance plans that complement MediShield Life and differ across benefit tiers, hospital class coverage, and insurer product structures.

The problem addressed by this project is not underwriting or pricing. Instead, it is the information access and comparison workflow around these products. Consumers and advisers often need quick answers to practical questions such as which plan matches a preferred hospital tier, what the annual premium is for a given age band, how much of the premium can be funded through MediSave, how much cash remains payable, and whether a specific benefit such as intensive care unit coverage or psychiatric coverage is included.

This makes the process inefficient. A user must identify the correct document set, locate the relevant tier, identify the correct insurer plan, interpret the correct age band or benefit row, and reconcile that information with CPF withdrawal rules. Even simple questions can require several document searches and cross-checks.

An agentic AI approach is appropriate because the problem has both unstructured and structured components. Users ask questions in natural language, often incompletely or ambiguously. However, the answer space itself is highly structured and should not be invented by the model. The value of the agentic approach lies in dividing the problem into stages: interpret the question, execute deterministic retrieval and calculation, and then present the answer clearly.

# Current Workflow, Challenges, and Motivation for Innovation

The current workflow for IP comparison is largely document-driven. A customer or adviser begins with MOH comparison PDFs, insurer-specific product names, and age-based premium tables. The user must identify the appropriate tier, such as basic, standard, Class B1, Class A, or private hospital coverage, and then manually scan the correct row and column combinations. If the task is a benefit lookup, the user must also parse textual benefit categories and notes embedded in dense schedules.

This process has several important challenges. First, information is fragmented across multiple files and pages. In this project alone, the source layer contains five separate MOH PDF documents. After extraction, these yield forty-two raw tables, which then require cleaning and normalization before becoming reliable runtime assets.

Second, the workflow mixes lookup logic with calculation logic. Premium values may appear as single values or ranges, and the eventual cash outlay depends on CPF MediSave withdrawal limits that differ by age band. A generic chatbot should not be trusted to perform that transformation without constraints.

Third, the workflow is vulnerable to ambiguity. Insurers can have multiple products within the same tier, and user phrasing is often incomplete. Someone may ask for "Prudential Class A" without specifying which plan variant is intended, or ask for "standard plan ICU cover" without naming an insurer. A manual workflow depends on the user knowing how to disambiguate these cases, while an AI workflow must handle them safely.

The motivation for innovation is therefore both operational and strategic. On the operational side, a guided system can reduce lookup time, improve consistency, and expose citations more clearly. On the strategic side, an agentic architecture shows how conversational AI can be introduced into a financial-services workflow without giving up control over high-risk tasks such as product interpretation and monetary calculation.

# Proposed Agentic AI System Architecture

The proposed system architecture is implemented as a deployed prototype. It consists of a user-facing Streamlit application, a FastAPI backend hosted on Render, a LangGraph orchestration layer for chat requests, a deterministic tool layer for retrieval and computation, and a local master CSV data layer.

Figure 1 should be inserted here from `docs/architecture_diagram.md`. For the main body, the most suitable option is the "High-Level Architecture Diagram" or the "Compact Report Diagram", depending on available page space.

From the user perspective, the frontend provides three interaction surfaces. The first is a natural-language chat interface for open-ended questions. The second is a Premium Explorer that supports structured premium lookup by age, insurer, tier, and optional plan name. The third is a Benefit Explorer that supports structured benefit search by insurer, tier, optional plan name, and benefit keyword. This separation is intentional: chat is useful for flexible queries, while explorer tabs are more suitable for guided information retrieval.

At the time of submission, the prototype is accessible through the deployed frontend at [citizen-health-policy-navigator.streamlit.app](https://citizen-health-policy-navigator.streamlit.app/) and the deployed backend at [health-policy-navigator-backend.onrender.com](https://health-policy-navigator-backend.onrender.com/). This deployment makes the prototype more credible as a working submission, but it is still best understood as a controlled information-support tool rather than a production-ready insurance platform.

The backend exposes four main routes. `GET /health` reports system status and row counts for the runtime master tables. `POST /premium/quote` performs deterministic premium and CPF computations. `POST /benefit/search` performs deterministic benefit lookup. `POST /chat` runs the two-step LangGraph flow. The presence of both conversational and deterministic routes reflects a practical architectural decision: not every workflow should involve the LLM.

The runtime logic is divided into three functional agent roles. The Planner/Router Agent receives the user message and extracts intent plus structured fields. The Execution Agent resolves the correct plan, retrieves age-banded or benefit-specific information, and performs CPF-aware premium calculations. The Response Synthesis Agent turns the tool payload into a concise user-facing response with traceable references to the source PDF, page, and table. This agent decomposition is conceptually clear for the report and also mirrors the actual backend flow.

The data layer is implemented with normalized master CSV files rather than a database. I made that choice deliberately because the source domain for this assignment is finite, highly structured, and already published in table form. For a prototype, CSV master tables are easier to inspect, validate, and explain than a more complex persistence layer. The master layer currently contains a plan catalog with thirty-nine canonical plans, a benefits master with 1,736 rows, a premiums master with 570 rows, and a CPF limits table with three age-banded records. This design prioritizes transparency, reproducibility, and auditability.

# Agent Reasoning, Task Execution, Decision Logic, and Human Oversight

The Planner/Router Agent is responsible for intent classification and parameter extraction. Its task is to determine whether the user is asking for a premium calculation, a benefit lookup, or something outside the supported scope. It does not answer the question directly. Instead, it produces structured output such as age, insurer, tier, plan name, and benefit keyword.

The Execution Agent performs the most important operational work. For premium requests, it resolves the intended plan, retrieves the relevant CPF withdrawal limit for the user's age, locates the matching premium band, and calculates the cash-payable portion after MediSave funding. For benefit requests, it resolves the intended plan and performs a deterministic lookup against normalized benefit text and search fields. The plan resolution logic includes insurer aliases, tier aliases, ambiguity detection, and a fallback mechanism for shared Standard IP benefit schedules. This matters because insurance queries are often under-specified, and safe resolution is more important than aggressive guessing.

The Response Synthesis Agent performs the final communication step. It receives only the structured tool payload and is instructed to use those facts exclusively. In other words, it cannot invent premium numbers, benefit clauses, age bands, or citations. Its purpose is not to decide but to explain.

Human oversight remains necessary at several points. First, humans are required in the data preparation stage to validate that extracted and cleaned tables match the source material. The workspace already includes verification reports for raw extraction and cleaned tables, which show a pass status across the checked tables and therefore support trust in the preparation pipeline. Second, users should review citations before relying on any answer for a real financial decision. Third, ambiguous or unsupported questions should be reviewed rather than forced into a potentially misleading answer. Finally, the governance, monitoring, and update process itself should remain under human control because policy schedules and product offerings can change over time. In my view, this is the most realistic boundary for the prototype: it can speed up retrieval and comparison, but it should not replace human judgment.

This human-in-the-loop design is appropriate for financial services. The system is not positioned as an autonomous advice engine. Instead, it is a controlled information and comparison assistant that improves access to source-backed content while still leaving high-stakes judgment to human users, advisers, or compliance reviewers.

# Data Requirements, Preparation, and Retrieval

The proposed system depends on structured, current, and traceable product information. In this prototype, the primary data source is the set of publicly available MOH comparison PDF documents for Integrated Shield Plans. These documents contain both textual benefit schedules and tabular premium information across multiple plan tiers.

However, the source PDFs are not directly suitable for reliable runtime use. A preprocessing pipeline is therefore required. The first stage extracts tables from the PDFs into raw CSV files. In the current workspace, the five source PDFs produce forty-two extracted raw tables. The second stage cleans those tables by normalizing headers, repairing embedded header rows, attaching notes to the correct rows, and standardizing section and benefit structure. The third stage normalizes the cleaned outputs into runtime master tables that can be used consistently by application logic.

The runtime layer contains four important datasets. `plan_catalog.csv` is the canonical plan directory used for plan resolution. `benefits_master.csv` stores normalized benefit rows together with supporting text and traceability fields. `premiums_master.csv` stores age-banded premium information, including scalar and range values, premium-excluding-MediShield-Life values, annual change information, and source references. `cpf_limits_master.csv` stores age-banded CPF MediSave Additional Withdrawal Limits.

The system retrieves data through a cached loader layer, which validates the required columns, converts relevant fields into runtime-friendly forms, and builds indices such as plan-by-ID mappings and token-based lookup structures. This is a practical design choice because it reduces repeated file processing at runtime while keeping the data path simple enough to audit.

For the user-facing application, data retrieval differs by interface. In the chat route, the extracted user intent determines which deterministic retrieval path is executed. In the explorer interfaces, the LLM is bypassed entirely and the backend endpoints use structured form inputs directly.

The workspace also contains verification artifacts and smoke tests that support the quality of the data and service layers. These include reports for raw table verification, cleaned table verification, and smoke tests for health, premium, benefit, boundary-age, ambiguity, and no-match scenarios.

# Risk, Governance, and Monitoring

Although this prototype addresses a relatively narrow insurance information workflow, it still raises important risk and governance questions. The first major risk is incorrect plan resolution. Users may supply incomplete or ambiguous plan names, insurer names, or tiers. If the system guesses incorrectly, it could provide the wrong premium or benefit description. The current design mitigates this by using deterministic alias handling, ambiguity detection, and explicit error responses when the request is under-specified.

The second risk is hallucination by the LLM. This is especially relevant in financial-services contexts because users may assume that a fluent answer is a correct answer. The architecture mitigates this by restricting the LLM to routing and grounded synthesis tasks. Premium values, benefit clauses, and citation metadata come from deterministic tools and normalized source tables rather than from model inference.

The third risk is stale or malformed source data. Insurance schedules evolve, and if the underlying documents change, a previously correct runtime table may become outdated. For this reason, the prototype includes a reproducible extraction-cleaning-normalization pipeline and validation steps that can be rerun when source documents are updated. In governance terms, this supports change control and auditability.

Monitoring should therefore focus on both system quality and business usability. Useful operational metrics include successful lookup rate, ambiguous plan rate, unsupported query rate, benefit keyword miss rate, and endpoint usage by query type. The deployed version of the system should also track which source version is currently loaded and when the master tables were last regenerated. If I were extending this project further, I would also add lightweight logging around failed matches and repeated user reformulations, because those would show where the assistant is still confusing or incomplete.

From a governance perspective, the system should be framed as an information support tool rather than a regulated advice engine. Outputs should remain source-backed, citations should remain visible, and users should be encouraged to verify results before making actual purchase decisions. That framing is both responsible and consistent with the implemented design.

# Economic Value Measurement

The economic value of this solution should be measured by comparing the assisted workflow against the manual baseline. The baseline process includes opening the relevant MOH document, finding the correct tier, identifying the insurer plan, locating the correct premium band or benefit row, and computing the cash-payable amount after CPF limits where relevant. This is a repetitive but still non-trivial information task.

The prototype creates value in three ways. First, it reduces lookup time. Second, it reduces the probability of manual interpretation error. Third, it improves consistency by standardizing plan resolution and citation display. These benefits are meaningful for customer service teams, financial advisers, digital support channels, and even end users who self-serve through a guided interface.

A practical measurement approach would include the following metrics:

- Average time to complete a premium lookup before and after using the system.
- Average time to complete a benefit lookup before and after using the system.
- Successful lookup rate.
- Ambiguity rate and unsupported query rate.
- Percentage of responses with source citation visibility.
- Estimated staff minutes saved per 100 queries.

These operational metrics can be converted into economic terms. For example, if the prototype reduces average lookup time from several minutes to under one minute for repeated policy questions, the time savings can be translated into labour-cost savings using an assumed hourly cost for service or advisory staff. If it also reduces the number of escalations caused by unclear or inconsistent answers, that yields an additional efficiency benefit. Even without claiming a precise financial return, this gives a reasonable way to connect technical performance to business value.

The assignment requires a methodology rather than a proven financial return, so the objective is to define a credible framework. In that framework, the system's economic value comes not from replacing human advice, but from improving the efficiency and consistency of repeated information retrieval.

# Assumptions

This report is based on several assumptions:

- The system is treated as a deployed prototype rather than as a production-ready insurance platform.
- The MOH source documents are treated as the authoritative factual baseline for the implemented comparison workflow.
- The prototype is intended for information support, comparison assistance, and retrieval tasks, not for underwriting, financial recommendation, or regulated advisory decision-making.
- Users are assumed to review the citations shown by the system before relying on an answer in a real decision context.
- The current prototype assumes a finite and locally stored data universe, which is why local master CSV files are sufficient for the present implementation.
- The business value of the prototype is judged through operational efficiency, accuracy support, and user convenience rather than direct revenue generation.

# Limitations and Next Steps

This prototype was intentionally scoped to fit the assignment and to keep the core workflow trustworthy. It does not include a live insurer feed, a persistent user profile, or a formal audit dashboard. The recommendation flow is also deliberately conservative: it helps narrow options, but it does not attempt to replace regulated advice or suitability assessment.

If I were extending the project beyond this assignment, the next steps would be to automate source refreshes when MOH tables change, add structured monitoring for failed lookups and ambiguous queries, and introduce a clearer evaluation framework for recommendation quality. Those additions would make the system more useful operationally without changing its core design principle of keeping high-risk facts and calculations deterministic.

# Conclusion

This project demonstrates a credible and technically disciplined application of agentic AI in insurance. By focusing on the comparison of Singapore Integrated Shield Plans, it addresses a real workflow problem with clear user value. The system improves accessibility to premium and benefit information while preserving control over calculations and evidence retrieval.

The most important architectural contribution is the separation of conversational reasoning from factual execution. The Planner/Router Agent interprets user intent, the Execution Agent performs deterministic retrieval and computation, and the Response Synthesis Agent communicates results in natural language without inventing facts. For this use case, that separation is more important than making the system sound fully conversational, because correctness and traceability matter more than fluency alone.

Overall, the prototype meets the broader goals of the assignment. It connects AI capability to measurable economic value, incorporates human oversight and governance thinking, and shows how data preparation underpins trustworthy agent behavior. Taken together, these elements make the Singapore Health Policy Navigator a strong example of how agentic AI can improve an existing insurance workflow in a controlled and business-relevant way.

# Appendix

The following items can be included in the appendix section of the final Word document:

- Architecture diagram exported from `docs/architecture_diagram.md`
- Raw extraction verification summary
- Cleaned-table verification summary
- Smoke test summary
- Sample user questions from `docs/DEMO_QUESTIONS.md`
- Selected screenshots of the Streamlit interface after deployment
- Deployed frontend URL: `https://citizen-health-policy-navigator.streamlit.app/`
- Deployed backend URL: `https://health-policy-navigator-backend.onrender.com/`
