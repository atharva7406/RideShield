import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import RiskDonut from '../components/RiskDonut';
import IncidentHeatmap from '../components/IncidentHeatmap';
import { CLAIMS, RIDERS, getRiderById } from '../data/mockData';

const INITIAL_STATS = { activeShifts: 3, activePolicies: 5, totalClaims: 6, verifiedIncidents: 5 };

export default function Dashboard() {
  const navigate = useNavigate();
  const [claims, setClaims] = useState(CLAIMS);
  const [alertVisible, setAlertVisible] = useState(true);
  const [simulating, setSimulating] = useState(false);

  function handleSimulateCrash() {
    setSimulating(true);
    setTimeout(() => {
      const newClaim = {
        id: `CLM-LIVE-${Date.now()}`,
        riderId: 'RDR-2287',
        timestamp: new Date().toISOString(),
        dateDisplay: 'Just now',
        timeDisplay: new Date().toLocaleTimeString('en-IN') + ' IST',
        location: 'LIVE: Andheri East, Mumbai',
        riskLevel: 'HIGH',
        status: 'UNDER_REVIEW',
        severity: 'Severe Impact',
        crashConfidence: 94,
        riskScore: 79,
        _isNew: true,
      };
      setClaims(prev => [newClaim, ...prev]);
      setSimulating(false);
      setAlertVisible(true);
    }, 1500);
  }

  const recentClaims = claims.slice(0, 3);

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar title="Dashboard Overview" />
        <main className="flex-1 p-6 max-w-[1440px] mx-auto w-full">

          {/* Page header */}
          <div className="mb-6 flex justify-between items-end">
            <div>
              <h2 className="text-[28px] font-bold text-on-background">Dashboard Overview</h2>
              <p className="text-[14px] text-on-surface-variant mt-1">Real-time telemetry and claims status across active regions.</p>
            </div>
            <div className="flex items-center gap-2 text-[13px] text-on-surface-variant">
              <span className="w-2 h-2 rounded-full bg-status-safe animate-pulse" />
              System Live
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
            <StatCard label="Active Shifts"     value={INITIAL_STATS.activeShifts + (simulating ? 0 : 0)} subtext="+12% from last hour" badge="trending_up" icon="speed"         iconBg="text-primary" />
            <StatCard label="Active Policies"   value={INITIAL_STATS.activePolicies}  subtext="Stable coverage"         badge="remove"      icon="verified_user"  iconBg="text-secondary" />
            <StatCard label="Total Claims"      value={claims.length}                  subtext="2 pending review"        badge="info"        icon="request_quote"  iconBg="text-status-warning" />
            <StatCard label="Verified Incidents" value={INITIAL_STATS.verifiedIncidents} subtext="Requires attention"   badge="warning"     icon="report_problem" iconBg="text-status-emergency" highlight />
          </div>

          {/* Main bento grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

            {/* Left 8 cols */}
            <div className="lg:col-span-8 flex flex-col gap-5">

              {/* Recent Claims Table */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b border-surface-border flex justify-between items-center">
                  <h3 className="text-[16px] font-bold text-on-background">Recent Claims</h3>
                  <button
                    onClick={() => navigate('/claims')}
                    className="text-primary text-[12px] font-semibold hover:underline flex items-center gap-1"
                  >
                    View All <span className="material-symbols-outlined" style={{ fontSize: 14 }}>arrow_forward</span>
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-surface-muted text-on-surface-variant text-[11px] font-bold uppercase tracking-wider">
                        <th className="px-6 py-3">Claim ID</th>
                        <th className="px-6 py-3">Rider</th>
                        <th className="px-6 py-3">Time &amp; Location</th>
                        <th className="px-6 py-3 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border text-[13px]">
                      {recentClaims.map(c => {
                        const rider = getRiderById(c.riderId);
                        return (
                          <tr
                            key={c.id}
                            onClick={() => c.shiftId && navigate(`/claims/${c.id}`)}
                            className={`hover:bg-surface-muted transition-colors cursor-pointer group ${c._isNew ? 'animate-slide-in' : ''}`}
                          >
                            <td className="px-6 py-4 font-bold text-primary group-hover:underline">{c.id}</td>
                            <td className="px-6 py-4 text-on-background">
                              <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center text-[11px] font-bold text-on-surface-variant flex-shrink-0">
                                  {rider?.initials || '??'}
                                </div>
                                {rider?.name || c.riderId}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-on-surface-variant">
                              <div className="text-[13px]">{c.timeDisplay || c.dateDisplay}</div>
                              <div className="text-[11px] text-outline">{c.location}</div>
                            </td>
                            <td className="px-6 py-4 text-right">
                              <StatusBadge status={c.status} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Live Incident Heatmap */}
              <IncidentHeatmap />
            </div>

            {/* Right 4 cols */}
            <div className="lg:col-span-4 flex flex-col gap-5">

              {/* Priority Alert / Live Feed */}
              {alertVisible && (
                <div className="bg-surface rounded-xl border border-error-container shadow-md overflow-hidden relative animate-fade-in">
                  <div className="absolute top-0 left-0 w-full h-1 bg-status-emergency animate-pulse" />
                  <div className="p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="material-symbols-outlined text-status-emergency" style={{ fontVariationSettings: "'FILL' 1", fontSize: 22 }}>emergency</span>
                      <h3 className="text-[15px] font-bold text-status-emergency">Priority Alert</h3>
                      <button
                        onClick={() => setAlertVisible(false)}
                        className="ml-auto text-on-surface-variant hover:text-on-surface"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                      </button>
                    </div>
                    <div className="bg-error-container/30 rounded-lg p-4 border border-error-container/50">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] font-bold uppercase bg-error-container text-on-error-container px-2 py-0.5 rounded tracking-wide">New Claim</span>
                        <span className="text-[11px] text-on-surface-variant flex items-center gap-1">
                          <span className="material-symbols-outlined" style={{ fontSize: 13 }}>schedule</span> 2m ago
                        </span>
                      </div>
                      <p className="text-[13px] text-on-background font-medium mb-3">
                        Verified accident at Worli Naka, Mumbai. High G-force impact recorded. Crash confidence: <strong>94%</strong>
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => navigate('/claims/CLM-001')}
                          className="flex-1 bg-status-emergency text-on-error py-2 rounded-lg text-[12px] font-bold hover:bg-status-emergency/90 transition-colors"
                        >
                          Investigate
                        </button>
                      </div>
                    </div>

                    {/* Simulate crash button */}
                    <button
                      onClick={handleSimulateCrash}
                      disabled={simulating}
                      className="mt-3 w-full border border-dashed border-outline-variant text-on-surface-variant hover:border-primary hover:text-primary py-2 rounded-lg text-[11px] font-semibold transition-colors flex items-center justify-center gap-2"
                    >
                      {simulating ? (
                        <><span className="material-symbols-outlined animate-spin" style={{ fontSize: 14 }}>progress_activity</span> Simulating…</>
                      ) : (
                        <><span className="material-symbols-outlined" style={{ fontSize: 14 }}>play_circle</span> Simulate New Crash</>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {/* Risk Distribution */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6 flex-1">
                <h3 className="text-[16px] font-bold text-on-background mb-5">Current Risk Distribution</h3>
                <RiskDonut
                  distribution={{ low: 75, medium: 20, high: 5 }}
                  totalLabel="Shifts"
                  total={1248}
                />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
