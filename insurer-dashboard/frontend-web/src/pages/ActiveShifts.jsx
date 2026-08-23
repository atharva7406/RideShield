import { useState, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getActiveShifts } from '../services/api';

export default function ActiveShifts() {
  const [shifts, setShifts] = useState([]);

  useEffect(() => {
    async function loadShifts() {
      try {
        const list = await getActiveShifts();
        setShifts(list);
      } catch (err) {
        console.error('Failed to load active shifts:', err);
      }
    }
    loadShifts();
    const interval = setInterval(loadShifts, 5000);
    return () => clearInterval(interval);
  }, []);

  const activeCount = shifts.filter(s => s.status === 'ACTIVE').length;
  const endedCount = shifts.filter(s => s.status === 'COMPLETED').length;

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar title="Active Shifts" />
        <main className="flex-1 p-6">
          <div className="flex justify-between items-end mb-6">
            <div>
              <h2 className="text-[28px] font-bold text-on-surface">Active Shifts</h2>
              <p className="text-[14px] text-on-surface-variant mt-1">
                <span className="text-status-safe font-semibold">{activeCount} active</span> · {shifts.length} total shifts
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button className="flex items-center gap-2 px-4 py-2 bg-surface border border-surface-border rounded-lg text-[12px] font-semibold text-on-surface-variant hover:bg-surface-muted hover:text-primary transition-colors">
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>filter_list</span>
                Filter
              </button>
            </div>
          </div>

          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Active',  value: activeCount, color: 'text-status-safe',      dot: 'bg-status-safe' },
              { label: 'Ended',   value: endedCount,  color: 'text-on-surface-variant', dot: 'bg-outline' },
              { label: 'High Risk', value: 0, color: 'text-status-emergency', dot: 'bg-status-emergency' },
              { label: 'Total Shifts', value: shifts.length, color: 'text-on-surface', dot: 'bg-primary' },
            ].map(s => (
              <div key={s.label} className="bg-surface rounded-xl border border-surface-border shadow-sm p-4 flex items-center gap-3">
                <span className={`w-3 h-3 rounded-full flex-shrink-0 ${s.dot} ${s.label === 'Active' ? 'animate-pulse' : ''}`} />
                <div>
                  <p className={`text-[22px] font-bold leading-none ${s.color}`}>{s.value}</p>
                  <p className="text-[11px] text-on-surface-variant mt-1">{s.label}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Shifts Table */}
          <div className="bg-surface rounded-xl border border-surface-border shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-surface-border bg-surface-muted">
                    {['Shift ID', 'Rider', 'Start', 'Distance', 'Premium', 'Status'].map(h => (
                      <th key={h} className="px-5 py-4 text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {shifts.map(s => {
                    const initials = s.rider?.fullName ? s.rider.fullName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'GR';
                    return (
                      <tr key={s.id} className="hover:bg-surface-muted transition-colors">
                        <td className="px-5 py-4 whitespace-nowrap font-mono text-[12px] font-semibold text-primary">{s.id}</td>
                        <td className="px-5 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-secondary-container flex items-center justify-center text-[10px] font-bold text-on-secondary-container flex-shrink-0">
                              {initials}
                            </div>
                            <div>
                              <p className="text-[13px] font-semibold text-on-surface">{s.rider?.fullName || 'Gig Rider'}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-4 whitespace-nowrap text-[12px] text-on-surface">{new Date(s.startedAt).toLocaleTimeString('en-IN')}</td>
                        <td className="px-5 py-4 whitespace-nowrap text-[12px] text-on-surface">{s.distanceKm ? s.distanceKm.toFixed(2) : '0.00'} km</td>
                        <td className="px-5 py-4 whitespace-nowrap text-[13px] font-bold text-status-safe">₹{s.premiumPaidInr ? s.premiumPaidInr.toFixed(2) : '0.00'}</td>
                        <td className="px-5 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {s.status === 'ACTIVE' && <span className="w-2 h-2 bg-status-safe rounded-full animate-pulse" />}
                            <StatusBadge status={s.status} size="sm" />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
