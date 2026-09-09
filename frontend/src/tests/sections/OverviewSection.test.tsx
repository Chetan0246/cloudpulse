import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { OverviewSection } from '../../components/sections/OverviewSection';
import type { ResourceSummary, IncidentSummary } from '../../api/types';

const mockResources: ResourceSummary[] = [
  {
    resource_id: 'VM-001',
    resource_type: 'VM',
    current_state: 'HEALTHY',
    health_status: 'HEALTHY',
    active_failure_type: null,
    last_heartbeat: '2026-09-09T10:00:00Z',
    cpu_utilization: 25.0,
  },
  {
    resource_id: 'API-001',
    resource_type: 'API',
    current_state: 'FAILURE_DETECTED',
    health_status: 'CRITICAL',
    active_failure_type: 'HIGH_CPU',
    last_heartbeat: '2026-09-09T10:00:00Z',
    cpu_utilization: 95.0,
  },
];

const mockIncidents: IncidentSummary[] = [
  {
    incident_id: 'test-inc-1',
    resource_id: 'API-001',
    failure_type: 'HIGH_CPU',
    severity: 'HIGH',
    status: 'OPEN',
    detected_at: '2026-09-09T10:00:00Z',
    resolved_at: null,
  },
  {
    incident_id: 'test-inc-2',
    resource_id: 'VM-001',
    failure_type: 'STORAGE_EXHAUSTION',
    severity: 'MEDIUM',
    status: 'RESOLVED',
    detected_at: '2026-09-09T09:00:00Z',
    resolved_at: '2026-09-09T09:00:10Z',
    duration_seconds: 10.0,
  },
];

describe('OverviewSection', () => {
  it('renders KPI metrics and active alert banner', () => {
    const handleSelectIncident = vi.fn();
    const handleNavigateTab = vi.fn();

    render(
      <OverviewSection
        resources={mockResources}
        incidents={mockIncidents}
        onSelectIncident={handleSelectIncident}
        onNavigateTab={handleNavigateTab}
      />
    );

    expect(screen.getByText('ACTIVE INCIDENT DETECTED — 1 IN FLIGHT')).toBeInTheDocument();
    expect(screen.getByText('Healthy Resources')).toBeInTheDocument();
    expect(screen.getByText('Failed Resources')).toBeInTheDocument();
    expect(screen.getByText('Active Incidents')).toBeInTheDocument();
    expect(screen.getByText('Recovery Success Rate')).toBeInTheDocument();
    expect(screen.getByText('Recent Incidents')).toBeInTheDocument();

    // Inspect recent incident
    const detailsButtons = screen.getAllByText('Details →');
    fireEvent.click(detailsButtons[0]);
    expect(handleSelectIncident).toHaveBeenCalledWith('test-inc-1');
  });

  it('renders nominal banner when no active incidents', () => {
    render(
      <OverviewSection
        resources={mockResources}
        incidents={[mockIncidents[1]]} // only resolved
        onSelectIncident={() => {}}
        onNavigateTab={() => {}}
      />
    );

    expect(screen.getByText('All Simulated Systems Nominal')).toBeInTheDocument();
  });
});
