import { useState, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getPolicies } from '../services/api';

export default function Policies() {
  const [policies, setPolicies] = useState([]);

  useEffect(() => {
    async function loadPolicies() {
      try {
        const list = await getPolicies();
        setPolicies(list);
      } catch (err) {
        console.error('Failed to load policies:', err);
      }
    }
    loadPolicies();
    const interval = setInterval(loadPolicies, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar title="Policies" />
        <main className="flex-1 p-6">
          <div className="flex justify-between items-end mb-6">
            <div>
              <h2 className="text-[28px] font-bold text-on-surface">Policies</h2>
              <p className="text-[14px] text-on-surface-variant mt-1">{policies.length} active shift-based micro-insurance policies.</p>
            </div>
            <button className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg text-[12px] font-bold hover:opacity-90 transition-opacity shadow-sm">
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>add</span>
              New Policy
            </button>
          </div>

          <div className="bg-surface rounded-xl border border-surface-border shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-surface-border bg-surface-muted">
                    {['Policy Number', 'Rider', 'Premium Paid', 'Start Date', 'End Date', 'Status'].map(h => (
                      <th key={h} className="px-5 py-4 text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {policies.map(p => {
                    const initials = p.rider?.fullName ? p.rider.fullName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'GR';
                    return (
                      <tr key={p.id} className="hover:bg-surface-muted transition-colors">
                        <td className="px-5 py-4 font-mono text-[12px] font-semibold text-primary">{p.policyNumber || 'N/A'}</td>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-secondary-container flex items-center justify-center text-[10px] font-bold text-on-secondary-container">
                              {initials}
                            </div>
                            <div>
                              <p className="text-[13px] font-semibold text-on-surface">{p.rider?.fullName || 'Gig Rider'}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-4 text-[13px] font-bold text-status-safe">₹{p.premiumPaidInr ? p.premiumPaidInr.toFixed(2) : '0.00'}</td>
                        <td className="px-5 py-4 text-[13px] text-on-surface">{new Date(p.startedAt).toLocaleString('en-IN')}</td>
                        <td className="px-5 py-4 text-[13px] text-on-surface">{p.endedAt ? new Date(p.endedAt).toLocaleString('en-IN') : 'Active Now'}</td>
                        <td className="px-5 py-4"><StatusBadge status={p.status} size="sm" /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Info note */}
          <div className="mt-4 flex items-start gap-2 bg-surface border border-surface-border rounded-xl px-5 py-4">
            <span className="material-symbols-outlined text-status-warning flex-shrink-0" style={{ fontSize: 16 }}>info</span>
            <p className="text-[12px] text-on-surface-variant leading-relaxed">
              <span className="font-semibold text-on-surface">Prototype mode.</span> RideShield acts as the risk-scoring and premium-collection layer. Full underwriting and payout settlement is provided by an IRDAI-licensed micro-insurance partner (future integration).
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
