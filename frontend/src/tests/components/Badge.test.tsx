import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  StateBadge,
  HealthBadge,
  StatusBadge,
  SeverityBadge,
  FailureTypeBadge,
} from '../../components/common/Badge';

describe('Badge Components', () => {
  it('renders StateBadge with state text', () => {
    render(<StateBadge state="HEALTHY" />);
    expect(screen.getByText('HEALTHY')).toBeInTheDocument();
  });

  it('renders HealthBadge with health text', () => {
    render(<HealthBadge health="DEGRADED" />);
    expect(screen.getByText('DEGRADED')).toBeInTheDocument();
  });

  it('renders StatusBadge with status text', () => {
    render(<StatusBadge status="RECOVERING" />);
    expect(screen.getByText('RECOVERING')).toBeInTheDocument();
  });

  it('renders SeverityBadge with severity text', () => {
    render(<SeverityBadge severity="CRITICAL" />);
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
  });

  it('renders FailureTypeBadge with failure type text', () => {
    render(<FailureTypeBadge failureType="HIGH_CPU" />);
    expect(screen.getByText('HIGH_CPU')).toBeInTheDocument();
  });
});
