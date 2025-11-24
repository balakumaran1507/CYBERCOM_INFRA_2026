# 🎯 CYBERCOM CTF 2026 - UI FORENSIC ANALYSIS & SAFE PLACEHOLDER DESIGN

**Mission**: Analyze CTFd UI architecture and design minimal, safe CYBERCOM placeholder UI
**Engineer**: Senior Frontend Systems Architect & CTFd UI Reverse Engineer
**Date**: 2025-11-24
**Status**: Phase 1 Complete - Forensic Analysis

---

## PHASE 1: FORENSIC UI ANALYSIS

### 📊 UI ARCHITECTURE MAP

```
┌────────────────────────────────────────────────────────────────┐
│                    CTFd THEME ARCHITECTURE                     │
└────────────────────────────────────────────────────────────────┘

TEMPLATE INHERITANCE FLOW:
═══════════════════════════

base.html (Root Template)
├── Defines: <html>, <head>, <body>
├── Includes: components/navbar.html
├── Block: {% block content %} (empty - child templates fill this)
├── Block: {% block scripts %} (page.js by default)
├── Includes: components/snackbar.html
├── Includes: components/notifications.html
└── Footer: "Powered by CTFd" (line 52-60)

        ↓ extends

page.html (Simple Content Pages)
├── Extends: base.html
├── Block content: <div class="container">{{ content | safe }}</div>
└── Used for: Static pages, custom content

        ↓ extends

challenges.html (Challenge Grid)
├── Extends: base.html
├── Block content: Full challenge grid with Alpine.js
├── Uses: x-data="ChallengeBoard" (Alpine.js component)
├── Renders: Dynamic challenge cards (col-sm-6 col-md-4 col-lg-3)
└── Scripts: challenges.js (loaded in scripts block)


COMPONENT STRUCTURE:
═══════════════════

components/navbar.html
├── Bootstrap 5 navbar (navbar-dark bg-dark fixed-top)
├── Brand: Configs.ctf_logo OR Configs.ctf_name (line 3-14)
├── Menu Items:
│   ├── Users (if visible)
│   ├── Teams (if team mode)
│   ├── Scoreboard (if visible)
│   ├── Challenges (always visible)
│   ├── Admin Panel (if admin)
│   ├── Notifications (if authenticated)
│   ├── Profile (if authenticated)
│   ├── Settings (if authenticated)
│   ├── Login/Register (if not authenticated)
│   ├── Language Selector (dropdown)
│   └── Theme Toggle (light/dark)
└── Responsive: Collapses to hamburger on mobile

components/snackbar.html
└── Toast notifications (Bootstrap alerts)

components/notifications.html
└── Notification modal/dropdown
```

---

### 🎨 CSS PIPELINE ANALYSIS

```
CSS LOADING ORDER:
═════════════════

1. GLOBAL STYLES (base.html line 11-13):
   └── {{ Assets.css("assets/scss/main.scss") }}
       ├── Compiles to: static/assets/main.[hash].css
       └── Contains:

main.scss Structure:
├── Bootstrap 5 (with custom $info color: #5c728f)
├── Components:
│   ├── table.scss (table styling)
│   ├── jumbotron.scss (header sections)
│   ├── challenge.scss (challenge cards)
│   ├── sticky-footer.scss (footer positioning)
│   └── graphs.scss (scoreboard graphs)
├── Utils:
│   ├── fonts.scss (typography)
│   ├── opacity.scss (opacity utilities)
│   ├── min-height.scss (height utilities)
│   ├── cursors.scss (cursor styles)
│   └── lolight.scss (code highlighting)
└── Icons:
    ├── award-icons.scss (trophy icons)
    └── flag-icons.scss (country flags)

2. PLUGIN STYLES (base.html line 15):
   └── {{ Plugins.styles }}
       └── Injected by plugins (Phase 2, docker_challenges, etc.)

3. THEME HEADER (base.html line 40):
   └── {{ Configs.theme_header }}
       └── Custom CSS/JS from admin config

4. INLINE OVERRIDES:
   └── Can be added via theme_header config in admin panel


CRITICAL CSS CLASSES:
════════════════════

Navigation:
├── .navbar-dark.bg-dark (dark navbar)
├── .navbar-brand (logo/title)
└── .nav-link (menu items)

Challenges:
├── .challenge-button (challenge card button)
├── .challenge-solved (green highlight when solved)
├── .challenge-inner (card content wrapper)
└── .category-header (category title)

Layout:
├── .jumbotron (page headers - deprecated but still used)
├── .container (max-width content wrapper)
└── .footer (sticky footer at bottom)

Theme:
├── [data-theme="dark"] (dark mode attribute)
└── [data-theme="light"] (light mode attribute)
```

---

### ⚙️ JAVASCRIPT BEHAVIOR ANALYSIS

```
JS LOADING ORDER:
════════════════

1. COLOR MODE SWITCHER (base.html line 17):
   └── Assets.js("assets/js/color_mode_switcher.js", type=None)
       └── Loads BEFORE window.init
       └── Sets theme before page renders (prevents flash)

2. WINDOW.INIT CONFIG (base.html line 19-38):
   └── JavaScript object with:
       ├── urlRoot: API base URL
       ├── csrfNonce: CSRF token for API calls
       ├── userMode: "users" or "teams"
       ├── userId, userName, userEmail (current user)
       ├── teamId, teamName (if team mode)
       ├── start, end: Competition timestamps
       ├── themeSettings: Custom theme config
       └── eventSounds: Notification sound files

3. PAGE SCRIPTS (base.html line 64-66):
   └── {% block scripts %}
       └── {{ Assets.js("assets/js/page.js") }}
           ├── Default: page.js (basic page functionality)
           ├── Override: challenges.js (for challenges.html)
           └── Contains: Alpine.js, Bootstrap, CTFd API wrappers

4. PLUGIN SCRIPTS (base.html line 68):
   └── {{ Plugins.scripts }}
       └── Injected by plugins

5. THEME FOOTER (base.html line 70):
   └── {{ Configs.theme_footer }}
       └── Custom JS from admin config


CRITICAL JS DEPENDENCIES:
═════════════════════════

Alpine.js (challenges.html):
├── x-data="ChallengeBoard" (challenge grid component)
├── x-ref="challengeWindow" (modal reference)
├── x-show="loaded" (show/hide challenges)
├── x-for="category in getCategories()" (loop categories)
└── @click="loadChallenge(c.id)" (challenge click handler)

Bootstrap 5:
├── data-bs-toggle="modal" (modal trigger)
├── data-bs-toggle="dropdown" (dropdown menus)
├── data-bs-toggle="tooltip" (tooltips)
└── data-bs-toggle="collapse" (mobile menu)

CTFd API (challenges.js):
├── loadChallenges() - Fetch challenge list
├── loadChallenge(id) - Load challenge modal
├── submitChallenge() - Submit flag
└── Challenge data stored in: $store.challenge


⚠️ CRITICAL: DO NOT MODIFY
═══════════════════════════

These JS components are MANDATORY:
1. window.init object (API calls will fail without it)
2. Alpine.js x-data bindings (challenges won't load)
3. Bootstrap data-bs-* attributes (navigation breaks)
4. CSRF nonce (form submissions fail)
5. Assets.js() calls (webpack-compiled bundles)
```

---

### 🔍 ASSET COMPILATION PIPELINE

```
WEBPACK BUILD PROCESS:
═════════════════════

Source Files:
└── CTFd/themes/core/assets/
    ├── js/*.js (JavaScript modules)
    └── scss/*.scss (Sass stylesheets)

        ↓ webpack compile

Compiled Output:
└── CTFd/themes/core/static/
    ├── assets/main.[hash].css (compiled CSS)
    ├── assets/page.[hash].js (page scripts)
    └── assets/challenges.[hash].js (challenge scripts)

Asset Loading:
├── {{ Assets.css("path") }} → Resolves to hashed filename
└── {{ Assets.js("path") }} → Resolves to hashed filename

⚠️ IMPORTANT:
- Modifying source files requires webpack rebuild
- Hash changes on every build (cache busting)
- Direct static file edits are LOST on rebuild
```

---

## 🎯 SAFE MODIFICATION ZONES

### ✅ SAFE TO MODIFY (No Rebuild Required)

```
TEMPLATES (HTML):
├── base.html
│   ├── Lines 52-60: Footer text ✅ SAFE
│   ├── Line 4: <title> tag ✅ SAFE
│   └── Line 7: Favicon ✅ SAFE
├── navbar.html
│   ├── Lines 3-14: Brand logo/text ✅ SAFE
│   └── Navbar classes ✅ SAFE
└── challenges.html
    └── Lines 4-10: Jumbotron header ✅ SAFE

INLINE CSS (via theme_header config):
└── Add custom CSS without touching source ✅ SAFE

CUSTOM TEMPLATES (new files):
└── Create new templates that extend base.html ✅ SAFE
```

### ⚠️ MEDIUM RISK (Requires Testing)

```
CSS SOURCE FILES:
└── CTFd/themes/core/assets/scss/
    └── Requires webpack rebuild
    └── Test thoroughly after changes

JS SOURCE FILES:
└── CTFd/themes/core/assets/js/
    └── Requires webpack rebuild
    └── May break Alpine.js components
```

### ❌ UNSAFE (DO NOT MODIFY)

```
CORE JAVASCRIPT LOGIC:
├── Alpine.js x-data bindings (challenges break)
├── window.init object (API calls fail)
├── Bootstrap JS (navigation breaks)
└── CTFd API wrappers (submissions fail)

TEMPLATE STRUCTURE:
├── {% block %} declarations (inheritance breaks)
├── Alpine.js directives (x-data, x-show, etc.)
└── Bootstrap data-bs-* attributes
```

---

## 📋 BRANDING OPPORTUNITIES (Safe Changes)

### 1. Footer Branding
```html
<!-- base.html line 52-60 -->
<!-- BEFORE: -->
<footer class="footer">
  <div class="container text-center">
    <a href="https://ctfd.io" class="text-secondary">
      <small class="text-muted">
        {% trans %}Powered by CTFd{% endtrans %}
      </small>
    </a>
  </div>
</footer>

<!-- AFTER: -->
<footer class="footer">
  <div class="container text-center">
    <small class="text-muted">
      CYBERCOM CTF 2026 | Engineered for Excellence
    </small>
  </div>
</footer>
```

### 2. Navbar Brand
```html
<!-- navbar.html line 3-14 -->
<!-- Current: Uses Configs.ctf_logo or Configs.ctf_name -->
<!-- Change via Admin Panel → Config → CTF Name -->
<!-- Set: CYBERCOM CTF 2026 -->
```

### 3. Page Title
```html
<!-- base.html line 4 -->
<!-- BEFORE: -->
<title>{{ title or Configs.ctf_name }}</title>

<!-- AFTER: -->
<title>{{ title or "CYBERCOM CTF 2026" }}</title>
```

### 4. Custom CSS (No Rebuild)
```html
<!-- Add to Admin Panel → Config → Theme Header -->
<style>
:root {
  --cybercom-primary: #00ff41;
  --cybercom-dark: #0a0e27;
  --cybercom-accent: #00d4ff;
}

.navbar-dark {
  background-color: var(--cybercom-dark) !important;
}

.challenge-button {
  border: 1px solid var(--cybercom-primary);
  transition: all 0.3s ease;
}

.challenge-button:hover {
  box-shadow: 0 0 10px var(--cybercom-primary);
}

.challenge-solved {
  background-color: rgba(0, 255, 65, 0.2) !important;
}

.footer small {
  color: var(--cybercom-primary) !important;
  font-family: 'Courier New', monospace;
}
</style>
```

---

## 🚀 RECOMMENDED APPROACH

### Option A: ADMIN CONFIG ONLY (Safest)
**No code changes required**

1. Admin Panel → Config:
   - CTF Name: "CYBERCOM CTF 2026"
   - Theme Header: Add custom CSS (above)
   - Small Icon: Upload CYBERCOM favicon
   - Logo: Upload CYBERCOM logo

2. Result:
   - ✅ Navbar shows CYBERCOM
   - ✅ Custom color scheme
   - ✅ Footer unchanged (still says CTFd)
   - ✅ Zero code modifications
   - ✅ Instantly reversible

### Option B: THEME OVERRIDE (Recommended)
**Create custom theme based on core**

1. Copy core theme → cybercom_ui
2. Modify only templates (no CSS/JS rebuild)
3. Change footer, titles, branding
4. Activate via config

See "PHASE 2: SAFE PLACEHOLDER DESIGN" for implementation.

### Option C: FULL CUSTOM THEME (Advanced)
**Requires webpack rebuild**

1. Fork core theme completely
2. Rebuild CSS/JS from source
3. Custom design system
4. High maintenance

**NOT RECOMMENDED for initial placeholder**

---

## ⚠️ KNOWN FRAGILITY POINTS

### 1. Alpine.js Dependencies
```javascript
// challenges.html relies on Alpine.js x-data
// Breaking this breaks challenge loading

❌ DO NOT REMOVE:
x-data="ChallengeBoard"
x-show="loaded"
x-for="(c, idx) in getChallenges(category)"
@click="loadChallenge(c.id)"
```

### 2. Bootstrap Modal System
```html
<!-- Challenge modal relies on Bootstrap JS -->
❌ DO NOT REMOVE:
data-bs-toggle="modal"
class="modal fade"
id="challenge-window"
```

### 3. Webpack Asset Hashes
```python
# Assets.css() and Assets.js() resolve hashed filenames
# Direct <link> or <script> tags will break

❌ DO NOT USE:
<link href="/static/main.css">

✅ ALWAYS USE:
{{ Assets.css("assets/scss/main.scss") }}
```

---

## 📊 THEME ACTIVATION METHOD

```python
# How CTFd selects active theme:

1. Check database config: theme_name
2. Look in: CTFd/themes/[theme_name]/
3. Load templates from: [theme_name]/templates/
4. Fallback to: core theme

Current theme: "core" (default)

To activate custom theme:
1. Admin Panel → Config → Theme: "cybercom_ui"
2. Or database:
   UPDATE config SET value = 'cybercom_ui' WHERE key = 'theme_name';
```

---

## 🎯 CONCLUSION - PHASE 1

### What We Learned:

1. **Template Inheritance**: base.html → page.html/challenges.html
2. **Asset Pipeline**: Webpack compiles SCSS → hashed CSS/JS
3. **Critical Dependencies**: Alpine.js, Bootstrap 5, window.init
4. **Safe Zones**: Templates (HTML), Admin config, Inline CSS
5. **Danger Zones**: JS logic, Alpine.js bindings, webpack source files

### Safest Path Forward:

✅ **Option B: Theme Override (Recommended)**
- Copy core → cybercom_ui
- Modify templates only (no rebuild)
- Safe, reversible, maintainable

---

**Next**: PHASE 2 - SAFE PLACEHOLDER UI DESIGN

**Status**: ✅ Forensic Analysis Complete
**Risk Assessment**: Template modifications = LOW RISK
**Recommendation**: Proceed with theme override approach
