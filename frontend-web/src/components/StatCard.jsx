export default function StatCard({ label, value, subtext, icon, iconBg = 'text-primary', badge, highlight }) {
  return (
    <div className={`bg-surface rounded-xl p-6 border shadow-sm flex flex-col justify-between transition-shadow hover:shadow-md ${
      highlight ? 'border-status-emergency/30 ring-1 ring-status-emergency/20 relative overflow-hidden' : 'border-surface-border'
    }`}>
      {highlight && <div className="absolute inset-0 bg-error-container/10 pointer-events-none" />}
      <div className="relative flex justify-between items-start mb-4">
        <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">{label}</p>
        <div className={`p-2 rounded-lg ${highlight ? 'bg-error-container' : 'bg-surface-container'} ${iconBg}`}>
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{icon}</span>
        </div>
      </div>
      <div className="relative">
        <h3 className={`text-[42px] font-bold leading-none tracking-tight ${highlight ? 'text-status-emergency' : 'text-on-background'}`}>
          {value}
        </h3>
        {subtext && (
          <div className={`flex items-center gap-1 mt-2 text-[12px] font-semibold ${highlight ? 'text-status-emergency' : 'text-on-surface-variant'}`}>
            {badge && <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{badge}</span>}
            <span>{subtext}</span>
          </div>
        )}
      </div>
    </div>
  );
}
