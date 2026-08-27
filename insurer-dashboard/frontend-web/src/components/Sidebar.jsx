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

export default function Sidebar() {
  const navigate = useNavigate();
  const auth = JSON.parse(localStorage.getItem('rs_auth') || '{}');
  const name = auth.name || 'Insurer';
  const email = auth.email || '';

  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('rs_sidebar_collapsed') === 'true';
  });

  useEffect(() => {
    if (isCollapsed) {
      document.body.classList.add('sidebar-collapsed');
    } else {
      document.body.classList.remove('sidebar-collapsed');
    }
  }, [isCollapsed]);

  const toggleCollapse = () => {
    const nextState = !isCollapsed;
    setIsCollapsed(nextState);
    localStorage.setItem('rs_sidebar_collapsed', String(nextState));
  };

  const initials = name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'SR';

  function handleLogout() {
    localStorage.removeItem('rs_auth');
    navigate('/login');
  }

  return (
    <aside className={`fixed left-0 top-0 h-screen bg-surface-container-high border-r border-surface-border flex flex-col py-8 z-40 transition-all duration-200 ${isCollapsed ? 'w-[72px]' : 'w-[260px]'}`}>
      {/* Brand & Toggle */}
      <div className={`mb-8 flex items-center ${isCollapsed ? 'flex-col gap-4 px-2' : 'justify-between px-6'}`}>
        {!isCollapsed && (
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary flex-shrink-0">
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>shield</span>
            </div>
            <div>
              <h1 className="text-[20px] font-bold leading-none text-primary">RideShield</h1>
              <p className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-widest mt-0.5">Insurer Portal</p>
            </div>
          </div>
        )}
        {isCollapsed && (
          <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary flex-shrink-0">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>shield</span>
          </div>
        )}
        <button
          onClick={toggleCollapse}
          className="w-8 h-8 rounded-full hover:bg-surface-muted flex items-center justify-center text-on-surface-variant transition-colors cursor-pointer"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
            {isCollapsed ? 'menu' : 'menu_open'}
          </span>
        </button>
      </div>

      {/* Main nav */}
      <nav className={`flex-1 flex flex-col gap-0.5 overflow-y-auto scrollbar-thin transition-all duration-200 ${isCollapsed ? 'px-1' : 'px-3'}`}>
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            title={isCollapsed ? item.label : undefined}
            className={({ isActive }) =>
              `flex items-center rounded-lg transition-all duration-150 text-[12px] font-semibold tracking-wide uppercase ${
                isCollapsed
                  ? 'justify-center py-3'
                  : 'gap-3 px-4 py-3 rounded-r-lg border-l-4'
              } ${
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
                {!isCollapsed && <span>{item.label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className={`pt-4 mt-4 border-t border-surface-border flex flex-col gap-0.5 transition-all duration-200 ${isCollapsed ? 'px-1' : 'px-3'}`}>
        {BOTTOM_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            title={isCollapsed ? item.label : undefined}
            className={`flex items-center rounded-lg transition-colors text-[12px] font-semibold tracking-wide uppercase ${
              isCollapsed
                ? 'justify-center py-3 text-on-surface-variant hover:bg-surface-muted'
                : 'gap-3 px-4 py-3 text-on-surface-variant hover:bg-surface-muted'
            }`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{item.icon}</span>
            {!isCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}

        {/* User */}
        <button
          onClick={handleLogout}
          title={isCollapsed ? `Sign out (${name})` : undefined}
          className={`flex items-center hover:bg-surface-muted rounded-lg transition-colors group cursor-pointer ${
            isCollapsed ? 'justify-center py-3 mt-3' : 'mt-3 gap-3 px-4 py-3 w-full'
          }`}
        >
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-on-primary text-xs font-bold flex-shrink-0">{initials}</div>
          {!isCollapsed && (
            <>
              <div className="text-left min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-on-surface truncate">{name}</p>
                <p className="text-[11px] text-on-surface-variant truncate">{email || 'Sign out'}</p>
              </div>
              <span className="material-symbols-outlined text-on-surface-variant ml-auto group-hover:text-status-emergency transition-colors" style={{ fontSize: 16 }}>logout</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

