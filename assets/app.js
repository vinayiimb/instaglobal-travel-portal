const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const ROOT = document.body.dataset.root || '';
const visaUrl = o => `${ROOT}visa/${o.s}.html`;
const money = n => '$' + (Math.round(n * 100) / 100).toLocaleString('en-US', {minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2});

// "Visa by" dates: n working days from today, skipping Sat/Sun (UAE weekend).
function workDays(n) {
  const d = new Date();
  while (n > 0) { d.setDate(d.getDate() + 1); if (d.getDay() % 6) n--; }
  return d;
}
const fmtDate = d => d.toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric'});
const visaBy = days => fmtDate(workDays(days));
const destDays = o => o.h ? Math.ceil(o.h / 24) : null;
$$('[data-days]').forEach(el => el.textContent = visaBy(+el.dataset.days));

// close mobile menu on navigation / outside click
document.addEventListener('click', e => { const m = $('.menu[open]'); if (m && (!m.contains(e.target) || e.target.closest('a'))) m.open = false; });

// destination search with suggestions
$$('form[data-search]').forEach(form => {
  const input = $('input', form), list = $('.sugg', form);
  let items = [], active = -1;
  const show = () => {
    const q = input.value.trim().toLowerCase();
    items = (q ? DEST.filter(o => o.n.toLowerCase().includes(q)).sort((a, b) => a.n.toLowerCase().indexOf(q) - b.n.toLowerCase().indexOf(q))
               : DEST.filter(o => o.p)).slice(0, 8);
    active = -1;
    list.innerHTML = items.map((o, i) => `<li role="option" id="sg${i}" aria-selected="false" data-i="${i}"><span class="f">${o.f}</span><span class="n">${o.n}</span><span class="m">from ${money(o.$)}<br>${o.h ? 'visa by ' + visaBy(destDays(o)) : ''}</span></li>`).join('')
      || `<li class="none">No match yet. <a class="more" href="${ROOT}contact.html">Ask our visa team</a></li>`;
    list.hidden = false; input.setAttribute('aria-expanded', 'true');
  };
  const hide = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); };
  const move = i => {
    active = (i + items.length) % items.length;
    $$('li', list).forEach((li, j) => li.setAttribute('aria-selected', j === active));
    input.setAttribute('aria-activedescendant', 'sg' + active);
  };
  input.addEventListener('focus', show);
  input.addEventListener('input', show);
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); if (list.hidden) show(); move(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(active - 1); }
    else if (e.key === 'Escape') hide();
  });
  list.addEventListener('mousedown', e => { const li = e.target.closest('[data-i]'); if (li) location.href = visaUrl(items[li.dataset.i]); });
  document.addEventListener('click', e => { if (!form.contains(e.target)) hide(); });
  form.addEventListener('submit', e => {
    e.preventDefault();
    if (!input.value.trim() && active < 0) return input.focus();
    const pick = items[Math.max(active, 0)];
    if (pick) location.href = visaUrl(pick); else location.href = `${ROOT}destinations.html?q=${encodeURIComponent(input.value)}`;
  });
});

// destination grid with region / search / sort
const grid = $('#grid');
if (grid) {
  const REGIONS = {all: 'All', gcc: 'GCC', middle_east: 'Middle East', asia: 'Asia', southeast_asia: 'Southeast Asia', south_asia: 'South Asia', africa: 'Africa', europe: 'Europe', north_america: 'North America', south_america: 'South America', oceania: 'Oceania'};
  const limit = +grid.dataset.limit || Infinity;
  const state = {g: 'all', all: false};
  const used = new Set(DEST.flatMap(o => o.g));
  const find = $('#find'), sort = $('#sort'), more = $('#more');
  find.value = new URLSearchParams(location.search).get('q') || '';
  $('#regions').innerHTML = Object.entries(REGIONS).filter(([k]) => k === 'all' || used.has(k))
    .map(([k, v]) => `<button class="chip" type="button" data-g="${k}" aria-pressed="${k === 'all'}">${v}</button>`).join('');
  $('#regions').onclick = e => {
    const b = e.target.closest('[data-g]'); if (!b) return;
    state.g = b.dataset.g;
    $$('#regions .chip').forEach(c => c.setAttribute('aria-pressed', c === b));
    render();
  };
  const sorts = {pop: (a, b) => b.p - a.p || a.n.localeCompare(b.n), price: (a, b) => a.$ - b.$, fast: (a, b) => (a.h || 1e9) - (b.h || 1e9), az: (a, b) => a.n.localeCompare(b.n)};
  const card = o => `
    <a class="card" href="${visaUrl(o)}">
      <div class="ph"><img src="${o.img}" alt="" loading="lazy">${o.h ? `<span class="tag">⚡ Visa by ${visaBy(destDays(o))}</span>` : ''}</div>
      <div class="cb">
        <div><h3>${o.f} ${o.n}</h3><p>${o.ft === 'evisa' ? 'E-Visa' : 'Visa'} · ${o.st}-day stay</p></div>
        <div class="pr"><small>from</small><b>${money(o.$)}</b></div>
      </div>
    </a>`;
  function render() {
    const q = find.value.trim().toLowerCase();
    const list = DEST.filter(o => (state.g === 'all' || o.g.includes(state.g)) && o.n.toLowerCase().includes(q)).sort(sorts[sort.value]);
    const capped = !state.all && !q && list.length > limit;
    grid.innerHTML = (capped ? list.slice(0, limit) : list).map(card).join('')
      || `<p class="empty">No destinations match “${q.replace(/</g, '&lt;')}”. <a class="more" href="${ROOT}contact.html">Ask our visa team</a></p>`;
    if (more) { more.hidden = !capped && !state.all; more.textContent = state.all ? 'Show fewer' : `Show all ${list.length} destinations`; }
  }
  find.oninput = sort.onchange = render;
  if (more) more.onclick = () => { state.all = !state.all; render(); };
  render();
}

// visa page: option picker + live price summary
const calc = $('#calc');
if (calc) {
  const V = JSON.parse($('#vdata').textContent);
  const n = {v: 1};
  const prod = () => V.products.find(p => p.id === $('input[name=pid]:checked').value);
  const sel = {speed: '', extras: new Set()};

  function fields() {
    const p = prod();
    sel.speed = ''; sel.extras.clear();
    const fast = p.addons.filter(a => a.cat === 'express');
    const other = p.addons.filter(a => a.cat !== 'express');
    $('#speed').innerHTML = !fast.length ? '' : `<fieldset class="fld"><legend>Delivery speed</legend><div class="speed">
      <label><input type="radio" name="speed" value="" checked><span>Standard<small>Visa by <i data-d="${p.days}"></i></small></span><b>Included</b></label>
      ${fast.map(a => `<label><input type="radio" name="speed" value="${a.code}"><span>⚡ ${a.name}<small>Visa by <i data-d="${a.days}"></i></small></span><b>+${money(a.total)}</b></label>`).join('')}
    </div></fieldset>`;
    $('#extras').innerHTML = !other.length ? '' : `<div class="fld"><label>Add-ons</label>${other.map(a => `<label class="addon"><input type="checkbox" value="${a.code}"> ${a.name}<span>+${money(a.total)}</span></label>`).join('')}</div>`;
    $$('[data-d]', calc).forEach(el => el.textContent = visaBy(+el.dataset.d).replace(/^\w+, /, ''));
    $$('[data-pid]').forEach(el => el.hidden = el.dataset.pid !== p.id);
    update();
  }

  function update() {
    const p = prod(), k = n.v;
    const fast = p.addons.find(a => a.code === sel.speed);
    const extras = p.addons.filter(a => sel.extras.has(a.code));
    const disc = V.offer && k >= V.offer.min ? p.svc * k * V.offer.pct / 100 : 0;
    const total = (p.total + (fast ? fast.total : 0) + extras.reduce((s, a) => s + a.total, 0)) * k - disc;
    const by = visaBy(fast ? fast.days : p.days);
    $('#c-name').textContent = p.name;
    $('#c-sub').textContent = `${p.entry} entry · stay ${p.stay} days · valid ${p.valid} days`;
    $('#c-by').textContent = by;
    $('#c-lines').innerHTML = [
      p.govt != null ? `<div><span>Government fee × ${k}</span><span>${money(p.govt * k)}</span></div><div><span>Service fee × ${k}</span><span>${money(p.svc * k)}</span></div>`
                     : `<div><span>Visa × ${k}</span><span>${money(p.total * k)}</span></div>`,
      fast ? `<div><span>${fast.name} × ${k}</span><span>${money(fast.total * k)}</span></div>` : '',
      ...extras.map(a => `<div><span>${a.name} × ${k}</span><span>${money(a.total * k)}</span></div>`),
      disc ? `<div class="disc"><span>Family ${V.offer.pct}% off service fee</span><span>−${money(disc)}</span></div>` : '',
    ].join('');
    $('#c-hint').textContent = V.offer && k < V.offer.min ? `Add ${V.offer.min - k} more traveller${V.offer.min - k > 1 ? 's' : ''} to save ${V.offer.pct}% on the service fee.` : '';
    $('#c-total').textContent = money(total);
    $('#c-n').value = k;
    $('#c-minus').disabled = k <= 1;
    $('#m-total').textContent = money(total);
    $('#m-by').textContent = 'Visa by ' + by;
  }

  $$('input[name=pid]').forEach(r => r.onchange = fields);
  calc.addEventListener('change', e => {
    if (e.target.name === 'speed') sel.speed = e.target.value;
    else if (e.target.type === 'checkbox') e.target.checked ? sel.extras.add(e.target.value) : sel.extras.delete(e.target.value);
    update();
  });
  $('#c-minus').onclick = () => { n.v = Math.max(1, n.v - 1); update(); };
  $('#c-plus').onclick = () => { n.v = Math.min(20, n.v + 1); update(); };
  fields();
}
