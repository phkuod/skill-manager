import { describe, it, expect, beforeEach } from 'vitest';
import { screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@testing-library/react';
import { ThemeProvider, useTheme } from './ThemeContext';

function TestConsumer() {
  const { dark, toggle } = useTheme();
  return (
    <div>
      <span data-testid="theme">{dark ? 'dark' : 'light'}</span>
      <button onClick={toggle}>Toggle</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove('dark');
});

describe('ThemeContext', () => {
  it('should provide dark state', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );
    const theme = screen.getByTestId('theme');
    expect(['dark', 'light']).toContain(theme.textContent);
  });

  it('should toggle between dark and light', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );

    const theme = screen.getByTestId('theme');
    const initial = theme.textContent;
    await user.click(screen.getByText('Toggle'));
    expect(theme.textContent).not.toBe(initial);
  });

  it('should add dark class to html when dark', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );

    // Start from light
    if (document.documentElement.classList.contains('dark')) {
      await user.click(screen.getByText('Toggle'));
    }
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    await user.click(screen.getByText('Toggle'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('should remove dark class when light', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );

    // Ensure dark first
    if (!document.documentElement.classList.contains('dark')) {
      await user.click(screen.getByText('Toggle'));
    }
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    await user.click(screen.getByText('Toggle'));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('should persist to localStorage', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );

    await user.click(screen.getByText('Toggle'));
    const stored = localStorage.getItem('theme');
    expect(['dark', 'light']).toContain(stored);
  });

  it('should read initial value from localStorage', () => {
    localStorage.setItem('theme', 'dark');
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('dark');
  });

  it('should read light from localStorage', () => {
    localStorage.setItem('theme', 'light');
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('light');
  });
});
