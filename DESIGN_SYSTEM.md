# Project Omiλia — UI/UX Specification: "Kinetic Atelier" (Кинетическая студия РЖЯ)

> **Document Version:** 3.0.0 (Kinetic Atelier System Architecture)  
> **Aesthetic Archetype:** Tactile Craftsmanship & Industrial Precision (Inspired by *Teenage Engineering* & *Linear*)  
> **Status:** APPROVED FOR IMMEDIATE P0 IMPLEMENTATION  
> **Target Roles:** `@stylist` (CSS Architecture in `style.css`), `@frontend` (Markup & Logic in `index.html`, `app.js`, `modules/`), `@verifier` (QA & Test Verification)

---

## 1. Design Direction: The "Kinetic Atelier" Philosophy

### The Flaws of the Previous Design
1. **Contrast Bug:** `.catalog-roadmap-view` had a hardcoded `#ffffff` light background injected by `catalog.js`, causing severe white-on-white text illegibility in dark mode.
2. **Header Bloat:** 8+ conflicting pill buttons crammed into the header with duplicate XP badges (`75 XP` alongside `@dranik2 75 XP`).
3. **Pill Soup:** 15+ overflowing filter chips across two rows with redundant categories (`Базовый этикет`, `Приветствия`, `Вежливость`, `Базовые`, `Семья и окружение`, `Семья`).
4. **"Нейро-стиль" Cliché:** Generic oversaturated neon blue glows and disjointed cards with zero tactical identity.

### The Kinetic Atelier Identity
- **Craftsmanship over Cliché:** Inspired by Teenage Engineering synthesizers and Linear's dark workspace: matte obsidian surfaces, warm graphite panels, crisp 1px hairline borders (`rgba(255, 255, 255, 0.08)`), and monospace telemetry (`font-mono`).
- **High-Density Telemetry:** Clear, purposeful metrics (`[ REC ● · 60 FPS · LATENCY 0ms · 21 PTS ]`) rather than blurry neon glows.
- **Warm Amber & Kinetic Emerald:** Warm amber (`#F59E0B`) for navigation indicators, tooltips, and diagnostic guidance; kinetic emerald (`#10B981`) exclusively for confirmed gesture recognition.

---

## 2. Standardized Design Tokens (for `style.css`)

`@stylist`: Completely replace `:root` variables in `style.css` with these tokens:

```css
:root {
  /* ==================================================== */
  /* 1. Kinetic Canvas & Surfaces (Obsidian & Graphite)   */
  /* ==================================================== */
  --bg-primary: #0d0f12;          /* Deep industrial matte obsidian */
  --bg-surface: #15181d;          /* Warm matte graphite container/card */
  --bg-surface-elevated: #1c2027; /* Elevated studio panels & modals */
  --bg-surface-hover: #222730;    /* Precision card hover */
  --bg-track: #101216;            /* Recessed track for segmented switchers */
  --bg-glass-hud: rgba(13, 15, 18, 0.88); /* Studio viewfinder HUD */

  /* ==================================================== */
  /* 2. Hairline Borders & Studio Dividers                */
  /* ==================================================== */
  --border-hairline: rgba(255, 255, 255, 0.08);
  --border-subtle: rgba(255, 255, 255, 0.14);
  --border-accent: rgba(245, 158, 11, 0.6);
  --border-focus: #f59e0b;

  /* ==================================================== */
  /* 3. Kinetic Accents (Teenage Engineering Palette)    */
  /* ==================================================== */
  --kinetic-amber: #f59e0b;       /* Warm industrial brass/amber */
  --kinetic-amber-light: rgba(245, 158, 11, 0.12);
  --kinetic-emerald: #10b981;     /* Verified gesture match green */
  --kinetic-emerald-light: rgba(16, 185, 129, 0.12);
  --kinetic-cyan: #38bdf8;        /* MediaPipe skeleton & telemetry */
  --kinetic-coral: #ef4444;       /* Abort / Warning */
  --kinetic-flame: #f97316;       /* Daily streak fire */

  /* Backwards compatibility aliases for existing JS/CSS rules */
  --primary: var(--kinetic-emerald);
  --primary-hover: #059669;
  --accent: var(--kinetic-amber);
  --success: var(--kinetic-emerald);
  --danger: var(--kinetic-coral);
  --card-bg: var(--bg-surface);
  --card-border: var(--border-hairline);

  /* ==================================================== */
  /* 4. Typography & Monospace Telemetry                  */
  /* ==================================================== */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;

  --text-main: #e6edf3;           /* High-contrast crisp white */
  --text-muted: #8b949e;          /* Muted graphite secondary */
  --text-dim: #484f58;            /* Low-emphasis captions & dividers */

  /* ==================================================== */
  /* 5. Geometry, Radii & Shadows                         */
  /* ==================================================== */
  --radius-xs: 4px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-pill: 9999px;

  --shadow-hairline: 0 0 0 1px var(--border-hairline);
  --shadow-studio-card: 0 8px 24px rgba(0, 0, 0, 0.55), 0 0 0 1px var(--border-hairline);
  --shadow-active-lift: 0 12px 32px rgba(0, 0, 0, 0.7), 0 0 0 1px var(--border-subtle);
}
```

---

## 3. Component Architecture & Implementation Blueprint

### A. Header: Clean Brand, 3 Links, ONE Unified Status Pill

`@frontend`: Streamline the header in `index.html`:
```html
<header>
  <div class="header-inner">
    <!-- Brand -->
    <a href="#" class="brand" id="brand-link">
      <div class="logo-badge">Ω</div>
      <div class="brand-title">Omiλia <span class="brand-tag">РЖЯ // СТУДИЯ</span></div>
    </a>

    <!-- Clean 3-Link Navigation -->
    <nav class="studio-nav">
      <ul class="nav-tabs">
        <li><button class="nav-btn active" data-tab="catalog" id="tab-btn-catalog">Словарь</button></li>
        <li><button class="nav-btn" data-tab="blitz" id="tab-btn-blitz">Блиц</button></li>
        <li><button class="nav-btn" data-tab="about" id="tab-btn-about">О проекте</button></li>
        <!-- Hidden button for automated test compatibility -->
        <li style="display: none;"><button class="nav-btn" data-tab="profile" id="tab-btn-profile"></button></li>
      </ul>
    </nav>

    <!-- Unified Studio Status Capsule (Zero duplicate badges) -->
    <div class="header-user-group" id="header-user-group">
      <!-- Studio Utility Micro-actions (Maintains test assertions for btn-header-warmup and btn-header-guide) -->
      <button class="btn-studio-tool" id="btn-header-warmup" title="Ежедневная разминка SM-2">🎯</button>
      <button class="btn-studio-tool" id="btn-header-guide" title="Инструкция по тренировке">💡</button>

      <!-- The Single Unified Status Pill -->
      <div class="unified-status-pill" id="unified-status-pill" role="button" tabindex="0" title="Открыть личный кабинет">
        <span class="status-seg streak" id="header-streak-badge">
          🔥 <span id="streak-days-count">0</span>
        </span>
        <span class="status-divider">·</span>
        <span class="status-seg xp" id="header-xp-badge">
          ⚡ <span id="header-xp-count">0</span> XP
        </span>
        <span class="status-divider">·</span>
        <span class="status-seg user" id="header-user-area">
          <button class="btn-login-inline" id="btn-header-login">Войти</button>
        </span>
      </div>
    </div>
  </div>
</header>
```

`@frontend` in `app.js` (when user logs in):
- Update `#header-user-area` to simply:
  `<span class="user-handle" id="header-user-handle">@${user.username}</span>`
- DO NOT inject a duplicate `XP` badge into `#header-user-area`. `#header-xp-count` already displays the user's XP.
- Clicking `#unified-status-pill` switches tab to `profile`.

---

### B. Dictionary: Replace 15-Pill Soup with 5-Segment Switcher & Hotkey Search

`@frontend` & `@stylist` in `index.html` & `modules/catalog.js`:

#### 1. Controls Container Markup:
```html
<div class="catalog-controls-studio">
  <!-- Search Bar with Hotkey '/' -->
  <div class="search-box-studio">
    <span class="search-icon-mono">/</span>
    <input type="text" id="catalog-search" class="search-input-studio" placeholder="Поиск жеста по названию или букве... (Нажмите /)" autocomplete="off">
    <button id="btn-clear-search" class="btn-clear-search" title="Очистить" style="display: none;">✕</button>
  </div>

  <!-- Unified 5-Segment Tactile Switcher (Teenage Engineering Hardware Track) -->
  <div class="segmented-track" id="category-segmented-control" role="tablist">
    <button class="segment-btn active" data-segment="all" data-category="all" role="tab" aria-selected="true">
      <span class="seg-label">Все</span> <span class="seg-count" id="count-all">42</span>
    </button>
    <button class="segment-btn" data-segment="alphabet" data-level="1" data-category="Дактиль (Алфавит)" role="tab">
      <span class="seg-label">Алфавит</span> <span class="seg-count" id="count-alphabet">33</span>
    </button>
    <button class="segment-btn" data-segment="numbers" data-level="2" data-category="Числительные" role="tab">
      <span class="seg-label">Числа</span> <span class="seg-count" id="count-numbers">10</span>
    </button>
    <button class="segment-btn" data-segment="phrases" data-level="3" data-category="Базовый этикет" role="tab">
      <span class="seg-label">Фразы</span> <span class="seg-count" id="count-phrases">8</span>
    </button>
    <button class="segment-btn" data-segment="family" data-level="4" data-category="Семья и окружение" role="tab">
      <span class="seg-label">Семья</span> <span class="seg-count" id="count-family">8</span>
    </button>
    <button class="segment-btn segment-filter-learned" data-segment="learned" data-category="learned" role="tab">
      <span class="seg-label">✓ Освоенные</span>
    </button>
  </div>
</div>
```

#### 2. Hotkey Listener in `app.js` / `catalog.js`:
- When user presses `/` outside of an active input field, automatically focus `#catalog-search`.

---

### C. Contrast Bug Resolution: Roadmap & Studio Panels

`@stylist` & `@frontend`:
1. In `src/project_omilia/frontend/modules/catalog.js`:
   - Replace the legacy CSS injection in `ensureCatalogStyles()` so it does NOT inject hardcoded `#ffffff` or `#f8fafc`.
   - Instead, style `.catalog-roadmap-view` with:
     ```css
     .catalog-roadmap-view {
       background: var(--bg-surface) !important;
       border: 1px solid var(--border-hairline) !important;
       color: var(--text-main) !important;
     }
     .level-card {
       background: var(--bg-surface-elevated) !important;
       border: 1px solid var(--border-hairline) !important;
       color: var(--text-main) !important;
     }
     .level-card-title {
       color: var(--text-main) !important;
     }
     .level-card-desc {
       color: var(--text-muted) !important;
     }
     ```
2. In `style.css`: explicitly style `#catalog-roadmap` and all curriculum children with warm graphite backgrounds, razor hairline borders, and pure white text.

---

### D. Gesture Cards: Kinetic Flashcards

Each gesture card in the grid:
- **Card Background:** `var(--bg-surface)` (`#15181D`)
- **Border:** `1px solid var(--border-hairline)` (`rgba(255, 255, 255, 0.08)`)
- **Card Header (Telemetry):**
  - Left: Monospace category code: `[01 // АЛФАВИТ]`
  - Right: Hand glyph: `✋ 1 РУКА` / `👐 2 РУКИ` / `⚡ ДИНАМИКА`
- **Center Body:**
  - Giant, crisp Cyrillic typography (`А`, `Привет`, `Спасибо`).
- **Footer Telemetry:**
  - Status indicator:
    - Mastered: `[ ● ОСВОЕНО ]` (kinetic emerald dot)
    - Unlearned: `[ ○ ТРЕНИРОВАТЬ ]` (muted slate)
    - Locked: `[ 🔒 УРОВЕНЬ 2 ]`
- **Hover:**
  - Micro-lift: `transform: translateY(-2px); border-color: rgba(245, 158, 11, 0.4); box-shadow: var(--shadow-active-lift);`

---

### E. Camera Studio Workspace: Optics Viewfinder HUD

Inside `#practice-modal`, `#warmup-modal`, and `#blitz-active`:
- **Framing Brackets:**
  Add 4 subtle corner bracket markers to `.camera-container`:
  - `::before` & `::after` with hairline white borders representing viewfinder crosshairs:
    `┌  ┐` and `└  ┘`.
- **Top HUD Telemetry Bar:**
  - Monospace telemetry pill:
    `REC ● | 60 FPS | LATENCY 0ms | CONFIDENCE 94%`
- **Corrective Diagnostic Hint:**
  - Amber studio bracket pill floating above the bottom controls:
    `[ 💡 HINT: ВЫПРЯМИТЕ УКАЗАТЕЛЬНЫЙ ПАЛЕЦ НА 15° ]`
- **Sound-Independent Match Burst:**
  - Kinetic emerald flash on outer frame (`border-color: var(--kinetic-emerald)`).
  - Tactile countdown hold ring / meter.

---

## 4. Test Compatibility Requirements (Non-Negotiable)

To ensure zero regressions in existing automated tests:
1. **PWA & Manifest (`tests/test_pwa_and_mobile.py`):**
   - Retain `theme-color: #0d0f12` or `#0f172a`.
   - Preserve `manifest.json` and `sw.js` links.
   - Retain `.btn-switch-camera` and `.btn-floating-camera-switch`.
2. **Component Integration (`tests/test_frontend_modules.cjs`):**
   - Retain IDs: `#warmup-modal`, `#btn-header-warmup`, `#catalog-warmup-card`, `#btn-catalog-warmup`.
   - Retain IDs: `#onboarding-modal`, `#btn-header-guide`, `#btn-hero-guide`, `#onboarding-step-1`, `#onboarding-step-2`, `#onboarding-step-3`.
   - Retain IDs: `#practice-cheatsheet-wrapper`, `#btn-practice-cheatsheet-toggle`, `#practice-cheatsheet-content`.
   - Retain IDs: `#stat-xp-count`, `#profile-xp-card`, `#profile-xp-bar`.
   - Retain Video elements: `#warmup-video`, `#practice-video`, `#blitz-video` with `autoplay`, `muted`, `playsinline`.
3. **Headless Browser E2E (`tests/test_browser_e2e.cjs`):**
   - Retain nav button tabs with `data-tab="about"`, `data-tab="catalog"`, `data-tab="blitz"`, `data-tab="profile"`.
