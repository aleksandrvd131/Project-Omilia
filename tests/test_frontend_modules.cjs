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

    // 4. openPracticeModal загружает силуэт для статического жеста
    const stateStatic = { practice: {} };
    Practice.openPracticeModal({ name: 'мир', is_dynamic: false }, stateStatic, dom);
    await new Promise((r) => setTimeout(r, 20));
    assert.ok(stateStatic.practice.ghostSilhouette);
    assert.equal(stateStatic.practice.ghostSilhouette[0].length, 21);

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
