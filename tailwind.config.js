/**
 * Config for regenerating the vendored Tailwind bundle. There is NO permanent
 * build step — run the standalone CLI once whenever templates/JS start using
 * a utility class that is not yet in the bundle. Procedure: CLAUDE.md
 * ("Tailwind regen").
 */
module.exports = {
  content: [
    './skills/templates/**/*.html',
    './skills/static/skills/js/*.js',
    './skills/static/skills/dev/*.js',
  ],
  darkMode: 'class',
};
