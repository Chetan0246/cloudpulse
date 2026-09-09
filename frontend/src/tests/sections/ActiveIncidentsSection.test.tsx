import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ActiveIncidentsSection } from '../../components/sections/ActiveIncidentsSection';
import type { IncidentSummary } from '../../api/types';

const mockIncidents: IncidentSummary[] = [
  {
    incident_id: 'inc-001',
    resource_id: 'VM-001',
    failure_type: 'HIGH_CPU',
    severity: 'CRITICAL',
    status: 'OPEN',
    detected_at: '2026-09-09T10:00:00Z',
    resolved_at: null,
    recovery_action: 'SCALE_OUT',
    recovery_result: 'IN_PROGRESS',
  },
  {
    incident_id: 'inc-002',
    resource_id: 'DB-001',
    failure_type: 'SERVICE_FAILURE',
    severity: 'MEDIUM',
    status: 'RESOLVED',
    detected_at: '2026-09-09T09:00:00Z',
    resolved_at: '2026-09-09T09:00:15Z',
    duration_seconds: 15.0,
    recovery_action: 'SERVICE_RESTART',
    recovery_result: 'SUCCEEDED',
  },
];

describe('ActiveIncidentsSection', () => {
  it('renders incidents and filters by status', () => {
    const handleSelect = vi.fn();
    render(
      <ActiveIncidentsSection
        incidents={mockIncidents}
        onSelectIncident={handleSelect}
      />
    );

    expect(screen.getByText('Incident Lifecycle Telemetry')).toBeInTheDocument();
    expect(screen.getByText('VM-001')).toBeInTheDocument();
    expect(screen.getByText('DB-001')).toBeInTheDocument();

    // Filter by OPEN
    const openBtn = screen.getByRole('button', { name: 'OPEN' });
    fireEvent.click(openBtn);
    expect(screen.getByText('VM-001')).toBeInTheDocument();
    expect(screen.queryByText('DB-001')).not.toBeInTheDocument();
  });

  it('filters by search query', () => {
    render(
      <ActiveIncidentsSection
        incidents={mockIncidents}
        onSelectIncident={vi.fn()}
      />
    );

    const searchInput = screen.getByPlaceholderText('Search Incident / Resource ID...');
    fireEvent.change(searchInput, { target: { value: 'DB-001' } });

    expect(screen.queryByText('VM-001')).not.toBeInTheDocument();
    expect(screen.getByText('DB-001')).toBeInTheDocument();
  });

  it('triggers onSelectIncident on click', () => {
    const handleSelect = vi.fn();
    render(
      <ActiveIncidentsSection
        incidents={mockIncidents}
        onSelectIncident={handleSelect}
      />
    );

    const inspectButtons = screen.getAllByText('Inspect →');
    fireEvent.click(inspectButtons[0]);
    expect(handleSelect).toHaveBeenCalledWith('inc-001');
  });
});
