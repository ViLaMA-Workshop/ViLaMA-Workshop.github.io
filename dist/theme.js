/* Load before the stylesheet so the first frame uses the visitor's appearance. */
(() => {
  'use strict';
  const storageKey = 'vilama-theme';
  const root = document.documentElement;
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const validMode = value => ['light', 'dark', 'auto'].includes(value) ? value : 'auto';
  let mode = 'auto';
  let buttons = [];
  try { mode = validMode(window.localStorage.getItem(storageKey)); } catch (_) { /* Private browsing can block storage. */ }

  function apply() {
    const theme = mode === 'auto' ? (system.matches ? 'dark' : 'light') : mode;
    root.dataset.themeMode = mode;
    root.dataset.theme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#142823' : '#f6f5ef');
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.themeChoice === mode)));
  }
  apply();

  // A device appearance change only changes the page while Auto is selected.
  system.addEventListener('change', () => { if (mode === 'auto') apply(); });
  window.addEventListener('storage', event => {
    if (event.key !== storageKey && event.key !== null) return;
    mode = validMode(event.newValue);
    apply();
  });
  document.addEventListener('DOMContentLoaded', () => {
    buttons = Array.from(document.querySelectorAll('[data-theme-choice]'));
    buttons.forEach(button => button.addEventListener('click', () => {
      mode = validMode(button.dataset.themeChoice);
      try { window.localStorage.setItem(storageKey, mode); } catch (_) { /* The selection still works for this visit. */ }
      apply();
    }));
    apply();
    const controls = document.querySelector('[data-theme-controls]');
    if (controls) controls.hidden = false;
  });
})();
