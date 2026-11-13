/**
 * Project Omiλia — Camera & MediaPipe Module
 * Инициализация MediaPipe Hands/Pose, захват веб-камеры и отрисовка скелета рук.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Omilia = root.Omilia || {};
    root.Omilia.Camera = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function compactLandmarks(landmarks) {
    if (!landmarks) return null;
    return landmarks.map((p) => ({
      x: Math.round(p.x * 10000) / 10000,
      y: Math.round(p.y * 10000) / 10000,
      z: Math.round((p.z || 0) * 10000) / 10000,
    }));
  }

  function drawHandLandmarks(ctx, landmarks, width, height, options = {}) {
    if (!ctx || !landmarks || landmarks.length < 21) return;

    const fingerConnections = [
      [[0, 1], [1, 2], [2, 3], [3, 4]],         // Большой (палец 0)
      [[0, 5], [5, 6], [6, 7], [7, 8]],         // Указательный (палец 1)
      [[5, 9], [9, 10], [10, 11], [11, 12]],    // Средний (палец 2)
      [[9, 13], [13, 14], [14, 15], [15, 16]],  // Безымянный (палец 3)
      [[13, 17], [17, 18], [18, 19], [19, 20]], // Мизинец (палец 4)
    ];
    const palmBase = [0, 17];

    const isMatch = Boolean(options.isMatch);
    const problemFingers = options.problemFingers || [];

    // 1. Отрисовка основания ладони
    ctx.lineWidth = 3;
    ctx.strokeStyle = isMatch ? '#10b981' : '#38bdf8';
    ctx.beginPath();
    ctx.moveTo(landmarks[palmBase[0]].x * width, landmarks[palmBase[0]].y * height);
    ctx.lineTo(landmarks[palmBase[1]].x * width, landmarks[palmBase[1]].y * height);
    ctx.stroke();

    // 2. Отрисовка каждого пальца с биометрической подсветкой
    for (let f = 0; f < 5; f++) {
      const isProblem = problemFingers.includes(f);
      if (isMatch) {
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 3.5;
      } else if (isProblem) {
        ctx.strokeStyle = '#f59e0b'; // Янтарный цвет для пальца, требующего корректировки
        ctx.lineWidth = 4.5;
      } else {
        ctx.strokeStyle = '#38bdf8'; // Небесно-голубой по умолчанию
        ctx.lineWidth = 3;
      }

      ctx.beginPath();
      for (const [startIdx, endIdx] of fingerConnections[f]) {
        const p1 = landmarks[startIdx];
        const p2 = landmarks[endIdx];
        ctx.moveTo(p1.x * width, p1.y * height);
        ctx.lineTo(p2.x * width, p2.y * height);
      }
      ctx.stroke();
    }

    // 3. Отрисовка суставов (точек)
    for (let i = 0; i < landmarks.length; i++) {
      const p = landmarks[i];
      let fIdx = -1;
      if (i >= 1 && i <= 4) fIdx = 0;
      else if (i >= 5 && i <= 8) fIdx = 1;
      else if (i >= 9 && i <= 12) fIdx = 2;
      else if (i >= 13 && i <= 16) fIdx = 3;
      else if (i >= 17 && i <= 20) fIdx = 4;

      const isProblem = fIdx >= 0 && problemFingers.includes(fIdx);

      if (isMatch) {
        ctx.fillStyle = '#34d399';
      } else if (isProblem) {
        ctx.fillStyle = '#fbbf24';
      } else {
        ctx.fillStyle = '#7dd3fc';
      }

      ctx.beginPath();
      ctx.arc(p.x * width, p.y * height, isProblem ? 5.5 : 4.0, 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  function initMediaPipe(state, getExpectedHandsCount) {
    if (state.mediaPipeHands && state.mediaPipePose) return;

    if (typeof Hands !== 'undefined' && !state.mediaPipeHands) {
      state.mediaPipeHands = new Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
      });

      state.mediaPipeHands.setOptions({
        maxNumHands: 2,
        modelComplexity: 1,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });

      state.mediaPipeHands.onResults((results) => {
        let rawHands = results.multiHandLandmarks || [];
        const expectedHands = getExpectedHandsCount ? getExpectedHandsCount() : 1;
        if (expectedHands === 1) {
          state.latestHands = rawHands.slice(0, 1);
        } else {
          if (rawHands.length >= 2) {
            const h0 = rawHands[0];
            const h1 = rawHands[1];
            const distWrist = Math.hypot(h0[0].x - h1[0].x, h0[0].y - h1[0].y);
            if (distWrist < 0.08) {
              rawHands = [h0];
            }
          }
          state.latestHands = rawHands.slice(0, 2);
        }
      });
    }

    if (typeof Pose !== 'undefined' && !state.mediaPipePose) {
      state.mediaPipePose = new Pose({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
      });

      state.mediaPipePose.setOptions({
        modelComplexity: 0,
        smoothLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });

      state.mediaPipePose.onResults((results) => {
        state.latestPose = results.poseLandmarks || null;
      });
    }
  }

  function startCamera(target, state, dom, callbacks = {}) {
    state.cameraTarget = target;
    const { getExpectedHandsCount, onFrameRender, ensureWebSocket } = callbacks;

    if (ensureWebSocket) ensureWebSocket();
    initMediaPipe(state, getExpectedHandsCount);

    const videoEl = target === 'practice' ? dom.practiceVideo : dom.blitzVideo;
    if (!videoEl || !state.mediaPipeHands) return;

    if (state.camera) {
      state.camera.stop();
      state.camera = null;
    }

    const targetHands = getExpectedHandsCount ? getExpectedHandsCount() : 1;
    state.mediaPipeHands.setOptions({ maxNumHands: targetHands });

    let lastAnalysisAt = 0;
    let lastPoseAt = 0;
    const ANALYSIS_INTERVAL_MS = 1000 / 24; // ~41.67 ms (~24 FPS)
    const POSE_INTERVAL_MS = 250;           // раз в 0.25 с (250 мс)

    if (typeof Camera !== 'undefined') {
      state.camera = new Camera(videoEl, {
        onFrame: async () => {
          if (state.isCameraRunning && state.cameraTarget) {
            const capturedAt = performance.now();
            if (capturedAt - lastAnalysisAt < ANALYSIS_INTERVAL_MS) {
              return;
            }
            lastAnalysisAt = capturedAt;

            const attempt = state.dynamicAttempt;
            const elapsed = attempt?.startedAt == null ? -1 : capturedAt - attempt.startedAt;
            const clipDuration = window.omiliaDynamicClip?.durationMs || 1000;
            const capturing = elapsed >= 0 && elapsed < clipDuration;

            if (state.mediaPipeHands) {
              await state.mediaPipeHands.send({ image: videoEl });
            }
            if (state.mediaPipePose && (!state.latestPose || (capturedAt - lastPoseAt >= POSE_INTERVAL_MS))) {
              lastPoseAt = capturedAt;
              await state.mediaPipePose.send({ image: videoEl });
            }
            if (capturing && state.dynamicAttempt === attempt && !attempt.awaitingResult) {
              attempt.frames.push({
                t_ms: elapsed,
                hands_data: structuredClone(state.latestHands),
                pose_landmarks: structuredClone(state.latestPose),
              });
            }
            if (onFrameRender) onFrameRender();
          }
        },
        width: 640,
        height: 480,
        frameRate: {
          max: 30,
          ideal: 24,
        },
      });

      state.isCameraRunning = true;
      state.camera.start();
    }
  }

  function stopCamera(state) {
    state.dynamicAttempt = null;
    if (state.blitz && state.blitz.advanceTimer !== null) {
      clearTimeout(state.blitz.advanceTimer);
      state.blitz.advanceTimer = null;
    }
    state.isCameraRunning = false;
    if (state.camera) {
      state.camera.stop();
      state.camera = null;
    }
    state.latestHands = [];
    state.latestPose = null;
    state.cameraTarget = null;
  }

  return {
    compactLandmarks,
    drawHandLandmarks,
    initMediaPipe,
    startCamera,
    stopCamera,
  };
});
