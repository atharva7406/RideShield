import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getClaims } from '../services/api';

export default function HospitalDashboard() {
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    async function load() {
      try {
        const data = await getClaims();
        setClaims(data);
      } catch (err) {
        console.error('Failed to load hospital claims:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="flex-1 flex flex-col min-h-screen">
        <Topbar />
        <main className="flex-1 p-6 max-w-[1440px] mx-auto w-full">
          <div className="mb-6 flex justify-between items-end">
            <div>
              <h1 className="text-[24px] font-bold text-on-surface">Hospital Dashboard</h1>
              <p className="text-on-surface-variant text-[14px]">Claims requiring medical attention in your locality.</p>
            </div>
          </div>

          <div className="bg-surface rounded-xl border border-surface-border shadow-sm overflow-hidden">
            {loading ? (
              <div className="p-12 flex justify-center"><span className="material-symbols-outlined animate-spin text-primary">progress_activity</span></div>
            ) : claims.length === 0 ? (
              <div className="p-12 text-center text-on-surface-variant flex flex-col items-center">
                <span className="material-symbols-outlined mb-2" style={{ fontSize: 32 }}>inbox</span>
                <p>No claims pending medical reports.</p>
              </div>
            ) : (
              <table className="w-full text-left text-[13px]">
                <thead className="bg-surface-muted border-b border-surface-border text-on-surface-variant uppercase tracking-wider text-[11px] font-bold">
                  <tr>
                    <th className="px-5 py-3">Claim No.</th>
                    <th className="px-5 py-3">Rider</th>
                    <th className="px-5 py-3">Filed At</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {claims.map(c => (
                    <tr key={c.id} className="hover:bg-surface-muted/50 transition-colors">
                      <td className="px-5 py-3 font-mono font-semibold text-primary">{c.claimNumber}</td>
                      <td className="px-5 py-3 font-medium text-on-surface">{c.rider?.fullName || 'Gig Rider'}</td>
                      <td className="px-5 py-3 text-on-surface-variant">{new Date(c.filedAt).toLocaleString('en-IN')}</td>
                      <td className="px-5 py-3"><StatusBadge status={c.status} /></td>
                      <td className="px-5 py-3 text-right">
                        <button onClick={() => navigate(`/hospital/claims/${c.id}`)} className="text-primary font-semibold hover:underline">
                          Upload Report
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
