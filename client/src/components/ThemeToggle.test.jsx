import { describe, it, expect, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import ThemeToggle from './ThemeToggle';

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove('dark');
});

describe('ThemeToggle', () => {
  it('should render the toggle button', () => {
    renderWithProviders(<ThemeToggle />);
    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
  });

  it('should have a title attribute', () => {
    renderWithProviders(<ThemeToggle />);
    const button = screen.getByRole('button');
    expect(button.title).toMatch(/switch to (dark|light) mode/i);
  });

  it('should toggle dark class on html element when clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ThemeToggle />);
    const button = screen.getByRole('button');

    const wasDark = document.documentElement.classList.contains('dark');
    await user.click(button);
    const isDark = document.documentElement.classList.contains('dark');
    expect(isDark).toBe(!wasDark);
  });

  it('should toggle back on double click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ThemeToggle />);
    const button = screen.getByRole('button');

    const initialDark = document.documentElement.classList.contains('dark');
    await user.click(button);
    await user.click(button);
    expect(document.documentElement.classList.contains('dark')).toBe(initialDark);
  });

  it('should persist theme to localStorage', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ThemeToggle />);
    const button = screen.getByRole('button');

    await user.click(button);
    const stored = localStorage.getItem('theme');
    expect(['dark', 'light']).toContain(stored);
  });
});
