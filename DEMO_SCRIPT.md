# Verity — Judge Demo Script (3 to 5 Minutes)

> **The Novelty Hook**: *"Every number on this dashboard is provable. Watch."*  
> Follow this exact click-by-click sequence to present Verity to hackathon judges or executive stakeholders.

---

## Quick Reference & Live Numbers

| Metric | Live System Value | Visual Element |
| :--- | :--- | :--- |
| **Total Ingested Records** | `154 transactions` (`552 source rows`) | Metric Card 1 |
| **Match Rate** | `77.3%` | Metric Card 2 (Hero Click Target) |
| **Exceptions Flagged** | `35` | Metric Card 3 |
| **Financial Impact at Risk** | `₹277,880.82` | Metric Card 4 (Hero Click Target) |
| **Autonomous Resolutions** | `17` | Metric Card 5 |
| **Pending Review** | `15` | Metric Card 6 |
| **Unresolved Rule 11** | `3` | Metric Card 7 |

---

## Timing Overview

- **0:00 – 0:40 (40s)**: The Problem & One-Line Pitch
- **0:40 – 1:30 (50s)**: **Hero Moment #1 — The Glass-Box Numbers** (Clicking the Metrics)
- **1:30 – 2:30 (60s)**: Exception Center & Pattern Insights (Clustering by Root Cause)
- **2:30 – 3:30 (60s)**: Exception Detail, Deterministic Proof, and AI Explainer Fallback
- **3:30 – 4:15 (45s)**: Human-in-the-Loop Approval & Immutable Audit Trail
- **4:15 – 4:45 (30s)**: Architectural Integrity, Automated Test Rigor & Wrap-up

---

## Step-by-Step Presentation Sequence

### Act 1: The Problem & Live Ingestion (0:00 – 0:40)
**Screen**: Overview page (`http://localhost:5173/overview`)

1. **Say out loud**:
   > *"Modern fintechs and marketplaces reconcile millions of payments across gateways, bank statements, merchant ledgers, and settlement files. Most teams either pay for legacy 'black-box' software or write fragile batch scripts that output hundreds of uninvestigated spreadsheet rows."*
   >
   > *"Verity is an explainable finance controller that reconciles transactions across four independent financial sources, investigates every single exception for an undeniable root cause, quantifies the exact money at risk, and shows its work — where every number on screen is clickable proof, not a claim."*

2. **Action**: Point to the top header showing "Active run · 154 transactions".
3. **Say out loud**:
   > *"We ingested 154 transactions across four financial sources: Razorpay gateway, bank settlement statements, internal merchant ledger, and partner settlement files. Let's see what happened."*

---

### Act 2: Hero Moment #1 — The Glass-Box Interaction (0:40 – 1:30)
**Screen**: Overview page (`http://localhost:5173/overview`)

1. **Say out loud**:
   > *"Notice our headline metrics: we hit a 77.3% match rate. In a traditional black box, you have to take that number on faith. In Verity, there is no separate 'trust me' layer."*

2. **Action**: **CLICK ON THE MATCH RATE CARD (`77.3%`)**.
   - *Result*: The glass-box inline drawer expands immediately beneath the metric row with smooth zero-latency rendering, displaying the underlying transaction table with hairline borders, green ledger badges, and exact transaction IDs.

3. **Say out loud**:
   > *"Watch. I click 77.3%, and the interface immediately reveals the underlying records that prove that calculation. 119 records matched with 100% mathematical confidence across payment IDs, amounts, and settlement dates."*

4. **Action**: **CLICK ON THE EXCEPTIONS CARD (`35`) OR IMPACT CARD (`₹277,880.82`)**.
   - *Result*: The drawer switches live to reveal all 35 flagged exception records with their specific root cause, resolution status, and financial impact.

5. **Say out loud**:
   > *"I click ₹277,880.82 at risk, and here are the exact 35 exceptions contributing to that variance. Every single figure in Verity is directly connected to the raw ledger data."*

6. **Action**: Click the `✕ Close drawer` button or click the card again to collapse the panel.

---

### Act 3: Exception Center & Root-Cause Clustering (1:30 – 2:30)
**Screen**: Exception Center (`http://localhost:5173/exceptions`)

1. **Action**: Click **Exceptions** in the left navigation rail.
2. **Say out loud**:
   > *"Instead of hiding the remaining 22.7%, Verity investigates every exception autonomously. This isn't 35 disconnected rows — it's a discrete set of known root-cause patterns."*

3. **Action**: Scroll to the **Pattern Insights (Exception Clusters)** panel at the top.
4. **Say out loud**:
   > *"Our deterministic clustering engine groups exceptions by their mathematical failure signature. Look at this top cluster:
   > - Fee & Tax Mismatch: 8 records, ₹19,840 at risk.
   > - Duplicate Transactions: 7 records, ₹104,200 at risk.
   > - Settlement Timing Windows: 6 records, ₹0 capital loss because money arrived on T+2.
   >
   > Rather than investigating 35 separate tickets, a finance controller can understand the entire batch through 6 root-cause clusters."*

5. **Action**: Click on the **Auto-Resolvable** tab filter above the table, then switch to **Review Required**, and finally **Unresolved**.
6. **Say out loud**:
   > *"We route exceptions into three strict deterministic tiers:
   > 1. Auto-resolvable (confidence >= 95% with mathematical proof)
   > 2. Review Required (actionable discrepancy needing human sign-off)
   > 3. Unresolved (unidentified records that we NEVER guess on)."*

---

### Act 4: Exception Detail & Glass-Box AI Explanation (2:30 – 3:30)
**Screen**: Exception Detail (`/exceptions/:id`)

1. **Action**: Find an exception in the list (e.g. `exc_rzp_txn_00131_dup` or a `FEE_MISMATCH` exception) and click **Inspect**.
2. **Say out loud**:
   > *"Here is the Exception Detail screen. Notice the layout:
   > - Side-by-side source records showing Razorpay on the left and Bank on the right.
   > - The exact arithmetic difference calculated to the paisa.
   > - The deterministic evidence ledger showing the rule triggered."*

3. **Action**: Point to the **AI Root-Cause Briefing** card at the top.
4. **Say out loud**:
   > *"Here is how Verity uses AI. We adhere to a strict invariant: the LLM never calculates financial totals. All math is solved deterministically by Rules 1 through 10.
   >
   > Gemini 2.5 Flash synthesizes the evidence into an executive briefing and recommended ledger journal entry. And per our specification, if the Gemini API is unreachable or omitted, Verity instantly uses its zero-latency deterministic template fallback. The system never blocks on an external API."*

---

### Act 5: Human-in-the-Loop Resolution & Audit Trail (3:30 – 4:15)
**Screen**: Exception Detail action bar and Audit Log (`/audit`)

1. **Action**: Click the green **Approve Resolution** button.
   - *Result*: The status badge immediately flips to `APPROVED`, and a success toast appears.

2. **Say out loud**:
   > *"When the controller approves the action, Verity records an immutable audit trail entry recording the actor, timestamp, evidence payload, and financial impact."*

3. **Action**: Click **Audit Log** in the left navigation.
4. **Say out loud**:
   > *"Here is our chronological, tamper-evident audit log. Every single automated classification, AI generation, and human controller decision is logged with its exact evidence signature. External auditors can inspect every step."*

---

### Act 6: Automated Test Rigor & Wrap-up (4:15 – 4:45)
**Screen**: Overview page or Terminal

1. **Say out loud**:
   > *"Behind this dashboard is an airtight backend. All 63 automated tests pass with 100% coverage across exact matching, fuzzy transcription matching, amount mismatches, fee calculations, duplicate detection, and two-way missing transactions.
   >
   > Most importantly, the financial reconciliation invariant always holds:
   > `matched_value + exception_value == total_processed_value`
   >
   > Verity gives finance teams speed without sacrificing verification. Thank you."*

---

## Anticipated Judge Questions & Quick Answers

- **Q: Does the LLM ever hallucinate numbers or invent settlements?**  
  **A**: *"No. By architecture, the LLM is completely isolated from the calculation pipeline. It is only passed pre-computed, deterministic values (amounts, dates, confidence scores) and is instructed to generate natural-language explanations. If any returned number differs from the structured input, the response is discarded and our verified template fallback is used."*

- **Q: What happens if a payment appears in the bank statement but has no gateway record?**  
  **A**: *"Our two-way matching engine detects missing records in both directions. Rule 4 flags gateway payments missing from the bank; Rule 5 flags bank credits missing from the gateway as 'Unidentified bank transactions' and routes them for controller investigation."*

- **Q: How are fuzzy matches handled?**  
  **A**: *"Level 4 matching uses normalized Levenshtein token similarity on reference IDs for typos and manual entry errors. Any fuzzy match is classified as `LIKELY_MATCH` with scores strictly between 80% and 94% — our engine invariant guarantees a fuzzy match is NEVER silently promoted to a clean match without human confirmation."*
