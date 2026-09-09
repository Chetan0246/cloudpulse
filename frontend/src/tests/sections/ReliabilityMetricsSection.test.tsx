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

  it('renders all 8 SRE observability and reliability metrics when overview prop is provided', () => {
    const mockOverview = {
      incident_count: 8,
      recovery_success_rate_pct: 87.5,
      recovery_failure_rate_pct: 12.5,
      avg_recovery_time_seconds: 6.2,
      mttr_seconds: 9.4,
      avg_detection_time_seconds: 3.8,
      incident_frequency_per_hour: 2.0,
      incident_frequency_per_day: 48.0,
      mtbf_seconds: 1800,
      health_distribution: {
        total_resources: 4,
        healthy_count: 3,
        warning_count: 1,
        failed_count: 0,
        recovering_count: 0,
        healthy_pct: 75.0,
        by_state: { HEALTHY: 3, WARNING: 1 },
        by_status: { HEALTHY: 3, DEGRADED: 1 },
      },
      computed_at: '2026-09-09T12:00:00Z',
    };

    render(
      <ReliabilityMetricsSection
        metrics={mockMetrics}
        overview={mockOverview}
        selectedWindow="DAILY"
        onChangeWindow={vi.fn()}
      />
    );

    // 1. Incident count
    expect(screen.getByText('Incident Count')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();

    // 2. Recovery success rate
    expect(screen.getByText('Recovery Success Rate')).toBeInTheDocument();
    expect(screen.getByText('87.5%')).toBeInTheDocument();

    // 3. Recovery failure rate
    expect(screen.getByText('Recovery Failure Rate')).toBeInTheDocument();
    expect(screen.getByText('12.5%')).toBeInTheDocument();

    // 4. Average recovery time
    expect(screen.getByText('Average Recovery Time')).toBeInTheDocument();
    expect(screen.getByText('6.2s')).toBeInTheDocument();

    // 5. Mean Time to Recovery (MTTR)
    expect(screen.getByText('Mean Time To Recovery (MTTR)')).toBeInTheDocument();
    expect(screen.getByText('9.4s')).toBeInTheDocument();

    // 6. Average detection time
    expect(screen.getByText('Average Detection Time')).toBeInTheDocument();
    expect(screen.getByText('3.8s')).toBeInTheDocument();

    // 7. Incident frequency
    expect(screen.getByText('Incident Frequency')).toBeInTheDocument();
    expect(screen.getByText('2.00/hr')).toBeInTheDocument();

    // 8. Current resource health distribution
    expect(screen.getByText('Current Resource Health Distribution')).toBeInTheDocument();
    expect(screen.getByText('Fleet Health Index')).toBeInTheDocument();
    expect(screen.getByText('3 (75%)')).toBeInTheDocument();
  });
});

