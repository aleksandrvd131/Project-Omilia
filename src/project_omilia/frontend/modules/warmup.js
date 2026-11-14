/**
 * Project Omiλia — Daily Warmup & SRS Module (US-1)
 * Ежедневная разминка по методике интервального повторения SM-2 с обновлением серий (streak) и XP.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Omilia = root.Omilia || {};
    root.Omilia.Warmup = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function createWarmupState() {
    return {
      isActive: false,
      gestures: [],
      currentIndex: 0,
      holdProgress: 0,
      holdTarget: 1.5,
      lastTimestamp: null,
      advanceTimer: null,
      isFinished: false,
    };
  }

  async function fetchWarmupQueue(state, ui) {
    if (!state.authToken) {
      return { status: 'unauthorized', gestures: [], count: 0, streak: 0 };
    }
    const api = ui || (typeof window !== 'undefined' ? window.Omilia?.UI : null);
    try {
      const data = await (api ? api.apiFetch('/api/gestures/warmup', {}, state.authToken) : (typeof fetch !== 'undefined' ? fetch('/api/gestures/warmup', {
        headers: { Authorization: `Bearer ${state.authToken}` },
      }).then((r) => r.json()) : { gestures: [], count: 0, streak: 0 }));

      return {
        status: 'ok',
        gestures: data.gestures || data.warmup || [],
        count: data.count || (data.gestures ? data.gestures.length : 0),
        streak: typeof data.streak === 'number' ? data.streak : 0,
      };
    } catch (err) {
      console.warn('Ошибка загрузки ежедневной разминки:', err);
      return { status: 'error', gestures: [], count: 0, streak: 0, error: err.message };
    }
  }

  function renderWarmupStep(state, dom) {
    const warmup = state.warmup;
    if (!warmup || !warmup.gestures.length) return;

    const currentGesture = warmup.gestures[warmup.currentIndex];
    warmup.holdProgress = 0;
    warmup.lastTimestamp = null;

    if (dom.warmupProgressStep) {
      dom.warmupProgressStep.textContent = `Жест ${warmup.currentIndex + 1} из ${warmup.gestures.length}`;
    }
    if (dom.warmupTargetTitle) {
      dom.warmupTargetTitle.textContent = `Жест: «${currentGesture.title || currentGesture.name}»`;
    }
    if (dom.warmupTargetTip) {
      dom.warmupTargetTip.textContent = currentGesture.tip
        ? `Подсказка: ${currentGesture.tip}`
        : (currentGesture.description || 'Покажите жест на камеру и удерживайте 1.5 сек.');
    }
    if (dom.warmupHudGesture) dom.warmupHudGesture.textContent = 'Ожидание руки...';
    if (dom.warmupHudScore) dom.warmupHudScore.textContent = 'Точность: —';
    if (dom.warmupHoldFill) dom.warmupHoldFill.style.width = '0%';
    if (dom.warmupQuestionSuccess) dom.warmupQuestionSuccess.style.display = 'none';
    if (dom.warmupFinishOverlay) dom.warmupFinishOverlay.style.display = 'none';

    // Шпаргалка внутри модалки разминки
    if (dom.warmupCheatsheetDesc) {
      dom.warmupCheatsheetDesc.textContent = currentGesture.description || 'Повторяйте правильную форму кисти.';
    }
    if (dom.warmupCheatsheetTip) {
      if (currentGesture.tip) {
        dom.warmupCheatsheetTip.style.display = 'block';
        dom.warmupCheatsheetTip.textContent = `💡 ${currentGesture.tip}`;
      } else {
        dom.warmupCheatsheetTip.style.display = 'none';
      }
    }
    if (dom.warmupCheatsheetContent) {
      dom.warmupCheatsheetContent.style.display = 'none';
    }
    if (dom.btnWarmupCheatsheetToggle) {
      dom.btnWarmupCheatsheetToggle.setAttribute('aria-expanded', 'false');
      const arrow = dom.warmupCheatsheetArrow || dom.btnWarmupCheatsheetToggle.querySelector('.cheatsheet-arrow');
      if (arrow) arrow.textContent = '▾';
    }
  }

  async function startWarmup(state, dom, startCamera, callbacks = {}) {
    state.warmup = state.warmup || createWarmupState();

    if (!state.authToken) {
      if (callbacks.onRequireAuth) {
        callbacks.onRequireAuth();
      } else {
        alert('Для сохранения серии ежедневной разминки и прогресса SM-2 войдите в личный кабинет.');
      }
      return;
    }

    const ui = window.Omilia?.UI;
    const res = await fetchWarmupQueue(state, ui);

    if (res.status === 'ok' && res.gestures.length === 0) {
      if (callbacks.onWarmupEmpty) {
        callbacks.onWarmupEmpty(res.streak);
      } else {
        alert(`Все жесты на сегодня уже повторены! Ваша текущая серия: ${res.streak} 🔥 дн.`);
      }
      return;
    }

    if (res.status === 'error') {
      alert(`Не удалось загрузить разминку: ${res.error || 'Ошибка сервера'}`);
      return;
    }

    state.warmup.isActive = true;
    state.warmup.gestures = res.gestures;
    state.warmup.currentIndex = 0;
    state.warmup.isFinished = false;
    state.warmup.streak = res.streak;

    if (dom.warmupModal) dom.warmupModal.style.display = 'flex';
    if (dom.warmupActiveCard) dom.warmupActiveCard.style.display = 'block';
    if (dom.warmupFinishOverlay) dom.warmupFinishOverlay.style.display = 'none';

    renderWarmupStep(state, dom);

    if (startCamera) {
      startCamera('warmup');
    }
  }

  function abortWarmup(state, dom, stopCamera) {
    if (!state.warmup) return;
    if (state.warmup.advanceTimer !== null) {
      clearTimeout(state.warmup.advanceTimer);
      state.warmup.advanceTimer = null;
    }
    state.warmup.isActive = false;
    state.warmup.gestures = [];
    state.warmup.currentIndex = 0;

    if (dom.warmupModal) dom.warmupModal.style.display = 'none';
    if (dom.warmupDiagnosticHint) dom.warmupDiagnosticHint.style.display = 'none';
    state.currentProblemFingers = [];
    state.isMatchingGesture = false;

    if (stopCamera) stopCamera();
  }

  async function completeWarmupStep(state, dom, callbacks = {}) {
    const warmup = state.warmup;
    if (!warmup || !warmup.isActive || warmup.advanceTimer !== null) return;

    const currentGesture = warmup.gestures[warmup.currentIndex];
    if (dom.warmupQuestionSuccess) dom.warmupQuestionSuccess.style.display = 'flex';

    if (callbacks.playSpeech) {
      callbacks.playSpeech(currentGesture.title || currentGesture.name);
    }

    warmup.advanceTimer = setTimeout(() => {
      advanceWarmup(state, dom, callbacks);
    }, 1200);

    // Фиксация повторения через SM-2 POST /api/gestures/review (если авторизован)
    const ui = typeof window !== 'undefined' ? window.Omilia?.UI : null;
    if (state.authToken) {
      try {
        const reviewPayload = {
          gesture_name: currentGesture.name,
          quality: 5,
        };
        const res = await (ui ? ui.apiFetch('/api/gestures/review', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(reviewPayload),
        }, state.authToken) : (typeof fetch !== 'undefined' ? fetch('/api/gestures/review', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${state.authToken}`,
          },
          body: JSON.stringify(reviewPayload),
        }).then((r) => r.json()) : null));

        if (res && res.streak !== undefined) {
          warmup.streak = res.streak;
          if (state.currentUser) {
            state.currentUser.streak = res.streak;
          }
        }
      } catch (err) {
        console.warn('Ошибка отправки повторения SM-2:', err);
      }
    }
  }

  function advanceWarmup(state, dom, callbacks = {}) {
    const warmup = state.warmup;
    if (!warmup || !warmup.isActive) return;
    if (warmup.advanceTimer !== null) {
      clearTimeout(warmup.advanceTimer);
      warmup.advanceTimer = null;
    }

    warmup.currentIndex++;
    if (warmup.currentIndex < warmup.gestures.length) {
      renderWarmupStep(state, dom);
    } else {
      finishWarmup(state, dom, callbacks);
    }
  }

  function finishWarmup(state, dom, callbacks = {}) {
    const warmup = state.warmup;
    if (!warmup) return;
    warmup.isFinished = true;
    warmup.isActive = false;

    // Начисление +50 XP за ежедневную разминку
    const ui = typeof window !== 'undefined' ? window.Omilia?.UI : null;
    if (ui && ui.addExtraXP) {
      ui.addExtraXP(50);
    }

    if (dom.warmupActiveCard) dom.warmupActiveCard.style.display = 'none';
    if (dom.warmupFinishOverlay) dom.warmupFinishOverlay.style.display = 'flex';

    if (dom.warmupFinishStreakCount) {
      dom.warmupFinishStreakCount.textContent = `${warmup.streak} 🔥`;
    }
    if (dom.warmupFinishDesc) {
      dom.warmupFinishDesc.textContent = `Вы повторили ${warmup.gestures.length} жестов! Серия практики: ${warmup.streak} дней подряд (+50 XP).`;
    }

    if (callbacks.onWarmupFinished) {
      callbacks.onWarmupFinished(warmup.streak, warmup.gestures.length);
    }
  }

  function handleWarmupPrediction(pred, now, delta, state, dom, callbacks = {}) {
    const warmup = state.warmup;
    if (!warmup || !warmup.isActive || warmup.advanceTimer !== null) return;

    const currentGesture = warmup.gestures[warmup.currentIndex];
    if (!currentGesture) return;

    const gestureName = pred.gesture || pred.name || '';
    const predictedName = gestureName.trim().toLowerCase();
    const targetName = currentGesture.name.trim().toLowerCase();

    const confidenceVal = pred.confidence !== undefined ? pred.confidence : null;
    const scoreVal = pred.score !== undefined ? pred.score : pred.distance;
    let distText = '';
    if (confidenceVal !== null && confidenceVal > 0) {
      distText = `Точность: ${Math.round(confidenceVal)}%`;
    } else if (scoreVal !== undefined && scoreVal !== null) {
      distText = `Дистанция: ${Number(scoreVal).toFixed(2)}`;
    }

    if (dom.warmupHudGesture) dom.warmupHudGesture.textContent = gestureName || '—';
    if (dom.warmupHudScore) dom.warmupHudScore.textContent = distText;

    if (predictedName === targetName) {
      dom.warmupCanvas?.parentElement?.classList.add('matching');
      warmup.holdProgress += delta;
      const progressPct = Math.min(100, Math.round((warmup.holdProgress / warmup.holdTarget) * 100));
      if (dom.warmupHoldFill) dom.warmupHoldFill.style.width = `${progressPct}%`;

      if (warmup.holdProgress >= warmup.holdTarget) {
        dom.warmupCanvas?.parentElement?.classList.remove('matching');
        completeWarmupStep(state, dom, callbacks);
      }
    } else {
      dom.warmupCanvas?.parentElement?.classList.remove('matching');
      warmup.holdProgress = Math.max(0, warmup.holdProgress - delta * 1.5);
      const progressPct = Math.min(100, Math.round((warmup.holdProgress / warmup.holdTarget) * 100));
      if (dom.warmupHoldFill) dom.warmupHoldFill.style.width = `${progressPct}%`;
    }
  }

  function toggleWarmupCheatsheet(dom, forceState) {
    if (!dom.warmupCheatsheetContent) return false;
    const isCurrentlyHidden = dom.warmupCheatsheetContent.style.display === 'none';
    const nextOpen = forceState !== undefined ? Boolean(forceState) : isCurrentlyHidden;

    dom.warmupCheatsheetContent.style.display = nextOpen ? 'block' : 'none';
    if (dom.btnWarmupCheatsheetToggle) {
      dom.btnWarmupCheatsheetToggle.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
      const arrow = dom.warmupCheatsheetArrow || dom.btnWarmupCheatsheetToggle.querySelector('.cheatsheet-arrow');
      if (arrow) arrow.textContent = nextOpen ? '▴' : '▾';
    }
    return nextOpen;
  }

  return {
    createWarmupState,
    fetchWarmupQueue,
    startWarmup,
    abortWarmup,
    completeWarmupStep,
    advanceWarmup,
    finishWarmup,
    handleWarmupPrediction,
    toggleWarmupCheatsheet,
    renderWarmupStep,
  };
});
