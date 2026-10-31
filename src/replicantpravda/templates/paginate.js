/* Deterministic measured pagination. Fonts and images must be ready before calling. */
window.paginateNewspaper = () => {
  const first = document.querySelector('.sheet');
  const pageTemplate = document.querySelector('#continuation-page');
  const source = document.querySelector('#print-content').content;
  let sheet = first, columnIndex = 0, column, fragment = null, activeId = null;
  const sheets = [first];
  const errors = [];
  function selectColumn() {
    column = sheet.querySelectorAll('.print-column')[columnIndex];
    fragment = null;
  }
  selectColumn();
  function advance() {
    if (columnIndex === 0) columnIndex = 1;
    else {
      sheet = pageTemplate.content.firstElementChild.cloneNode(true);
      document.body.append(sheet);
      sheets.push(sheet);
      columnIndex = 0;
    }
    selectColumn();
  }
  function target() {
    if (!activeId) return column;
    if (!fragment) {
      fragment = document.createElement('article');
      fragment.dataset.article = activeId;
      column.append(fragment);
    }
    return fragment;
  }
  function fits() {
    const bottom = column.getBoundingClientRect().bottom;
    return [...column.querySelectorAll('p,h2,h3,li,blockquote,figure')].every(
      e => e.getBoundingClientRect().bottom <= bottom - 2
    ) && column.scrollHeight <= column.clientHeight + 1;
  }
  function clearEmpty() {
    if (fragment && !fragment.children.length) { fragment.remove(); fragment = null; }
  }
  function place(node, next = null) {
    let destination = target();
    destination.append(node);
    // Headings must fit with the first two lines of their following block.
    let probe = null;
    if (next && /^(H2|H3)$/.test(node.tagName)) {
      probe = next.cloneNode(true);
      probe.style.maxHeight = '2.7em';
      probe.style.overflow = 'hidden';
      destination.append(probe);
    }
    const ok = fits();
    if (probe) probe.remove();
    if (ok) return;
    node.remove();
    clearEmpty();
    // Divide long paragraphs at a word boundary (or a Japanese character).
    if (node.tagName === 'P' && node.childElementCount === 0) {
      const chars = Array.from(node.textContent);
      let low = 0, high = chars.length;
      destination = target();
      destination.append(node);
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        node.textContent = chars.slice(0, middle).join('');
        if (fits()) low = middle; else high = middle - 1;
      }
      let cut = low;
      const prefix = chars.slice(0, cut).join('');
      const boundary = prefix.search(/\s+\S*$/u);
      if (boundary > cut * 0.7) cut = boundary + 1;
      node.textContent = chars.slice(0, cut).join('');
      const lineHeight = parseFloat(getComputedStyle(node).lineHeight);
      const enoughLines = node.getBoundingClientRect().height >= 2 * lineHeight - 1;
      if (cut > 0 && cut < chars.length && enoughLines) {
        const remainder = node.cloneNode(false);
        remainder.textContent = chars.slice(cut).join('');
        advance();
        place(remainder);
        return;
      }
      node.remove();
      node.textContent = chars.join('');
      clearEmpty();
    }
    if (!column.children.length) {
      errors.push({article: activeId, reason: 'A block cannot fit an empty column', text: node.textContent.slice(0, 100)});
      target().append(node);
      return;
    }
    advance();
    place(node, next);
  }
  for (const section of source.querySelectorAll('.editorial-section')) {
    const heading = section.querySelector('.section-heading').cloneNode(true);
    activeId = null;
    const firstArticle = section.querySelector('article');
    // Section heading plus article title and first text should stay together.
    const probe = document.createElement('div');
    for (const child of [...firstArticle.children].slice(0, 2)) probe.append(child.cloneNode(true));
    place(heading, probe);
    for (const article of section.querySelectorAll('article')) {
      activeId = article.dataset.article;
      fragment = null;
      const nodes = [];
      for (const child of article.children) {
        if (child.tagName === 'FOOTER') {
          for (const part of child.children) {
            const copy = part.cloneNode(true);
            copy.classList.add('source-line');
            nodes.push(copy);
          }
        } else if (child.tagName === 'UL') {
          // Each item is independently pageable and keeps its bullet.
          for (const item of child.children) {
            const list = document.createElement('ul'); list.append(item.cloneNode(true)); nodes.push(list);
          }
        } else nodes.push(child.cloneNode(true));
      }
      nodes.forEach((node, index) => place(node, nodes[index + 1]));
    }
  }
  // Balance only the final page, leaving its unused space below both columns.
  if (!errors.length) {
    const last = sheets[sheets.length - 1];
    const count = sheets.length;
    const height = last.querySelector('.print-column').clientHeight;
    const groups = [];
    for (const col of last.querySelectorAll('.print-column')) {
      for (const node of col.children) {
        groups.push({id: node.dataset.article || null,
          nodes: node.dataset.article ? [...node.children].map(n => n.cloneNode(true)) : [node.cloneNode(true)]});
      }
    }
    function refill(capacity) {
      while (sheets.length > count) sheets.pop().remove();
      for (const col of last.querySelectorAll('.print-column')) {
        col.replaceChildren(); col.style.height = `${capacity}px`;
      }
      sheet = last; columnIndex = 0; activeId = null; selectColumn();
      errors.length = 0;
      for (const group of groups) {
        activeId = group.id; fragment = null;
        group.nodes.forEach((node, index) => place(node.cloneNode(true), group.nodes[index + 1]));
      }
      return sheets.length === count && !errors.length;
    }
    let low = Math.floor(height / 4), high = height;
    for (let trial = 0; trial < 10 && high - low > 1; trial++) {
      const middle = Math.floor((low + high) / 2);
      if (refill(middle)) high = middle; else low = middle;
    }
    refill(Math.min(height, high + 1));
  }
  const articles = {};
  const images = [];
  const glossary_cards = [];
  sheets.forEach((page, index) => {
    page.dataset.page = index + 1;
    page.querySelector('.page-number').textContent = `${index + 1} / ${sheets.length}`;
    page.querySelectorAll('[data-article]').forEach(article => {
      article.querySelectorAll('.print-glossary-card').forEach(card => {
        glossary_cards.push({index: Number(card.dataset.glossaryIndex), page: index + 1,
          term: card.querySelector('h3').textContent, definition: card.querySelector('p').textContent});
      });
      article.querySelectorAll('.article-illustration img').forEach(image => {
        images.push({article: article.dataset.article, page: index + 1, src: image.getAttribute('src')});
      });
      (articles[article.dataset.article] ||= []).push({page: index + 1, text: article.textContent});
    });
  });
  const columns = sheets.map((page, index) => ({
    page: index + 1,
    fill: [...page.querySelectorAll('.print-column')].map(col => {
      const last = col.querySelector('article:last-child') || col.lastElementChild;
      return last ? Math.round(1000 * (last.getBoundingClientRect().bottom -
        col.getBoundingClientRect().top) / col.clientHeight) / 1000 : 0;
    })
  }));
  return {page_count: sheets.length, articles, images, glossary_cards, columns, errors};
};
