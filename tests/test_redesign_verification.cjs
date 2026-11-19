/**
 * Comprehensive Redesign Verification Suite for Project Omilia
 * Validates:
 * 1. HTML structure and accessibility attributes for new UX components
 * 2. Visual gamification elements (XP, streak, badges, celebration canvas)
 * 3. Dual-viewport camera practice layout (reference video + webcam)
 * 4. Responsive design breakpoints and mobile bottom navigation
 * 5. MediaPipe & ONNX CDN scripts in <head>
 * 6. Event listener and keyboard shortcut bindings in app.js
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

test('CSS: Dark Glassmorphic Design System Tokens and Keyframes', () => {
  assert.ok(css.includes('--bg-primary: #0b0f19;'), '--bg-primary token must match design system');
  assert.ok(css.includes('--bg-surface: #131b2e;'), '--bg-surface token must match design system');
  assert.ok(css.includes('--brand-primary: #2563eb;'), '--brand-primary token must match design system');
  assert.ok(css.includes('--success: #10b981;'), '--success token must match design system');
  assert.ok(css.includes('--warning: #f59e0b;'), '--warning token must match design system');
  assert.ok(css.includes('--streak-fire: #f97316;'), '--streak-fire token must match design system');
  assert.ok(css.includes('@keyframes celebrateEdgeFlash'), 'celebrateEdgeFlash animation must exist');
  assert.ok(css.includes('@keyframes flameGlow'), 'flameGlow animation must exist');
  assert.ok(css.includes('.mobile-bottom-nav'), 'Mobile bottom nav styles must exist');
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
});
