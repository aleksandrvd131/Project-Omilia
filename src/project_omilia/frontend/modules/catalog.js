/**
 * Голос рук — Catalog Module
 * Загрузка, фильтрация, поиск, дерево курсов (Roadmap) и отрисовка карточек жестов по уровням.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Omilia = root.Omilia || {};
    root.Omilia.Catalog = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Структура формальных уровней учебной программы
  const CURRICULUM_LEVELS = [
    {
      level: 1,
      title: 'Дактильный алфавит',
      badge: '🔤',
      description: 'Буквы дактильного алфавита РЖЯ (А, Б, В, ...)',
      unlockThreshold: 0.0, // Всегда открыт
    },
    {
      level: 2,
      title: 'Числительные и счёт',
      badge: '🔢',
      description: 'Базовые числа и счёт на пальцах (1, 2, 3, ...)',
      unlockThreshold: 0.7, // Открывается при изучении >= 70% Уровня 1
    },
    {
      level: 3,
      title: 'Базовый этикет',
      badge: '🤝',
      description: 'Приветствия, вежливость и базовый контакт (Привет, Спасибо, Да, Нет, ...)',
      unlockThreshold: 0.7, // Открывается при изучении >= 70% Уровня 2
    },
    {
      level: 4,
      title: 'Семья и окружение',
      badge: '🏡',
      description: 'Семья, дом, близкие и окружающий мир (Дом, Мама, Папа, Я, Ты, ...)',
      unlockThreshold: 0.7, // Открывается при изучении >= 70% Уровня 3
    },
  ];

  const LEVEL_TITLES = {
    1: 'Дактильный алфавит',
    2: 'Числительные и счёт',
    3: 'Базовый этикет',
    4: 'Семья и окружение',
  };

  const filters = {
    search: '',
    category: 'all',
    level: 'all', // 'all' | 1 | 2 | 3 | 4
  };

  let isLoading = false;

  /**
   * Определение уровня и названия уровня для жеста.
   */
  function getGestureLevelInfo(gesture) {
    if (!gesture) {
      return { level: 3, level_title: 'Базовый этикет' };
    }

    if (typeof gesture === 'string') {
      gesture = { name: gesture };
    }

    if (gesture.level && gesture.level_title) {
      return {
        level: Number(gesture.level),
        level_title: String(gesture.level_title),
      };
    }

    const level = Number(gesture.level) || 3;
    return {level, level_title: LEVEL_TITLES[level] || LEVEL_TITLES[3]};
  }

  /**
   * Подсчёт статистики и расчёт логики разблокировки уровней:
   * Level 1: всегда открыт.
   * Level 2..4: открывается, если предыдущий уровень изучен не менее чем на 70%.
   */
  function calculateLevelStats(gestures) {
    const stats = {};
    for (const lvl of CURRICULUM_LEVELS) {
      stats[lvl.level] = {
        level: lvl.level,
        title: lvl.title,
        badge: lvl.badge,
        description: lvl.description,
        unlockThreshold: lvl.unlockThreshold,
        total: 0,
        learned: 0,
        percentage: 0,
        isUnlocked: false,
        isCompleted: false,
      };
    }

    (gestures || []).forEach((g) => {
      const info = g._levelInfo || getGestureLevelInfo(g);
      g._levelInfo = info;
      g.level = info.level;
      g.level_title = info.level_title;

      if (stats[info.level]) {
        stats[info.level].total += 1;
        if (g.is_learned) {
          stats[info.level].learned += 1;
        }
      }
    });

    let prevUnlocked = true;
    let prevRatio = 1.0;

    for (const lvl of CURRICULUM_LEVELS) {
      const st = stats[lvl.level];
      const ratio = st.total > 0 ? (st.learned / st.total) : 0;
      st.percentage = Math.round(ratio * 100);
      st.isCompleted = st.total > 0 && st.learned === st.total;

      if (lvl.level === 1) {
        st.isUnlocked = true;
      } else {
        const prevTotal = stats[lvl.level - 1].total;
        // Открывается, если предыдущий уровень открыт и пройден >= 70% (или пуст в базе)
        st.isUnlocked = prevUnlocked && (prevRatio >= lvl.unlockThreshold || prevTotal === 0);
      }

      prevUnlocked = st.isUnlocked;
      prevRatio = ratio;
    }

    return stats;
  }

  /**
   * Фильтрация жестов с учётом поиска, категорий и уровней.
   */
  function getFilteredGestures(gestures) {
    const q = filters.search.trim().toLowerCase();
    const cat = filters.category;
    const lvl = filters.level;

    return (gestures || []).filter((g) => {
      if (!g._levelInfo) {
        g._levelInfo = getGestureLevelInfo(g);
        g.level = g._levelInfo.level;
        g.level_title = g._levelInfo.level_title;
      }

      // 1. Фильтр по уровню
      if (lvl !== 'all' && Number(lvl) !== g._levelInfo.level) {
        return false;
      }

      // 2. Фильтр по категории
      if (cat === 'learned' && !g.is_learned) return false;
      if (cat !== 'all' && cat !== 'learned') {
        const gCat = (g.category || '').toLowerCase();
        const fCat = String(cat).toLowerCase();
        if (gCat !== fCat && !gCat.includes(fCat) && !fCat.includes(gCat)) {
          return false;
        }
      }

      // 3. Текстовый поиск
      if (q) {
        const title = (g.title || g.name || '').toLowerCase();
        const desc = (g.description || '').toLowerCase();
        const tip = (g.tip || '').toLowerCase();
        const levelTitle = (g._levelInfo.level_title || '').toLowerCase();
        if (!title.includes(q) && !desc.includes(q) && !tip.includes(q) && !levelTitle.includes(q)) {
          return false;
        }
      }
      return true;
    });
  }

  /**
   * Создание контейнеров маршрута обучения и фильтров уровней.
   */
  function ensureCurriculumDOM(dom) {
    if (typeof document === 'undefined') return { roadmap: null, levelFilters: null };

    // 1. Контейнер дорожной карты
    let roadmap = document.getElementById('catalog-roadmap');
    if (!roadmap) {
      roadmap = document.createElement('details');
      roadmap.id = 'catalog-roadmap';
      roadmap.className = 'catalog-roadmap-view';

      const controls = document.querySelector('.catalog-controls');
      if (controls && controls.parentNode) {
        controls.parentNode.insertBefore(roadmap, controls.nextSibling);
      } else if (dom.gesturesGrid && dom.gesturesGrid.parentNode) {
        dom.gesturesGrid.parentNode.insertBefore(roadmap, dom.gesturesGrid);
      }
    }

    // 2. Контейнер чипов уровней
    let levelFilters = document.getElementById('level-filters');
    if (!levelFilters) {
      levelFilters = document.createElement('div');
      levelFilters.id = 'level-filters';
      levelFilters.className = 'level-filter-bar';

      const catFilters = dom.categoryFilters || document.getElementById('category-filters');
      if (catFilters && catFilters.parentNode) {
        catFilters.parentNode.insertBefore(levelFilters, catFilters);
      }
    }

    return { roadmap, levelFilters };
  }

  /**
   * Отрисовка интерактивной дорожной карты уровней (Roadmap) с бейджами и прогрессом.
   */
  function renderRoadmapView(state, dom, levelStats, onOpenTutorial) {
    const { roadmap } = ensureCurriculumDOM(dom);
    if (!roadmap) return;

    roadmap.innerHTML = `
      <summary class="roadmap-header">
        <div>
          <div class="roadmap-title">

            <span>Маршрут обучения · 4 уровня</span>
          </div>
          <div class="roadmap-subtitle">
            Изучите дактильный алфавит и счёт, чтобы разблокировать базовый этикет и расширенные жесты
          </div>
        </div>
        <span class="roadmap-toggle" aria-hidden="true">+</span>
      </summary>
      <div class="roadmap-grid">
        ${CURRICULUM_LEVELS.map((lvl) => {
          const st = levelStats[lvl.level] || {
            total: 0,
            learned: 0,
            percentage: 0,
            isUnlocked: lvl.level === 1,
            isCompleted: false,
          };

          let statusBadge = '';
          if (!st.isUnlocked) {
            statusBadge = '<span class="level-card-status status-locked">Закрыт</span>';
          } else if (st.isCompleted) {
            statusBadge = '<span class="level-card-status status-completed">Завершён</span>';
          } else if (st.percentage >= 70) {
            statusBadge = `<span class="level-card-status status-completed">✓ Освоен (${st.percentage}%)</span>`;
          } else if (st.learned > 0) {
            statusBadge = `<span class="level-card-status status-in-progress">В процессе (${st.percentage}%)</span>`;
          } else {
            statusBadge = '<span class="level-card-status status-unlocked">Доступен</span>';
          }

          const lockHint = !st.isUnlocked
            ? `<div class="level-lock-hint">Требуется ≥ 70% Уровня ${lvl.level - 1}</div>`
            : '';

          const isActive = filters.level === lvl.level;
          const cardClass = `level-card ${st.isUnlocked ? '' : 'locked'} ${isActive ? 'active' : ''}`;

          return `
            <button type="button" class="${cardClass}" data-level="${lvl.level}" aria-pressed="${isActive}">
              <div class="level-card-top">
                <span class="level-card-badge">${lvl.level}</span>
                ${statusBadge}
              </div>
              <span class="level-card-title">${lvl.title}</span>
              <div class="level-card-desc">${lvl.description}</div>
              <div>
                <div class="level-progress-bar">
                  <div class="level-progress-fill ${st.isUnlocked ? '' : 'locked'}" style="width: ${st.percentage}%;"></div>
                </div>
                <div class="level-card-stats">
                  <span>Выучено: ${st.learned}/${st.total}</span>
                  <span>${st.percentage}%</span>
                </div>
                ${lockHint}
              </div>
            </button>
          `;
        }).join('')}
      </div>
    `;

    // Клик по карточке уровня переключает фильтр уровня
    roadmap.querySelectorAll('.level-card').forEach((card) => {
      card.addEventListener('click', () => {
        const lvlNum = Number(card.dataset.level);
        if (filters.level === lvlNum) {
          filters.level = 'all';
        } else {
          filters.level = lvlNum;
        }

        // Синхронизация чипов уровней
        document.querySelectorAll('#level-filters .filter-chip').forEach((c) => {
          c.classList.toggle('active', c.dataset.level === String(filters.level));
        });

        renderCatalog(state, dom, onOpenTutorial);
      });
    });
  }

  /**
   * Отрисовка чипов фильтрации по уровням рядом с категориями.
   */
  function renderLevelFilterChips(state, dom, onOpenTutorial, levelStats) {
    const { levelFilters } = ensureCurriculumDOM(dom);
    if (!levelFilters) return;

    const totalAll = (state.gestures || []).length;
    const l1 = levelStats?.[1]?.total ?? 0;
    const l2 = levelStats?.[2]?.total ?? 0;
    const l3 = levelStats?.[3]?.total ?? 0;
    const l4 = levelStats?.[4]?.total ?? 0;

    levelFilters.innerHTML = `
      <span class="level-filter-label">Уровень:</span>
      <button class="filter-chip ${filters.level === 'all' ? 'active' : ''}" data-level="all">Все уровни ${totalAll > 0 ? `(${totalAll})` : ''}</button>
      <button class="filter-chip ${filters.level == 1 ? 'active' : ''}" data-level="1">Ур. 1: Дактиль ${l1 > 0 ? `(${l1})` : ''}</button>
      <button class="filter-chip ${filters.level == 2 ? 'active' : ''}" data-level="2">Ур. 2: Счёт ${l2 > 0 ? `(${l2})` : ''}</button>
      <button class="filter-chip ${filters.level == 3 ? 'active' : ''}" data-level="3">Ур. 3: Этикет ${l3 > 0 ? `(${l3})` : ''}</button>
      <button class="filter-chip ${filters.level == 4 ? 'active' : ''}" data-level="4">Ур. 4: Семья ${l4 > 0 ? `(${l4})` : ''}</button>
    `;

    levelFilters.querySelectorAll('.filter-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        levelFilters.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');

        filters.level = chip.dataset.level === 'all' ? 'all' : Number(chip.dataset.level);
        renderCatalog(state, dom, onOpenTutorial);
      });
    });
  }

  /**
   * Отрисовка и синхронизация чипов категорий со счётчиками жестов.
   */
  function updateCategoryFilterChips(state, dom, onOpenTutorial) {
    const catContainer = dom.categoryFilters || document.getElementById('category-filters');
    if (!catContainer) return;

    const categoryCounts = {};
    (state.gestures || []).forEach((g) => {
      const c = (g.category || 'Общие жесты').trim();
      categoryCounts[c] = (categoryCounts[c] || 0) + 1;
    });

    if (Object.keys(categoryCounts).length === 0) {
      categoryCounts['Дактиль (Алфавит)'] = 0;
      categoryCounts['Числительные'] = 0;
      categoryCounts['Базовый этикет'] = 0;
      categoryCounts['Семья и окружение'] = 0;
    }

    const currentCat = filters.category;
    let chipsHtml = `
      <button class="filter-chip ${currentCat === 'all' ? 'active' : ''}" data-category="all">Все жесты</button>
    `;

    const primaryOrder = [
      'Дактиль (Алфавит)',
      'Числительные',
      'Базовый этикет',
      'Приветствия',
      'Вежливость',
      'Базовые',
      'Семья и окружение',
      'Семья',
      'Общие жесты',
    ];

    const sortedCats = Object.keys(categoryCounts).sort((a, b) => {
      const idxA = primaryOrder.indexOf(a);
      const idxB = primaryOrder.indexOf(b);
      if (idxA !== -1 && idxB !== -1) return idxA - idxB;
      if (idxA !== -1) return -1;
      if (idxB !== -1) return 1;
      return a.localeCompare(b);
    });

    sortedCats.forEach((c) => {
      const cnt = categoryCounts[c] || 0;
      chipsHtml += `
        <button class="filter-chip ${currentCat === c ? 'active' : ''}" data-category="${c}">
          ${c} ${cnt > 0 ? `(${cnt})` : ''}
        </button>
      `;
    });

    const learnedCount = (state.gestures || []).filter((g) => g.is_learned).length;
    chipsHtml += `
      <button class="filter-chip ${currentCat === 'learned' ? 'active' : ''}" data-category="learned">
        ✓ Только выученные ${learnedCount > 0 ? `(${learnedCount})` : ''}
      </button>
    `;

    catContainer.innerHTML = chipsHtml;

    catContainer.querySelectorAll('.filter-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        catContainer.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        filters.category = chip.dataset.category;
        renderCatalog(state, dom, onOpenTutorial);
      });
    });
  }

  /**
   * Загрузка каталога с бэкенда и отрисовка.
   */
  async function loadCatalog(state, dom, onOpenTutorial) {
    if (isLoading) return;
    isLoading = true;
    const ui = window.Omilia?.UI;

    try {
      const data = await ui.apiFetch('/api/gestures', {}, state.authToken);
      state.gestures = data.gestures || [];

      if (dom.catalogLearnedCounter) {
        const total = data.total_available ?? data.total_count ?? (state.gestures ? state.gestures.length : 0);
        const learned = data.total_learned ?? data.learned_count ?? (state.gestures ? state.gestures.filter((g) => g.is_learned).length : 0);
        dom.catalogLearnedCounter.textContent = `Выучено: ${learned} из ${total}`;
      }

      renderCatalog(state, dom, onOpenTutorial);
    } catch (err) {
      if (dom.gesturesGrid) {
        dom.gesturesGrid.innerHTML = `
          <div style="grid-column: 1 / -1; text-align: center; color: var(--danger); padding: 2rem;">
            Не удалось загрузить каталог: ${ui?.escapeHtml(err.message) || err.message}
          </div>
        `;
      }
    } finally {
      isLoading = false;
    }
  }

  /**
   * Отрисовка каталога жестов, дорожной карты и фильтров.
   */
  function renderCatalog(state, dom, onOpenTutorial) {
    if (!dom.gesturesGrid) return;
    const ui = window.Omilia?.UI;

    // Рассчитываем уровни и статистику
    const levelStats = calculateLevelStats(state.gestures);

    // Отрисовываем компоненты дорожной карты и чипов уровней
    renderRoadmapView(state, dom, levelStats, onOpenTutorial);
    renderLevelFilterChips(state, dom, onOpenTutorial, levelStats);
    updateCategoryFilterChips(state, dom, onOpenTutorial);

    dom.gesturesGrid.innerHTML = '';

    if (!state.gestures || state.gestures.length === 0) {
      dom.gesturesGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 3rem;">
          В датасете пока нет записанных жестов. Используйте <a href="/dev" style="color: var(--primary);">панель разработчика</a> для записи.
        </div>
      `;
      return;
    }

    const filtered = getFilteredGestures(state.gestures);
    if (filtered.length === 0) {
      dom.gesturesGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 3rem;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔍</div>
          <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.35rem;">Ничего не найдено</h3>
          <p style="font-size: 0.9rem;">Попробуйте изменить поисковый запрос, сбросить категорию или фильтр уровня.</p>
          <button class="btn-hero-secondary" id="btn-reset-filters" style="margin-top: 1rem; padding: 0.45rem 1.15rem;">
            Сбросить фильтры
          </button>
        </div>
      `;
      document.getElementById('btn-reset-filters')?.addEventListener('click', () => {
        filters.search = '';
        filters.category = 'all';
        filters.level = 'all';
        if (dom.catalogSearch) dom.catalogSearch.value = '';
        if (dom.btnClearSearch) dom.btnClearSearch.style.display = 'none';

        dom.categoryFilters?.querySelectorAll('.filter-chip').forEach((c) => {
          c.classList.toggle('active', c.dataset.category === 'all');
        });
        document.querySelectorAll('#level-filters .filter-chip').forEach((c) => {
          c.classList.toggle('active', c.dataset.level === 'all');
        });

        renderCatalog(state, dom, onOpenTutorial);
      });
      return;
    }

    filtered.forEach((gesture) => {
      const isLevelUnlocked = levelStats[gesture.level]?.isUnlocked ?? true;
      const card = document.createElement('div');
      card.className = `gesture-card ${gesture.is_learned ? 'learned' : ''} ${!isLevelUnlocked ? 'level-locked' : ''}`;

      const handsBadge = gesture.dynamic_hands_count
        ? 'В движении'
        : (gesture.hands_count === 2 ? '2 руки' : '1 рука');

      const lockBanner = !isLevelUnlocked
        ? `<div class="gesture-lock-banner">

             <span>Уровень ${gesture.level} заблокирован (требуется ≥ 70% Уровня ${gesture.level - 1})</span>
           </div>`
        : '';

      const isReady = gesture.is_ready !== false;
      const btnText = !isReady
        ? 'Эталоны ещё записываются'
        : !isLevelUnlocked
        ? (gesture.is_learned ? 'Повторить жест ↺' : `Изучить (Ур. ${gesture.level})`)
        : (gesture.is_learned ? 'Повторить жест ↺' : 'Изучить жест →');

      card.innerHTML = `
        <div>
          <div class="gesture-top">
            <span class="gesture-badge ${gesture.is_learned ? 'badge-learned' : 'badge-unlearned'}">
              ${gesture.is_learned ? '✓ Выучен' : 'Не изучен'}
            </span>
            <div class="gesture-meta">
              <span class="gesture-level-tag">Ур. ${gesture.level}</span>
              <span class="gesture-hands">
                ${handsBadge}
              </span>
              <span style="font-size: 0.78rem; color: var(--text-muted);">${ui?.escapeHtml(gesture.category)}</span>
            </div>
          </div>
          <h3 class="gesture-title">${ui?.escapeHtml(gesture.title || gesture.name)}</h3>
          <p class="gesture-desc">${ui?.escapeHtml(gesture.description)}</p>
          <div class="gesture-tip">
            ${ui?.escapeHtml(gesture.tip)}
          </div>
          ${lockBanner}
        </div>
        <div style="margin-top: 1rem;">
          <button class="btn-practice" data-name="${ui?.escapeHtml(gesture.name)}" ${isReady ? '' : 'disabled'}>
            ${btnText}
          </button>
        </div>
      `;

      card.querySelector('.btn-practice')?.addEventListener('click', () => {
        if (onOpenTutorial) onOpenTutorial(gesture);
      });

      dom.gesturesGrid.appendChild(card);
    });
  }

  /**
   * Настройка обработчиков событий для поиска, категорий и фильтров уровней.
   */
  function setupCatalogFilters(state, dom, onOpenTutorial) {
    ensureCurriculumDOM(dom);
    const levelStats = calculateLevelStats(state.gestures);
    renderLevelFilterChips(state, dom, onOpenTutorial, levelStats);
    updateCategoryFilterChips(state, dom, onOpenTutorial);

    dom.catalogSearch?.addEventListener('input', (e) => {
      filters.search = e.target.value;
      if (dom.btnClearSearch) {
        dom.btnClearSearch.style.display = filters.search ? 'block' : 'none';
      }
      renderCatalog(state, dom, onOpenTutorial);
    });

    dom.btnClearSearch?.addEventListener('click', () => {
      filters.search = '';
      if (dom.catalogSearch) dom.catalogSearch.value = '';
      dom.btnClearSearch.style.display = 'none';
      renderCatalog(state, dom, onOpenTutorial);
    });
  }

  return {
    filters,
    CURRICULUM_LEVELS,
    getGestureLevelInfo,
    calculateLevelStats,
    getFilteredGestures,
    updateCategoryFilterChips,
    loadCatalog,
    renderCatalog,
    setupCatalogFilters,
  };
});
