import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import { setupFetchMock, mockSkillDetail } from '../test/mocks';
import SkillPage from './SkillPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ name: 'frontend-design' }),
    useNavigate: () => mockNavigate,
  };
});

beforeEach(() => {
  setupFetchMock();
  mockNavigate.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SkillPage', () => {
  it('should render "Back to skills" link', () => {
    renderWithProviders(<SkillPage />);
    expect(screen.getByText('Back to skills')).toBeInTheDocument();
  });

  it('should navigate back when back link is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SkillPage />);
    await user.click(screen.getByText('Back to skills'));
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('should render theme toggle', () => {
    renderWithProviders(<SkillPage />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('should show loading state initially', () => {
    renderWithProviders(<SkillPage />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('should render skill detail after loading', async () => {
    renderWithProviders(<SkillPage />);
    await waitFor(() => {
      expect(screen.getByText(mockSkillDetail.name)).toBeInTheDocument();
    });
    expect(screen.getByText(mockSkillDetail.description)).toBeInTheDocument();
  });

  it('should render install commands', async () => {
    renderWithProviders(<SkillPage />);
    await waitFor(() => {
      // "Claude Code" appears in install tabs and sidebar
      expect(screen.getAllByText('Claude Code').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getAllByText(/Opencode/i).length).toBeGreaterThanOrEqual(1);
  });

  it('should render Download ZIP button', async () => {
    renderWithProviders(<SkillPage />);
    await waitFor(() => {
      expect(screen.getByText('Download ZIP')).toBeInTheDocument();
    });
  });

  it('should render markdown documentation', async () => {
    renderWithProviders(<SkillPage />);
    await waitFor(() => {
      expect(screen.getByText('Documentation')).toBeInTheDocument();
    });
  });

  it('should handle fetch error', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Not found')));
    renderWithProviders(<SkillPage />);
    await waitFor(() => {
      expect(screen.getByText(/Error: Not found/)).toBeInTheDocument();
    });
  });
});
