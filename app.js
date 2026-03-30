const dateEl = document.getElementById('today-date');
dateEl.textContent = new Date().toLocaleDateString('en-US', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
});

function storyCard(item, sectionClass) {
  const preview = item.summary.length > 120
    ? item.summary.slice(0, 120).replace(/\s\S*$/, '') + '…'
    : item.summary;

  const card = document.createElement('details');
  card.className = `article ${sectionClass}`;
  card.innerHTML = `
    <summary>
      <h2>${item.headline}</h2>
      <p class="preview">${preview}</p>
      <span class="chevron" aria-hidden="true">›</span>
    </summary>
    <div class="expanded">
      <p>${item.summary}</p>
      <span class="source">— ${item.source}</span>
    </div>
  `;
  return card;
}

function section(label, colorClass, cards) {
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

    const headlineCards = data.top_headlines.map(h => storyCard(h, 'featured'));
    container.appendChild(section('Top Headlines', 'label-red', headlineCards));

    const singles = [
      { label: 'Tech & AI',          key: 'tech_ai',          cls: 'label-blue'   },
      { label: 'Business & Finance', key: 'business_finance', cls: 'label-green'  },
      { label: 'World News',         key: 'world_news',       cls: 'label-yellow' },
    ];

    singles.forEach(({ label, key, cls }) => {
      if (data[key]) {
        container.appendChild(section(label, cls, [storyCard(data[key], 'single')]));
      }
    });
  })
  .catch(() => {
    document.getElementById('news-container').innerHTML =
      '<p class="error">Could not load news.json. Serve the folder over HTTP.</p>';
  });
