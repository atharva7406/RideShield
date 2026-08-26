import { useState, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';

// ── helpers ──────────────────────────────────────────────────────────────────
function loadAuth() {
  try { return JSON.parse(localStorage.getItem('rs_auth')) || {}; } catch { return {}; }
}
function loadPrefs() {
  try { return JSON.parse(localStorage.getItem('rs_prefs')) || {}; } catch { return {}; }
}
function savePrefs(prefs) { localStorage.setItem('rs_prefs', JSON.stringify(prefs)); }

// ── sub-components ────────────────────────────────────────────────────────────
function SectionCard({ title, children }) {
  return (
    <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6 mb-5">
      <h2 className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest mb-4">{title}</h2>
      {children}
    </div>
  );
}

function Row({ icon, title, description, children }) {
  return (
    <div className="flex items-start justify-between py-3.5 border-b border-surface-border last:border-0 gap-4">
      <div className="flex items-start gap-3 min-w-0">
        <span className="material-symbols-outlined text-on-surface-variant mt-0.5 flex-shrink-0" style={{ fontSize: 19 }}>{icon}</span>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-on-background">{title}</p>
          <p className="text-[11px] text-on-surface-variant mt-0.5">{description}</p>
        </div>
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`relative w-10 h-5 rounded-full transition-colors duration-200 ${value ? 'bg-primary' : 'bg-surface-border'}`}
    >
      <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${value ? 'translate-x-5' : 'translate-x-0'}`} />
    </button>
  );
}

function Toast({ message, type = 'success', onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 3000); return () => clearTimeout(t); }, []);
  const colors = type === 'success'
    ? { bg: '#f0fdf4', border: '#bbf7d0', text: '#15803d', icon: 'check_circle' }
    : { bg: '#fef2f2', border: '#fecaca', text: '#dc2626', icon: 'error' };
  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex items-center gap-2 px-4 py-3 rounded-xl border shadow-lg text-[13px] font-semibold animate-fade-in"
      style={{ background: colors.bg, borderColor: colors.border, color: colors.text }}>
      <span className="material-symbols-outlined" style={{ fontSize: 18, fontVariationSettings: "'FILL' 1" }}>{colors.icon}</span>
      {message}
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-surface rounded-2xl border border-surface-border shadow-2xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-[16px] font-bold text-on-background">{title}</h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ── main component ─────────────────────────────────────────────────────────────
export default function Settings() {
  const auth = loadAuth();
  const prefs = loadPrefs();

  const [name, setName]               = useState(auth.name || '');
  const [email, setEmail]             = useState(auth.email || '');

  // Notifications
  const [notifCrash, setNotifCrash]   = useState(prefs.notifCrash ?? true);
  const [notifClaims, setNotifClaims] = useState(prefs.notifClaims ?? true);
  const [notifShifts, setNotifShifts] = useState(prefs.notifShifts ?? false);
  const [notifEmail, setNotifEmail]   = useState(prefs.notifEmail ?? true);
  const [notifSMS, setNotifSMS]       = useState(prefs.notifSMS ?? false);

  // Display
  const [compactView, setCompactView]     = useState(prefs.compactView ?? false);
  const [showRiskScore, setShowRiskScore] = useState(prefs.showRiskScore ?? true);
  const [timezone, setTimezone]           = useState(prefs.timezone ?? 'IST');

  // Security
  const [twoFA, setTwoFA]                     = useState(prefs.twoFA ?? false);
  const [sessionTimeout, setSessionTimeout]   = useState(prefs.sessionTimeout ?? '30');

  // UI state
  const [toast, setToast]           = useState(null);
  const [showPwModal, setShowPwModal] = useState(false);
  const [showLogModal, setShowLogModal] = useState(false);

  // Password form
  const [pwCurrent, setPwCurrent]   = useState('');
  const [pwNew, setPwNew]           = useState('');
  const [pwConfirm, setPwConfirm]   = useState('');
  const [pwError, setPwError]       = useState('');
  const [pwLoading, setPwLoading]   = useState(false);

  function showToast(msg, type = 'success') { setToast({ msg, type }); }

  function handleSave() {
    // Update auth (name)
    const newAuth = { ...auth, name: name.trim() || auth.name, email: email.trim() || auth.email };
    localStorage.setItem('rs_auth', JSON.stringify(newAuth));

    // Save prefs
    savePrefs({ notifCrash, notifClaims, notifShifts, notifEmail, notifSMS, compactView, showRiskScore, timezone, twoFA, sessionTimeout });

    showToast('Settings saved successfully');
    // Force sidebar to re-read
    window.dispatchEvent(new Event('storage'));
  }

  async function handlePasswordChange(e) {
    e.preventDefault();
    setPwError('');
    if (!pwCurrent) { setPwError('Enter your current password.'); return; }
    if (pwNew.length < 8) { setPwError('New password must be at least 8 characters.'); return; }
    if (pwNew !== pwConfirm) { setPwError('Passwords do not match.'); return; }
    setPwLoading(true);
    await new Promise(r => setTimeout(r, 800)); // simulate API
    setPwLoading(false);
    setShowPwModal(false);
    setPwCurrent(''); setPwNew(''); setPwConfirm('');
    showToast('Password changed successfully');
  }

  const LOGIN_LOG = [
    { device: 'Chrome · Windows',    location: 'Mumbai, IN',    time: 'Today, 7:08 PM',      current: true },
    { device: 'Safari · iPhone',     location: 'Pune, IN',      time: 'Aug 24, 11:42 AM',   current: false },
    { device: 'Chrome · MacOS',      location: 'Bangalore, IN', time: 'Aug 22, 3:15 PM',    current: false },
    { device: 'Firefox · Windows',   location: 'Delhi, IN',     time: 'Aug 19, 9:01 AM',    current: false },
  ];

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar title="Settings" />
        <main className="flex-1 p-8 max-w-3xl mx-auto w-full">

          {/* Account */}
          <SectionCard title="Account">
            <div className="flex items-center gap-4 pb-4 mb-2 border-b border-surface-border">
              <div className="w-14 h-14 rounded-full bg-primary flex items-center justify-center text-on-primary text-xl font-bold flex-shrink-0">
                {name.trim().split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase() || 'U'}
              </div>
              <div>
                <p className="text-[15px] font-bold text-on-background">{name || '—'}</p>
                <p className="text-[12px] text-on-surface-variant">{email || '—'}</p>
                <span className="inline-block mt-1 text-[10px] font-bold px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">Insurer Admin</span>
              </div>
            </div>
            <Row icon="badge" title="Full Name" description="Your display name across the portal">
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="px-3 py-1.5 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low w-44"
              />
            </Row>
            <Row icon="alternate_email" title="Email Address" description="Used for login and notifications">
              <input
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="px-3 py-1.5 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low w-52"
              />
            </Row>
            <Row icon="lock" title="Password" description="Last changed 30 days ago">
              <button
                onClick={() => setShowPwModal(true)}
                className="px-4 py-1.5 text-[11px] font-semibold border border-primary text-primary rounded-lg hover:bg-primary/5 transition-colors"
              >
                Change Password
              </button>
            </Row>
          </SectionCard>

          {/* Notifications */}
          <SectionCard title="Notifications">
            <Row icon="emergency" title="Crash Alerts" description="Instant alert when a crash is detected">
              <Toggle value={notifCrash} onChange={setNotifCrash} />
            </Row>
            <Row icon="request_quote" title="New Claim Updates" description="Notify on claim status changes">
              <Toggle value={notifClaims} onChange={setNotifClaims} />
            </Row>
            <Row icon="speed" title="Shift Start / End" description="Alert when a rider starts or ends a shift">
              <Toggle value={notifShifts} onChange={setNotifShifts} />
            </Row>
            <Row icon="email" title="Email Digest" description="Receive a daily summary via email">
              <Toggle value={notifEmail} onChange={setNotifEmail} />
            </Row>
            <Row icon="sms" title="SMS Alerts" description="High-priority alerts via SMS">
              <Toggle value={notifSMS} onChange={setNotifSMS} />
            </Row>
          </SectionCard>

          {/* Display */}
          <SectionCard title="Display & Preferences">
            <Row icon="table_rows" title="Compact Table View" description="Show more rows with less padding">
              <Toggle value={compactView} onChange={setCompactView} />
            </Row>
            <Row icon="speed" title="Show Risk Score Column" description="Display risk score in rider/shift tables">
              <Toggle value={showRiskScore} onChange={setShowRiskScore} />
            </Row>
            <Row icon="language" title="Timezone" description="All timestamps displayed in this timezone">
              <select
                value={timezone}
                onChange={e => setTimezone(e.target.value)}
                className="px-3 py-1.5 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low"
              >
                <option value="IST">IST (UTC+5:30)</option>
                <option value="UTC">UTC</option>
                <option value="EST">EST (UTC-5)</option>
                <option value="PST">PST (UTC-8)</option>
              </select>
            </Row>
          </SectionCard>

          {/* Security */}
          <SectionCard title="Security">
            <Row icon="security" title="Two-Factor Authentication" description="Add an extra layer of login security via OTP">
              <div className="flex items-center gap-2">
                {twoFA && <span className="text-[10px] font-bold text-green-600 bg-green-50 border border-green-200 px-2 py-0.5 rounded">Active</span>}
                <Toggle value={twoFA} onChange={v => { setTwoFA(v); showToast(v ? '2FA enabled' : '2FA disabled'); }} />
              </div>
            </Row>
            <Row icon="timer" title="Session Timeout" description="Auto sign-out after period of inactivity">
              <select
                value={sessionTimeout}
                onChange={e => setSessionTimeout(e.target.value)}
                className="px-3 py-1.5 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low"
              >
                <option value="15">15 minutes</option>
                <option value="30">30 minutes</option>
                <option value="60">1 hour</option>
                <option value="240">4 hours</option>
                <option value="0">Never</option>
              </select>
            </Row>
            <Row icon="history" title="Login Activity" description="Recent sign-ins across your devices">
              <button
                onClick={() => setShowLogModal(true)}
                className="px-4 py-1.5 text-[11px] font-semibold border border-surface-border text-on-surface-variant rounded-lg hover:bg-surface-muted transition-colors"
              >
                View Log
              </button>
            </Row>
          </SectionCard>

          {/* Save */}
          <div className="flex justify-end mb-10">
            <button
              onClick={handleSave}
              className="px-8 py-2.5 bg-primary text-on-primary rounded-lg text-[13px] font-bold hover:bg-primary/90 transition-colors shadow-sm"
            >
              Save Changes
            </button>
          </div>
        </main>
      </div>

      {/* Toast */}
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

      {/* Change Password Modal */}
      {showPwModal && (
        <Modal title="Change Password" onClose={() => { setShowPwModal(false); setPwError(''); }}>
          <form onSubmit={handlePasswordChange} className="flex flex-col gap-3">
            {['Current password', 'New password', 'Confirm new password'].map((label, i) => {
              const [val, setter] = [[pwCurrent, setPwCurrent], [pwNew, setPwNew], [pwConfirm, setPwConfirm]][i];
              return (
                <div key={label}>
                  <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">{label}</label>
                  <input
                    type="password"
                    value={val}
                    onChange={e => setter(e.target.value)}
                    className="w-full px-3 py-2 border border-surface-border rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low"
                    placeholder={i === 0 ? 'Enter current password' : i === 1 ? 'Min. 8 characters' : 'Repeat new password'}
                  />
                </div>
              );
            })}
            {pwError && <p className="text-[11px] text-red-600 font-medium">{pwError}</p>}
            <div className="flex gap-2 pt-2">
              <button type="button" onClick={() => setShowPwModal(false)}
                className="flex-1 py-2 border border-surface-border rounded-lg text-[12px] font-semibold text-on-surface-variant hover:bg-surface-muted transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={pwLoading}
                className="flex-1 py-2 bg-primary text-on-primary rounded-lg text-[12px] font-bold hover:bg-primary/90 transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
                {pwLoading && <span className="material-symbols-outlined animate-spin" style={{ fontSize: 14 }}>progress_activity</span>}
                {pwLoading ? 'Saving…' : 'Update Password'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Login Log Modal */}
      {showLogModal && (
        <Modal title="Recent Login Activity" onClose={() => setShowLogModal(false)}>
          <div className="flex flex-col gap-2">
            {LOGIN_LOG.map((entry, i) => (
              <div key={i} className={`flex items-start justify-between p-3 rounded-lg border ${entry.current ? 'border-primary/30 bg-primary/5' : 'border-surface-border bg-surface-container'}`}>
                <div className="flex items-start gap-3">
                  <span className="material-symbols-outlined text-on-surface-variant mt-0.5" style={{ fontSize: 18 }}>
                    {entry.device.includes('iPhone') ? 'smartphone' : 'computer'}
                  </span>
                  <div>
                    <p className="text-[12px] font-semibold text-on-background">{entry.device}</p>
                    <p className="text-[11px] text-on-surface-variant">{entry.location} · {entry.time}</p>
                  </div>
                </div>
                {entry.current
                  ? <span className="text-[10px] font-bold text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded flex-shrink-0">Current</span>
                  : <button className="text-[10px] font-semibold text-red-500 hover:underline flex-shrink-0">Revoke</button>
                }
              </div>
            ))}
          </div>
          <p className="text-[10px] text-on-surface-variant mt-4 text-center opacity-60">
            Showing last 30 days · Unrecognised session? Change your password immediately.
          </p>
        </Modal>
      )}
    </div>
  );
}
