#!/usr/bin/env node
'use strict';

// Run with: node --test tools/test_theme.cjs
// These small browser mocks exercise the real synchronous head script without
// installing a DOM emulator or running a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const themePath = path.resolve(__dirname, '..', 'theme.js');
const THEME_KEY = 'vilama-theme';
const COLORS = { light: '#f6f5ef', dark: '#142823' };

class Events {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, callback) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(callback);
  }
  removeEventListener(type, callback) {
    this.listeners.set(type, (this.listeners.get(type) || []).filter(item => item !== callback));
  }
  dispatchEvent(event) {
    event.target ??= this;
    event.currentTarget = this;
    for (const callback of [...(this.listeners.get(event.type) || [])]) {
      if (typeof callback === 'function') callback.call(this, event);
      else callback.handleEvent(event);
    }
    return true;
  }
}

class Element extends Events {
  constructor(attributes = {}) {
    super();
    this.attributes = { ...attributes };
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    for (const [key, value] of Object.entries(attributes)) {
      if (key.startsWith('data-')) this.dataset[this.dataName(key)] = value;
    }
  }
  dataName(name) { return name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()); }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name.startsWith('data-')) this.dataset[this.dataName(name)] = String(value);
  }
  getAttribute(name) {
    if (name.startsWith('data-')) return this.dataset[this.dataName(name)] ?? null;
    return this.attributes[name] ?? null;
  }
  click() { this.dispatchEvent({ type: 'click', preventDefault() {} }); }
  set content(value) { this.setAttribute('content', value); }
  get content() { return this.getAttribute('content'); }
}

function fixture({ saved = null, dark = false, denyRead = false, denyWrite = false } = {}) {
  let storedValue = saved;
  const writes = [];
  const localStorage = {
    getItem(key) {
      if (denyRead) throw new Error('Storage read denied');
      return key === THEME_KEY ? storedValue : null;
    },
    setItem(key, value) {
      if (denyWrite) throw new Error('Storage write denied');
      writes.push([key, String(value)]);
      if (key === THEME_KEY) storedValue = String(value);
    },
    removeItem(key) { if (key === THEME_KEY) storedValue = null; },
  };
  const root = new Element();
  const meta = new Element({ name: 'theme-color', content: COLORS.light });
  const controls = new Element({ 'data-theme-controls': '' });
  controls.hidden = true;
  const choices = ['light', 'dark', 'auto'];
  const buttons = choices.map(value => new Element({ 'data-theme-choice': value }));
  const document = new Events();
  document.documentElement = root;
  document.readyState = 'loading';
  document.querySelector = selector => {
    if (/meta\[name=["']?theme-color["']?\]/.test(selector)) return meta;
    if (selector === '[data-theme-controls]') return controls;
    if (selector === '[data-theme-choice]') return buttons[0];
    const choice = selector.match(/^\[data-theme-choice=["']?(light|dark|auto)["']?\]$/);
    return choice ? buttons[choices.indexOf(choice[1])] : null;
  };
  document.querySelectorAll = selector => {
    if (selector === '[data-theme-choice]') return buttons;
    if (selector === '[data-theme-controls]') return [controls];
    return [];
  };
  const media = new Events();
  media.matches = dark;
  media.media = '(prefers-color-scheme: dark)';
  media.addListener = callback => media.addEventListener('change', callback);
  media.removeListener = callback => media.removeEventListener('change', callback);
  const window = new Events();
  window.document = document;
  window.localStorage = localStorage;
  window.matchMedia = query => {
    assert.equal(query, '(prefers-color-scheme: dark)', 'Only the user color-scheme preference is queried');
    return media;
  };
  const context = {
    window, document, localStorage, matchMedia: window.matchMedia,
    console, setTimeout, clearTimeout,
  };
  window.window = window;
  vm.runInNewContext(fs.readFileSync(themePath, 'utf8'), context, { filename: themePath });

  return {
    root, meta, controls, buttons, writes,
    resolved(expected, mode = expected) {
      assert.equal(root.getAttribute('data-theme'), expected, 'Resolved theme');
      assert.equal(root.getAttribute('data-theme-mode'), mode, 'Selected preference');
      assert.equal(meta.content, COLORS[expected], 'Browser chrome follows the resolved theme');
    },
    ready() {
      document.readyState = 'interactive';
      document.dispatchEvent({ type: 'DOMContentLoaded' });
    },
    choose(choice) { buttons[choices.indexOf(choice)].click(); },
    selected(expected) {
      for (const button of buttons) {
        assert.equal(button.getAttribute('aria-pressed'), String(button.dataset.themeChoice === expected));
      }
    },
    systemPrefersDark(matches) {
      media.matches = matches;
      media.dispatchEvent({ type: 'change', matches, media: media.media });
    },
    storage(value, key = THEME_KEY) {
      storedValue = value;
      window.dispatchEvent({ type: 'storage', key, newValue: value, storageArea: localStorage });
    },
  };
}

test('head script resolves auto synchronously before controls are available', () => {
  for (const dark of [false, true]) {
    const page = fixture({ dark });
    page.resolved(dark ? 'dark' : 'light', 'auto');
    assert.equal(page.controls.hidden, true);
    page.ready();
    assert.equal(page.controls.hidden, false);
    page.selected('auto');
  }
});

test('saved explicit preferences override the system and saved auto follows it', () => {
  for (const saved of ['light', 'dark', 'auto']) {
    for (const dark of [false, true]) {
      const page = fixture({ saved, dark });
      page.resolved(saved === 'auto' ? (dark ? 'dark' : 'light') : saved, saved);
      page.ready();
      page.selected(saved);
    }
  }
});

test('unknown stored values safely fall back to auto', () => {
  for (const saved of ['', 'sepia', 'DARK', 'null', ' light ']) {
    const page = fixture({ saved, dark: true });
    page.resolved('dark', 'auto');
    page.ready();
    page.selected('auto');
  }
});

test('each choice updates appearance, accessible state, and persisted preference', () => {
  const page = fixture({ dark: true });
  page.ready();
  for (const choice of ['light', 'dark', 'auto']) {
    page.choose(choice);
    page.resolved(choice === 'auto' ? 'dark' : choice, choice);
    page.selected(choice);
    assert.deepEqual(page.writes.at(-1), [THEME_KEY, choice]);
  }
});

test('system changes affect auto while respecting both explicit choices', () => {
  const page = fixture();
  page.ready();
  page.systemPrefersDark(true);
  page.resolved('dark', 'auto');
  page.selected('auto');
  page.choose('light');
  page.systemPrefersDark(false);
  page.systemPrefersDark(true);
  page.resolved('light');
  page.selected('light');
  page.choose('dark');
  page.systemPrefersDark(false);
  page.resolved('dark');
  page.selected('dark');
  page.choose('auto');
  page.resolved('light', 'auto');
  page.systemPrefersDark(true);
  page.resolved('dark', 'auto');
});

test('storage changes synchronize another tab and a cleared preference returns to auto', () => {
  const page = fixture({ saved: 'light', dark: true });
  page.ready();
  page.storage('dark');
  page.resolved('dark');
  page.selected('dark');
  page.storage('light');
  page.resolved('light');
  page.selected('light');
  page.storage('auto');
  page.resolved('dark', 'auto');
  page.selected('auto');
  page.storage('light');
  page.storage(null, null);
  page.resolved('dark', 'auto');
  page.selected('auto');
  page.storage('invalid');
  page.resolved('dark', 'auto');
  page.storage('light', 'unrelated-setting');
  page.resolved('dark', 'auto');
  assert.deepEqual(page.writes, [], 'Cross-tab updates do not write back and create event loops');
});

test('denied storage reads and writes do not prevent using the controls', () => {
  const page = fixture({ denyRead: true, denyWrite: true });
  page.resolved('light', 'auto');
  page.ready();
  assert.doesNotThrow(() => page.choose('dark'));
  page.resolved('dark');
  page.selected('dark');
  assert.doesNotThrow(() => page.choose('auto'));
  page.systemPrefersDark(true);
  page.resolved('dark', 'auto');
  page.selected('auto');
});
