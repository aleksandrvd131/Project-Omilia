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

  // Карта уровней для всех известных жестов учебной программы (Уровни 1-4)
  const KNOWN_GESTURE_LEVELS = {
    // Level 1: Дактильный алфавит (все 33 буквы: а-я)
    'а': 1, 'б': 1, 'в': 1, 'г': 1, 'д': 1, 'е': 1, 'ё': 1, 'ж': 1, 'з': 1, 'и': 1,
    'й': 1, 'к': 1, 'л': 1, 'м': 1, 'н': 1, 'о': 1, 'п': 1, 'р': 1, 'с': 1, 'т': 1,
    'у': 1, 'ф': 1, 'х': 1, 'ц': 1, 'ч': 1, 'ш': 1, 'щ': 1, 'ъ': 1, 'ы': 1, 'ь': 1,
    'э': 1, 'ю': 1, 'я': 1,
    // Level 2: Числительные и счёт
    '1': 2, '2': 2, '3': 2, '4': 2, '5': 2, '10': 2,
    // Level 3: Базовый этикет
    'привет': 3, 'спасибо': 3, 'помоги': 3, 'пожалуйста': 3, 'да': 3, 'нет': 3, 'мир': 3, 'хорошо': 3,
    // Level 4: Семья и окружение
    'дом': 4, 'мама': 4, 'папа': 4, 'семья': 4, 'любовь': 4, 'стоп': 4, 'книга': 4, 'ты': 4,
  };

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

    const name = (gesture.name || '').trim().toLowerCase();
    const cat = (gesture.category || '').toLowerCase();

    // 0. Точное сопоставление по реестру жестов программы
    if (KNOWN_GESTURE_LEVELS[name]) {
      const lvl = KNOWN_GESTURE_LEVELS[name];
      return { level: lvl, level_title: LEVEL_TITLES[lvl] };
    }

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
      return { level: 1, level_title: 'Дактильный алфавит' };
    }
    if (name.startsWith('буква_') || name.startsWith('буква ')) {
      return { level: 1, level_title: 'Дактильный алфавит' };
    }

    if (/^\d+$/.test(name) || ['один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять', 'десять'].includes(name)) {
      return { level: 2, level_title: 'Числительные и счёт' };
    }

    if (['привет', 'спасибо', 'помоги', 'да', 'нет', 'пожалуйста', 'здравствуйте', 'до свидания', 'прости', 'извини', 'мир', 'хорошо', 'благодарю'].includes(name)) {
      return { level: 3, level_title: 'Базовый этикет' };
    }

    if (['дом', 'мама', 'папа', 'семья', 'друг', 'ты', 'мы', 'вы', 'они', 'брат', 'сестра', 'любовь', 'стоп', 'книга'].includes(name)) {
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
        background: var(--bg-surface, #15181d) !important;
        border: 1px solid var(--border-hairline, rgba(255,255,255,0.08)) !important;
        border-radius: var(--radius-md, 12px) !important;
        padding: 1.25rem !important;
        color: var(--text-main, #e6edf3) !important;
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
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text-main, #e6edf3) !important;
        display: flex;
        align-items: center;
        gap: 0.5rem;
      }
      .roadmap-subtitle {
        font-size: 0.82rem;
        color: var(--text-muted, #8b949e) !important;
      }
      .roadmap-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.85rem;
      }
      .level-card {
        background: var(--bg-surface-elevated, #1c2027) !important;
        border: 1px solid var(--border-hairline, rgba(255,255,255,0.08)) !important;
        border-radius: var(--radius-sm, 8px) !important;
        padding: 0.95rem !important;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
        text-align: left;
        color: var(--text-main, #e6edf3) !important;
      }
      .level-card:hover {
        transform: translateY(-2px);
        border-color: rgba(245, 158, 11, 0.4) !important;
      }
      .level-card.active {
        border-color: var(--kinetic-emerald, #10b981) !important;
        background: rgba(16, 185, 129, 0.08) !important;
      }
      .level-card.locked {
        opacity: 0.5 !important;
        background: rgba(255, 255, 255, 0.02) !important;
        border-style: dashed !important;
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
        background: rgba(56, 189, 248, 0.12) !important;
        color: #38bdf8 !important;
      }
      .status-in-progress {
        background: rgba(245, 158, 11, 0.12) !important;
        color: #f59e0b !important;
      }
      .status-completed {
        background: rgba(16, 185, 129, 0.12) !important;
        color: #10b981 !important;
        border: 1px solid rgba(16, 185, 129, 0.3) !important;
      }
      .status-locked {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #8b949e !important;
      }
      .level-card-title {
        font-size: 0.92rem;
        font-weight: 700;
        color: var(--text-main, #e6edf3) !important;
        margin-bottom: 0.2rem;
      }
      .level-card-desc {
        font-size: 0.74rem;
        color: var(--text-muted, #8b949e) !important;
        margin-bottom: 0.65rem;
        line-height: 1.3;
      }
      .level-progress-bar {
        width: 100%;
        height: 4px;
        background: rgba(255, 255, 255, 0.08) !important;
        border-radius: 9999px;
        overflow: hidden;
        margin-bottom: 0.3rem;
      }
      .level-progress-fill {
        height: 100%;
        background: var(--kinetic-emerald, #10b981) !important;
        transition: width 0.3s ease;
      }
      .level-progress-fill.locked {
        background: rgba(255, 255, 255, 0.2) !important;
      }
      .level-card-stats {
        display: flex;
        justify-content: space-between;
        font-size: 0.72rem;
        color: var(--text-muted, #8b949e) !important;
        font-weight: 600;
      }
      .level-lock-hint {
        font-size: 0.7rem;
        color: #f59e0b !important;
        margin-top: 0.35rem;
        font-weight: 600;
      }
      .gesture-level-tag {
        font-size: 0.73rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 4px;
        background: rgba(245, 158, 11, 0.12) !important;
        color: #f59e0b !important;
        border: 1px solid rgba(245, 158, 11, 0.25) !important;
        font-family: var(--font-mono, monospace);
      }
      .gesture-card.level-locked {
        opacity: 0.55 !important;
      }
      .gesture-lock-banner {
        background: rgba(245, 158, 11, 0.08) !important;
        border: 1px solid rgba(245, 158, 11, 0.25) !important;
        color: #f59e0b !important;
        border-radius: 6px;
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
  function renderLevelFilterChips(state, dom, onOpenTutorial, levelStats) {
    const { levelFilters } = ensureCurriculumDOM(dom);
    if (!levelFilters) return;
    levelFilters.innerHTML = '';
    levelFilters.style.display = 'none';
  }

  /**
   * Отрисовка унифицированного 5-сегментного переключателя (Kinetic Segmented Track).
   */
  function updateCategoryFilterChips(state, dom, onOpenTutorial) {
    const catContainer = dom.categoryFilters || document.getElementById('category-filters') || document.getElementById('category-segmented-control');
    if (!catContainer) return;

    const levelStats = calculateLevelStats(state.gestures);
    const totalAll = (state.gestures || []).length;
    const l1 = levelStats?.[1]?.total ?? 0;
    const l2 = levelStats?.[2]?.total ?? 0;
    const l3 = levelStats?.[3]?.total ?? 0;
    const l4 = levelStats?.[4]?.total ?? 0;
    const learnedCount = (state.gestures || []).filter((g) => g.is_learned).length;

    const currentCat = filters.category;
    const currentLvl = filters.level;

    let activeSegment = 'all';
    if (currentCat === 'learned') {
      activeSegment = 'learned';
    } else if (currentLvl === 1) {
      activeSegment = 'alphabet';
    } else if (currentLvl === 2) {
      activeSegment = 'numbers';
    } else if (currentLvl === 3) {
      activeSegment = 'phrases';
    } else if (currentLvl === 4) {
      activeSegment = 'family';
    }

    catContainer.className = 'segmented-track category-filters';
    catContainer.setAttribute('role', 'tablist');
    catContainer.innerHTML = `
      <button class="segment-btn filter-chip ${activeSegment === 'all' ? 'active' : ''}" data-segment="all" data-category="all" role="tab">
        <span class="seg-label">Все</span> <span class="seg-count" id="count-all">${totalAll}</span>
      </button>
      <button class="segment-btn filter-chip ${activeSegment === 'alphabet' ? 'active' : ''}" data-segment="alphabet" data-level="1" data-category="Дактиль (Алфавит)" role="tab">
        <span class="seg-label">Алфавит</span> <span class="seg-count" id="count-alphabet">${l1}</span>
      </button>
      <button class="segment-btn filter-chip ${activeSegment === 'numbers' ? 'active' : ''}" data-segment="numbers" data-level="2" data-category="Числительные" role="tab">
        <span class="seg-label">Числа</span> <span class="seg-count" id="count-numbers">${l2}</span>
      </button>
      <button class="segment-btn filter-chip ${activeSegment === 'phrases' ? 'active' : ''}" data-segment="phrases" data-level="3" data-category="Базовый этикет" role="tab">
        <span class="seg-label">Фразы</span> <span class="seg-count" id="count-phrases">${l3}</span>
      </button>
      <button class="segment-btn filter-chip ${activeSegment === 'family' ? 'active' : ''}" data-segment="family" data-level="4" data-category="Семья и окружение" role="tab">
        <span class="seg-label">Семья</span> <span class="seg-count" id="count-family">${l4}</span>
      </button>
      <button class="segment-btn filter-chip segment-filter-learned ${activeSegment === 'learned' ? 'active' : ''}" data-segment="learned" data-category="learned" role="tab">
        <span class="seg-label">✓ Освоенные</span> <span class="seg-count" id="count-learned">${learnedCount}</span>
      </button>
    `;

    catContainer.querySelectorAll('.segment-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        catContainer.querySelectorAll('.segment-btn').forEach((c) => c.classList.remove('active'));
        btn.classList.add('active');

        const seg = btn.dataset.segment;
        if (seg === 'all') {
          filters.level = 'all';
          filters.category = 'all';
        } else if (seg === 'alphabet') {
          filters.level = 1;
          filters.category = 'all';
        } else if (seg === 'numbers') {
          filters.level = 2;
          filters.category = 'all';
        } else if (seg === 'phrases') {
          filters.level = 3;
          filters.category = 'all';
        } else if (seg === 'family') {
          filters.level = 4;
          filters.category = 'all';
        } else if (seg === 'learned') {
          filters.level = 'all';
          filters.category = 'learned';
        }
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
        ? '⚡ Движение'
        : (gesture.hands_count === 2 || ['дом', 'книга', 'семья', '10'].includes(gesture.name) ? '👐 2 руки' : '✋ 1 рука');

      const lockBanner = !isLevelUnlocked
        ? `<div class="gesture-lock-banner">
             <span>🔒</span>
             <span>Уровень ${gesture.level} заблокирован (требуется ≥ 70% Уровня ${gesture.level - 1})</span>
           </div>`
        : '';

      const btnText = !isLevelUnlocked
        ? (gesture.is_learned ? 'Повторить жест ↺' : `Изучить (Ур. ${gesture.level}) 🔒`)
        : (gesture.is_learned ? 'Повторить жест ↺' : 'Изучить жест →');

      const levelCode = String(gesture.level || 1).padStart(2, '0');
      const categoryCode = `${levelCode} // ${(gesture.level_title || gesture.category || 'РЖЯ').toUpperCase()}`;
      const statusTelemetry = gesture.is_learned
        ? '<span class="status-pill-learned">● ОСВОЕНО</span>'
        : (!isLevelUnlocked ? `<span class="status-pill-locked">🔒 УРОВЕНЬ ${gesture.level}</span>` : '<span class="status-pill-unlearned">○ ТРЕНИРОВАТЬ</span>');

      card.innerHTML = `
        <div class="gesture-card-inner">
          <div class="gesture-top">
            <span class="gesture-telemetry-code">${categoryCode}</span>
            <span class="gesture-hands-glyph">${handsBadge}</span>
          </div>
          <div class="gesture-body">
            <h3 class="gesture-title">${ui?.escapeHtml(gesture.title || gesture.name)}</h3>
            <p class="gesture-desc">${ui?.escapeHtml(gesture.description)}</p>
            ${gesture.tip ? `<div class="gesture-tip">💡 ${ui?.escapeHtml(gesture.tip)}</div>` : ''}
          </div>
          ${lockBanner}
          <div class="gesture-footer">
            ${statusTelemetry}
            <button class="btn-practice ${!isLevelUnlocked ? 'locked' : ''}" data-name="${ui?.escapeHtml(gesture.name)}">
              ${btnText}
            </button>
          </div>
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
    KNOWN_GESTURE_LEVELS,
    getGestureLevelInfo,
    calculateLevelStats,
    getFilteredGestures,
    updateCategoryFilterChips,
    loadCatalog,
    renderCatalog,
    setupCatalogFilters,
  };
});
