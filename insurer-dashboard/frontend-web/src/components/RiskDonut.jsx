export default function RiskDonut({ distribution, totalLabel = 'Total', total }) {
  const { low = 75, medium = 20, high = 5 } = distribution || {};

  // SVG donut: r=40, circumference = 2π×40 ≈ 251.2
  const C = 251.2;
  const lowLen   = (low   / 100) * C;
  const medLen   = (medium / 100) * C;
  const highLen  = (high  / 100) * C;

  const highOffset = 0;
  const medOffset  = -(highLen);
  const lowOffset  = -(highLen + medLen);

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-48 h-48">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          {/* Track */}
          <circle cx="50" cy="50" r="40" fill="transparent" stroke="#f2f3ff" strokeWidth="14" />
          {/* High Risk */}
          <circle cx="50" cy="50" r="40" fill="transparent" stroke="#EF4444"
            strokeDasharray={`${highLen} ${C}`} strokeDashoffset={highOffset} strokeWidth="14"
            strokeLinecap="butt" />
          {/* Medium Risk */}
          <circle cx="50" cy="50" r="40" fill="transparent" stroke="#F59E0B"
            strokeDasharray={`${medLen} ${C}`} strokeDashoffset={medOffset} strokeWidth="14"
            strokeLinecap="butt" />
          {/* Low Risk */}
          <circle cx="50" cy="50" r="40" fill="transparent" stroke="#10B981"
            strokeDasharray={`${lowLen} ${C}`} strokeDashoffset={lowOffset} strokeWidth="14"
            strokeLinecap="butt" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">{totalLabel}</span>
          <span className="text-[28px] font-bold text-on-background leading-none">{total?.toLocaleString() ?? '1,248'}</span>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-5 w-full space-y-2.5">
        {[
          { label: 'Low Risk',    color: '#10B981', pct: low,    count: Math.round(total * low / 100) || 936 },
          { label: 'Medium Risk', color: '#F59E0B', pct: medium, count: Math.round(total * medium / 100) || 250 },
          { label: 'High Risk',   color: '#EF4444', pct: high,   count: Math.round(total * high / 100) || 62 },
        ].map(item => (
          <div key={item.label} className="flex justify-between items-center text-[13px]">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
              <span className="text-on-background">{item.label}</span>
            </div>
            <div className="flex items-center gap-3 text-right">
              <span className="text-on-surface-variant">{item.count.toLocaleString()}</span>
              <span className="font-semibold w-9 text-right">{item.pct}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
