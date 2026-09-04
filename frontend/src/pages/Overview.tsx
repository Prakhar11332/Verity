import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type {
  ReconciliationSummaryResponse,
  ReconciliationRecordItem,
  ExceptionListItem,
  DataQualityResponse,
} from '../api/types';
import { StatusIndicator } from '../components/StatusIndicator';
import { formatCurrency, formatConfidence, formatDateTime } from '../utils/formatters';
import { MonoText } from '../components/MonoText';

type ActiveMetric =
  | 'total_records'
  | 'match_rate'
  | 'exceptions'
  | 'financial_impact'
  | 'auto_resolved'
  | 'pending_review'
  | 'unresolved'
  | null;

export const Overview: React.FC = () => {
  const searchParams = new URLSearchParams(window.location.search);
  const initialMetric = searchParams.get('metric') as ActiveMetric;
  const hoverMetric = searchParams.get('hover');

  const [summary, setSummary] = useState<ReconciliationSummaryResponse | null>(null);
  const [records, setRecords] = useState<ReconciliationRecordItem[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionListItem[]>([]);
  const [dataQuality, setDataQuality] = useState<DataQualityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeMetric, setActiveMetric] = useState<ActiveMetric>(initialMetric);

  const loadData = useCallback(async () => {
    try {
      const [sumData, recData, excData, dqData] = await Promise.all([
        api.getSummary(),
        api.getRecords({ limit: 150 }),
        api.getExceptions({ limit: 150 }),
        api.getDataQuality(),
      ]);
      setSummary(sumData);
      setRecords(recData);
      setExceptions(excData);
      setDataQuality(dqData);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load reconciliation data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const fetchInit = async () => {
      try {
        const [sumData, recData, excData, dqData] = await Promise.all([
          api.getSummary(),
          api.getRecords({ limit: 150 }),
          api.getExceptions({ limit: 150 }),
          api.getDataQuality(),
        ]);
        if (active) {
          setSummary(sumData);
          setRecords(recData);
          setExceptions(excData);
          setDataQuality(dqData);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load reconciliation data');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    void fetchInit();
    return () => {
      active = false;
    };
  }, []);

  const handleRunReconciliation = async () => {
    try {
      setRunning(true);
      setError(null);
      await api.runReconciliation();
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to execute reconciliation run');
    } finally {
      setRunning(false);
    }
  };

  const toggleMetric = (metric: ActiveMetric) => {
    setActiveMetric((prev) => (prev === metric ? null : metric));
  };

  // Compute counts for auto-resolved, pending review, and unresolved from exceptions
  const autoResolvedCount = exceptions.filter(
    (e) => e.resolution_status === 'AUTO_RESOLVE' || e.resolution_status === 'AUTO_RESOLVED' || e.resolution_status === 'APPROVED'
  ).length;

  const pendingReviewCount = exceptions.filter(
    (e) => e.resolution_status === 'REVIEW_REQUIRED' || e.resolution_status === 'PENDING'
  ).length;

  const unresolvedCount = exceptions.filter(
    (e) => e.resolution_status === 'UNRESOLVED' || e.resolution_status === 'REJECTED'
  ).length;

  // Filter drilldown records based on active metric
  const getDrilldownContent = () => {
    if (!activeMetric) return null;

    if (activeMetric === 'total_records') {
      return {
        title: 'Total processed records',
        subtitle: `All ${records.length} canonical records ingested across Razorpay, Bank, Ledger, and Settlement sources.`,
        rule: 'Engine rule: Canonical multi-source ingestion',
        type: 'records' as const,
        items: records,
      };
    }

    if (activeMetric === 'match_rate') {
      const matched = records.filter((r) => r.classification === 'MATCHED');
      const ratePct = summary ? (summary.match_rate * 100).toFixed(1) : '0.0';
      return {
        title: `Matched transactions (${ratePct}%)`,
        subtitle: `${matched.length} transactions reconciled with 100% mathematical certainty across exact IDs and tolerances.`,
        rule: 'Engine rule: Level 1 (Exact primary ID) & Level 2 (Amount / date tolerance window)',
        type: 'records' as const,
        items: matched,
      };
    }

    if (activeMetric === 'exceptions') {
      return {
        title: `Reconciliation exceptions (${exceptions.length})`,
        subtitle: `Discrepancies identified and classified into deterministic root causes.`,
        rule: 'Engine rule: Deterministic 11-rule exception classifier',
        type: 'exceptions' as const,
        items: exceptions,
      };
    }

    if (activeMetric === 'financial_impact') {
      const impactExceptions = exceptions.filter((e) => parseFloat(String(e.financial_impact)) > 0);
      const totalImpact = summary ? formatCurrency(summary.exception_value) : '₹0.00';
      return {
        title: `Financial impact at risk (${totalImpact})`,
        subtitle: `${impactExceptions.length} exceptions carrying monetary variance requiring adjustment or recovery.`,
        rule: 'Engine rule: Arithmetic variance quantification (fee deductions, missing credits, refunds)',
        type: 'exceptions' as const,
        items: impactExceptions,
      };
    }

    if (activeMetric === 'auto_resolved') {
      const items = exceptions.filter(
        (e) => e.resolution_status === 'AUTO_RESOLVE' || e.resolution_status === 'AUTO_RESOLVED' || e.resolution_status === 'APPROVED'
      );
      return {
        title: `Auto-resolved exceptions (${items.length})`,
        subtitle: `High-confidence cases (≥ 95%) resolved automatically with deterministic evidence.`,
        rule: 'Engine rule: High-confidence routing (confidence >= 0.95 and full mathematical proof)',
        type: 'exceptions' as const,
        items,
      };
    }

    if (activeMetric === 'pending_review') {
      const items = exceptions.filter(
        (e) => e.resolution_status === 'REVIEW_REQUIRED' || e.resolution_status === 'PENDING'
      );
      return {
        title: `Review required (${items.length})`,
        subtitle: `Exceptions requiring human sign-off (confidence between 80% and 94%).`,
        rule: 'Engine rule: Human-in-the-loop operator review threshold',
        type: 'exceptions' as const,
        items,
      };
    }

    if (activeMetric === 'unresolved') {
      const items = exceptions.filter(
        (e) => e.resolution_status === 'UNRESOLVED' || e.resolution_status === 'REJECTED'
      );
      return {
        title: `Unresolved exceptions (${items.length})`,
        subtitle: `Transactions that could not be verified automatically and require manual audit.`,
        rule: 'Engine rule: Rule 11 strict catch-all (never auto-resolved by policy)',
        type: 'exceptions' as const,
        items,
      };
    }

    return null;
  };

  const drilldown = getDrilldownContent();

  return (
    <div style={{ padding: '24px 32px' }}>
      {/* Header bar */}
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '20px',
          borderBottom: '1px solid var(--color-line)',
          paddingBottom: '16px',
        }}
      >
        <div>
          <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)' }}>
            Overview
          </h1>
          <p style={{ fontSize: '12px', color: '#6A727D', marginTop: '3px' }}>
            Multi-source reconciliation metrics. Every number is an interactive proof button.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {summary && (
            <span style={{ fontSize: '11px', color: '#6A727D' }}>
              Run <MonoText>{summary.run_id}</MonoText> ({formatDateTime(summary.created_at)})
            </span>
          )}
          <button
            onClick={handleRunReconciliation}
            disabled={running}
            className="btn btn-primary"
            style={{ minWidth: '140px' }}
          >
            {running ? 'Reconciling...' : 'Run reconciliation'}
          </button>
        </div>
      </header>

      {error && (
        <div
          style={{
            padding: '10px 14px',
            backgroundColor: '#FBEBEA',
            border: '1px solid var(--color-signal-red)',
            color: 'var(--color-signal-red)',
            fontSize: '12px',
            marginBottom: '16px',
          }}
        >
          {error}
        </div>
      )}

      {/* The Glass-Box Metric Row: Plain horizontal strip, NOT individual cards */}
      <section
        style={{
          border: '1px solid var(--color-line)',
          backgroundColor: 'var(--color-surface)',
          marginBottom: activeMetric ? '0px' : '24px',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
          }}
        >
          {/* 1. Total Records */}
          <div
            onClick={() => toggleMetric('total_records')}
            className={`metric-cell ${activeMetric === 'total_records' ? 'active' : ''} ${hoverMetric === 'total_records' ? 'force-hover' : ''}`}
            title="Click to expand underlying canonical records"
          >
            <div className="metric-header">
              <span className="metric-label">Total records</span>
              <span className={`metric-glyph ${activeMetric === 'total_records' ? 'expanded' : ''}`}>
                {activeMetric === 'total_records' ? '−' : '+'}
              </span>
            </div>
            <div className="metric-value font-mono tabular-nums" style={{ color: 'var(--color-ink)' }}>
              {summary ? summary.total_records : '—'}
            </div>
            <div className="metric-caption">Across 4 sources</div>
          </div>

          {/* 2. Match Rate */}
          <div
            onClick={() => toggleMetric('match_rate')}
            className={`metric-cell ${activeMetric === 'match_rate' ? 'active' : ''} ${hoverMetric === 'match_rate' ? 'force-hover' : ''}`}
            title="Click to expand matched records proof"
          >
            <div className="metric-header">
              <span className="metric-label">Match rate</span>
              <span className={`metric-glyph ${activeMetric === 'match_rate' ? 'expanded' : ''}`}>
                {activeMetric === 'match_rate' ? '−' : '+'}
              </span>
            </div>
            <div className="metric-value font-mono tabular-nums" style={{ color: 'var(--color-ledger-green)' }}>
              {summary ? `${(summary.match_rate * 100).toFixed(1)}%` : '—'}
            </div>
            <div className="metric-caption">
              {summary ? `${summary.matched_count} matched records` : ''}
            </div>
          </div>

          {/* 3. Exceptions */}
          <div
            onClick={() => toggleMetric('exceptions')}
            className={`metric-cell ${activeMetric === 'exceptions' ? 'active' : ''} ${hoverMetric === 'exceptions' ? 'force-hover' : ''}`}
            title="Click to expand classified exceptions"
          >
            <div className="metric-header">
              <span className="metric-label">Exceptions</span>
              <span className={`metric-glyph ${activeMetric === 'exceptions' ? 'expanded' : ''}`}>
                {activeMetric === 'exceptions' ? '−' : '+'}
              </span>
            </div>
            <div className="metric-value font-mono tabular-nums" style={{ color: 'var(--color-signal-red)' }}>
              {summary ? summary.exception_count : '—'}
            </div>
            <div className="metric-caption">Classified discrepancies</div>
          </div>

          {/* 4. Financial Impact */}
          <div
            onClick={() => toggleMetric('financial_impact')}
            className={`metric-cell ${activeMetric === 'financial_impact' ? 'active' : ''} ${hoverMetric === 'financial_impact' ? 'force-hover' : ''}`}
            title="Click to expand value at risk breakdown"
          >
            <div className="metric-header">
              <span className="metric-label">Financial impact</span>
              <span className={`metric-glyph ${activeMetric === 'financial_impact' ? 'expanded' : ''}`}>
                {activeMetric === 'financial_impact' ? '−' : '+'}
              </span>
            </div>
            <div className="metric-value font-mono tabular-nums" style={{ color: 'var(--color-signal-red)' }}>
              {summary ? formatCurrency(summary.exception_value) : '—'}
            </div>
            <div className="metric-caption">Total value at risk</div>
          </div>

          {/* 5. Auto-resolved */}
          <div
            onClick={() => toggleMetric('auto_resolved')}
            className={`metric-cell ${activeMetric === 'auto_resolved' ? 'active' : ''} ${hoverMetric === 'auto_resolved' ? 'force-hover' : ''}`}
            title="Click to expand high-confidence auto-resolved cases"
          >
            <div className="metric-header">
              <span className="metric-label">Auto-resolved</span>
              <span className={`metric-glyph ${activeMetric === 'auto_resolved' ? 'expanded' : ''}`}>
                {activeMetric === 'auto_resolved' ? '−' : '+'}
              </span>
            </div>
            <div className="metric-value font-mono tabular-nums" style={{ color: 'var(--color-ledger-green)' }}>
              {autoResolvedCount}
            </div>
            <div className="metric-caption">High confidence (≥95%)</div>
          </div>

          {/* 6. Pending Review */}
          <div
            onClick={() => toggleMetric('pending_review')}
            className={`metric-cell ${activeMetric === 'pending_review' ? 'active' : ''} ${hoverMetric === 'pending_review' ? 'force-hover' : ''}`}
            title="Click to expand review required exceptions"
          >
            <div className="metric-header">
              <span className="metric-label">Pending review</span>
              <span className={`metric-glyph ${activeMetric === 'pending_review' ? 'expanded' : ''}`}>
                {activeMetric === 'pending_review' ? '−' : '+'}
              </span>
            </div>
            <div className="metric-value font-mono tabular-nums" style={{ color: 'var(--color-signal-amber)' }}>
              {pendingReviewCount}
            </div>
            <div className="metric-caption">Requires operator review</div>
          </div>

          {/* 7. Unresolved */}
          <div
            onClick={() => toggleMetric('unresolved')}
            className={`metric-cell ${activeMetric === 'unresolved' ? 'active' : ''} ${hoverMetric === 'unresolved' ? 'force-hover' : ''}`}
            title="Click to expand unresolved exceptions"
          >
            <div className="metric-header">
              <span className="metric-label">Unresolved</span>
              <span className={`metric-glyph ${activeMetric === 'unresolved' ? 'expanded' : ''}`}>
                {activeMetric === 'unresolved' ? '−' : '+'}
              </span>
            </div>
            <div className="metric-value font-mono tabular-nums" style={{ color: 'var(--color-signal-red)' }}>
              {unresolvedCount}
            </div>
            <div className="metric-caption">Rule 11 manual audit</div>
          </div>
        </div>
      </section>

      {/* The Inline Glass-Box Panel: Expands immediately below the metric row */}
      {activeMetric && drilldown && (
        <section
          className="glassbox-panel"
          style={{
            borderLeft: '1px solid var(--color-line)',
            borderRight: '1px solid var(--color-line)',
            marginBottom: '24px',
          }}
        >
          <div
            style={{
              padding: '14px 20px',
              borderBottom: '1px solid var(--color-line)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: '#F5F3EE',
            }}
          >
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-ink)' }}>
                {drilldown.title}
              </div>
              <div style={{ fontSize: '11px', color: '#6A727D', marginTop: '2px' }}>
                {drilldown.subtitle} — <span style={{ fontWeight: 500, color: 'var(--color-ink)' }}>{drilldown.rule}</span>
              </div>
            </div>
            <button
              onClick={() => setActiveMetric(null)}
              className="btn"
              style={{ padding: '4px 8px', fontSize: '11px' }}
            >
              Close proof panel
            </button>
          </div>

          <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
            {drilldown.type === 'records' ? (
              <table className="dense-table">
                <thead>
                  <tr>
                    <th>Record ID</th>
                    <th>Source</th>
                    <th>Matched ID</th>
                    <th>Source amount</th>
                    <th>Matched amount</th>
                    <th>Difference</th>
                    <th>Score</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(drilldown.items as ReconciliationRecordItem[]).map((rec) => (
                    <tr key={rec.id}>
                      <td>
                        <MonoText>{rec.record_a_id}</MonoText>
                      </td>
                      <td>{rec.record_a_source || '—'}</td>
                      <td>
                        <MonoText>{rec.record_b_id || 'None'}</MonoText>
                      </td>
                      <td>
                        <MonoText>{formatCurrency(rec.record_a_amount)}</MonoText>
                      </td>
                      <td>
                        <MonoText>{rec.record_b_amount ? formatCurrency(rec.record_b_amount) : '—'}</MonoText>
                      </td>
                      <td>
                        <MonoText>{rec.difference ? formatCurrency(rec.difference) : '₹0.00'}</MonoText>
                      </td>
                      <td>
                        <MonoText>{formatConfidence(rec.match_score)}</MonoText>
                      </td>
                      <td>
                        <StatusIndicator status={rec.classification} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="dense-table">
                <thead>
                  <tr>
                    <th>Exception ID</th>
                    <th>Type</th>
                    <th>Root cause</th>
                    <th>Financial impact</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(drilldown.items as ExceptionListItem[]).map((exc) => (
                    <tr key={exc.id}>
                      <td>
                        <Link to={`/exceptions/${exc.id}`} style={{ textDecoration: 'underline' }}>
                          <MonoText>{exc.id}</MonoText>
                        </Link>
                      </td>
                      <td>{exc.exception_type}</td>
                      <td>{exc.root_cause || '—'}</td>
                      <td>
                        <MonoText>{formatCurrency(exc.financial_impact)}</MonoText>
                      </td>
                      <td>
                        <MonoText>{formatConfidence(exc.confidence)}</MonoText>
                      </td>
                      <td>
                        <StatusIndicator status={exc.resolution_status} />
                      </td>
                      <td>
                        <Link to={`/exceptions/${exc.id}`} className="btn" style={{ padding: '3px 7px', fontSize: '11px' }}>
                          Inspect
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {/* Data Quality Score Panel */}
      <section
        style={{
          marginBottom: '24px',
          border: '1px solid var(--color-line)',
          backgroundColor: 'var(--color-surface)',
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--color-line)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#FAF9F6',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '8px',
                height: '8px',
                backgroundColor:
                  dataQuality?.status === 'HEALTHY'
                    ? 'var(--color-ledger-green)'
                    : dataQuality?.status === 'DEGRADED'
                    ? 'var(--color-signal-amber)'
                    : 'var(--color-signal-red)',
              }}
            />
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-ink)', margin: 0 }}>
              Data quality score
            </h2>
            <span style={{ fontSize: '12px', color: '#6A727D' }}>
              — Ingestion integrity across 4 financial source feeds
            </span>
          </div>
          {dataQuality && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: '#6A727D' }}>Overall integrity:</span>
              <MonoText style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-ink)' }}>
                {dataQuality.overall_score.toFixed(1)}%
              </MonoText>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  padding: '2px 6px',
                  border: '1px solid var(--color-line)',
                  backgroundColor: '#FFFFFF',
                  color:
                    dataQuality.status === 'HEALTHY'
                      ? 'var(--color-ledger-green)'
                      : 'var(--color-signal-amber)',
                }}
              >
                {dataQuality.status}
              </span>
            </div>
          )}
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
          }}
        >
          {/* Missing IDs */}
          <div style={{ padding: '14px 16px', borderRight: '1px solid var(--color-line)' }}>
            <div style={{ fontSize: '11px', color: '#6A727D', marginBottom: '6px' }}>Missing IDs</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '4px' }}>
              <MonoText style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)' }}>
                {dataQuality?.dimensions.missing_ids.count ?? 0}
              </MonoText>
              <span style={{ fontSize: '11px', color: '#6A727D' }}>
                (<MonoText>{(dataQuality?.dimensions.missing_ids.percentage ?? 0).toFixed(1)}%</MonoText>)
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#6A727D' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  backgroundColor:
                    dataQuality?.dimensions.missing_ids.status === 'PASS'
                      ? 'var(--color-ledger-green)'
                      : 'var(--color-signal-red)',
                  display: 'inline-block',
                }}
              />
              <span>
                {dataQuality?.dimensions.missing_ids.count === 0
                  ? 'Pass · 100% ID presence'
                  : `${dataQuality?.dimensions.missing_ids.count} unindexed IDs`}
              </span>
            </div>
          </div>

          {/* Duplicate IDs */}
          <div style={{ padding: '14px 16px', borderRight: '1px solid var(--color-line)' }}>
            <div style={{ fontSize: '11px', color: '#6A727D', marginBottom: '6px' }}>Duplicate IDs</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '4px' }}>
              <MonoText style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)' }}>
                {dataQuality?.dimensions.duplicate_ids.count ?? 0}
              </MonoText>
              <span style={{ fontSize: '11px', color: '#6A727D' }}>
                (<MonoText>{(dataQuality?.dimensions.duplicate_ids.percentage ?? 0).toFixed(1)}%</MonoText>)
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#6A727D' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  backgroundColor:
                    dataQuality?.dimensions.duplicate_ids.count === 0
                      ? 'var(--color-ledger-green)'
                      : 'var(--color-signal-amber)',
                  display: 'inline-block',
                }}
              />
              <span>
                {dataQuality?.dimensions.duplicate_ids.count === 0
                  ? 'Pass · Zero duplicates'
                  : `${dataQuality?.dimensions.duplicate_ids.count} duplicated keys flagged`}
              </span>
            </div>
          </div>

          {/* Missing Amounts */}
          <div style={{ padding: '14px 16px', borderRight: '1px solid var(--color-line)' }}>
            <div style={{ fontSize: '11px', color: '#6A727D', marginBottom: '6px' }}>Missing amounts</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '4px' }}>
              <MonoText style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)' }}>
                {dataQuality?.dimensions.missing_amounts.count ?? 0}
              </MonoText>
              <span style={{ fontSize: '11px', color: '#6A727D' }}>
                (<MonoText>{(dataQuality?.dimensions.missing_amounts.percentage ?? 0).toFixed(1)}%</MonoText>)
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#6A727D' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  backgroundColor:
                    dataQuality?.dimensions.missing_amounts.count === 0
                      ? 'var(--color-ledger-green)'
                      : 'var(--color-signal-red)',
                  display: 'inline-block',
                }}
              />
              <span>
                {dataQuality?.dimensions.missing_amounts.count === 0
                  ? 'Pass · 100% positive values'
                  : `${dataQuality?.dimensions.missing_amounts.count} null amounts`}
              </span>
            </div>
          </div>

          {/* Invalid Dates */}
          <div style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: '11px', color: '#6A727D', marginBottom: '6px' }}>Invalid dates</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '4px' }}>
              <MonoText style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)' }}>
                {dataQuality?.dimensions.invalid_dates.count ?? 0}
              </MonoText>
              <span style={{ fontSize: '11px', color: '#6A727D' }}>
                (<MonoText>{(dataQuality?.dimensions.invalid_dates.percentage ?? 0).toFixed(1)}%</MonoText>)
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#6A727D' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  backgroundColor:
                    dataQuality?.dimensions.invalid_dates.count === 0
                      ? 'var(--color-ledger-green)'
                      : 'var(--color-signal-red)',
                  display: 'inline-block',
                }}
              />
              <span>
                {dataQuality?.dimensions.invalid_dates.count === 0
                  ? 'Pass · All historical dates'
                  : `${dataQuality?.dimensions.invalid_dates.count} future or malformed`}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Reconciliation Records Table */}
      <section style={{ border: '1px solid var(--color-line)', backgroundColor: 'var(--color-surface)' }}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--color-line)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#FAF9F6',
          }}
        >
          <div>
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-ink)' }}>
              Recent reconciliation records
            </h2>
            <p style={{ fontSize: '11px', color: '#6A727D', marginTop: '1px' }}>
              Dense multi-level matched ledger entries with hairline borders and direct proof links.
            </p>
          </div>
          <Link to="/reconciliation" className="btn" style={{ fontSize: '11px', padding: '4px 10px' }}>
            View all records
          </Link>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="dense-table">
            <thead>
              <tr>
                <th>Record ID</th>
                <th>Source</th>
                <th>Matched ID</th>
                <th>Source amount</th>
                <th>Matched amount</th>
                <th>Difference</th>
                <th>Match score</th>
                <th>Classification</th>
                <th>Match level</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                    Loading reconciliation summary and canonical records...
                  </td>
                </tr>
              ) : (
                records.slice(0, 20).map((rec) => (
                  <tr key={rec.id}>
                    <td>
                      <MonoText>{rec.record_a_id}</MonoText>
                    </td>
                  <td>{rec.record_a_source || '—'}</td>
                  <td>
                    <MonoText>{rec.record_b_id || 'None'}</MonoText>
                  </td>
                  <td>
                    <MonoText>{formatCurrency(rec.record_a_amount)}</MonoText>
                  </td>
                  <td>
                    <MonoText>{rec.record_b_amount ? formatCurrency(rec.record_b_amount) : '—'}</MonoText>
                  </td>
                  <td>
                    <MonoText>{rec.difference ? formatCurrency(rec.difference) : '₹0.00'}</MonoText>
                  </td>
                  <td>
                    <MonoText>{formatConfidence(rec.match_score)}</MonoText>
                  </td>
                  <td>
                    <StatusIndicator status={rec.classification} />
                  </td>
                  <td style={{ fontSize: '11px', color: '#6A727D' }}>
                    <MonoText>{rec.match_level || '—'}</MonoText>
                  </td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
