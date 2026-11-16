const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const frontend = path.join(__dirname, '../src/project_omilia/frontend');
const html = fs.readFileSync(path.join(frontend, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script src="\/static\/([^"]+)"/g)].map(match => match[1]);

test('homepage scripts initialize and all hero buttons respond', async () => {
  const nodes = new Map();
  function element(id = '') {
    const classes = new Set();
    const handlers = new Map();
    return {
      id, dataset: {}, style: {}, textContent: '', innerHTML: '',
      classList: {
        add(name) { classes.add(name); },
        remove(name) { classes.delete(name); },
        toggle(name, active) {
          if (active) classes.add(name);
          else classes.delete(name);
        },
        contains(name) { return classes.has(name); },
      },
      addEventListener(event, callback) { handlers.set(event, callback); },
      click() {
        assert.ok(handlers.has('click'), `Missing click handler for ${id}`);
        return handlers.get('click')({ preventDefault() {} });
      },
      appendChild() {}, append() {}, replaceChildren() {}, setAttribute() {},
      querySelectorAll() { return []; }, querySelector() { return null; },
    };
  }
  for (const match of html.matchAll(/id="([^"]+)"/g)) {
    nodes.set(match[1], element(match[1]));
  }
  const tabs = ['about', 'catalog', 'blitz', 'profile'].map(name => nodes.get(`tab-${name}`));
  const nav = tabs.map(tab => {
    const button = element();
    button.dataset.tab = tab.id.slice(4);
    return button;
  });
  let ready;
  const alerts = [];
  const context = vm.createContext({
    console, setTimeout, clearTimeout, setInterval, clearInterval,
    localStorage: { getItem() { return null; } },
    alert(message) { alerts.push(message); },
    scrollTo() {},
    addEventListener() {},
    document: {
      readyState: 'loading',
      head: element(),
      querySelector() { return null; },
      getElementById(id) { return nodes.get(id) || null; },
      createElement() { return element(); },
      querySelectorAll(selector) {
        if (selector === '.nav-btn') return nav;
        if (selector === '.tab-content') return tabs;
        return [];
      },
      addEventListener(event, callback) {
        if (event === 'DOMContentLoaded') ready = callback;
      },
    },
    fetch: async () => ({
      ok: true,
      json: async () => ({ gestures: [], total_count: 0, learned_count: 0 }),
    }),
  });
  context.window = context;
  context.self = context;

  for (const script of scripts) {
    vm.runInContext(fs.readFileSync(path.join(frontend, script), 'utf8'), context, { filename: script });
  }
  assert.equal(typeof ready, 'function');
  await ready();

  nodes.get('btn-hero-start').click();
  assert.ok(nodes.get('tab-catalog').classList.contains('active'));
  nodes.get('btn-hero-lk').click();
  assert.ok(nodes.get('tab-profile').classList.contains('active'));
  nodes.get('btn-hero-guide').click();
  assert.equal(nodes.get('onboarding-modal').style.display, 'flex');
  assert.equal(nodes.get('onboarding-step-1').style.display, 'block');
  nodes.get('btn-close-onboarding').click();
  assert.equal(nodes.get('onboarding-modal').style.display, 'none');
  await nodes.get('btn-hero-warmup').click();
  assert.equal(alerts.length, 1);
  assert.ok(nodes.get('tab-profile').classList.contains('active'));
});
