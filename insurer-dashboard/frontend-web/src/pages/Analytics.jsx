import { useState, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import RiskDonut from '../components/RiskDonut';
import { getAnalytics, getRiskDistribution, getClaims } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function Analytics() {
  const [stats, setStats] = useState({ totalShifts: 0, activePolicies: 0, claimsSubmitted: 0, payoutAmount: 0 });
  const [riskDistribution, setRiskDistribution] = useState({ low: 100, medium: 0, high: 0 });
  const [recentClaims, setRecentClaims] = useState([]);

  useEffect(() => {
    async function loadAnalytics() {
      try {
        const data = await getAnalytics();
        setStats(data);

        const risk = await getRiskDistribution();
        setRiskDistribution(risk);

        const list = await getClaims();
        setRecentClaims(list.slice(0, 4));
      } catch (err) {
        console.error('Failed to load analytics:', err);
      }
    }
    loadAnalytics();
    const interval = setInterval(loadAnalytics, 5000);
    return () => clearInterval(interval);
  }, []);

  const claimStatusData = [
    { name: 'Approved',     value: recentClaims.filter(c => c.status === 'APPROVED').length, color: '#10B981' },
    { name: 'Submitted',    value: recentClaims.filter(c => c.status === 'SUBMITTED').length, color: '#727687' },
    { name: 'Rejected',     value: recentClaims.filter(c => c.status === 'REJECTED').length, color: '#EF4444' },
  ];

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar title="Analytics" />
        <main className="flex-1 p-6">
          <div className="mb-6">
            <h2 className="text-[28px] font-bold text-on-surface">Analytics</h2>
            <p className="text-[14px] text-on-surface-variant mt-1">Platform health, claim metrics, and risk intelligence summary.</p>
          </div>

          {/* Top stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-6">
            {[
              { label: 'Total Shifts',      value: stats.totalShifts,         icon: 'speed',        color: 'text-primary' },
              { label: 'Total Policies',    value: stats.activePolicies,        icon: 'verified_user',color: 'text-secondary' },
              { label: 'Total Claims',      value: stats.claimsSubmitted,          icon: 'request_quote',color: 'text-status-warning' },
              { label: 'Total Payouts',     value: `₹${stats.payoutAmount.toFixed(0)}`, icon: 'timer',        color: 'text-status-safe' },
            ].map(s => (
              <div key={s.label} className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <div className="flex justify-between items-start mb-3">
                  <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-wide">{s.label}</p>
                  <span className={`material-symbols-outlined ${s.color}`} style={{ fontSize: 20 }}>{s.icon}</span>
                </div>
                <p className={`text-[32px] font-bold leading-none ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Risk distribution */}
            <div className="lg:col-span-6 bg-surface rounded-xl border border-surface-border shadow-sm p-5">
              <h3 className="text-[14px] font-bold text-on-surface mb-4">Risk Distribution</h3>
              <RiskDonut
                distribution={riskDistribution}
                totalLabel="Shifts"
                total={stats.totalShifts}
              />
            </div>

            {/* Claim status breakdown */}
            <div className="lg:col-span-6 bg-surface rounded-xl border border-surface-border shadow-sm p-5">
              <h3 className="text-[14px] font-bold text-on-surface mb-5">Claim Status Breakdown</h3>
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={claimStatusData} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e1e2ee" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#727687' }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#424656' }} tickLine={false} axisLine={false} width={90} />
                    <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #E2E8F0', borderRadius: 12, fontSize: 12 }} cursor={{ fill: '#f2f3ff' }} />
                    <Bar dataKey="value" name="Claims" radius={[0, 6, 6, 0]}>
                      {claimStatusData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Recent verified claims */}
            <div className="lg:col-span-12 bg-surface rounded-xl border border-surface-border shadow-sm p-5">
              <h3 className="text-[14px] font-bold text-on-surface mb-4">Recent Verified Incident Claims</h3>
              <div className="space-y-3">
                {recentClaims.map(c => (
                  <div key={c.id} className="flex items-center justify-between py-2 border-b border-surface-border last:border-b-0">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-status-emergency flex-shrink-0" />
                      <div>
                        <p className="text-[13px] font-semibold text-on-surface">{c.claimNumber}</p>
                        <p className="text-[11px] text-on-surface-variant">Rider: {c.rider?.fullName || 'Gig Rider'}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-[14px] font-bold text-status-safe">
                        ₹{c.claimedAmount ? c.claimedAmount.toFixed(2) : '0.00'}
                      </p>
                      <p className="text-[10px] text-on-surface-variant">{c.status}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
