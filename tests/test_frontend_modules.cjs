const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const UI = require('../src/project_omilia/frontend/modules/ui.js');
const Camera = require('../src/project_omilia/frontend/modules/camera.js');
const Socket = require('../src/project_omilia/frontend/modules/socket.js');
const Practice = require('../src/project_omilia/frontend/modules/practice.js');
const Blitz = require('../src/project_omilia/frontend/modules/blitz.js');
const Catalog = require('../src/project_omilia/frontend/modules/catalog.js');
const Warmup = require('../src/project_omilia/frontend/modules/warmup.js');

test('UI module: escapeHtml escapes dangerous characters', () => {
  assert.equal(UI.escapeHtml('hello <script>alert("1")</script> & \'world\''), 'hello &lt;script&gt;alert(&quot;1&quot;)&lt;/script&gt; &amp; &#039;world&#039;');
  assert.equal(UI.escapeHtml(''), '');
  assert.equal(UI.escapeHtml(null), '');
});

test('Camera module: compactLandmarks rounds to 4 decimals', () => {
  const input = [
    { x: 0.123456, y: 0.654321, z: 0.987654 },
    { x: 0.0, y: 1.0 },
  ];
  const output = Camera.compactLandmarks(input);
  assert.equal(output.length, 2);
  assert.equal(output[0].x, 0.1235);
  assert.equal(output[0].y, 0.6543);
  assert.equal(output[0].z, 0.9877);
  assert.equal(output[1].x, 0);
  assert.equal(output[1].y, 1);
  assert.equal(output[1].z, 0);
});

test('Socket module: exports methods and manages socket state', () => {
  assert.equal(typeof Socket.ensureWebSocket, 'function');
  assert.equal(typeof Socket.sendPayload, 'function');
  assert.equal(typeof Socket.sendRaw, 'function');
  assert.equal(typeof Socket.close, 'function');
  assert.equal(typeof Socket.isOpen, 'function');
  assert.equal(Socket.isOpen(), false);
});

test('Practice module: handlePracticePrediction updates progress and triggers learned callback', () => {
  const state = {
    practice: {
      gesture: { name: 'привет', title: 'Привет' },
      holdProgress: 0,
      holdTarget: 1.0,
      isLearned: false,
      lastTimestamp: 1000,
    },
  };
  const dom = {
    practiceHudGesture: {},
    practiceHudScore: {},
    practiceHoldFill: { style: {} },
    practiceCanvas: { parentElement: { classList: { add() {}, remove() {} } } },
    practiceSuccessOverlay: { style: {} },
  };

  let learnedCalled = false;
  // Matching prediction with delta 1.0s (>= holdTarget)
  Practice.handlePracticePrediction(
    { gesture: 'привет', confidence: 95 },
    2000,
    1.0,
    state,
    dom,
    {
      playSpeech: () => {},
      updateProfileView: () => { learnedCalled = true; },
    }
  );

  assert.equal(state.practice.isLearned, true);
  assert.equal(state.practice.holdProgress, 1.0);
  assert.equal(dom.practiceHudGesture.textContent, 'привет');
  assert.match(dom.practiceHudScore.textContent, /95%/);
});

test('Blitz module: handleBlitzPrediction advances hold progress on match', () => {
  const state = {
    blitz: {
      questions: [{ gesture_name: 'спасибо', title: 'Спасибо' }],
      currentIndex: 0,
      holdProgress: 0,
      holdTarget: 1.5,
      isActive: true,
      advanceTimer: null,
    },
  };
  const dom = {
    blitzHudGesture: {},
    blitzHudScore: {},
    blitzHoldFill: { style: {} },
    blitzCanvas: { parentElement: { classList: { add() {}, remove() {} } } },
  };

  // Prediction matches question
  Blitz.handleBlitzPrediction(
    { gesture: 'спасибо', confidence: 92 },
    2000,
    0.5,
    state,
    dom
  );

  assert.equal(state.blitz.holdProgress, 0.5);
  assert.equal(dom.blitzHudGesture.textContent, 'спасибо');
  assert.match(dom.blitzHudScore.textContent, /92%/);
});

test('Catalog module: getGestureLevelInfo correctly maps all curriculum levels (1-4)', () => {
  const lvl1 = [
    'а', 'б', 'в', 'г', 'д', 'е', 'ё', 'ж', 'з', 'и', 'й', 'к', 'л', 'м', 'н', 'о',
    'п', 'р', 'с', 'т', 'у', 'ф', 'х', 'ц', 'ч', 'ш', 'щ', 'ъ', 'ы', 'ь', 'э', 'ю', 'я',
  ];
  const lvl2 = ['1', '2', '3', '4', '5'];
  const lvl3 = ['привет', 'спасибо', 'помоги', 'пожалуйста', 'да', 'нет', 'мир', 'хорошо'];
  const lvl4 = ['дом', 'мама', 'папа', 'семья', 'любовь', 'стоп', 'книга', 'ты'];

  for (const name of lvl1) {
    const info = Catalog.getGestureLevelInfo({ name });
    assert.equal(info.level, 1, `Expected level 1 for ${name}`);
    assert.equal(info.level_title, 'Дактильный алфавит');
  }

  for (const name of lvl2) {
    const info = Catalog.getGestureLevelInfo({ name });
    assert.equal(info.level, 2, `Expected level 2 for ${name}`);
    assert.equal(info.level_title, 'Числительные и счёт');
  }

  for (const name of lvl3) {
    const info = Catalog.getGestureLevelInfo({ name });
    assert.equal(info.level, 3, `Expected level 3 for ${name}`);
    assert.equal(info.level_title, 'Базовый этикет');
  }

  for (const name of lvl4) {
    const info = Catalog.getGestureLevelInfo({ name });
    assert.equal(info.level, 4, `Expected level 4 for ${name}`);
    assert.equal(info.level_title, 'Семья и окружение');
  }
});

test('Catalog module: calculateLevelStats accurately computes level totals and unlock conditions', () => {
  const lvl1 = [
    'а', 'б', 'в', 'г', 'д', 'е', 'ё', 'ж', 'з', 'и', 'й', 'к', 'л', 'м', 'н', 'о',
    'п', 'р', 'с', 'т', 'у', 'ф', 'х', 'ц', 'ч', 'ш', 'щ', 'ъ', 'ы', 'ь', 'э', 'ю', 'я',
  ];
  const lvl2 = ['1', '2', '3', '4', '5'];
  const lvl3 = ['привет', 'спасибо', 'помоги', 'пожалуйста', 'да', 'нет', 'мир', 'хорошо'];
  const lvl4 = ['дом', 'мама', 'папа', 'семья', 'любовь', 'стоп', 'книга', 'ты'];

  const mockGestures = [
    ...lvl1.map((n, i) => ({ name: n, is_learned: i < 24 })), // 24/33 = 73% learned
    ...lvl2.map((n) => ({ name: n, is_learned: false })),
    ...lvl3.map((n) => ({ name: n, is_learned: false })),
    ...lvl4.map((n) => ({ name: n, is_learned: false })),
  ];

  const stats = Catalog.calculateLevelStats(mockGestures);
  assert.equal(stats[1].total, 33);
  assert.equal(stats[1].learned, 24);
  assert.equal(stats[1].percentage, 73);
  assert.equal(stats[1].isUnlocked, true);

  assert.equal(stats[2].total, 5);
  assert.equal(stats[2].isUnlocked, true); // Level 1 is >= 70%, unlocking Level 2

  assert.equal(stats[3].total, 8);
  assert.equal(stats[3].isUnlocked, false); // Level 2 is 0%, Level 3 remains locked

  assert.equal(stats[4].total, 8);
  assert.equal(stats[4].isUnlocked, false);
});

test('Camera module: checkHandAlignment detects hand alignment correctly', () => {
  const baseHand = Array.from({ length: 21 }, (_, i) => ({
    x: 0.5 + i * 0.01,
    y: 0.6 + i * 0.005,
    z: 0.0,
  }));

  // Тождественная рука
  const identicalHand = baseHand.map((p) => ({ ...p }));
  assert.equal(Camera.checkHandAlignment(identicalHand, baseHand), true);

  // Слегка смещенная рука (та же анатомическая форма)
  const translatedHand = baseHand.map((p) => ({ x: p.x + 0.02, y: p.y - 0.02, z: p.z }));
  assert.equal(Camera.checkHandAlignment(translatedHand, baseHand), true);

  // Принципиально другая форма руки
  const differentHand = baseHand.map((p) => ({ x: 0.1, y: 0.1, z: 0.0 }));
  differentHand[4] = { x: 0.9, y: 0.9, z: 0.0 };
  assert.equal(Camera.checkHandAlignment(differentHand, baseHand), false);

  // Неполная или пустая рука
  assert.equal(Camera.checkHandAlignment(null, baseHand), false);
  assert.equal(Camera.checkHandAlignment([], baseHand), false);
});

test('Camera module: drawGhostSilhouette renders translucent bones and highlights green on match', () => {
  const ghostHand = [
    Array.from({ length: 21 }, (_, i) => ({
      x: 0.5 + i * 0.005,
      y: 0.5 + i * 0.005,
      z: 0.0,
    })),
  ];

  let strokeStyles = [];
  let fillStyles = [];
  let arcCount = 0;

  const mockCtx = {
    save() {},
    restore() {},
    beginPath() {},
    closePath() {},
    moveTo() {},
    lineTo() {},
    stroke() {
      strokeStyles.push(mockCtx.strokeStyle);
    },
    fill() {
      fillStyles.push(mockCtx.fillStyle);
    },
    arc() {
      arcCount++;
    },
    lineWidth: 1,
    strokeStyle: '',
    fillStyle: '',
    shadowColor: '',
    shadowBlur: 0,
    lineCap: '',
    lineJoin: '',
  };

  // 1. Без совпадения — кости отрисованы полупрозрачным цианом
  Camera.drawGhostSilhouette(mockCtx, ghostHand, 640, 480, { userHands: [], isMatch: false });
  assert.ok(strokeStyles.some((s) => s.includes('56, 189, 248')));
  assert.equal(arcCount, 21);

  // 2. Совпадение (isMatch: true) — кости подсвечены ярко-зеленым
  strokeStyles = [];
  fillStyles = [];
  arcCount = 0;
  Camera.drawGhostSilhouette(mockCtx, ghostHand, 640, 480, { userHands: [], isMatch: true });
  assert.ok(strokeStyles.some((s) => s.includes('34, 197, 94')));
  assert.ok(fillStyles.some((s) => s.includes('74, 222, 128')));
  assert.equal(arcCount, 21);
});

test('Practice module: fetchGhostSilhouette and openPracticeModal exclude dynamic gestures', async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    const decodedUrl = decodeURIComponent(url);
    if (decodedUrl.includes('нет')) {
      return {
        ok: true,
        json: async () => ({ status: 'ok', name: 'нет', is_dynamic: true, silhouette: null }),
      };
    }
    return {
      ok: true,
      json: async () => ({
        status: 'ok',
        name: 'мир',
        is_dynamic: false,
        silhouette: [Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5, z: 0.0 }))],
      }),
    };
  };

  try {
    // 1. Динамический жест никогда не возвращает силуэт
    const dynamicRes = await Practice.fetchGhostSilhouette('нет');
    assert.equal(dynamicRes, null);

    // 2. Статический жест возвращает 21-точечный силуэт
    const staticRes = await Practice.fetchGhostSilhouette('мир');
    assert.ok(Array.isArray(staticRes));
    assert.equal(staticRes[0].length, 21);

    // 3. openPracticeModal устанавливает ghostSilhouette = null для динамического жеста
    const stateDynamic = { practice: {} };
    const dom = {
      practiceTitle: {},
      btnDynamicPractice: {},
      practiceHoldFill: { style: {}, parentElement: {} },
      practiceTipText: {},
      practiceHudGesture: {},
      practiceHudScore: {},
      practiceSuccessOverlay: { style: {} },
      practiceModal: { style: {} },
    };
    Practice.openPracticeModal({ name: 'нет', is_dynamic: true, dynamic_hands_count: 1 }, stateDynamic, dom);
    assert.equal(stateDynamic.practice.ghostSilhouette, null);

    // 4. openPracticeModal оставляет ghostSilhouette = null (призрачный показ отключен, чтобы не путать пользователя)
    const stateStatic = { practice: {} };
    Practice.openPracticeModal({ name: 'мир', is_dynamic: false }, stateStatic, dom);
    await new Promise((r) => setTimeout(r, 20));
    assert.equal(stateStatic.practice.ghostSilhouette, null);

    // 5. closePracticeModal очищает ghostSilhouette
    Practice.closePracticeModal(stateStatic, dom, () => {});
    assert.equal(stateStatic.practice.ghostSilhouette, null);
  } finally {
    global.fetch = originalFetch;
  }
});

test('Camera module: facingMode defaults to user and switches between user and environment', async () => {
  // 1. По умолчанию режим фронтальной камеры 'user'
  Camera.setFacingMode('user');
  assert.equal(Camera.getFacingMode(), 'user');

  const state = { facingMode: 'user', isCameraRunning: false };
  const containerClasses = new Set(['camera-container', 'mirrored']);
  const dom = {
    practiceCanvas: {
      parentElement: {
        classList: {
          contains: (cls) => containerClasses.has(cls),
          add: (cls) => containerClasses.add(cls),
          remove: (cls) => containerClasses.delete(cls),
        },
      },
    },
  };

  // 2. Переключение с 'user' на 'environment'
  const mode1 = await Camera.switchCamera(state, dom);
  assert.equal(mode1, 'environment');
  assert.equal(state.facingMode, 'environment');
  assert.equal(containerClasses.has('mirrored'), false, 'mirrored class should be removed for environment camera');

  // 3. Обратное переключение с 'environment' на 'user'
  const mode2 = await Camera.switchCamera(state, dom);
  assert.equal(mode2, 'user');
  assert.equal(state.facingMode, 'user');
  assert.equal(containerClasses.has('mirrored'), true, 'mirrored class should be added back for user camera');
});

test('Camera module: switchCamera respects device availability and restarts active camera', async () => {
  const origDesc = Object.getOwnPropertyDescriptor(globalThis, 'navigator');

  try {
    // 1. При наличии только одного видеоустройства переключение отклоняется
    Object.defineProperty(globalThis, 'navigator', {
      value: {
        mediaDevices: {
          enumerateDevices: async () => [{ kind: 'videoinput', deviceId: 'cam1' }],
        },
      },
      configurable: true,
      writable: true,
    });

    const stateSingle = { facingMode: 'user', isCameraRunning: false };
    const resSingle = await Camera.switchCamera(stateSingle);
    assert.equal(resSingle, 'user', 'Should keep user facingMode when single device exists');
    assert.equal(stateSingle.facingMode, 'user');

    // 2. При наличии 2 и более видеоустройств переключение выполняется
    Object.defineProperty(globalThis, 'navigator', {
      value: {
        mediaDevices: {
          enumerateDevices: async () => [
            { kind: 'videoinput', deviceId: 'cam1' },
            { kind: 'videoinput', deviceId: 'cam2' },
          ],
        },
      },
      configurable: true,
      writable: true,
    });

    let stopCalled = false;
    const stateRunning = {
      facingMode: 'user',
      isCameraRunning: true,
      cameraTarget: 'practice',
      camera: {
        stop: () => {
          stopCalled = true;
        },
      },
      latestHands: [],
    };

    const resMulti = await Camera.switchCamera(stateRunning, null, {});
    assert.equal(resMulti, 'environment');
    assert.equal(stateRunning.facingMode, 'environment');
    assert.equal(stopCalled, true, 'Running camera should be stopped before restart');
  } finally {
    if (origDesc) {
      Object.defineProperty(globalThis, 'navigator', origDesc);
    }
  }
});

test('Camera module: startCamera binds correct video element for practice, warmup, and blitz modes', () => {
  const origCamera = globalThis.Camera;
  try {
    let capturedVideoEl = null;
    globalThis.Camera = class MockCamera {
      constructor(videoElement) {
        capturedVideoEl = videoElement;
      }
      start() {
        return Promise.resolve();
      }
      stop() {}
    };

    const mockHands = { setOptions: () => {} };
    const mockDom = {
      practiceVideo: { id: 'practice-video', closest: () => null },
      warmupVideo: { id: 'warmup-video', closest: () => null },
      blitzVideo: { id: 'blitz-video', closest: () => null },
    };

    // 1. Режим практики
    const statePractice = { mediaPipeHands: mockHands };
    Camera.startCamera('practice', statePractice, mockDom, {});
    assert.equal(capturedVideoEl, mockDom.practiceVideo);
    assert.equal(statePractice.cameraTarget, 'practice');

    // 2. Режим разминки (SM-2 SRS)
    const stateWarmup = { mediaPipeHands: mockHands };
    Camera.startCamera('warmup', stateWarmup, mockDom, {});
    assert.equal(capturedVideoEl, mockDom.warmupVideo);
    assert.equal(stateWarmup.cameraTarget, 'warmup');

    // 3. Режим блиц-опроса
    const stateBlitz = { mediaPipeHands: mockHands };
    Camera.startCamera('blitz', stateBlitz, mockDom, {});
    assert.equal(capturedVideoEl, mockDom.blitzVideo);
    assert.equal(stateBlitz.cameraTarget, 'blitz');
  } finally {
    globalThis.Camera = origCamera;
  }
});

test('PWA Manifest: loads valid manifest with required fields and icons', () => {
  const manifestPath = path.resolve(__dirname, '../src/project_omilia/frontend/manifest.json');
  assert.ok(fs.existsSync(manifestPath), 'manifest.json must exist');

  const raw = fs.readFileSync(manifestPath, 'utf8');
  const manifest = JSON.parse(raw);

  assert.equal(manifest.name, 'Omiλia - Тренажер РЖЯ');
  assert.equal(manifest.short_name, 'Omiλia');
  assert.equal(manifest.display, 'standalone');
  assert.ok(manifest.theme_color, 'theme_color is required');
  assert.ok(manifest.background_color, 'background_color is required');
  assert.ok(Array.isArray(manifest.icons), 'icons must be an array');
  assert.ok(manifest.icons.length >= 2, 'at least 2 icons expected');

  const iconsDir = path.resolve(__dirname, '../src/project_omilia/frontend/icons');
  assert.ok(fs.existsSync(iconsDir), 'icons directory must exist');

  for (const icon of manifest.icons) {
    assert.ok(icon.src, 'icon src is required');
    assert.ok(icon.sizes, 'icon sizes is required');
    assert.ok(icon.type, 'icon type is required');

    // Проверка физического наличия файла на диске
    const relativePath = icon.src.replace('/static/', '');
    const iconFilePath = path.resolve(__dirname, '../src/project_omilia/frontend', relativePath);
    assert.ok(fs.existsSync(iconFilePath), `Icon file ${iconFilePath} must exist on disk`);
  }
});

// ============================================================================
// Тесты новых пользовательских историй (US-1 .. US-6)
// ============================================================================

test('UI module: calculateUserXP correctly computes rank tiers and progress', () => {
  // Новичок: 0 XP
  const s0 = { currentUser: { learned_gestures: [] }, streak: 0 };
  const r0 = UI.calculateUserXP(s0);
  assert.equal(r0.currentXp, 0);
  assert.equal(r0.rank, 'Новичок РЖЯ 🌱');
  assert.equal(r0.nextRank, 'Ученик РЖЯ 📚');
  assert.equal(r0.progressPct, 0);
  assert.equal(r0.xpNeeded, 100);
  assert.equal(r0.isMaxRank, false);

  // Ученик: 4 жеста = 100 XP
  const s1 = { currentUser: { learned_gestures: ['а', 'б', 'в', 'г'] }, streak: 0 };
  const r1 = UI.calculateUserXP(s1);
  assert.equal(r1.currentXp, 100);
  assert.equal(r1.rank, 'Ученик РЖЯ 📚');
  assert.equal(r1.nextRank, 'Знаток РЖЯ 🚀');
  assert.equal(r1.progressPct, 0);
  assert.equal(r1.xpNeeded, 200);

  // Знаток: 10 жестов (250) + 3 дня стрик (150) = 400 XP
  const s2 = { currentUser: { learned_gestures: new Array(10).fill('g'), streak: 3 } };
  const r2 = UI.calculateUserXP(s2);
  assert.equal(r2.currentXp, 400);
  assert.equal(r2.rank, 'Знаток РЖЯ 🚀');
  assert.equal(r2.nextRank, 'Мастер РЖЯ 🌟');
  assert.equal(r2.progressPct, 25); // (400 - 300) / 400 = 25%
  assert.equal(r2.xpNeeded, 300);

  // Мастер: 20 жестов (500) + 5 дней стрик (250) = 750 XP
  const s3 = { currentUser: { learned_gestures: new Array(20).fill('g'), streak: 5 } };
  const r3 = UI.calculateUserXP(s3);
  assert.equal(r3.currentXp, 750);
  assert.equal(r3.rank, 'Мастер РЖЯ 🌟');
  assert.equal(r3.nextRank, null);
  assert.equal(r3.progressPct, 100);
  assert.equal(r3.xpNeeded, 0);
  assert.equal(r3.isMaxRank, true);
});

test('Camera module: formatCameraError correctly categorizes error types', () => {
  // Доступ запрещен
  const notAllowed = Camera.formatCameraError({ name: 'NotAllowedError' });
  assert.equal(notAllowed.type, 'permission_denied');
  assert.match(notAllowed.title, /заблокирован|запрещён/);
  assert.match(notAllowed.message, /настройках браузера/);
  assert.ok(notAllowed.actionText);

  // Камера не найдена
  const notFound = Camera.formatCameraError({ name: 'NotFoundError' });
  assert.equal(notFound.type, 'not_found');
  assert.match(notFound.title, /не найдена/);

  // Камера занята
  const inUse = Camera.formatCameraError({ name: 'NotReadableError' });
  assert.equal(inUse.type, 'in_use');
  assert.match(inUse.title, /занята/);

  // Неизвестная ошибка
  const unknown = Camera.formatCameraError(new Error('Unknown device fault'));
  assert.equal(unknown.type, 'unknown');
  assert.match(unknown.title, /Не удалось запустить/);
});

test('Practice module: toggleCheatsheet toggles visibility and updates attributes', () => {
  const dom = {
    practiceCheatsheetContent: { style: { display: 'none' } },
    btnPracticeCheatsheetToggle: {
      setAttribute(k, v) { this[k] = v; },
      querySelector() { return dom.practiceCheatsheetArrow; },
    },
    practiceCheatsheetArrow: { textContent: '▾' },
  };

  // 1. Раскрыть шпаргалку
  const openResult = Practice.toggleCheatsheet(dom);
  assert.equal(openResult, true);
  assert.equal(dom.practiceCheatsheetContent.style.display, 'block');
  assert.equal(dom.btnPracticeCheatsheetToggle['aria-expanded'], 'true');
  assert.equal(dom.practiceCheatsheetArrow.textContent, '▴');

  // 2. Свернуть шпаргалку
  const closeResult = Practice.toggleCheatsheet(dom);
  assert.equal(closeResult, false);
  assert.equal(dom.practiceCheatsheetContent.style.display, 'none');
  assert.equal(dom.btnPracticeCheatsheetToggle['aria-expanded'], 'false');
  assert.equal(dom.practiceCheatsheetArrow.textContent, '▾');
});

test('Warmup module: createWarmupState and toggleWarmupCheatsheet', () => {
  const ws = Warmup.createWarmupState();
  assert.equal(ws.isActive, false);
  assert.equal(ws.currentIndex, 0);
  assert.equal(ws.holdProgress, 0);
  assert.equal(ws.isFinished, false);

  const dom = {
    warmupCheatsheetContent: { style: { display: 'none' } },
    btnWarmupCheatsheetToggle: {
      setAttribute(k, v) { this[k] = v; },
      querySelector() { return dom.warmupCheatsheetArrow; },
    },
    warmupCheatsheetArrow: { textContent: '▾' },
  };

  const openRes = Warmup.toggleWarmupCheatsheet(dom);
  assert.equal(openRes, true);
  assert.equal(dom.warmupCheatsheetContent.style.display, 'block');
  assert.equal(dom.warmupCheatsheetArrow.textContent, '▴');

  const closeRes = Warmup.toggleWarmupCheatsheet(dom);
  assert.equal(closeRes, false);
  assert.equal(dom.warmupCheatsheetContent.style.display, 'none');
  assert.equal(dom.warmupCheatsheetArrow.textContent, '▾');
});

test('Warmup module: handleWarmupPrediction advances holdProgress and triggers step completion', () => {
  const state = {
    warmup: {
      isActive: true,
      gestures: [
        { name: 'привет', title: 'Привет', tip: 'Ладонь вперёд' },
        { name: 'спасибо', title: 'Спасибо', tip: 'Поклон ладонью' },
      ],
      currentIndex: 0,
      holdProgress: 0,
      holdTarget: 1.0,
      advanceTimer: null,
      streak: 2,
    },
    cameraTarget: 'warmup',
  };

  const dom = {
    warmupHudGesture: {},
    warmupHudScore: {},
    warmupHoldFill: { style: {} },
    warmupCanvas: { parentElement: { classList: { add() {}, remove() {} } } },
    warmupQuestionSuccess: { style: {} },
  };

  let speechCalled = false;
  Warmup.handleWarmupPrediction(
    { gesture: 'привет', confidence: 94 },
    1000,
    1.0, // delta >= holdTarget
    state,
    dom,
    {
      playSpeech: () => { speechCalled = true; },
    }
  );

  assert.equal(state.warmup.holdProgress, 1.0);
  assert.equal(dom.warmupHudGesture.textContent, 'привет');
  assert.match(dom.warmupHudScore.textContent, /94%/);
  assert.ok(state.warmup.advanceTimer !== null, 'advanceTimer must be set after step completion');

  // Очищаем таймер, чтобы не висел в фоне
  clearTimeout(state.warmup.advanceTimer);
});

test('HTML & PWA Integration: index.html contains all new UI components', () => {
  const indexPath = path.resolve(__dirname, '../src/project_omilia/frontend/index.html');
  assert.ok(fs.existsSync(indexPath), 'index.html must exist');
  const html = fs.readFileSync(indexPath, 'utf8');

  // US-1: Daily warmup
  assert.ok(html.includes('id="warmup-modal"'), 'warmup-modal must exist');
  assert.ok(html.includes('id="btn-header-warmup"'), 'btn-header-warmup must exist in header');
  assert.ok(html.includes('id="catalog-warmup-card"'), 'catalog-warmup-card must exist in catalog');
  assert.ok(html.includes('id="btn-catalog-warmup"'), 'btn-catalog-warmup must exist');
  assert.ok(html.includes('/static/modules/warmup.js'), 'warmup.js script tag must be included');

  // US-2: Onboarding
  assert.ok(html.includes('id="onboarding-modal"'), 'onboarding-modal must exist');
  assert.ok(html.includes('id="btn-header-guide"'), 'btn-header-guide must exist in header');
  assert.ok(html.includes('id="btn-hero-guide"'), 'btn-hero-guide must exist in hero');
  assert.ok(html.includes('onboarding-step-1'), 'onboarding step 1 must exist');
  assert.ok(html.includes('onboarding-step-2'), 'onboarding step 2 must exist');
  assert.ok(html.includes('onboarding-step-3'), 'onboarding step 3 must exist');

  // US-3: Gesture cheatsheet
  assert.ok(html.includes('id="practice-cheatsheet-wrapper"'), 'practice-cheatsheet-wrapper must exist');
  assert.ok(html.includes('id="btn-practice-cheatsheet-toggle"'), 'btn-practice-cheatsheet-toggle must exist');
  assert.ok(html.includes('id="practice-cheatsheet-content"'), 'practice-cheatsheet-content must exist');

  // US-6: XP & Rank
  assert.ok(html.includes('id="stat-xp-count"'), 'stat-xp-count must exist');
  assert.ok(html.includes('id="profile-xp-card"'), 'profile-xp-card must exist');
  assert.ok(html.includes('id="profile-xp-bar"'), 'profile-xp-bar must exist');
});

test('Service Worker: sw.js caches warmup.js and has omilia-pwa-v4 with Network-First strategy', () => {
  const swPath = path.resolve(__dirname, '../src/project_omilia/frontend/sw.js');
  const swContent = fs.readFileSync(swPath, 'utf8');
  assert.ok(swContent.includes('/static/modules/warmup.js'), 'sw.js must pre-cache warmup.js');
  assert.ok(swContent.includes("CACHE_NAME = 'omilia-pwa-v4'"), 'sw.js must use omilia-pwa-v4 cache name');
  assert.ok(swContent.includes('skipWaiting()'), 'sw.js must skip waiting on install');
  assert.ok(swContent.includes('clients.claim()'), 'sw.js must claim clients on activate');
});

test('HTML Video attributes: warmup, practice, and blitz video elements include autoplay, muted, and playsinline', () => {
  const indexPath = path.resolve(__dirname, '../src/project_omilia/frontend/index.html');
  const html = fs.readFileSync(indexPath, 'utf8');
  for (const id of ['warmup-video', 'practice-video', 'blitz-video']) {
    const match = html.match(new RegExp(`<video\\s+id="${id}"([^>]*)>`, 'i'));
    assert.ok(match, `Element #${id} must exist`);
    const attrs = match[1];
    assert.ok(attrs.includes('autoplay'), `#${id} must have autoplay`);
    assert.ok(attrs.includes('muted'), `#${id} must have muted`);
    assert.ok(attrs.includes('playsinline'), `#${id} must have playsinline`);
  }
});
