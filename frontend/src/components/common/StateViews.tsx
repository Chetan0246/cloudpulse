import React from 'react';

interface LoadingStateProps {
  message?: string;
  subtext?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading telemetry data...',
  subtext = 'Connecting to CloudPulse observability engine',
  size = 'md',
}) => {
  const spinnerSizes = {
    sm: 'w-6 h-6 border-2',
    md: 'w-10 h-10 border-3',
    lg: 'w-14 h-14 border-4',
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center p-12 text-center"
    >
      <div className="relative mb-4">
        <div
          className={`${spinnerSizes[size]} rounded-full border-slate-700 border-t-cyan-400 animate-spin`}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
        </div>
      </div>
      <p className="text-sm font-semibold text-slate-200 tracking-wide font-mono">{message}</p>
      {subtext && <p className="text-xs text-slate-400 mt-1 font-mono">{subtext}</p>}
    </div>
  );
};

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  actionText?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to Load Telemetry',
  message,
  onRetry,
  actionText = 'Retry Connection',
}) => {
  return (
    <div
      role="alert"
      className="bg-rose-950/20 border border-rose-500/40 rounded-xl p-6 text-center my-4 shadow-lg shadow-rose-950/30"
    >
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-rose-500/15 text-rose-400 mb-3 border border-rose-500/30">
        <span className="text-xl font-bold">⚠️</span>
      </div>
      <h4 className="text-base font-semibold text-rose-300 mb-1 font-mono">{title}</h4>
      <p className="text-xs text-slate-300 font-mono max-w-lg mx-auto mb-4 bg-slate-950/80 p-3 rounded-lg border border-rose-900/50 break-words leading-relaxed">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-rose-600/30 hover:bg-rose-600/50 focus:ring-2 focus:ring-rose-500 focus:outline-none text-rose-200 text-xs font-semibold rounded-lg border border-rose-500/50 transition-all font-mono"
        >
          <span>🔄</span>
          <span>{actionText}</span>
        </button>
      )}
    </div>
  );
};

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: string;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon = '📡',
  actionText,
  onAction,
}) => {
  return (
    <div className="border border-dashed border-slate-800 rounded-xl p-10 text-center my-4 bg-slate-950/40">
      <div className="text-3xl mb-3">{icon}</div>
      <h4 className="text-sm font-semibold text-slate-200 mb-1 font-mono">{title}</h4>
      <p className="text-xs text-slate-400 max-w-md mx-auto mb-4 font-mono">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center space-x-2 px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 focus:ring-2 focus:ring-cyan-500 focus:outline-none text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition-all font-mono cursor-pointer"
        >
          <span>{actionText}</span>
        </button>
      )}
    </div>
  );
};
