/**
 * Project Omiλia — Frontend Application Coordinator
 * Модульная архитектура: координирует UI, Catalog, Camera, Socket, Practice и Blitz.
 */

(function () {
  'use strict';

  // --- Состояние приложения ---
  const state = {
    classifier: null,
    authToken: localStorage.getItem('omilia_token') || null,
    currentUser: null,
    settings: {
      ttsEnabled: localStorage.getItem('omilia_tts') !== 'false',
    },
    gestures: [],
    activeTab: 'about',

    // Состояние практики (Шаг 2 обучения)
    practice: {
      gesture: null,
      holdProgress: 0,
      holdTarget: 1.5,
      isLearned: false,
      lastTimestamp: null,
      ghostSilhouette: null,
    },

    // Состояние блиц-опроса
    blitz: {
      questions: [],
      currentIndex: 0,
      holdProgress: 0,
      holdTarget: 1.5,
      advanceTimer: null,
      lastTimestamp: null,
      isActive: false,
    },

    // Состояние ежедневной разминки (SM-2 SRS, US-1)
    warmup: {
      isActive: false,
      gestures: [],
      currentIndex: 0,
      holdProgress: 0,
      holdTarget: 1.5,
      lastTimestamp: null,
      advanceTimer: null,
      isFinished: false,
      streak: 0,
    },

    dynamicAttempt: null,

    // Камера и распознавание
    camera: null,
    cameraTarget: null, // 'practice', 'blitz' или 'warmup'
    facingMode: 'user', // 'user' или 'environment'
    currentProblemFingers: [],
    isMatchingGesture: false,
    mediaPipeHands: null,
    mediaPipePose: null,
    latestHands: [],
    latestPose: null,
    isCameraRunning: false,
  };

  let nextDynamicAttemptId = 0;

  // --- Селекторы элементов DOM ---
  const dom = {
    brandLink: document.getElementById('brand-link'),
    navBtns: document.querySelectorAll('.nav-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    headerUserArea: document.getElementById('header-user-area'),
    btnHeaderLogin: document.getElementById('btn-header-login'),
    btnHeaderWarmup: document.getElementById('btn-header-warmup'),
    btnHeaderGuide: document.getElementById('btn-header-guide'),

    // Главная
    btnHeroStart: document.getElementById('btn-hero-start'),
    btnHeroWarmup: document.getElementById('btn-hero-warmup'),
    btnHeroGuide: document.getElementById('btn-hero-guide'),
    btnHeroLk: document.getElementById('btn-hero-lk'),
    contactForm: document.getElementById('contact-form'),
    contactSuccess: document.getElementById('contact-success'),

    // Каталог
    gesturesGrid: document.getElementById('gestures-grid'),
    catalogLearnedCounter: document.getElementById('catalog-learned-counter'),
    catalogWarmupCard: document.getElementById('catalog-warmup-card'),
    btnCatalogWarmup: document.getElementById('btn-catalog-warmup'),
    catalogSearch: document.getElementById('catalog-search'),
    btnClearSearch: document.getElementById('btn-clear-search'),
    categoryFilters: document.getElementById('category-filters'),

    // ЛК
    authBox: document.getElementById('auth-box'),
    profileBox: document.getElementById('profile-box'),
    authTabLogin: document.getElementById('auth-tab-login'),
    authTabRegister: document.getElementById('auth-tab-register'),
    formLogin: document.getElementById('form-login'),
    formRegister: document.getElementById('form-register'),
    loginError: document.getElementById('login-error'),
    regError: document.getElementById('reg-error'),
    profileUsername: document.getElementById('profile-username'),
    profileRankBadge: document.getElementById('profile-rank-badge'),
    statLearnedCount: document.getElementById('stat-learned-count'),
    statTotalCount: document.getElementById('stat-total-count'),
    statPercentCount: document.getElementById('stat-percent-count'),
    statXpCount: document.getElementById('stat-xp-count'),
    profileProgressBar: document.getElementById('profile-progress-bar'),
    profileProgressText: document.getElementById('profile-progress-text'),
    profileXpBar: document.getElementById('profile-xp-bar'),
    profileXpText: document.getElementById('profile-xp-text'),
    profileXpSummary: document.getElementById('profile-xp-summary'),
    profileStatsSummary: document.getElementById('profile-stats-summary'),
    profileLearnedBadges: document.getElementById('profile-learned-badges'),
    ttsToggle: document.getElementById('tts-toggle'),
    btnLogout: document.getElementById('btn-logout'),

    // Блиц
    blitzIntro: document.getElementById('blitz-intro'),
    blitzActive: document.getElementById('blitz-active'),
    blitzFinish: document.getElementById('blitz-finish'),
    blitzFinishDesc: document.getElementById('blitz-finish-desc'),
    blitzEligibility: document.getElementById('blitz-eligibility'),
    btnStartBlitz: document.getElementById('btn-start-blitz'),
    blitzProgressStep: document.getElementById('blitz-progress-step'),
    blitzTargetTitle: document.getElementById('blitz-target-title'),
    blitzTargetTip: document.getElementById('blitz-target-tip'),
    blitzVideo: document.getElementById('blitz-video'),
    blitzCanvas: document.getElementById('blitz-canvas'),
    blitzHudGesture: document.getElementById('blitz-hud-gesture'),
    blitzHudScore: document.getElementById('blitz-hud-score'),
    blitzDiagnosticHint: document.getElementById('blitz-diagnostic-hint'),
    blitzHoldFill: document.getElementById('blitz-hold-fill'),
    blitzAttemptStatus: document.getElementById('blitz-attempt-status'),
    btnDynamicBlitz: document.getElementById('btn-dynamic-blitz'),
    blitzQuestionSuccess: document.getElementById('blitz-question-success'),
    btnAbortBlitz: document.getElementById('btn-abort-blitz'),
    btnRepeatBlitz: document.getElementById('btn-repeat-blitz'),
    btnBlitzToCatalog: document.getElementById('btn-blitz-to-catalog'),

    // Модальное окно 1: Обучение
    tutorialModal: document.getElementById('tutorial-modal'),
    tutorialTitle: document.getElementById('tutorial-title'),
    tutorialCategory: document.getElementById('tutorial-category'),
    tutorialDesc: document.getElementById('tutorial-desc'),
    tutorialTip: document.getElementById('tutorial-tip'),
    tutorialVideo: document.getElementById('tutorial-video'),
    tutorialVideoFallback: document.getElementById('tutorial-video-fallback'),
    btnCloseTutorial: document.getElementById('btn-close-tutorial'),
    btnStartCameraPractice: document.getElementById('btn-start-camera-practice'),

    // Модальное окно 2: Практика
    practiceModal: document.getElementById('practice-modal'),
    practiceTitle: document.getElementById('practice-title'),
    practiceTipText: document.getElementById('practice-tip-text'),
    btnDynamicPractice: document.getElementById('btn-dynamic-practice'),
    practiceVideo: document.getElementById('practice-video'),
    practiceCanvas: document.getElementById('practice-canvas'),
    practiceHudGesture: document.getElementById('practice-hud-gesture'),
    practiceHudScore: document.getElementById('practice-hud-score'),
    practiceHoldFill: document.getElementById('practice-hold-fill'),
    practiceDiagnosticHint: document.getElementById('practice-diagnostic-hint'),
    practiceSuccessOverlay: document.getElementById('practice-success-overlay'),
    practiceSuccessMsg: document.getElementById('practice-success-msg'),
    btnPracticeDone: document.getElementById('btn-practice-done'),
    btnClosePracticeModal: document.getElementById('btn-close-practice-modal'),
    btnPracticeCancel: document.getElementById('btn-practice-cancel'),

    // Шпаргалка практики (US-3)
    btnPracticeCheatsheetToggle: document.getElementById('btn-practice-cheatsheet-toggle'),
    practiceCheatsheetContent: document.getElementById('practice-cheatsheet-content'),
    practiceCheatsheetDesc: document.getElementById('practice-cheatsheet-desc'),
    practiceCheatsheetTip: document.getElementById('practice-cheatsheet-tip'),
    practiceCheatsheetArrow: document.getElementById('practice-cheatsheet-arrow'),

    // Модальное окно 3: Разминка (US-1)
    warmupModal: document.getElementById('warmup-modal'),
    warmupActiveCard: document.getElementById('warmup-active-card'),
    warmupProgressStep: document.getElementById('warmup-progress-step'),
    warmupTargetTitle: document.getElementById('warmup-target-title'),
    warmupTargetTip: document.getElementById('warmup-target-tip'),
    warmupVideo: document.getElementById('warmup-video'),
    warmupCanvas: document.getElementById('warmup-canvas'),
    warmupHudGesture: document.getElementById('warmup-hud-gesture'),
    warmupHudScore: document.getElementById('warmup-hud-score'),
    warmupDiagnosticHint: document.getElementById('warmup-diagnostic-hint'),
    warmupHoldFill: document.getElementById('warmup-hold-fill'),
    warmupQuestionSuccess: document.getElementById('warmup-question-success'),
    warmupFinishOverlay: document.getElementById('warmup-finish-overlay'),
    warmupFinishStreakCount: document.getElementById('warmup-finish-streak-count'),
    warmupFinishDesc: document.getElementById('warmup-finish-desc'),
    btnWarmupDone: document.getElementById('btn-warmup-done'),
    btnCloseWarmupModal: document.getElementById('btn-close-warmup-modal'),
    btnAbortWarmup: document.getElementById('btn-abort-warmup'),
    btnWarmupCheatsheetToggle: document.getElementById('btn-warmup-cheatsheet-toggle'),
    warmupCheatsheetContent: document.getElementById('warmup-cheatsheet-content'),
    warmupCheatsheetDesc: document.getElementById('warmup-cheatsheet-desc'),
    warmupCheatsheetTip: document.getElementById('warmup-cheatsheet-tip'),
    warmupCheatsheetArrow: document.getElementById('warmup-cheatsheet-arrow'),

    // Модальное окно 4: Онбординг (US-2)
    onboardingModal: document.getElementById('onboarding-modal'),
    btnCloseOnboarding: document.getElementById('btn-close-onboarding'),
    btnOnboardingPrev: document.getElementById('btn-onboarding-prev'),
    btnOnboardingNext: document.getElementById('btn-onboarding-next'),
    onboardingStepCounter: document.getElementById('onboarding-step-counter'),
    onboardingDots: document.getElementById('onboarding-dots'),
  };

  const ui = window.Omilia?.UI;
  const catalog = window.Omilia?.Catalog;
  const socket = window.Omilia?.Socket;
  const camera = window.Omilia?.Camera;
  const practice = window.Omilia?.Practice;
  const blitz = window.Omilia?.Blitz;
  const warmup = window.Omilia?.Warmup;

  // --- Вспомогательные функции гестур ---
  function getCameraGesture() {
    if (state.cameraTarget === 'practice') return state.practice.gesture;
    if (state.cameraTarget === 'blitz' && state.blitz.isActive) {
      return state.blitz.questions[state.blitz.currentIndex];
    }
    if (state.cameraTarget === 'warmup' && state.warmup?.isActive) {
      return state.warmup.gestures[state.warmup.currentIndex];
    }
    return null;
  }
  }

  function getExpectedHandsCount() {
    const g = getCameraGesture();
    return g?.hands_count || g?.dynamic_hands_count || 1;
  }

  function getTargetGestureName() {
    const g = getCameraGesture();
    if (!g) return '';
    const name = g.gesture_name || g.name || '';
    return name.trim().toLowerCase();
  }

  // --- Навигация и профиль ---
  function switchTab(tabId) {
    ui.switchTab(tabId, state, dom, {
      onAbortBlitz: () => blitz.abortBlitz(state, dom, stopCamera),
      onLoadCatalog: () => catalog.loadCatalog(state, dom, openTutorialModal),
      onSetupBlitz: () => blitz.setupBlitzIntro(state, dom, switchTab),
      onUpdateProfile: () => ui.updateProfileView(state, dom, () => switchTab('catalog')),
    });
  }

  async function checkAuth() {
    if (!state.authToken) {
      ui.updateUserHeader(state, dom, () => switchTab('profile'));
      ui.updateProfileView(state, dom, () => switchTab('catalog'));
      return;
    }
    try {
      const data = await ui.apiFetch('/api/auth/me', {}, state.authToken);
      state.currentUser = {
        ...data.user,
        learned_gestures: data.learned_gestures || data.user?.learned_gestures || [],
      };
    } catch {
      state.authToken = null;
      localStorage.removeItem('omilia_token');
      state.currentUser = null;
    }
    ui.updateUserHeader(state, dom, () => switchTab('profile'));
    ui.updateProfileView(state, dom, () => switchTab('catalog'));
  }

  // --- Камера и Сокет ---
  function ensureWebSocket() {
    socket.ensureWebSocket({
      authToken: state.authToken,
      onMessage: handleServerPrediction,
      onClose: () => {
        if (state.dynamicAttempt) {
          endDynamicAttempt('Соединение прервалось. Начните попытку ещё раз.');
        }
      },
    });
  }

  function startCamera(target) {
    camera.startCamera(target, state, dom, {
      getExpectedHandsCount,
      onFrameRender,
      ensureWebSocket,
    });
  }

  function stopCamera() {
    camera.stopCamera(state);
  }

  function onFrameRender() {
    if (!state.isCameraRunning || !state.cameraTarget) return;

    let canvas, video;
    if (state.cameraTarget === 'practice') {
      canvas = dom.practiceCanvas;
      video = dom.practiceVideo;
    } else if (state.cameraTarget === 'warmup') {
      canvas = dom.warmupCanvas;
      video = dom.warmupVideo;
    } else {
      canvas = dom.blitzCanvas;
      video = dom.blitzVideo;
    }
    if (!canvas || !video) return;

    if (video.videoWidth && (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight)) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    const ctx = canvas.getContext('2d');
    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Отрисовка отслеживаемых рук пользователя (призрачный показ жестов отключён, чтобы не мешать обзору)
    const handsData = state.latestHands || [];
    for (const landmarks of handsData) {
      camera.drawHandLandmarks(ctx, landmarks, canvas.width, canvas.height, {
        isMatch: state.isMatchingGesture,
        problemFingers: state.currentProblemFingers,
      });
    }
    ctx.restore();

    if (getCameraGesture()?.dynamic_hands_count || state.blitz.advanceTimer !== null || state.warmup?.advanceTimer !== null) return;

    const expectedHands = getExpectedHandsCount();
    if (handsData.length === 0 || (expectedHands === 2 && handsData.length < 2)) {
      const waitMsg = (expectedHands === 2 && handsData.length === 1) ? 'Покажите обе руки' : 'Покажите руку';
      if (state.cameraTarget === 'practice' && !state.practice.isLearned) {
        if (dom.practiceHudGesture) dom.practiceHudGesture.textContent = '—';
        if (dom.practiceHudScore) dom.practiceHudScore.textContent = waitMsg;
      } else if (state.cameraTarget === 'warmup') {
        if (dom.warmupHudGesture) dom.warmupHudGesture.textContent = '—';
        if (dom.warmupHudScore) dom.warmupHudScore.textContent = waitMsg;
      } else if (state.cameraTarget === 'blitz' && state.blitz.isActive) {
        if (dom.blitzHudGesture) dom.blitzHudGesture.textContent = '—';
        if (dom.blitzHudScore) dom.blitzHudScore.textContent = waitMsg;
      }
      return;
    }

    let handsToSend = [];
    if (expectedHands === 1) {
      handsToSend = handsData.slice(0, 1).map(camera.compactLandmarks);
    } else {
      handsToSend = handsData.slice(0, 2).map(camera.compactLandmarks);
    }

    const targetGesture = getTargetGestureName();
    socket.sendPayload({
      token: state.authToken || localStorage.getItem('omilia_token') || '',
      hands_data: handsToSend,
      pose_landmarks: camera.compactLandmarks(state.latestPose),
      hands_count: expectedHands,
      target_gesture: targetGesture || undefined,
    });
  }

  // --- Обработка распознанного жеста ---
  function handleServerPrediction(pred) {
    if (pred.type === 'dynamic_clip') {
      handleDynamicResult(pred);
      return;
    }
    if (getCameraGesture()?.dynamic_hands_count || state.blitz.advanceTimer !== null || state.warmup?.advanceTimer !== null) return;

    const now = performance.now();
    const gestureName = pred.gesture || pred.name || '';
    const predictedName = gestureName.trim().toLowerCase();
    const targetName = getTargetGestureName();
    const isMatching = Boolean(targetName && predictedName === targetName);
    state.isMatchingGesture = isMatching;

    // Биометрическая диагностика и подсветка
    let hintEl;
    if (state.cameraTarget === 'practice') {
      hintEl = dom.practiceDiagnosticHint;
    } else if (state.cameraTarget === 'warmup') {
      hintEl = dom.warmupDiagnosticHint;
    } else {
      hintEl = dom.blitzDiagnosticHint;
    }

    if (hintEl) {
      if (isMatching) {
        hintEl.style.display = 'flex';
        hintEl.classList.add('matching');
        const icon = hintEl.querySelector('.diagnostic-hint-icon');
        const text = hintEl.querySelector('.diagnostic-hint-text');
        if (icon) icon.textContent = '✨';
        if (text) text.textContent = 'Поза правильная! Удерживайте...';
        state.currentProblemFingers = [];
      } else if (pred.diagnostics && pred.diagnostics.primary_hint) {
        hintEl.style.display = 'flex';
        hintEl.classList.remove('matching');
        const icon = hintEl.querySelector('.diagnostic-hint-icon');
        const text = hintEl.querySelector('.diagnostic-hint-text');
        if (icon) icon.textContent = '💡';
        if (text) text.textContent = pred.diagnostics.primary_hint;
        state.currentProblemFingers = pred.diagnostics.problem_fingers || [];
      } else {
        hintEl.style.display = 'none';
        state.currentProblemFingers = [];
      }
    }

    if (state.cameraTarget === 'practice') {
      const delta = state.practice.lastTimestamp ? (now - state.practice.lastTimestamp) / 1000 : 0.05;
      state.practice.lastTimestamp = now;
      practice.handlePracticePrediction(pred, now, delta, state, dom, {
        playSpeech: (text) => ui.playSpeech(text, state.settings.ttsEnabled),
        updateProfileView: () => ui.updateProfileView(state, dom, () => switchTab('catalog')),
      });
    } else if (state.cameraTarget === 'warmup') {
      const delta = state.warmup.lastTimestamp ? (now - state.warmup.lastTimestamp) / 1000 : 0.05;
      state.warmup.lastTimestamp = now;
      warmup.handleWarmupPrediction(pred, now, delta, state, dom, {
        playSpeech: (text) => ui.playSpeech(text, state.settings.ttsEnabled),
        onWarmupFinished: (streak) => {
          ui.updateUserHeader(state, dom, () => switchTab('profile'));
          ui.updateProfileView(state, dom, () => switchTab('catalog'));
        },
      });
    } else if (state.cameraTarget === 'blitz') {
      const delta = state.blitz.lastTimestamp ? (now - state.blitz.lastTimestamp) / 1000 : 0.05;
      state.blitz.lastTimestamp = now;
      blitz.handleBlitzPrediction(pred, now, delta, state, dom, {
        playSpeech: (text) => ui.playSpeech(text, state.settings.ttsEnabled),
      });
    }
  }

  // --- Динамические жесты (Клипы) ---
  function startDynamicAttempt() {
    const gesture = getCameraGesture();
    if (!gesture?.dynamic_hands_count || state.dynamicAttempt) return;

    const isBlitz = state.cameraTarget === 'blitz';
    if (isBlitz ? state.blitz.advanceTimer !== null : state.practice.isLearned) return;

    const video = isBlitz ? dom.blitzVideo : dom.practiceVideo;
    const controls = isBlitz
      ? { button: dom.btnDynamicBlitz, status: dom.blitzAttemptStatus, gesture: dom.blitzHudGesture, score: dom.blitzHudScore }
      : { button: dom.btnDynamicPractice, status: dom.practiceTipText, gesture: dom.practiceHudGesture, score: dom.practiceHudScore };

    if (!state.mediaPipeHands || !state.mediaPipePose || video.readyState < 2) {
      controls.status.textContent = 'Дождитесь запуска камеры.';
      return;
    }
    if (!socket.isOpen()) {
      ensureWebSocket();
      controls.status.textContent = 'Дождитесь подключения и начните попытку снова.';
      return;
    }

    const clip = window.omiliaDynamicClip;
    const attempt = {
      id: ++nextDynamicAttemptId,
      isBlitz,
      gesture,
      controls,
      startedAt: null,
      awaitingResult: false,
      frames: [],
    };
    state.dynamicAttempt = attempt;
    controls.button.disabled = true;
    controls.gesture.textContent = 'Готовьтесь';
    controls.score.textContent = '';

    function countdown(secondsLeft) {
      if (state.dynamicAttempt !== attempt) return;
      if (secondsLeft > 0) {
        controls.status.textContent = `Приготовьтесь: ${secondsLeft}…`;
        setTimeout(() => countdown(secondsLeft - 1), 1000);
        return;
      }

      attempt.startedAt = performance.now();
      controls.status.textContent = 'Покажите жест за одну секунду.';

      setTimeout(() => {
        if (state.dynamicAttempt !== attempt) return;
        try {
          const frames = clip.selectFrames(attempt.frames, gesture.dynamic_hands_count);
          if (!socket.isOpen()) {
            throw new Error('Соединение прервалось. Повторите попытку.');
          }
          socket.sendRaw({
            type: 'dynamic_clip',
            mode: 'practice',
            attempt_id: attempt.id,
            label: gesture.name ?? gesture.gesture_name,
            hands_count: gesture.dynamic_hands_count,
            frames,
          });
        } catch (error) {
          endDynamicAttempt(error.message);
          return;
        }

        attempt.awaitingResult = true;
        controls.status.textContent = 'Проверяем жест…';
        setTimeout(() => {
          if (state.dynamicAttempt === attempt) {
            endDynamicAttempt('Сервер не ответил. Повторите попытку.');
          }
        }, 5000);
      }, (clip?.durationMs || 1000) + 100);
    }

    countdown(clip?.prepSeconds || 3);
  }

  function endDynamicAttempt(message) {
    if (!state.dynamicAttempt) return;
    const { controls } = state.dynamicAttempt;
    state.dynamicAttempt = null;
    controls.button.disabled = false;
    controls.status.textContent = message;
  }

  function handleDynamicResult(result) {
    const attempt = state.dynamicAttempt;
    if (!attempt?.awaitingResult || result.attempt_id !== attempt.id) return;
    if (result.status !== 'verified') {
      endDynamicAttempt(result.reason || 'Повторите попытку.');
      return;
    }

    const { controls, gesture, isBlitz } = attempt;
    controls.gesture.textContent = result.accepted ? 'Жест засчитан' : 'Жест не засчитан';
    const confText = result.confidence !== undefined
      ? `Точность: ${Math.round(result.confidence)}%`
      : `Расстояние DTW: ${Number(result.distance).toFixed(2)}`;
    controls.score.textContent = confText;
    endDynamicAttempt(result.accepted ? 'Жест выполнен правильно.' : 'Повторите движение после отсчёта.');
    if (!result.accepted) return;

    controls.button.disabled = true;
    if (isBlitz) {
      blitz.completeBlitzQuestion(gesture, state, dom, {
        playSpeech: (text) => ui.playSpeech(text, state.settings.ttsEnabled),
      });
    } else {
      state.practice.isLearned = true;
      practice.onGestureSuccessfullyLearned(gesture, state, dom, {
        playSpeech: (text) => ui.playSpeech(text, state.settings.ttsEnabled),
        updateProfileView: () => ui.updateProfileView(state, dom, () => switchTab('catalog')),
      });
    }
  }

  // --- Модальные окна практики ---
  function openTutorialModal(gesture) {
    practice.openTutorialModal(gesture, state, dom);
  }

  function closeTutorialModal() {
    practice.closeTutorialModal(dom);
  }

  function openPracticeModal(gesture) {
    practice.openPracticeModal(gesture, state, dom, startCamera);
  }

  function closePracticeModal() {
    practice.closePracticeModal(state, dom, stopCamera, {
      onLoadCatalog: () => catalog.loadCatalog(state, dom, openTutorialModal),
      onCheckAuth: checkAuth,
    });
  }

  // --- Ежедневная разминка (SM-2 SRS, US-1) ---
  function startWarmupSession() {
    warmup.startWarmup(state, dom, startCamera, {
      onRequireAuth: () => {
        alert('Для сохранения серии ежедневной разминки и прогресса SM-2 войдите в личный кабинет.');
        switchTab('profile');
      },
      onWarmupEmpty: (streak) => {
        alert(`Все жесты на сегодня уже повторены! Ваша текущая серия: ${streak} 🔥 дн.\nВы можете повторить любой жест из словаря или запустить блиц!`);
      },
      playSpeech: (text) => ui.playSpeech(text, state.settings.ttsEnabled),
      onWarmupFinished: () => {
        ui.updateUserHeader(state, dom, () => switchTab('profile'));
        ui.updateProfileView(state, dom, () => switchTab('catalog'));
      },
    });
  }

  function abortWarmupSession() {
    warmup.abortWarmup(state, dom, stopCamera);
  }

  // --- Онбординг «Как тренироваться» (US-2) ---
  let currentOnboardingStep = 1;

  function setOnboardingStep(step) {
    currentOnboardingStep = Math.max(1, Math.min(3, step));
    for (let i = 1; i <= 3; i++) {
      const stepEl = document.getElementById(`onboarding-step-${i}`);
      if (stepEl) {
        stepEl.style.display = i === currentOnboardingStep ? 'block' : 'none';
      }
    }
    if (dom.onboardingStepCounter) {
      dom.onboardingStepCounter.textContent = `Шаг ${currentOnboardingStep} из 3`;
    }
    if (dom.btnOnboardingPrev) {
      dom.btnOnboardingPrev.style.visibility = currentOnboardingStep > 1 ? 'visible' : 'hidden';
    }
    if (dom.btnOnboardingNext) {
      dom.btnOnboardingNext.textContent = currentOnboardingStep === 3
        ? 'Всё понятно, начать! [Enter]'
        : 'Далее → [Пробел]';
    }
    document.querySelectorAll('.onboarding-dot').forEach((dot) => {
      const s = parseInt(dot.dataset.step, 10);
      dot.classList.toggle('active', s === currentOnboardingStep);
    });
  }

  function openOnboarding(step = 1) {
    setOnboardingStep(step);
    if (dom.onboardingModal) dom.onboardingModal.style.display = 'flex';
  }

  function closeOnboarding() {
    if (dom.onboardingModal) dom.onboardingModal.style.display = 'none';
  }

  // --- Горячие клавиши для бесконтактного управления (US-4) ---
  function handleGlobalKeyDown(e) {
    const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') {
      return;
    }

    // 1. Escape: закрыть любую открытую модалку
    if (e.key === 'Escape') {
      if (dom.onboardingModal && dom.onboardingModal.style.display !== 'none') {
        closeOnboarding();
        return;
      }
      if (dom.warmupModal && dom.warmupModal.style.display !== 'none') {
        abortWarmupSession();
        return;
      }
      if (dom.practiceModal && dom.practiceModal.style.display !== 'none') {
        closePracticeModal();
        return;
      }
      if (dom.tutorialModal && dom.tutorialModal.style.display !== 'none') {
        closeTutorialModal();
        return;
      }
      if (state.blitz?.isActive) {
        blitz.abortBlitz(state, dom, stopCamera);
        return;
      }
    }

    // 2. Space / Enter: продолжить после успеха / подтвердить действие
    if (e.key === ' ' || e.key === 'Spacebar' || e.key === 'Enter') {
      // Онбординг
      if (dom.onboardingModal && dom.onboardingModal.style.display !== 'none') {
        e.preventDefault();
        if (currentOnboardingStep < 3) {
          setOnboardingStep(currentOnboardingStep + 1);
        } else {
          closeOnboarding();
        }
        return;
      }

      // Практика: экран успеха
      if (dom.practiceSuccessOverlay && dom.practiceSuccessOverlay.style.display !== 'none') {
        e.preventDefault();
        closePracticeModal();
        return;
      }

      // Практика: динамический жест
      if (
        dom.practiceModal &&
        dom.practiceModal.style.display !== 'none' &&
        dom.btnDynamicPractice &&
        !dom.btnDynamicPractice.hidden &&
        !dom.btnDynamicPractice.disabled
      ) {
        e.preventDefault();
        startDynamicAttempt();
        return;
      }

      // Разминка: экран финиша
      if (dom.warmupFinishOverlay && dom.warmupFinishOverlay.style.display !== 'none') {
        e.preventDefault();
        abortWarmupSession();
        ui.updateUserHeader(state, dom, () => switchTab('profile'));
        ui.updateProfileView(state, dom, () => switchTab('catalog'));
        return;
      }

      // Ошибка камеры: кнопка повтора
      const retryBtn = document.querySelector('.btn-retry-camera');
      if (retryBtn) {
        e.preventDefault();
        retryBtn.click();
        return;
      }
    }

    // 3. M: зеркальное отображение камеры
    if (e.key === 'm' || e.key === 'M' || e.key === 'ь' || e.key === 'Ь') {
      const activeContainer =
        (state.cameraTarget === 'practice' && dom.practiceCanvas?.parentElement) ||
        (state.cameraTarget === 'warmup' && dom.warmupCanvas?.parentElement) ||
        (state.cameraTarget === 'blitz' && dom.blitzCanvas?.parentElement) ||
        document.querySelector('.camera-container');
      if (activeContainer) {
        activeContainer.classList.toggle('mirrored');
      }
    }
  }

  // --- Привязка событий DOM ---
  function bindEvents() {
    dom.brandLink?.addEventListener('click', (e) => {
      e.preventDefault();
      switchTab('about');
    });

    dom.navBtns.forEach((btn) => {
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    dom.btnHeroStart?.addEventListener('click', () => switchTab('catalog'));
    dom.btnHeroLk?.addEventListener('click', () => switchTab('profile'));
    dom.btnHeroWarmup?.addEventListener('click', startWarmupSession);
    dom.btnHeroGuide?.addEventListener('click', () => openOnboarding(1));
    dom.btnHeaderWarmup?.addEventListener('click', startWarmupSession);
    dom.btnHeaderGuide?.addEventListener('click', () => openOnboarding(1));
    dom.btnCatalogWarmup?.addEventListener('click', startWarmupSession);

    // Онбординг
    dom.btnCloseOnboarding?.addEventListener('click', closeOnboarding);
    dom.btnOnboardingPrev?.addEventListener('click', () => setOnboardingStep(currentOnboardingStep - 1));
    dom.btnOnboardingNext?.addEventListener('click', () => {
      if (currentOnboardingStep < 3) {
        setOnboardingStep(currentOnboardingStep + 1);
      } else {
        closeOnboarding();
      }
    });
    document.querySelectorAll('.onboarding-dot').forEach((dot) => {
      dot.addEventListener('click', () => {
        const s = parseInt(dot.dataset.step, 10);
        if (s) setOnboardingStep(s);
      });
    });

    // Шпаргалки (US-3)
    dom.btnPracticeCheatsheetToggle?.addEventListener('click', () => {
      practice.toggleCheatsheet(dom);
    });
    dom.btnWarmupCheatsheetToggle?.addEventListener('click', () => {
      warmup.toggleWarmupCheatsheet(dom);
    });

    // Разминка
    dom.btnCloseWarmupModal?.addEventListener('click', abortWarmupSession);
    dom.btnAbortWarmup?.addEventListener('click', abortWarmupSession);
    dom.btnWarmupDone?.addEventListener('click', () => {
      abortWarmupSession();
      switchTab('catalog');
    });

    // Горячие клавиши
    window.addEventListener('keydown', handleGlobalKeyDown);

    dom.contactForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      dom.contactSuccess.style.display = 'block';
      dom.contactForm.reset();
      setTimeout(() => {
        dom.contactSuccess.style.display = 'none';
      }, 4000);
    });

    // Аутентификация
    dom.authTabLogin?.addEventListener('click', () => {
      dom.authTabLogin.classList.add('active');
      dom.authTabRegister.classList.remove('active');
      dom.formLogin.style.display = 'block';
      dom.formRegister.style.display = 'none';
    });

    dom.authTabRegister?.addEventListener('click', () => {
      dom.authTabRegister.classList.add('active');
      dom.authTabLogin.classList.remove('active');
      dom.formRegister.style.display = 'block';
      dom.formLogin.style.display = 'none';
    });

    dom.formLogin?.addEventListener('submit', async (e) => {
      e.preventDefault();
      dom.loginError.style.display = 'none';
      const username = document.getElementById('login-username').value.trim();
      const password = document.getElementById('login-password').value.trim();
      try {
        const data = await ui.apiFetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        state.authToken = data.user.token;
        localStorage.setItem('omilia_token', state.authToken);
        state.currentUser = {
          ...data.user,
          learned_gestures: data.learned_gestures || data.user?.learned_gestures || [],
        };
        ui.updateUserHeader(state, dom, () => switchTab('profile'));
        ui.updateProfileView(state, dom, () => switchTab('catalog'));
        catalog.loadCatalog(state, dom, openTutorialModal);
      } catch (err) {
        dom.loginError.textContent = err.message;
        dom.loginError.style.display = 'block';
      }
    });

    dom.formRegister?.addEventListener('submit', async (e) => {
      e.preventDefault();
      dom.regError.style.display = 'none';
      const username = document.getElementById('reg-username').value.trim();
      const password = document.getElementById('reg-password').value.trim();
      try {
        const data = await ui.apiFetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        state.authToken = data.user.token;
        localStorage.setItem('omilia_token', state.authToken);
        state.currentUser = {
          ...data.user,
          learned_gestures: data.learned_gestures || data.user?.learned_gestures || [],
        };
        ui.updateUserHeader(state, dom, () => switchTab('profile'));
        ui.updateProfileView(state, dom, () => switchTab('catalog'));
        catalog.loadCatalog(state, dom, openTutorialModal);
      } catch (err) {
        dom.regError.textContent = err.message;
        dom.regError.style.display = 'block';
      }
    });

    dom.btnLogout?.addEventListener('click', async () => {
      try {
        await ui.apiFetch('/api/auth/logout', { method: 'POST' }, state.authToken);
      } catch {}
      state.authToken = null;
      localStorage.removeItem('omilia_token');
      state.currentUser = null;
      ui.updateUserHeader(state, dom, () => switchTab('profile'));
      ui.updateProfileView(state, dom, () => switchTab('catalog'));
      catalog.loadCatalog(state, dom, openTutorialModal);
    });

    dom.ttsToggle?.addEventListener('change', (e) => {
      state.settings.ttsEnabled = e.target.checked;
      localStorage.setItem('omilia_tts', state.settings.ttsEnabled ? 'true' : 'false');
      if (state.settings.ttsEnabled) {
        ui.playSpeech('Озвучивание жестов включено', true);
      }
    });

    // Фильтры и поиск каталога
    catalog.setupCatalogFilters(state, dom, openTutorialModal);

    // Зеркалирование камеры
    document.querySelectorAll('.btn-toggle-mirror').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const container = e.target.closest('.camera-container') || document.querySelector('.camera-container');
        if (container) container.classList.toggle('mirrored');
      });
    });

    // Переключение камеры (фронтальная / основная)
    document.querySelectorAll('.btn-switch-camera').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (camera?.switchCamera) {
          await camera.switchCamera(state, dom, {
            getExpectedHandsCount: () =>
              state.cameraTarget === 'practice' ? state.practice.gesture?.hands_count || 1 : 1,
            onFrameRender,
            ensureWebSocket: socket?.ensureWebSocket,
          });
        }
      });
    });

    // Модальные окна
    dom.btnCloseTutorial?.addEventListener('click', closeTutorialModal);
    dom.btnStartCameraPractice?.addEventListener('click', () => {
      if (state.practice.gesture) openPracticeModal(state.practice.gesture);
    });
    dom.btnClosePracticeModal?.addEventListener('click', closePracticeModal);
    dom.btnPracticeCancel?.addEventListener('click', closePracticeModal);
    dom.btnDynamicPractice?.addEventListener('click', startDynamicAttempt);
    dom.btnPracticeDone?.addEventListener('click', closePracticeModal);

    // Блиц-опрос
    dom.btnStartBlitz?.addEventListener('click', () => blitz.startBlitz(state, dom, startCamera));
    dom.btnDynamicBlitz?.addEventListener('click', startDynamicAttempt);
    dom.btnAbortBlitz?.addEventListener('click', () => blitz.abortBlitz(state, dom, stopCamera));
    dom.btnRepeatBlitz?.addEventListener('click', () => blitz.startBlitz(state, dom, startCamera));
    dom.btnBlitzToCatalog?.addEventListener('click', () => switchTab('catalog'));
  }

  // --- Инициализация приложения ---
  async function init() {
    bindEvents();
    await checkAuth();
    await catalog.loadCatalog(state, dom, openTutorialModal);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
