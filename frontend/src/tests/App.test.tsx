import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';

vi.mock('../pages/Dashboard', () => ({
  default: () => <div data-testid="mock-dashboard">Dashboard Loaded</div>,
}));

describe('App Component', () => {
  it('renders Dashboard without crashing', () => {
    render(<App />);
    expect(screen.getByTestId('mock-dashboard')).toBeInTheDocument();
  });
});
