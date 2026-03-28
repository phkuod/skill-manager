export default function CategoryFilter({ categories, selected, onSelect }) {
  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {categories.map((cat) => (
        <button
          key={cat}
          onClick={() => onSelect(cat)}
          className="px-3 py-1 rounded-full text-xs font-medium transition-colors"
          style={
            selected === cat
              ? { backgroundColor: 'var(--accent)', color: '#ffffff' }
              : {
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-secondary)',
                }
          }
        >
          {cat}
        </button>
      ))}
    </div>
  );
}
