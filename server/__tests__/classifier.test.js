import { describe, it, expect } from 'vitest';
import { classify, getCategories } from '../classifier.js';

describe('classifier', () => {
  describe('classify', () => {
    it('should classify known Development skills', () => {
      expect(classify('frontend-design')).toEqual({ category: 'Development', icon: '🎨' });
      expect(classify('web-artifacts-builder')).toEqual({ category: 'Development', icon: '🌐' });
      expect(classify('mcp-builder')).toEqual({ category: 'Development', icon: '🔧' });
      expect(classify('skill-creator')).toEqual({ category: 'Development', icon: '⚡' });
    });

    it('should classify known Content skills', () => {
      expect(classify('doc-coauthoring')).toEqual({ category: 'Content', icon: '📝' });
      expect(classify('internal-comms')).toEqual({ category: 'Content', icon: '📢' });
      expect(classify('brand-guidelines')).toEqual({ category: 'Content', icon: '🏷️' });
      expect(classify('slack-gif-creator')).toEqual({ category: 'Content', icon: '🎬' });
    });

    it('should classify known Tools skills', () => {
      expect(classify('pdf')).toEqual({ category: 'Tools', icon: '📄' });
      expect(classify('docx')).toEqual({ category: 'Tools', icon: '📃' });
      expect(classify('pptx')).toEqual({ category: 'Tools', icon: '📊' });
      expect(classify('xlsx')).toEqual({ category: 'Tools', icon: '📈' });
      expect(classify('canvas-design')).toEqual({ category: 'Tools', icon: '🖼️' });
      expect(classify('theme-factory')).toEqual({ category: 'Tools', icon: '🎭' });
    });

    it('should classify known Data & AI skills', () => {
      expect(classify('claude-api')).toEqual({ category: 'Data & AI', icon: '🤖' });
      expect(classify('algorithmic-art')).toEqual({ category: 'Data & AI', icon: '🎆' });
    });

    it('should classify known Testing skills', () => {
      expect(classify('webapp-testing')).toEqual({ category: 'Testing', icon: '🧪' });
    });

    it('should return default for unknown skills', () => {
      expect(classify('unknown-skill')).toEqual({ category: 'Other', icon: '📦' });
    });

    it('should return default for empty string', () => {
      expect(classify('')).toEqual({ category: 'Other', icon: '📦' });
    });
  });

  describe('getCategories', () => {
    it('should return all categories with "All" first', () => {
      const categories = getCategories();
      expect(categories[0]).toBe('All');
    });

    it('should include all defined categories', () => {
      const categories = getCategories();
      expect(categories).toContain('Development');
      expect(categories).toContain('Content');
      expect(categories).toContain('Tools');
      expect(categories).toContain('Data & AI');
      expect(categories).toContain('Testing');
    });

    it('should not include "Other" (only mapped categories)', () => {
      const categories = getCategories();
      expect(categories).not.toContain('Other');
    });

    it('should return categories sorted alphabetically after "All"', () => {
      const categories = getCategories();
      const withoutAll = categories.slice(1);
      const sorted = [...withoutAll].sort();
      expect(withoutAll).toEqual(sorted);
    });

    it('should have no duplicates', () => {
      const categories = getCategories();
      const unique = [...new Set(categories)];
      expect(categories).toEqual(unique);
    });
  });
});
