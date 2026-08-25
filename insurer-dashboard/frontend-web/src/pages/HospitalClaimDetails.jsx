import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getClaimDetails, uploadMedicalReport } from '../services/api';

export default function HospitalClaimDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [claim, setClaim] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [file, setFile] = useState(null);
  const [documentType, setDocumentType] = useState('FIR');
  const [notes, setNotes] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  async function loadDetails() {
    try {
      setLoading(true);
      const data = await getClaimDetails(id);
      setClaim(data);
    } catch (err) {
      console.error('Failed to load claim details:', err);
      setError('Failed to load claim. You may not be authorized.');
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
      setError('Please select a file.');
      return;
    }
    setUploading(true);
    setError('');
    try {
      await uploadMedicalReport(claim.id, file, documentType, notes);
      await loadDetails();
      setFile(null);
      setNotes('');
    } catch (err) {
      setError(err.message || 'Failed to upload report.');
    } finally {
      setUploading(false);
    }
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

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="flex-1 flex flex-col min-h-screen">
        <Topbar />
        <main className="flex-1 p-6 max-w-[800px] mx-auto w-full">
          <button
            onClick={() => navigate('/hospital')}
            className="flex items-center gap-1.5 text-on-surface-variant hover:text-primary text-[13px] font-semibold transition-colors mb-4 group"
          >
            <span className="material-symbols-outlined group-hover:-translate-x-0.5 transition-transform" style={{ fontSize: 18 }}>arrow_back</span>
            Back to Dashboard
          </button>

          <div className="flex items-center gap-3 flex-wrap mb-6">
            <h1 className="text-[28px] font-bold text-on-surface">Upload Medical Report</h1>
            <span className="text-[22px] font-bold text-on-surface-variant">{claim.claimNumber}</span>
            <StatusBadge status={claim.status} />
          </div>

          <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6 mb-6">
            <h3 className="text-[14px] font-bold text-on-surface mb-4">Patient Information</h3>
            <p className="text-[13px] text-on-surface-variant">Name: <strong className="text-on-surface">{claim.rider?.fullName || 'Gig Rider'}</strong></p>
            <p className="text-[13px] text-on-surface-variant mt-1">Incident Time: <strong className="text-on-surface">{new Date(claim.incident?.detectedAt).toLocaleString('en-IN')}</strong></p>
          </div>

          <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6">
            <h3 className="text-[16px] font-bold text-on-surface mb-4">Upload Document</h3>
            
            {error && (
              <div className="mb-4 bg-error-container text-on-error-container p-3 rounded-lg text-sm font-medium">
                {error}
              </div>
            )}

            {claim.status === 'MEDICAL_REPORT_SUBMITTED' ? (
              <div className="bg-[#d1fae5] text-[#065f46] p-4 rounded-lg flex items-center gap-2">
                <span className="material-symbols-outlined">check_circle</span>
                <span className="font-semibold text-sm">Medical report submitted successfully. Waiting for insurer review.</span>
              </div>
            ) : (
              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Document Type</label>
                  <select
                    value={documentType}
                    onChange={(e) => setDocumentType(e.target.value)}
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary"
                  >
                    <option value="FIR">FIR</option>
                    <option value="Hospital Bill">Hospital Bill</option>
                    <option value="Doctor Note">Doctor Note</option>
                    <option value="Discharge Summary">Discharge Summary</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">File (PDF, JPG, PNG)</label>
                  <input
                    type="file"
                    accept=".pdf,image/jpeg,image/png"
                    onChange={(e) => setFile(e.target.files[0])}
                    className="w-full text-[14px]"
                  />
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Notes (Optional)</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={3}
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary"
                    placeholder="Any additional details..."
                  />
                </div>

                <button
                  type="submit"
                  disabled={uploading}
                  className="w-full flex items-center justify-center gap-2 bg-primary text-white rounded-lg py-2.5 font-bold hover:opacity-90 disabled:opacity-60"
                >
                  {uploading ? <span className="material-symbols-outlined animate-spin" style={{ fontSize: 18 }}>progress_activity</span> : <span className="material-symbols-outlined" style={{ fontSize: 18 }}>upload</span>}
                  Submit Report
                </button>
              </form>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
