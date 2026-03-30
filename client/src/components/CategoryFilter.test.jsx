import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import CategoryFilter from './CategoryFilter';
import { mockCategories } from '../test/mocks';

describe('CategoryFilter', () => {
  it('should render all category buttons', () => {
    renderWithProviders(
      <CategoryFilter categories={mockCategories} selected="All" onSelect={vi.fn()} />
    );
    mockCategories.forEach((cat) => {
      expect(screen.getByText(cat)).toBeInTheDocument();
    });
  });

  it('should call onSelect when a category is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderWithProviders(
      <CategoryFilter categories={mockCategories} selected="All" onSelect={onSelect} />
    );

    await user.click(screen.getByText('Tools'));
    expect(onSelect).toHaveBeenCalledWith('Tools');
  });

  it('should call onSelect with "All" when All is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderWithProviders(
      <CategoryFilter categories={mockCategories} selected="Tools" onSelect={onSelect} />
    );

    await user.click(screen.getByText('All'));
    expect(onSelect).toHaveBeenCalledWith('All');
  });

  it('should visually distinguish the selected category', () => {
    renderWithProviders(
      <CategoryFilter categories={mockCategories} selected="Tools" onSelect={vi.fn()} />
    );
    const toolsButton = screen.getByText('Tools');
    const allButton = screen.getByText('All');
    // Selected button has accent background color
    expect(toolsButton.style.backgroundColor).not.toBe(allButton.style.backgroundColor);
  });

  it('should render with empty categories', () => {
    renderWithProviders(
      <CategoryFilter categories={[]} selected="All" onSelect={vi.fn()} />
    );
    // Should render without errors
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
