import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ActiveShifts from './pages/ActiveShifts';
import Claims from './pages/Claims';
import ClaimDetails from './pages/ClaimDetails';
import Policies from './pages/Policies';
import Analytics from './pages/Analytics';

function ProtectedRoute({ children }) {
  const auth = localStorage.getItem('rs_auth');
  if (!auth) return <Navigate to="/login" replace />;
  return children;
}

function PlaceholderPage({ title }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-muted ml-[260px]">
      <div className="text-center">
        <span className="material-symbols-outlined text-on-surface-variant mb-3 block" style={{ fontSize: 48 }}>construction</span>
        <h2 className="text-[20px] font-bold text-on-surface">{title}</h2>
        <p className="text-on-surface-variant mt-2">This page is under construction.</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/dashboard"    element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/active-shifts" element={<ProtectedRoute><ActiveShifts /></ProtectedRoute>} />
        <Route path="/claims"       element={<ProtectedRoute><Claims /></ProtectedRoute>} />
        <Route path="/claims/:id"   element={<ProtectedRoute><ClaimDetails /></ProtectedRoute>} />
        <Route path="/policies"     element={<ProtectedRoute><Policies /></ProtectedRoute>} />
        <Route path="/analytics"    element={<ProtectedRoute><Analytics /></ProtectedRoute>} />
        <Route path="/settings"     element={<ProtectedRoute><PlaceholderPage title="Settings" /></ProtectedRoute>} />
        <Route path="/support"      element={<ProtectedRoute><PlaceholderPage title="Support" /></ProtectedRoute>} />
        <Route path="*"             element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
