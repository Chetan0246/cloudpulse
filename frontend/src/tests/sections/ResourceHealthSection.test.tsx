import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ResourceHealthSection } from '../../components/sections/ResourceHealthSection';
import type { ResourceSummary } from '../../api/types';

const mockResources: ResourceSummary[] = [
  {
    resource_id: 'VM-001',
    resource_type: 'VM',
    current_state: 'HEALTHY',
    health_status: 'HEALTHY',
    active_failure_type: null,
    last_heartbeat: '2026-09-09T10:00:00Z',
    cpu_utilization: 35.0,
    memory_utilization: 45.0,
    storage_utilization: 22.0,
    network_latency_ms: 15.0,
  },
  {
    resource_id: 'DB-001',
    resource_type: 'DB',
    current_state: 'WARNING',
    health_status: 'DEGRADED',
    active_failure_type: null,
    last_heartbeat: '2026-09-09T10:00:00Z',
    cpu_utilization: 82.0,
    memory_utilization: 78.0,
    storage_utilization: 88.0,
    network_latency_ms: 85.0,
  },
];

describe('ResourceHealthSection', () => {
  it('renders resource cards with metrics and gauges', () => {
    const handleReset = vi.fn().mockResolvedValue(undefined);
    const handleSimulate = vi.fn();

    render(
      <ResourceHealthSection
        resources={mockResources}
        onResetResource={handleReset}
        onSimulateForResource={handleSimulate}
      />
    );

    expect(screen.getByText('VM-001')).toBeInTheDocument();
    expect(screen.getByText('DB-001')).toBeInTheDocument();
    expect(screen.getAllByText('CPU Utilization').length).toBe(2);
  });

  it('handles reset action button', async () => {
    const handleReset = vi.fn().mockResolvedValue(undefined);
    const handleSimulate = vi.fn();

    render(
      <ResourceHealthSection
        resources={mockResources}
        onResetResource={handleReset}
        onSimulateForResource={handleSimulate}
      />
    );

    const resetButtons = screen.getAllByText('Reset to Healthy');
    fireEvent.click(resetButtons[0]);

    await waitFor(() => {
      expect(handleReset).toHaveBeenCalledWith('VM-001');
    });
  });

  it('switches to table view and filters by type', () => {
    render(
      <ResourceHealthSection
        resources={mockResources}
        onResetResource={vi.fn().mockResolvedValue(undefined)}
        onSimulateForResource={vi.fn()}
      />
    );

    // Switch to table view
    const tableBtn = screen.getByTitle('Table View');
    fireEvent.click(tableBtn);
    expect(screen.getByText('Infrastructure Telemetry Grid')).toBeInTheDocument();

    // Filter by DB
    const dbFilterBtn = screen.getByRole('button', { name: 'DB' });
    fireEvent.click(dbFilterBtn);
    expect(screen.queryByText('VM-001')).not.toBeInTheDocument();
    expect(screen.getByText('DB-001')).toBeInTheDocument();
  });
});
