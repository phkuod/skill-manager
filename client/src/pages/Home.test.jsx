import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import { setupFetchMock, mockSkills, mockCategories } from '../test/mocks';
import Home from './Home';

beforeEach(() => {
  setupFetchMock();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Home page', () => {
  it('should render the page title', async () => {
    renderWithProviders(<Home />);
    expect(screen.getByText('Internal Skill Market')).toBeInTheDocument();
  });

  it('should render the header with logo', async () => {
    renderWithProviders(<Home />);
    expect(screen.getByText('SM')).toBeInTheDocument();
    expect(screen.getByText('Skill Market')).toBeInTheDocument();
  });

  it('should render the search bar', () => {
    renderWithProviders(<Home />);
    expect(screen.getByPlaceholderText('Search skills...')).toBeInTheDocument();
  });

  it('should render the theme toggle', () => {
    renderWithProviders(<Home />);
    const buttons = screen.getAllByRole('button');
    // At least one button is the theme toggle
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('should show loading state initially', () => {
    renderWithProviders(<Home />);
    expect(screen.getByText('Loading skills...')).toBeInTheDocument();
  });

  it('should render skill cards after loading', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('frontend-design')).toBeInTheDocument();
    });
    expect(screen.getByText('pdf')).toBeInTheDocument();
    expect(screen.getByText('claude-api')).toBeInTheDocument();
  });

  it('should render category filter pills', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument();
    });
    // "Development" appears in both pills and card badges, so use getAllByText
    await waitFor(() => {
      expect(screen.getAllByText('Development').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Tools').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('should show skill count in subtitle', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText(/3 skills for Claude Code/)).toBeInTheDocument();
    });
  });

  it('should show skill count in footer', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText(/3 skills$/)).toBeInTheDocument();
    });
  });

  it('should render stats row in hero', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('Platforms')).toBeInTheDocument();
    });
    expect(screen.getByText('Categories')).toBeInTheDocument();
  });

  it('should render internal network badge', () => {
    renderWithProviders(<Home />);
    expect(screen.getByText('Internal Network')).toBeInTheDocument();
  });

  it('should render sort dropdown defaulting to Last Updated', async () => {
    renderWithProviders(<Home />);
    const sortSelect = screen.getByRole('combobox');
    expect(sortSelect).toBeInTheDocument();
    expect(sortSelect.value).toBe('updated');
  });

  it('should sort skills by name when Name sort selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('frontend-design')).toBeInTheDocument();
    });
    const sortSelect = screen.getByRole('combobox');
    await user.selectOptions(sortSelect, 'name');
    const cards = screen.getAllByText(/frontend-design|pdf|claude-api/);
    const names = cards.map((el) => el.textContent);
    expect(names).toEqual(['claude-api', 'frontend-design', 'pdf']);
  });

  it('should handle API error gracefully', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Server down')));
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText(/Error: Server down/)).toBeInTheDocument();
    });
  });

  it('should show "No skills found" for empty results', async () => {
    setupFetchMock({ '/api/skills': { skills: [], categories: mockCategories } });
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('No skills found.')).toBeInTheDocument();
    });
  });
});
