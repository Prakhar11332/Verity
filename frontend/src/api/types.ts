export interface ReconciliationSummaryResponse {
  run_id: string;
  created_at: string;
  total_records: number;
  matched_count: number;
  likely_match_count: number;
  exception_count: number;
  unresolved_count: number;
  match_rate: number;
  total_processed_value: string | number;
  matched_value: string | number;
  exception_value: string | number;
  unresolved_value: string | number;
  status: string;
}

export interface ReconciliationRecordItem {
  id: string;
  run_id: string;
  record_a_id: string;
  record_b_id?: string | null;
  match_score: number;
  match_level: string;
  classification: string;
  score_components?: Record<string, any> | null;
  created_at: string;
  record_a_amount?: string | number | null;
  record_a_source?: string | null;
  record_b_amount?: string | number | null;
  record_b_source?: string | null;
  difference?: string | number | null;
}

export interface ExceptionListItem {
  id: string;
  exception_type: string;
  root_cause?: string | null;
  financial_impact: string | number;
  confidence: number;
  resolution_status: string;
  recommended_action: string;
  source_record_id: string;
  matched_record_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceRecordDetail {
  transaction_id: string;
  source_name: string;
  amount: string | number;
  currency: string;
  transaction_date: string;
  settlement_date?: string | null;
  transaction_type: string;
  status: string;
  description?: string | null;
  merchant_id?: string | null;
  payment_id?: string | null;
  order_id?: string | null;
  settlement_id?: string | null;
  settlement_utr?: string | null;
  fee?: string | number | null;
  tax?: string | number | null;
  net_amount?: string | number | null;
  payment_method?: string | null;
  bank_reference?: string | null;
}

export interface AuditLogEntryResponse {
  id: string;
  timestamp: string;
  event_type: string;
  transaction_id?: string | null;
  exception_id?: string | null;
  action: string;
  actor: string;
  evidence?: any;
  details: string;
}

export interface ExceptionDetailResponse {
  id: string;
  exception_type: string;
  root_cause?: string | null;
  financial_impact: string | number;
  confidence: number;
  evidence: Array<{
    field?: string;
    value?: any;
    description?: string;
    [key: string]: any;
  }>;
  recommended_action: string;
  resolution_status: string;
  source_record_id: string;
  matched_record_id?: string | null;
  created_at: string;
  updated_at: string;
  source_record?: SourceRecordDetail | null;
  matched_record?: SourceRecordDetail | null;
  audit_trail: AuditLogEntryResponse[];
}

export interface ExceptionClusterResponse {
  cluster_id: string;
  exception_type: string;
  root_cause?: string | null;
  record_count: number;
  total_financial_impact: string | number;
  pct_of_all_exceptions: number;
  avg_confidence: number;
  recommended_action: string;
  exception_ids: string[];
  priority_score: number;
}

export interface ActionResponse {
  success: boolean;
  exception_id: string;
  new_status: string;
  message: string;
  audit_log_id: string;
}

export interface ExplanationResponse {
  exception_id: string;
  explanation: string;
  action_text: string;
  source: 'LLM' | 'TEMPLATE';
}

export interface ClusterSummaryResponse {
  cluster_id: string;
  summary: string;
  source: 'LLM' | 'TEMPLATE';
}

export interface DataQualityDimension {
  count: number;
  percentage: number;
  status: 'PASS' | 'FLAGGED';
  details: string;
}

export interface DataQualityResponse {
  overall_score: number;
  status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  total_records: number;
  clean_records: number;
  dimensions: {
    missing_ids: DataQualityDimension;
    duplicate_ids: DataQualityDimension;
    missing_amounts: DataQualityDimension;
    invalid_dates: DataQualityDimension;
  };
  last_analyzed: string;
}
