import { useState } from 'react';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';

// ── FAQ data ──────────────────────────────────────────────────────────────────
const FAQS = [
  { q: 'How does crash detection work?', a: 'RideShield uses a multi-layer sensor fusion pipeline. On-device ML models analyse accelerometer, gyroscope and GPS data in real time. A crash candidate triggers a 15-second L1 alert, escalating to L2 (SMS/WhatsApp) and L3 (sensor verification) if unacknowledged.' },
  { q: 'How do I dispute a claim decision?', a: 'Open the claim from the Claims page, click "Dispute" in the top-right corner, and fill in the reason. The risk team will review raw telemetry and respond within 48 hours.' },
  { q: 'Can I add or remove riders from a policy?', a: 'Yes — navigate to Policies, open the relevant policy, and use the "Manage Riders" button. Changes take effect from the next shift.' },
  { q: 'What does the risk score represent?', a: 'The risk score (0–100) is a composite of hard-braking frequency, speeding events, time-of-day, and historical incident rate. Scores above 70 trigger a HIGH risk flag.' },
  { q: 'How are premiums calculated per shift?', a: "Premiums are dynamic and calculated at shift start based on the rider's trailing 30-day risk score, route density, weather risk index, and vehicle class." },
  { q: 'What happens if a rider does not respond to the L1 alert?', a: 'After 15 seconds with no response, the system automatically escalates to L2 (multi-channel alert to the rider and emergency contact) and then L3 (sensor fusion verification) within 60 seconds.' },
];

// ── Ticket data ───────────────────────────────────────────────────────────────
const INITIAL_TICKETS = [
  { id: 'TKT-3301', subject: 'Cannot export claims report', status: 'Open',     date: 'Aug 24, 2026', priority: 'Medium', detail: 'The Export CSV button on the Claims page returns a 502 error. Tried on Chrome and Firefox. Affected since Aug 23.' },
  { id: 'TKT-3214', subject: 'API rate limit exceeded',     status: 'Resolved', date: 'Aug 18, 2026', priority: 'High',   detail: 'Burst of automated requests hit the 1000 req/min limit. Resolved by whitelisting insurer IP range and raising limit to 5000 req/min.' },
  { id: 'TKT-3089', subject: 'Policy CSV import failed',    status: 'Resolved', date: 'Aug 10, 2026', priority: 'Low',    detail: 'The CSV had a BOM character causing parse errors. Fixed by stripping BOM in the import pipeline. Re-import succeeded.' },
];

const STATUS_STYLE   = { Open: { bg:'#fef3c7', text:'#d97706', border:'#fde68a' }, Resolved: { bg:'#f0fdf4', text:'#16a34a', border:'#bbf7d0' } };
const PRIORITY_STYLE = { High: { bg:'#fee2e2', text:'#dc2626', border:'#fecaca' }, Medium: { bg:'#fef3c7', text:'#d97706', border:'#fde68a' }, Low: { bg:'#f0fdf4', text:'#16a34a', border:'#bbf7d0' } };

function Badge({ label, style }) {
  return <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ background: style.bg, color: style.text, border: `1px solid ${style.border}` }}>{label}</span>;
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-surface rounded-2xl border border-surface-border shadow-2xl w-full max-w-lg mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[16px] font-bold text-on-background">{title}</h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Toast({ message, onClose }) {
  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex items-center gap-2 px-4 py-3 rounded-xl border shadow-lg text-[13px] font-semibold"
      style={{ background:'#f0fdf4', borderColor:'#bbf7d0', color:'#15803d' }}>
      <span className="material-symbols-outlined" style={{ fontSize:18, fontVariationSettings:"'FILL' 1" }}>check_circle</span>
      {message}
      <button onClick={onClose} className="ml-2 text-green-700 opacity-60 hover:opacity-100">
        <span className="material-symbols-outlined" style={{ fontSize:14 }}>close</span>
      </button>
    </div>
  );
}

// ── Chat widget ───────────────────────────────────────────────────────────────
const BOT_REPLIES = [
  "Thanks for reaching out! Let me connect you with a support agent.",
  "I understand the issue. Could you give me your Ticket ID or Claim ID?",
  "Got it. Our team will follow up within 2 business hours. Is there anything else I can help with?",
  "Happy to help! Our support hours are Mon–Sat, 9am–7pm IST.",
];

function ChatWidget({ onClose }) {
  const [msgs, setMsgs] = useState([{ from: 'bot', text: 'Hi! I\'m the RideShield support bot. How can I help you today?' }]);
  const [input, setInput] = useState('');
  const [botIdx, setBotIdx] = useState(0);

  function send() {
    if (!input.trim()) return;
    const userMsg = { from: 'user', text: input.trim() };
    setMsgs(prev => [...prev, userMsg]);
    setInput('');
    setTimeout(() => {
      const reply = BOT_REPLIES[botIdx % BOT_REPLIES.length];
      setMsgs(prev => [...prev, { from: 'bot', text: reply }]);
      setBotIdx(i => i + 1);
    }, 800);
  }

  return (
    <div className="fixed bottom-6 right-6 z-[9999] w-80 bg-surface rounded-2xl border border-surface-border shadow-2xl flex flex-col overflow-hidden" style={{ height: 400 }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-primary text-on-primary">
        <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>support_agent</span>
        </div>
        <div>
          <p className="text-[13px] font-bold">RideShield Support</p>
          <p className="text-[10px] opacity-70">Typically replies in minutes</p>
        </div>
        <button onClick={onClose} className="ml-auto opacity-70 hover:opacity-100"><span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span></button>
      </div>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-2">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.from === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] px-3 py-2 rounded-xl text-[12px] leading-relaxed ${m.from === 'user' ? 'bg-primary text-on-primary' : 'bg-surface-container border border-surface-border text-on-background'}`}>
              {m.text}
            </div>
          </div>
        ))}
      </div>
      {/* Input */}
      <div className="flex gap-2 px-3 py-3 border-t border-surface-border">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Type a message…"
          className="flex-1 px-3 py-1.5 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low"
        />
        <button onClick={send} className="px-3 py-1.5 bg-primary text-on-primary rounded-lg text-[12px] font-bold hover:bg-primary/90">
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>send</span>
        </button>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function Support() {
  const [openFaq, setOpenFaq]         = useState(null);
  const [subject, setSubject]         = useState('');
  const [message, setMessage]         = useState('');
  const [category, setCategory]       = useState('claims');
  const [submitted, setSubmitted]     = useState(false);
  const [tickets, setTickets]         = useState(INITIAL_TICKETS);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [toast, setToast]             = useState(null);
  const [showChat, setShowChat]       = useState(false);
  const [copiedPhone, setCopiedPhone] = useState(false);

  function showToast(msg) { setToast(msg); setTimeout(() => setToast(null), 3000); }

  function handleSubmit(e) {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) return;
    const newTicket = {
      id: `TKT-${Math.floor(3302 + Math.random() * 100)}`,
      subject: subject.trim(),
      status: 'Open',
      date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
      priority: 'Medium',
      detail: message.trim(),
    };
    setTickets(prev => [newTicket, ...prev]);
    setSubmitted(true);
    setSubject(''); setMessage('');
    setTimeout(() => setSubmitted(false), 4000);
    showToast('Ticket submitted — we\'ll respond within 24 hours');
  }

  function copyPhone() {
    navigator.clipboard?.writeText('+91 1800-456-7890').catch(() => {});
    setCopiedPhone(true);
    setTimeout(() => setCopiedPhone(false), 2000);
    showToast('Phone number copied to clipboard');
  }

  const CONTACT_CARDS = [
    { icon: 'chat_bubble', title: 'Live Chat',    desc: 'Mon–Sat, 9am–7pm IST',      actionLabel: 'Start Chat',   color: '#3b82f6', onClick: () => setShowChat(true) },
    { icon: 'mail',        title: 'Email Us',     desc: 'support@rideshield.in',      actionLabel: 'Send Email',   color: '#8b5cf6', onClick: () => window.open('mailto:support@rideshield.in?subject=RideShield Support Request', '_blank') },
    { icon: 'call',        title: 'Call Support', desc: '+91 1800-456-7890 (toll-free)', actionLabel: copiedPhone ? 'Copied!' : 'Copy Number', color: '#16a34a', onClick: copyPhone },
  ];

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex-1 ml-[260px] flex flex-col min-h-screen">
        <Topbar title="Support" />
        <main className="flex-1 p-8 max-w-4xl mx-auto w-full">

          {/* Quick contact */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
            {CONTACT_CARDS.map(card => (
              <div key={card.title} className="bg-surface rounded-xl border border-surface-border p-5 flex flex-col shadow-sm hover:shadow-md transition-shadow">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: card.color + '18' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 22, color: card.color }}>{card.icon}</span>
                </div>
                <p className="text-[14px] font-bold text-on-background">{card.title}</p>
                <p className="text-[11px] text-on-surface-variant mt-1 mb-4 flex-1">{card.desc}</p>
                <button
                  onClick={card.onClick}
                  className="text-[11px] font-bold px-4 py-1.5 rounded-lg transition-all"
                  style={{ background: card.color + '14', color: card.color, border: `1px solid ${card.color}33` }}
                >
                  {card.actionLabel}
                </button>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Submit Ticket */}
            <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6">
              <h2 className="text-[15px] font-bold text-on-background mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>confirmation_number</span>
                Submit a Ticket
              </h2>
              {submitted ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <span className="material-symbols-outlined text-green-500 mb-2" style={{ fontSize: 44, fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                  <p className="text-[14px] font-bold text-on-background">Ticket Submitted!</p>
                  <p className="text-[12px] text-on-surface-variant mt-1">We'll respond within 24 hours.</p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">Category</label>
                    <select value={category} onChange={e => setCategory(e.target.value)}
                      className="w-full px-3 py-2 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low">
                      <option value="claims">Claims</option>
                      <option value="policies">Policies</option>
                      <option value="riders">Riders / Shifts</option>
                      <option value="billing">Billing</option>
                      <option value="technical">Technical Issue</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">Subject</label>
                    <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Brief description of the issue"
                      className="w-full px-3 py-2 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low" />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">Message</label>
                    <textarea value={message} onChange={e => setMessage(e.target.value)} placeholder="Describe your issue in detail…" rows={4}
                      className="w-full px-3 py-2 border border-surface-border rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-container-low resize-none" />
                  </div>
                  <button type="submit" className="bg-primary text-on-primary py-2 rounded-lg text-[12px] font-bold hover:bg-primary/90 transition-colors">
                    Submit Ticket
                  </button>
                </form>
              )}
            </div>

            {/* My Tickets */}
            <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6">
              <h2 className="text-[15px] font-bold text-on-background mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>inbox</span>
                My Tickets
              </h2>
              <div className="flex flex-col gap-2">
                {tickets.map(t => (
                  <button key={t.id} onClick={() => setSelectedTicket(t)}
                    className="flex items-start justify-between p-3 rounded-lg bg-surface-container border border-surface-border hover:bg-surface-muted transition-colors text-left w-full">
                    <div className="min-w-0 mr-3">
                      <p className="text-[12px] font-bold text-on-background truncate">{t.subject}</p>
                      <p className="text-[10px] text-on-surface-variant mt-0.5">{t.id} · {t.date}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <Badge label={t.status}   style={STATUS_STYLE[t.status]} />
                      <Badge label={t.priority} style={PRIORITY_STYLE[t.priority]} />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* FAQ */}
          <div className="bg-surface rounded-xl border border-surface-border shadow-sm p-6 mb-8">
            <h2 className="text-[15px] font-bold text-on-background mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>quiz</span>
              Frequently Asked Questions
            </h2>
            <div className="flex flex-col gap-1">
              {FAQS.map((faq, i) => (
                <div key={i} className="border border-surface-border rounded-lg overflow-hidden">
                  <button
                    className="w-full flex items-center justify-between px-4 py-3 text-left text-[13px] font-semibold text-on-background hover:bg-surface-muted transition-colors"
                    onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  >
                    <span>{faq.q}</span>
                    <span className="material-symbols-outlined text-on-surface-variant ml-3 flex-shrink-0 transition-transform duration-200"
                      style={{ fontSize: 18, transform: openFaq === i ? 'rotate(180deg)' : 'none' }}>expand_more</span>
                  </button>
                  {openFaq === i && (
                    <div className="px-4 pb-4 pt-3 text-[12px] text-on-surface-variant leading-relaxed border-t border-surface-border">{faq.a}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>

      {/* Toast */}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}

      {/* Live Chat widget */}
      {showChat && <ChatWidget onClose={() => setShowChat(false)} />}

      {/* Ticket Detail Modal */}
      {selectedTicket && (
        <Modal title={selectedTicket.id} onClose={() => setSelectedTicket(null)}>
          <div className="flex gap-2 mb-4">
            <Badge label={selectedTicket.status}   style={STATUS_STYLE[selectedTicket.status]} />
            <Badge label={selectedTicket.priority} style={PRIORITY_STYLE[selectedTicket.priority]} />
            <span className="text-[10px] text-on-surface-variant ml-auto">{selectedTicket.date}</span>
          </div>
          <p className="text-[14px] font-bold text-on-background mb-2">{selectedTicket.subject}</p>
          <p className="text-[12px] text-on-surface-variant leading-relaxed mb-5">{selectedTicket.detail}</p>
          {selectedTicket.status === 'Open' && (
            <button
              onClick={() => {
                setTickets(prev => prev.map(t => t.id === selectedTicket.id ? { ...t, status: 'Resolved' } : t));
                setSelectedTicket(null);
                showToast('Ticket marked as resolved');
              }}
              className="w-full py-2 bg-primary text-on-primary rounded-lg text-[12px] font-bold hover:bg-primary/90 transition-colors"
            >
              Mark as Resolved
            </button>
          )}
        </Modal>
      )}
    </div>
  );
}
