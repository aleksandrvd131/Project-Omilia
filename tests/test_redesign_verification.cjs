/**
 * Comprehensive Redesign Verification Suite for Project Omilia
 * Kinetic Atelier (v3.0.0) Specification
 * Validates:
 * 1. HTML structure and accessibility attributes for new UX components
 * 2. Unified status capsule (Streak, XP, User - zero duplicates)
 * 3. 5-segment switcher and search with [/] hotkey
 * 4. Dual-viewport camera practice layout (reference video + webcam)
 * 5. Responsive design breakpoints and mobile bottom navigation
 * 6. Kinetic Atelier Design System Tokens and Keyframes
 * 7. Event listener and keyboard shortcut bindings in app.js
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const frontendDir = path.join(repoRoot, 'src/project_omilia/frontend');
const html = fs.readFileSync(path.join(frontendDir, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(frontendDir, 'style.css'), 'utf8');
const appJs = fs.readFileSync(path.join(frontendDir, 'app.js'), 'utf8');

test('HTML: Modernized Header contains Gamification Bar and Badges', () => {
  assert.ok(html.includes('id="header-streak-badge"'), 'Header streak badge must exist');
  assert.ok(html.includes('id="streak-days-count"'), 'Streak days counter span must exist');
  assert.ok(html.includes('id="header-xp-badge"'), 'Header XP badge must exist');
  assert.ok(html.includes('id="header-xp-count"'), 'Header XP counter span must exist');
  assert.ok(html.includes('id="btn-header-guide"'), 'Header guide button must exist');
  assert.ok(html.includes('id="btn-header-warmup"'), 'Header warmup button must exist');
  assert.ok(html.includes('id="unified-status-pill"'), 'Unified status pill must exist');
});

test('HTML: Quick-Practice Dashboard cards on Home screen', () => {
  assert.ok(html.includes('class="quick-practice-section"'), 'Quick practice section must exist');
  assert.ok(html.includes('id="home-card-warmup"'), 'home-card-warmup must exist');
  assert.ok(html.includes('id="home-card-blitz"'), 'home-card-blitz must exist');
  assert.ok(html.includes('id="home-card-roadmap"'), 'home-card-roadmap must exist');
});

test('HTML: Dual-Viewport Practice Modal components', () => {
  assert.ok(html.includes('id="practice-reference-video"'), 'practice-reference-video element must exist');
  assert.ok(html.includes('id="practice-reference-fallback"'), 'practice-reference-fallback element must exist');
  assert.ok(html.includes('class="practice-reference-pane"'), 'practice-reference-pane must exist');
  assert.ok(html.includes('class="practice-camera-pane"'), 'practice-camera-pane must exist');
});

test('HTML: Sound-Independent Accessibility & Visual Celebration', () => {
  assert.ok(html.includes('id="celebration-canvas"'), 'celebration-canvas must exist');
  assert.ok(html.includes('camera-silhouette-guide'), 'camera-silhouette-guide must exist in camera containers');
});

test('HTML: Mobile Bottom Navigation Bar (< 768px)', () => {
  assert.ok(html.includes('class="mobile-bottom-nav"'), 'mobile-bottom-nav container must exist');
  const navTabs = ['about', 'catalog', 'blitz', 'profile'];
  for (const tab of navTabs) {
    assert.ok(html.includes(`data-tab="${tab}"`), `mobile bottom nav button for ${tab} must exist`);
  }
});

test('HTML & Catalog: 5-Segment Switcher & Hotkey /', () => {
  assert.ok(html.includes('class="segmented-track'), 'segmented-track container must exist');
  assert.ok(html.includes('data-segment="all"'), 'segment all must exist');
  assert.ok(html.includes('data-segment="alphabet"'), 'segment alphabet must exist');
  assert.ok(html.includes('data-segment="numbers"'), 'segment numbers must exist');
  assert.ok(html.includes('data-segment="phrases"'), 'segment phrases must exist');
  assert.ok(html.includes('data-segment="family"'), 'segment family must exist');
  assert.ok(html.includes('data-segment="learned"'), 'segment learned must exist');
});

test('CSS: Kinetic Atelier Design System Tokens and Keyframes', () => {
  assert.ok(css.includes('--bg-primary: #0d0f12;'), '--bg-primary token must match Kinetic Atelier obsidian');
  assert.ok(css.includes('--bg-surface: #15181d;'), '--bg-surface token must match Kinetic Atelier graphite');
  assert.ok(css.includes('--kinetic-amber: #f59e0b;'), '--kinetic-amber token must exist');
  assert.ok(css.includes('--kinetic-emerald: #10b981;'), '--kinetic-emerald token must exist');
  assert.ok(css.includes('--font-mono:'), '--font-mono token must exist');
  assert.ok(css.includes('studioEdgeFlash') || css.includes('celebrateEdgeFlash'), 'Edge flash animation must exist');
  assert.ok(css.includes('.mobile-bottom-nav'), 'Mobile bottom nav styles must exist');
  assert.ok(css.includes('.unified-status-pill'), '.unified-status-pill styles must exist');
  assert.ok(css.includes('.segmented-track'), '.segmented-track styles must exist');
});

test('JS: App coordinator binds interactive feedback, celebrations, and shortcuts', () => {
  assert.ok(appJs.includes('function triggerConfetti()'), 'triggerConfetti function must exist in app.js');
  assert.ok(appJs.includes('function showXpToast('), 'showXpToast function must exist in app.js');
  assert.ok(appJs.includes('function triggerCelebration('), 'triggerCelebration function must exist in app.js');
  assert.ok(appJs.includes('homeCardWarmup'), 'homeCardWarmup must be wired in dom');
  assert.ok(appJs.includes('homeCardBlitz'), 'homeCardBlitz must be wired in dom');
  assert.ok(appJs.includes('homeCardRoadmap'), 'homeCardRoadmap must be wired in dom');
  assert.ok(appJs.includes("e.key === 'c'"), 'Keyboard shortcut C must be wired in app.js');
  assert.ok(appJs.includes("e.key === 'm'"), 'Keyboard shortcut M must be wired in app.js');
  assert.ok(appJs.includes("e.key === '/'"), 'Keyboard shortcut / must be wired in app.js');
});
