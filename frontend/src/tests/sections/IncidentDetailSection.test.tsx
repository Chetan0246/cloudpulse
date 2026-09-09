import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { IncidentDetailSection } from '../../components/sections/IncidentDetailSection';
import { incidentsApi } from '../../api/incidents';
import type { Incident, IncidentSummary } from '../../api/types';

vi.mock('../../api/incidents', () => ({
  incidentsApi: {
    get: vi.fn(),
  },
}));

const mockIncidentDetail: Incident = {
  incident_id: 'a1b2c3d4-e5f6-4a1b-8c2d-123456789abc',
  resource_id: 'VM-001',
  failure_type: 'HIGH_CPU',
  severity: 'HIGH',
  status: 'RESOLVED',
  state_at_detection: 'FAILURE_DETECTED',
  state_at_resolution: 'RECOVERED',
  created_at: '2026-09-09T10:00:00Z',
  detected_at: '2026-09-09T10:00:00Z',
  recovery_started_at: '2026-09-09T10:00:02Z',
  recovery_initiated_at: '2026-09-09T10:00:02Z',
  recovered_at: '2026-09-09T10:00:08Z',
  resolved_at: '2026-09-09T10:00:08Z',
  duration_seconds: 6.0,
  recovery_action: 'SCALE_OUT',
  recovery_result: 'SUCCEEDED',
  notification_status: 'DELIVERED (SNS)',
  notification_sent: true,
  notified_transitions: ['FAILURE_DETECTED', 'RECOVERY_STARTED', 'RECOVERY_SUCCEEDED'],
  retry_count: 1,
  recovery_attempts: 1,
  error_message: null,
  recovery_actions: [
    {
      action_id: '11111111-1111-4111-8111-111111111111',
      action_type: 'SCALE_OUT',
      status: 'SUCCEEDED',
      started_at: '2026-09-09T10:00:02Z',
      completed_at: '2026-09-09T10:00:08Z',
      outcome_message: 'Simulated scale out succeeded. CPU reset to 25.0%.',
    },
  ],
  recovery_notes: ['Autonomous remediation successful.'],
};

const mockSummaryList: IncidentSummary[] = [
  {
    incident_id: 'a1b2c3d4-e5f6-4a1b-8c2d-123456789abc',
    resource_id: 'VM-001',
    failure_type: 'HIGH_CPU',
    severity: 'HIGH',
    status: 'RESOLVED',
    detected_at: '2026-09-09T10:00:00Z',
    resolved_at: '2026-09-09T10:00:08Z',
  },
];

describe('IncidentDetailSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches and displays all 14 lifecycle fields and stepper', async () => {
    vi.mocked(incidentsApi.get).mockResolvedValue(mockIncidentDetail);

    render(
      <IncidentDetailSection
        selectedIncidentId="a1b2c3d4-e5f6-4a1b-8c2d-123456789abc"
        allIncidents={mockSummaryList}
        onSelectIncident={vi.fn()}
        onNavigateTab={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Incident Details')).toBeInTheDocument();
      expect(screen.getByText('14 Incident Lifecycle Fields')).toBeInTheDocument();
      expect(screen.getByText('1. Incident ID')).toBeInTheDocument();
      expect(screen.getByText('2. Resource ID')).toBeInTheDocument();
      expect(screen.getByText('VM-001')).toBeInTheDocument();
      expect(screen.getByText('10. Recovery Action')).toBeInTheDocument();
      expect(screen.getByText('11. Recovery Result')).toBeInTheDocument();
      expect(screen.getByText('12. Notification Status')).toBeInTheDocument();
      expect(screen.getByText('DELIVERED (SNS)')).toBeInTheDocument();
      expect(screen.getByText('13. Retry Count')).toBeInTheDocument();
      expect(screen.getByText('14. Error Message')).toBeInTheDocument();
      expect(screen.getByText('Executed Recovery Actions')).toBeInTheDocument();
      expect(
        screen.getByText('Simulated scale out succeeded. CPU reset to 25.0%.')
      ).toBeInTheDocument();
    });
  });

  it('renders empty state when no incident is selected or available', () => {
    render(
      <IncidentDetailSection
        selectedIncidentId={undefined}
        allIncidents={[]}
        onSelectIncident={vi.fn()}
        onNavigateTab={vi.fn()}
      />
    );

    expect(screen.getByText('No Incident Selected')).toBeInTheDocument();
  });
});
