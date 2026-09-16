// Apply the saved theme before React mounts; keep this local for desktop CSP.
try {
  const saved = localStorage.getItem('cbos_theme');
  const theme = saved === 'light' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.style.colorScheme = theme;
} catch {
  document.documentElement.setAttribute('data-theme', 'dark');
}
