import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ExceptionDetailResponse, ExplanationResponse, AuditLogEntryResponse } from '../api/types';
import { StatusIndicator } from '../components/StatusIndicator';
import { formatCurrency, formatConfidence, formatDateTime } from '../utils/formatters';
import { MonoText } from '../components/MonoText';

export const ExceptionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [exception, setException] = useState<ExceptionDetailResponse | null>(null);
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [auditTrail, setAuditTrail] = useState<AuditLogEntryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [explaining, setExplaining] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [actionNotes, setActionNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    const fetchInit = async () => {
      try {
        const data = await api.getExceptionDetail(id);
        if (active) {
          setException(data);
          setAuditTrail(data.audit_trail || []);
          setError(null);
        }

        try {
          if (active) setExplaining(true);
          const exp = await api.explainException(id);
          if (active) setExplanation(exp);
        } catch (expErr: unknown) {
          console.warn('Could not load initial explanation:', expErr);
        } finally {
          if (active) setExplaining(false);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load exception details');
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
  }, [id]);

  const handleRefreshExplanation = async () => {
    if (!id) return;
    try {
      setExplaining(true);
      const exp = await api.explainException(id);
      setExplanation(exp);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate explanation');
    } finally {
      setExplaining(false);
    }
  };

  const handleAction = async (action: 'approve' | 'reject' | 'unresolve') => {
    if (!id) return;
    try {
      setActionLoading(true);
      setActionMessage(null);

      let res;
      if (action === 'approve') {
        res = await api.approveException(id, actionNotes, 'OPERATOR');
      } else if (action === 'reject') {
        res = await api.rejectException(id, actionNotes, 'OPERATOR');
      } else {
        res = await api.unresolveException(id, actionNotes, 'OPERATOR');
      }

      setActionMessage({ type: 'success', text: res.message });
      setActionNotes('');

      // Refresh data
      const updated = await api.getExceptionDetail(id);
      setException(updated);
      setAuditTrail(updated.audit_trail || []);
    } catch (err: unknown) {
      setActionMessage({ type: 'error', text: err instanceof Error ? err.message : `Failed to ${action} exception` });
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !exception) {
    return (
      <div style={{ padding: '48px', textAlign: 'center', color: '#6A727D' }}>
        Loading exception details for <MonoText>{id}</MonoText>...
      </div>
    );
  }

  if (error && !exception) {
    return (
      <div style={{ padding: '32px' }}>
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: '#FBEBEA',
            border: '1px solid var(--color-signal-red)',
            color: 'var(--color-signal-red)',
            fontSize: '13px',
            marginBottom: '16px',
          }}
        >
          {error}
        </div>
        <Link to="/exceptions" className="btn">Back to exception center</Link>
      </div>
    );
  }

  if (!exception) return null;

  const srcRecord = exception.source_record;
  const matchRecord = exception.matched_record;

  const srcAmount = srcRecord ? parseFloat(String(srcRecord.amount)) : 0;
  const matchAmount = matchRecord ? parseFloat(String(matchRecord.amount)) : 0;
  const difference = Math.abs(srcAmount - matchAmount);

  return (
    <div style={{ padding: '24px 32px' }}>
      {/* Header */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <Link to="/exceptions" style={{ fontSize: '12px', color: '#6A727D', textDecoration: 'underline' }}>
              Exception center
            </Link>
            <span style={{ color: '#8A929B', fontSize: '11px' }}>/</span>
            <span style={{ fontSize: '12px', color: 'var(--color-ink)' }}>
              <MonoText>{exception.id}</MonoText>
            </span>
          </div>
          <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)' }}>
            {exception.root_cause || exception.exception_type}
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '4px' }}>
            <span style={{ fontSize: '12px', color: '#6A727D' }}>
              Type: <MonoText>{exception.exception_type}</MonoText>
            </span>
            <StatusIndicator status={exception.resolution_status} />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '20px', textAlign: 'right' }}>
          <div>
            <div style={{ fontSize: '11px', color: '#6A727D' }}>Financial impact</div>
            <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-signal-red)' }}>
              <MonoText>{formatCurrency(exception.financial_impact)}</MonoText>
            </div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#6A727D' }}>Confidence</div>
            <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)' }}>
              <MonoText>{formatConfidence(exception.confidence)}</MonoText>
            </div>
          </div>
        </div>
      </header>

      {actionMessage && (
        <div
          style={{
            padding: '10px 14px',
            backgroundColor: actionMessage.type === 'success' ? '#EEF6F2' : '#FBEBEA',
            border: `1px solid ${actionMessage.type === 'success' ? 'var(--color-ledger-green)' : 'var(--color-signal-red)'}`,
            color: actionMessage.type === 'success' ? 'var(--color-ledger-green)' : 'var(--color-signal-red)',
            fontSize: '12px',
            marginBottom: '16px',
          }}
        >
          {actionMessage.text}
        </div>
      )}

      {/* Operator Action Bar */}
      <section
        style={{
          border: '1px solid var(--color-line)',
          backgroundColor: 'var(--color-surface)',
          padding: '14px 18px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: 1, minWidth: '260px' }}>
          <input
            type="text"
            placeholder="Operator resolution notes (logged to immutable audit trail)..."
            value={actionNotes}
            onChange={(e) => setActionNotes(e.target.value)}
            className="filter-input"
            style={{ width: '100%' }}
          />
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => handleAction('approve')}
            disabled={actionLoading}
            className="btn btn-primary"
            style={{ backgroundColor: 'var(--color-ledger-green)', borderColor: 'var(--color-ledger-green)' }}
          >
            {actionLoading ? 'Processing...' : 'Approve resolution'}
          </button>

          <button
            onClick={() => handleAction('reject')}
            disabled={actionLoading}
            className="btn btn-danger"
          >
            {actionLoading ? 'Processing...' : 'Reject resolution'}
          </button>

          <button
            onClick={() => handleAction('unresolve')}
            disabled={actionLoading}
            className="btn"
          >
            {actionLoading ? 'Processing...' : 'Mark unresolved'}
          </button>
        </div>
      </section>

      {/* Difference Calculation Banner */}
      <section
        style={{
          border: '1px solid var(--color-line)',
          backgroundColor: '#FAF9F6',
          padding: '14px 18px',
          marginBottom: '24px',
        }}
      >
        <div style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500, marginBottom: '6px' }}>
          Deterministic difference calculation
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            fontSize: '13px',
            color: 'var(--color-ink)',
            flexWrap: 'wrap',
          }}
        >
          <div>
            Source: <MonoText>{formatCurrency(srcAmount)}</MonoText>
          </div>
          <span style={{ color: '#8A929B' }}>−</span>
          <div>
            Matched: <MonoText>{formatCurrency(matchAmount)}</MonoText>
          </div>
          <span style={{ color: '#8A929B' }}>=</span>
          <div style={{ fontWeight: 600, color: difference > 0 ? 'var(--color-signal-red)' : 'var(--color-ledger-green)' }}>
            Variance: <MonoText>{formatCurrency(difference)}</MonoText>
          </div>
          <div style={{ marginLeft: 'auto', fontSize: '11px', color: '#6A727D' }}>
            Root cause: <span style={{ fontWeight: 500, color: 'var(--color-ink)' }}>{exception.root_cause || exception.exception_type}</span>
          </div>
        </div>
      </section>

      {/* Side-by-Side Source Records Comparison */}
      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-ink)', marginBottom: '10px' }}>
          Source records comparison
        </h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '16px',
          }}
        >
          {/* Source Record (Record A) */}
          <div style={{ border: '1px solid var(--color-line)', backgroundColor: 'var(--color-surface)' }}>
            <div
              style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--color-line)',
                backgroundColor: '#FAF9F6',
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ fontSize: '12px', fontWeight: 600 }}>Source record (Gateway / Primary)</span>
              <span style={{ fontSize: '11px', color: '#6A727D' }}>
                <MonoText>{srcRecord?.source_name || 'Primary source'}</MonoText>
              </span>
            </div>
            {srcRecord ? (
              <table className="dense-table">
                <tbody>
                  <tr>
                    <td style={{ width: '38%', color: '#6A727D' }}>Transaction ID</td>
                    <td><MonoText>{srcRecord.transaction_id}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Amount</td>
                    <td><MonoText>{formatCurrency(srcRecord.amount)}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Fee & GST Tax</td>
                    <td>
                      <MonoText>
                        Fee: {formatCurrency(srcRecord.fee)} / Tax: {formatCurrency(srcRecord.tax)}
                      </MonoText>
                    </td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Net amount</td>
                    <td><MonoText>{formatCurrency(srcRecord.net_amount)}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Transaction date</td>
                    <td><MonoText>{srcRecord.transaction_date}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Settlement date</td>
                    <td><MonoText>{srcRecord.settlement_date || '—'}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>UTR / Reference</td>
                    <td><MonoText>{srcRecord.settlement_utr || srcRecord.bank_reference || '—'}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Status</td>
                    <td><StatusIndicator status={srcRecord.status} /></td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <div style={{ padding: '24px', textAlign: 'center', color: '#6A727D', fontSize: '12px' }}>
                No source record data available.
              </div>
            )}
          </div>

          {/* Matched Record (Record B) */}
          <div style={{ border: '1px solid var(--color-line)', backgroundColor: 'var(--color-surface)' }}>
            <div
              style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--color-line)',
                backgroundColor: '#FAF9F6',
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ fontSize: '12px', fontWeight: 600 }}>Matched record (Bank / Ledger)</span>
              <span style={{ fontSize: '11px', color: '#6A727D' }}>
                <MonoText>{matchRecord?.source_name || 'Counterparty'}</MonoText>
              </span>
            </div>
            {matchRecord ? (
              <table className="dense-table">
                <tbody>
                  <tr>
                    <td style={{ width: '38%', color: '#6A727D' }}>Transaction ID</td>
                    <td><MonoText>{matchRecord.transaction_id}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Amount</td>
                    <td><MonoText>{formatCurrency(matchRecord.amount)}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Fee & GST Tax</td>
                    <td>
                      <MonoText>
                        Fee: {formatCurrency(matchRecord.fee)} / Tax: {formatCurrency(matchRecord.tax)}
                      </MonoText>
                    </td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Net amount</td>
                    <td><MonoText>{formatCurrency(matchRecord.net_amount)}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Transaction date</td>
                    <td><MonoText>{matchRecord.transaction_date}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Settlement date</td>
                    <td><MonoText>{matchRecord.settlement_date || '—'}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>UTR / Reference</td>
                    <td><MonoText>{matchRecord.settlement_utr || matchRecord.bank_reference || '—'}</MonoText></td>
                  </tr>
                  <tr>
                    <td style={{ color: '#6A727D' }}>Status</td>
                    <td><StatusIndicator status={matchRecord.status} /></td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <div style={{ padding: '36px', textAlign: 'center', color: '#6A727D', fontSize: '12px' }}>
                No counterparty record found in target source within settlement window.
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Grounded Evidence List */}
      <section
        style={{
          border: '1px solid var(--color-line)',
          backgroundColor: 'var(--color-surface)',
          marginBottom: '24px',
        }}
      >
        <div
          style={{
            padding: '10px 14px',
            borderBottom: '1px solid var(--color-line)',
            backgroundColor: '#FAF9F6',
          }}
        >
          <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-ink)' }}>
            Deterministic rule evidence
          </h2>
        </div>
        <table className="dense-table">
          <thead>
            <tr>
              <th style={{ width: '22%' }}>Field</th>
              <th style={{ width: '30%' }}>Observed value</th>
              <th>Rule evaluation description</th>
            </tr>
          </thead>
          <tbody>
            {(exception.evidence || []).map((item, idx) => (
              <tr key={idx}>
                <td>
                  <MonoText>{item.field || `Evidence #${idx + 1}`}</MonoText>
                </td>
                <td>
                  <MonoText>
                    {typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}
                  </MonoText>
                </td>
                <td>{item.description || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Explainable AI Explanation */}
      <section
        style={{
          border: '1px solid var(--color-line)',
          backgroundColor: 'var(--color-surface)',
          padding: '16px 20px',
          marginBottom: '24px',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-ink)' }}>
              Operator narrative
            </h2>
            {explanation && (
              <span
                style={{
                  fontSize: '10px',
                  padding: '2px 6px',
                  border: '1px solid var(--color-line)',
                  backgroundColor: '#FAF9F6',
                  color: '#6A727D',
                }}
              >
                Source: {explanation.source === 'LLM' ? 'LLM (Gemini)' : 'Deterministic template'}
              </span>
            )}
          </div>
          <button
            onClick={handleRefreshExplanation}
            disabled={explaining}
            className="btn"
            style={{ fontSize: '11px', padding: '3px 8px' }}
          >
            {explaining ? 'Generating...' : 'Refresh explanation'}
          </button>
        </div>

        {explaining ? (
          <div style={{ fontSize: '12px', color: '#6A727D', fontStyle: 'italic' }}>
            Generating grounded natural language explanation...
          </div>
        ) : explanation ? (
          <div>
            <p style={{ fontSize: '13px', lineHeight: 1.5, color: 'var(--color-ink)', marginBottom: '10px' }}>
              {explanation.explanation}
            </p>
            <div
              style={{
                padding: '8px 12px',
                backgroundColor: '#F7F6F2',
                borderLeft: '2px solid var(--color-ink)',
                fontSize: '12px',
                color: 'var(--color-ink)',
              }}
            >
              <span style={{ fontWeight: 600 }}>Recommended action:</span> {explanation.action_text}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: '12px', color: '#6A727D' }}>
            No explanation loaded.{' '}
            <button
              onClick={handleRefreshExplanation}
              className="btn"
              style={{ fontSize: '11px', padding: '2px 6px', marginLeft: '6px' }}
            >
              Generate
            </button>
          </div>
        )}
      </section>

      {/* Immutable Audit Trail for this Record */}
      <section style={{ border: '1px solid var(--color-line)', backgroundColor: 'var(--color-surface)' }}>
        <div
          style={{
            padding: '10px 14px',
            borderBottom: '1px solid var(--color-line)',
            backgroundColor: '#FAF9F6',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-ink)' }}>
            Immutable audit trail
          </h2>
          <span style={{ fontSize: '11px', color: '#6A727D' }}>
            {auditTrail.length} recorded events
          </span>
        </div>

        <table className="dense-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Event type</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {auditTrail.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '20px', color: '#6A727D' }}>
                  No audit trail records found.
                </td>
              </tr>
            ) : (
              auditTrail.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <MonoText>{formatDateTime(entry.timestamp)}</MonoText>
                  </td>
                  <td>
                    <MonoText>{entry.actor}</MonoText>
                  </td>
                  <td style={{ fontWeight: 500 }}>
                    <MonoText>{entry.action}</MonoText>
                  </td>
                  <td style={{ fontSize: '11px', color: '#6A727D' }}>
                    <MonoText>{entry.event_type}</MonoText>
                  </td>
                  <td style={{ fontSize: '12px' }}>{entry.details}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
};
