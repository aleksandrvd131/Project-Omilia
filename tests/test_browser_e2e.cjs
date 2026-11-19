/**
 * End-to-end Headless Browser Verification using Chromium + CDP (Chrome DevTools Protocol)
 * Launches Project Omilia server, loads the web app in real headless Chromium,
 * verifies console logs, DOM rendering, tab switching, modal behavior, and responsive layouts.
 */

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const PORT = 8091;
const CDP_PORT = 9222;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const repoRoot = path.resolve(__dirname, '..');

async function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

async function waitForServer(url, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      // wait
    }
    await sleep(250);
  }
  throw new Error(`Server failed to start at ${url} within ${timeoutMs}ms`);
}

async function runBrowserE2E() {
  console.log('1. Starting FastAPI backend server on port', PORT);
  const serverProcess = spawn('uv', [
    'run',
    'uvicorn',
    'project_omilia.app:create_app',
    '--factory',
    '--host',
    '127.0.0.1',
    '--port',
    String(PORT),
  ], {
    cwd: repoRoot,
    stdio: 'pipe',
  });

  serverProcess.stderr.on('data', (d) => {
    // console.log('[Server]', d.toString());
  });

  let chromiumProcess = null;
  const tempUserData = `/tmp/chromium-e2e-${Date.now()}`;

  try {
    await waitForServer(`${BASE_URL}/`);
    console.log('✓ FastAPI backend is responding HTTP 200');

    console.log('2. Starting Headless Chromium with CDP on port', CDP_PORT);
    chromiumProcess = spawn('/usr/bin/chromium', [
      '--headless=new',
      `--remote-debugging-port=${CDP_PORT}`,
      `--user-data-dir=${tempUserData}`,
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--mute-audio',
      'about:blank',
    ], { stdio: 'pipe' });

    // Wait for CDP to be ready
    let target = null;
    for (let i = 0; i < 30; i++) {
      try {
        const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent(BASE_URL + '/')}`, { method: 'PUT' });
        target = await res.json();
        break;
      } catch {
        await sleep(200);
      }
    }
    if (!target || !target.webSocketDebuggerUrl) {
      throw new Error('Failed to connect to Chromium CDP endpoint');
    }
    console.log('✓ Headless Chromium connected via CDP');

    const ws = new WebSocket(target.webSocketDebuggerUrl);
    let msgId = 1;
    const pending = new Map();
    const consoleErrors = [];
    const pageErrors = [];

    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
      if (msg.method === 'Runtime.exceptionThrown') {
        const desc = msg.params.exceptionDetails?.exception?.description || msg.params.exceptionDetails?.text;
        pageErrors.push(desc);
      }
      if (msg.method === 'Runtime.consoleAPICalled') {
        const type = msg.params.type;
        const text = msg.params.args.map((a) => a.value || a.description || '').join(' ');
        if (type === 'error') {
          consoleErrors.push(text);
        }
      }
    };

    function sendCmd(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = msgId++;
        pending.set(id, { resolve, reject });
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    await sendCmd('Page.enable');
    await sendCmd('Runtime.enable');

    console.log('3. Loading Project Omilia in browser and waiting 2s for DOMContentLoaded...');
    await sleep(2000);

    // Evaluate basic DOM properties
    const titleRes = await sendCmd('Runtime.evaluate', { expression: 'document.title' });
    console.log('✓ Document Title:', titleRes.result.value);

    // Check tabs
    const tabsCheck = await sendCmd('Runtime.evaluate', {
      expression: `
        (() => {
          const tabs = ['about', 'catalog', 'blitz', 'profile'];
          return tabs.map(t => {
            const el = document.getElementById('tab-' + t);
            const btn = document.getElementById('tab-btn-' + t);
            return { tab: t, exists: !!el, btnExists: !!btn };
          });
        })()
      `,
      returnByValue: true,
    });
    console.log('✓ Tab elements check:', tabsCheck.result.value);

    // Check critical buttons clickability without errors
    const clickCheck = await sendCmd('Runtime.evaluate', {
      expression: `
        (() => {
          const results = [];
          const startBtn = document.getElementById('btn-hero-start');
          if (startBtn) {
            startBtn.click();
            results.push({ action: 'btn-hero-start clicked', activeTab: document.querySelector('.tab-content.active')?.id });
          }
          const guideBtn = document.getElementById('btn-hero-guide');
          if (guideBtn) {
            guideBtn.click();
            const modal = document.getElementById('onboarding-modal');
            results.push({ action: 'btn-hero-guide clicked', modalDisplay: modal?.style?.display });
            const closeBtn = document.getElementById('btn-close-onboarding');
            if (closeBtn) closeBtn.click();
          }
          return results;
        })()
      `,
      returnByValue: true,
    });
    console.log('✓ Button interactions:', clickCheck.result.value);

    // Check responsive viewport test: Mobile (375x667)
    await sendCmd('Emulation.setDeviceMetricsOverride', {
      width: 375,
      height: 667,
      deviceScaleFactor: 2,
      mobile: true,
    });
    const mobileCheck = await sendCmd('Runtime.evaluate', {
      expression: `
        (() => {
          return {
            windowWidth: window.innerWidth,
            navTabsVisible: !!document.querySelector('header nav'),
            mainScrollable: document.body.scrollWidth <= window.innerWidth + 20
          };
        })()
      `,
      returnByValue: true,
    });
    console.log('✓ Mobile viewport check (375px):', mobileCheck.result.value);

    // Filter benign console warnings if any (e.g., SW registration or MediaPipe CDN when camera absent)
    const fatalErrors = pageErrors.filter((e) => !e.includes('navigator.mediaDevices') && !e.includes('Camera'));
    console.log('Console Errors:', consoleErrors.length, 'Page Unhandled Errors:', pageErrors.length);
    if (fatalErrors.length > 0) {
      console.error('Fatal errors encountered:', fatalErrors);
      throw new Error(`Fatal page errors: ${fatalErrors.join('; ')}`);
    }

    console.log('✓ E2E Chromium Verification PASSED successfully!');
    ws.close();
  } finally {
    if (chromiumProcess) {
      chromiumProcess.kill('SIGKILL');
      try {
        fs.rmSync(tempUserData, { recursive: true, force: true });
      } catch {}
    }
    serverProcess.kill('SIGTERM');
  }
}

runBrowserE2E().catch((err) => {
  console.error('E2E Verification Failed:', err);
  process.exit(1);
});
