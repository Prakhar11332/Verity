import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';

const navItems = [
  { path: '/overview', label: 'Overview' },
  { path: '/reconciliation', label: 'Reconciliation' },
  { path: '/exceptions', label: 'Exception center' },
  { path: '/pattern-insights', label: 'Pattern insights' },
  { path: '/audit-log', label: 'Audit log' },
];

export const Layout: React.FC = () => {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Left Nav Rail */}
      <aside
        style={{
          width: '220px',
          backgroundColor: 'var(--color-ink)',
          color: 'var(--color-paper)',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          borderRight: '1px solid var(--color-line)',
        }}
      >
        <div
          style={{
            padding: '24px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <div style={{ fontSize: '15px', fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--color-paper)' }}>
            Verity
          </div>
          <div style={{ fontSize: '11px', color: '#8A929B', marginTop: '2px' }}>
            Finance controller
          </div>
        </div>

        <nav style={{ padding: '16px 0', flex: 1 }}>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              style={({ isActive }) => ({
                display: 'block',
                padding: '10px 20px',
                fontSize: '13px',
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: isActive ? 500 : 400,
                color: isActive ? '#F6F5F1' : '#8A929B',
                backgroundColor: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
                borderLeft: isActive ? '3px solid #1F6F54' : '3px solid transparent',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div
          style={{
            padding: '16px 20px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            fontSize: '11px',
            color: '#6A727D',
          }}
        >
          <span className="tabular-nums">v0.1.0</span> / Track 04
        </div>
      </aside>

      {/* Main Content Area */}
      <main
        style={{
          flex: 1,
          backgroundColor: 'var(--color-paper)',
          overflowY: 'auto',
          minHeight: '100vh',
        }}
      >
        <Outlet />
      </main>
    </div>
  );
};
