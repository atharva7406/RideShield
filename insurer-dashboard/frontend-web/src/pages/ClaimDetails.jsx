import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getClaimDetails, updateClaimStatus, startClaimReview, downloadMedicalReport } from '../services/api';

export default function ClaimDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [claim, setClaim] = useState(null);
  const [loading, setLoading] = useState(true);
  const [approveLoading, setApproveLoading] = useState(false);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  async function loadDetails() {
    try {
      setLoading(true);
      const data = await getClaimDetails(id);
      setClaim(data);
    } catch (err) {
      console.error('Failed to load claim details:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setClaim(null);
    setShowEvidence(false);
    loadDetails();
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-screen bg-surface-muted">
        <Sidebar />
        <div className="flex-1 ml-[260px] flex items-center justify-center">
          <span className="material-symbols-outlined animate-spin text-primary" style={{ fontSize: 32 }}>progress_activity</span>
        </div>
      </div>
    );
  }

  if (!claim) {
    return (
      <div className="flex min-h-screen bg-surface-muted">
        <Sidebar />
        <div className="flex-1 ml-[260px] flex flex-col items-center justify-center">
          <span className="material-symbols-outlined text-on-surface-variant mb-4" style={{ fontSize: 48 }}>search_off</span>
          <h2 className="text-[20px] font-bold text-on-surface">Claim Not Found</h2>
          <p className="text-on-surface-variant mt-2 mb-6">Claim ID <strong>{id}</strong> does not exist.</p>
          <button onClick={() => navigate('/claims')} className="bg-primary text-on-primary px-6 py-2.5 rounded-lg font-semibold hover:opacity-90">
            Back to Claims
          </button>
        </div>
      </div>
    );
  }

  async function handleStartReview() {
    try {
      setReviewLoading(true);
      await startClaimReview(claim.id);
      await loadDetails();
    } catch (err) {
      console.error('Failed to start review:', err);
      alert(err.message || 'Failed to start review.');
    } finally {
      setReviewLoading(false);
    }
  }

  async function handleApprove() {
    try {
      setApproveLoading(true);
      await updateClaimStatus(claim.id, 'APPROVED');
      await loadDetails();
    } catch (err) {
      console.error('Approval failed:', err);
    } finally {
      setApproveLoading(false);
    }
  }

  async function handleReject() {
    try {
      setRejectLoading(true);
      await updateClaimStatus(claim.id, 'REJECTED');
      await loadDetails();
    } catch (err) {
      console.error('Rejection failed:', err);
    } finally {
      setRejectLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar />
        <main className="flex-1 p-6 max-w-[1440px] mx-auto w-full">

          {/* Back + Header */}
          <div className="mb-6">
            <button
              onClick={() => navigate('/claims')}
              className="flex items-center gap-1.5 text-on-surface-variant hover:text-primary text-[13px] font-semibold transition-colors mb-4 group"
            >
              <span className="material-symbols-outlined group-hover:-translate-x-0.5 transition-transform" style={{ fontSize: 18 }}>arrow_back</span>
              Back to Claims
            </button>

            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-[28px] font-bold text-on-surface">Claim Investigation</h1>
                  <span className="text-[22px] font-bold text-on-surface-variant">{claim.claimNumber}</span>
                  <StatusBadge status={claim.status} />
                </div>
                <p className="text-[13px] text-on-surface-variant mt-1">
                  Filed on {new Date(claim.filedAt).toLocaleString('en-IN')}
                </p>
              </div>

              {/* Actions */}
              {claim.status === 'UNDER_REVIEW' ? (
                <div className="flex items-center gap-3 flex-shrink-0">
                  <button
                    onClick={handleReject}
                    disabled={rejectLoading}
                    className="flex items-center gap-2 px-5 py-2.5 border border-error text-error rounded-lg text-[13px] font-bold hover:bg-error-container transition-colors disabled:opacity-60"
                  >
                    {rejectLoading ? <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>progress_activity</span> : <span className="material-symbols-outlined" style={{ fontSize: 16 }}>cancel</span>}
                    Reject Claim
                  </button>
                  <button
                    onClick={handleApprove}
                    disabled={approveLoading}
                    className="flex items-center gap-2 px-5 py-2.5 bg-status-safe text-white rounded-lg text-[13px] font-bold hover:opacity-90 transition-opacity shadow-sm disabled:opacity-60"
                  >
                    {approveLoading ? <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>progress_activity</span> : <span className="material-symbols-outlined" style={{ fontSize: 16 }}>check_circle</span>}
                    Approve Claim
                  </button>
                </div>
              ) : claim.status === 'MEDICAL_REPORT_SUBMITTED' || claim.status === 'SUBMITTED' ? (
                <div className="flex items-center gap-3 flex-shrink-0">
                  <button
                    onClick={handleStartReview}
                    disabled={reviewLoading}
                    className="flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-lg text-[13px] font-bold hover:opacity-90 transition-opacity shadow-sm disabled:opacity-60"
                  >
                    {reviewLoading ? <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>progress_activity</span> : <span className="material-symbols-outlined" style={{ fontSize: 16 }}>rate_review</span>}
                    Start Review
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-3 flex-shrink-0">
                  <div className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-[13px] font-bold ${
                    claim.status === 'APPROVED' ? 'bg-[#d1fae5] text-[#065f46]' : claim.status === 'REJECTED' ? 'bg-error-container text-on-error-container' : 'bg-[#fef3c7] text-[#92400e]'
                  }`}>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                      {claim.status === 'APPROVED' ? 'check_circle' : claim.status === 'REJECTED' ? 'cancel' : 'pending_actions'}
                    </span>
                    {claim.status === 'APPROVED' ? 'Claim Approved' : claim.status === 'REJECTED' ? 'Claim Rejected' : 'Need Medical Report'}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Main grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

            {/* LEFT: 8 cols */}
            <div className="lg:col-span-8 flex flex-col gap-5">

              {/* Rider + Shift Info Row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

                {/* Rider Info */}
                <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                  <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4 flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>person</span>
                    Rider Information
                  </h3>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center text-on-primary font-bold text-[16px] flex-shrink-0">
                      {claim.rider?.fullName ? claim.rider.fullName.slice(0, 2).toUpperCase() : 'GR'}
                    </div>
                    <div>
                      <p className="font-bold text-[16px] text-on-surface">{claim.rider?.fullName || 'Gig Rider'}</p>
                      <p className="text-[12px] text-on-surface-variant">ID: {claim.riderId}</p>
                    </div>
                  </div>
                  <div className="space-y-2 text-[13px]">
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Phone</span>
                      <span className="font-medium text-on-surface">{claim.rider?.phone || 'N/A'}</span>
                    </div>
                  </div>
                </div>

                {/* Shift Info */}
                <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                  <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4 flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>speed</span>
                    Shift Information
                  </h3>
                  <div className="space-y-2 text-[13px]">
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Shift ID</span>
                      <span className="font-mono font-semibold text-primary">{claim.shiftId}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* GPS Location */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>location_on</span>
                  GPS Location
                </h3>
                <div className="bg-surface-muted rounded-xl border border-surface-border relative overflow-hidden h-40 flex items-center justify-center">
                  <div className="absolute inset-0 bg-[#e8eaf0]" />
                  <div className="absolute inset-0" style={{
                    backgroundImage: 'repeating-linear-gradient(0deg,transparent,transparent 20px,#d0d3dc 20px,#d0d3dc 21px),repeating-linear-gradient(90deg,transparent,transparent 20px,#d0d3dc 20px,#d0d3dc 21px)',
                    opacity: 0.3,
                  }} />
                  <div className="absolute w-5 h-5 bg-status-emergency rounded-full border-4 border-white shadow-lg z-10 flex items-center justify-center">
                    <div className="w-2 h-2 bg-status-emergency rounded-full animate-ping" />
                  </div>
                  <div className="absolute top-3 right-3 bg-surface/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-surface-border text-[11px] z-20 text-right">
                    <p className="font-mono font-semibold text-on-surface">{claim.incident?.latitude?.toFixed(4)}°N, {claim.incident?.longitude?.toFixed(4)}°E</p>
                  </div>
                </div>
              </div>

              {/* Evidence Bundle */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>receipt_long</span>
                    Evidence Bundle
                  </h3>
                  <button
                    onClick={() => setShowEvidence(!showEvidence)}
                    className="text-primary text-[12px] font-semibold hover:underline flex items-center gap-1"
                  >
                    {showEvidence ? 'Hide' : 'Show'} raw data
                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{showEvidence ? 'expand_less' : 'expand_more'}</span>
                  </button>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                  {[
                    { label: 'Peak Acceleration (g)', value: claim.incident?.peakGForce ? `${claim.incident.peakGForce.toFixed(2)}G` : 'N/A', color: 'text-status-emergency' },
                    { label: 'Incident Confidence', value: claim.incident?.confidenceScore ? `${(claim.incident.confidenceScore * 100).toFixed(0)}%` : 'N/A', color: 'text-primary' },
                  ].map(m => (
                    <div key={m.label} className="bg-surface-muted rounded-lg p-3 border border-surface-border">
                      <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wide mb-1">{m.label}</p>
                      <p className={`text-[18px] font-bold ${m.color}`}>{m.value}</p>
                    </div>
                  ))}
                </div>

                {showEvidence && (
                  <pre className="bg-[#1e1e2e] text-[#cdd6f4] rounded-xl p-4 text-[11px] font-mono overflow-x-auto border border-surface-border animate-fade-in leading-relaxed">
{JSON.stringify(claim, null, 2)}
                  </pre>
                )}
              </div>

              {/* Medical Reports */}
              {claim.medicalReports && claim.medicalReports.length > 0 && (
                <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                  <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4 flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>medical_information</span>
                    Medical Reports
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {claim.medicalReports.map((report, idx) => (
                      <div key={idx} className="bg-surface-muted rounded-lg p-4 border border-surface-border">
                        <div className="flex justify-between items-start mb-2">
                          <p className="font-bold text-on-surface">{report.document_type}</p>
                          <span className="text-[11px] text-on-surface-variant font-medium">{new Date(report.uploaded_at).toLocaleDateString()}</span>
                        </div>
                        <p className="text-[12px] text-on-surface-variant mb-3">{report.notes || 'No additional notes provided.'}</p>
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              await downloadMedicalReport(claim.id, report.id);
                            } catch (err) {
                              alert(err.message || 'Failed to download report.');
                            }
                          }}
                          className="inline-flex items-center gap-1.5 text-[12px] font-bold text-primary hover:underline cursor-pointer"
                        >
                          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>download</span>
                          Download Document
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT: 4 cols */}
            <div className="lg:col-span-4 flex flex-col gap-5">

              {/* Crash Confidence */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5 text-center">
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4">Crash Confidence</h3>
                <div className="relative w-36 h-36 mx-auto mb-3">
                  <svg viewBox="0 0 100 100" className="w-full h-full transform -rotate-90">
                    <circle cx="50" cy="50" r="40" fill="transparent" stroke="#f2f3ff" strokeWidth="12" />
                    <circle
                      cx="50" cy="50" r="40" fill="transparent"
                      stroke={claim.incident?.confidenceScore >= 0.8 ? '#EF4444' : claim.incident?.confidenceScore >= 0.5 ? '#F59E0B' : '#10B981'}
                      strokeWidth="12"
                      strokeDasharray={`${(claim.incident?.confidenceScore * 251.2)} 251.2`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className={`text-[32px] font-bold leading-none ${claim.incident?.confidenceScore >= 0.8 ? 'text-status-emergency' : 'text-on-surface'}`}>
                      {claim.incident?.confidenceScore ? `${(claim.incident.confidenceScore * 100).toFixed(0)}%` : 'N/A'}
                    </span>
                    <span className="text-[11px] text-on-surface-variant mt-1">confidence</span>
                  </div>
                </div>
              </div>

              {/* Claim Status */}
              <div className={`rounded-xl border p-5 ${
                claim.status === 'APPROVED' ? 'bg-[#d1fae5] border-[#a7f3d0]'
                : claim.status === 'REJECTED' ? 'bg-error-container border-error-container'
                : 'bg-surface border-surface-border'
              }`}>
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-3">Claim Status</h3>
                <div className="flex items-center gap-3">
                  <span className={`material-symbols-outlined text-[28px] ${
                    claim.status === 'APPROVED' ? 'text-status-safe'
                    : claim.status === 'REJECTED' ? 'text-status-emergency'
                    : 'text-on-surface-variant'
                  }`} style={{ fontVariationSettings: "'FILL' 1" }}>
                    {claim.status === 'APPROVED' ? 'check_circle' : claim.status === 'REJECTED' ? 'cancel' : 'pending'}
                  </span>
                  <div>
                    <p className="text-[16px] font-bold text-on-surface">{claim.status}</p>
                    <p className="text-[12px] text-on-surface-variant">
                      {claim.status === 'APPROVED' ? 'Payout initiated (sandbox)' : claim.status === 'REJECTED' ? 'Claim closed' : 'Awaiting insurer decision'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
