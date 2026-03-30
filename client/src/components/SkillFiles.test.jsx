import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/render';
import SkillFiles from './SkillFiles';
import { mockSkillFiles, setupFetchMock } from '../test/mocks';

beforeEach(() => {
  setupFetchMock();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SkillFiles', () => {
  it('shows loading state initially', () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    expect(screen.getByText('Loading files…')).toBeInTheDocument();
  });

  it('renders a block for each file after loading', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('SKILL.md')).toBeInTheDocument();
    expect(screen.getByText('LICENSE.txt')).toBeInTheDocument();
    expect(screen.getByText('templates/example.js')).toBeInTheDocument();
  });

  it('renders markdown files with ReactMarkdown', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    // ReactMarkdown renders the h1 from the SKILL.md content
    expect(screen.getByRole('heading', { name: 'Frontend Design' })).toBeInTheDocument();
  });

  it('renders non-markdown files as code blocks', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    // LICENSE.txt content rendered verbatim
    expect(screen.getByText(/MIT License/)).toBeInTheDocument();
  });

  it('shows language badge on non-markdown files', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('javascript')).toBeInTheDocument();
  });

  it('shows truncation notice for truncated files', async () => {
    setupFetchMock({
      '/api/skills/frontend-design/files': [
        { path: 'big-file.md', content: null, language: 'markdown', truncated: true },
      ],
    });
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('File too large to preview')).toBeInTheDocument();
  });

  it('shows error message on fetch failure', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Network error')));
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText(/Network error/)).toBeInTheDocument();
  });

  it('shows no-files notice when list is empty', async () => {
    setupFetchMock({ '/api/skills/frontend-design/files': [] });
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('No files found')).toBeInTheDocument();
  });
});
