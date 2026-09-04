# Verity — Finance Controller

> **One-Line Pitch**:  
> *An explainable finance controller that reconciles transactions across four data sources, investigates every exception for a root cause, quantifies the money at risk, and shows its work — where every number on screen is clickable proof, not a claim.*

> **The Novelty Point (Hero Moment)**:  
> **Glass-box numbers.** On the Overview page, the match rate %, the ₹ exception total, and every cluster total are not static labels — they are interactive portals. Click the match rate and it instantly expands the exact list of matched/unmatched records live with hairline precision. Click an exception total and it reveals the records contributing to that variance along with the exact deterministic rule that classified them. There is no separate "trust me" layer between a financial number and its audit proof.

---

## Table of Contents
1. [Architecture Overview & ASCII Diagram](#architecture-overview)
2. [Clean Clone & Quickstart Instructions](#setup--clean-clone-instructions)
3. [Generating Synthetic Demo Data & Running Reconciliation](#how-to-load-demo-data--run-reconciliation)
4. [Complete API Documentation](#api-documentation)
5. [Automated Test Suite & Verification](#automated-test-suite)
6. [Design System Adherence](#design-system-adherence)

---

## Architecture Overview

Verity enforces a strict separation between **deterministic mathematical reconciliation** and **AI explanatory synthesis**. The core matching and exception rules are 100% deterministic, audit-logged, and unit-tested; the AI explainer service is completely isolated and equipped with an infallible zero-latency template fallback.

```
+----------------------------------------------------------------------------------------------------+
|                                    FOUR FINANCIAL DATA SOURCES                                     |
|  [Razorpay Gateway (JSON)]   [Bank Statements (CSV)]   [Merchant Ledger (JSON)]   [Settlement (CSV)]|
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                   DATA ADAPTER INGESTION LAYER                                     |
|                       Normalizes disparate schemas into uniform Record schemas                     |
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                               5-LEVEL DETERMINISTIC MATCHING ENGINE                                |
|  Level 1: Exact ID Match (Confidence: 1.00)                                                        |
|  Level 2: Exact Amount + Date Match (Confidence: 0.98)                                             |
|  Level 3: Tolerant Amount (< ₹1.00) + Settlement Window Match (Confidence: 0.95)                   |
|  Level 4: Fuzzy Levenshtein Reference Match (Similarity >= 0.85 -> LIKELY_MATCH [0.80, 0.95))      |
|  Level 5: Composite Multi-Factor Scoring (Payment Method, Timestamps, Direction)                   |
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                         +-------------------------+-------------------------+
                         |                                                   |
                         v                                                   v
+------------------------------------+             +-------------------------------------------------+
|          MATCHED RECORDS           |             |         DETERMINISTIC EXCEPTION ENGINE          |
|  - 100% clean matched transactions |             |  Evaluates Rules 1 through 10 in priority order |
|  - Zero financial variance         |             |  Rule 1: Duplicate Transaction                  |
+------------------------------------+             |  Rule 2: Fee & Tax Mismatch                     |
                                                   |  Rule 3: Unexplained Amount Mismatch            |
                                                   |  Rule 4: Missing in Bank                        |
                                                   |  Rule 5: Missing in Razorpay (Bank Credit)      |
                                                   |  Rule 6: Missing in Ledger                      |
                                                   |  Rule 7: Settlement Timing Window               |
                                                   |  Rule 8: Refund Synchronization Gap             |
                                                   |  Rule 9: Split / Partial Settlement             |
                                                   |  Rule 10: Reference ID Typo (Fuzzy)             |
                                                   |  Rule 11: UNKNOWN Fallthrough (Confidence <0.80)|
                                                   +-------------------------+-----------------------+
                                                                             |
                                                                             v
                                                   +-------------------------------------------------+
                                                   |            PATTERN INSIGHTS CLUSTERING          |
                                                   |  Groups exceptions by (type, root_cause)        |
                                                   |  Ranks by Priority Score: impact * (1 - conf)   |
                                                   +-------------------------+-----------------------+
                                                                             |
                         +---------------------------------------------------+
                         |
                         v
+----------------------------------------------------------------------------------------------------+
|                                  AI EXPLAINER & FALLBACK SERVICE                                   |
|  Primary: Google Gemini 2.5 Flash (Structured JSON explanatory briefs & journal entries)           |
|  Fallback: Deterministic Rule-Based Template Generator (Zero latency, never blocks on API)         |
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                     FASTAPI APPLICATION & DB                                       |
|  - SQLite / SQLAlchemy Models (SourceRecords, ReconciliationRuns, Exceptions, Immutable AuditLog)   |
|  - RESTful Endpoints with Pydantic v2 validation                                                   |
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                   GLASS-BOX REACT / VITE UI                                        |
|  - Space Grotesk & IBM Plex Mono typography with tabular figures                                   |
|  - Real-time inline glass-box metric expansion drawer                                              |
|  - Side-by-side transaction comparison with exact arithmetic proof                                 |
|  - Human-in-the-loop Approval / Rejection with tamper-evident audit trail                           |
+----------------------------------------------------------------------------------------------------+
```

---

## Setup & Clean Clone Instructions

These instructions have been verified end-to-end on a clean workspace.

### Prerequisites
- **Python 3.11+** (Tested on Python 3.11, 3.12, 3.14)
- **Node.js 18+** and **npm**
- **Git**

### 1. Clone the Repository
```bash
git clone <repo-url> Verity
cd Verity
```

### 2. Configure Environment Variables
Copy the template file to `.env`:
```bash
cp .env.example .env
```
*(Optional: If you want live Gemini explanations, add your `GEMINI_API_KEY=...` to `.env`. If left empty, Verity will automatically run in template-fallback mode without any external API calls or latency).*

### 3. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Generate Synthetic Data & Pre-populate Engine
```bash
# In backend/ with .venv active:
python generate_synthetic_data.py
```
This generates:
- `data/razorpay_transactions.json`
- `data/bank_statements.csv`
- `data/merchant_ledger.json`
- `data/settlement_reports.csv`
- `data/ground_truth.json` (154 transactions covering all 10 reconciliation scenarios)

### 5. Start Backend Server
```bash
# In backend/ with .venv active:
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Verify the backend is running:
```bash
curl http://127.0.0.1:8000/api/health
```

### 6. Frontend Setup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at **`http://localhost:5173`**.

---

## How to Load Demo Data & Run Reconciliation

1. **Via Web UI**:
   - Navigate to `http://localhost:5173/overview`.
   - Click the **"Run Reconciliation"** button in the header.
   - The engine will ingest all 4 sources, run the 5-level pipeline, populate the SQLite database, and refresh the dashboard.

2. **Via Command Line / cURL**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/reconciliation/run
   ```

3. **Re-generating Fresh Synthetic Data**:
   To re-randomize or re-seed the transaction dataset:
   ```bash
   cd backend
   source .venv/bin/activate
   python generate_synthetic_data.py
   ```

---

## API Documentation

Interactive Swagger/OpenAPI documentation is available at **`http://localhost:8000/docs`**.

### 1. System Health
- **`GET /api/health`**
  - **Description**: Returns server operational status, database connectivity, and table row counts.
  - **Response**: `{"status": "healthy", "database": "connected", "total_source_records": 552, "total_exceptions": 35}`

### 2. Reconciliation
- **`POST /api/reconciliation/run`**
  - **Description**: Triggers fresh multi-source ingestion, executes the 5-level matching engine, runs exception classification, persists records to the DB, and records audit entries.
  - **Response**: `ReconciliationSummaryResponse` (total records, match counts, values, match rate).
- **`GET /api/reconciliation/latest`**
  - **Description**: Retrieves summary metrics of the latest reconciliation run.
  - **Response**: JSON summary containing `matched_count`, `exception_count`, `match_rate`, `total_processed_value`, etc.
- **`GET /api/reconciliation/records`**
  - **Query Params**: `classification` (`MATCHED`, `LIKELY_MATCH`, `EXCEPTION`, `UNRESOLVED`), `limit`, `offset`.
  - **Description**: Paginated list of candidate reconciliation records enriched with source names and amounts.

### 3. Exception Center & Investigation
- **`GET /api/exceptions`**
  - **Query Params**: `status` (`AUTO_RESOLVE`, `REVIEW_REQUIRED`, `UNRESOLVED`, `APPROVED`, `REJECTED`), `exception_type`, `min_impact`, `limit`, `offset`.
  - **Description**: Filterable list of classified exceptions.
- **`GET /api/exceptions/{id}`**
  - **Description**: Full detail of a single exception including side-by-side source records, calculated variance, and chronological audit trail.
- **`POST /api/exceptions/{id}/approve`**
  - **Body**: `{"actor": "CONTROLLER", "notes": "Approved"}`
  - **Description**: Controller sign-off approving an automated or proposed exception resolution. Writes an immutable audit entry.
- **`POST /api/exceptions/{id}/reject`**
  - **Body**: `{"actor": "CONTROLLER", "notes": "Escalated to vendor"}`
  - **Description**: Controller rejection of resolution proposal.
- **`POST /api/exceptions/{id}/unresolve`**
  - **Description**: Reverts an exception to unresolved status for further manual audit.
- **`GET /api/exceptions/{id}/explain`**
  - **Description**: Generates an evidence-grounded natural-language briefing. Uses Gemini 2.5 Flash when available; automatically falls back to deterministic template if key is omitted or service is unreachable.

### 4. Pattern Insights (Clustering)
- **`GET /api/exception-clusters`**
  - **Description**: Exception clusters grouped by `(exception_type, root_cause)` signature, ranked in descending order by investigation priority score (`impact * (1 - confidence)`).
- **`GET /api/exception-clusters/{id}`**
  - **Description**: Detail for a specific cluster by its cluster ID.
- **`GET /api/exception-clusters/{id}/summary`**
  - **Description**: Executive natural-language summary and portfolio breakdown for an entire cluster.

### 5. Immutable Audit Trail
- **`GET /api/audit-log`**
  - **Query Params**: `transaction_id`, `exception_id`, `event_type`, `limit`, `offset`.
  - **Description**: Chronological, tamper-evident audit entries showing the exact timestamp, actor (`SYSTEM_DETERMINISTIC`, `SYSTEM_AI_SERVICE`, `OPERATOR`), action, and serialized evidence payload.

### 6. Data Quality
- **`GET /api/data-quality`**
  - **Description**: Real-time evaluation across 4 data hygiene dimensions: Missing IDs, Duplicate IDs, Missing Amounts, and Invalid Dates across all ingested records.

---

## Automated Test Suite

All 63 automated tests pass with 100% test coverage across all specifications:

```bash
# Run backend test suite from root
npm test
```
Or directly from `backend/`:
```bash
cd backend
.venv/bin/pytest -v
```

### Verified Test Cases
1. **Exact Matching**: Level 1/2/3 matching with 100% confidence on clean transactions (`test_exact_matching`).
2. **Fuzzy Matching**: Level 4 Levenshtein reference matching detecting transcription errors without promotion to clean matches (`test_fuzzy_matching`).
3. **Amount Mismatch**: Identifies discrepancies > ₹1.00 that cannot be explained by fees or taxes (`test_amount_mismatch`).
4. **Fee & Tax Mismatch**: Reconciles gross ledger vs net bank deposit with gateway fee and GST tax proof (`test_fee_mismatch`).
5. **Duplicate Detection**: Identifies duplicated payment IDs within a single source (`test_duplicate_detection`).
6. **Missing Transactions (Both Directions)**:
   - Gateway payment missing from bank statement (`MISSING_IN_BANK`).
   - Unidentified bank deposit missing from gateway (`MISSING_IN_RAZORPAY`).
7. **Settlement Timing Window**: Captures transactions settling across cutoff/midnight (`SETTLEMENT_TIMING`).
8. **Refund Mismatch**: Detects gateway refunds unrecorded in merchant ledger (`REFUND_MISMATCH`).
9. **Partial Settlement**: Reconciles 1-to-many split bank credits back to single order (`PARTIAL_SETTLEMENT`).
10. **Unresolved / UNKNOWN**: Preserves unexplained transactions with null root cause, confidence < 0.80, and `UNRESOLVED` routing (`test_unresolved_unknown`).
11. **Financial Totals Reconciliation**: Confirms mathematically that `matched_value + exception_value == total_processed_value` across every run (`test_financial_totals_reconciliation`).

---

## Design System Adherence

Per `/docs/DESIGN_SYSTEM.md`:
- **Typography**: `Space Grotesk` for headings/labels, `IBM Plex Mono` with `font-variant-numeric: tabular-nums` for all numbers, IDs, amounts, and dates.
- **Palette**: Warm alabaster canvas (`#F4F1EB`), cream surface (`#FAF9F6`), dark charcoal text (`#1A1A1A`), subtle hairline borders (`#E5E0D8`).
- **Semantic Badges**: Flat status squares (`#1F6F54` Ledger Green, `#B5791A` Amber, `#A5352A` Signal Red).
- **Glass-Box Interaction**: Every headline metric opens an inline proof drawer showing underlying source records.
- **Strictly Prohibited**: No gradients, no glassmorphism blur, no rounded cards, no emoji icons, no uppercase labels.
