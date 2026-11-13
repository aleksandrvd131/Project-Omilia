/**
 * Project Omiλia — Catalog Module
 * Загрузка, фильтрация, поиск и отрисовка карточек жестов в словаре.
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

  const filters = {
    search: '',
    category: 'all',
  };

  let isLoading = false;

  function getFilteredGestures(gestures) {
    const q = filters.search.trim().toLowerCase();
    const cat = filters.category;

    return gestures.filter((g) => {
      if (cat === 'learned' && !g.is_learned) return false;
      if (cat !== 'all' && cat !== 'learned' && g.category !== cat) return false;

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

  function renderCatalog(state, dom, onOpenTutorial) {
    if (!dom.gesturesGrid) return;
    const ui = window.Omilia?.UI;
    dom.gesturesGrid.innerHTML = '';

    if (state.gestures.length === 0) {
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
          <p style="font-size: 0.9rem;">Попробуйте изменить поисковый запрос или сбросить категорию.</p>
          <button class="btn-hero-secondary" id="btn-reset-filters" style="margin-top: 1rem; padding: 0.45rem 1.15rem;">
            Сбросить фильтры
          </button>
        </div>
      `;
      document.getElementById('btn-reset-filters')?.addEventListener('click', () => {
        filters.search = '';
        filters.category = 'all';
        if (dom.catalogSearch) dom.catalogSearch.value = '';
        if (dom.btnClearSearch) dom.btnClearSearch.style.display = 'none';
        dom.categoryFilters?.querySelectorAll('.filter-chip').forEach((c) => {
          c.classList.toggle('active', c.dataset.category === 'all');
        });
        renderCatalog(state, dom, onOpenTutorial);
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
              <span style="font-size: 0.78rem; color: var(--text-muted);">${ui?.escapeHtml(gesture.category)}</span>
            </div>
          </div>
          <h3 class="gesture-title">${ui?.escapeHtml(gesture.title || gesture.name)}</h3>
          <p class="gesture-desc">${ui?.escapeHtml(gesture.description)}</p>
          <div class="gesture-tip">
            💡 ${ui?.escapeHtml(gesture.tip)}
          </div>
        </div>
        <div>
          <button class="btn-practice" data-name="${ui?.escapeHtml(gesture.name)}">
            ${gesture.is_learned ? 'Повторить жест ↺' : 'Изучить жест →'}
          </button>
        </div>
      `;

      card.querySelector('.btn-practice')?.addEventListener('click', () => {
        if (onOpenTutorial) onOpenTutorial(gesture);
      });

      dom.gesturesGrid.appendChild(card);
    });
  }

  function setupCatalogFilters(state, dom, onOpenTutorial) {
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
    loadCatalog,
    renderCatalog,
    setupCatalogFilters,
  };
});
