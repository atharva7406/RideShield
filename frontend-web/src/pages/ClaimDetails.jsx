import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import Timeline from '../components/Timeline';
import SensorChart from '../components/SensorChart';
import { getClaimById, getRiderById, getShiftById } from '../data/mockData';

const ESCALATION_LEVEL_STYLES = {
  VERIFIED:    { bg: 'bg-[#d1fae5]', text: 'text-[#065f46]', icon: 'verified', iconColor: 'text-status-safe' },
  TRIGGERED:   { bg: 'bg-[#fef3c7]', text: 'text-[#92400e]', icon: 'call',     iconColor: 'text-status-warning' },
  NO_RESPONSE: { bg: 'bg-error-container', text: 'text-on-error-container', icon: 'phone_missed', iconColor: 'text-status-emergency' },
  PARTIAL:     { bg: 'bg-[#fef3c7]', text: 'text-[#92400e]', icon: 'hourglass', iconColor: 'text-status-warning' },
};

export default function ClaimDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const claimRaw = getClaimById(id);
  const [claimStatus, setClaimStatus] = useState(claimRaw?.status || 'PENDING');
  const [approveLoading, setApproveLoading] = useState(false);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  if (!claimRaw) {
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

  const claim = { ...claimRaw, status: claimStatus };
  const rider = getRiderById(claim.riderId);
  const shift = getShiftById(claim.shiftId);

  async function handleApprove() {
    setApproveLoading(true);
    await new Promise(r => setTimeout(r, 800));
    setClaimStatus('APPROVED');
    setApproveLoading(false);
  }

  async function handleReject() {
    setRejectLoading(true);
    await new Promise(r => setTimeout(r, 800));
    setClaimStatus('REJECTED');
    setRejectLoading(false);
  }

  const canAct = claimStatus === 'PENDING' || claimStatus === 'UNDER_REVIEW';

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
                  <span className="text-[22px] font-bold text-on-surface-variant">{claim.id}</span>
                  <StatusBadge status={claimStatus} />
                </div>
                <p className="text-[13px] text-on-surface-variant mt-1">
                  {claim.location} · {claim.dateDisplay} at {claim.timeDisplay}
                </p>
              </div>

              {/* Actions */}
              {canAct ? (
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
              ) : (
                <div className="flex items-center gap-3 flex-shrink-0">
                  <div className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-[13px] font-bold ${
                    claimStatus === 'APPROVED' ? 'bg-[#d1fae5] text-[#065f46]' : 'bg-error-container text-on-error-container'
                  }`}>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                      {claimStatus === 'APPROVED' ? 'check_circle' : 'cancel'}
                    </span>
                    Claim {claimStatus}
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
                      {rider?.initials}
                    </div>
                    <div>
                      <p className="font-bold text-[16px] text-on-surface">{rider?.name}</p>
                      <p className="text-[12px] text-on-surface-variant">{rider?.id}</p>
                    </div>
                  </div>
                  <div className="space-y-2 text-[13px]">
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Phone</span>
                      <span className="font-medium text-on-surface">{rider?.phone}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Vehicle</span>
                      <span className="font-medium text-on-surface">{rider?.vehicle}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">City</span>
                      <span className="font-medium text-on-surface">{rider?.city}</span>
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
                      <span className="font-mono font-semibold text-primary">{shift?.id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Start Time</span>
                      <span className="font-medium text-on-surface">{shift?.start?.slice(11, 16) || '—'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Duration</span>
                      <span className="font-medium text-on-surface">{shift?.duration}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Distance</span>
                      <span className="font-medium text-on-surface">{shift?.distance}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant">Premium Paid</span>
                      <span className="font-bold text-status-safe">₹{shift?.premium?.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-on-surface-variant">Coverage</span>
                      <StatusBadge status={shift?.coverageStatus || 'EXPIRED'} size="sm" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Incident Timeline */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-5 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>timeline</span>
                  Incident Timeline
                </h3>
                <Timeline events={claim.timeline} />
              </div>

              {/* Sensor Evidence Chart */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>sensors</span>
                    Sensor Evidence — Telemetry Stream
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] bg-error-container text-on-error-container px-2 py-0.5 rounded font-bold uppercase tracking-wide">
                      Peak: {claim.evidence?.peakAccel}
                    </span>
                    <span className="text-[11px] bg-surface-container text-on-surface-variant px-2 py-0.5 rounded font-bold uppercase">
                      Jerk: {claim.evidence?.jerk}
                    </span>
                  </div>
                </div>
                <SensorChart data={claim.telemetry} crashIndex={20} />
                <p className="text-[11px] text-on-surface-variant mt-3 text-center">
                  Red vertical line marks crash event. Acceleration crosses threshold (4.5g) triggering L1 alert.
                </p>
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
                    <p className="font-mono font-semibold text-on-surface">{claim.evidence?.gps?.lat}°N, {claim.evidence?.gps?.lng}°E</p>
                    <p className="text-on-surface-variant">GPS Accuracy: {claim.evidence?.gps?.accuracy}</p>
                  </div>
                  <div className="z-20 bg-surface/90 backdrop-blur-sm rounded-lg px-4 py-2 border border-surface-border text-center shadow-sm pointer-events-none mt-12">
                    <p className="text-[13px] font-semibold text-on-surface">{claim.location}</p>
                    <p className="text-[11px] text-on-surface-variant">{claim.locationDetails}</p>
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
                    { label: 'Peak Acceleration', value: claim.evidence?.peakAccel, color: 'text-status-emergency' },
                    { label: 'Gyro Variance',    value: claim.evidence?.gyroVariance, color: 'text-on-surface' },
                    { label: 'Jerk',             value: claim.evidence?.jerk, color: 'text-on-surface' },
                    { label: 'Post-event Still', value: claim.evidence?.postEventStillness, color: 'text-status-warning' },
                    { label: 'Rolling Baseline', value: claim.evidence?.rollingBaseline, color: 'text-on-surface' },
                    { label: 'Classifier Score', value: `${(claim.evidence?.classifierScore * 100).toFixed(0)}%`, color: 'text-primary' },
                  ].map(m => (
                    <div key={m.label} className="bg-surface-muted rounded-lg p-3 border border-surface-border">
                      <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wide mb-1">{m.label}</p>
                      <p className={`text-[18px] font-bold ${m.color}`}>{m.value}</p>
                    </div>
                  ))}
                </div>

                {showEvidence && (
                  <pre className="bg-[#1e1e2e] text-[#cdd6f4] rounded-xl p-4 text-[11px] font-mono overflow-x-auto border border-surface-border animate-fade-in leading-relaxed">
{JSON.stringify(
  {
    claim_id: claim.id,
    timestamp: claim.timestamp,
    location: { lat: claim.evidence?.gps?.lat, lng: claim.evidence?.gps?.lng, accuracy: claim.evidence?.gps?.accuracy },
    impact: { peakAccel: claim.evidence?.peakAccel, gyroVariance: claim.evidence?.gyroVariance, jerk: claim.evidence?.jerk, postStillness: claim.evidence?.postEventStillness },
    classifier: { score: claim.evidence?.classifierScore, method: claim.evidence?.verificationMethod },
    escalation: claim.escalation?.map(e => ({ level: e.level, status: e.status, time: e.time })),
    crashConfidence: `${claim.crashConfidence}%`,
    riskScore: claim.riskScore,
  },
  null, 2
)}
                  </pre>
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
                      stroke={claim.crashConfidence >= 80 ? '#EF4444' : claim.crashConfidence >= 60 ? '#F59E0B' : '#10B981'}
                      strokeWidth="12"
                      strokeDasharray={`${(claim.crashConfidence / 100) * 251.2} 251.2`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className={`text-[32px] font-bold leading-none ${claim.crashConfidence >= 80 ? 'text-status-emergency' : claim.crashConfidence >= 60 ? 'text-status-warning' : 'text-status-safe'}`}>
                      {claim.crashConfidence}%
                    </span>
                    <span className="text-[11px] text-on-surface-variant mt-1">confidence</span>
                  </div>
                </div>
                <p className="text-[12px] font-semibold text-on-surface">{claim.evidence?.verificationMethod}</p>
              </div>

              {/* Risk Score */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4">Shift Risk Score</h3>
                <div className="flex items-end gap-3 mb-3">
                  <span className={`text-[40px] font-bold leading-none ${claim.riskScore >= 67 ? 'text-status-emergency' : claim.riskScore >= 34 ? 'text-status-warning' : 'text-status-safe'}`}>
                    {claim.riskScore}
                  </span>
                  <span className="text-[13px] text-on-surface-variant mb-1">/ 100</span>
                  <StatusBadge status={claim.riskLevel} size="sm" />
                </div>
                {/* Progress bar */}
                <div className="w-full h-2.5 bg-surface-container-high rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${claim.riskScore >= 67 ? 'bg-status-emergency' : claim.riskScore >= 34 ? 'bg-status-warning' : 'bg-status-safe'}`}
                    style={{ width: `${claim.riskScore}%` }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-on-surface-variant mt-1">
                  <span>Low</span><span>Medium</span><span>High</span>
                </div>
              </div>

              {/* Telemetry Snapshot */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>monitoring</span>
                  Impact Snapshot
                </h3>
                <div className="space-y-3">
                  {[
                    { icon: 'speed', label: 'G-Force',       value: claim.evidence?.peakAccel,        color: 'text-status-emergency' },
                    { icon: 'rotate_90_degrees_ccw', label: 'Gyro Variance', value: claim.evidence?.gyroVariance, color: 'text-[#8b5cf6]' },
                    { icon: 'bolt', label: 'Jerk',           value: claim.evidence?.jerk,             color: 'text-status-warning' },
                    { icon: 'hourglass_bottom', label: 'Post-Stillness', value: claim.evidence?.postEventStillness, color: 'text-status-safe' },
                  ].map(m => (
                    <div key={m.label} className="flex items-center justify-between bg-surface-muted rounded-lg px-4 py-2.5 border border-surface-border">
                      <div className="flex items-center gap-2.5">
                        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 16 }}>{m.icon}</span>
                        <span className="text-[13px] text-on-surface-variant">{m.label}</span>
                      </div>
                      <span className={`text-[15px] font-bold ${m.color}`}>{m.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Escalation History */}
              <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-5">
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>call</span>
                  Escalation History
                </h3>
                <div className="space-y-3">
                  {claim.escalation?.map((esc, i) => {
                    const s = ESCALATION_LEVEL_STYLES[esc.status] || ESCALATION_LEVEL_STYLES.TRIGGERED;
                    return (
                      <div key={i} className={`rounded-xl border p-4 ${s.bg} border-transparent`}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className={`material-symbols-outlined ${s.iconColor}`} style={{ fontSize: 16 }}>{s.icon}</span>
                            <span className="font-bold text-[13px] text-on-surface">{esc.level} — {esc.label}</span>
                          </div>
                          <span className={`text-[10px] font-bold uppercase ${s.text} px-2 py-0.5 rounded-full bg-white/40`}>{esc.status.replace(/_/g, ' ')}</span>
                        </div>
                        <p className="text-[12px] text-on-surface-variant">{esc.note}</p>
                        <p className="text-[11px] font-mono text-on-surface-variant mt-1">{esc.time}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Claim Status */}
              <div className={`rounded-xl border p-5 ${
                claimStatus === 'APPROVED' ? 'bg-[#d1fae5] border-[#a7f3d0]'
                : claimStatus === 'REJECTED' ? 'bg-error-container border-error-container'
                : 'bg-surface border-surface-border'
              }`}>
                <h3 className="text-[13px] font-bold text-on-surface-variant uppercase tracking-wide mb-3">Claim Status</h3>
                <div className="flex items-center gap-3">
                  <span className={`material-symbols-outlined text-[28px] ${
                    claimStatus === 'APPROVED' ? 'text-status-safe'
                    : claimStatus === 'REJECTED' ? 'text-status-emergency'
                    : 'text-on-surface-variant'
                  }`} style={{ fontVariationSettings: "'FILL' 1" }}>
                    {claimStatus === 'APPROVED' ? 'check_circle' : claimStatus === 'REJECTED' ? 'cancel' : 'pending'}
                  </span>
                  <div>
                    <p className="text-[16px] font-bold text-on-surface">{claimStatus.replace(/_/g, ' ')}</p>
                    <p className="text-[12px] text-on-surface-variant">
                      {claimStatus === 'APPROVED' ? 'Payout initiated (sandbox)' : claimStatus === 'REJECTED' ? 'Claim closed' : 'Awaiting insurer decision'}
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
