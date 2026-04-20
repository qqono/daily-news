// ── Animated <details> ───────────────────────────────────────
document.addEventListener('click', e => {
  const summary = e.target.closest('summary');
  if (!summary) return;
  const details = summary.closest('details');
  if (!details) return;
  e.preventDefault();
  const content = details.querySelector('.expanded');
  if (details.open) {
    content.style.height = content.scrollHeight + 'px';
    content.offsetHeight;
    content.style.height = '0';
    content.addEventListener('transitionend', () => {
      details.removeAttribute('open');
      details.classList.remove('spanning');
      content.style.height = '';
    }, { once: true });
  } else {
    details.setAttribute('open', '');
    details.classList.add('spanning');
    const h = content.scrollHeight;
    content.style.height = '0';
    content.offsetHeight;
    content.style.height = h + 'px';
    content.addEventListener('transitionend', () => { content.style.height = ''; }, { once: true });
  }
});

// ── Story card ────────────────────────────────────────────────
function storyCard(item, accentClass) {
  const preview = item.summary.length > 120
    ? item.summary.slice(0, 120).replace(/\s\S*$/, '') + '…'
    : item.summary;
  const leanClass = item.lean ? `lean-${item.lean.replace(/\s+/g, '-')}` : '';
  const leanDot   = leanClass ? `<span class="lean-dot ${leanClass}" title="${item.lean}"></span>` : '';
  const card = document.createElement('details');
  card.className = `article ${accentClass}`;
  card.innerHTML = `
    <summary>
      <div class="summary-inner">
        <h2>${item.headline}</h2>
        <p class="preview">${preview}</p>
      </div>
      <span class="chevron" aria-hidden="true">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M3 5L7 9L11 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
    </summary>
    <div class="expanded">
      <p>${item.summary}</p>
      <span class="source">${leanDot}— ${item.source}</span>
    </div>`;
  return card;
}

// ── Main column section pager ─────────────────────────────────
function renderMainPager(data) {
  const container = document.getElementById('news-container');

  const SECTIONS = [
    { label: 'Headlines', key: 'top_headlines',    colorCls: 'label-red',    accentCls: 'accent-love', id: 'headlines', color: 'var(--love)' },
    { label: 'Tech',      key: 'tech_ai',          colorCls: 'label-blue',   accentCls: 'accent-pine', id: 'tech',      color: 'var(--pine)' },
    { label: 'Business',  key: 'business_finance', colorCls: 'label-green',  accentCls: 'accent-foam', id: 'business',  color: 'var(--foam)' },
    { label: 'World',     key: 'world_news',       colorCls: 'label-yellow', accentCls: 'accent-gold', id: 'world',     color: 'var(--gold)' },
    { label: 'Music',     key: 'music',            colorCls: 'label-rose',   accentCls: 'accent-rose', id: 'music',     color: 'var(--rose)' },
  ].filter(s => data[s.key] && data[s.key].length);

  const saved   = localStorage.getItem('bb-section') || SECTIONS[0].id;
  const tabBar  = document.createElement('div');
  tabBar.className = 'section-tabs';
  container.appendChild(tabBar);

  const map = {};

  SECTIONS.forEach(({ label, key, colorCls, accentCls, id, color }) => {
    const btn = document.createElement('button');
    btn.className = 'section-tab';
    btn.textContent = label;
    btn.dataset.id = id;
    tabBar.appendChild(btn);

    const sec = document.createElement('section');
    sec.id = id;
    sec.innerHTML = `<div class="section-label ${colorCls}">${label}</div>`;
    const grid = document.createElement('div');
    grid.className = 'section-grid';
    data[key].forEach(h => grid.appendChild(storyCard(h, accentCls)));
    sec.appendChild(grid);
    container.appendChild(sec);
    map[id] = { el: sec, btn, color };
  });

  function activate(id) {
    Object.entries(map).forEach(([sid, { el, btn }]) => {
      const on = sid === id;
      el.style.display  = on ? '' : 'none';
      btn.classList.toggle('active', on);
      btn.style.color   = on ? map[sid].color : '';
    });
    localStorage.setItem('bb-section', id);
    // Re-animate cards on switch
    map[id].el.querySelectorAll('.article').forEach((c, i) => {
      c.classList.remove('fade-in');
      c.offsetHeight;
      c.style.animationDelay = `${i * 55}ms`;
      c.classList.add('fade-in');
    });
  }

  tabBar.addEventListener('click', e => {
    const btn = e.target.closest('.section-tab');
    if (btn) activate(btn.dataset.id);
  });

  activate(map[saved] ? saved : SECTIONS[0].id);
}

// ── Sidebar item builders ─────────────────────────────────────
function hnItem(s, i) {
  const a = document.createElement('a');
  a.href = s.url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.className = 'sidebar-item hn-item fade-in';
  a.style.animationDelay = `${i * 45}ms`;
  a.innerHTML = `
    <span class="s-rank iris">${i + 1}</span>
    <div>
      <div class="s-title">${s.title}</div>
      <div class="s-meta">${s.score} pts · ${s.comments} comments · ${s.by}</div>
    </div>`;
  return a;
}

function githubItem(r, i) {
  const a = document.createElement('a');
  a.href = r.url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.className = 'sidebar-item gh-item fade-in';
  a.style.animationDelay = `${i * 45}ms`;
  const lang = r.language ? `${r.language} · ` : '';
  a.innerHTML = `
    <span class="s-rank pine">${i + 1}</span>
    <div>
      <div class="s-title gh-name">${r.name}</div>
      <div class="gh-desc">${r.description}</div>
      <div class="s-meta">${lang}★ ${r.stars_today} today</div>
    </div>`;
  return a;
}

function redditItem(p, i) {
  const a = document.createElement('a');
  a.href = p.permalink;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.className = 'sidebar-item reddit-item fade-in';
  a.style.animationDelay = `${i * 45}ms`;
  a.innerHTML = `
    <span class="s-rank love">${i + 1}</span>
    <div>
      <div class="s-title">${p.title}</div>
      <div class="s-meta">${p.subreddit} · ${p.score.toLocaleString()} pts · ${p.comments} comments</div>
    </div>`;
  return a;
}

function xItem(t, i) {
  const a = document.createElement('a');
  a.href = `https://x.com/search?q=${encodeURIComponent(t.topic)}`;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.className = 'sidebar-item x-item fade-in';
  a.style.animationDelay = `${i * 40}ms`;
  a.innerHTML = `
    <span class="s-rank foam">${i + 1}</span>
    <div>
      <div class="s-title">${t.topic}</div>
      <div class="s-meta">${t.posts} · ${t.category}</div>
    </div>`;
  return a;
}

// ── Sidebar pager ─────────────────────────────────────────────
function renderSidebar(data) {
  const aside = document.getElementById('hn-container');

  const TABS = [
    { id: 'hn-hot',  label: 'HN',     color: 'var(--iris)' },
    { id: 'hn-top',  label: 'Top',    color: 'var(--iris)' },
    { id: 'github',  label: 'GitHub', color: 'var(--pine)' },
    { id: 'reddit',  label: 'Reddit', color: 'var(--love)' },
    { id: 'x',       label: 'X',      color: 'var(--foam)' },
  ];

  const tabBar = document.createElement('div');
  tabBar.className = 'sidebar-tabs';
  aside.appendChild(tabBar);

  const map = {};

  TABS.forEach(({ id, label, color }) => {
    const btn = document.createElement('button');
    btn.className = 'sidebar-tab';
    btn.textContent = label;
    btn.dataset.id = id;
    tabBar.appendChild(btn);

    const panel = document.createElement('div');
    panel.className = 'sidebar-panel';
    panel.style.display = 'none';
    aside.appendChild(panel);
    map[id] = { el: panel, btn, color };
  });

  // Populate panels
  (data.hacker_news     || []).forEach((s, i) => map['hn-hot'].el.appendChild(hnItem(s, i)));
  (data.hacker_news_top || []).forEach((s, i) => map['hn-top'].el.appendChild(hnItem(s, i)));
  (data.github_trending || []).forEach((r, i) => map['github'].el.appendChild(githubItem(r, i)));
  (data.reddit_trending || []).forEach((p, i) => map['reddit'].el.appendChild(redditItem(p, i)));
  (data.x_trending      || []).forEach((t, i) => map['x'].el.appendChild(xItem(t, i)));

  function activate(id) {
    Object.entries(map).forEach(([sid, { el, btn }]) => {
      const on = sid === id;
      el.style.display = on ? 'flex' : 'none';
      btn.classList.toggle('active', on);
      btn.style.color = on ? map[sid].color : '';
    });
  }

  tabBar.addEventListener('click', e => {
    const btn = e.target.closest('.sidebar-tab');
    if (btn) activate(btn.dataset.id);
  });

  activate('hn-hot');
}

// ── Bootstrap ─────────────────────────────────────────────────
fetch('news.json')
  .then(r => r.json())
  .then(({ data, date }) => {
    document.getElementById('news-date').textContent = date;
    renderMainPager(data);
    renderSidebar(data);
  })
  .catch(() => {
    document.getElementById('news-container').innerHTML =
      '<p class="error">Could not load news.json. Serve the folder over HTTP.</p>';
  });
