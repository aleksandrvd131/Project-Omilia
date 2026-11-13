const test = require('node:test');
const assert = require('node:assert/strict');

const UI = require('../src/project_omilia/frontend/modules/ui.js');
const Camera = require('../src/project_omilia/frontend/modules/camera.js');
const Socket = require('../src/project_omilia/frontend/modules/socket.js');
const Practice = require('../src/project_omilia/frontend/modules/practice.js');
const Blitz = require('../src/project_omilia/frontend/modules/blitz.js');

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
