import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from '../../components/navigation/Header';
import { TabNav } from '../../components/navigation/TabNav';

describe('Navigation Components', () => {
  it('renders Header with nominal system status', () => {
    const handleToggle = vi.fn();
    const handleRefresh = vi.fn();
    render(
      <Header
        systemStatus="NOMINAL"
        isPolling={true}
        onTogglePolling={handleToggle}
        onManualRefresh={handleRefresh}
        lastUpdated={new Date('2026-09-09T10:00:00Z')}
        activeIncidentsCount={0}
      />
    );
    expect(screen.getByText('CloudPulse')).toBeInTheDocument();
    expect(screen.getByText('SYSTEM NOMINAL')).toBeInTheDocument();
    expect(screen.getByText('LIVE (10s)')).toBeInTheDocument();

    fireEvent.click(screen.getByText('⏸ Pause'));
    expect(handleToggle).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText('Sync'));
    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });

  it('renders Header with degraded system status and active incidents', () => {
    render(
      <Header
        systemStatus="DEGRADED"
        isPolling={false}
        onTogglePolling={() => {}}
        onManualRefresh={() => {}}
        lastUpdated={null}
        activeIncidentsCount={2}
      />
    );
    expect(screen.getByText('DEGRADED (2 ACTIVE)')).toBeInTheDocument();
    expect(screen.getByText('PAUSED')).toBeInTheDocument();
  });

  it('renders TabNav with 9 sections and switches tab', () => {
    const handleSelectTab = vi.fn();
    render(
      <TabNav
        activeTab="overview"
        onSelectTab={handleSelectTab}
        activeIncidentsCount={3}
      />
    );

    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Resource Health')).toBeInTheDocument();
    expect(screen.getByText('Failure Simulator')).toBeInTheDocument();
    expect(screen.getByText('Active Incidents')).toBeInTheDocument();
    expect(screen.getByText('Incident Details')).toBeInTheDocument();
    expect(screen.getByText('Recovery Activity')).toBeInTheDocument();
    expect(screen.getByText('Reliability Metrics')).toBeInTheDocument();
    expect(screen.getByText('Architecture View')).toBeInTheDocument();
    expect(screen.getByText('System Events')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument(); // active incident count badge

    fireEvent.click(screen.getByText('Failure Simulator'));
    expect(handleSelectTab).toHaveBeenCalledWith('simulator');
  });
});
