import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import SkillDetail from './SkillDetail';
import { mockSkillDetail } from '../test/mocks';

describe('SkillDetail', () => {
  it('should render skill name', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText(mockSkillDetail.name)).toBeInTheDocument();
  });

  it('should render skill icon', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText(mockSkillDetail.icon)).toBeInTheDocument();
  });

  it('should render skill description', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText(mockSkillDetail.description)).toBeInTheDocument();
  });

  it('should render category badge', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    // Category appears in hero header and sidebar
    const badges = screen.getAllByText(mockSkillDetail.category);
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  it('should render file count', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText(`${mockSkillDetail.fileCount} files`)).toBeInTheDocument();
  });

  it('should render license', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    // License appears in hero header badge and sidebar
    const licenses = screen.getAllByText(mockSkillDetail.license);
    expect(licenses.length).toBeGreaterThanOrEqual(1);
  });

  it('should render last updated date', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    const dateStr = new Date(mockSkillDetail.lastUpdated).toLocaleDateString();
    expect(screen.getByText(dateStr)).toBeInTheDocument();
  });

  it('should render Install section heading', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText('Install')).toBeInTheDocument();
  });

  it('should render InstallCommands component with tabs', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    // "Claude Code" appears in install tabs and sidebar install paths
    expect(screen.getAllByText('Claude Code').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Opencode/i).length).toBeGreaterThanOrEqual(1);
  });

  it('should render Download ZIP button', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText('Download ZIP')).toBeInTheDocument();
  });

  it('should open ZIP URL when Download ZIP clicked', async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {});
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);

    await user.click(screen.getByText('Download ZIP'));
    expect(openSpy).toHaveBeenCalledWith(
      `/api/skills/${mockSkillDetail.name}/zip`,
      '_blank'
    );
    openSpy.mockRestore();
  });

  it('should render Documentation section', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText('Documentation')).toBeInTheDocument();
  });

  it('should render markdown content', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    // react-markdown renders the heading from content
    expect(screen.getByText('Frontend Design')).toBeInTheDocument();
    expect(screen.getByText('Usage')).toBeInTheDocument();
  });

  it('should render sidebar details section', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText('Details')).toBeInTheDocument();
  });

  it('should render install paths in sidebar', () => {
    renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
    expect(screen.getByText('Install Paths')).toBeInTheDocument();
    expect(screen.getByText(mockSkillDetail.installPaths.claudeCode)).toBeInTheDocument();
    expect(screen.getByText(mockSkillDetail.installPaths.opencode)).toBeInTheDocument();
  });
});
