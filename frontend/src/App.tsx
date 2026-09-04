import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Landing } from './pages/Landing';
import { Overview } from './pages/Overview';
import { Reconciliation } from './pages/Reconciliation';
import { ExceptionCenter } from './pages/ExceptionCenter';
import { ExceptionDetail } from './pages/ExceptionDetail';
import { PatternInsights } from './pages/PatternInsights';
import { AuditLog } from './pages/AuditLog';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Entry Landing Page (Vesper.ai Operational AI Infrastructure) */}
        <Route path="/" element={<Landing />} />

        {/* Operational Controller Console */}
        <Route element={<Layout />}>
          <Route path="overview" element={<Overview />} />
          <Route path="reconciliation" element={<Reconciliation />} />
          <Route path="exceptions" element={<ExceptionCenter />} />
          <Route path="exceptions/:id" element={<ExceptionDetail />} />
          <Route path="pattern-insights" element={<PatternInsights />} />
          <Route path="audit-log" element={<AuditLog />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
