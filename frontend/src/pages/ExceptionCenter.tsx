import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ExceptionListItem } from '../api/types';
import { StatusIndicator } from '../components/StatusIndicator';
import { formatCurrency, formatConfidence } from '../utils/formatters';
import { MonoText } from '../components/MonoText';

type TabFilter = 'ALL' | 'HIGH_IMPACT' | 'AUTO_RESOLVE' | 'REVIEW_REQUIRED' | 'UNRESOLVED';

export const ExceptionCenter: React.FC = () => {
  const [exceptions, setExceptions] = useState<ExceptionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [activeTab, setActiveTab] = useState<TabFilter>('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    let active = true;
    const fetchInit = async () => {
      try {
        const data = await api.getExceptions({ limit: 200 });
        if (active) {
          setExceptions(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load exceptions');
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

  const filteredExceptions = exceptions.filter((exc) => {
    // Tab filter
    if (activeTab === 'HIGH_IMPACT') {
      const impact = parseFloat(String(exc.financial_impact));
      if (isNaN(impact) || impact < 10000) return false;
    } else if (activeTab === 'AUTO_RESOLVE') {
      if (exc.resolution_status !== 'AUTO_RESOLVE' && exc.resolution_status !== 'AUTO_RESOLVED' && exc.resolution_status !== 'APPROVED') {
        return false;
      }
    } else if (activeTab === 'REVIEW_REQUIRED') {
      if (exc.resolution_status !== 'REVIEW_REQUIRED' && exc.resolution_status !== 'PENDING') {
        return false;
      }
    } else if (activeTab === 'UNRESOLVED') {
      if (exc.resolution_status !== 'UNRESOLVED' && exc.resolution_status !== 'REJECTED') {
        return false;
      }
    }

    // Type filter
    if (typeFilter !== 'ALL' && exc.exception_type !== typeFilter) {
      return false;
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchId = exc.id.toLowerCase().includes(q);
      const matchSrc = exc.source_record_id.toLowerCase().includes(q);
      const matchCause = (exc.root_cause || '').toLowerCase().includes(q);
      if (!matchId && !matchSrc && !matchCause) return false;
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
            Exception center
          </h1>
          <p style={{ fontSize: '12px', color: '#6A727D', marginTop: '3px' }}>
            Queue of classified financial exceptions requiring automated rule routing or operator sign-off.
          </p>
        </div>

        <div style={{ fontSize: '12px', color: '#6A727D' }}>
          Total exceptions: <MonoText>{exceptions.length}</MonoText>
        </div>
      </header>

      {/* Quiet tab row per DESIGN_SYSTEM.md (not tabs-as-buttons) */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--color-line)',
          marginBottom: '16px',
        }}
      >
        {(
          [
            { key: 'ALL', label: 'All exceptions' },
            { key: 'HIGH_IMPACT', label: 'High impact (≥ ₹10,000)' },
            { key: 'AUTO_RESOLVE', label: 'Auto-resolvable' },
            { key: 'REVIEW_REQUIRED', label: 'Review required' },
            { key: 'UNRESOLVED', label: 'Unresolved' },
          ] as const
        ).map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                padding: '8px 16px',
                fontSize: '12px',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--color-ink)' : '#6A727D',
                backgroundColor: 'transparent',
                border: 'none',
                borderBottom: isActive ? '2px solid var(--color-ink)' : '2px solid transparent',
                cursor: 'pointer',
                fontFamily: 'var(--font-ui)',
                marginBottom: '-1px',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

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
            placeholder="Search by ID or root cause..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="filter-input"
            style={{ width: '240px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6A727D', fontWeight: 500 }}>Exception type:</span>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="filter-select"
          >
            <option value="ALL">All exception types</option>
            <option value="FEE_MISMATCH">Fee mismatch</option>
            <option value="SETTLEMENT_TIMING">Settlement timing</option>
            <option value="DUPLICATE_TRANSACTION">Duplicate transaction</option>
            <option value="MISSING_IN_BANK">Missing in bank</option>
            <option value="MISSING_IN_LEDGER">Missing in ledger</option>
            <option value="REFUND_MISMATCH">Refund mismatch</option>
            <option value="WRONG_REFERENCE">Wrong reference</option>
            <option value="PARTIAL_SETTLEMENT">Partial settlement</option>
            <option value="UNKNOWN">Unknown</option>
          </select>
        </div>

        <div style={{ marginLeft: 'auto', fontSize: '11px', color: '#6A727D' }}>
          Showing <MonoText>{filteredExceptions.length}</MonoText> exceptions
        </div>
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
              <th>Exception ID</th>
              <th>Type</th>
              <th>Root cause</th>
              <th>Financial impact</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Source record</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  Loading exception queue...
                </td>
              </tr>
            ) : filteredExceptions.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  No exceptions found matching the current filter.
                </td>
              </tr>
            ) : (
              filteredExceptions.map((exc) => (
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
                    <MonoText>{exc.source_record_id}</MonoText>
                  </td>
                  <td>
                    <Link
                      to={`/exceptions/${exc.id}`}
                      className="btn"
                      style={{ padding: '3px 8px', fontSize: '11px' }}
                    >
                      Investigate
                    </Link>
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
