/**
 * Project Omiλia — Catalog Module
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

    if (gesture.level && gesture.level_title) {
      return {
        level: Number(gesture.level),
        level_title: String(gesture.level_title),
      };
    }

    const name = (gesture.name || '').trim().toLowerCase();
    const cat = (gesture.category || '').toLowerCase();

    // 1. По категории
    if (cat.includes('алфавит') || cat.includes('дактиль')) {
      return { level: 1, level_title: 'Дактильный алфавит' };
    }
    if (cat.includes('числительн') || cat.includes('счёт') || cat.includes('счет') || cat.includes('цифр')) {
      return { level: 2, level_title: 'Числительные и счёт' };
    }
    if (cat.includes('привет') || cat.includes('вежливост') || cat.includes('этикет') || cat.includes('базов')) {
      return { level: 3, level_title: 'Базовый этикет' };
    }
    if (cat.includes('семь') || cat.includes('дом') || cat.includes('окружен')) {
      return { level: 4, level_title: 'Семья и окружение' };
    }

    // 2. По названию
    if (name.length === 1 && /[а-яё]/i.test(name)) {
      if (name === 'я') return { level: 4, level_title: 'Семья и окружение' };
      return { level: 1, level_title: 'Дактильный алфавит' };
    }
    if (name.startsWith('буква_') || name.startsWith('буква ')) {
      return { level: 1, level_title: 'Дактильный алфавит' };
    }

    if (/^\d+$/.test(name) || ['один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять', 'десять'].includes(name)) {
      return { level: 2, level_title: 'Числительные и счёт' };
    }

    if (['привет', 'спасибо', 'помоги', 'да', 'нет', 'пожалуйста', 'здравствуйте', 'до свидания', 'прости', 'извини'].includes(name)) {
      return { level: 3, level_title: 'Базовый этикет' };
    }

    if (['дом', 'мама', 'папа', 'семья', 'друг', 'ты', 'я', 'мы', 'вы', 'они'].includes(name)) {
      return { level: 4, level_title: 'Семья и окружение' };
    }

    return { level: 3, level_title: 'Базовый этикет' };
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
      if (cat !== 'all' && cat !== 'learned' && g.category !== cat) return false;

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
   * Внедрение CSS-стилей для дорожной карты курсов и карточек уровней.
   */
  function ensureCatalogStyles() {
    if (typeof document === 'undefined') return;
    if (document.getElementById('catalog-curriculum-styles')) return;

    const style = document.createElement('style');
    style.id = 'catalog-curriculum-styles';
    style.textContent = `
      .catalog-roadmap-view {
        margin-bottom: 1.5rem;
        background: #ffffff;
        border: 1px solid var(--card-border, #e2e8f0);
        border-radius: var(--radius, 16px);
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      }
      .roadmap-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        flex-wrap: wrap;
        gap: 0.5rem;
      }
      .roadmap-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: var(--text-main, #0f172a);
        display: flex;
        align-items: center;
        gap: 0.5rem;
      }
      .roadmap-subtitle {
        font-size: 0.82rem;
        color: var(--text-muted, #64748b);
      }
      .roadmap-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.85rem;
      }
      .level-card {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 0.95rem;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
        text-align: left;
      }
      .level-card:hover {
        transform: translateY(-2px);
        border-color: var(--primary-border, #86efac);
        box-shadow: 0 6px 16px -2px rgba(16, 185, 129, 0.12);
      }
      .level-card.active {
        border-color: var(--primary, #10b981);
        background: #f0fdf4;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.25);
      }
      .level-card.locked {
        opacity: 0.68;
        background: #f1f5f9;
        border-style: dashed;
        cursor: pointer;
      }
      .level-card-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.4rem;
      }
      .level-card-badge {
        font-size: 1.35rem;
      }
      .level-card-status {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 9999px;
      }
      .status-unlocked {
        background: #e0f2fe;
        color: #0369a1;
      }
      .status-in-progress {
        background: #fef3c7;
        color: #b45309;
      }
      .status-completed {
        background: #dcfce7;
        color: #15803d;
        border: 1px solid #86efac;
      }
      .status-locked {
        background: #e2e8f0;
        color: #64748b;
      }
      .level-card-title {
        font-size: 0.92rem;
        font-weight: 700;
        color: var(--text-main, #0f172a);
        margin-bottom: 0.2rem;
      }
      .level-card-desc {
        font-size: 0.74rem;
        color: var(--text-muted, #64748b);
        margin-bottom: 0.65rem;
        line-height: 1.3;
      }
      .level-progress-bar {
        width: 100%;
        height: 5px;
        background: #e2e8f0;
        border-radius: 9999px;
        overflow: hidden;
        margin-bottom: 0.3rem;
      }
      .level-progress-fill {
        height: 100%;
        background: var(--primary, #10b981);
        transition: width 0.3s ease;
      }
      .level-progress-fill.locked {
        background: #94a3b8;
      }
      .level-card-stats {
        display: flex;
        justify-content: space-between;
        font-size: 0.72rem;
        color: var(--text-muted, #64748b);
        font-weight: 600;
      }
      .level-lock-hint {
        font-size: 0.7rem;
        color: #b45309;
        margin-top: 0.35rem;
        font-weight: 600;
      }
      .level-filter-bar {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-bottom: 0.65rem;
      }
      .level-filter-label {
        font-size: 0.8rem;
        font-weight: 700;
        color: var(--text-muted, #64748b);
        margin-right: 0.2rem;
      }
      .gesture-level-tag {
        font-size: 0.73rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 6px;
        background: #eef2ff;
        color: #4338ca;
        border: 1px solid #c7d2fe;
      }
      .gesture-card.level-locked {
        opacity: 0.82;
        background: #fafafa;
      }
      .gesture-lock-banner {
        background: #fffbeb;
        border: 1px solid #fde68a;
        color: #b45309;
        border-radius: 8px;
        padding: 0.35rem 0.6rem;
        font-size: 0.76rem;
        font-weight: 600;
        margin-top: 0.6rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
      }
    `;
    document.head.appendChild(style);
  }

  /**
   * Создание или получение DOM-контейнеров для Roadmap и фильтров уровней.
   */
  function ensureCurriculumDOM(dom) {
    if (typeof document === 'undefined') return { roadmap: null, levelFilters: null };

    ensureCatalogStyles();

    // 1. Контейнер дорожной карты
    let roadmap = document.getElementById('catalog-roadmap');
    if (!roadmap) {
      roadmap = document.createElement('div');
      roadmap.id = 'catalog-roadmap';
      roadmap.className = 'catalog-roadmap-view';

      const controls = document.querySelector('.catalog-controls');
      if (controls && controls.parentNode) {
        controls.parentNode.insertBefore(roadmap, controls);
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
      <div class="roadmap-header">
        <div>
          <div class="roadmap-title">
            <span>🗺️</span>
            <span>Дерево курсов и уровни сложности</span>
          </div>
          <div class="roadmap-subtitle">
            Изучите дактильный алфавит и счёт, чтобы разблокировать базовый этикет и расширенные жесты
          </div>
        </div>
      </div>
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
            statusBadge = '<span class="level-card-status status-locked">🔒 Закрыт</span>';
          } else if (st.isCompleted) {
            statusBadge = '<span class="level-card-status status-completed">🏆 Завершён (100%)</span>';
          } else if (st.percentage >= 70) {
            statusBadge = `<span class="level-card-status status-completed">✓ Освоен (${st.percentage}%)</span>`;
          } else if (st.learned > 0) {
            statusBadge = `<span class="level-card-status status-in-progress">⚡ В процессе (${st.percentage}%)</span>`;
          } else {
            statusBadge = '<span class="level-card-status status-unlocked">🟢 Открыт</span>';
          }

          const lockHint = !st.isUnlocked
            ? `<div class="level-lock-hint">🔒 Требуется ≥ 70% Уровня ${lvl.level - 1}</div>`
            : '';

          const isActive = filters.level === lvl.level;
          const cardClass = `level-card ${st.isUnlocked ? '' : 'locked'} ${isActive ? 'active' : ''}`;

          return `
            <div class="${cardClass}" data-level="${lvl.level}">
              <div class="level-card-top">
                <span class="level-card-badge">${lvl.badge}</span>
                ${statusBadge}
              </div>
              <div class="level-card-title">Уровень ${lvl.level}: ${lvl.title}</div>
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
            </div>
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
  function renderLevelFilterChips(state, dom, onOpenTutorial) {
    const { levelFilters } = ensureCurriculumDOM(dom);
    if (!levelFilters) return;

    levelFilters.innerHTML = `
      <span class="level-filter-label">Уровень:</span>
      <button class="filter-chip ${filters.level === 'all' ? 'active' : ''}" data-level="all">Все уровни</button>
      <button class="filter-chip ${filters.level == 1 ? 'active' : ''}" data-level="1">Ур. 1: Дактиль</button>
      <button class="filter-chip ${filters.level == 2 ? 'active' : ''}" data-level="2">Ур. 2: Счёт</button>
      <button class="filter-chip ${filters.level == 3 ? 'active' : ''}" data-level="3">Ур. 3: Этикет</button>
      <button class="filter-chip ${filters.level == 4 ? 'active' : ''}" data-level="4">Ур. 4: Семья</button>
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
    renderLevelFilterChips(state, dom, onOpenTutorial);

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
        ? '⚡ Движение'
        : (gesture.hands_count === 2 || gesture.name === 'дом' ? '👐 2 руки' : '✋ 1 рука');

      const lockBanner = !isLevelUnlocked
        ? `<div class="gesture-lock-banner">
             <span>🔒</span>
             <span>Уровень ${gesture.level} заблокирован (требуется ≥ 70% Уровня ${gesture.level - 1})</span>
           </div>`
        : '';

      const btnText = !isLevelUnlocked
        ? (gesture.is_learned ? 'Повторить жест ↺' : `Изучить (Ур. ${gesture.level}) 🔒`)
        : (gesture.is_learned ? 'Повторить жест ↺' : 'Изучить жест →');

      card.innerHTML = `
        <div>
          <div class="gesture-top">
            <span class="gesture-badge ${gesture.is_learned ? 'badge-learned' : 'badge-unlearned'}">
              ${gesture.is_learned ? '✓ Выучен' : 'Не изучен'}
            </span>
            <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
              <span class="gesture-level-tag">Ур. ${gesture.level}</span>
              <span style="font-size: 0.75rem; background: #f1f5f9; padding: 2px 7px; border-radius: 6px; font-weight: 600; color: var(--text-muted);">
                ${handsBadge}
              </span>
              <span style="font-size: 0.78rem; color: var(--text-muted);">${ui?.escapeHtml(gesture.category)}</span>
            </div>
          </div>
          <h3 class="gesture-title">${ui?.escapeHtml(gesture.title || gesture.name)}</h3>
          <p class="gesture-desc">${ui?.escapeHtml(gesture.description)}</p>
          <div class="gesture-tip">
            💡 ${ui?.escapeHtml(gesture.tip)}
          </div>
          ${lockBanner}
        </div>
        <div style="margin-top: 1rem;">
          <button class="btn-practice" data-name="${ui?.escapeHtml(gesture.name)}">
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
    renderLevelFilterChips(state, dom, onOpenTutorial);

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

    dom.categoryFilters?.querySelectorAll('.filter-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        dom.categoryFilters.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        filters.category = chip.dataset.category;
        renderCatalog(state, dom, onOpenTutorial);
      });
    });
  }

  return {
    filters,
    CURRICULUM_LEVELS,
    getGestureLevelInfo,
    calculateLevelStats,
    getFilteredGestures,
    loadCatalog,
    renderCatalog,
    setupCatalogFilters,
  };
});
