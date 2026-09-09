import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FailureSimulatorSection } from '../../components/sections/FailureSimulatorSection';
import { simulateApi } from '../../api/simulate';
import type { ResourceSummary } from '../../api/types';

vi.mock('../../api/simulate', () => ({
  simulateApi: {
    inject: vi.fn(),
    reset: vi.fn(),
    recover: vi.fn(),
  },
}));

const mockResources: ResourceSummary[] = [
  {
    resource_id: 'VM-001',
    resource_type: 'VM',
    current_state: 'HEALTHY',
    health_status: 'HEALTHY',
    active_failure_type: null,
    last_heartbeat: '2026-09-09T10:00:00Z',
  },
  {
    resource_id: 'API-001',
    resource_type: 'API',
    current_state: 'HEALTHY',
    health_status: 'HEALTHY',
    active_failure_type: null,
    last_heartbeat: '2026-09-09T10:00:00Z',
  },
];

describe('FailureSimulatorSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders simulator controls, 5-stage lifecycle stepper, and blueprint', () => {
    render(
      <FailureSimulatorSection
        resources={mockResources}
        onInjectFailure={vi.fn().mockResolvedValue({ message: 'Success' })}
        onResetResource={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(
      screen.getByText('Chaos Engineering & Fault Injection Simulator')
    ).toBeInTheDocument();
    expect(screen.getByText('Simulated Reliability Lifecycle')).toBeInTheDocument();

    // 5 Lifecycle Stages displayed
    expect(screen.getByText('Healthy')).toBeInTheDocument();
    expect(screen.getByText('Failure')).toBeInTheDocument();
    expect(screen.getByText('Detection')).toBeInTheDocument();
    expect(screen.getByText('Recovery')).toBeInTheDocument();
    expect(screen.getByText('Recovered')).toBeInTheDocument();

    expect(screen.getByText('1. Select Target Virtual Resource')).toBeInTheDocument();
    expect(screen.getByText('2. Select Failure Scenario')).toBeInTheDocument();
    expect(screen.getByText('FS-01: High CPU Utilization')).toBeInTheDocument();
    expect(screen.getByText('Scenario Architecture Blueprint')).toBeInTheDocument();
  });

  it('progresses through complete 5-stage lifecycle: Healthy → Failure → Detection → Recovery → Recovered', async () => {
    vi.mocked(simulateApi.recover).mockResolvedValue({
      message: 'Resource VM-001 successfully recovered',
      scenario_id: 'FS-01',
      scenario_name: 'FS-01 High CPU Utilization',
      resource: { ...mockResources[0], current_state: 'HEALTHY' } as any,
      incident: { incident_id: 'recovered-inc-123' } as any,
      metrics_emitted: { CPUUtilization: 25.0 },
    });

    const handleInject = vi.fn().mockResolvedValue({
      message: "Simulated failure 'High CPU' successfully injected",
      incident: { incident_id: 'new-inc-123' },
      metrics_emitted: { CPUUtilization: 98.0 },
    });
    const handleReset = vi.fn().mockResolvedValue(undefined);

    render(
      <FailureSimulatorSection
        resources={mockResources}
        onInjectFailure={handleInject}
        onResetResource={handleReset}
      />
    );

    // Initial stage is Healthy
    expect(screen.getByText('STAGE: HEALTHY')).toBeInTheDocument();

    // Trigger failure
    const triggerBtn = screen.getByText('Trigger Failure Scenario');
    fireEvent.click(triggerBtn);

    // Transitions through Failure and Detection
    await waitFor(() => {
      expect(handleInject).toHaveBeenCalledWith('VM-001', 'HIGH_CPU', 'HIGH');
      expect(screen.getByText('STAGE: DETECTION')).toBeInTheDocument();
      expect(screen.getByText('new-inc-123')).toBeInTheDocument();
    });

    // Transitions through Recovery to Recovered (via auto-heal)
    await waitFor(
      () => {
        expect(screen.getByText('STAGE: RECOVERED')).toBeInTheDocument();
      },
      { timeout: 4000 }
    );
  });

  it('triggers reset target resource', async () => {
    const handleReset = vi.fn().mockResolvedValue(undefined);

    render(
      <FailureSimulatorSection
        resources={mockResources}
        onInjectFailure={vi.fn().mockResolvedValue({ message: 'Success' })}
        onResetResource={handleReset}
      />
    );

    const resetBtn = screen.getByText('Reset Target Resource');
    fireEvent.click(resetBtn);

    await waitFor(() => {
      expect(handleReset).toHaveBeenCalledWith('VM-001');
    });
  });
});
