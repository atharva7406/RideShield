import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import RiskDonut from '../components/RiskDonut';
import { ANALYTICS, CLAIMS } from '../data/mockData';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const STATUS_COLORS = {
  APPROVED: '#10B981', REJECTED: '#EF4444', PENDING: '#727687', UNDER_REVIEW: '#F59E0B',
};

export default function Analytics() {
  const claimStatusData = [
    { name: 'Approved',     value: ANALYTICS.approvedClaims,    color: '#10B981' },
    { name: 'Pending',      value: ANALYTICS.pendingClaims,     color: '#727687' },
    { name: 'Under Review', value: ANALYTICS.underReviewClaims, color: '#F59E0B' },
    { name: 'Rejected',     value: ANALYTICS.rejectedClaims,    color: '#EF4444' },
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
              { label: 'Total Shifts',      value: ANALYTICS.totalShifts,         icon: 'speed',        color: 'text-primary' },
              { label: 'Total Policies',    value: ANALYTICS.totalPolicies,        icon: 'verified_user',color: 'text-secondary' },
              { label: 'Total Claims',      value: ANALYTICS.totalClaims,          icon: 'request_quote',color: 'text-status-warning' },
              { label: 'Avg Response Time', value: ANALYTICS.avgResponseTime,      icon: 'timer',        color: 'text-status-safe' },
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

            {/* Claims by week bar chart */}
            <div className="lg:col-span-8 bg-surface rounded-xl border border-surface-border shadow-sm p-5">
              <h3 className="text-[14px] font-bold text-on-surface mb-5">Claims by Week</h3>
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ANALYTICS.claimsByWeek} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e1e2ee" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 11, fill: '#727687' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#727687' }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: '#ffffff', border: '1px solid #E2E8F0', borderRadius: 12, fontSize: 12 }}
                      cursor={{ fill: '#f2f3ff' }}
                    />
                    <Bar dataKey="claims" name="Claims" fill="#0050cb" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Risk distribution */}
            <div className="lg:col-span-4 bg-surface rounded-xl border border-surface-border shadow-sm p-5">
              <h3 className="text-[14px] font-bold text-on-surface mb-4">Risk Distribution</h3>
              <RiskDonut
                distribution={ANALYTICS.riskDistribution}
                totalLabel="Shifts"
                total={ANALYTICS.totalShifts}
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

            {/* Recent verified incidents */}
            <div className="lg:col-span-6 bg-surface rounded-xl border border-surface-border shadow-sm p-5">
              <h3 className="text-[14px] font-bold text-on-surface mb-4">Recent Verified Incidents</h3>
              <div className="space-y-3">
                {CLAIMS.filter(c => c.status !== 'REJECTED').slice(0, 4).map(c => (
                  <div key={c.id} className="flex items-center justify-between py-2 border-b border-surface-border last:border-b-0">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        c.riskLevel === 'HIGH' ? 'bg-status-emergency' : c.riskLevel === 'MEDIUM' ? 'bg-status-warning' : 'bg-status-safe'
                      }`} />
                      <div>
                        <p className="text-[13px] font-semibold text-on-surface">{c.id}</p>
                        <p className="text-[11px] text-on-surface-variant">{c.location}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-[14px] font-bold ${c.crashConfidence >= 80 ? 'text-status-emergency' : 'text-status-warning'}`}>
                        {c.crashConfidence}%
                      </p>
                      <p className="text-[10px] text-on-surface-variant">confidence</p>
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
