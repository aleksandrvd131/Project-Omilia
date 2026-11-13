/**
 * Project Omiλia — UI & Helper Module
 * Вспомогательные функции DOM, синтеза речи (TTS), API-запросов и профиля.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Omilia = root.Omilia || {};
    root.Omilia.UI = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function apiFetch(endpoint, options = {}, authToken = null) {
    options.headers = options.headers || {};
    const token = authToken || localStorage.getItem('omilia_token');
    if (token) {
      options.headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(endpoint, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || `Ошибка сервера: ${res.status}`);
    }
    return data;
  }

  function playSpeech(text, ttsEnabled = true) {
    if (!ttsEnabled || !text) return;
    try {
      const audio = new Audio(`/api/tts?text=${encodeURIComponent(text)}`);
      audio.play().catch(() => {
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

  function switchTab(tabId, state, dom, callbacks = {}) {
    state.activeTab = tabId;

    if (tabId !== 'blitz' && state.cameraTarget === 'blitz' && callbacks.onAbortBlitz) {
      callbacks.onAbortBlitz();
    }

    dom.navBtns?.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    dom.tabContents?.forEach((content) => {
      content.classList.toggle('active', content.id === `tab-${tabId}`);
    });

    if (tabId === 'catalog' && callbacks.onLoadCatalog) {
      callbacks.onLoadCatalog();
    } else if (tabId === 'blitz' && callbacks.onSetupBlitz) {
      callbacks.onSetupBlitz();
    } else if (tabId === 'profile' && callbacks.onUpdateProfile) {
      callbacks.onUpdateProfile();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function updateUserHeader(state, dom, onOpenProfile) {
    if (!dom.headerUserArea) return;
    if (state.currentUser) {
      dom.headerUserArea.innerHTML = `
        <div class="user-badge" id="btn-header-profile" title="Перейти в личный кабинет">
          <span>👤</span>
          <span>${escapeHtml(state.currentUser.username)}</span>
        </div>
      `;
      document.getElementById('btn-header-profile')?.addEventListener('click', () => {
        if (onOpenProfile) onOpenProfile();
      });
    } else {
      dom.headerUserArea.innerHTML = `
        <button class="btn-login" id="btn-header-login">Войти в ЛК</button>
      `;
      document.getElementById('btn-header-login')?.addEventListener('click', () => {
        if (onOpenProfile) onOpenProfile();
      });
    }
  }

  function updateProfileView(state, dom, onGoToCatalog) {
    if (!dom.authBox || !dom.profileBox) return;

    if (state.currentUser) {
      dom.authBox.style.display = 'none';
      dom.profileBox.style.display = 'block';
      if (dom.profileUsername) dom.profileUsername.textContent = state.currentUser.username;

      if (dom.ttsToggle) {
        dom.ttsToggle.checked = state.settings.ttsEnabled;
      }

      const total = state.gestures.length || 1;
      const learned = state.currentUser.learned_gestures || [];
      const percent = Math.min(100, Math.round((learned.length / total) * 100));

      if (dom.statLearnedCount) dom.statLearnedCount.textContent = learned.length;
      if (dom.statTotalCount) dom.statTotalCount.textContent = state.gestures.length;
      if (dom.statPercentCount) dom.statPercentCount.textContent = `${percent}%`;

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

      if (dom.profileProgressBar) dom.profileProgressBar.style.width = `${percent}%`;
      if (dom.profileProgressText) dom.profileProgressText.textContent = `${percent}%`;
      if (dom.profileStatsSummary) {
        dom.profileStatsSummary.textContent = `Вы выучили ${learned.length} из ${state.gestures.length} доступных жестов`;
      }

      if (dom.profileLearnedBadges) {
        dom.profileLearnedBadges.innerHTML = '';
        if (learned.length === 0) {
          dom.profileLearnedBadges.innerHTML = `
            <div style="color: var(--text-muted); font-size: 0.9rem;">
              Пока нет выученных жестов. Перейдите в <a href="#" style="color: var(--primary-hover); text-decoration: underline;" id="link-to-catalog">словарь жестов</a>, чтобы начать обучение!
            </div>
          `;
          document.getElementById('link-to-catalog')?.addEventListener('click', (e) => {
            e.preventDefault();
            if (onGoToCatalog) onGoToCatalog();
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
      }
    } else {
      dom.authBox.style.display = 'block';
      dom.profileBox.style.display = 'none';
    }
  }

  return {
    escapeHtml,
    apiFetch,
    playSpeech,
    switchTab,
    updateUserHeader,
    updateProfileView,
  };
});
