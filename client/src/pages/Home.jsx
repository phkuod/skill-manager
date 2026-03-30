import { useState, useCallback, useMemo } from 'react';
import { useSkills } from '../hooks/useSkills';
import ThemeToggle from '../components/ThemeToggle';
import SearchBar from '../components/SearchBar';
import CategoryFilter from '../components/CategoryFilter';
import SkillCard from '../components/SkillCard';

const SORT_OPTIONS = [
  { value: 'updated', label: 'Last Updated' },
  { value: 'name', label: 'Name' },
];

export default function Home() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [sort, setSort] = useState('updated');
  const { skills, categories, loading, error } = useSkills(search, category);

  const handleSearch = useCallback((val) => setSearch(val), []);

  const sortedSkills = useMemo(() => {
    const list = [...skills];
    if (sort === 'updated') {
      list.sort((a, b) => new Date(b.lastUpdated) - new Date(a.lastUpdated));
    } else if (sort === 'name') {
      list.sort((a, b) => a.name.localeCompare(b.name));
    }
    return list;
  }, [skills, sort]);

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
      <section
        className="relative overflow-hidden"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        {/* Decorative gradient background */}
        <div
          className="absolute inset-0 opacity-50"
          style={{
            background: 'linear-gradient(135deg, var(--accent) 0%, transparent 50%)',
            opacity: 0.06,
          }}
        />
        <div className="relative max-w-6xl mx-auto px-4 py-10 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-4"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
            }}
          >
            <span
              className="w-2 h-2 rounded-full inline-block"
              style={{ backgroundColor: '#22c55e' }}
            />
            Internal Network
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            Internal Skill Market
          </h1>
          <p className="text-sm sm:text-base max-w-lg mx-auto" style={{ color: 'var(--text-secondary)' }}>
            Browse and install {skills.length} skills for Claude Code & Opencode
          </p>

          {/* Stats Row */}
          <div className="flex items-center justify-center gap-6 mt-6">
            <div className="text-center">
              <div className="text-xl font-bold" style={{ color: 'var(--accent)' }}>{skills.length}</div>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>Skills</div>
            </div>
            <div className="w-px h-8" style={{ backgroundColor: 'var(--border)' }} />
            <div className="text-center">
              <div className="text-xl font-bold" style={{ color: 'var(--accent)' }}>{categories.length > 0 ? categories.length - 1 : 0}</div>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>Categories</div>
            </div>
            <div className="w-px h-8" style={{ backgroundColor: 'var(--border)' }} />
            <div className="text-center">
              <div className="text-xl font-bold" style={{ color: 'var(--accent)' }}>2</div>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>Platforms</div>
            </div>
          </div>
        </div>
      </section>

      {/* Category Filter + Sort */}
      <section className="px-4 pt-6 pb-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <CategoryFilter categories={categories} selected={category} onSelect={setCategory} />
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
              Sort
            </span>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="text-xs rounded-md px-2 py-1 outline-none cursor-pointer"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border)',
              }}
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
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
        {!loading && !error && sortedSkills.length === 0 && (
          <p className="text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
            No skills found.
          </p>
        )}
        {!loading && !error && sortedSkills.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {sortedSkills.map((skill) => (
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
