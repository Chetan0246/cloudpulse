import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Panel, MetricCard, StatBox } from '../../components/common/Card';

describe('Card & Panel Components', () => {
  it('renders Panel with title, subtitle, and children', () => {
    render(
      <Panel title="System Fleet" subtitle="Telemetry stream">
        <div>Child Content</div>
      </Panel>
    );
    expect(screen.getByText('System Fleet')).toBeInTheDocument();
    expect(screen.getByText('Telemetry stream')).toBeInTheDocument();
    expect(screen.getByText('Child Content')).toBeInTheDocument();
  });

  it('renders MetricCard with title, value, subtext, and handles click', () => {
    const handleClick = vi.fn();
    render(
      <MetricCard
        title="Availability"
        value="99.98%"
        subtext="30-day window"
        icon="🛡️"
        onClick={handleClick}
      />
    );
    expect(screen.getByText('Availability')).toBeInTheDocument();
    expect(screen.getByText('99.98%')).toBeInTheDocument();
    expect(screen.getByText('30-day window')).toBeInTheDocument();
    expect(screen.getByText('🛡️')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Availability'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders StatBox with label and value', () => {
    render(<StatBox label="Memory" value="42%" highlight />);
    expect(screen.getByText('Memory')).toBeInTheDocument();
    expect(screen.getByText('42%')).toBeInTheDocument();
  });
});
