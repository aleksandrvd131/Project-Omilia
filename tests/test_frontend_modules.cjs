const test = require('node:test');
const assert = require('node:assert/strict');

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
  const lvl1 = ['а', 'б', 'в', 'г', 'д', 'е', 'и', 'о', 'с', 'у'];
  const lvl2 = ['1', '2', '3', '4', '5'];
  const lvl3 = ['привет', 'спасибо', 'помоги', 'пожалуйста', 'да', 'нет', 'мир', 'хорошо'];
  const lvl4 = ['дом', 'мама', 'папа', 'семья', 'любовь', 'стоп', 'книга', 'я', 'ты'];

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
  const lvl1 = ['а', 'б', 'в', 'г', 'д', 'е', 'и', 'о', 'с', 'у'];
  const lvl2 = ['1', '2', '3', '4', '5'];
  const lvl3 = ['привет', 'спасибо', 'помоги', 'пожалуйста', 'да', 'нет', 'мир', 'хорошо'];
  const lvl4 = ['дом', 'мама', 'папа', 'семья', 'любовь', 'стоп', 'книга', 'я', 'ты'];

  const mockGestures = [
    ...lvl1.map((n, i) => ({ name: n, is_learned: i < 7 })), // 7/10 = 70% learned
    ...lvl2.map((n) => ({ name: n, is_learned: false })),
    ...lvl3.map((n) => ({ name: n, is_learned: false })),
    ...lvl4.map((n) => ({ name: n, is_learned: false })),
  ];

  const stats = Catalog.calculateLevelStats(mockGestures);
  assert.equal(stats[1].total, 10);
  assert.equal(stats[1].learned, 7);
  assert.equal(stats[1].percentage, 70);
  assert.equal(stats[1].isUnlocked, true);

  assert.equal(stats[2].total, 5);
  assert.equal(stats[2].isUnlocked, true); // Level 1 is >= 70%, unlocking Level 2

  assert.equal(stats[3].total, 8);
  assert.equal(stats[3].isUnlocked, false); // Level 2 is 0%, Level 3 remains locked

  assert.equal(stats[4].total, 9);
  assert.equal(stats[4].isUnlocked, false);
});
