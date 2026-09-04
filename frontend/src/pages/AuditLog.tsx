import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { AuditLogEntryResponse } from '../api/types';
import { formatDateTime } from '../utils/formatters';
import { MonoText } from '../components/MonoText';

export const AuditLog: React.FC = () => {
  const [entries, setEntries] = useState<AuditLogEntryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [txnFilter, setTxnFilter] = useState('');
  const [excFilter, setExcFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('ALL');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');

  const loadAuditLog = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditLog({
        transaction_id: txnFilter.trim() || undefined,
        exception_id: excFilter.trim() || undefined,
        event_type: eventTypeFilter !== 'ALL' ? eventTypeFilter : undefined,
        order: sortOrder,
        limit: 200,
      });
      setEntries(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load audit log');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    const fetchInit = async () => {
      try {
        const data = await api.getAuditLog({
          transaction_id: txnFilter.trim() || undefined,
          exception_id: excFilter.trim() || undefined,
          event_type: eventTypeFilter !== 'ALL' ? eventTypeFilter : undefined,
          order: sortOrder,
          limit: 200,
        });
        if (active) {
          setEntries(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load audit log');
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
  }, [sortOrder, eventTypeFilter, txnFilter, excFilter]);

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    loadAuditLog();
  };

  const handleResetFilters = () => {
    setTxnFilter('');
    setExcFilter('');
    setEventTypeFilter('ALL');
    setSortOrder('desc');
  };

  return (
    <div style={{ padding: '24px 32px' }}>
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
            Audit log
          </h1>
          <p style={{ fontSize: '12px', color: '#6A727D', marginTop: '3px' }}>
            Append-only chronological audit trail capturing automated rule executions, AI model outputs, and operator decisions.
          </p>
        </div>

        <div style={{ fontSize: '12px', color: '#6A727D' }}>
          Loaded entries: <MonoText>{entries.length}</MonoText>
        </div>
      </header>

      {/* Filter Toolbar */}
      <form
        onSubmit={handleApplyFilters}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-line)',
          marginBottom: '16px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Transaction ID:</span>
          <input
            type="text"
            placeholder="e.g. rzp_txn_00001"
            value={txnFilter}
            onChange={(e) => setTxnFilter(e.target.value)}
            className="filter-input"
            style={{ width: '160px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Exception ID:</span>
          <input
            type="text"
            placeholder="e.g. exc_rzp_txn_00001"
            value={excFilter}
            onChange={(e) => setExcFilter(e.target.value)}
            className="filter-input"
            style={{ width: '170px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Event type:</span>
          <select
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
            className="filter-select"
          >
            <option value="ALL">All event types</option>
            <option value="EXCEPTION_CLASSIFIED">Exception classified</option>
            <option value="RESOLUTION_APPROVED">Resolution approved</option>
            <option value="RESOLUTION_REJECTED">Resolution rejected</option>
            <option value="RESOLUTION_UNRESOLVED">Resolution unresolved</option>
            <option value="EXPLANATION_GENERATED">Explanation generated</option>
            <option value="CLUSTER_SUMMARY_GENERATED">Cluster summary generated</option>
            <option value="RECONCILIATION_RUN">Reconciliation run</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Sort:</span>
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as 'desc' | 'asc')}
            className="filter-select"
          >
            <option value="desc">Latest first (desc)</option>
            <option value="asc">Oldest first (asc)</option>
          </select>
        </div>

        <button type="submit" className="btn btn-primary" style={{ padding: '5px 12px', fontSize: '11px' }}>
          Filter
        </button>

        {(txnFilter || excFilter || eventTypeFilter !== 'ALL') && (
          <button
            type="button"
            onClick={handleResetFilters}
            className="btn"
            style={{ padding: '5px 10px', fontSize: '11px' }}
          >
            Reset
          </button>
        )}
      </form>

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

      {/* Dense Audit Trail Table */}
      <div style={{ border: '1px solid var(--color-line)', backgroundColor: 'var(--color-surface)', overflowX: 'auto' }}>
        <table className="dense-table">
          <thead>
            <tr>
              <th style={{ width: '16%' }}>Timestamp</th>
              <th style={{ width: '14%' }}>Actor</th>
              <th style={{ width: '16%' }}>Action</th>
              <th style={{ width: '12%' }}>Transaction ID</th>
              <th style={{ width: '14%' }}>Exception ID</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  Loading immutable audit log...
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  No audit log entries found matching criteria.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <MonoText>{formatDateTime(entry.timestamp)}</MonoText>
                  </td>
                  <td>
                    <span
                      style={{
                        fontSize: '11px',
                        padding: '1px 5px',
                        backgroundColor:
                          entry.actor === 'OPERATOR' || entry.actor.includes('LEAD')
                            ? '#EDECE8'
                            : '#F5F4F0',
                        border: '1px solid var(--color-line)',
                      }}
                    >
                      <MonoText>{entry.actor}</MonoText>
                    </span>
                  </td>
                  <td style={{ fontWeight: 500 }}>
                    <MonoText>{entry.action}</MonoText>
                  </td>
                  <td>
                    {entry.transaction_id ? (
                      <MonoText>{entry.transaction_id}</MonoText>
                    ) : (
                      <span style={{ color: '#8A929B' }}>—</span>
                    )}
                  </td>
                  <td>
                    {entry.exception_id ? (
                      <Link to={`/exceptions/${entry.exception_id}`} style={{ textDecoration: 'underline' }}>
                        <MonoText>{entry.exception_id}</MonoText>
                      </Link>
                    ) : (
                      <span style={{ color: '#8A929B' }}>—</span>
                    )}
                  </td>
                  <td style={{ fontSize: '12px' }}>{entry.details}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
