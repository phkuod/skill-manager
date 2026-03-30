import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/render';
import InstallCommands from './InstallCommands';
import { mockSkillDetail } from '../test/mocks';

beforeEach(() => {
  const clipboard = {
    writeText: vi.fn(() => Promise.resolve()),
  };
  Object.defineProperty(navigator, 'clipboard', {
    value: clipboard,
    writable: true,
    configurable: true,
  });
});

describe('InstallCommands', () => {
  it('should render Claude Code and Opencode CLI tabs', () => {
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);
    expect(screen.getByText('Claude Code')).toBeInTheDocument();
    expect(screen.getByText('Opencode CLI')).toBeInTheDocument();
  });

  it('should show Claude Code install command by default', () => {
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);
    const codeBlock = document.querySelector('code');
    expect(codeBlock.textContent).toContain('.claude/skills/');
    expect(codeBlock.textContent).toContain('cp -r');
  });

  it('should switch to Opencode command when tab clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);

    await user.click(screen.getByText('Opencode CLI'));
    const codeBlock = document.querySelector('code');
    expect(codeBlock.textContent).toContain('.opencode/skills/');
  });

  it('should switch back to Claude Code command', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);

    await user.click(screen.getByText('Opencode CLI'));
    await user.click(screen.getByText('Claude Code'));
    const codeBlock = document.querySelector('code');
    expect(codeBlock.textContent).toContain('.claude/skills/');
  });

  it('should render a Copy button', () => {
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);
    expect(screen.getByText('Copy')).toBeInTheDocument();
  });

  it('should copy correct command to clipboard when Copy clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);

    // Click Copy — if it succeeds, "Copied!" appears
    await user.click(screen.getByText('Copy'));
    expect(screen.getByText('Copied!')).toBeInTheDocument();

    // Verify the command text in the code block contains the expected content
    const codeBlock = document.querySelector('code');
    expect(codeBlock.textContent).toContain('cp -r');
    expect(codeBlock.textContent).toContain(mockSkillDetail.repoPath);
    expect(codeBlock.textContent).toContain('.claude/skills/');
  });

  it('should show "Copied!" after clicking Copy', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);

    await user.click(screen.getByText('Copy'));
    expect(screen.getByText('Copied!')).toBeInTheDocument();
  });

  it('should include install hint text', () => {
    renderWithProviders(<InstallCommands skill={mockSkillDetail} />);
    expect(screen.getByText(/Paste this command/)).toBeInTheDocument();
  });
});
