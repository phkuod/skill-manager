import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useSkills, useSkillDetail } from './useSkills';
import { mockSkills, mockCategories, mockSkillDetail, setupFetchMock } from '../test/mocks';

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
