import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '../pages/Dashboard';
import { resourcesApi } from '../api/resources';
import { incidentsApi } from '../api/incidents';
import { metricsApi } from '../api/metrics';

vi.mock('../api/health', () => ({
  healthApi: {
    check: vi.fn().mockResolvedValue({ status: 'ok', service: 'cloudpulse-api' }),
    ready: vi.fn().mockResolvedValue({ status: 'ready', service: 'cloudpulse-api' }),
  },
}));

vi.mock('../api/resources', () => ({
  resourcesApi: {
    list: vi.fn(),
    get: vi.fn(),
  },
}));


vi.mock('../api/incidents', () => ({
  incidentsApi: {
    list: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock('../api/metrics', () => ({
  metricsApi: {
    list: vi.fn(),
    getLatest: vi.fn(),
    getOverview: vi.fn(),
  },
}));

describe('Dashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially and then displays telemetry control center', async () => {
    vi.mocked(resourcesApi.list).mockResolvedValue([
      {
        resource_id: 'VM-001',
        resource_type: 'VM',
        current_state: 'HEALTHY',
        health_status: 'HEALTHY',
        active_failure_type: null,
        last_heartbeat: '2026-09-09T10:00:00Z',
      },
    ]);
    vi.mocked(incidentsApi.list).mockResolvedValue([]);
    vi.mocked(metricsApi.list).mockResolvedValue([]);
    vi.mocked(metricsApi.getOverview).mockResolvedValue(null as any);

    render(<Dashboard />);

    expect(
      screen.getByText('Connecting to CloudPulse Backend Telemetry API...')
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('CloudPulse')).toBeInTheDocument();
      expect(screen.getByText('SYSTEM NOMINAL')).toBeInTheDocument();
      expect(screen.getByText('Healthy Resources')).toBeInTheDocument();
    });
  });
});
