/**
 * Project Omiλia — Frontend Application Logic
 * Модульная архитектура: SPA, Управление состоянием, MediaPipe Hands, WebSockets, Аутентификация, Блиц.
 */

(function () {
  'use strict';

  // --- Состояние приложения ---
  const state = {
    classifier: null,
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
      advanceTimer: null,
      lastTimestamp: null,
      isActive: false,
    },

    dynamicAttempt: null,

    // WebSocket и MediaPipe
    ws: null,
    camera: null,
    cameraTarget: null, // 'practice' или 'blitz'
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

    // Главная
    btnHeroStart: document.getElementById('btn-hero-start'),
    btnHeroLk: document.getElementById('btn-hero-lk'),
    contactForm: document.getElementById('contact-form'),
    contactSuccess: document.getElementById('contact-success'),

    // Каталог
    gesturesGrid: document.getElementById('gestures-grid'),
    catalogLearnedCounter: document.getElementById('catalog-learned-counter'),
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
    blitzHoldFill: document.getElementById('blitz-hold-fill'),
    blitzAttemptStatus: document.getElementById('blitz-attempt-status'),
    btnDynamicBlitz: document.getElementById('btn-dynamic-blitz'),
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
    btnDynamicPractice: document.getElementById('btn-dynamic-practice'),
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
      abortBlitz();
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
      state.currentUser = {
        ...data.user,
        learned_gestures: data.learned_gestures || data.user?.learned_gestures || [],
      };
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

      // Подсчёт прогресса и ранга
      const total = state.gestures.length || 1;
      const learned = state.currentUser.learned_gestures || [];
      const percent = Math.min(100, Math.round((learned.length / total) * 100));

      // Карточки метрик
      if (dom.statLearnedCount) dom.statLearnedCount.textContent = learned.length;
      if (dom.statTotalCount) dom.statTotalCount.textContent = state.gestures.length;
      if (dom.statPercentCount) dom.statPercentCount.textContent = `${percent}%`;

      // Расчёт ранга пользователя
      if (dom.profileRankBadge) {
        let rankTitle = 'Новичок РЖЯ';
        if (learned.length >= 8) {
          rankTitle = 'Мастер жестового языка 🌟';
        } else if (learned.length >= 4) {
          rankTitle = 'Знаток РЖЯ 🚀';
        } else if (learned.length >= 1) {
          rankTitle = 'Ученик РЖЯ 📚';
        }
        dom.profileRankBadge.textContent = rankTitle;
      }

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
  // Каталог жестов, поиск и фильтрация
  // ==========================================================

  let isLoadingCatalog = false;
  const catalogFilters = {
    search: '',
    category: 'all',
  };

  async function loadCatalog() {
    if (isLoadingCatalog) return;
    isLoadingCatalog = true;
    try {
      const data = await apiFetch('/api/gestures');
      state.gestures = data.gestures || [];

      // Обновляем счётчик с безопасными фоллбэками
      if (dom.catalogLearnedCounter) {
        const total = data.total_available ?? data.total_count ?? (state.gestures ? state.gestures.length : 0);
        const learned = data.total_learned ?? data.learned_count ?? (state.gestures ? state.gestures.filter((g) => g.is_learned).length : 0);
        dom.catalogLearnedCounter.textContent = `Выучено: ${learned} из ${total}`;
      }

      renderCatalog();
    } catch (err) {
      if (dom.gesturesGrid) {
        dom.gesturesGrid.innerHTML = `
          <div style="grid-column: 1 / -1; text-align: center; color: var(--danger); padding: 2rem;">
            Не удалось загрузить каталог: ${escapeHtml(err.message)}
          </div>
        `;
      }
    } finally {
      isLoadingCatalog = false;
    }
  }

  function getFilteredGestures() {
    const q = catalogFilters.search.trim().toLowerCase();
    const cat = catalogFilters.category;

    return state.gestures.filter((g) => {
      // Фильтр по категории
      if (cat === 'learned' && !g.is_learned) return false;
      if (cat !== 'all' && cat !== 'learned' && g.category !== cat) return false;

      // Поиск по тексту
      if (q) {
        const title = (g.title || g.name || '').toLowerCase();
        const desc = (g.description || '').toLowerCase();
        const tip = (g.tip || '').toLowerCase();
        if (!title.includes(q) && !desc.includes(q) && !tip.includes(q)) {
          return false;
        }
      }
      return true;
    });
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

    const filtered = getFilteredGestures();
    if (filtered.length === 0) {
      dom.gesturesGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 3rem;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔍</div>
          <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.35rem;">Ничего не найдено</h3>
          <p style="font-size: 0.9rem;">Попробуйте изменить поисковый запрос или сбросить категорию.</p>
          <button class="btn-hero-secondary" id="btn-reset-filters" style="margin-top: 1rem; padding: 0.45rem 1.15rem;">
            Сбросить фильтры
          </button>
        </div>
      `;
      document.getElementById('btn-reset-filters')?.addEventListener('click', () => {
        catalogFilters.search = '';
        catalogFilters.category = 'all';
        if (dom.catalogSearch) dom.catalogSearch.value = '';
        if (dom.btnClearSearch) dom.btnClearSearch.style.display = 'none';
        dom.categoryFilters?.querySelectorAll('.filter-chip').forEach((c) => {
          c.classList.toggle('active', c.dataset.category === 'all');
        });
        renderCatalog();
      });
      return;
    }

    filtered.forEach((gesture) => {
      const card = document.createElement('div');
      card.className = `gesture-card ${gesture.is_learned ? 'learned' : ''}`;

      const handsBadge = gesture.dynamic_hands_count
        ? '⚡ Движение'
        : (gesture.hands_count === 2 || gesture.name === 'дом' ? '👐 2 руки' : '✋ 1 рука');

      card.innerHTML = `
        <div>
          <div class="gesture-top">
            <span class="gesture-badge ${gesture.is_learned ? 'badge-learned' : 'badge-unlearned'}">
              ${gesture.is_learned ? '✓ Выучен' : 'Не изучен'}
            </span>
            <div style="display: flex; gap: 0.4rem; align-items: center;">
              <span style="font-size: 0.75rem; background: #f1f5f9; padding: 2px 7px; border-radius: 6px; font-weight: 600; color: var(--text-muted);">
                ${handsBadge}
              </span>
              <span style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(gesture.category)}</span>
            </div>
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
    const isDynamic = Boolean(gesture.dynamic_hands_count);
    dom.btnDynamicPractice.hidden = !isDynamic;
    dom.btnDynamicPractice.disabled = false;
    dom.practiceHoldFill.parentElement.hidden = isDynamic;
    dom.practiceTipText.textContent = isDynamic
      ? 'Нажмите «Начать попытку». Покажите жест целиком после отсчёта.'
      : `Покажите жест «${gesture.title || gesture.name}» и удерживайте его 1.5 секунды`;
    dom.practiceHudGesture.textContent = isDynamic ? 'Готовьтесь к попытке' : 'Ожидание руки...';
    dom.practiceHudScore.textContent = isDynamic ? '' : 'Точность: —';
    dom.practiceHoldFill.style.width = '0%';
    dom.practiceSuccessOverlay.style.display = 'none';

    dom.practiceModal.style.display = 'flex';
    startCamera('practice');
  }

  function getCameraGesture() {
    if (state.cameraTarget === 'practice') return state.practice.gesture;
    if (state.cameraTarget === 'blitz' && state.blitz.isActive) {
      return state.blitz.questions[state.blitz.currentIndex];
    }
    return null;
  }

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
    if (state.ws?.readyState !== WebSocket.OPEN) {
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
          if (state.ws?.readyState !== WebSocket.OPEN) {
            throw new Error('Соединение прервалось. Повторите попытку.');
          }
          state.ws.send(JSON.stringify({
            type: 'dynamic_clip',
            mode: 'practice',
            attempt_id: attempt.id,
            label: gesture.name ?? gesture.gesture_name,
            hands_count: gesture.dynamic_hands_count,
            frames,
          }));
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
      }, clip.durationMs + 100);
    }

    countdown(clip.prepSeconds);
  }

  function endDynamicAttempt(message) {
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
      completeBlitzQuestion(gesture);
    } else {
      state.practice.isLearned = true;
      onGestureSuccessfullyLearned(gesture);
    }
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

    const learnedNames = new Set(state.currentUser.learned_gestures || []);
    const learned = state.gestures.filter(gesture => learnedNames.has(gesture.name));
    if (learned.length === 0) {
      dom.blitzEligibility.innerHTML = `
        <div style="background: #fffbeb; border: 1px solid #fef3c7; color: #92400e; padding: 1rem; border-radius: 8px; font-weight: 500;">
          💡 Для блица выучите хотя бы один жест в <a href="#" style="color: var(--primary-hover); text-decoration: underline;" id="blitz-link-catalog">словаре жестов</a>!
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
    const isDynamic = Boolean(q.dynamic_hands_count);
    dom.btnDynamicBlitz.hidden = !isDynamic;
    dom.btnDynamicBlitz.disabled = false;
    dom.blitzAttemptStatus.textContent = isDynamic
      ? 'Нажмите «Начать попытку» и покажите жест после отсчёта.'
      : 'Покажите требуемый жест и удерживайте его 1.5 секунды';
    dom.blitzHudGesture.textContent = isDynamic ? 'Готовьтесь к попытке' : 'Ожидание руки...';
    dom.blitzHudScore.textContent = isDynamic ? '' : 'Точность: —';
    dom.blitzHoldFill.parentElement.hidden = isDynamic;
    dom.blitzHoldFill.style.width = '0%';
    dom.blitzQuestionSuccess.style.display = 'none';
    if (state.cameraTarget === 'blitz') {
      state.mediaPipeHands?.setOptions({ maxNumHands: q.dynamic_hands_count || 2 });
    }
  }

  function completeBlitzQuestion(question) {
    if (state.blitz.advanceTimer !== null) return;

    dom.blitzQuestionSuccess.style.display = 'flex';
    playSpeech(question.title || question.gesture_name);
    state.blitz.advanceTimer = setTimeout(() => {
      state.blitz.advanceTimer = null;
      loadBlitzQuestion(state.blitz.currentIndex + 1);
    }, 1200);
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
      state.isWsBusy = false;
      if (state.wsTimeout) {
        clearTimeout(state.wsTimeout);
        state.wsTimeout = null;
      }
      try {
        const data = JSON.parse(event.data);
        handleServerPrediction(data);
      } catch (err) {
        console.warn('Ошибка парсинга WebSocket сообщения:', err);
      }
    };

    state.ws.onerror = (err) => {
      state.isWsBusy = false;
      console.error('[WebSocket] Ошибка:', err);
    };

    state.ws.onclose = () => {
      state.isWsBusy = false;
      if (state.dynamicAttempt) {
        endDynamicAttempt('Соединение прервалось. Начните попытку ещё раз.');
      }
      console.log('[WebSocket] Соединение закрыто');
    };
  }

  function initMediaPipe() {
    if (state.mediaPipeHands && state.mediaPipePose) return;

    if (typeof Hands !== 'undefined' && !state.mediaPipeHands) {
      state.mediaPipeHands = new Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
      });

      state.mediaPipeHands.setOptions({
        maxNumHands: 2,
        modelComplexity: 1,
        minDetectionConfidence: 0.6,
        minTrackingConfidence: 0.6,
      });

      state.mediaPipeHands.onResults((results) => {
        let rawHands = results.multiHandLandmarks || [];
        // Защита от ложного дублирования одной руки ребром
        if (rawHands.length >= 2) {
          const h0 = rawHands[0];
          const h1 = rawHands[1];
          const distWrist = Math.hypot(h0[0].x - h1[0].x, h0[0].y - h1[0].y);
          if (distWrist < 0.08) {
            rawHands = [h0];
          }
        }
        state.latestHands = rawHands;
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

    const handsCount = getCameraGesture()?.dynamic_hands_count;
    state.mediaPipeHands.setOptions({ maxNumHands: handsCount || 2 });

    let lastAnalysisAt = 0;
    let lastPoseAt = 0;
    const ANALYSIS_INTERVAL_MS = 1000 / 24; // ~41.67 ms (~24 FPS для анализа)
    const POSE_INTERVAL_MS = 250;           // раз в 0.25 с (250 мс)

    state.camera = new Camera(videoEl, {
      onFrame: async () => {
        if (state.isCameraRunning && state.cameraTarget) {
          const capturedAt = performance.now();
          // Ограничение числа кадров для анализа до ~24 FPS
          if (capturedAt - lastAnalysisAt < ANALYSIS_INTERVAL_MS) {
            return;
          }
          lastAnalysisAt = capturedAt;

          const attempt = state.dynamicAttempt;
          const elapsed = attempt?.startedAt == null ? -1 : capturedAt - attempt.startedAt;
          const capturing = elapsed >= 0 && elapsed < window.omiliaDynamicClip.durationMs;

          if (state.mediaPipeHands) {
            await state.mediaPipeHands.send({ image: videoEl });
          }
          // ОПТИМИЗАЦИЯ: опрашиваем Pose намного реже — раз в 0.25 с
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
          onFrameRender();
        }
      },
      width: 640,
      height: 480,
    });

    state.isCameraRunning = true;
    state.camera.start();
  }

  function stopCamera() {
    state.dynamicAttempt = null;
    if (state.blitz.advanceTimer !== null) {
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

  // Отрисовка кадра и отправка данных в WebSocket
  function onFrameRender() {
    if (!state.isCameraRunning || !state.cameraTarget) return;

    const canvas = state.cameraTarget === 'practice' ? dom.practiceCanvas : dom.blitzCanvas;
    const video = state.cameraTarget === 'practice' ? dom.practiceVideo : dom.blitzVideo;
    if (!canvas || !video) return;

    // Оптимизация canvas: обновляем размеры только при изменении разрешения видео
    if (video.videoWidth && (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight)) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    const ctx = canvas.getContext('2d');
    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const handsData = state.latestHands || [];
    for (const landmarks of handsData) {
      drawHandLandmarks(ctx, landmarks, canvas.width, canvas.height);
    }

    ctx.restore();

    if (getCameraGesture()?.dynamic_hands_count || state.blitz.advanceTimer !== null) return;

    // Если руки не обнаружены в кадре — сразу обновляем подсказку и не шлём пустые кадры на сервер
    if (handsData.length === 0) {
      if (state.cameraTarget === 'practice' && !state.practice.isLearned) {
        if (dom.practiceHudGesture) dom.practiceHudGesture.textContent = '—';
        if (dom.practiceHudScore) dom.practiceHudScore.textContent = 'Покажите руку';
      } else if (state.cameraTarget === 'blitz' && !state.blitz.isGameOver) {
        if (dom.blitzHudGesture) dom.blitzHudGesture.textContent = '—';
        if (dom.blitzHudScore) dom.blitzHudScore.textContent = 'Покажите руку';
      }
      return;
    }

    // СВЕРХБЫСТРЫЙ КЛИЕНТСКИЙ ML-ИНФЕРЕНС (0ms задержка, вычисление прямо в браузере):
    if (state.classifier && handsData.length > 0) {
      const handsMode = handsData.length > 1 ? 2 : 1;
      const clientPred = state.classifier.predict(handsData, state.latestPose, handsMode);
      if (clientPred && clientPred.detected) {
        handleServerPrediction(clientPred);
        return; // Мгновенный отклик без отправки по сети!
      }
    }

    // Фоллбэк: отправка через WebSocket, если клиентский классификатор ещё загружается
    const now = performance.now();
    if (state.ws && state.ws.readyState === WebSocket.OPEN && handsData.length > 0) {
      if (!state.isWsBusy && (now - (state.lastWsSendTime || 0) >= 41)) {
        state.isWsBusy = true;
        state.lastWsSendTime = now;
        if (state.wsTimeout) clearTimeout(state.wsTimeout);
        state.wsTimeout = setTimeout(() => { state.isWsBusy = false; }, 350);

        const payload = {
          hands_data: handsData.map(compactLandmarks),
          pose_landmarks: compactLandmarks(state.latestPose),
        };
        state.ws.send(JSON.stringify(payload));
      }
    }
  }

  function compactLandmarks(landmarks) {
    if (!landmarks) return null;
    return landmarks.map((p) => ({
      x: Math.round(p.x * 10000) / 10000,
      y: Math.round(p.y * 10000) / 10000,
      z: Math.round((p.z || 0) * 10000) / 10000,
    }));
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
    if (pred.type === 'dynamic_clip') {
      handleDynamicResult(pred);
      return;
    }
    if (getCameraGesture()?.dynamic_hands_count || state.blitz.advanceTimer !== null) return;

    const now = performance.now();
    const gestureName = pred.gesture || pred.name || '';
    const predictedName = gestureName.trim().toLowerCase();
    const confidenceVal = pred.confidence !== undefined ? pred.confidence : null;
    const scoreVal = pred.score !== undefined ? pred.score : pred.distance;
    let distText = '';
    if (confidenceVal !== null && confidenceVal > 0) {
      distText = `Точность: ${Math.round(confidenceVal)}%`;
    } else if (scoreVal !== undefined && scoreVal !== null) {
      distText = `Дистанция: ${Number(scoreVal).toFixed(2)}`;
    }

    // --- Обработка в режиме практики (Шаг 2) ---
    if (state.cameraTarget === 'practice' && state.practice.gesture && !state.practice.isLearned) {
      const targetName = state.practice.gesture.name.trim().toLowerCase();

      dom.practiceHudGesture.textContent = gestureName || '—';
      dom.practiceHudScore.textContent = distText;

      const delta = state.practice.lastTimestamp ? (now - state.practice.lastTimestamp) / 1000 : 0.05;
      state.practice.lastTimestamp = now;

      if (predictedName === targetName) {
        dom.practiceCanvas?.parentElement?.classList.add('matching');
        state.practice.holdProgress += delta;
        const progressPct = Math.min(100, Math.round((state.practice.holdProgress / state.practice.holdTarget) * 100));
        dom.practiceHoldFill.style.width = `${progressPct}%`;

        // Жест успешно удержан!
        if (state.practice.holdProgress >= state.practice.holdTarget) {
          state.practice.isLearned = true;
          dom.practiceCanvas?.parentElement?.classList.remove('matching');
          onGestureSuccessfullyLearned(state.practice.gesture);
        }
      } else {
        dom.practiceCanvas?.parentElement?.classList.remove('matching');
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
      dom.blitzHudGesture.textContent = gestureName || '—';
      dom.blitzHudScore.textContent = distText;

      const delta = state.blitz.lastTimestamp ? (now - state.blitz.lastTimestamp) / 1000 : 0.05;
      state.blitz.lastTimestamp = now;

      if (predictedName === targetName) {
        dom.blitzCanvas?.parentElement?.classList.add('matching');
        state.blitz.holdProgress += delta;
        const progressPct = Math.min(100, Math.round((state.blitz.holdProgress / state.blitz.holdTarget) * 100));
        dom.blitzHoldFill.style.width = `${progressPct}%`;

        if (state.blitz.holdProgress >= state.blitz.holdTarget) {
          state.blitz.holdProgress = 0;
          dom.blitzCanvas?.parentElement?.classList.remove('matching');
          completeBlitzQuestion(currentQ);
        }
      } else {
        dom.blitzCanvas?.parentElement?.classList.remove('matching');
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
        const resp = await apiFetch('/api/gestures/learn', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ gesture_name: gesture.name }),
        });
        if (resp && resp.learned_gestures && state.currentUser) {
          state.currentUser.learned_gestures = resp.learned_gestures;
          updateProfileView();
        }
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
        state.currentUser = {
          ...data.user,
          learned_gestures: data.learned_gestures || data.user?.learned_gestures || [],
        };
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
        state.currentUser = {
          ...data.user,
          learned_gestures: data.learned_gestures || data.user?.learned_gestures || [],
        };
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

    // Поиск по словарю жестов
    dom.catalogSearch?.addEventListener('input', (e) => {
      catalogFilters.search = e.target.value;
      if (dom.btnClearSearch) {
        dom.btnClearSearch.style.display = e.target.value ? 'flex' : 'none';
      }
      renderCatalog();
    });

    dom.btnClearSearch?.addEventListener('click', () => {
      if (dom.catalogSearch) dom.catalogSearch.value = '';
      catalogFilters.search = '';
      dom.btnClearSearch.style.display = 'none';
      renderCatalog();
    });

    // Фильтры по категориям
    dom.categoryFilters?.addEventListener('click', (e) => {
      const chip = e.target.closest('.filter-chip');
      if (!chip) return;
      dom.categoryFilters.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      catalogFilters.category = chip.dataset.category || 'all';
      renderCatalog();
    });

    // Переключение зеркалирования камеры
    document.querySelectorAll('.btn-toggle-mirror').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const container = e.target.closest('.camera-container') || document.querySelector('.camera-container');
        if (container) {
          container.classList.toggle('mirrored');
        }
      });
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
    dom.btnDynamicPractice.addEventListener('click', startDynamicAttempt);
    dom.btnPracticeDone?.addEventListener('click', closePracticeModal);

    // Блиц-опрос
    dom.btnStartBlitz?.addEventListener('click', startBlitz);
    dom.btnDynamicBlitz.addEventListener('click', startDynamicAttempt);
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
    if (window.OmiliaInference && window.OmiliaInference.OmiliaStaticClassifier) {
      state.classifier = new window.OmiliaInference.OmiliaStaticClassifier();
    }
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
