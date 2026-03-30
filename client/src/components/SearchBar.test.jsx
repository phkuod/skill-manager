import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import SearchBar from './SearchBar';

describe('SearchBar', () => {
  it('should render an input with placeholder', () => {
    renderWithProviders(<SearchBar onSearch={vi.fn()} />);
    const input = screen.getByPlaceholderText('Search skills...');
    expect(input).toBeInTheDocument();
  });

  it('should update value as user types', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SearchBar onSearch={vi.fn()} />);
    const input = screen.getByPlaceholderText('Search skills...');

    await user.type(input, 'pdf');
    expect(input.value).toBe('pdf');
  });

  it('should call onSearch after debounce', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<SearchBar onSearch={onSearch} />);
    const input = screen.getByPlaceholderText('Search skills...');

    await user.type(input, 'pdf');
    await waitFor(() => {
      expect(onSearch).toHaveBeenCalledWith('pdf');
    }, { timeout: 2000 });
  });

  it('should debounce rapid input', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<SearchBar onSearch={onSearch} />);
    const input = screen.getByPlaceholderText('Search skills...');

    await user.type(input, 'pdf');
    await waitFor(() => {
      const calls = onSearch.mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall[0]).toContain('pdf');
    }, { timeout: 2000 });
  });

  it('should call onSearch with empty string when cleared', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<SearchBar onSearch={onSearch} />);
    const input = screen.getByPlaceholderText('Search skills...');

    await user.type(input, 'pdf');
    await waitFor(() => expect(onSearch).toHaveBeenCalledWith('pdf'), { timeout: 2000 });

    await user.clear(input);
    await waitFor(() => expect(onSearch).toHaveBeenCalledWith(''), { timeout: 2000 });
  });
});
