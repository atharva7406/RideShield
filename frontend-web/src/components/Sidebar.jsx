import { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/dashboard',    icon: 'dashboard',      label: 'Overview' },
  { to: '/active-shifts',icon: 'speed',          label: 'Active Shifts' },
  { to: '/claims',       icon: 'request_quote',  label: 'Claims' },
  { to: '/policies',     icon: 'verified_user',  label: 'Policies' },
  { to: '/analytics',    icon: 'analytics',      label: 'Analytics' },
];

const BOTTOM_ITEMS = [
  { to: '/settings', icon: 'settings', label: 'Settings' },
  { to: '/support',  icon: 'help',     label: 'Support' },
];

function getUser() {
  try {
    const raw = localStorage.getItem('rs_auth');
    if (!raw) return { name: 'User', initials: 'U', email: '' };
    const parsed = JSON.parse(raw);
    const name = parsed.name || parsed.email || 'User';
    const parts = name.trim().split(' ');
    const initials = parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : name.slice(0, 2).toUpperCase();
    return { name, initials, email: parsed.email || '' };
  } catch {
    return { name: 'User', initials: 'U', email: '' };
  }
}

export default function Sidebar() {
  const navigate = useNavigate();
  const [user, setUser] = useState(getUser);

  // Re-read when Settings saves (dispatches 'storage' event)
  useEffect(() => {
    const handler = () => setUser(getUser());
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  function handleLogout() {
    localStorage.removeItem('rs_auth');
    navigate('/login');
  }

  return (
    <aside className="fixed left-0 top-0 h-screen w-[260px] bg-surface-container-high border-r border-surface-border flex flex-col py-8 z-40">
      {/* Brand */}
      <div className="px-6 mb-8 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary flex-shrink-0">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>shield</span>
        </div>
        <div>
          <h1 className="text-[20px] font-bold leading-none text-primary">RideShield</h1>
          <p className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-widest mt-0.5">Insurer Portal</p>
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-3 overflow-y-auto scrollbar-thin">
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-r-lg border-l-4 transition-all duration-150 text-[12px] font-semibold tracking-wide uppercase ${
                isActive
                  ? 'bg-surface-container text-primary border-primary'
                  : 'text-on-surface-variant hover:bg-surface-muted border-transparent hover:border-outline-variant'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className="material-symbols-outlined"
                  style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0", fontSize: 20 }}
                >
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="px-3 pt-4 mt-4 border-t border-surface-border flex flex-col gap-0.5">
        {BOTTOM_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 transition-colors rounded-lg text-[12px] font-semibold tracking-wide uppercase ${
                isActive
                  ? 'bg-surface-container text-primary'
                  : 'text-on-surface-variant hover:bg-surface-muted'
              }`
            }
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}

        {/* User */}
        <button
          onClick={handleLogout}
          className="mt-3 flex items-center gap-3 px-4 py-3 hover:bg-surface-muted rounded-lg w-full transition-colors group"
        >
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-on-primary text-xs font-bold flex-shrink-0">
            {user.initials}
          </div>
          <div className="text-left min-w-0">
            <p className="text-[13px] font-semibold text-on-surface truncate">{user.name}</p>
            <p className="text-[11px] text-on-surface-variant">Sign out</p>
          </div>
          <span className="material-symbols-outlined text-on-surface-variant ml-auto group-hover:text-status-emergency transition-colors" style={{ fontSize: 16 }}>logout</span>
        </button>
      </div>
    </aside>
  );
}
