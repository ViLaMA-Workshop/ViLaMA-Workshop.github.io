/* Progressive enhancements only. All workshop content lives in the HTML. */
(() => {
  'use strict';
  document.documentElement.classList.add('js');
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#navigation');
  function closeMenu() {
    toggle.setAttribute('aria-expanded', 'false');
    nav.classList.remove('is-open');
    toggle.querySelector('span').textContent = 'Menu';
  }
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    nav.classList.toggle('is-open', open);
    toggle.querySelector('span').textContent = open ? 'Close' : 'Menu';
  });
  nav.addEventListener('click', event => {
    if (event.target.closest('a')) closeMenu();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
      closeMenu();
      toggle.focus();
    }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.nav-shell')) closeMenu();
  });
  const desktop = window.matchMedia('(min-width: 761px)');
  desktop.addEventListener('change', closeMenu);

  // Mark the section in view without changing the visitor's URL or history.
  if ('IntersectionObserver' in window) {
    const links = Array.from(nav.querySelectorAll('a[href^="#"]'));
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        links.forEach(link => {
          if (link.getAttribute('href') === '#' + entry.target.id) {
            link.setAttribute('aria-current', 'location');
          } else {
            link.removeAttribute('aria-current');
          }
        });
      });
    }, { rootMargin: '-15% 0px -65% 0px', threshold: 0 });
    document.querySelectorAll('main section[id]').forEach(section => observer.observe(section));
  }

  // Expand the remaining source proposal details when printing.
  let printDetails = [];
  window.addEventListener('beforeprint', () => {
    printDetails = Array.from(document.querySelectorAll('details')).map(node => [node, node.open]);
    printDetails.forEach(([node]) => { node.open = true; });
  });
  window.addEventListener('afterprint', () => {
    printDetails.forEach(([node, wasOpen]) => { node.open = wasOpen; });
  });
})();
