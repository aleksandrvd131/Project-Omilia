/**
 * Project Omiλia — Practice & Tutorial Module
 * Обучение жестам: просмотр видеоуроков, интерактивная практика перед камерой и фиксация прогресса.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Omilia = root.Omilia || {};
    root.Omilia.Practice = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function openTutorialModal(gesture, state, dom) {
    state.practice.gesture = gesture;
    const ui = window.Omilia?.UI;

    if (dom.tutorialTitle) dom.tutorialTitle.textContent = `Жест: «${gesture.title || gesture.name}»`;
    if (dom.tutorialCategory) dom.tutorialCategory.textContent = gesture.category || 'Общие жесты';
    if (dom.tutorialDesc) dom.tutorialDesc.textContent = gesture.description;
    if (dom.tutorialTip) {
      dom.tutorialTip.innerHTML = `💡 <strong>Подсказка:</strong> ${ui?.escapeHtml(gesture.tip) || gesture.tip}`;
    }

    if (dom.tutorialVideo) {
      const hasVideo = Boolean(gesture.has_video || gesture.video_url);
      if (hasVideo) {
        const videoSrc = gesture.video_url || `/static/videos/${encodeURIComponent(gesture.name.toLowerCase())}.mp4`;
        dom.tutorialVideo.src = videoSrc;
        dom.tutorialVideo.style.display = 'block';
        if (dom.tutorialVideoFallback) dom.tutorialVideoFallback.style.display = 'none';

        dom.tutorialVideo.onerror = () => {
          dom.tutorialVideo.style.display = 'none';
          if (dom.tutorialVideoFallback) {
            dom.tutorialVideoFallback.style.display = 'flex';
            const caption = document.getElementById('tutorial-demo-caption');
            if (caption) {
              caption.textContent = `Схема жеста: ${gesture.title || gesture.name}`;
            }
          }
        };
        dom.tutorialVideo.play().catch(() => {});
      } else {
        dom.tutorialVideo.style.display = 'none';
        dom.tutorialVideo.src = '';
        if (dom.tutorialVideoFallback) {
          dom.tutorialVideoFallback.style.display = 'flex';
          const caption = document.getElementById('tutorial-demo-caption');
          if (caption) {
            caption.textContent = `Схема жеста: ${gesture.title || gesture.name}`;
          }
        }
      }
    }

    if (dom.tutorialModal) dom.tutorialModal.style.display = 'flex';
  }

  function closeTutorialModal(dom) {
    if (dom.tutorialModal) dom.tutorialModal.style.display = 'none';
    if (dom.tutorialVideo) {
      dom.tutorialVideo.pause();
      dom.tutorialVideo.src = '';
    }
  }

  function openPracticeModal(gesture, state, dom, onStartCamera) {
    closeTutorialModal(dom);
    state.practice.gesture = gesture;
    state.practice.holdProgress = 0;
    state.practice.isLearned = false;
    state.practice.lastTimestamp = null;

    if (dom.practiceTitle) dom.practiceTitle.textContent = `Жест: «${gesture.title || gesture.name}»`;
    const isDynamic = Boolean(gesture.dynamic_hands_count);
    if (dom.btnDynamicPractice) {
      dom.btnDynamicPractice.hidden = !isDynamic;
      dom.btnDynamicPractice.disabled = false;
    }
    if (dom.practiceHoldFill?.parentElement) {
      dom.practiceHoldFill.parentElement.hidden = isDynamic;
    }
    if (dom.practiceTipText) {
      dom.practiceTipText.textContent = isDynamic
        ? 'Нажмите «Начать попытку». Покажите жест целиком после отсчёта.'
        : `Покажите жест «${gesture.title || gesture.name}» и удерживайте его 1.5 секунды`;
    }
    if (dom.practiceHudGesture) {
      dom.practiceHudGesture.textContent = isDynamic ? 'Готовьтесь к попытке' : 'Ожидание руки...';
    }
    if (dom.practiceHudScore) {
      dom.practiceHudScore.textContent = isDynamic ? '' : 'Точность: —';
    }
    if (dom.practiceHoldFill) dom.practiceHoldFill.style.width = '0%';
    if (dom.practiceSuccessOverlay) dom.practiceSuccessOverlay.style.display = 'none';

    if (dom.practiceModal) dom.practiceModal.style.display = 'flex';
    if (onStartCamera) onStartCamera('practice');
  }

  function closePracticeModal(state, dom, onStopCamera, callbacks = {}) {
    if (dom.practiceModal) dom.practiceModal.style.display = 'none';
    if (dom.practiceDiagnosticHint) dom.practiceDiagnosticHint.style.display = 'none';
    state.currentProblemFingers = [];
    state.isMatchingGesture = false;

    if (onStopCamera) onStopCamera();
    state.practice.gesture = null;

    if (callbacks.onLoadCatalog) callbacks.onLoadCatalog();
    if (callbacks.onCheckAuth) callbacks.onCheckAuth();
  }

  async function onGestureSuccessfullyLearned(gesture, state, dom, callbacks = {}) {
    if (dom.practiceSuccessOverlay) dom.practiceSuccessOverlay.style.display = 'flex';

    if (callbacks.playSpeech) {
      callbacks.playSpeech(gesture.title || gesture.name);
    }

    if (state.authToken) {
      const ui = window.Omilia?.UI;
      try {
        const resp = await (ui ? ui.apiFetch('/api/gestures/learn', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ gesture_name: gesture.name }),
        }, state.authToken) : fetch('/api/gestures/learn', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${state.authToken}` },
          body: JSON.stringify({ gesture_name: gesture.name }),
        }).then(r => r.json()));

        if (resp && resp.learned_gestures && state.currentUser) {
          state.currentUser.learned_gestures = resp.learned_gestures;
          if (callbacks.updateProfileView) callbacks.updateProfileView();
        }
      } catch (err) {
        console.warn('Ошибка сохранения прогресса:', err);
      }
    }
  }

  function handlePracticePrediction(pred, now, delta, state, dom, callbacks = {}) {
    if (!state.practice.gesture || state.practice.isLearned) return;

    const gestureName = pred.gesture || pred.name || '';
    const predictedName = gestureName.trim().toLowerCase();
    const targetName = state.practice.gesture.name.trim().toLowerCase();

    const confidenceVal = pred.confidence !== undefined ? pred.confidence : null;
    const scoreVal = pred.score !== undefined ? pred.score : pred.distance;
    let distText = '';
    if (confidenceVal !== null && confidenceVal > 0) {
      distText = `Точность: ${Math.round(confidenceVal)}%`;
    } else if (scoreVal !== undefined && scoreVal !== null) {
      distText = `Дистанция: ${Number(scoreVal).toFixed(2)}`;
    }

    if (dom.practiceHudGesture) dom.practiceHudGesture.textContent = gestureName || '—';
    if (dom.practiceHudScore) dom.practiceHudScore.textContent = distText;

    if (predictedName === targetName) {
      dom.practiceCanvas?.parentElement?.classList.add('matching');
      state.practice.holdProgress += delta;
      const progressPct = Math.min(100, Math.round((state.practice.holdProgress / state.practice.holdTarget) * 100));
      if (dom.practiceHoldFill) dom.practiceHoldFill.style.width = `${progressPct}%`;

      if (state.practice.holdProgress >= state.practice.holdTarget) {
        state.practice.isLearned = true;
        dom.practiceCanvas?.parentElement?.classList.remove('matching');
        onGestureSuccessfullyLearned(state.practice.gesture, state, dom, callbacks);
      }
    } else {
      dom.practiceCanvas?.parentElement?.classList.remove('matching');
      state.practice.holdProgress = Math.max(0, state.practice.holdProgress - delta * 1.5);
      const progressPct = Math.min(100, Math.round((state.practice.holdProgress / state.practice.holdTarget) * 100));
      if (dom.practiceHoldFill) dom.practiceHoldFill.style.width = `${progressPct}%`;
    }
  }

  return {
    openTutorialModal,
    closeTutorialModal,
    openPracticeModal,
    closePracticeModal,
    onGestureSuccessfullyLearned,
    handlePracticePrediction,
  };
});
