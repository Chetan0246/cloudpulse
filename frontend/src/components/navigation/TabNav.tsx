import React from 'react';

export type SectionTabId =
  | 'overview'
  | 'resources'
  | 'simulator'
  | 'incidents'
  | 'incident-detail'
  | 'recovery'
  | 'metrics'
  | 'architecture'
  | 'events';

interface TabItem {
  id: SectionTabId;
  label: string;
  icon: string;
  badgeCount?: number;
}

interface TabNavProps {
  activeTab: SectionTabId;
  onSelectTab: (id: SectionTabId) => void;
  activeIncidentsCount?: number;
}

export const TabNav: React.FC<TabNavProps> = ({
  activeTab,
  onSelectTab,
  activeIncidentsCount = 0,
}) => {
  const tabs: TabItem[] = [
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'resources', label: 'Resource Health', icon: '🖥️' },
    { id: 'simulator', label: 'Failure Simulator', icon: '⚡' },
    {
      id: 'incidents',
      label: 'Active Incidents',
      icon: '🚨',
      badgeCount: activeIncidentsCount,
    },
    { id: 'incident-detail', label: 'Incident Details', icon: '🔍' },
    { id: 'recovery', label: 'Recovery Activity', icon: '🛠️' },
    { id: 'metrics', label: 'Reliability Metrics', icon: '📈' },
    { id: 'architecture', label: 'Architecture View', icon: '🗺️' },
    { id: 'events', label: 'System Events', icon: '📜' },
  ];

  return (
    <nav aria-label="Main Navigation" className="border-b border-slate-800 bg-slate-950/70 backdrop-blur sticky top-[57px] z-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex space-x-1 sm:space-x-2 overflow-x-auto py-2 no-scrollbar">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-mono font-medium whitespace-nowrap transition-all duration-150 ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 border border-indigo-500'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
                {typeof tab.badgeCount === 'number' && tab.badgeCount > 0 && (
                  <span
                    className={`ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                      isActive
                        ? 'bg-white text-indigo-700'
                        : 'bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse'
                    }`}
                  >
                    {tab.badgeCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
};
