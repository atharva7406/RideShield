import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getClaimDetails, updateClaimStatus, startClaimReview, downloadMedicalReport, uploadMedicalReport, deleteMedicalReport } from '../services/api';

export default function ClaimDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [claim, setClaim] = useState(null);
  const [loading, setLoading] = useState(true);
  const [approveLoading, setApproveLoading] = useState(false);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadDocType, setUploadDocType] = useState('HOSPITAL_ADMISSION_REPORT');
  const [uploadNotes, setUploadNotes] = useState('');
  const [uploadingReport, setUploadingReport] = useState(false);
  const [deletingReportId, setDeletingReportId] = useState(null);

  const hospitalReportEvidence = claim?.evidence?.find(e => e.file_type === 'hospital_report');
  let hospitalReportData = null;
  if (hospitalReportEvidence) {
    try {
      hospitalReportData = JSON.parse(hospitalReportEvidence.file_url);
    } catch (e) {
      console.error('Failed to parse hospital report data:', e);
    }
  }

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
      setErrorMsg(null);
      await startClaimReview(claim.id);
      await loadDetails();
    } catch (err) {
      console.error('Failed to start review:', err);
      setErrorMsg(err.message || 'Failed to start review.');
    } finally {
      setReviewLoading(false);
    }
  }

  async function handleApprove() {
    try {
      setApproveLoading(true);
      setErrorMsg(null);
      await updateClaimStatus(claim.id, 'APPROVED');
      await loadDetails();
    } catch (err) {
      console.error('Approval failed:', err);
      setErrorMsg(err.message || 'Approval failed.');
    } finally {
      setApproveLoading(false);
    }
  }

  async function handleReject() {
    try {
      setRejectLoading(true);
      setErrorMsg(null);
      await updateClaimStatus(claim.id, 'REJECTED');
      await loadDetails();
    } catch (err) {
      console.error('Rejection failed:', err);
      setErrorMsg(err.message || 'Rejection failed.');
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

            {errorMsg && (
              <div className="mb-4 p-3.5 bg-error-container text-on-error-container border border-error rounded-xl text-xs font-bold flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">warning</span>
                  {errorMsg}
                </span>
                <button onClick={() => setErrorMsg(null)} className="text-on-error-container hover:opacity-80">
                  <span className="material-symbols-outlined text-sm">close</span>
                </button>
              </div>
            )}

            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-[28px] font-bold text-on-surface">Claim Investigation</h1>
                  <span className="text-[22px] font-bold text-on-surface-variant">{claim.claimNumber}</span>
                  <StatusBadge status={claim.status} />
                </div>
                <p className="text-[13px] text-on-surface-variant mt-1 flex items-center gap-2">
                  <span>Filed on {new Date(claim.filedAt).toLocaleString('en-IN')}</span>
                  {(claim.verification_run_id || claim.verificationRunId) && (
                    <span className="text-[11px] font-mono font-semibold bg-surface-muted px-2 py-0.5 rounded border border-surface-border">
                      Run #{String(claim.verification_run_id || claim.verificationRunId).slice(0, 8)}
                    </span>
                  )}
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
                    {claim.status === 'APPROVED' ? 'Claim Approved (Terminal)' : claim.status === 'REJECTED' ? 'Claim Rejected (Terminal)' : 'Need Medical Report'}
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

              {/* Automated Claim Verification Analysis */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <div className="flex justify-between items-center mb-4 border-b border-surface-border pb-3">
                  <h3 className="text-[14px] font-bold text-on-surface flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>analytics</span>
                    Automated Verification Engine
                  </h3>
                  {claim.verificationScore !== null && claim.verificationScore !== undefined ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] font-semibold text-on-surface-variant">System Score:</span>
                      <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                        claim.verificationScore >= 70 ? 'bg-[#d1fae5] text-[#065f46]' : claim.verificationScore >= 50 ? 'bg-[#fef3c7] text-[#92400e]' : 'bg-red-50 text-red-700'
                      }`}>
                        {claim.verificationScore} / 100
                      </span>
                    </div>
                  ) : (
                    <span className="text-[11px] bg-surface-muted text-on-surface-variant px-2.5 py-1 rounded-full font-semibold">
                      Awaiting Verification Run
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Left Column: Telemetry Evidence */}
                  <div className="bg-surface-muted/50 rounded-xl p-4 border border-surface-border">
                    <h4 className="text-xs font-bold text-primary uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>sensors</span>
                      Telemetry Evidence
                    </h4>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between py-1 border-b border-surface-border/50">
                        <span className="text-on-surface-variant">Peak G-Force</span>
                        <span className="font-semibold text-on-surface">{claim.incident?.peakGForce ? `${claim.incident.peakGForce.toFixed(2)} G` : 'N/A'}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-surface-border/50">
                        <span className="text-on-surface-variant">Telemetry Confidence</span>
                        <span className="font-semibold text-on-surface">{claim.incident?.confidenceScore ? `${(claim.incident.confidenceScore * 100).toFixed(0)}%` : 'N/A'}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-surface-border/50">
                        <span className="text-on-surface-variant">Incident GPS</span>
                        <span className="font-mono font-medium text-on-surface">
                          {claim.incident?.latitude?.toFixed(4)}°N, {claim.incident?.longitude?.toFixed(4)}°E
                        </span>
                      </div>
                      <div className="flex justify-between py-1">
                        <span className="text-on-surface-variant">Detected At</span>
                        <span className="font-medium text-on-surface">
                          {claim.incident?.detectedAt ? new Date(claim.incident.detectedAt).toLocaleString('en-IN') : 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Hospital Evidence */}
                  <div className="bg-surface-muted/50 rounded-xl p-4 border border-surface-border">
                    <h4 className="text-xs font-bold text-[#10B981] uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>local_hospital</span>
                      Hospital Evidence Summary
                    </h4>
                    {claim.medicalReports && claim.medicalReports.length > 0 ? (
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between py-1 border-b border-surface-border/50">
                          <span className="text-on-surface-variant">Facility / Hospital</span>
                          <span className="font-semibold text-on-surface">
                            {claim.rider?.hospital?.name || hospitalReportData?.facility_name || 'Network Hospital'}
                          </span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-surface-border/50">
                          <span className="text-on-surface-variant">Locality Match</span>
                          <span className="font-semibold text-[#047857] flex items-center gap-0.5">
                            <span className="material-symbols-outlined text-[12px]">check_circle</span>
                            {claim.incident?.locality || 'Locality Verified'}
                          </span>
                        </div>
                        {claim.incident?.detectedAt && (
                          <div className="flex justify-between py-1 border-b border-surface-border/50">
                            <span className="text-on-surface-variant">Incident to Report Delta</span>
                            <span className="font-medium text-on-surface">
                              {(() => {
                                const incTime = new Date(claim.incident.detectedAt);
                                const reportTime = new Date(claim.medicalReports[0].uploaded_at || claim.medicalReports[0].uploadedAt);
                                const diffHrs = Math.abs(reportTime - incTime) / (1000 * 60 * 60);
                                return `${diffHrs.toFixed(1)} hours after incident`;
                              })()}
                            </span>
                          </div>
                        )}
                        <div className="flex flex-col py-1">
                          <span className="text-on-surface-variant mb-0.5">Diagnosis / Injury Notes</span>
                          <span className="font-medium text-on-surface italic bg-surface p-2 rounded border border-surface-border/30 mt-1">
                            "{claim.medicalReports.find(r => r.notes)?.notes || hospitalReportData?.injury_description || 'Observation and treatment notes attached'}"
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-32 text-center text-on-surface-variant">
                        <span className="material-symbols-outlined mb-1 text-on-surface-variant/60" style={{ fontSize: 24 }}>pending_actions</span>
                        <p className="text-[11px]">No formal hospital admittance report submitted yet.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Evidence Verification Engine & Per-Factor Breakdown */}
              {claim.verificationScore !== null && claim.verificationScore !== undefined && (
                <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                  <div className="flex justify-between items-center mb-4 border-b border-surface-border pb-3">
                    <h3 className="text-[14px] font-bold text-on-surface flex items-center gap-2">
                      <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>fact_check</span>
                      Explainable Evidence Verification Score
                    </h3>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-3 py-1 font-bold rounded-full bg-primary/10 text-primary border border-primary/20">
                        {claim.verificationBand || 'VERIFIED'}
                      </span>
                      <span className={`text-[18px] font-extrabold px-3 py-1 rounded-lg ${
                        claim.verificationScore >= 80 ? 'bg-[#d1fae5] text-[#065f46]' : 'bg-[#fef3c7] text-[#92400e]'
                      }`}>
                        {claim.verificationScore} / 100
                      </span>
                    </div>
                  </div>

                  {claim.verificationDetails && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {Object.entries(claim.verificationDetails).map(([key, factor]) => (
                        <div key={key} className="bg-surface-muted p-3 rounded-lg border border-surface-border flex flex-col justify-between">
                          <div className="flex justify-between items-center mb-1">
                            <span className="font-bold text-xs text-on-surface capitalize">
                              {key.replace(/_/g, ' ')}
                            </span>
                            <span className={`text-xs font-mono font-bold ${factor.passed ? 'text-[#047857]' : 'text-[#b91c1c]'}`}>
                              {factor.score} / {factor.max} pts
                            </span>
                          </div>
                          <p className="text-[11px] text-on-surface-variant mt-1">
                            {factor.detail}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

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
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
                  <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>medical_information</span>
                    Attached Hospital Evidence Documents ({claim.medicalReports?.length || 0})
                  </h3>
                  <button
                    type="button"
                    onClick={() => setShowUploadModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-on-primary rounded-lg text-[12px] font-bold hover:opacity-90 transition-opacity shadow-sm"
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>cloud_upload</span>
                    Upload Evidence
                  </button>
                </div>

                {(!claim.medicalReports || claim.medicalReports.length === 0) ? (
                  <div className="p-6 text-center border-2 border-dashed border-surface-border rounded-xl text-on-surface-variant">
                    <span className="material-symbols-outlined text-[32px] mb-1 text-on-surface-variant">folder_open</span>
                    <p className="text-xs font-medium">No medical documents attached yet.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {claim.medicalReports.map((report, idx) => (
                      <div key={report.id || idx} className="bg-surface-muted rounded-lg p-4 border border-surface-border flex flex-col justify-between">
                        <div>
                          <div className="flex justify-between items-start mb-1.5">
                            <span className="font-bold text-[13px] text-on-surface">
                              {report.document_type?.replace(/_/g, ' ')}
                            </span>
                            <span className="text-[11px] text-on-surface-variant font-medium">
                              {new Date(report.uploaded_at || report.uploadedAt).toLocaleString('en-IN')}
                            </span>
                          </div>
                          {report.original_filename && (
                            <p className="text-[12px] text-on-surface-variant font-mono mb-1 truncate">
                              📄 {report.original_filename} {report.file_size ? `(${(report.file_size / 1024).toFixed(1)} KB)` : ''}
                            </p>
                          )}
                          {report.notes && (
                            <p className="text-[12px] text-on-surface-variant mb-3 italic">"{report.notes}"</p>
                          )}
                        </div>
                        <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-surface-border/50">
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
                            Download
                          </button>
                          <button
                            type="button"
                            disabled={deletingReportId === report.id}
                            onClick={async () => {
                              if (!window.confirm('Delete this medical report? Score will be recalculated.')) return;
                              try {
                                setDeletingReportId(report.id);
                                await deleteMedicalReport(claim.id, report.id);
                                await loadDetails();
                              } catch (err) {
                                alert(err.message || 'Failed to delete report.');
                              } finally {
                                setDeletingReportId(null);
                              }
                            }}
                            className="inline-flex items-center gap-1 text-[11px] font-bold text-red-600 hover:text-red-800 disabled:opacity-50"
                          >
                            {deletingReportId === report.id ? (
                              <span className="material-symbols-outlined animate-spin" style={{ fontSize: 14 }}>progress_activity</span>
                            ) : (
                              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>delete</span>
                            )}
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
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

      {/* Upload Evidence Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-surface border border-surface-border rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-[18px] font-bold text-on-surface flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">cloud_upload</span>
                Upload Medical Evidence
              </h3>
              <button onClick={() => setShowUploadModal(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!uploadFile) {
                  alert('Please select a file to upload.');
                  return;
                }
                setUploadingReport(true);
                try {
                  await uploadMedicalReport(
                    claim.id,
                    uploadFile,
                    uploadDocType,
                    claim.rider?.fullName || '',
                    'Network Hospital',
                    claim.incident?.locality || '',
                    '',
                    '',
                    uploadNotes
                  );
                  setShowUploadModal(false);
                  setUploadFile(null);
                  setUploadNotes('');
                  await loadDetails();
                } catch (err) {
                  alert(err.message || 'Upload failed.');
                } finally {
                  setUploadingReport(false);
                }
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-[12px] font-bold text-on-surface-variant mb-1">Document Type</label>
                <select
                  value={uploadDocType}
                  onChange={(e) => setUploadDocType(e.target.value)}
                  className="w-full rounded-lg border border-surface-border p-2.5 text-[13px] bg-surface text-on-surface outline-none focus:ring-2 focus:ring-primary/30"
                >
                  <option value="HOSPITAL_ADMISSION_REPORT">Hospital Admission Report</option>
                  <option value="HOSPITAL_BILL">Hospital / Pharmacy Bill</option>
                  <option value="PRESCRIPTION">Doctor Prescription</option>
                  <option value="DISCHARGE_SUMMARY">Discharge Summary</option>
                  <option value="DIAGNOSTIC_REPORT">Lab / Diagnostic Report</option>
                  <option value="OTHER">Other Supporting Document</option>
                </select>
              </div>

              <div>
                <label className="block text-[12px] font-bold text-on-surface-variant mb-1">Select PDF/Image File *</label>
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => setUploadFile(e.target.files[0])}
                  required
                  className="w-full text-xs text-on-surface-variant file:mr-3 file:py-2 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                />
              </div>

              <div>
                <label className="block text-[12px] font-bold text-on-surface-variant mb-1">Notes / Remarks</label>
                <textarea
                  value={uploadNotes}
                  onChange={(e) => setUploadNotes(e.target.value)}
                  rows={2}
                  placeholder="Optional notes regarding this document..."
                  className="w-full rounded-lg border border-surface-border p-2.5 text-[13px] bg-surface text-on-surface outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="flex-1 py-2.5 border border-surface-border text-on-surface-variant rounded-lg text-[13px] font-semibold hover:bg-surface-muted transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploadingReport}
                  className="flex-1 py-2.5 bg-primary text-on-primary rounded-lg text-[13px] font-bold hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-60"
                >
                  {uploadingReport ? <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>progress_activity</span> : 'Upload & Recalculate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
