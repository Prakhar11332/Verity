import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ExceptionClusterResponse, ExceptionListItem, ClusterSummaryResponse } from '../api/types';
import { StatusIndicator } from '../components/StatusIndicator';
import { formatCurrency, formatConfidence } from '../utils/formatters';
import { MonoText } from '../components/MonoText';

export const PatternInsights: React.FC = () => {
  const [clusters, setClusters] = useState<ExceptionClusterResponse[]>([]);
  const [allExceptions, setAllExceptions] = useState<Record<string, ExceptionListItem>>({});
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null);
  const [clusterSummaries, setClusterSummaries] = useState<Record<string, ClusterSummaryResponse>>({});
  const [loadingSummaries, setLoadingSummaries] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const fetchInit = async () => {
      try {
        const [clusterData, excData] = await Promise.all([
          api.getClusters(),
          api.getExceptions({ limit: 250 }),
        ]);
        if (active) {
          setClusters(clusterData);
          const map: Record<string, ExceptionListItem> = {};
          excData.forEach((e) => {
            map[e.id] = e;
          });
          setAllExceptions(map);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load pattern insights');
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

  const toggleCluster = async (clusterId: string) => {
    if (expandedClusterId === clusterId) {
      setExpandedClusterId(null);
      return;
    }
    setExpandedClusterId(clusterId);

    // Fetch cluster summary if not yet loaded
    if (!clusterSummaries[clusterId] && !loadingSummaries[clusterId]) {
      try {
        setLoadingSummaries((prev) => ({ ...prev, [clusterId]: true }));
        const summary = await api.getClusterSummary(clusterId);
        setClusterSummaries((prev) => ({ ...prev, [clusterId]: summary }));
      } catch (err) {
        console.warn('Could not fetch cluster summary:', err);
      } finally {
        setLoadingSummaries((prev) => ({ ...prev, [clusterId]: false }));
      }
    }
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
            Pattern insights
          </h1>
          <p style={{ fontSize: '12px', color: '#6A727D', marginTop: '3px' }}>
            Systemic discrepancy clustering ranked by investigation priority score. Click any cluster to expand member records.
          </p>
        </div>

        <div style={{ fontSize: '12px', color: '#6A727D' }}>
          Identified clusters: <MonoText>{clusters.length}</MonoText>
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

      {/* Dense Cluster List per DESIGN_SYSTEM.md */}
      <div style={{ border: '1px solid var(--color-line)', backgroundColor: 'var(--color-surface)' }}>
        <table className="dense-table">
          <thead>
            <tr>
              <th style={{ width: '8%' }}>Priority</th>
              <th style={{ width: '22%' }}>Root cause</th>
              <th style={{ width: '18%' }}>Exception type</th>
              <th style={{ width: '10%' }}>Records</th>
              <th style={{ width: '14%' }}>Financial impact</th>
              <th style={{ width: '10%' }}>% of total</th>
              <th style={{ width: '10%' }}>Confidence</th>
              <th style={{ width: '8%' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  Analyzing discrepancy patterns...
                </td>
              </tr>
            ) : clusters.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: '#6A727D' }}>
                  No exception clusters detected.
                </td>
              </tr>
            ) : (
              clusters.map((cluster, idx) => {
                const isExpanded = expandedClusterId === cluster.cluster_id;
                const summary = clusterSummaries[cluster.cluster_id];
                const isLoadingSummary = loadingSummaries[cluster.cluster_id];

                return (
                  <React.Fragment key={cluster.cluster_id}>
                    <tr
                      onClick={() => toggleCluster(cluster.cluster_id)}
                      style={{
                        cursor: 'pointer',
                        backgroundColor: isExpanded ? '#F5F4EE' : undefined,
                      }}
                    >
                      <td>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 6px',
                            backgroundColor: idx === 0 ? 'var(--color-ink)' : '#EDECE8',
                            color: idx === 0 ? 'var(--color-paper)' : 'var(--color-ink)',
                            fontSize: '11px',
                            fontWeight: 600,
                          }}
                        >
                          <MonoText>P{idx + 1}</MonoText>
                        </span>
                      </td>
                      <td style={{ fontWeight: 500, color: 'var(--color-ink)' }}>
                        {cluster.root_cause || cluster.exception_type}
                      </td>
                      <td>
                        <MonoText>{cluster.exception_type}</MonoText>
                      </td>
                      <td>
                        <MonoText>{cluster.record_count}</MonoText>
                      </td>
                      <td style={{ fontWeight: 600, color: 'var(--color-signal-red)' }}>
                        <MonoText>{formatCurrency(cluster.total_financial_impact)}</MonoText>
                      </td>
                      <td>
                        <MonoText>{(cluster.pct_of_all_exceptions * 100).toFixed(1)}%</MonoText>
                      </td>
                      <td>
                        <MonoText>{formatConfidence(cluster.avg_confidence)}</MonoText>
                      </td>
                      <td>
                        <button
                          className="btn"
                          style={{ padding: '2px 7px', fontSize: '11px' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleCluster(cluster.cluster_id);
                          }}
                        >
                          {isExpanded ? 'Collapse' : 'Expand'}
                        </button>
                      </td>
                    </tr>

                    {/* Inline Expansion for Cluster Members */}
                    {isExpanded && (
                      <tr>
                        <td
                          colSpan={8}
                          style={{
                            padding: '0',
                            backgroundColor: '#FAF9F6',
                            borderBottom: '2px solid var(--color-ink)',
                          }}
                        >
                          <div style={{ padding: '16px 20px' }}>
                            {/* AI / Template Cluster Narrative */}
                            <div
                              style={{
                                padding: '12px 16px',
                                border: '1px solid var(--color-line)',
                                backgroundColor: 'var(--color-surface)',
                                marginBottom: '16px',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  marginBottom: '6px',
                                }}
                              >
                                <span style={{ fontSize: '12px', fontWeight: 600 }}>
                                  Pattern diagnosis & recommended remediation
                                </span>
                                {summary && (
                                  <span
                                    style={{
                                      fontSize: '10px',
                                      padding: '1px 5px',
                                      border: '1px solid var(--color-line)',
                                      color: '#6A727D',
                                    }}
                                  >
                                    Source: {summary.source === 'LLM' ? 'LLM (Gemini)' : 'Deterministic template'}
                                  </span>
                                )}
                              </div>

                              {isLoadingSummary ? (
                                <div style={{ fontSize: '12px', color: '#6A727D', fontStyle: 'italic' }}>
                                  Generating cluster synthesis...
                                </div>
                              ) : summary ? (
                                <p style={{ fontSize: '12px', lineHeight: 1.5, color: 'var(--color-ink)' }}>
                                  {summary.summary}
                                </p>
                              ) : (
                                <p style={{ fontSize: '12px', color: '#6A727D' }}>
                                  {cluster.recommended_action}
                                </p>
                              )}
                            </div>

                            {/* Member Exceptions List */}
                            <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px', color: 'var(--color-ink)' }}>
                              Cluster member exceptions ({cluster.exception_ids.length})
                            </div>

                            <table className="dense-table" style={{ border: '1px solid var(--color-line)' }}>
                              <thead>
                                <tr>
                                  <th>Exception ID</th>
                                  <th>Source record</th>
                                  <th>Financial impact</th>
                                  <th>Confidence</th>
                                  <th>Status</th>
                                  <th>Action</th>
                                </tr>
                              </thead>
                              <tbody>
                                {cluster.exception_ids.map((excId) => {
                                  const exc = allExceptions[excId];
                                  return (
                                    <tr key={excId}>
                                      <td>
                                        <Link to={`/exceptions/${excId}`} style={{ textDecoration: 'underline' }}>
                                          <MonoText>{excId}</MonoText>
                                        </Link>
                                      </td>
                                      <td>
                                        <MonoText>{exc ? exc.source_record_id : '—'}</MonoText>
                                      </td>
                                      <td>
                                        <MonoText>{exc ? formatCurrency(exc.financial_impact) : '—'}</MonoText>
                                      </td>
                                      <td>
                                        <MonoText>{exc ? formatConfidence(exc.confidence) : '—'}</MonoText>
                                      </td>
                                      <td>
                                        <StatusIndicator status={exc ? exc.resolution_status : 'PENDING'} />
                                      </td>
                                      <td>
                                        <Link
                                          to={`/exceptions/${excId}`}
                                          className="btn"
                                          style={{ padding: '2px 6px', fontSize: '11px' }}
                                        >
                                          Inspect
                                        </Link>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
