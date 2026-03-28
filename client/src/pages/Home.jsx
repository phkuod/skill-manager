import { useState, useCallback } from 'react';
import { useSkills } from '../hooks/useSkills';
import ThemeToggle from '../components/ThemeToggle';
import SearchBar from '../components/SearchBar';
import CategoryFilter from '../components/CategoryFilter';
import SkillCard from '../components/SkillCard';

export default function Home() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const { skills, categories, loading, error } = useSkills(search, category);

  const handleSearch = useCallback((val) => setSearch(val), []);

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Header */}
      <header
        className="sticky top-0 z-10 backdrop-blur"
        style={{ borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg-primary)', opacity: 0.97 }}
      >
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              SM
            </div>
            <span className="font-semibold text-sm hidden sm:inline" style={{ color: 'var(--text-primary)' }}>
              Skill Market
            </span>
          </div>
          <SearchBar onSearch={handleSearch} />
          <ThemeToggle />
        </div>
      </header>

      {/* Hero */}
      <section className="text-center py-8 px-4">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Internal Skill Market
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Browse and install {skills.length} skills for Claude Code & Opencode
        </p>
      </section>

      {/* Category Filter */}
      <section className="px-4 pb-6">
        <CategoryFilter categories={categories} selected={category} onSelect={setCategory} />
      </section>

      {/* Skill Cards Grid */}
      <section className="max-w-6xl mx-auto px-4 pb-12">
        {loading && (
          <p className="text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
            Loading skills...
          </p>
        )}
        {error && (
          <p className="text-center text-sm text-red-500">
            Error: {error}
          </p>
        )}
        {!loading && !error && skills.length === 0 && (
          <p className="text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
            No skills found.
          </p>
        )}
        {!loading && !error && skills.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {skills.map((skill) => (
              <SkillCard key={skill.name} skill={skill} />
            ))}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer
        className="text-center py-6 text-xs"
        style={{ color: 'var(--text-secondary)', borderTop: '1px solid var(--border)' }}
      >
        Internal Skill Market &middot; {skills.length} skills
      </footer>
    </div>
  );
}
