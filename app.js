const dateEl = document.getElementById('today-date');
dateEl.textContent = new Date().toLocaleDateString('en-US', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
});

// Animated <details> open/close
document.addEventListener('click', e => {
  const summary = e.target.closest('summary');
  if (!summary) return;
  const details = summary.closest('details');
  if (!details) return;
  e.preventDefault();

  const content = details.querySelector('.expanded');

  if (details.open) {
    content.style.height = content.scrollHeight + 'px';
    content.offsetHeight; // force reflow
    content.style.height = '0';
    content.addEventListener('transitionend', () => {
      details.removeAttribute('open');
      content.style.height = '';
    }, { once: true });
  } else {
    details.setAttribute('open', '');
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
      <span class="source">— ${item.source}</span>
    </div>
  `;
  return card;
}

function section(label, colorClass, accentClass, cards) {
  const sec = document.createElement('section');
  sec.innerHTML = `<div class="section-label ${colorClass}">${label}</div>`;
  const grid = document.createElement('div');
  grid.className = 'section-grid';
  cards.forEach(c => grid.appendChild(c));
  sec.appendChild(grid);
  return sec;
}

fetch('news.json')
  .then(r => r.json())
  .then(({ data, date }) => {
    document.getElementById('news-date').textContent = date;
    const container = document.getElementById('news-container');

    const headlineCards = data.top_headlines.map(h => storyCard(h, 'accent-love'));
    container.appendChild(section('Top Headlines', 'label-red', 'accent-love', headlineCards));

    const singles = [
      { label: 'Tech & AI',          key: 'tech_ai',          colorCls: 'label-blue',   accentCls: 'accent-pine'   },
      { label: 'Business & Finance', key: 'business_finance', colorCls: 'label-green',  accentCls: 'accent-foam'   },
      { label: 'World News',         key: 'world_news',       colorCls: 'label-yellow', accentCls: 'accent-gold'   },
    ];

    singles.forEach(({ label, key, colorCls, accentCls }) => {
      if (data[key]) {
        container.appendChild(section(label, colorCls, accentCls, [storyCard(data[key], accentCls)]));
      }
    });

    // Stagger card entrance
    document.querySelectorAll('.article').forEach((card, i) => {
      card.style.animationDelay = `${i * 60}ms`;
      card.classList.add('fade-in');
    });
  })
  .catch(() => {
    document.getElementById('news-container').innerHTML =
      '<p class="error">Could not load news.json. Serve the folder over HTTP.</p>';
  });
