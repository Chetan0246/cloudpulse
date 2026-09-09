import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LinearGauge, LatencyGauge } from '../../components/common/Gauge';

describe('Gauge Components', () => {
  it('renders LinearGauge with label and percentage', () => {
    render(<LinearGauge label="CPU Utilization" value={45.6} />);
    expect(screen.getByText('CPU Utilization')).toBeInTheDocument();
    expect(screen.getByText('45.6%')).toBeInTheDocument();
  });

  it('clamps LinearGauge value between 0 and 100', () => {
    render(<LinearGauge label="Storage" value={120} />);
    expect(screen.getByText('100.0%')).toBeInTheDocument();
  });

  it('renders LatencyGauge with latency ms', () => {
    render(<LatencyGauge latencyMs={28.4} />);
    expect(screen.getByText('Latency')).toBeInTheDocument();
    expect(screen.getByText('28.4ms')).toBeInTheDocument();
  });
});
