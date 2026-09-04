from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ReconciliationSummaryResponse(BaseModel):
    run_id: str
    created_at: datetime
    total_records: int
    matched_count: int
    likely_match_count: int
    exception_count: int
    unresolved_count: int
    match_rate: float
    total_processed_value: Decimal
    matched_value: Decimal
    exception_value: Decimal
    unresolved_value: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRecordItem(BaseModel):
    id: str
    run_id: str
    record_a_id: str
    record_b_id: str | None = None
    match_score: float
    match_level: str
    classification: str
    score_components: dict[str, Any] | None = None
    created_at: datetime

    # Associated record details for table view
    record_a_amount: Decimal | None = None
    record_a_source: str | None = None
    record_b_amount: Decimal | None = None
    record_b_source: str | None = None
    difference: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class ExceptionListItem(BaseModel):
    id: str
    exception_type: str
    root_cause: str | None = None
    financial_impact: Decimal
    confidence: float
    resolution_status: str
    recommended_action: str
    source_record_id: str
    matched_record_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceRecordDetail(BaseModel):
    transaction_id: str
    source_name: str
    amount: Decimal
    currency: str
    transaction_date: date
    settlement_date: date | None = None
    transaction_type: str
    status: str
    description: str | None = None
    merchant_id: str | None = None
    payment_id: str | None = None
    order_id: str | None = None
    settlement_id: str | None = None
    settlement_utr: str | None = None
    fee: Decimal | None = None
    tax: Decimal | None = None
    net_amount: Decimal | None = None
    payment_method: str | None = None
    bank_reference: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    transaction_id: str | None = None
    exception_id: str | None = None
    action: str
    actor: str
    evidence: Any | None = None
    details: str

    model_config = ConfigDict(from_attributes=True)


class ExceptionDetailResponse(BaseModel):
    id: str
    exception_type: str
    root_cause: str | None = None
    financial_impact: Decimal
    confidence: float
    evidence: list[dict[str, Any]]
    recommended_action: str
    resolution_status: str
    source_record_id: str
    matched_record_id: str | None = None
    created_at: datetime
    updated_at: datetime
    source_record: SourceRecordDetail | None = None
    matched_record: SourceRecordDetail | None = None
    audit_trail: list[AuditLogEntryResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ExceptionClusterResponse(BaseModel):
    cluster_id: str
    exception_type: str
    root_cause: str | None = None
    record_count: int
    total_financial_impact: Decimal
    pct_of_all_exceptions: float
    avg_confidence: float
    recommended_action: str
    exception_ids: list[str]
    priority_score: float

    model_config = ConfigDict(from_attributes=True)


class ActionRequest(BaseModel):
    actor: str = "OPERATOR"
    notes: str | None = None


class ActionResponse(BaseModel):
    success: bool
    exception_id: str
    new_status: str
    message: str
    audit_log_id: str


class ExplanationResponse(BaseModel):
    exception_id: str
    explanation: str
    action_text: str
    source: str  # "LLM" | "TEMPLATE"


class ClusterSummaryResponse(BaseModel):
    cluster_id: str
    summary: str
    source: str  # "LLM" | "TEMPLATE"


class DataQualityDimension(BaseModel):
    count: int
    percentage: float
    status: str
    details: str


class DataQualityResponse(BaseModel):
    overall_score: float
    status: str
    total_records: int
    clean_records: int
    dimensions: dict[str, DataQualityDimension]
    last_analyzed: datetime

