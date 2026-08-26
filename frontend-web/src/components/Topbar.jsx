import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { RIDERS, CLAIMS, SHIFTS } from '../data/mockData';

// Build a flat search index from mock data
function buildIndex() {
  const items = [];

  RIDERS.forEach(r => items.push({
    type: 'Rider',
    icon: 'person',
    label: r.name,
    sub: `${r.id} · ${r.vehicle} · ${r.city}`,
    keywords: `${r.name} ${r.id} ${r.vehicle} ${r.city}`.toLowerCase(),
    href: `/riders/${r.id}`,
  }));

  CLAIMS.forEach(c => items.push({
    type: 'Claim',
    icon: 'description',
    label: c.id,
    sub: `${c.severity ?? 'Claim'} · ${c.status} · ${c.location ?? ''}`,
    keywords: `${c.id} ${c.status} ${c.severity ?? ''} ${c.location ?? ''} ${c.riskLevel ?? ''}`.toLowerCase(),
    href: `/claims/${c.id}`,
  }));

  SHIFTS.forEach(s => items.push({
    type: 'Shift',
    icon: 'two_wheeler',
    label: s.id,
    sub: `Risk ${s.riskScore} · ${s.riskLevel} · ${s.status}`,
    keywords: `${s.id} ${s.riskLevel} ${s.status}`.toLowerCase(),
    href: `/shifts/${s.id}`,
  }));

  return items;
}

const INDEX = buildIndex();

const TYPE_COLOR = {
  Rider: { bg: '#eff6ff', text: '#3b82f6', border: '#bfdbfe' },
  Claim: { bg: '#fef3c7', text: '#d97706', border: '#fde68a' },
  Shift: { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0' },
};

function getUser() {
  try {
    const raw = localStorage.getItem('rs_auth') || localStorage.getItem('user');
    if (!raw) return { name: 'Insurer Admin', initials: 'IA', email: 'admin@rideshield.io', role: 'Insurer Admin' };
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    const name = parsed.name || parsed.fullName || parsed.full_name || parsed.email || 'Insurer Admin';
    const parts = name.trim().split(' ');
    const initials = parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : name.slice(0, 2).toUpperCase();
    return {
      name,
      initials,
      email: parsed.email || `${name.toLowerCase().replace(/\s+/g, '.')}@rideshield.io`,
      role: parsed.role || 'Insurer Admin'
    };
  } catch {
    return { name: 'Insurer Admin', initials: 'IA', email: 'admin@rideshield.io', role: 'Insurer Admin' };
  }
}

export default function Topbar({ title, subtitle, actions }) {
  const [user, setUser] = useState(getUser);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [focused, setFocused] = useState(false);
  const [cursor, setCursor] = useState(-1);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [hasUnread, setHasUnread] = useState(true);

  // Sync user state on storage change
  useEffect(() => {
    const syncUser = () => setUser(getUser());
    window.addEventListener('storage', syncUser);
    return () => window.removeEventListener('storage', syncUser);
  }, []);
  const [notifications, setNotifications] = useState([
    {
      id: 1,
      title: 'High G-Force Impact Detected',
      desc: 'Rahul Sharma (CLM-001) at Worli Naka · 94% crash confidence',
      time: '2m ago',
      type: 'critical',
      unread: true,
      href: '/claims/CLM-001',
    },
    {
      id: 2,
      title: 'Hospital Report Uploaded',
      desc: 'Lilavati Hospital uploaded discharge summary for CLM-002',
      time: '18m ago',
      type: 'info',
      unread: true,
      href: '/claims/CLM-002',
    },
    {
      id: 3,
      title: 'SOS Emergency Escalation',
      desc: 'Shift SH-104 initiated manual emergency alert',
      time: '1h ago',
      type: 'warning',
      unread: false,
      href: '/claims?filter=emergency',
    },
  ]);

  const navigate = useNavigate();
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);
  const notifRef = useRef(null);
  const profileRef = useRef(null);

  // Search logic
  useEffect(() => {
    const q = query.trim().toLowerCase();
    if (!q) { setResults([]); return; }
    const hits = INDEX.filter(item => item.keywords.includes(q)).slice(0, 8);
    setResults(hits);
    setCursor(-1);
  }, [query]);

  // Click-outside closes search and popups
  useEffect(() => {
    function handleClick(e) {
      if (
        !inputRef.current?.contains(e.target) &&
        !dropdownRef.current?.contains(e.target)
      ) {
        setFocused(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setShowNotifications(false);
      }
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setShowProfileMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function handleKey(e) {
    if (!results.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, results.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c - 1, -1)); }
    if (e.key === 'Enter' && cursor >= 0) { go(results[cursor]); }
    if (e.key === 'Escape') { setFocused(false); setQuery(''); }
  }

  function go(item) {
    setQuery('');
    setFocused(false);
    setResults([]);
    navigate(item.href);
  }

  function handleLogout() {
    localStorage.removeItem('insurer_token');
    localStorage.removeItem('user');
    navigate('/login');
  }

  function markAllRead() {
    setNotifications(prev => prev.map(n => ({ ...n, unread: false })));
    setHasUnread(false);
  }

  const showDropdown = focused && query.trim().length > 0;

  return (
    <header className="bg-surface border-b border-surface-border flex justify-between items-center h-16 px-6 sticky top-0 z-30">
      {/* Left: search */}
      <div className="flex items-center gap-4 flex-1">
        <div className="relative hidden sm:block">
          <span
            className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant"
            style={{ fontSize: 18 }}
          >
            search
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={() => setFocused(true)}
            onKeyDown={handleKey}
            className="pl-9 pr-4 py-2 bg-surface-container-low border border-surface-border rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all w-64"
            placeholder="Search shifts, claims, riders…"
            autoComplete="off"
          />

          {/* Search Dropdown */}
          {showDropdown && (
            <div
              ref={dropdownRef}
              className="absolute top-full left-0 mt-1 w-80 bg-surface rounded-xl border border-surface-border shadow-2xl overflow-hidden"
              style={{ zIndex: 999 }}
            >
              {results.length === 0 ? (
                <div className="px-4 py-6 text-center text-[12px] text-on-surface-variant">
                  <span className="material-symbols-outlined block mx-auto mb-1" style={{ fontSize: 24, opacity: 0.3 }}>search_off</span>
                  No results for "<strong>{query}</strong>"
                </div>
              ) : (
                <>
                  <div className="px-3 pt-2 pb-1 text-[10px] font-bold text-on-surface-variant tracking-widest uppercase opacity-60">
                    {results.length} result{results.length !== 1 ? 's' : ''}
                  </div>
                  {results.map((item, i) => {
                    const tc = TYPE_COLOR[item.type];
                    return (
                      <button
                        key={i}
                        className="w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors"
                        style={{ background: cursor === i ? 'rgba(0,0,0,0.04)' : 'transparent' }}
                        onMouseEnter={() => setCursor(i)}
                        onMouseLeave={() => setCursor(-1)}
                        onClick={() => go(item)}
                      >
                        <span
                          className="material-symbols-outlined flex-shrink-0"
                          style={{ fontSize: 16, color: tc.text }}
                        >
                          {item.icon}
                        </span>
                        <span className="flex-1 min-w-0">
                          <span className="block text-[13px] font-semibold text-on-background truncate">{item.label}</span>
                          <span className="block text-[11px] text-on-surface-variant truncate">{item.sub}</span>
                        </span>
                        <span
                          className="text-[9px] font-bold px-1.5 py-0.5 rounded flex-shrink-0"
                          style={{ background: tc.bg, color: tc.text, border: `1px solid ${tc.border}` }}
                        >
                          {item.type.toUpperCase()}
                        </span>
                      </button>
                    );
                  })}
                  <div className="px-3 py-1.5 border-t border-surface-border text-[10px] text-on-surface-variant opacity-50 flex gap-3">
                    <span>↑↓ navigate</span><span>↵ open</span><span>Esc close</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Center: page title */}
      {title && (
        <div className="flex-1 text-center hidden md:block">
          <span className="text-[18px] font-bold text-on-surface">{title}</span>
          {subtitle && <p className="text-[11px] text-on-surface-variant">{subtitle}</p>}
        </div>
      )}

      {/* Right: actions */}
      <div className="flex items-center gap-3 flex-1 justify-end">
        {actions}

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowProfileMenu(false);
            }}
            className="text-on-surface-variant hover:text-primary transition-colors p-2 rounded-full hover:bg-surface-muted relative flex items-center justify-center cursor-pointer"
            title="Notifications"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>notifications</span>
            {hasUnread && (
              <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-surface animate-pulse" />
            )}
          </button>

          {/* Notifications Dropdown Panel */}
          {showNotifications && (
            <div
              className="absolute right-0 mt-2 w-80 sm:w-96 bg-surface rounded-2xl border border-surface-border shadow-2xl overflow-hidden animate-fadeIn"
              style={{ zIndex: 1000 }}
            >
              <div className="px-4 py-3 border-b border-surface-border flex items-center justify-between bg-surface-container-low">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[14px] text-on-surface">Incident Alerts</span>
                  {hasUnread && (
                    <span className="bg-red-100 text-red-700 text-[10px] font-bold px-2 py-0.5 rounded-full">
                      New
                    </span>
                  )}
                </div>
                {hasUnread && (
                  <button
                    onClick={markAllRead}
                    className="text-[11px] font-semibold text-primary hover:underline"
                  >
                    Mark read
                  </button>
                )}
              </div>

              <div className="divide-y divide-surface-border max-h-80 overflow-y-auto">
                {notifications.map(n => (
                  <div
                    key={n.id}
                    onClick={() => {
                      setShowNotifications(false);
                      navigate(n.href);
                    }}
                    className={`p-3.5 hover:bg-surface-container transition-colors cursor-pointer flex gap-3 items-start ${
                      n.unread ? 'bg-primary/5' : ''
                    }`}
                  >
                    <span
                      className="material-symbols-outlined text-[20px] mt-0.5"
                      style={{
                        color:
                          n.type === 'critical' ? '#ef4444' : n.type === 'warning' ? '#f59e0b' : '#3b82f6',
                      }}
                    >
                      {n.type === 'critical' ? 'emergency' : n.type === 'warning' ? 'warning' : 'info'}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-[12px] font-bold text-on-surface truncate">{n.title}</span>
                        <span className="text-[10px] text-on-surface-variant whitespace-nowrap">{n.time}</span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant mt-0.5 line-clamp-2 leading-relaxed">{n.desc}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-2 border-t border-surface-border bg-surface-container-low text-center">
                <button
                  onClick={() => {
                    setShowNotifications(false);
                    navigate('/claims');
                  }}
                  className="text-[12px] font-bold text-primary hover:underline py-1 w-full"
                >
                  View All Claims & Alerts →
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Emergency Log Button */}
        <button
          className="hidden md:flex items-center gap-2 px-3 py-1.5 border border-error text-error hover:bg-error-container transition-colors rounded-lg text-[11px] font-bold uppercase tracking-wide cursor-pointer"
          onClick={() => navigate('/claims?filter=emergency')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>emergency</span>
          Emergency Log
        </button>

        {/* Profile Avatar & Dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => {
              setShowProfileMenu(!showProfileMenu);
              setShowNotifications(false);
            }}
            className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-on-primary text-xs font-bold ring-2 ring-transparent hover:ring-primary/40 transition-all ml-1 cursor-pointer"
            title="Account & Profile"
          >
            {user.initials}
          </button>

          {/* Profile Menu Popup */}
          {showProfileMenu && (
            <div
              className="absolute right-0 mt-2 w-56 bg-surface rounded-2xl border border-surface-border shadow-2xl overflow-hidden py-1.5 animate-fadeIn"
              style={{ zIndex: 1000 }}
            >
              {/* User Header */}
              <div className="px-4 py-3 border-b border-surface-border bg-surface-container-low">
                <p className="text-[13px] font-bold text-on-surface truncate">{user.name}</p>
                <p className="text-[11px] text-on-surface-variant truncate">{user.email}</p>
                <span className="inline-block mt-1.5 bg-primary/10 text-primary text-[10px] font-bold px-2 py-0.5 rounded-full">
                  {user.role}
                </span>
              </div>

              {/* Links */}
              <div className="py-1">
                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    navigate('/settings');
                  }}
                  className="w-full px-4 py-2 text-left text-[12px] font-medium text-on-surface hover:bg-surface-container flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px] text-on-surface-variant">settings</span>
                  Settings & Preferences
                </button>

                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    navigate('/support');
                  }}
                  className="w-full px-4 py-2 text-left text-[12px] font-medium text-on-surface hover:bg-surface-container flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px] text-on-surface-variant">help</span>
                  Help & Support Desk
                </button>

                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    navigate('/policies');
                  }}
                  className="w-full px-4 py-2 text-left text-[12px] font-medium text-on-surface hover:bg-surface-container flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px] text-on-surface-variant">verified_user</span>
                  Policy Coverage Rules
                </button>
              </div>

              {/* Logout */}
              <div className="border-t border-surface-border pt-1">
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2 text-left text-[12px] font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px] text-red-600">logout</span>
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
