/**
 * Project Omiλia — Blitz Quiz Module
 * Режим экспресс-тестирования знаний выученных жестов на время.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Omilia = root.Omilia || {};
    root.Omilia.Blitz = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function setupBlitzIntro(state, dom, onSwitchTab) {
    if (!dom.blitzIntro || !dom.blitzActive || !dom.blitzFinish) return;

    dom.blitzIntro.style.display = 'block';
    dom.blitzActive.style.display = 'none';
    dom.blitzFinish.style.display = 'none';

    if (!state.currentUser) {
      if (dom.blitzEligibility) {
        dom.blitzEligibility.innerHTML = `
          <div style="background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 1rem; border-radius: 8px; font-weight: 500;">
            ⚠️ Для прохождения блиц-опроса необходимо войти в аккаунт.
          </div>
        `;
      }
      if (dom.btnStartBlitz) {
        dom.btnStartBlitz.disabled = true;
        dom.btnStartBlitz.style.opacity = '0.5';
      }
      return;
    }

    const learnedNames = new Set(state.currentUser.learned_gestures || []);
    const learned = state.gestures.filter((g) => learnedNames.has(g.name));

    if (learned.length === 0) {
      if (dom.blitzEligibility) {
        dom.blitzEligibility.innerHTML = `
          <div style="background: #fffbeb; border: 1px solid #fef3c7; color: #92400e; padding: 1rem; border-radius: 8px; font-weight: 500;">
            💡 Для блица выучите хотя бы один жест в <a href="#" style="color: var(--primary-hover); text-decoration: underline;" id="blitz-link-catalog">словаре жестов</a>!
          </div>
        `;
        document.getElementById('blitz-link-catalog')?.addEventListener('click', (e) => {
          e.preventDefault();
          if (onSwitchTab) onSwitchTab('catalog');
        });
      }
      if (dom.btnStartBlitz) {
        dom.btnStartBlitz.disabled = true;
        dom.btnStartBlitz.style.opacity = '0.5';
      }
    } else {
      if (dom.blitzEligibility) {
        dom.blitzEligibility.innerHTML = `
          <div style="background: var(--primary-light); border: 1px solid var(--primary-border); color: var(--primary-hover); padding: 1rem; border-radius: 8px; font-weight: 600;">
            Вам доступно для проверки: <strong>${learned.length}</strong> выученных жестов.
          </div>
        `;
      }
      if (dom.btnStartBlitz) {
        dom.btnStartBlitz.disabled = false;
        dom.btnStartBlitz.style.opacity = '1';
      }
    }
  }

  async function startBlitz(state, dom, onStartCamera) {
    const ui = window.Omilia?.UI;
    try {
      const data = await (ui ? ui.apiFetch('/api/blitz/questions?count=3', {}, state.authToken) : fetch('/api/blitz/questions?count=3').then(r => r.json()));
      if (!data.questions || data.questions.length === 0) {
        alert(data.message || 'Нет доступных вопросов для блица');
        return;
      }

      state.blitz.questions = data.questions;
      state.blitz.currentIndex = 0;
      state.blitz.isActive = true;

      if (dom.blitzIntro) dom.blitzIntro.style.display = 'none';
      if (dom.blitzFinish) dom.blitzFinish.style.display = 'none';
      if (dom.blitzActive) dom.blitzActive.style.display = 'block';

      loadBlitzQuestion(0, state, dom);
      if (onStartCamera) onStartCamera('blitz');
    } catch (err) {
      alert(`Ошибка запуска блиц-опроса: ${err.message}`);
    }
  }

  function loadBlitzQuestion(index, state, dom) {
    if (index >= state.blitz.questions.length) {
      finishBlitz(state, dom, null);
      return;
    }

    state.blitz.currentIndex = index;
    state.blitz.holdProgress = 0;
    state.blitz.lastTimestamp = null;

    const q = state.blitz.questions[index];
    const ui = window.Omilia?.UI;

    if (dom.blitzProgressStep) dom.blitzProgressStep.textContent = `Вопрос ${index + 1} из ${state.blitz.questions.length}`;
    if (dom.blitzTargetTitle) dom.blitzTargetTitle.textContent = `Жест: «${q.title || q.gesture_name}»`;
    if (dom.blitzTargetTip) {
      dom.blitzTargetTip.innerHTML = `💡 Подсказка: ${ui?.escapeHtml(q.tip || 'Покажите жест на камеру') || (q.tip || 'Покажите жест на камеру')}`;
    }

    const isDynamic = Boolean(q.dynamic_hands_count);
    if (dom.btnDynamicBlitz) {
      dom.btnDynamicBlitz.hidden = !isDynamic;
      dom.btnDynamicBlitz.disabled = false;
    }
    if (dom.blitzAttemptStatus) {
      dom.blitzAttemptStatus.textContent = isDynamic
        ? 'Нажмите «Начать попытку» и покажите жест после отсчёта.'
        : 'Покажите требуемый жест и удерживайте его 1.5 секунды';
    }
    if (dom.blitzHudGesture) dom.blitzHudGesture.textContent = isDynamic ? 'Готовьтесь к попытке' : 'Ожидание руки...';
    if (dom.blitzHudScore) dom.blitzHudScore.textContent = isDynamic ? '' : 'Точность: —';
    if (dom.blitzHoldFill?.parentElement) dom.blitzHoldFill.parentElement.hidden = isDynamic;
    if (dom.blitzHoldFill) dom.blitzHoldFill.style.width = '0%';
    if (dom.blitzQuestionSuccess) dom.blitzQuestionSuccess.style.display = 'none';

    if (state.cameraTarget === 'blitz' && state.mediaPipeHands) {
      const targetHands = q.hands_count || q.dynamic_hands_count || 1;
      state.mediaPipeHands.setOptions({ maxNumHands: targetHands });
    }
  }

  function completeBlitzQuestion(question, state, dom, callbacks = {}) {
    if (state.blitz.advanceTimer !== null) return;

    if (dom.blitzQuestionSuccess) dom.blitzQuestionSuccess.style.display = 'flex';
    if (callbacks.playSpeech) {
      callbacks.playSpeech(question.title || question.gesture_name);
    }

    state.blitz.advanceTimer = setTimeout(() => {
      state.blitz.advanceTimer = null;
      loadBlitzQuestion(state.blitz.currentIndex + 1, state, dom);
    }, 1200);
  }

  function finishBlitz(state, dom, onStopCamera, callbacks = {}) {
    if (onStopCamera) onStopCamera();
    state.blitz.isActive = false;

    if (dom.blitzActive) dom.blitzActive.style.display = 'none';
    if (dom.blitzFinish) dom.blitzFinish.style.display = 'block';
    if (dom.blitzFinishDesc) {
      dom.blitzFinishDesc.textContent = `Поздравляем! Вы успешно подтвердили знание всех ${state.blitz.questions.length} жестов в блиц-опросе!`;
    }

    if (callbacks.playSpeech) {
      callbacks.playSpeech('Блиц успешно пройден! Отличная работа!');
    }
  }

  function abortBlitz(state, dom, onStopCamera) {
    if (onStopCamera) onStopCamera();
    state.blitz.isActive = false;
    setupBlitzIntro(state, dom);
  }

  function handleBlitzPrediction(pred, now, delta, state, dom, callbacks = {}) {
    if (!state.blitz.isActive) return;
    const currentQ = state.blitz.questions[state.blitz.currentIndex];
    if (!currentQ) return;

    const gestureName = pred.gesture || pred.name || '';
    const predictedName = gestureName.trim().toLowerCase();
    const targetName = currentQ.gesture_name.trim().toLowerCase();

    const confidenceVal = pred.confidence !== undefined ? pred.confidence : null;
    const scoreVal = pred.score !== undefined ? pred.score : pred.distance;
    let distText = '';
    if (confidenceVal !== null && confidenceVal > 0) {
      distText = `Точность: ${Math.round(confidenceVal)}%`;
    } else if (scoreVal !== undefined && scoreVal !== null) {
      distText = `Дистанция: ${Number(scoreVal).toFixed(2)}`;
    }

    if (dom.blitzHudGesture) dom.blitzHudGesture.textContent = gestureName || '—';
    if (dom.blitzHudScore) dom.blitzHudScore.textContent = distText;

    if (predictedName === targetName) {
      dom.blitzCanvas?.parentElement?.classList.add('matching');
      state.blitz.holdProgress += delta;
      const progressPct = Math.min(100, Math.round((state.blitz.holdProgress / state.blitz.holdTarget) * 100));
      if (dom.blitzHoldFill) dom.blitzHoldFill.style.width = `${progressPct}%`;

      if (state.blitz.holdProgress >= state.blitz.holdTarget) {
        state.blitz.holdProgress = 0;
        dom.blitzCanvas?.parentElement?.classList.remove('matching');
        completeBlitzQuestion(currentQ, state, dom, callbacks);
      }
    } else {
      dom.blitzCanvas?.parentElement?.classList.remove('matching');
      state.blitz.holdProgress = Math.max(0, state.blitz.holdProgress - delta * 1.5);
      const progressPct = Math.min(100, Math.round((state.blitz.holdProgress / state.blitz.holdTarget) * 100));
      if (dom.blitzHoldFill) dom.blitzHoldFill.style.width = `${progressPct}%`;
    }
  }

  return {
    setupBlitzIntro,
    startBlitz,
    loadBlitzQuestion,
    completeBlitzQuestion,
    finishBlitz,
    abortBlitz,
    handleBlitzPrediction,
  };
});
