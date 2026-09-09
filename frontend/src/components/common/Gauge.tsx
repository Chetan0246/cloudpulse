import React from 'react';

interface LinearGaugeProps {
  label: string;
  value: number; // 0 to 100
  unit?: string;
  warnThreshold?: number;
  critThreshold?: number;
  showValue?: boolean;
}

export const LinearGauge: React.FC<LinearGaugeProps> = ({
  label,
  value,
  unit = '%',
  warnThreshold = 70,
  critThreshold = 85,
  showValue = true,
}) => {
  const clamped = Math.max(0, Math.min(100, isNaN(value) ? 0 : value));

  let colorClass = 'bg-emerald-500';
  let textClass = 'text-emerald-400';
  if (clamped >= critThreshold) {
    colorClass = 'bg-rose-500 animate-pulse';
    textClass = 'text-rose-400 font-bold';
  } else if (clamped >= warnThreshold) {
    colorClass = 'bg-amber-500';
    textClass = 'text-amber-400';
  }

  return (
    <div className="w-full">
      <div className="flex justify-between items-center text-xs font-mono mb-1">
        <span className="text-slate-400">{label}</span>
        {showValue && (
          <span className={textClass}>
            {clamped.toFixed(1)}
            {unit}
          </span>
        )}
      </div>
      <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
        <div
          className={`h-full rounded-full transition-all duration-500 ${colorClass}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
};

interface LatencyGaugeProps {
  latencyMs: number;
  warnThreshold?: number; // e.g. 50ms
  critThreshold?: number; // e.g. 100ms
}

export const LatencyGauge: React.FC<LatencyGaugeProps> = ({
  latencyMs,
  warnThreshold = 60,
  critThreshold = 120,
}) => {
  const safeLatency = isNaN(latencyMs) ? 0 : latencyMs;
  // Max scale to 200ms for gauge bar
  const percent = Math.min(100, (safeLatency / 200) * 100);

  let textClass = 'text-emerald-400';
  let barClass = 'bg-emerald-500';
  if (safeLatency >= critThreshold) {
    textClass = 'text-rose-400 font-bold';
    barClass = 'bg-rose-500 animate-pulse';
  } else if (safeLatency >= warnThreshold) {
    textClass = 'text-amber-400';
    barClass = 'bg-amber-500';
  }

  return (
    <div className="w-full">
      <div className="flex justify-between items-center text-xs font-mono mb-1">
        <span className="text-slate-400">Latency</span>
        <span className={textClass}>{safeLatency.toFixed(1)}ms</span>
      </div>
      <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barClass}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
};
