// nav.js — shared navigation sidebar injected on every page
(function () {
  const HOME_ICON    = `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 8.5L9 2l7 6.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 7.5V15a1 1 0 001 1h3v-4h2v4h3a1 1 0 001-1V7.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const NEWS_ICON    = `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="3" width="14" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/><line x1="5" y1="7" x2="13" y2="7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><line x1="5" y1="10" x2="13" y2="10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><line x1="5" y1="13" x2="9" y2="13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
  const CONTACT_ICON = `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="4" width="14" height="10" rx="2" stroke="currentColor" stroke-width="1.5"/><polyline points="2,6 9,11 16,6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const GEAR_ICON    = `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="2.5" stroke="currentColor" stroke-width="1.5"/><path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M3.55 3.55l1.41 1.41M13.04 13.04l1.41 1.41M3.55 14.45l1.41-1.41M13.04 4.96l1.41-1.41" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;

  const PAGES = [
    { href: 'home.html',    label: 'Home',    icon: HOME_ICON    },
    { href: 'index.html',   label: 'News',    icon: NEWS_ICON    },
    { href: 'contact.html', label: 'Contact', icon: CONTACT_ICON },
  ];

  const file = location.pathname.split('/').pop() || 'index.html';

  // ── Build sidebar ──────────────────────────────────────────
  const nav = document.createElement('nav');
  nav.id = 'nav-sidebar';
  nav.setAttribute('aria-label', 'Site navigation');

  PAGES.forEach(p => {
    const a = document.createElement('a');
    a.href = p.href;
    a.className = 'nav-link';
    a.dataset.label = p.label;
    a.innerHTML = p.icon;
    if (file === p.href || (file === '' && p.href === 'index.html')) {
      a.classList.add('active');
    }
    nav.appendChild(a);
  });

  const spacer = document.createElement('div');
  spacer.className = 'nav-spacer';
  nav.appendChild(spacer);

  const settingsBtn = document.createElement('button');
  settingsBtn.id = 'settings-btn';
  settingsBtn.className = 'nav-link';
  settingsBtn.dataset.label = 'Settings';
  settingsBtn.type = 'button';
  settingsBtn.setAttribute('aria-label', 'Settings');
  settingsBtn.innerHTML = GEAR_ICON;
  nav.appendChild(settingsBtn);

  // ── Settings popout ────────────────────────────────────────
  const popout = document.createElement('div');
  popout.id = 'settings-popout';
  popout.setAttribute('aria-hidden', 'true');
  popout.innerHTML = `
    <div class="settings-title">Settings</div>
    <label class="settings-row">
      <span>Light mode</span>
      <span class="toggle-wrap">
        <input type="checkbox" id="toggle-light">
        <span class="toggle-track"><span class="toggle-thumb"></span></span>
      </span>
    </label>
    <label class="settings-row">
      <span>List view</span>
      <span class="toggle-wrap">
        <input type="checkbox" id="toggle-list">
        <span class="toggle-track"><span class="toggle-thumb"></span></span>
      </span>
    </label>
  `;

  document.body.prepend(nav);
  document.body.appendChild(popout);

  // ── Apply stored prefs ─────────────────────────────────────
  function applyLight(on) {
    document.body.classList.toggle('light-mode', on);
    document.getElementById('toggle-light').checked = on;
  }
  function applyList(on) {
    document.body.classList.toggle('list-view', on);
    document.getElementById('toggle-list').checked = on;
  }

  applyLight(localStorage.getItem('bb-light') === '1');
  applyList(localStorage.getItem('bb-list') === '1');

  document.getElementById('toggle-light').addEventListener('change', e => {
    localStorage.setItem('bb-light', e.target.checked ? '1' : '0');
    applyLight(e.target.checked);
  });
  document.getElementById('toggle-list').addEventListener('change', e => {
    localStorage.setItem('bb-list', e.target.checked ? '1' : '0');
    applyList(e.target.checked);
  });

  // ── Popout open/close ──────────────────────────────────────
  let popoutOpen = false;
  settingsBtn.addEventListener('click', e => {
    e.stopPropagation();
    popoutOpen = !popoutOpen;
    popout.classList.toggle('open', popoutOpen);
    popout.setAttribute('aria-hidden', String(!popoutOpen));
  });
  document.addEventListener('click', e => {
    if (popoutOpen && !popout.contains(e.target)) {
      popoutOpen = false;
      popout.classList.remove('open');
      popout.setAttribute('aria-hidden', 'true');
    }
  });
})();
