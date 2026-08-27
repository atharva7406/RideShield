import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Topbar from '../components/Topbar';
import StatusBadge from '../components/StatusBadge';
import { getClaimDetails, submitHospitalReport } from '../services/api';

export default function HospitalClaimDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [claim, setClaim] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [patientIdentifier, setPatientIdentifier] = useState('');
  const [injuryDescription, setInjuryDescription] = useState('');
  const [admissionTimestamp, setAdmissionTimestamp] = useState('');
  const [facilityName, setFacilityName] = useState('');
  const [reportFile, setReportFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  async function loadDetails() {
    try {
      setLoading(true);
      const data = await getClaimDetails(id);
      setClaim(data);
      // Pre-fill facility if hospital exists
      if (data.rider?.hospital?.name) {
        setFacilityName(data.rider.hospital.name);
      }
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
    if (!patientIdentifier || !injuryDescription || !admissionTimestamp || !facilityName) {
      setError('Please fill in all the fields.');
      return;
    }
    setUploading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('patient_identifier', patientIdentifier);
      formData.append('injury_description', injuryDescription);
      formData.append('admission_timestamp', new Date(admissionTimestamp).toISOString());
      formData.append('facility_name', facilityName);
      if (reportFile) {
        formData.append('report_file', reportFile);
      }
      
      await submitHospitalReport(claim.id, formData);
      await loadDetails();
    } catch (err) {
      setError(err.message || 'Failed to submit report.');
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
            <h3 className="text-[16px] font-bold text-on-surface mb-4">Official Hospital Admittance Report</h3>
            
            {error && (
              <div className="mb-4 bg-error-container text-on-error-container p-3 rounded-lg text-sm font-medium">
                {error}
              </div>
            )}

            {claim.status === 'MEDICAL_REPORT_SUBMITTED' || claim.status === 'APPROVED' || claim.status === 'REJECTED' || claim.status === 'UNDER_REVIEW' ? (
              <div className="bg-[#d1fae5] text-[#065f46] p-4 rounded-lg flex items-center gap-2">
                <span className="material-symbols-outlined">check_circle</span>
                <span className="font-semibold text-sm">Medical report submitted successfully. System verification complete. Status: {claim.status}</span>
              </div>
            ) : (
              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Patient Identifier (Name/ID)</label>
                  <input
                    type="text"
                    value={patientIdentifier}
                    onChange={(e) => setPatientIdentifier(e.target.value)}
                    required
                    placeholder="e.g. Suhaas / Rider ID"
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                  />
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Facility Name</label>
                  <input
                    type="text"
                    value={facilityName}
                    onChange={(e) => setFacilityName(e.target.value)}
                    required
                    placeholder="e.g. Apollo Hospital"
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                  />
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Admittance Timestamp</label>
                  <input
                    type="datetime-local"
                    value={admissionTimestamp}
                    onChange={(e) => setAdmissionTimestamp(e.target.value)}
                    required
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                  />
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Injury Diagnosis & Notes</label>
                  <textarea
                    value={injuryDescription}
                    onChange={(e) => setInjuryDescription(e.target.value)}
                    required
                    rows={3}
                    placeholder="e.g. Left knee abrasion, minor concussion. Patient admitted for observation."
                    className="w-full rounded-md border border-surface-border py-2 px-3 text-[14px] outline-none focus:border-primary bg-surface text-on-surface"
                  />
                </div>

                <div>
                  <label className="block text-[13px] font-bold text-on-surface-variant mb-1">Attach Document (Optional)</label>
                  <input
                    type="file"
                    onChange={(e) => setReportFile(e.target.files[0])}
                    className="w-full text-[14px] text-on-surface file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary file:text-on-primary hover:file:opacity-90"
                    accept=".pdf,.png,.jpg,.jpeg"
                  />
                </div>

                <button
                  type="submit"
                  disabled={uploading}
                  className="w-full flex items-center justify-center gap-2 bg-primary text-white rounded-lg py-2.5 font-bold hover:opacity-90 disabled:opacity-60"
                  style={{ backgroundColor: '#0066ff' }}
                >
                  {uploading ? <span className="material-symbols-outlined animate-spin" style={{ fontSize: 18 }}>progress_activity</span> : <span className="material-symbols-outlined" style={{ fontSize: 18 }}>assignment_turned_in</span>}
                  Submit Hospital Report
                </button>
              </form>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
