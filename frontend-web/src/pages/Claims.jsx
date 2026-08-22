import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { CLAIMS, getRiderById, getShiftById } from '../data/mockData';

export default function Claims() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  const statuses = ['ALL', 'UNDER_REVIEW', 'PENDING', 'APPROVED', 'REJECTED'];

  const filtered = CLAIMS
    .filter(c => filter === 'ALL' || c.status === filter)
    .filter(c => {
      if (!search) return true;
      const rider = getRiderById(c.riderId);
      const q = search.toLowerCase();
      return c.id.toLowerCase().includes(q) || rider?.name.toLowerCase().includes(q) || c.location.toLowerCase().includes(q);
    });

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar title="Claims Ledger" />
        <main className="flex-1 p-6">

          {/* Page header */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
            <div>
              <h2 className="text-[28px] font-bold text-on-surface">Active Claims</h2>
              <p className="text-[14px] text-on-surface-variant mt-1">Review and investigate reported incidents from the fleet.</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline" style={{ fontSize: 16 }}>search</span>
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search claims, riders…"
                  className="pl-9 pr-4 py-2 bg-surface border border-surface-border rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary w-56 transition-all"
                />
              </div>
              <button className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg text-[12px] font-bold hover:opacity-90 transition-opacity shadow-sm">
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>download</span>
                Export
              </button>
            </div>
          </div>

          {/* Filter tabs */}
          <div className="flex items-center gap-2 mb-5 flex-wrap">
            {statuses.map(s => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`px-4 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wide transition-all border ${
                  filter === s
                    ? 'bg-primary text-on-primary border-primary shadow-sm'
                    : 'bg-surface text-on-surface-variant border-surface-border hover:border-primary hover:text-primary'
                }`}
              >
                {s.replace(/_/g, ' ')}
              </button>
            ))}
          </div>

          {/* Claims Table */}
          <div className="bg-surface rounded-xl shadow-sm border border-surface-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-surface-border bg-surface-muted">
                    {['Claim ID', 'Rider Details', 'Date & Time', 'Location', 'Risk Level', 'Status', 'Severity', 'Action'].map((h, i) => (
                      <th key={h} className={`px-6 py-4 text-[11px] font-bold text-on-surface-variant uppercase tracking-wider ${i === 7 ? 'text-right' : ''}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center text-on-surface-variant text-[14px]">
                        <span className="material-symbols-outlined block mx-auto mb-2" style={{ fontSize: 32 }}>search_off</span>
                        No claims match your filter.
                      </td>
                    </tr>
                  ) : filtered.map(c => {
                    const rider = getRiderById(c.riderId);
                    return (
                      <tr
                        key={c.id}
                        className="hover:bg-surface-muted transition-colors group cursor-pointer"
                        onClick={() => navigate(`/claims/${c.id}`)}
                      >
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="font-bold text-[13px] text-on-surface">{c.id}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center text-on-secondary-container font-bold text-[11px] flex-shrink-0">
                              {rider?.initials}
                            </div>
                            <div>
                              <p className="text-[13px] font-semibold text-on-surface">{rider?.name}</p>
                              <p className="text-[11px] text-on-surface-variant">ID: {c.riderId}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <p className="text-[13px] text-on-surface">{c.dateDisplay}</p>
                          <p className="text-[11px] text-on-surface-variant">{c.timeDisplay}</p>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <p className="text-[13px] text-on-surface">{c.location?.split(',')[0]}</p>
                          <p className="text-[11px] text-on-surface-variant">{c.location?.split(',')[1]?.trim()}</p>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <StatusBadge status={c.riskLevel} size="sm" />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <StatusBadge status={c.status} size="sm" />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`text-[13px] font-semibold ${
                            c.riskLevel === 'HIGH' ? 'text-status-emergency'
                            : c.riskLevel === 'MEDIUM' ? 'text-status-warning'
                            : 'text-status-safe'
                          }`}>{c.severity}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <button
                            onClick={e => { e.stopPropagation(); navigate(`/claims/${c.id}`); }}
                            className={`px-4 py-2 rounded-lg text-[11px] font-bold transition-colors ${
                              c.status === 'UNDER_REVIEW'
                                ? 'bg-primary text-on-primary hover:opacity-90'
                                : 'bg-surface text-primary border border-primary hover:bg-primary-container hover:text-on-primary-container'
                            }`}
                          >
                            {c.status === 'APPROVED' || c.status === 'REJECTED' ? 'View Details' : 'Investigate'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="px-6 py-4 border-t border-surface-border bg-surface flex items-center justify-between">
              <span className="text-[13px] text-on-surface-variant">Showing {filtered.length} of {CLAIMS.length} claims</span>
              <div className="flex gap-2">
                <button className="px-3 py-1.5 border border-surface-border rounded-lg text-on-surface-variant text-[12px] hover:bg-surface-muted disabled:opacity-40" disabled>Prev</button>
                <button className="px-3 py-1.5 bg-primary text-on-primary rounded-lg text-[12px] font-bold">1</button>
                <button className="px-3 py-1.5 border border-surface-border rounded-lg text-on-surface-variant text-[12px] hover:bg-surface-muted">Next</button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
