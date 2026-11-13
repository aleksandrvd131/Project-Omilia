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

  function safeLocalStorageGet(key) {
    try {
      if (typeof window !== 'undefined' && typeof process === 'undefined' && window.localStorage) {
        return window.localStorage.getItem(key);
      }
    } catch {
      // Ignore in mock/restricted environments
    }
    return null;
  }

  async function apiFetch(endpoint, options = {}, authToken = null) {
    options.headers = options.headers || {};
    const token = authToken || safeLocalStorageGet('omilia_token');
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

  function getStreakValue(state) {
    const user = state?.currentUser;
    if (!user) return 0;
    if (typeof user.streak === 'number') return user.streak;
    if (typeof user.current_streak === 'number') return user.current_streak;
    if (typeof user.daily_streak === 'number') return user.daily_streak;
    if (typeof user.streak_days === 'number') return user.streak_days;
    if (typeof state?.streak === 'number') return state.streak;
    return 0;
  }

  function tryFetchStreak(state, dom, onOpenProfile) {
    if (
      !state?.currentUser ||
      !state?.authToken ||
      typeof state.currentUser.streak === 'number' ||
      state._fetchingStreak ||
      typeof fetch === 'undefined'
    ) {
      return;
    }

    state._fetchingStreak = true;
    apiFetch('/api/gestures/warmup', {}, state.authToken)
      .then((data) => {
        if (data && typeof data.streak === 'number') {
          state.currentUser.streak = data.streak;
          const doc = typeof document !== 'undefined' ? document : null;
          const streakCountEl = dom?.streakDaysCount || (doc ? doc.getElementById('streak-days-count') : null);
          const streakBadge = dom?.headerStreakBadge || (doc ? doc.getElementById('header-streak-badge') : null);
          if (streakCountEl) streakCountEl.textContent = String(data.streak);
          if (streakBadge) {
            streakBadge.title = `Дни практики подряд: ${data.streak}`;
            if (streakBadge.classList) {
              streakBadge.classList.toggle('active', data.streak > 0);
            }
          }
          const statStreakEl = dom?.statStreakCount || (doc ? doc.getElementById('stat-streak-count') : null);
          if (statStreakEl) statStreakEl.textContent = `${data.streak} 🔥`;
          renderAchievements(state, dom);
        }
      })
      .catch(() => {
        // Silently ignore if warmup API not implemented or offline
      })
      .finally(() => {
        state._fetchingStreak = false;
      });
  }

  function computeAchievements(state) {
    const user = state?.currentUser;
    const learned = (user && Array.isArray(user.learned_gestures)) ? user.learned_gestures : [];
    const learnedCount = learned.length;

    const streak = getStreakValue(state);

    const blitzCompletions = (user?.blitz_completions || user?.blitz_count || state?.blitzCompletions || 0);
    const doc = (typeof document !== 'undefined') ? document : null;
    const domBlitzFinish = doc ? doc.getElementById('blitz-finish') : null;
    const isDomBlitzFinished = domBlitzFinish && domBlitzFinish.style && domBlitzFinish.style.display === 'block';

    const blitzCompleted = Boolean(
      blitzCompletions > 0 ||
      user?.blitz_completed ||
      user?.has_completed_blitz ||
      state?.blitzCompleted ||
      isDomBlitzFinished ||
      safeLocalStorageGet('omilia_blitz_completed') === 'true' ||
      (user?.username && safeLocalStorageGet(`omilia_blitz_${user.username}`) === 'true')
    );

    return [
      {
        id: 'first_word',
        title: 'Первое слово',
        desc: 'Выучен 1 жест',
        icon: '👋',
        unlocked: learnedCount >= 1,
        progress: `${Math.min(1, learnedCount)} / 1`,
      },
      {
        id: 'expert_5',
        title: 'Знаток',
        desc: 'Выучено 5 жестов',
        icon: '📚',
        unlocked: learnedCount >= 5,
        progress: `${Math.min(5, learnedCount)} / 5`,
      },
      {
        id: 'blitz_sniper',
        title: 'Снайпер блица',
        desc: 'Пройден блиц-опрос',
        icon: '🎯',
        unlocked: blitzCompleted,
        progress: blitzCompleted ? 'Пройден' : '0 / 1',
      },
      {
        id: 'master_10',
        title: 'Мастер РЖЯ',
        desc: 'Выучено 10+ жестов',
        icon: '👑',
        unlocked: learnedCount >= 10,
        progress: `${Math.min(10, learnedCount)} / 10`,
      },
      {
        id: 'streak_3',
        title: 'Ударный режим',
        desc: 'Серия занятий 3+ дня',
        icon: '🔥',
        unlocked: streak >= 3,
        progress: `${Math.min(3, streak)} / 3 дн.`,
      },
    ];
  }

  function renderAchievements(state, dom) {
    const achievements = computeAchievements(state);
    const doc = typeof document !== 'undefined' ? document : null;

    const counterEl = dom?.profileAchievementsCounter || (doc ? doc.getElementById('profile-achievements-counter') : null);
    const unlockedCount = achievements.filter((a) => a.unlocked).length;
    if (counterEl) {
      counterEl.textContent = `${unlockedCount} / ${achievements.length}`;
    }

    const gridEl = dom?.profileAchievementsGrid || (doc ? doc.getElementById('profile-achievements-grid') : null);
    if (!gridEl) return;

    if (!doc || typeof doc.createElement !== 'function') {
      gridEl.innerHTML = achievements.map((ach) => `
        <div class="achievement-card ${ach.unlocked ? 'unlocked' : 'locked'}" data-achievement-id="${ach.id}" id="badge-${ach.id}">
          <div class="achievement-icon">${ach.icon}</div>
          <div class="achievement-title">${escapeHtml(ach.title)}</div>
          <div class="achievement-desc">${escapeHtml(ach.desc)}</div>
          <div class="achievement-status">${ach.unlocked ? '✓ Получено' : `🔒 ${escapeHtml(ach.progress)}`}</div>
        </div>
      `).join('');
      return;
    }

    gridEl.innerHTML = '';
    achievements.forEach((ach) => {
      const card = doc.createElement('div');
      card.className = `achievement-card ${ach.unlocked ? 'unlocked' : 'locked'}`;
      card.dataset.achievementId = ach.id;
      card.id = `badge-${ach.id}`;

      card.innerHTML = `
        <div class="achievement-icon" title="${ach.unlocked ? 'Достижение разблокировано' : 'Заблокировано'}">
          ${ach.icon}
        </div>
        <div class="achievement-title">${escapeHtml(ach.title)}</div>
        <div class="achievement-desc">${escapeHtml(ach.desc)}</div>
        <div class="achievement-status">
          ${ach.unlocked ? '✓ Получено' : `🔒 ${escapeHtml(ach.progress)}`}
        </div>
      `;
      gridEl.appendChild(card);
    });
  }

  function updateUserHeader(state, dom, onOpenProfile) {
    const doc = typeof document !== 'undefined' ? document : null;
    const headerUserArea = dom?.headerUserArea || (doc ? doc.getElementById('header-user-area') : null);
    if (headerUserArea) {
      if (state.currentUser) {
        headerUserArea.innerHTML = `
          <div class="user-badge" id="btn-header-profile" title="Перейти в личный кабинет">
            <span>👤</span>
            <span>${escapeHtml(state.currentUser.username)}</span>
          </div>
        `;
        if (doc) {
          doc.getElementById('btn-header-profile')?.addEventListener('click', () => {
            if (onOpenProfile) onOpenProfile();
          });
        }
      } else {
        headerUserArea.innerHTML = `
          <button class="btn-login" id="btn-header-login">Войти в ЛК</button>
        `;
        if (doc) {
          doc.getElementById('btn-header-login')?.addEventListener('click', () => {
            if (onOpenProfile) onOpenProfile();
          });
        }
      }
    }

    // Обновление бейджа ударного режима (streak) в шапке
    const streakBadge = dom?.headerStreakBadge || (doc ? doc.getElementById('header-streak-badge') : null);
    const streakCountEl = dom?.streakDaysCount || (doc ? doc.getElementById('streak-days-count') : null);
    const streak = getStreakValue(state);

    if (streakCountEl) {
      streakCountEl.textContent = String(streak);
    }
    if (streakBadge) {
      streakBadge.title = `Дни практики подряд: ${streak}`;
      if (streakBadge.classList) {
        streakBadge.classList.toggle('active', streak > 0);
      }
      streakBadge.onclick = () => {
        if (onOpenProfile) onOpenProfile();
      };
    }

    // Если авторизован, пробуем подтянуть свежий streak из API
    tryFetchStreak(state, dom, onOpenProfile);
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

      if (dom.statLearnedCount) dom.statLearnedCount.textContent = String(learned.length);
      if (dom.statTotalCount) dom.statTotalCount.textContent = String(state.gestures.length);
      if (dom.statPercentCount) dom.statPercentCount.textContent = `${percent}%`;

      const streak = getStreakValue(state);
      const doc = typeof document !== 'undefined' ? document : null;
      const statStreakEl = dom.statStreakCount || (doc ? doc.getElementById('stat-streak-count') : null);
      if (statStreakEl) {
        statStreakEl.textContent = `${streak} 🔥`;
      }

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
          if (doc) {
            doc.getElementById('link-to-catalog')?.addEventListener('click', (e) => {
              e.preventDefault();
              if (onGoToCatalog) onGoToCatalog();
            });
          }
        } else {
          learned.forEach((gname) => {
            if (doc && typeof doc.createElement === 'function') {
              const badge = doc.createElement('span');
              badge.className = 'gesture-badge badge-learned';
              badge.style.padding = '0.4rem 0.85rem';
              badge.style.fontSize = '0.88rem';
              badge.innerHTML = `✓ ${escapeHtml(gname)}`;
              dom.profileLearnedBadges.appendChild(badge);
            }
          });
        }
      }

      // Отрисовка бейджей достижений (Achievements)
      renderAchievements(state, dom);
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
    computeAchievements,
    renderAchievements,
    getStreakValue,
  };
});
