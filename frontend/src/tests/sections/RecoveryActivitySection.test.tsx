import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RecoveryActivitySection } from '../../components/sections/RecoveryActivitySection';
import type { IncidentSummary } from '../../api/types';

const mockIncidents: IncidentSummary[] = [
  {
    incident_id: 'inc-01',
    resource_id: 'VM-001',
    failure_type: 'HIGH_CPU',
    severity: 'HIGH',
    status: 'RESOLVED',
    detected_at: '2026-09-09T10:00:00Z',
    resolved_at: '2026-09-09T10:00:06Z',
    duration_seconds: 6.0,
    recovery_action: 'SCALE_OUT',
    recovery_result: 'SUCCEEDED',
  },
  {
    incident_id: 'inc-02',
    resource_id: 'DB-001',
    failure_type: 'STORAGE_EXHAUSTION',
    severity: 'MEDIUM',
    status: 'RESOLVED',
    detected_at: '2026-09-09T10:05:00Z',
    resolved_at: '2026-09-09T10:05:04Z',
    duration_seconds: 4.0,
    recovery_action: 'STORAGE_CLEANUP',
    recovery_result: 'SUCCEEDED',
  },
];

describe('RecoveryActivitySection', () => {
  it('renders recovery strategies and audit stream', () => {
    const handleSelect = vi.fn();
    render(
      <RecoveryActivitySection
        incidents={mockIncidents}
        onSelectIncident={handleSelect}
      />
    );

    expect(screen.getByText('Total Actions')).toBeInTheDocument();
    expect(screen.getByText('Succeeded')).toBeInTheDocument();
    expect(screen.getByText('Self-Healing Strategy Distribution')).toBeInTheDocument();
    expect(screen.getByText('Dynamic Scaling')).toBeInTheDocument();
    expect(screen.getByText('Disk Reclamation')).toBeInTheDocument();
    expect(screen.getByText('VM-001')).toBeInTheDocument();
    expect(screen.getByText('DB-001')).toBeInTheDocument();

    // Click an audit item
    fireEvent.click(screen.getByText('VM-001'));
    expect(handleSelect).toHaveBeenCalledWith('inc-01');
  });
});
