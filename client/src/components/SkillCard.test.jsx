import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import SkillCard from './SkillCard';
import { mockSkills } from '../test/mocks';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

describe('SkillCard', () => {
  const skill = mockSkills[0]; // frontend-design

  it('should render skill name', () => {
    renderWithProviders(<SkillCard skill={skill} />);
    expect(screen.getByText(skill.name)).toBeInTheDocument();
  });

  it('should render skill icon', () => {
    renderWithProviders(<SkillCard skill={skill} />);
    expect(screen.getByText(skill.icon)).toBeInTheDocument();
  });

  it('should render skill description', () => {
    renderWithProviders(<SkillCard skill={skill} />);
    expect(screen.getByText(skill.description)).toBeInTheDocument();
  });

  it('should render category badge', () => {
    renderWithProviders(<SkillCard skill={skill} />);
    expect(screen.getByText(skill.category)).toBeInTheDocument();
  });

  it('should render file count', () => {
    renderWithProviders(<SkillCard skill={skill} />);
    expect(screen.getByText(`${skill.fileCount} files`)).toBeInTheDocument();
  });

  it('should render relative time for lastUpdated', () => {
    renderWithProviders(<SkillCard skill={skill} />);
    const timeText = screen.getByText(/Updated/);
    expect(timeText).toBeInTheDocument();
    expect(timeText.textContent).toMatch(/Updated \d+[mhd]|mo ago/);
  });

  it('should navigate to skill detail on click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SkillCard skill={skill} />);
    const card = screen.getByText(skill.name).closest('[class*="cursor-pointer"]');
    await user.click(card);
    expect(mockNavigate).toHaveBeenCalledWith(`/skill/${skill.name}`);
  });

  it('should render different badge colors for different categories', () => {
    const { unmount } = renderWithProviders(<SkillCard skill={mockSkills[0]} />);
    const devBadge = screen.getByText('Development');
    const devBg = devBadge.style.backgroundColor;
    unmount();

    renderWithProviders(<SkillCard skill={mockSkills[1]} />);
    const toolsBadge = screen.getByText('Tools');
    const toolsBg = toolsBadge.style.backgroundColor;

    // CSS variables differ per category
    expect(devBg).not.toBe(toolsBg);
  });
});
