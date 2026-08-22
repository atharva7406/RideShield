import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function Topbar({ title, subtitle, actions }) {
  const [searchVal, setSearchVal] = useState('');
  const navigate = useNavigate();

  return (
    <header className="bg-surface border-b border-surface-border flex justify-between items-center h-16 px-6 sticky top-0 z-30">
      {/* Left: search */}
      <div className="flex items-center gap-4 flex-1">
        <div className="relative hidden sm:block">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" style={{ fontSize: 18 }}>search</span>
          <input
            value={searchVal}
            onChange={e => setSearchVal(e.target.value)}
            className="pl-9 pr-4 py-2 bg-surface-container-low border border-surface-border rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all w-64"
            placeholder="Search shifts, claims, riders…"
          />
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
        <button className="text-on-surface-variant hover:text-status-emergency transition-colors p-2 rounded-full hover:bg-surface-muted relative">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>notifications</span>
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-status-emergency rounded-full border-2 border-surface" />
        </button>
        <button
          className="hidden md:flex items-center gap-2 px-3 py-1.5 border border-error text-error hover:bg-error-container transition-colors rounded-lg text-[11px] font-bold uppercase tracking-wide"
          onClick={() => navigate('/claims?filter=emergency')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>emergency</span>
          Emergency Log
        </button>
        <button className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-on-primary text-xs font-bold ring-2 ring-transparent hover:ring-primary/30 transition-all ml-1">
          SR
        </button>
      </div>
    </header>
  );
}
