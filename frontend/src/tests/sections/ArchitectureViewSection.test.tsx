import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ArchitectureViewSection } from '../../components/sections/ArchitectureViewSection';
import type { ResourceSummary, IncidentSummary } from '../../api/types';

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

const mockIncidents: IncidentSummary[] = [];

describe('ArchitectureViewSection', () => {
  it('renders architecture topology nodes and displays technical specs', () => {
    render(
      <ArchitectureViewSection
        resources={mockResources}
        incidents={mockIncidents}
      />
    );

    expect(
      screen.getByText('Closed-Loop Self-Healing Architecture Map')
    ).toBeInTheDocument();
    expect(screen.getByText('Virtual Infrastructure Fleet')).toBeInTheDocument();
    expect(screen.getByText('CloudWatch Custom Metrics')).toBeInTheDocument();
    expect(screen.getByText('CloudWatch Alarms')).toBeInTheDocument();
    expect(screen.getByText('Amazon EventBridge')).toBeInTheDocument();
    expect(screen.getAllByText('Self-Healing Recovery Lambda').length).toBeGreaterThan(0);
    expect(screen.getByText('DynamoDB & SNS Alerts')).toBeInTheDocument();

    // Click on CloudWatch Alarms node
    const alarmBtn = screen.getByText('🔔');
    fireEvent.click(alarmBtn);

    expect(screen.getByText('Detection Mechanism')).toBeInTheDocument();
    expect(screen.getByText('CPU Threshold')).toBeInTheDocument();
  });
});
