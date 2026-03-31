import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useSkills, useSkillDetail, useSkillFiles, useSkillVersion } from './useSkills';
import { mockSkills, mockCategories, mockSkillDetail, mockSkillFiles, setupFetchMock } from '../test/mocks';

beforeEach(() => {
  setupFetchMock();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useSkills', () => {
  it('should fetch and return skills', async () => {
    const { result } = renderHook(() => useSkills('', 'All'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.skills).toEqual(mockSkills);
    expect(result.current.categories).toEqual(mockCategories);
    expect(result.current.error).toBeNull();
  });

  it('should start in loading state', () => {
    const { result } = renderHook(() => useSkills('', 'All'));
    expect(result.current.loading).toBe(true);
  });

  it('should pass search param to fetch', async () => {
    const { result } = renderHook(() => useSkills('pdf', 'All'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('search=pdf'));
  });

  it('should pass category param to fetch', async () => {
    const { result } = renderHook(() => useSkills('', 'Tools'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('category=Tools'));
  });

  it('should not include category param when "All"', async () => {
    const { result } = renderHook(() => useSkills('', 'All'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledWith('/api/skills');
  });

  it('should handle fetch errors', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Network error')));
    const { result } = renderHook(() => useSkills('', 'All'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Network error');
    expect(result.current.skills).toEqual([]);
  });

  it('should handle non-ok response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500 })
    );
    const { result } = renderHook(() => useSkills('', 'All'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('HTTP 500');
  });

  it('should re-fetch when search changes', async () => {
    const { result, rerender } = renderHook(
      ({ search, category }) => useSkills(search, category),
      { initialProps: { search: '', category: 'All' } }
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    rerender({ search: 'pdf', category: 'All' });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('should re-fetch when category changes', async () => {
    const { result, rerender } = renderHook(
      ({ search, category }) => useSkills(search, category),
      { initialProps: { search: '', category: 'All' } }
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    rerender({ search: '', category: 'Tools' });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe('useSkillDetail', () => {
  it('should fetch and return skill detail', async () => {
    const { result } = renderHook(() => useSkillDetail('frontend-design'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.skill).toEqual(mockSkillDetail);
    expect(result.current.error).toBeNull();
  });

  it('should start in loading state', () => {
    const { result } = renderHook(() => useSkillDetail('frontend-design'));
    expect(result.current.loading).toBe(true);
  });

  it('should not fetch when name is empty', () => {
    renderHook(() => useSkillDetail(''));
    expect(fetch).not.toHaveBeenCalled();
  });

  it('should not fetch when name is undefined', () => {
    renderHook(() => useSkillDetail(undefined));
    expect(fetch).not.toHaveBeenCalled();
  });

  it('should handle 404 error', async () => {
    const { result } = renderHook(() => useSkillDetail('nonexistent'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('HTTP 404');
    expect(result.current.skill).toBeNull();
  });

  it('should handle network errors', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Timeout')));
    const { result } = renderHook(() => useSkillDetail('frontend-design'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Timeout');
  });

  it('should re-fetch when name changes', async () => {
    const { result, rerender } = renderHook(
      ({ name }) => useSkillDetail(name),
      { initialProps: { name: 'frontend-design' } }
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    rerender({ name: 'pdf' });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe('useSkillFiles', () => {
  it('should fetch and return skill files', async () => {
    const { result } = renderHook(() => useSkillFiles('frontend-design'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.files).toEqual(mockSkillFiles);
    expect(result.current.error).toBeNull();
  });

  it('should start in loading state', () => {
    const { result } = renderHook(() => useSkillFiles('frontend-design'));
    expect(result.current.loading).toBe(true);
  });

  it('should not fetch when name is empty', () => {
    renderHook(() => useSkillFiles(''));
    expect(fetch).not.toHaveBeenCalled();
  });

  it('should not fetch when name is undefined', () => {
    renderHook(() => useSkillFiles(undefined));
    expect(fetch).not.toHaveBeenCalled();
  });

  it('should handle 404 error', async () => {
    const { result } = renderHook(() => useSkillFiles('nonexistent'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('HTTP 404');
    expect(result.current.files).toEqual([]);
  });

  it('should handle network errors', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Timeout')));
    const { result } = renderHook(() => useSkillFiles('frontend-design'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Timeout');
  });

  it('should re-fetch when name changes', async () => {
    const { result, rerender } = renderHook(
      ({ name }) => useSkillFiles(name),
      { initialProps: { name: 'frontend-design' } }
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    rerender({ name: 'pdf' });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe('useSkillFiles with version', () => {
  it('should fetch version-specific files when version provided', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([{ path: 'SKILL.md', content: 'test', language: 'markdown' }]),
    });

    const { result } = renderHook(() => useSkillFiles('test-skill', '20260401-v1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(global.fetch).toHaveBeenCalledWith('/api/skills/test-skill/versions/20260401-v1/files');
  });
});

describe('useSkillVersion', () => {
  it('should fetch specific version data', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        name: 'test-skill',
        description: 'Version 1',
        content: 'v1 content',
      }),
    });

    const { result } = renderHook(() => useSkillVersion('test-skill', '20260401-v1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.skill.description).toBe('Version 1');
    expect(global.fetch).toHaveBeenCalledWith('/api/skills/test-skill/versions/20260401-v1');
  });

  it('should not fetch when version is null', async () => {
    global.fetch = vi.fn();
    renderHook(() => useSkillVersion('test-skill', null));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
