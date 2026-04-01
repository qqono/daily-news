// Animated <details> open/close — spans full width on desktop when open
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
    content.addEventListener('transitionend', () => {
      content.style.height = '';
    }, { once: true });
  }
});

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
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M3 5L7 9L11 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
    </summary>
    <div class="expanded">
      <p>${item.summary}</p>
      <span class="source">${leanDot}— ${item.source}</span>
    </div>
  `;
  return card;
}

function section(label, colorClass, accentClass, cards, id) {
  const sec = document.createElement('section');
  if (id) sec.id = id;
  sec.innerHTML = `<div class="section-label ${colorClass}">${label}</div>`;
  const grid = document.createElement('div');
  grid.className = 'section-grid';
  cards.forEach(c => grid.appendChild(c));
  sec.appendChild(grid);
  return sec;
}

function hnItem(s, i) {
  const a = document.createElement('a');
  a.href = s.url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.className = 'hn-item fade-in';
  a.style.animationDelay = `${i * 45}ms`;
  a.innerHTML = `
    <span class="hn-rank">${i + 1}</span>
    <div>
      <div class="hn-title">${s.title}</div>
      <div class="hn-meta">${s.score} pts · ${s.comments} comments · ${s.by}</div>
    </div>
  `;
  return a;
}

function renderHN(hot, top) {
  const aside = document.getElementById('hn-container');

  // Header: label + Hot/Top tabs
  const header = document.createElement('div');
  header.className = 'hn-header';
  header.innerHTML = `
    <div class="section-label label-iris hn-label">HN Trending</div>
    <div class="hn-tabs">
      <button class="hn-tab active" data-tab="hot">Hot</button>
      <button class="hn-tab" data-tab="top">Top</button>
    </div>
  `;
  aside.appendChild(header);

  const hotList = document.createElement('div');
  hot.forEach((s, i) => hotList.appendChild(hnItem(s, i)));
  aside.appendChild(hotList);

  const topList = document.createElement('div');
  topList.style.display = 'none';
  (top || []).forEach((s, i) => topList.appendChild(hnItem(s, i)));
  aside.appendChild(topList);

  header.querySelectorAll('.hn-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      header.querySelectorAll('.hn-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      hotList.style.display = btn.dataset.tab === 'hot' ? '' : 'none';
      topList.style.display = btn.dataset.tab === 'top' ? '' : 'none';
    });
  });
}

function renderXTrending(topics) {
  const aside = document.getElementById('hn-container');

  const hr = document.createElement('hr');
  hr.className = 'x-divider';
  aside.appendChild(hr);

  const label = document.createElement('div');
  label.className = 'section-label label-foam';
  label.textContent = 'Trending on X';
  aside.appendChild(label);

  topics.forEach((t, i) => {
    const a = document.createElement('a');
    a.href = `https://x.com/search?q=${encodeURIComponent(t.topic)}`;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.className = 'x-item fade-in';
    a.style.animationDelay = `${i * 40}ms`;
    a.innerHTML = `
      <span class="x-rank">${i + 1}</span>
      <div>
        <div class="x-topic">${t.topic}</div>
        <div class="x-meta">${t.posts} · ${t.category}</div>
      </div>
    `;
    aside.appendChild(a);
  });
}

fetch('news.json')
  .then(r => r.json())
  .then(({ data, date }) => {
    document.getElementById('news-date').textContent = date;
    const container = document.getElementById('news-container');

    const headlineCards = data.top_headlines.map(h => storyCard(h, 'accent-love'));
    container.appendChild(section('Top Headlines', 'label-red', 'accent-love', headlineCards, 'headlines'));

    const categories = [
      { label: 'Tech & AI',          key: 'tech_ai',          colorCls: 'label-blue',   accentCls: 'accent-pine', id: 'tech'     },
      { label: 'Business & Finance', key: 'business_finance', colorCls: 'label-green',  accentCls: 'accent-foam', id: 'business' },
      { label: 'World News',         key: 'world_news',       colorCls: 'label-yellow', accentCls: 'accent-gold', id: 'world'    },
      { label: 'Music',              key: 'music',            colorCls: 'label-rose',   accentCls: 'accent-rose', id: 'music'    },
    ];

    categories.forEach(({ label, key, colorCls, accentCls, id }) => {
      const items = data[key];
      if (items && items.length) {
        container.appendChild(section(label, colorCls, accentCls, items.map(h => storyCard(h, accentCls)), id));
      }
    });

    // Stagger card entrance
    document.querySelectorAll('.article').forEach((card, i) => {
      card.style.animationDelay = `${i * 60}ms`;
      card.classList.add('fade-in');
    });

    // Right column
    if (data.hacker_news && data.hacker_news.length) {
      renderHN(data.hacker_news, data.hacker_news_top || []);
    }
    if (data.x_trending && data.x_trending.length) {
      renderXTrending(data.x_trending);
    }
  })
  .catch(() => {
    document.getElementById('news-container').innerHTML =
      '<p class="error">Could not load news.json. Serve the folder over HTTP.</p>';
  });
