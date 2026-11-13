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

  const GHOST_FINGER_CONNECTIONS = [
    [[0, 1], [1, 2], [2, 3], [3, 4]],         // Большой: 0->1->2->3->4
    [[0, 5], [5, 6], [6, 7], [7, 8]],         // Указательный: 0->5->6->7->8
    [[9, 10], [10, 11], [11, 12]],            // Средний: 9->10->11->12
    [[13, 14], [14, 15], [15, 16]],           // Безымянный: 13->14->15->16
    [[17, 18], [18, 19], [19, 20]],           // Мизинец: 17->18->19->20
  ];
  const GHOST_PALM_CONNECTIONS = [
    [0, 5], [5, 9], [9, 13], [13, 17], [0, 17]
  ];

  function checkHandAlignment(userLandmarks, ghostLandmarks, threshold = 0.16) {
    if (!userLandmarks || !ghostLandmarks || userLandmarks.length < 21 || ghostLandmarks.length < 21) {
      return false;
    }
    // 1. Прямая дистанция между точками
    let directDist = 0;
    for (let i = 0; i < 21; i++) {
      directDist += Math.hypot(userLandmarks[i].x - ghostLandmarks[i].x, userLandmarks[i].y - ghostLandmarks[i].y);
    }
    const avgDirectDist = directDist / 21;
    if (avgDirectDist < threshold) return true;

    // 2. Относительное совпадение формы кисти (инвариантное к смещению руки в кадре)
    const uWrist = userLandmarks[0];
    const gWrist = ghostLandmarks[0];
    let shapeDiff = 0;
    for (let i = 1; i < 21; i++) {
      const udx = userLandmarks[i].x - uWrist.x;
      const udy = userLandmarks[i].y - uWrist.y;
      const gdx = ghostLandmarks[i].x - gWrist.x;
      const gdy = ghostLandmarks[i].y - gWrist.y;
      shapeDiff += Math.hypot(udx - gdx, udy - gdy);
    }
    const avgShapeDiff = shapeDiff / 20;
    return avgShapeDiff < 0.12;
  }

  function drawGhostSilhouette(ctx, ghostData, width, height, options = {}) {
    if (!ctx || !ghostData) return;

    let handsList = [];
    if (Array.isArray(ghostData) && ghostData.length > 0) {
      if (Array.isArray(ghostData[0])) {
        handsList = ghostData;
      } else if (ghostData.length >= 21 && typeof ghostData[0].x === 'number') {
        handsList = [ghostData];
      }
    }
    if (handsList.length === 0) return;

    const userHands = options.userHands || [];
    const isGlobalMatch = Boolean(options.isMatch);

    for (let hIdx = 0; hIdx < handsList.length; hIdx++) {
      const hand = handsList[hIdx];
      if (!hand || hand.length < 21) continue;

      let isAligned = isGlobalMatch;
      if (!isAligned && userHands.length > 0) {
        const targetUserHand = userHands[hIdx] || userHands[0];
        if (targetUserHand && checkHandAlignment(targetUserHand, hand)) {
          isAligned = true;
        }
      }

      ctx.save();

      // Элегантная цветовая гамма: полупрозрачный циан/белый с мягким свечением, либо ярко-зеленый при совпадении
      const boneColor = isAligned ? 'rgba(34, 197, 94, 0.90)' : 'rgba(56, 189, 248, 0.45)';
      const glowColor = isAligned ? 'rgba(34, 197, 94, 0.95)' : 'rgba(186, 230, 253, 0.65)';
      const jointColor = isAligned ? 'rgba(74, 222, 128, 0.95)' : 'rgba(240, 249, 255, 0.75)';
      const lineWidth = isAligned ? 3.5 : 2.5;
      const shadowBlur = isAligned ? 14 : 9;
      const jointRadius = isAligned ? 4.5 : 3.5;

      ctx.strokeStyle = boneColor;
      ctx.lineWidth = lineWidth;
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = shadowBlur;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // 1. Отрисовка основания ладони
      ctx.beginPath();
      for (const [startIdx, endIdx] of GHOST_PALM_CONNECTIONS) {
        const p1 = hand[startIdx];
        const p2 = hand[endIdx];
        ctx.moveTo(p1.x * width, p1.y * height);
        ctx.lineTo(p2.x * width, p2.y * height);
      }
      ctx.stroke();

      // 2. Отрисовка костей пальцев (0->1->2->3->4, 0->5->6->7->8, и т.д.)
      ctx.beginPath();
      for (let f = 0; f < 5; f++) {
        for (const [startIdx, endIdx] of GHOST_FINGER_CONNECTIONS[f]) {
          const p1 = hand[startIdx];
          const p2 = hand[endIdx];
          ctx.moveTo(p1.x * width, p1.y * height);
          ctx.lineTo(p2.x * width, p2.y * height);
        }
      }
      ctx.stroke();

      // 3. Полупрозрачная заливка основания ладони для объёма силуэта
      ctx.fillStyle = isAligned ? 'rgba(34, 197, 94, 0.08)' : 'rgba(56, 189, 248, 0.06)';
      ctx.beginPath();
      ctx.moveTo(hand[0].x * width, hand[0].y * height);
      ctx.lineTo(hand[5].x * width, hand[5].y * height);
      ctx.lineTo(hand[9].x * width, hand[9].y * height);
      ctx.lineTo(hand[13].x * width, hand[13].y * height);
      ctx.lineTo(hand[17].x * width, hand[17].y * height);
      ctx.closePath();
      ctx.fill();

      // 4. Отрисовка суставов (точек MediaPipe)
      ctx.fillStyle = jointColor;
      ctx.shadowBlur = shadowBlur / 2;
      for (let i = 0; i < hand.length; i++) {
        const p = hand[i];
        ctx.beginPath();
        ctx.arc(p.x * width, p.y * height, jointRadius, 0, 2 * Math.PI);
        ctx.fill();
      }

      ctx.restore();
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

    const videoEl = target === 'practice' ? dom?.practiceVideo : dom?.blitzVideo;
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
      const activeFacingMode = getFacingMode(state);
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
        facingMode: activeFacingMode,
        frameRate: {
          max: 30,
          ideal: 24,
        },
      });

      state.isCameraRunning = true;
      state.camera.start();
    }
  }

  let currentFacingMode = 'user';

  function getFacingMode(state) {
    return state?.facingMode || currentFacingMode;
  }

  function setFacingMode(mode, state) {
    if (mode === 'user' || mode === 'environment') {
      currentFacingMode = mode;
      if (state) {
        state.facingMode = mode;
      }
    }
    return currentFacingMode;
  }

  async function getAvailableVideoInputs() {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.enumerateDevices) {
      return null;
    }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices.filter((d) => d.kind === 'videoinput');
    } catch {
      return null;
    }
  }

  async function switchCamera(state, dom, callbacks = {}) {
    const videoInputs = await getAvailableVideoInputs();
    if (videoInputs && videoInputs.length <= 1) {
      console.info('Only one video input detected; camera switch skipped.');
      return getFacingMode(state);
    }

    const currentMode = getFacingMode(state);
    const nextMode = currentMode === 'user' ? 'environment' : 'user';
    setFacingMode(nextMode, state);

    if (dom) {
      const targetCanvas =
        state?.cameraTarget === 'blitz' ? dom.blitzCanvas : dom.practiceCanvas || dom.blitzCanvas;
      const container =
        targetCanvas?.parentElement ||
        dom.cameraContainer ||
        (typeof document !== 'undefined' ? document.querySelector('.camera-container') : null);
      if (container && container.classList) {
        if (nextMode === 'environment') {
          container.classList.remove('mirrored');
        } else {
          container.classList.add('mirrored');
        }
      }
    }

    if (state && state.isCameraRunning && state.cameraTarget) {
      const target = state.cameraTarget;
      stopCamera(state);
      startCamera(target, state, dom, callbacks);
    }

    return nextMode;
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
    drawGhostSilhouette,
    checkHandAlignment,
    initMediaPipe,
    startCamera,
    stopCamera,
    getFacingMode,
    setFacingMode,
    switchCamera,
  };
});
