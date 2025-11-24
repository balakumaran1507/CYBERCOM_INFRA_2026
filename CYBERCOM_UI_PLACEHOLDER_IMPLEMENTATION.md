# 🎯 CYBERCOM CTF 2026 - SAFE PLACEHOLDER UI IMPLEMENTATION

**Phase**: 2 - Safe Placeholder Design & Implementation
**Risk Level**: LOW (Template-only modifications)
**Rollback**: Simple (git revert or theme switch)

---

## PHASE 2: SAFE PLACEHOLDER UI DESIGN

### 🎨 Design Philosophy

**CYBERCOM Cyber Theme - Minimal & Stable**

```
Design Principles:
├── Dark cyber aesthetic (hacker-style)
├── Minimal animations (stability over flash)
├── Clean typography (monospace accents)
├── Clear information hierarchy
└── Professional, not over-designed

Color Palette:
├── Primary: #00ff41 (Matrix green)
├── Accent: #00d4ff (Cyber blue)
├── Dark: #0a0e27 (Deep navy)
├── Surface: #1a1f3a (Card background)
└── Text: #e0e0e0 (Light grey)

Typography:
├── Headers: 'Rajdhani', sans-serif (cyber style)
├── Body: System sans-serif
└── Code/Accents: 'Courier New', monospace
```

---

## 🚀 IMPLEMENTATION GUIDE

### Step 1: Create Theme Sandbox

```bash
# Navigate to themes directory
cd /home/kali/CTF/CTFd/CTFd/themes

# Copy core theme to cybercom_ui
cp -r core cybercom_ui

# Verify structure
ls -la cybercom_ui/
```

**Result**: Safe sandbox for modifications, core theme untouched

---

### Step 2: Modify Base Template

**File**: `cybercom_ui/templates/base.html`

#### Change 1: Update Title (Line 4)
```html
<!-- BEFORE -->
<title>{{ title or Configs.ctf_name }}</title>

<!-- AFTER -->
<title>{% if title %}{{ title }} | {% endif %}CYBERCOM CTF 2026</title>
```

#### Change 2: Add Custom CSS Block (After line 13)
```html
{% block stylesheets %}
  {{ Assets.css("assets/scss/main.scss") }}

  <!-- CYBERCOM Custom Styles -->
  <style>
    :root {
      --cybercom-primary: #00ff41;
      --cybercom-accent: #00d4ff;
      --cybercom-dark: #0a0e27;
      --cybercom-surface: #1a1f3a;
      --cybercom-text: #e0e0e0;
    }

    /* Dark theme override */
    [data-theme="dark"] {
      --bs-body-bg: var(--cybercom-dark);
      --bs-body-color: var(--cybercom-text);
    }

    /* Navbar styling */
    .navbar-dark {
      background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%) !important;
      border-bottom: 1px solid rgba(0, 255, 65, 0.2);
    }

    .navbar-brand {
      font-family: 'Rajdhani', 'Arial Black', sans-serif;
      font-weight: 700;
      font-size: 1.5rem;
      letter-spacing: 2px;
      color: var(--cybercom-primary) !important;
      text-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
    }

    .nav-link {
      color: var(--cybercom-text) !important;
      transition: color 0.2s ease;
    }

    .nav-link:hover {
      color: var(--cybercom-primary) !important;
    }

    /* Challenge cards */
    .challenge-button {
      background: var(--cybercom-surface) !important;
      border: 1px solid rgba(0, 255, 65, 0.3) !important;
      color: var(--cybercom-text) !important;
      transition: all 0.3s ease;
      min-height: 120px;
    }

    .challenge-button:hover {
      border-color: var(--cybercom-primary) !important;
      box-shadow: 0 0 15px rgba(0, 255, 65, 0.3);
      transform: translateY(-2px);
    }

    .challenge-solved {
      background: rgba(0, 255, 65, 0.15) !important;
      border-color: var(--cybercom-primary) !important;
    }

    .challenge-inner p {
      font-weight: 600;
      margin-bottom: 0.5rem;
      font-size: 1rem;
    }

    .challenge-inner span {
      color: var(--cybercom-accent);
      font-family: 'Courier New', monospace;
      font-weight: bold;
    }

    /* Jumbotron header */
    .jumbotron {
      background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
      border-bottom: 2px solid rgba(0, 255, 65, 0.3);
      padding: 3rem 0;
    }

    .jumbotron h1 {
      color: var(--cybercom-primary);
      font-family: 'Rajdhani', sans-serif;
      font-weight: 700;
      letter-spacing: 3px;
      text-shadow: 0 0 20px rgba(0, 255, 65, 0.5);
    }

    /* Category headers */
    .category-header h3 {
      color: var(--cybercom-accent);
      font-family: 'Courier New', monospace;
      font-size: 1.5rem;
      border-left: 4px solid var(--cybercom-primary);
      padding-left: 1rem;
      margin-bottom: 1.5rem;
    }

    /* Footer */
    .footer {
      background: var(--cybercom-dark);
      border-top: 1px solid rgba(0, 255, 65, 0.2);
      padding: 2rem 0;
    }

    .footer small {
      color: var(--cybercom-primary) !important;
      font-family: 'Courier New', monospace;
      font-size: 0.9rem;
      letter-spacing: 1px;
    }

    /* Buttons */
    .btn-primary {
      background: var(--cybercom-primary) !important;
      border-color: var(--cybercom-primary) !important;
      color: #000 !important;
      font-weight: 600;
    }

    .btn-primary:hover {
      box-shadow: 0 0 15px rgba(0, 255, 65, 0.5);
    }

    /* Forms */
    input, textarea, select {
      background: var(--cybercom-surface) !important;
      border: 1px solid rgba(0, 255, 65, 0.3) !important;
      color: var(--cybercom-text) !important;
    }

    input:focus, textarea:focus, select:focus {
      border-color: var(--cybercom-primary) !important;
      box-shadow: 0 0 10px rgba(0, 255, 65, 0.2) !important;
    }

    /* Spinner */
    .fa-spin.spinner {
      color: var(--cybercom-primary);
    }
  </style>

  <!-- Google Fonts: Rajdhani -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&display=swap" rel="stylesheet">
{% endblock %}
```

#### Change 3: Update Footer (Lines 52-60)
```html
<!-- BEFORE -->
<footer class="footer">
  <div class="container text-center">
    <a href="https://ctfd.io" class="text-secondary">
      <small class="text-muted">
        {% trans %}Powered by CTFd{% endtrans %}
      </small>
    </a>
  </div>
</footer>

<!-- AFTER -->
<footer class="footer">
  <div class="container text-center">
    <small>
      <span style="color: var(--cybercom-primary);">█▓▒░</span>
      CYBERCOM CTF 2026
      <span style="color: var(--cybercom-primary);">░▒▓█</span>
      <span style="opacity: 0.6;"> | Engineered for Excellence in Cybersecurity</span>
    </small>
  </div>
</footer>
```

---

### Step 3: Modify Navbar

**File**: `cybercom_ui/templates/components/navbar.html`

#### Change: Brand Text (Lines 3-14)
```html
<!-- BEFORE -->
<a href="{{ url_for('views.static_html', route='/') }}" class="navbar-brand">
  {% if Configs.ctf_logo %}
    <img ... >
  {% else %}
    {{ Configs.ctf_name }}
  {% endif %}
</a>

<!-- AFTER -->
<a href="{{ url_for('views.static_html', route='/') }}" class="navbar-brand">
  {% if Configs.ctf_logo %}
    <img
        class="img-responsive ctf_logo"
        src="{{ url_for('views.files', path=Configs.ctf_logo) }}"
        alt="CYBERCOM CTF 2026"
        height="30"
    >
  {% else %}
    <span style="color: var(--cybercom-primary);">█▓▒░</span>
    CYBERCOM
    <span style="font-weight: 400; opacity: 0.8; margin-left: 8px;">CTF 2026</span>
  {% endif %}
</a>
```

---

### Step 4: Modify Challenges Page

**File**: `cybercom_ui/templates/challenges.html`

#### Change: Jumbotron Header (Lines 4-10)
```html
<!-- BEFORE -->
<div class="jumbotron">
  <div class="container">
    <h1>
      {% trans %}Challenges{% endtrans %}
    </h1>
  </div>
</div>

<!-- AFTER -->
<div class="jumbotron">
  <div class="container">
    <h1>
      <span style="color: var(--cybercom-primary);">█▓▒░</span>
      CHALLENGES
      <span style="color: var(--cybercom-primary);">░▒▓█</span>
    </h1>
    <p style="color: var(--cybercom-text); opacity: 0.8; font-family: 'Courier New', monospace; margin-top: 1rem;">
      [ SELECT YOUR TARGET ]
    </p>
  </div>
</div>
```

---

### Step 5: Activate Theme

#### Method A: Admin Panel (Recommended)
```
1. Login as admin
2. Admin Panel → Config → Style
3. Theme: Select "cybercom_ui"
4. Save Changes
5. Refresh page
```

#### Method B: Database
```sql
docker compose exec db mysql -u root -pctfd ctfd -e \
  "UPDATE config SET value = 'cybercom_ui' WHERE key = 'theme_name';"
```

#### Method C: Environment Variable
```bash
# In docker-compose.yml or .env
THEME_NAME=cybercom_ui
```

---

## 📋 VERIFICATION CHECKLIST

After activation, verify:

```bash
# 1. Check active theme
docker compose logs ctfd | grep -i theme

# 2. Access platform
curl -s http://localhost:8000 | grep -i CYBERCOM
# Should see: CYBERCOM CTF 2026

# 3. Test pages
- Homepage: http://localhost:8000
- Challenges: http://localhost:8000/challenges
- Scoreboard: http://localhost:8000/scoreboard
- Admin: http://localhost:8000/admin

# 4. Verify functionality
✅ Navbar works (all links functional)
✅ Challenges load (Alpine.js working)
✅ Challenge modal opens (Bootstrap working)
✅ Flag submission works (API working)
✅ Scoreboard loads (graphs visible)
✅ Admin panel accessible
```

---

## 🔄 ROLLBACK INSTRUCTIONS

### If UI breaks:

#### Quick Fix (Admin Panel):
```
Admin Panel → Config → Theme → "core" → Save
```

#### Database Fix:
```sql
docker compose exec db mysql -u root -pctfd ctfd -e \
  "UPDATE config SET value = 'core' WHERE key = 'theme_name';"
```

#### Delete Theme:
```bash
rm -rf /home/kali/CTF/CTFd/CTFd/themes/cybercom_ui
docker compose restart ctfd
```

#### Git Rollback:
```bash
git checkout CTFd/themes/cybercom_ui
# or
git reset --hard HEAD
```

---

## 🎯 WHAT THIS PLACEHOLDER ACHIEVES

### ✅ Visual Identity:
- CYBERCOM branding throughout
- Cyber/hacker aesthetic
- Professional dark theme
- Matrix-inspired colors

### ✅ Functionality Preserved:
- All core features work
- Challenge system intact
- Scoreboard functional
- Admin panel operational
- Submissions working

### ✅ Safety:
- No webpack rebuild needed
- No JS modifications
- Alpine.js untouched
- Bootstrap intact
- Instantly reversible

---

## 📊 BEFORE vs AFTER

| Element | Before (Core) | After (CYBERCOM) |
|---------|--------------|------------------|
| **Navbar** | CTFd logo | CYBERCOM branding |
| **Colors** | Blue/grey | Matrix green/cyan |
| **Typography** | Standard | Rajdhani + monospace |
| **Challenges** | Plain cards | Glowing borders |
| **Footer** | "Powered by CTFd" | CYBERCOM branding |
| **Theme** | Generic | Cyber/hacker style |

---

## 🚀 NEXT STEPS (Future Phases)

This placeholder is designed to be **expanded** later:

### Phase B: Enhanced Design System
- Custom icons
- Animated transitions
- Advanced layouts

### Phase C: Dynamic Dashboards
- Phase 2 leaderboard
- Suspicion analytics
- Challenge health metrics

### Phase D: Threat Interface
- Live activity feed
- Network-style visualizations
- Hacker terminal aesthetics

### Phase E: Final Polish
- Logo animations
- Sound effects
- Easter eggs
- Custom 404 pages

---

## ⚠️ IMPORTANT NOTES

### What This IS:
✅ Safe, minimal placeholder
✅ Professional CYBERCOM branding
✅ Fully functional
✅ Easy to maintain
✅ Foundation for future work

### What This IS NOT:
❌ Final UI design
❌ Production-perfect polish
❌ Custom JavaScript features
❌ Animated/complex interactions

**Philosophy**: **Safety > Beauty** at this stage

---

## 📞 SUPPORT

### If Issues Occur:

1. **Check logs**: `docker compose logs ctfd | tail -50`
2. **Rollback theme**: Switch to "core" in admin
3. **Clear cache**: `docker compose restart ctfd`
4. **Test core theme**: Verify issue isn't systemic

### Common Issues:

**Issue**: Challenges don't load
**Fix**: Check Alpine.js bindings intact (x-data, x-show)

**Issue**: Navbar broken
**Fix**: Verify Bootstrap classes unchanged

**Issue**: CSS not applying
**Fix**: Clear browser cache, check theme active

**Issue**: Footer unchanged
**Fix**: Verify you modified cybercom_ui, not core

---

**Status**: ✅ Implementation Guide Complete
**Risk Level**: LOW
**Estimated Time**: 15-20 minutes
**Rollback Time**: < 1 minute

**Ready to implement**: All code provided, tested approach, safe modifications only.
