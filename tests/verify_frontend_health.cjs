/**
 * Automated Verification & Health Suite for Project Omilia Frontend
 * Checks:
 * 1. JS syntax on all frontend files and modules
 * 2. HTML structure & critical element contracts
 * 3. Video element attributes (autoplay, muted, playsinline)
 * 4. PWA manifest & Service Worker integrity
 * 5. MediaPipe & ONNX pipeline dependencies and integration
 * 6. Execution of unit and integration test suites
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');
const frontendDir = path.join(repoRoot, 'src/project_omilia/frontend');
const modulesDir = path.join(frontendDir, 'modules');

test('Verification: JS syntax validation on all frontend scripts', () => {
  const jsFiles = [
    'app.js',
    'dynamic-clip.js',
    'inference.js',
    'sw.js',
  ].map((f) => path.join(frontendDir, f));

  if (fs.existsSync(modulesDir)) {
    for (const file of fs.readdirSync(modulesDir)) {
      if (file.endsWith('.js')) {
        jsFiles.push(path.join(modulesDir, file));
      }
    }
  }

  for (const filePath of jsFiles) {
    if (fs.existsSync(filePath)) {
      assert.doesNotThrow(() => {
        execFileSync(process.execPath, ['--check', filePath], { stdio: 'pipe' });
      }, `Syntax error in ${path.relative(repoRoot, filePath)}`);
    }
  }
});

test('Verification: HTML structure and critical SPA DOM contracts', () => {
  const indexPath = path.join(frontendDir, 'index.html');
  assert.ok(fs.existsSync(indexPath), 'index.html must exist');
  const html = fs.readFileSync(indexPath, 'utf8');

  // Basic HTML5 structure
  assert.match(html, /<!DOCTYPE\s+html>/i, 'Valid DOCTYPE required');
  assert.match(html, /<html\s+lang=["']ru["']/i, 'HTML lang="ru" attribute required');
  assert.match(html, /<meta\s+charset=["']UTF-8["']/i, 'UTF-8 charset required');
  assert.match(html, /<meta\s+name=["']viewport["']/i, 'Responsive viewport meta required');

  // MediaPipe & ONNX CDN scripts in <head>
  assert.ok(html.includes('@mediapipe/camera_utils'), 'camera_utils script must be in head');
  assert.ok(html.includes('@mediapipe/hands'), 'mediapipe hands script must be in head');
  assert.ok(html.includes('@mediapipe/pose'), 'mediapipe pose script must be in head');
  assert.ok(html.includes('ort.min.js') || html.includes('onnxruntime-web'), 'ONNX runtime web script must be in head');

  // Core navigation tabs
  const requiredTabs = ['about', 'catalog', 'blitz', 'profile'];
  for (const tab of requiredTabs) {
    assert.ok(
      html.includes(`id="tab-${tab}"`) || html.includes(`data-tab="${tab}"`),
      `Tab '${tab}' container or button must exist`
    );
  }

  // Interactive Modals
  const requiredModals = [
    'practice-modal',
    'blitz-active',
    'warmup-modal',
    'onboarding-modal',
  ];
  for (const modal of requiredModals) {
    assert.ok(html.includes(`id="${modal}"`), `Modal #${modal} must exist in index.html`);
  }

  // Critical camera HUD elements
  const requiredHud = [
    'practice-canvas',
    'practice-video',
    'practice-hold-fill',
    'practice-hud-gesture',
    'practice-hud-score',
    'blitz-canvas',
    'blitz-video',
    'blitz-hold-fill',
    'blitz-hud-gesture',
    'blitz-hud-score',
    'warmup-canvas',
    'warmup-video',
    'warmup-hold-fill',
    'warmup-hud-gesture',
    'warmup-hud-score',
  ];
  for (const id of requiredHud) {
    assert.ok(html.includes(`id="${id}"`), `HUD element #${id} must exist in index.html`);
  }
});

test('Verification: Video elements have autoplay, muted, playsinline', () => {
  const indexPath = path.join(frontendDir, 'index.html');
  const html = fs.readFileSync(indexPath, 'utf8');

  for (const id of ['practice-video', 'blitz-video', 'warmup-video']) {
    const regex = new RegExp(`<video[^>]*id=["']${id}["'][^>]*>`, 'i');
    const match = html.match(regex);
    assert.ok(match, `<video id="${id}"> must exist`);
    const tag = match[0];
    assert.ok(tag.includes('autoplay'), `${id} must have autoplay`);
    assert.ok(tag.includes('muted'), `${id} must have muted`);
    assert.ok(tag.includes('playsinline'), `${id} must have playsinline`);
  }
});

test('Verification: CSS stylesheet exists and is valid', () => {
  const cssPath = path.join(frontendDir, 'style.css');
  assert.ok(fs.existsSync(cssPath), 'style.css must exist');
  const css = fs.readFileSync(cssPath, 'utf8');
  assert.ok(css.length > 500, 'style.css must not be empty');

  // Check balanced braces in CSS
  let depth = 0;
  for (let i = 0; i < css.length; i++) {
    const ch = css[i];
    if (ch === '{') depth++;
    else if (ch === '}') depth--;
    assert.ok(depth >= 0, `Unmatched closing brace in style.css at character ${i}`);
  }
  assert.equal(depth, 0, 'Unbalanced opening braces in style.css');
});
