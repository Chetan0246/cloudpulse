import React from 'react';

/**
 * Pure SVG Donut / Circular Ring Chart for Availability and Health Scores.
 * No external charting library required.
 */
interface DonutGaugeProps {
  value: number; // 0 - 100
  size?: number;
  strokeWidth?: number;
  label?: string;
  subtext?: string;
  color?: 'emerald' | 'cyan' | 'amber' | 'rose' | 'purple';
}

export const DonutGauge: React.FC<DonutGaugeProps> = ({
  value,
  size = 120,
  strokeWidth = 10,
  label = 'Availability',
  subtext = 'SLO: 99.9%',
  color = 'emerald',
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedValue = Math.max(0, Math.min(100, isNaN(value) ? 0 : value));
  const offset = circumference - (clampedValue / 100) * circumference;

  const colorMap = {
    emerald: {
      stroke: 'stroke-emerald-400',
      text: 'text-emerald-400',
      glow: 'drop-shadow(0 0 6px rgba(52, 211, 153, 0.4))',
    },
    cyan: {
      stroke: 'stroke-cyan-400',
      text: 'text-cyan-400',
      glow: 'drop-shadow(0 0 6px rgba(34, 211, 238, 0.4))',
    },
    amber: {
      stroke: 'stroke-amber-400',
      text: 'text-amber-400',
      glow: 'drop-shadow(0 0 6px rgba(251, 191, 36, 0.4))',
    },
    rose: {
      stroke: 'stroke-rose-400',
      text: 'text-rose-400',
      glow: 'drop-shadow(0 0 6px rgba(244, 63, 94, 0.4))',
    },
    purple: {
      stroke: 'stroke-purple-400',
      text: 'text-purple-400',
      glow: 'drop-shadow(0 0 6px rgba(192, 132, 252, 0.4))',
    },
  };

  const currentTheme = colorMap[color] || colorMap.emerald;

  return (
    <div className="flex flex-col items-center justify-center font-mono">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          className="transform -rotate-90"
          style={{ filter: currentTheme.glow }}
          role="img"
          aria-label={`${label}: ${clampedValue.toFixed(1)}%`}
        >
          {/* Background track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            className="stroke-slate-800/80 fill-none"
            strokeWidth={strokeWidth}
          />
          {/* Progress stroke */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            className={`${currentTheme.stroke} fill-none transition-all duration-1000 ease-out`}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className={`text-base font-bold tracking-tight ${currentTheme.text}`}>
            {clampedValue.toFixed(1)}%
          </span>
        </div>
      </div>
      <span className="text-xs font-semibold text-slate-300 mt-2">{label}</span>
      {subtext && <span className="text-[10px] text-slate-500">{subtext}</span>}
    </div>
  );
};

/**
 * Segmented Fleet Health Bar Chart
 * Displays proportion of Healthy, Warning, Failed, and Recovering resources.
 */
interface SegmentedHealthBarProps {
  total: number;
  healthy: number;
  warning: number;
  failed: number;
  recovering: number;
}

export const SegmentedHealthBar: React.FC<SegmentedHealthBarProps> = ({
  total,
  healthy,
  warning,
  failed,
  recovering,
}) => {
  const safeTotal = Math.max(1, total);
  const healthyPct = (healthy / safeTotal) * 100;
  const warningPct = (warning / safeTotal) * 100;
  const failedPct = (failed / safeTotal) * 100;
  const recoveringPct = (recovering / safeTotal) * 100;

  return (
    <div className="w-full space-y-2 font-mono">
      <div className="flex justify-between items-center text-xs">
        <span className="text-slate-400 font-medium">Fleet Health Status Distribution</span>
        <span className="text-slate-300 font-semibold">{total} Total Resources</span>
      </div>

      <div
        className="w-full h-3 bg-slate-950 rounded-full overflow-hidden flex border border-slate-800"
        role="progressbar"
        aria-label="Fleet health distribution"
      >
        {healthyPct > 0 && (
          <div
            title={`Healthy: ${healthy} (${healthyPct.toFixed(0)}%)`}
            style={{ width: `${healthyPct}%` }}
            className="h-full bg-emerald-500 transition-all duration-500 hover:brightness-110"
          />
        )}
        {warningPct > 0 && (
          <div
            title={`Warning: ${warning} (${warningPct.toFixed(0)}%)`}
            style={{ width: `${warningPct}%` }}
            className="h-full bg-amber-500 transition-all duration-500 hover:brightness-110"
          />
        )}
        {failedPct > 0 && (
          <div
            title={`Failed: ${failed} (${failedPct.toFixed(0)}%)`}
            style={{ width: `${failedPct}%` }}
            className="h-full bg-rose-500 transition-all duration-500 hover:brightness-110 animate-pulse"
          />
        )}
        {recoveringPct > 0 && (
          <div
            title={`Recovering: ${recovering} (${recoveringPct.toFixed(0)}%)`}
            style={{ width: `${recoveringPct}%` }}
            className="h-full bg-cyan-400 transition-all duration-500 hover:brightness-110 animate-pulse"
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-slate-400">
        <div className="flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span>Healthy: <strong className="text-slate-200">{healthy}</strong></span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          <span>Warning: <strong className="text-slate-200">{warning}</strong></span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-rose-400" />
          <span>Failed: <strong className="text-slate-200">{failed}</strong></span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          <span>Recovering: <strong className="text-slate-200">{recovering}</strong></span>
        </div>
      </div>
    </div>
  );
};

/**
 * Responsive Incident Bar Chart
 * Displays incident counts by failure type with pure CSS bars.
 */
interface IncidentBarChartProps {
  data: Record<string, number>;
  totalIncidents?: number;
}

export const IncidentBarChart: React.FC<IncidentBarChartProps> = ({
  data,
  totalIncidents,
}) => {
  const entries = Object.entries(data);
  const total = totalIncidents ?? entries.reduce((sum, [, count]) => sum + count, 0);
  const maxCount = Math.max(1, ...entries.map(([, count]) => count));

  if (entries.length === 0) {
    return (
      <div className="text-center py-6 text-xs font-mono text-slate-500">
        No incident data recorded for this window.
      </div>
    );
  }

  const failureColorMap: Record<string, string> = {
    HIGH_CPU: 'bg-amber-500',
    SERVICE_FAILURE: 'bg-rose-500',
    STORAGE_EXHAUSTION: 'bg-indigo-500',
    NETWORK_LATENCY: 'bg-cyan-500',
    SERVICE_DOWNTIME: 'bg-purple-500',
  };

  return (
    <div className="space-y-3 font-mono">
      {entries.map(([type, count]) => {
        const percentOfMax = (count / maxCount) * 100;
        const percentOfTotal = total > 0 ? ((count / total) * 100).toFixed(0) : '0';
        const color = failureColorMap[type] || 'bg-slate-500';

        return (
          <div key={type} className="space-y-1">
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-300 font-medium truncate">{type}</span>
              <span className="text-slate-400 text-[11px]">
                <strong className="text-slate-200">{count}</strong> ({percentOfTotal}%)
              </span>
            </div>
            <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
              <div
                className={`h-full rounded-full transition-all duration-500 ${color}`}
                style={{ width: `${percentOfMax}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

/**
 * Pure SVG Mini Sparkline
 */
interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export const Sparkline: React.FC<SparklineProps> = ({
  data,
  width = 100,
  height = 24,
  color = '#22d3ee',
}) => {
  if (data.length < 2) {
    return <span className="text-[10px] text-slate-500 font-mono">No trend</span>;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((val, idx) => {
      const x = (idx / (data.length - 1)) * (width - 4) + 2;
      const y = height - ((val - min) / range) * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} className="overflow-visible inline-block">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
};
