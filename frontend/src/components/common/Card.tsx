import React from 'react';

interface PanelProps {
  title?: string;
  subtitle?: string;
  badge?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export const Panel: React.FC<PanelProps> = ({
  title,
  subtitle,
  badge,
  action,
  className = '',
  children,
}) => {
  return (
    <div
      className={`bg-slate-900/80 border border-slate-800/80 rounded-xl p-5 shadow-lg backdrop-blur-sm transition-all duration-200 hover:border-slate-700/80 ${className}`}
    >
      {(title || subtitle || action || badge) && (
        <div className="flex items-start justify-between mb-4 pb-3 border-b border-slate-800/60">
          <div>
            <div className="flex items-center space-x-2">
              {title && <h3 className="text-base font-semibold text-slate-100 tracking-wide">{title}</h3>}
              {badge}
            </div>
            {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
          </div>
          {action && <div className="flex items-center space-x-2">{action}</div>}
        </div>
      )}
      <div>{children}</div>
    </div>
  );
};

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon?: string;
  status?: 'emerald' | 'amber' | 'rose' | 'cyan' | 'purple' | 'slate';
  badge?: React.ReactNode;
  onClick?: () => void;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtext,
  icon,
  status = 'slate',
  badge,
  onClick,
}) => {
  const statusStyles: Record<string, { border: string; glow: string; text: string; bg: string }> = {
    emerald: {
      border: 'border-emerald-500/30 hover:border-emerald-500/50',
      glow: 'from-emerald-500/5 to-transparent',
      text: 'text-emerald-400',
      bg: 'bg-emerald-500/10 text-emerald-300',
    },
    amber: {
      border: 'border-amber-500/30 hover:border-amber-500/50',
      glow: 'from-amber-500/5 to-transparent',
      text: 'text-amber-400',
      bg: 'bg-amber-500/10 text-amber-300',
    },
    rose: {
      border: 'border-rose-500/30 hover:border-rose-500/50',
      glow: 'from-rose-500/5 to-transparent',
      text: 'text-rose-400',
      bg: 'bg-rose-500/10 text-rose-300',
    },
    cyan: {
      border: 'border-cyan-500/30 hover:border-cyan-500/50',
      glow: 'from-cyan-500/5 to-transparent',
      text: 'text-cyan-400',
      bg: 'bg-cyan-500/10 text-cyan-300',
    },
    purple: {
      border: 'border-purple-500/30 hover:border-purple-500/50',
      glow: 'from-purple-500/5 to-transparent',
      text: 'text-purple-400',
      bg: 'bg-purple-500/10 text-purple-300',
    },
    slate: {
      border: 'border-slate-800 hover:border-slate-700',
      glow: 'from-slate-800/10 to-transparent',
      text: 'text-slate-200',
      bg: 'bg-slate-800/50 text-slate-300',
    },
  };

  const currentTheme = statusStyles[status] || statusStyles.slate;

  return (
    <div
      onClick={onClick}
      className={`relative overflow-hidden bg-slate-900/90 border rounded-xl p-4 shadow-md bg-gradient-to-br ${currentTheme.glow} ${currentTheme.border} ${
        onClick ? 'cursor-pointer transform transition-transform hover:-translate-y-0.5' : ''
      }`}
    >
      <div className="flex items-center justify-between text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
        <span>{title}</span>
        {icon && (
          <span className={`p-1.5 rounded-lg text-sm ${currentTheme.bg}`}>
            {icon}
          </span>
        )}
      </div>
      <div className="flex items-baseline space-x-2">
        <span className={`text-2xl lg:text-3xl font-bold font-mono tracking-tight ${currentTheme.text}`}>
          {value}
        </span>
        {badge}
      </div>
      {subtext && <p className="text-xs text-slate-400 mt-1.5 truncate">{subtext}</p>}
    </div>
  );
};

interface StatBoxProps {
  label: string;
  value: string | number;
  highlight?: boolean;
}

export const StatBox: React.FC<StatBoxProps> = ({ label, value, highlight = false }) => {
  return (
    <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5">
      <div className="text-[11px] font-mono text-slate-400 uppercase">{label}</div>
      <div className={`text-sm font-mono font-semibold mt-0.5 ${highlight ? 'text-cyan-400' : 'text-slate-200'}`}>
        {value}
      </div>
    </div>
  );
};
