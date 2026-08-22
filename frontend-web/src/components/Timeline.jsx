const TYPE_STYLES = {
  normal:     { icon: 'radio_button_unchecked', color: 'text-on-surface-variant', dot: 'bg-outline' },
  warning:    { icon: 'warning',                color: 'text-status-warning',     dot: 'bg-status-warning' },
  alert:      { icon: 'emergency',              color: 'text-status-emergency',   dot: 'bg-status-emergency' },
  escalation: { icon: 'call',                   color: 'text-primary',            dot: 'bg-primary' },
  verified:   { icon: 'verified',               color: 'text-status-safe',        dot: 'bg-status-safe' },
  claim:      { icon: 'receipt_long',           color: 'text-primary',            dot: 'bg-primary' },
  safe:       { icon: 'check_circle',           color: 'text-status-safe',        dot: 'bg-status-safe' },
};

export default function Timeline({ events = [] }) {
  return (
    <div className="space-y-0">
      {events.map((ev, i) => {
        const style = TYPE_STYLES[ev.type] || TYPE_STYLES.normal;
        const isLast = i === events.length - 1;

        return (
          <div key={i} className="flex gap-4">
            {/* Left column: dot + line */}
            <div className="flex flex-col items-center">
              <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1.5 ${style.dot}`} />
              {!isLast && <div className="w-0.5 flex-1 bg-surface-border mt-1" />}
            </div>

            {/* Right column: content */}
            <div className={`pb-4 min-w-0 flex-1 ${isLast ? 'pb-0' : ''}`}>
              <div className="flex items-start gap-2 flex-wrap">
                <span className={`material-symbols-outlined flex-shrink-0 ${style.color}`} style={{ fontSize: 16 }}>
                  {style.icon}
                </span>
                <span className={`text-[13px] font-medium ${style.color}`}>{ev.event}</span>
              </div>
              <p className="text-[11px] text-on-surface-variant mt-0.5 font-mono">{ev.time}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
