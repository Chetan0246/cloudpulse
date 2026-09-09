import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReliabilityMetricsSection } from '../../components/sections/ReliabilityMetricsSection';
import type { ReliabilityMetric } from '../../api/types';

const mockMetrics: ReliabilityMetric[] = [
  {
    resource_id: 'VM-001',
    window_key: 'DAILY#2026-09-09',
    window_type: 'DAILY',
    window_start: '2026-09-09T00:00:00Z',
    window_end: '2026-09-09T23:59:59Z',
    total_incidents: 2,
    resolved_incidents: 2,
    failed_recoveries: 0,
    mttr_seconds: 5.5,
    mtbf_seconds: 43200,
    availability_pct: 99.98,
    failure_type_counts: { HIGH_CPU: 2 },
  },
];

describe('ReliabilityMetricsSection', () => {
  it('renders reliability metrics and handles window change', () => {
    const handleChangeWindow = vi.fn();
    render(
      <ReliabilityMetricsSection
        metrics={mockMetrics}
        selectedWindow="DAILY"
        onChangeWindow={handleChangeWindow}
      />
    );

    expect(screen.getByText('Reliability & Service Level Engineering')).toBeInTheDocument();
    expect(screen.getByText('Availability (SLO)')).toBeInTheDocument();
    expect(screen.getByText('99.980%')).toBeInTheDocument();
    expect(screen.getByText('Mean Time To Recovery (MTTR)')).toBeInTheDocument();
    expect(screen.getAllByText('5.5s').length).toBeGreaterThan(0);
    expect(screen.getByText('Resource Reliability Breakdown')).toBeInTheDocument();
    expect(screen.getByText('Failure Distribution')).toBeInTheDocument();

    // Switch window to WEEKLY
    fireEvent.click(screen.getByText('WEEKLY'));
    expect(handleChangeWindow).toHaveBeenCalledWith('WEEKLY');
  });
});
