import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ReconciliationRecordItem } from '../api/types';
import { StatusIndicator } from '../components/StatusIndicator';
import { formatCurrency, formatConfidence } from '../utils/formatters';
import { MonoText } from '../components/MonoText';

export const Reconciliation: React.FC = () => {
  const [records, setRecords] = useState<ReconciliationRecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    let active = true;
    const fetchInit = async () => {
      try {
        const data = await api.getRecords({ limit: 300 });
        if (active) {
          setRecords(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load reconciliation records');
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

  const filteredRecords = records.filter((rec) => {
    if (sourceFilter !== 'ALL' && (rec.record_a_source || '').toLowerCase() !== sourceFilter.toLowerCase()) {
      return false;
    }
    if (statusFilter !== 'ALL' && rec.classification !== statusFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchA = rec.record_a_id.toLowerCase().includes(q);
      const matchB = (rec.record_b_id || '').toLowerCase().includes(q);
      const matchSrc = (rec.record_a_source || '').toLowerCase().includes(q);
      if (!matchA && !matchB && !matchSrc) return false;
    }
    return true;
  });

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
            Reconciliation records
          </h1>
          <p style={{ fontSize: '12px', color: '#6A727D', marginTop: '3px' }}>
            Multi-level matching across Razorpay, bank statements, merchant ledger, and processor settlement reports.
          </p>
        </div>

        <div style={{ fontSize: '12px', color: '#6A727D' }}>
          Showing <MonoText>{filteredRecords.length}</MonoText> of <MonoText>{records.length}</MonoText> records
        </div>
      </header>

      {/* Filter Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-line)',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Search:</span>
          <input
            type="text"
            placeholder="Filter by transaction ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="filter-input"
            style={{ width: '220px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Source:</span>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="filter-select"
          >
            <option value="ALL">All sources</option>
            <option value="razorpay">Razorpay</option>
            <option value="bank">Bank statements</option>
            <option value="ledger">Merchant ledger</option>
            <option value="settlement">Settlement reports</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
          >
            <option value="ALL">All statuses</option>
            <option value="MATCHED">Matched</option>
            <option value="EXCEPTION">Exception</option>
            <option value="LIKELY_MATCH">Likely match</option>
            <option value="UNRESOLVED">Unresolved</option>
          </select>
        </div>

        {(sourceFilter !== 'ALL' || statusFilter !== 'ALL' || searchQuery) && (
          <button
            onClick={() => {
              setSourceFilter('ALL');
              setStatusFilter('ALL');
              setSearchQuery('');
            }}
            className="btn"
            style={{ fontSize: '11px', padding: '4px 8px', marginLeft: 'auto' }}
          >
            Clear filters
          </button>
        )}
      </div>

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

      {/* Dense Table */}
      <div style={{ border: '1px solid var(--color-line)', backgroundColor: 'var(--color-surface)', overflowX: 'auto' }}>
        <table className="dense-table">
          <thead>
            <tr>
              <th>Transaction ID</th>
              <th>Source</th>
              <th>Matched ID</th>
              <th>Source amount</th>
              <th>Matched amount</th>
              <th>Difference</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Match level</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  Loading reconciliation records...
                </td>
              </tr>
            ) : filteredRecords.length === 0 ? (
              <tr>
                <td colSpan={10} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  No records match the current filter criteria.
                </td>
              </tr>
            ) : (
              filteredRecords.map((rec) => (
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
                  <td>
                    {rec.classification !== 'MATCHED' ? (
                      <Link
                        to={`/exceptions/exc_${rec.record_a_id}`}
                        className="btn"
                        style={{ padding: '2px 6px', fontSize: '11px' }}
                      >
                        Inspect
                      </Link>
                    ) : (
                      <span style={{ fontSize: '11px', color: '#8A929B' }}>—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
