import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SystemEventsSection } from '../../components/sections/SystemEventsSection';
import type { IncidentSummary, ResourceSummary } from '../../api/types';

const mockResources: ResourceSummary[] = [
  {
    resource_id: 'VM-001',
    resource_type: 'VM',
    current_state: 'HEALTHY',
    health_status: 'HEALTHY',
    active_failure_type: null,
    last_heartbeat: '2026-09-09T10:00:00Z',
  },
];

const mockIncidents: IncidentSummary[] = [
  {
    incident_id: 'inc-evt-01',
    resource_id: 'VM-001',
    failure_type: 'HIGH_CPU',
    severity: 'HIGH',
    status: 'RESOLVED',
    detected_at: '2026-09-09T10:00:00Z',
    recovery_started_at: '2026-09-09T10:00:02Z',
    recovered_at: '2026-09-09T10:00:08Z',
    resolved_at: '2026-09-09T10:00:08Z',
    duration_seconds: 6.0,
    recovery_action: 'SCALE_OUT',
    notification_status: 'DELIVERED',
  },
];

describe('SystemEventsSection', () => {
  it('renders system event stream and filters events', () => {
    const handleSelect = vi.fn();
    render(
      <SystemEventsSection
        incidents={mockIncidents}
        resources={mockResources}
        onSelectIncident={handleSelect}
      />
    );

    expect(
      screen.getByText('Real-Time System Observability Event Stream')
    ).toBeInTheDocument();
    expect(screen.getByText('Anomaly Detected: HIGH_CPU')).toBeInTheDocument();
    expect(screen.getByText('Recovery Lambda Triggered: SCALE_OUT')).toBeInTheDocument();
    expect(screen.getByText('Incident Resolved: VM-001 Recovered')).toBeInTheDocument();

    // Filter by RESOLUTION
    const resFilterBtn = screen.getByText('RESOLUTION');
    fireEvent.click(resFilterBtn);

    expect(screen.getByText('Incident Resolved: VM-001 Recovered')).toBeInTheDocument();
    expect(screen.queryByText('Anomaly Detected: HIGH_CPU')).not.toBeInTheDocument();
  });
});
