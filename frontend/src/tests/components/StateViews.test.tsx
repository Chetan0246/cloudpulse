import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/StateViews';

describe('State View Components', () => {
  it('renders LoadingState with message and subtext', () => {
    render(<LoadingState message="Fetching data..." subtext="Connecting to AWS" />);
    expect(screen.getByText('Fetching data...')).toBeInTheDocument();
    expect(screen.getByText('Connecting to AWS')).toBeInTheDocument();
  });

  it('renders ErrorState and triggers retry', () => {
    const handleRetry = vi.fn();
    render(
      <ErrorState
        title="Network Error"
        message="Connection refused to DynamoDB"
        onRetry={handleRetry}
      />
    );
    expect(screen.getByText('Network Error')).toBeInTheDocument();
    expect(screen.getByText('Connection refused to DynamoDB')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Retry Connection'));
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it('renders EmptyState and triggers action', () => {
    const handleAction = vi.fn();
    render(
      <EmptyState
        title="No Records"
        description="Nothing here yet"
        actionText="Create Record"
        onAction={handleAction}
      />
    );
    expect(screen.getByText('No Records')).toBeInTheDocument();
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Create Record'));
    expect(handleAction).toHaveBeenCalledTimes(1);
  });
});
