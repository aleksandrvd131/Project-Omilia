/**
 * Project Omiλia — Frontend Application Logic
 * Модульная архитектура: SPA, Управление состоянием, MediaPipe Hands, WebSockets, Аутентификация, Блиц.
 */

(function () {
  'use strict';

  // --- Состояние приложения ---
  const state = {
    authToken: localStorage.getItem('omilia_token') || null,
    currentUser: null,
    settings: {
      ttsEnabled: localStorage.getItem('omilia_tts') !== 'false', // по умолчанию включено
    },
    gestures: [],
    activeTab: 'about',
    
    // Состояние практики (Шаг 2 обучения)
    practice: {
      gesture: null,
      holdProgress: 0,
      holdTarget: 1.5, // 1.5 секунды удержания
      isLearned: false,
      lastTimestamp: null,
    },

    // Состояние блиц-опроса
    blitz: {
      questions: [],
      currentIndex: 0,
      holdProgress: 0,
      holdTarget: 1.5,
      isHoldingCorrect: false,
      lastTimestamp: null,
      isActive: false,
    },

    // WebSocket и MediaPipe
    ws: null,
    camera: null,
    cameraTarget: null, // 'practice' или 'blitz'
    mediaPipeHands: null,
    isCameraRunning: false,
  };

  // --- Селекторы элементов DOM ---
  const dom = {
    brandLink: document.getElementById('brand-link'),
    navBtns: document.querySelectorAll('.nav-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    headerUserArea: document.getElementById('header-user-area'),
    btnHeaderLogin: document.getElementById('btn-header-login'),

    // Главная
    btnHeroStart: document.getElementById('btn-hero-start'),
    btnHeroLk: document.getElementById('btn-hero-lk'),
    contactForm: document.getElementById('contact-form'),
    contactSuccess: document.getElementById('contact-success'),

    // Каталог
    gesturesGrid: document.getElementById('gestures-grid'),
    catalogLearnedCounter: document.getElementById('catalog-learned-counter'),

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
    profileProgressBar: document.getElementById('profile-progress-bar'),
    profileProgressText: document.getElementById('profile-progress-text'),
    profileStatsSummary: document.getElementById('profile-stats-summary'),
    profileLearnedBadges: document.getElementById('profile-learned-badges'),
    ttsToggle: document.getElementById('tts-toggle'),
    btnLogout: document.getElementById('btn-logout'),

    // Блиц
    blitzIntro: document.getElementById('blitz-intro'),
    blitzActive: document.getElementById('blitz-active'),
    blitzFinish: document.getElementById('blitz-finish'),
    blitzEligibility: document.getElementById('blitz-eligibility'),
    btnStartBlitz: document.getElementById('btn-start-blitz'),
    blitzProgressStep: document.getElementById('blitz-progress-step'),
    blitzTargetTitle: document.getElementById('blitz-target-title'),
    blitzTargetTip: document.getElementById('blitz-target-tip'),
    blitzVideo: document.getElementById('blitz-video'),
    blitzCanvas: document.getElementById('blitz-canvas'),
    blitzHudGesture: document.getElementById('blitz-hud-gesture'),
    blitzHudScore: document.getElementById('blitz-hud-score'),
    blitzHoldFill: document.getElementById('blitz-hold-fill'),
    blitzQuestionSuccess: document.getElementById('blitz-question-success'),
    btnAbortBlitz: document.getElementById('btn-abort-blitz'),
    btnRepeatBlitz: document.getElementById('btn-repeat-blitz'),
    btnBlitzToCatalog: document.getElementById('btn-blitz-to-catalog'),

    // Модальное окно 1: Обучение (Видео + Описание)
    tutorialModal: document.getElementById('tutorial-modal'),
    tutorialTitle: document.getElementById('tutorial-title'),
    tutorialCategory: document.getElementById('tutorial-category'),
    tutorialDesc: document.getElementById('tutorial-desc'),
    tutorialTip: document.getElementById('tutorial-tip'),
    tutorialVideo: document.getElementById('tutorial-video'),
    tutorialVideoFallback: document.getElementById('tutorial-video-fallback'),
    btnCloseTutorial: document.getElementById('btn-close-tutorial'),
    btnStartCameraPractice: document.getElementById('btn-start-camera-practice'),

    // Модальное окно 2: Практика перед камерой
    practiceModal: document.getElementById('practice-modal'),
    practiceTitle: document.getElementById('practice-title'),
    practiceTipText: document.getElementById('practice-tip-text'),
    practiceVideo: document.getElementById('practice-video'),
    practiceCanvas: document.getElementById('practice-canvas'),
    practiceHudGesture: document.getElementById('practice-hud-gesture'),
    practiceHudScore: document.getElementById('practice-hud-score'),
    practiceHoldFill: document.getElementById('practice-hold-fill'),
    practiceSuccessOverlay: document.getElementById('practice-success-overlay'),
    practiceSuccessMsg: document.getElementById('practice-success-msg'),
    btnPracticeDone: document.getElementById('btn-practice-done'),
    btnClosePracticeModal: document.getElementById('btn-close-practice-modal'),
    btnPracticeCancel: document.getElementById('btn-practice-cancel'),
  };

  // ==========================================================
  // Вспомогательные функции (API, Аудио, Уведомления)
  // ==========================================================

  // Запрос к серверу с автоматической передачей Auth-токена
  async function apiFetch(endpoint, options = {}) {
    options.headers = options.headers || {};
    if (state.authToken) {
      options.headers['Authorization'] = `Bearer ${state.authToken}`;
    }
    const res = await fetch(endpoint, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || `Ошибка сервера: ${res.status}`);
    }
    return data;
  }

  // Озвучивание текста (Синтез речи) с учётом настроек пользователя
  function playSpeech(text) {
    if (!state.settings.ttsEnabled) {
      return; // Озвучивание отключено в настройках ЛК
    }
    try {
      // Используем серверный gTTS стрим
      const audio = new Audio(`/api/tts?text=${encodeURIComponent(text)}`);
      audio.play().catch(() => {
        // Fallback на нативный SpeechSynthesis браузера
        if ('speechSynthesis' in window) {
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.lang = 'ru-RU';
          window.speechSynthesis.speak(utterance);
        }
      });
    } catch (e) {
      console.warn('Ошибка воспроизведения аудио:', e);
    }
  }

  // Переключение вкладок SPA
  function switchTab(tabId) {
    state.activeTab = tabId;
    
    // Если уходим с блица, останавливаем камеру
    if (tabId !== 'blitz' && state.cameraTarget === 'blitz') {
      stopCamera();
    }

    dom.navBtns.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    dom.tabContents.forEach((content) => {
      content.classList.toggle('active', content.id === `tab-${tabId}`);
    });

    if (tabId === 'catalog') {
      loadCatalog();
    } else if (tabId === 'blitz') {
      setupBlitzIntro();
    } else if (tabId === 'profile') {
      updateProfileView();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ==========================================================
  // Аутентификация и Управление профилем
  // ==========================================================

  async function checkAuth() {
    if (!state.authToken) {
      updateUserHeader();
      updateProfileView();
      return;
    }
    try {
      const data = await apiFetch('/api/auth/me');
      state.currentUser = data.user;
    } catch {
      state.authToken = null;
      localStorage.removeItem('omilia_token');
      state.currentUser = null;
    }
    updateUserHeader();
    updateProfileView();
  }

  function updateUserHeader() {
    if (!dom.headerUserArea) return;
    if (state.currentUser) {
      dom.headerUserArea.innerHTML = `
        <div class="user-badge" id="btn-header-profile" title="Перейти в личный кабинет">
          <span>👤</span>
          <span>${escapeHtml(state.currentUser.username)}</span>
        </div>
      `;
      document.getElementById('btn-header-profile')?.addEventListener('click', () => {
        switchTab('profile');
      });
    } else {
      dom.headerUserArea.innerHTML = `
        <button class="btn-login" id="btn-header-login">Войти в ЛК</button>
      `;
      document.getElementById('btn-header-login')?.addEventListener('click', () => {
        switchTab('profile');
      });
    }
  }

  function updateProfileView() {
    if (state.currentUser) {
      dom.authBox.style.display = 'none';
      dom.profileBox.style.display = 'block';
      dom.profileUsername.textContent = state.currentUser.username;

      // Обновляем переключатель озвучивания
      if (dom.ttsToggle) {
        dom.ttsToggle.checked = state.settings.ttsEnabled;
      }

      // Подсчёт прогресса
      const total = state.gestures.length || 1;
      const learned = state.currentUser.learned_gestures || [];
      const percent = Math.min(100, Math.round((learned.length / total) * 100));

      dom.profileProgressBar.style.width = `${percent}%`;
      dom.profileProgressText.textContent = `${percent}%`;
      dom.profileStatsSummary.textContent = `Вы выучили ${learned.length} из ${state.gestures.length} доступных жестов`;

      // Отображение значков выученных жестов
      dom.profileLearnedBadges.innerHTML = '';
      if (learned.length === 0) {
        dom.profileLearnedBadges.innerHTML = `
          <div style="color: var(--text-muted); font-size: 0.9rem;">
            Пока нет выученных жестов. Перейдите в <a href="#" style="color: var(--primary-hover); text-decoration: underline;" id="link-to-catalog">словарь жестов</a>, чтобы начать обучение!
          </div>
        `;
        document.getElementById('link-to-catalog')?.addEventListener('click', (e) => {
          e.preventDefault();
          switchTab('catalog');
        });
      } else {
        learned.forEach((gname) => {
          const badge = document.createElement('span');
          badge.className = 'gesture-badge badge-learned';
          badge.style.padding = '0.4rem 0.85rem';
          badge.style.fontSize = '0.88rem';
          badge.innerHTML = `✓ ${escapeHtml(gname)}`;
          dom.profileLearnedBadges.appendChild(badge);
        });
      }
    } else {
      dom.authBox.style.display = 'block';
      dom.profileBox.style.display = 'none';
    }
  }

  // ==========================================================
  // Каталог жестов
  // ==========================================================

  async function loadCatalog() {
    try {
      const data = await apiFetch('/api/gestures');
      state.gestures = data.gestures || [];

      // Обновляем счётчик
      if (dom.catalogLearnedCounter) {
        dom.catalogLearnedCounter.textContent = `Выучено: ${data.total_learned} из ${data.total_available}`;
      }

      renderCatalog();
    } catch (err) {
      dom.gesturesGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: var(--danger); padding: 2rem;">
          Не удалось загрузить каталог: ${err.message}
        </div>
      `;
    }
  }

  function renderCatalog() {
    if (!dom.gesturesGrid) return;
    dom.gesturesGrid.innerHTML = '';

    if (state.gestures.length === 0) {
      dom.gesturesGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 3rem;">
          В датасете пока нет записанных жестов. Используйте <a href="/dev" style="color: var(--primary);">панель разработчика</a> для записи.
        </div>
      `;
      return;
    }

    state.gestures.forEach((gesture) => {
      const card = document.createElement('div');
      card.className = `gesture-card ${gesture.is_learned ? 'learned' : ''}`;

      card.innerHTML = `
        <div>
          <div class="gesture-top">
            <span class="gesture-badge ${gesture.is_learned ? 'badge-learned' : 'badge-unlearned'}">
              ${gesture.is_learned ? '✓ Выучен' : 'Не изучен'}
            </span>
            <span style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(gesture.category)}</span>
          </div>
          <h3 class="gesture-title">${escapeHtml(gesture.title || gesture.name)}</h3>
          <p class="gesture-desc">${escapeHtml(gesture.description)}</p>
          <div class="gesture-tip">
            💡 ${escapeHtml(gesture.tip)}
          </div>
        </div>
        <div>
          <button class="btn-practice" data-name="${escapeHtml(gesture.name)}">
            ${gesture.is_learned ? 'Повторить жест ↺' : 'Изучить жест →'}
          </button>
        </div>
      `;

      card.querySelector('.btn-practice').addEventListener('click', () => {
        openTutorialModal(gesture);
      });

      dom.gesturesGrid.appendChild(card);
    });
  }

  // ==========================================================
  // Двухэтапное обучение:
  // Шаг 1 — Демонстрация жеста (Видео + Описание)
  // Шаг 2 — Интерактивная практика перед веб-камерой
  // ==========================================================

  function openTutorialModal(gesture) {
    state.practice.gesture = gesture;

    dom.tutorialTitle.textContent = `Жест: «${gesture.title || gesture.name}»`;
    dom.tutorialCategory.textContent = gesture.category || 'Общие жесты';
    dom.tutorialDesc.textContent = gesture.description;
    dom.tutorialTip.innerHTML = `💡 <strong>Подсказка:</strong> ${escapeHtml(gesture.tip)}`;

    // Попытка настроить видеодемонстрацию
    const videoSrc = `/static/videos/${encodeURIComponent(gesture.name.toLowerCase())}.mp4`;
    dom.tutorialVideo.src = videoSrc;
    dom.tutorialVideo.style.display = 'block';
    dom.tutorialVideoFallback.style.display = 'none';

    dom.tutorialVideo.onerror = () => {
      // Если локальный mp4 файл не найден, переключаемся на красивую анимированную схему
      dom.tutorialVideo.style.display = 'none';
      dom.tutorialVideoFallback.style.display = 'flex';
      const caption = document.getElementById('tutorial-demo-caption');
      if (caption) {
        caption.textContent = `Схема жеста: ${gesture.title || gesture.name}`;
      }
    };

    dom.tutorialVideo.play().catch(() => {});
    dom.tutorialModal.style.display = 'flex';
  }

  function closeTutorialModal() {
    dom.tutorialModal.style.display = 'none';
    dom.tutorialVideo.pause();
    dom.tutorialVideo.src = '';
  }

  function openPracticeModal(gesture) {
    closeTutorialModal();
    state.practice.gesture = gesture;
    state.practice.holdProgress = 0;
    state.practice.isLearned = false;
    state.practice.lastTimestamp = null;

    dom.practiceTitle.textContent = `Жест: «${gesture.title || gesture.name}»`;
    dom.practiceTipText.innerHTML = `Покажите жест <strong>«${escapeHtml(gesture.title || gesture.name)}»</strong> и удерживайте его 1.5 секунды`;
    dom.practiceHudGesture.textContent = 'Ожидание руки...';
    dom.practiceHudScore.textContent = 'Точность: —';
    dom.practiceHoldFill.style.width = '0%';
    dom.practiceSuccessOverlay.style.display = 'none';

    dom.practiceModal.style.display = 'flex';
    startCamera('practice');
  }

  function closePracticeModal() {
    dom.practiceModal.style.display = 'none';
    stopCamera();
    state.practice.gesture = null;
    loadCatalog();
    checkAuth();
  }

  // ==========================================================
  // Блиц-опрос («Проверить себя»)
  // ==========================================================

  function setupBlitzIntro() {
    dom.blitzIntro.style.display = 'block';
    dom.blitzActive.style.display = 'none';
    dom.blitzFinish.style.display = 'none';

    if (!state.currentUser) {
      dom.blitzEligibility.innerHTML = `
        <div style="background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 1rem; border-radius: 8px; font-weight: 500;">
          ⚠️ Для прохождения блиц-опроса необходимо войти в аккаунт.
        </div>
      `;
      dom.btnStartBlitz.disabled = true;
      dom.btnStartBlitz.style.opacity = '0.5';
      return;
    }

    const learned = state.currentUser.learned_gestures || [];
    if (learned.length === 0) {
      dom.blitzEligibility.innerHTML = `
        <div style="background: #fffbeb; border: 1px solid #fef3c7; color: #92400e; padding: 1rem; border-radius: 8px; font-weight: 500;">
          💡 У вас пока нет выученных жестов. Изучите хотя бы один жест в <a href="#" style="color: var(--primary-hover); text-decoration: underline;" id="blitz-link-catalog">словаре жестов</a>!
        </div>
      `;
      document.getElementById('blitz-link-catalog')?.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('catalog');
      });
      dom.btnStartBlitz.disabled = true;
      dom.btnStartBlitz.style.opacity = '0.5';
    } else {
      dom.blitzEligibility.innerHTML = `
        <div style="background: var(--primary-light); border: 1px solid var(--primary-border); color: var(--primary-hover); padding: 1rem; border-radius: 8px; font-weight: 600;">
          Вам доступно для проверки: <strong>${learned.length}</strong> выученных жестов.
        </div>
      `;
      dom.btnStartBlitz.disabled = false;
      dom.btnStartBlitz.style.opacity = '1';
    }
  }

  async function startBlitz() {
    try {
      const data = await apiFetch('/api/blitz/questions?count=3');
      if (!data.questions || data.questions.length === 0) {
        alert(data.message || 'Нет доступных вопросов для блица');
        return;
      }

      state.blitz.questions = data.questions;
      state.blitz.currentIndex = 0;
      state.blitz.isActive = true;

      dom.blitzIntro.style.display = 'none';
      dom.blitzFinish.style.display = 'none';
      dom.blitzActive.style.display = 'block';

      loadBlitzQuestion(0);
      startCamera('blitz');
    } catch (err) {
      alert(`Ошибка запуска блиц-опроса: ${err.message}`);
    }
  }

  function loadBlitzQuestion(index) {
    if (index >= state.blitz.questions.length) {
      finishBlitz();
      return;
    }

    state.blitz.currentIndex = index;
    state.blitz.holdProgress = 0;
    state.blitz.lastTimestamp = null;

    const q = state.blitz.questions[index];
    dom.blitzProgressStep.textContent = `Вопрос ${index + 1} из ${state.blitz.questions.length}`;
    dom.blitzTargetTitle.textContent = `Жест: «${q.title || q.gesture_name}»`;
    dom.blitzTargetTip.innerHTML = `💡 Подсказка: ${escapeHtml(q.tip || 'Покажите жест на камеру')}`;
    dom.blitzHudGesture.textContent = 'Ожидание руки...';
    dom.blitzHudScore.textContent = 'Точность: —';
    dom.blitzHoldFill.style.width = '0%';
    dom.blitzQuestionSuccess.style.display = 'none';
  }

  function finishBlitz() {
    stopCamera();
    state.blitz.isActive = false;
    dom.blitzActive.style.display = 'none';
    dom.blitzFinish.style.display = 'block';
    dom.blitzFinishDesc.textContent = `Поздравляем! Вы успешно подтвердили знание всех ${state.blitz.questions.length} жестов в блиц-опросе!`;
    playSpeech('Блиц успешно пройден! Отличная работа!');
  }

  function abortBlitz() {
    stopCamera();
    state.blitz.isActive = false;
    setupBlitzIntro();
  }

  // ==========================================================
  // Камера и Интеграция с MediaPipe + WebSockets
  // ==========================================================

  function ensureWebSocket() {
    if (state.ws && (state.ws.readyState === WebSocket.OPEN || state.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws/gestures`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
      console.log('[WebSocket] Соединение установлено');
    };

    state.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerPrediction(data);
      } catch (err) {
        console.warn('Ошибка парсинга WebSocket сообщения:', err);
      }
    };

    state.ws.onerror = (err) => {
      console.error('[WebSocket] Ошибка:', err);
    };

    state.ws.onclose = () => {
      console.log('[WebSocket] Соединение закрыто');
    };
  }

  function initMediaPipe() {
    if (state.mediaPipeHands) return;

    if (typeof Hands === 'undefined') {
      console.error('Библиотека MediaPipe Hands не загружена.');
      return;
    }

    state.mediaPipeHands = new Hands({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
    });

    state.mediaPipeHands.setOptions({
      maxNumHands: 2,
      modelComplexity: 1,
      minDetectionConfidence: 0.6,
      minTrackingConfidence: 0.6,
    });

    state.mediaPipeHands.onResults(onMediaPipeResults);
  }

  function startCamera(target) {
    state.cameraTarget = target;
    ensureWebSocket();
    initMediaPipe();

    const videoEl = target === 'practice' ? dom.practiceVideo : dom.blitzVideo;
    if (!videoEl || !state.mediaPipeHands) return;

    if (state.camera) {
      state.camera.stop();
      state.camera = null;
    }

    state.camera = new Camera(videoEl, {
      onFrame: async () => {
        if (state.isCameraRunning && state.cameraTarget) {
          await state.mediaPipeHands.send({ image: videoEl });
        }
      },
      width: 640,
      height: 480,
    });

    state.isCameraRunning = true;
    state.camera.start();
  }

  function stopCamera() {
    state.isCameraRunning = false;
    if (state.camera) {
      state.camera.stop();
      state.camera = null;
    }
    state.cameraTarget = null;
  }

  // Обработка кадров от MediaPipe Hands
  function onMediaPipeResults(results) {
    if (!state.isCameraRunning || !state.cameraTarget) return;

    const canvas = state.cameraTarget === 'practice' ? dom.practiceCanvas : dom.blitzCanvas;
    const video = state.cameraTarget === 'practice' ? dom.practiceVideo : dom.blitzVideo;
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const handsData = [];
    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
      for (const landmarks of results.multiHandLandmarks) {
        handsData.push(landmarks);
        drawHandLandmarks(ctx, landmarks, canvas.width, canvas.height);
      }
    }

    ctx.restore();

    // Отправляем точки на бэкенд через WebSocket
    if (state.ws && state.ws.readyState === WebSocket.OPEN && handsData.length > 0) {
      const payload = {
        hands: handsData,
        pose_landmarks: null, // опционально
      };
      state.ws.send(JSON.stringify(payload));
    }
  }

  // Отрисовка скелета руки на холсте
  function drawHandLandmarks(ctx, landmarks, width, height) {
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4], // Большой палец
      [0, 5], [5, 6], [6, 7], [7, 8], // Указательный
      [5, 9], [9, 10], [10, 11], [11, 12], // Средний
      [9, 13], [13, 14], [14, 15], [15, 16], // Безымянный
      [13, 17], [17, 18], [18, 19], [19, 20], // Мизинец
      [0, 17], // Основание ладони
    ];

    // Линии связей (Изумрудно-зелёные)
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#10b981';
    for (const [startIdx, endIdx] of connections) {
      const p1 = landmarks[startIdx];
      const p2 = landmarks[endIdx];
      ctx.beginPath();
      ctx.moveTo(p1.x * width, p1.y * height);
      ctx.lineTo(p2.x * width, p2.y * height);
      ctx.stroke();
    }

    // Точки суставов (Яркие мятные точки)
    ctx.fillStyle = '#34d399';
    for (const point of landmarks) {
      ctx.beginPath();
      ctx.arc(point.x * width, point.y * height, 4.5, 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  // ==========================================================
  // Обработка распознанного жеста от сервера
  // ==========================================================

  function handleServerPrediction(pred) {
    const now = performance.now();
    const predictedName = (pred.name || '').trim().toLowerCase();
    const distText = pred.distance ? `Дистанция: ${Number(pred.distance).toFixed(2)}` : '';

    // --- Обработка в режиме практики (Шаг 2) ---
    if (state.cameraTarget === 'practice' && state.practice.gesture && !state.practice.isLearned) {
      const targetName = state.practice.gesture.name.trim().toLowerCase();

      dom.practiceHudGesture.textContent = pred.name || '—';
      dom.practiceHudScore.textContent = distText;

      const delta = state.practice.lastTimestamp ? (now - state.practice.lastTimestamp) / 1000 : 0.05;
      state.practice.lastTimestamp = now;

      if (predictedName === targetName) {
        state.practice.holdProgress += delta;
        const progressPct = Math.min(100, Math.round((state.practice.holdProgress / state.practice.holdTarget) * 100));
        dom.practiceHoldFill.style.width = `${progressPct}%`;

        // Жест успешно удержан!
        if (state.practice.holdProgress >= state.practice.holdTarget) {
          state.practice.isLearned = true;
          onGestureSuccessfullyLearned(state.practice.gesture);
        }
      } else {
        // Сброс удержания при показе другого жеста
        state.practice.holdProgress = Math.max(0, state.practice.holdProgress - delta * 1.5);
        const progressPct = Math.min(100, Math.round((state.practice.holdProgress / state.practice.holdTarget) * 100));
        dom.practiceHoldFill.style.width = `${progressPct}%`;
      }
    }

    // --- Обработка в режиме блиц-опроса ---
    if (state.cameraTarget === 'blitz' && state.blitz.isActive) {
      const currentQ = state.blitz.questions[state.blitz.currentIndex];
      if (!currentQ) return;

      const targetName = currentQ.gesture_name.trim().toLowerCase();
      dom.blitzHudGesture.textContent = pred.name || '—';
      dom.blitzHudScore.textContent = distText;

      const delta = state.blitz.lastTimestamp ? (now - state.blitz.lastTimestamp) / 1000 : 0.05;
      state.blitz.lastTimestamp = now;

      if (predictedName === targetName) {
        state.blitz.holdProgress += delta;
        const progressPct = Math.min(100, Math.round((state.blitz.holdProgress / state.blitz.holdTarget) * 100));
        dom.blitzHoldFill.style.width = `${progressPct}%`;

        if (state.blitz.holdProgress >= state.blitz.holdTarget) {
          // Успешный ответ в блице!
          state.blitz.holdProgress = 0;
          dom.blitzQuestionSuccess.style.display = 'flex';
          playSpeech(currentQ.title || currentQ.gesture_name);

          setTimeout(() => {
            loadBlitzQuestion(state.blitz.currentIndex + 1);
          }, 1200);
        }
      } else {
        state.blitz.holdProgress = Math.max(0, state.blitz.holdProgress - delta * 1.5);
        const progressPct = Math.min(100, Math.round((state.blitz.holdProgress / state.blitz.holdTarget) * 100));
        dom.blitzHoldFill.style.width = `${progressPct}%`;
      }
    }
  }

  // Успешное изучение жеста в практике
  async function onGestureSuccessfullyLearned(gesture) {
    dom.practiceSuccessOverlay.style.display = 'flex';

    // Озвучиваем жест при успешном выполнении, если включено в ЛК
    playSpeech(gesture.title || gesture.name);

    // Фиксируем в базе данных через API
    if (state.authToken) {
      try {
        await apiFetch('/api/gestures/learn', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ gesture_name: gesture.name }),
        });
      } catch (err) {
        console.warn('Ошибка сохранения прогресса:', err);
      }
    }
  }

  // ==========================================================
  // Привязка событий пользовательского интерфейса
  // ==========================================================

  function bindEvents() {
    // Логотип ведет на "О проекте"
    dom.brandLink?.addEventListener('click', (e) => {
      e.preventDefault();
      switchTab('about');
    });

    // Навигационные вкладки
    dom.navBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        switchTab(btn.dataset.tab);
      });
    });

    // Кнопки на главной
    dom.btnHeroStart?.addEventListener('click', () => switchTab('catalog'));
    dom.btnHeroLk?.addEventListener('click', () => switchTab('profile'));

    // Форма обратной связи
    dom.contactForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      dom.contactSuccess.style.display = 'block';
      dom.contactForm.reset();
      setTimeout(() => {
        dom.contactSuccess.style.display = 'none';
      }, 4000);
    });

    // Вкладки Вход / Регистрация
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

    // Отправка формы Входа
    dom.formLogin?.addEventListener('submit', async (e) => {
      e.preventDefault();
      dom.loginError.style.display = 'none';
      const username = document.getElementById('login-username').value.trim();
      const password = document.getElementById('login-password').value.trim();

      try {
        const data = await apiFetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        state.authToken = data.user.token;
        localStorage.setItem('omilia_token', state.authToken);
        state.currentUser = data.user;
        updateUserHeader();
        updateProfileView();
        loadCatalog();
      } catch (err) {
        dom.loginError.textContent = err.message;
        dom.loginError.style.display = 'block';
      }
    });

    // Отправка формы Регистрации
    dom.formRegister?.addEventListener('submit', async (e) => {
      e.preventDefault();
      dom.regError.style.display = 'none';
      const username = document.getElementById('reg-username').value.trim();
      const password = document.getElementById('reg-password').value.trim();

      try {
        const data = await apiFetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        state.authToken = data.user.token;
        localStorage.setItem('omilia_token', state.authToken);
        state.currentUser = data.user;
        updateUserHeader();
        updateProfileView();
        loadCatalog();
      } catch (err) {
        dom.regError.textContent = err.message;
        dom.regError.style.display = 'block';
      }
    });

    // Кнопка Выхода из ЛК
    dom.btnLogout?.addEventListener('click', async () => {
      try {
        await apiFetch('/api/auth/logout', { method: 'POST' });
      } catch {}
      state.authToken = null;
      localStorage.removeItem('omilia_token');
      state.currentUser = null;
      updateUserHeader();
      updateProfileView();
      loadCatalog();
    });

    // Переключатель озвучивания жестов (Настройки в ЛК)
    dom.ttsToggle?.addEventListener('change', (e) => {
      state.settings.ttsEnabled = e.target.checked;
      localStorage.setItem('omilia_tts', state.settings.ttsEnabled ? 'true' : 'false');
      if (state.settings.ttsEnabled) {
        playSpeech('Озвучивание жестов включено');
      }
    });

    // Управление модальными окнами обучения
    dom.btnCloseTutorial?.addEventListener('click', closeTutorialModal);
    dom.btnStartCameraPractice?.addEventListener('click', () => {
      if (state.practice.gesture) {
        openPracticeModal(state.practice.gesture);
      }
    });

    dom.btnClosePracticeModal?.addEventListener('click', closePracticeModal);
    dom.btnPracticeCancel?.addEventListener('click', closePracticeModal);
    dom.btnPracticeDone?.addEventListener('click', closePracticeModal);

    // Блиц-опрос
    dom.btnStartBlitz?.addEventListener('click', startBlitz);
    dom.btnAbortBlitz?.addEventListener('click', abortBlitz);
    dom.btnRepeatBlitz?.addEventListener('click', startBlitz);
    dom.btnBlitzToCatalog?.addEventListener('click', () => switchTab('catalog'));
  }

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // ==========================================================
  // Старт приложения
  // ==========================================================
  async function init() {
    bindEvents();
    await checkAuth();
    await loadCatalog();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
