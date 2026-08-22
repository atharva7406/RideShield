export default function StatusBadge({ status, size = 'md' }) {
  const styles = {
    PENDING:      'bg-surface-container-high text-on-surface-variant border border-surface-border',
    UNDER_REVIEW: 'bg-[#fef3c7] text-[#92400e] border border-[#fde68a]',
    APPROVED:     'bg-[#d1fae5] text-[#065f46] border border-[#a7f3d0]',
    REJECTED:     'bg-error-container text-on-error-container border border-error-container',
    ACTIVE:       'bg-[#d1fae5] text-[#065f46] border border-[#a7f3d0]',
    ENDED:        'bg-surface-container-high text-on-surface-variant border border-surface-border',
    EXPIRED:      'bg-surface-container-high text-on-surface-variant border border-surface-border',
    HIGH:         'bg-error-container text-on-error-container border border-error-container',
    MEDIUM:       'bg-[#fef3c7] text-[#92400e] border border-[#fde68a]',
    LOW:          'bg-[#d1fae5] text-[#065f46] border border-[#a7f3d0]',
    TRIGGERED:    'bg-[#fef3c7] text-[#92400e] border border-[#fde68a]',
    VERIFIED:     'bg-[#d1fae5] text-[#065f46] border border-[#a7f3d0]',
    NO_RESPONSE:  'bg-error-container text-on-error-container border border-error-container',
    PARTIAL:      'bg-[#fef3c7] text-[#92400e] border border-[#fde68a]',
  };

  const dots = {
    PENDING: '#727687',
    UNDER_REVIEW: '#F59E0B',
    APPROVED: '#10B981',
    REJECTED: '#EF4444',
    ACTIVE: '#10B981',
    ENDED: '#727687',
    HIGH: '#EF4444',
    MEDIUM: '#F59E0B',
    LOW: '#10B981',
    TRIGGERED: '#F59E0B',
    VERIFIED: '#10B981',
    NO_RESPONSE: '#EF4444',
    PARTIAL: '#F59E0B',
  };

  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-[11px]';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-bold uppercase tracking-wide ${sizeClass} ${styles[status] || styles.PENDING}`}>
      {dots[status] && (
        <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: dots[status] }} />
      )}
      {status?.replace(/_/g, ' ')}
    </span>
  );
}
