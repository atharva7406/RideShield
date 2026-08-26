import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getClaimDetails, uploadMedicalReport, deleteMedicalReport, downloadMedicalReport } from '../services/api';

const DOCUMENT_TYPES = [
  { value: 'HOSPITAL_ADMISSION_REPORT', label: 'Hospital Admission Report' },
  { value: 'HOSPITAL_BILL', label: 'Hospital / Pharmacy Bill' },
  { value: 'PRESCRIPTION', label: 'Doctor Prescription' },
  { value: 'DISCHARGE_SUMMARY', label: 'Discharge Summary' },
  { value: 'DIAGNOSTIC_REPORT', label: 'Lab / Diagnostic Report' },
  { value: 'OTHER', label: 'Other Supporting Document' },
];

export default function HospitalClaimDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [claim, setClaim] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [file, setFile] = useState(null);
  const [documentType, setDocumentType] = useState('HOSPITAL_ADMISSION_REPORT');
  const [patientIdentifier, setPatientIdentifier] = useState('');
  const [facilityName, setFacilityName] = useState('');
  const [hospitalLocality, setHospitalLocality] = useState('');
  const [admittanceTimestamp, setAdmittanceTimestamp] = useState('');
  const [diagnosisNotes, setDiagnosisNotes] = useState('');
  const [notes, setNotes] = useState('');

  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  async function loadDetails() {
    try {
      setLoading(true);
      const data = await getClaimDetails(id);
      setClaim(data);
      // Pre-fill rider name if empty
      if (data && data.rider?.fullName && !patientIdentifier) {
        setPatientIdentifier(data.rider.fullName);
      }
      if (data && data.incident?.locality && !hospitalLocality) {
        setHospitalLocality(data.incident.locality);
      }
    } catch (err) {
      console.error('Failed to load claim details:', err);
      setError('Failed to load claim. You may not be authorized for this locality.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetails();
  }, [id]);

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to upload.');
      return;
    }
    setUploading(true);
    setError('');
    setSuccessMsg('');
    try {
      await uploadMedicalReport(
        claim.id,
        file,
        documentType,
        patientIdentifier,
        facilityName,
        hospitalLocality,
        admittanceTimestamp,
        diagnosisNotes,
        notes
      );
      setSuccessMsg(`Document "${file.name}" added successfully! Score updated.`);
      setFile(null);
      setDiagnosisNotes('');
      setNotes('');
      const inputEl = document.getElementById('evidence-file-input');
      if (inputEl) inputEl.value = '';
      await loadDetails();
    } catch (err) {
      setError(err.message || 'Failed to upload document.');
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(reportId, originalName) {
    if (!window.confirm(`Are you sure you want to delete "${originalName || 'this document'}"?`)) {
      return;
    }
    setDeletingId(reportId);
    setError('');
    setSuccessMsg('');
    try {
      await deleteMedicalReport(claim.id, reportId);
      setSuccessMsg('Document deleted successfully. Evidence score recalculated.');
      await loadDetails();
    } catch (err) {
      setError(err.message || 'Failed to delete document.');
    } finally {
      setDeletingId(null);
    }
  }

  function formatBytes(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  if (loading) {
    return (
      <div className="flex min-h-screen bg-surface-muted">
        <div className="flex-1 flex items-center justify-center">
          <span className="material-symbols-outlined animate-spin text-primary" style={{ fontSize: 32 }}>progress_activity</span>
        </div>
      </div>
    );
  }

  if (!claim) {
    return (
      <div className="flex min-h-screen bg-surface-muted">
        <div className="flex-1 flex flex-col items-center justify-center">
          <span className="material-symbols-outlined text-on-surface-variant mb-4" style={{ fontSize: 48 }}>error</span>
          <h2 className="text-[20px] font-bold text-on-surface">Error</h2>
          <p className="text-on-surface-variant mt-2 mb-6">{error || 'Claim not found.'}</p>
          <button onClick={() => navigate('/hospital')} className="bg-primary text-on-primary px-6 py-2.5 rounded-lg font-semibold hover:opacity-90">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const reports = claim.medicalReports || claim.medical_reports || [];
  const isClosedOrInReview = !['MEDICAL_REPORT_PENDING', 'MEDICAL_REPORT_SUBMITTED'].includes(claim.status);

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="flex-1 flex flex-col min-h-screen">
        <Topbar />
        <main className="flex-1 p-6 max-w-[950px] mx-auto w-full">
          <button
            onClick={() => navigate('/hospital')}
            className="flex items-center gap-1.5 text-on-surface-variant hover:text-primary text-[13px] font-semibold transition-colors mb-4 group"
          >
            <span className="material-symbols-outlined group-hover:-translate-x-0.5 transition-transform" style={{ fontSize: 18 }}>arrow_back</span>
            Back to Dashboard
          </button>

          <div className="flex items-center justify-between gap-3 flex-wrap mb-6">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-[28px] font-bold text-on-surface">Hospital Evidence Management</h1>
              <span className="text-[22px] font-bold text-on-surface-variant">{claim.claimNumber}</span>
              <StatusBadge status={claim.status} />
            </div>

            {/* Evidence Score Indicator */}
            {claim.verificationScore !== null && claim.verificationScore !== undefined && (
              <div className="flex items-center gap-2 bg-surface px-4 py-2 rounded-xl border border-surface-border shadow-sm">
                <span className="text-xs font-bold text-on-surface-variant">Evidence Score:</span>
                <span className={`px-2.5 py-1 rounded-lg text-sm font-extrabold ${
                  claim.verificationScore >= 80 ? 'bg-[#d1fae5] text-[#065f46]' : claim.verificationScore >= 50 ? 'bg-[#fef3c7] text-[#92400e]' : 'bg-red-50 text-red-700'
                }`}>
                  {claim.verificationScore} / 100
                </span>
                <span className="text-xs font-semibold text-on-surface-variant">({claim.verificationBand})</span>
              </div>
            )}
          </div>

          {/* Patient Header */}
          <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6 mb-6">
            <h3 className="text-[14px] font-bold text-on-surface mb-3">Patient Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-[13px]">
              <div>
                <span className="text-on-surface-variant block">Rider Name</span>
                <strong className="text-on-surface font-semibold">{claim.rider?.fullName || 'Gig Rider'}</strong>
              </div>
              <div>
                <span className="text-on-surface-variant block">Claim Number</span>
                <strong className="text-on-surface font-mono font-semibold">{claim.claimNumber}</strong>
              </div>
              <div>
                <span className="text-on-surface-variant block">Incident Time</span>
                <strong className="text-on-surface font-semibold">{new Date(claim.filedAt || claim.filed_at).toLocaleString('en-IN')}</strong>
              </div>
            </div>
          </div>

          {/* Notification Messages */}
          {error && (
            <div className="mb-6 bg-error-container text-on-error-container p-4 rounded-xl text-sm font-medium flex items-center gap-2 border border-error">
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>error</span>
              {error}
            </div>
          )}

          {successMsg && (
            <div className="mb-6 bg-[#d1fae5] text-[#065f46] p-4 rounded-xl text-sm font-medium flex items-center gap-2 border border-[#a7f3d0]">
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>check_circle</span>
              {successMsg}
            </div>
          )}

          {isClosedOrInReview && (
            <div className="mb-6 bg-amber-50 text-amber-800 p-4 rounded-xl text-sm font-medium flex items-center gap-2 border border-amber-200">
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>lock</span>
              Claim is in state <strong>{claim.status}</strong>. Hospital evidence modifications are locked.
            </div>
          )}

          {/* Running List of Attached Documents */}
          <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[16px] font-bold text-on-surface">Attached Evidence Documents ({reports.length})</h3>
              {claim.status === 'MEDICAL_REPORT_SUBMITTED' && (
                <span className="text-xs px-2.5 py-1 bg-blue-50 text-blue-700 font-semibold rounded-full border border-blue-200">
                  Evidence Active
                </span>
              )}
            </div>

            {reports.length === 0 ? (
              <div className="p-8 text-center border-2 border-dashed border-surface-border rounded-xl text-on-surface-variant">
                <span className="material-symbols-outlined text-[36px] mb-2 text-on-surface-variant">folder_open</span>
                <p className="text-sm font-medium">No medical documents attached yet.</p>
                <p className="text-xs text-on-surface-variant mt-1">Add reports using the form below to support this claim.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {reports.map((doc, idx) => (
                  <div key={doc.id || idx} className="p-4 bg-surface-muted rounded-xl border border-surface-border hover:border-primary/40 transition-colors">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-primary mt-0.5" style={{ fontSize: 28 }}>
                          {doc.mime_type?.includes('pdf') || doc.file_reference?.endsWith('.pdf') ? 'picture_as_pdf' : 'description'}
                        </span>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-[14px] text-on-surface">
                              {DOCUMENT_TYPES.find(t => t.value === doc.document_type)?.label || doc.document_type?.replace(/_/g, ' ')}
                            </span>
                            {doc.file_size && (
                              <span className="text-[11px] text-on-surface-variant font-mono">({formatBytes(doc.file_size)})</span>
                            )}
                          </div>

                          <p className="text-[12px] text-on-surface-variant font-mono mt-1">
                            📄 {doc.original_filename || doc.file_reference?.split('_').slice(1).join('_') || 'Attachment'}
                          </p>

                          {/* Structured Fields Summary */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 mt-2 text-[12px] text-on-surface-variant bg-surface p-2.5 rounded-lg border border-surface-border/50">
                            {doc.patient_identifier && (
                              <div><span className="font-semibold text-on-surface">Patient:</span> {doc.patient_identifier}</div>
                            )}
                            {doc.facility_name && (
                              <div><span className="font-semibold text-on-surface">Facility:</span> {doc.facility_name}</div>
                            )}
                            {doc.hospital_locality && (
                              <div><span className="font-semibold text-on-surface">Locality:</span> {doc.hospital_locality}</div>
                            )}
                            {doc.admittance_timestamp && (
                              <div><span className="font-semibold text-on-surface">Admitted:</span> {new Date(doc.admittance_timestamp).toLocaleString('en-IN')}</div>
                            )}
                          </div>

                          {doc.diagnosis_notes && (
                            <p className="text-[12px] text-on-surface mt-2 italic bg-surface p-2 rounded border border-surface-border/30">
                              <span className="font-semibold not-italic">Diagnosis:</span> "{doc.diagnosis_notes}"
                            </p>
                          )}
                          {doc.notes && (
                            <p className="text-[12px] text-on-surface-variant mt-1 italic">
                              Notes: "{doc.notes}"
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2 self-start">
                        <button
                          type="button"
                          onClick={() => downloadMedicalReport(claim.id, doc.id)}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-primary hover:bg-primary/10 rounded-md transition-colors border border-primary/20"
                        >
                          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>download</span>
                          Download
                        </button>
                        {!isClosedOrInReview && (
                          <button
                            type="button"
                            disabled={deletingId === doc.id}
                            onClick={() => handleDelete(doc.id, doc.original_filename)}
                            className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-50 rounded-md transition-colors border border-red-200 disabled:opacity-50"
                          >
                            {deletingId === doc.id ? (
                              <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>progress_activity</span>
                            ) : (
                              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                            )}
                            Delete
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Add Document Form */}
          {!isClosedOrInReview && (
            <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6">
              <h3 className="text-[16px] font-bold text-on-surface mb-4">
                Add Document to Evidence Bundle
              </h3>

              <form onSubmit={handleUpload} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Document Type *</label>
                    <select
                      value={documentType}
                      onChange={(e) => setDocumentType(e.target.value)}
                      className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                    >
                      {DOCUMENT_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Patient Identifier (e.g. Full Name)</label>
                    <input
                      type="text"
                      value={patientIdentifier}
                      onChange={(e) => setPatientIdentifier(e.target.value)}
                      placeholder="e.g. Suhaas / Rajesh Kumar"
                      className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Facility Name</label>
                    <input
                      type="text"
                      value={facilityName}
                      onChange={(e) => setFacilityName(e.target.value)}
                      placeholder="e.g. Mumbai General Hospital"
                      className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                    />
                  </div>

                  <div>
                    <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Hospital Locality</label>
                    <input
                      type="text"
                      value={hospitalLocality}
                      onChange={(e) => setHospitalLocality(e.target.value)}
                      placeholder="e.g. Mumbai"
                      className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                    />
                  </div>

                  <div>
                    <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Admittance Timestamp</label>
                    <input
                      type="datetime-local"
                      value={admittanceTimestamp}
                      onChange={(e) => setAdmittanceTimestamp(e.target.value)}
                      className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Select File (PDF, PNG, JPG, DOC, DOCX - Max 5MB) *</label>
                  <input
                    id="evidence-file-input"
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,application/pdf,image/png,image/jpeg,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    onChange={(e) => setFile(e.target.files[0])}
                    required
                    className="w-full text-sm text-on-surface-variant file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                  />
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Diagnosis Notes</label>
                  <textarea
                    value={diagnosisNotes}
                    onChange={(e) => setDiagnosisNotes(e.target.value)}
                    rows={2}
                    placeholder="e.g. ACL injury following road incident..."
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface mb-2"
                  />
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Additional Notes (Optional)</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={2}
                    placeholder="Provide additional hospital remarks..."
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                  />
                </div>

                <button
                  type="submit"
                  disabled={uploading}
                  className="w-full flex items-center justify-center gap-2 text-white rounded-lg py-3 font-bold hover:opacity-90 disabled:opacity-60 transition-opacity"
                  style={{ backgroundColor: '#0066ff' }}
                >
                  {uploading ? (
                    <span className="material-symbols-outlined animate-spin" style={{ fontSize: 18 }}>progress_activity</span>
                  ) : (
                    <span className="material-symbols-outlined" style={{ fontSize: 18 }}>cloud_upload</span>
                  )}
                  Add Document to Evidence
                </button>
              </form>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
