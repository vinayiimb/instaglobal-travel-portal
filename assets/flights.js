// Flight search: our UI end to end, partner checkout only at the final "Continue to booking" click.
const F = {from: null, to: null, data: null, sort: 'best', pick: null};
const CUR = {inr: '₹', usd: '$', aed: 'AED '};
const fmtPrice = (n, c) => (CUR[c] || '') + Math.round(n).toLocaleString(c === 'inr' ? 'en-IN' : 'en-US');
const fmtDur = m => m ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m` : '';
const stopsText = n => n === 0 ? 'Non-stop' : `${n} stop${n > 1 ? 's' : ''}`;
// Times come with the airport's UTC offset; show them as local airport time.
const localTime = iso => iso.slice(11, 16);
const longDate = d => new Date(d.slice(0, 10) + 'T12:00').toLocaleDateString('en-GB', {weekday: 'short', day: 'numeric', month: 'short'});
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

// airport/city pickers
function picker(input, key) {
  const list = input.parentElement.querySelector('.sugg');
  let items = [], timer;
  const choose = p => { F[key] = p; input.value = `${p.city} (${p.code})`; list.hidden = true; };
  input.addEventListener('input', () => {
    F[key] = null; clearTimeout(timer);
    const term = input.value.trim();
    if (term.length < 2) { list.hidden = true; return; }
    timer = setTimeout(async () => {
      items = await fetch('/api/places?term=' + encodeURIComponent(term)).then(r => r.json()).catch(() => []);
      list.innerHTML = items.map((p, i) => `<li role="option" data-i="${i}"><span class="f">${p.type === 'city' ? '🏙' : '✈️'}</span><span class="n">${esc(p.name)}<br><small class="muted">${esc(p.country)}</small></span><span class="m"><b>${p.code}</b></span></li>`).join('') || '<li class="none">No airports found</li>';
      list.hidden = false;
    }, 180);
  });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !list.hidden && items[0]) { e.preventDefault(); choose(items[0]); } });
  list.addEventListener('mousedown', e => { const li = e.target.closest('[data-i]'); if (li) choose(items[li.dataset.i]); });
  input.addEventListener('blur', () => setTimeout(() => list.hidden = true, 150));
  return choose;
}
const setFrom = picker($('#f-from'), 'from');
const setTo = picker($('#f-to'), 'to');

$('#f-swap').onclick = () => { const a = F.from, b = F.to; if (b) setFrom(b); else { F.from = null; $('#f-from').value = ''; } if (a) setTo(a); else { F.to = null; $('#f-to').value = ''; } };
const today = new Date().toISOString().slice(0, 10);
$('#f-depart').min = $('#f-return').min = today;
$('#f-depart').onchange = () => { $('#f-return').min = $('#f-depart').value; };

const resetFilters = () => { F.f = {stops: 'any', dep: new Set(), arr: new Set(), air: new Set(), max: null}; };
resetFilters();
const memo = new Map(); // same search again (back button, re-search) renders instantly

async function search(push = true) {
  const depart = $('#f-depart').value, ret = $('#f-return').value;
  if (!F.from || !F.to) return status('Choose where you’re flying from and to.');
  if (!depart) return status('Choose a departure date.');
  if (ret && ret < depart) return status('Your return date is before departure.');
  const q = new URLSearchParams({origin: F.from.code, destination: F.to.code, depart, currency: $('#f-cur').value, direct: $('#f-direct').checked});
  if (ret) q.set('return', ret);
  F.q = q;
  if (push) history.pushState(null, '', '?' + new URLSearchParams({from: F.from.code, fromName: F.from.city, to: F.to.code, toName: F.to.city, toCountry: F.to.country || '', ...Object.fromEntries(q)}));
  $('#results').hidden = false; status('');
  $('#rs-route').textContent = `${F.from.city} → ${F.to.city}`;
  $('#rs-meta').textContent = `${longDate(depart)}${ret ? ' – ' + longDate(ret) : ' · One way'} · 1 adult · Economy`;
  $('#results').scrollIntoView({behavior: 'smooth', block: 'start'});
  resetFilters();
  const key = q.toString();
  if (memo.has(key)) { F.data = memo.get(key); return render(); }
  $('#tabs').innerHTML = ''; $('#fbody').innerHTML = ''; $('#count').textContent = '';
  $('#calwrap').hidden = $('#insight').hidden = true;
  $('#list').innerHTML = `<div class="progress" role="status"><i></i></div><p class="muted small" style="margin:10px 0 16px">Searching Google Flights for the best fares… this takes a few seconds.</p>` + '<div class="skel"></div>'.repeat(4);
  try {
    const r = await fetch('/api/flights?' + q);
    // On a static host (e.g. GitHub Pages) there is no API server, so the reply isn't JSON.
    const j = await r.json().catch(() => ({error: 'Live fares need our booking server, which isn’t running on this preview. Our travel desk can find your fare on WhatsApp.'}));
    if (!r.ok) throw new Error(j.error || 'Search failed');
    memo.set(key, j);
    if (F.q.toString() === key) { F.data = j; render(); }
  } catch (e) {
    $('#list').innerHTML = `<div class="unavail"><h2 style="font-size:28px">We couldn't load fares right now.</h2><p class="lead" style="margin:10px auto 0">${esc(e.message)}</p>
      <div class="row"><a class="btn wa" href="https://wa.me/971509518129?text=${encodeURIComponent(`Hi, I need a flight ${F.from.code} → ${F.to.code} on ${depart}`)}">Ask our travel desk</a></div></div>`;
  }
}
const status = t => { $('#f-msg').textContent = t; };
$('#f-form').onsubmit = e => { e.preventDefault(); search(); };
$('#rs-edit').onclick = () => { $('#f-form').scrollIntoView({behavior: 'smooth', block: 'center'}); $('#f-from').focus({preventScroll: true}); };

// ---------- results
const SLOTS = [['Before 6 AM', '🌅', 0, 6], ['6 AM – 12 PM', '☀️', 6, 12], ['12 PM – 6 PM', '🌤', 12, 18], ['After 6 PM', '🌙', 18, 24]];
const slotOf = iso => SLOTS.findIndex(([, , a, b]) => +iso.slice(11, 13) >= a && +iso.slice(11, 13) < b);
const carriers = f => f.segments ? [...new Set(f.segments.map(s => s.airline))] : [f.airlineName];
const plusDays = (a, b) => Math.round((new Date(b.slice(0, 10)) - new Date(a.slice(0, 10))) / 864e5);
const minBy = (list, fn) => list.reduce((m, f) => (m === null || fn(f) < fn(m) ? f : m), null);
const stopKey = n => n >= 2 ? '2' : String(n);

function passes(f, skip) {
  const x = F.f;
  if (skip !== 'stops' && x.stops !== 'any' && stopKey(f.stops) !== x.stops) return false;
  if (skip !== 'dep' && x.dep.size && !x.dep.has(slotOf(f.departAt))) return false;
  if (skip !== 'arr' && x.arr.size && f.arriveAt && !x.arr.has(slotOf(f.arriveAt))) return false;
  if (skip !== 'air' && x.air.size && !carriers(f).some(a => x.air.has(a))) return false;
  if (skip !== 'max' && x.max && f.price > x.max) return false;
  return true;
}

function filtersHTML() {
  const {flights, currency} = F.data;
  const low = (key, test) => { const m = minBy(flights.filter(f => passes(f, key) && test(f)), f => f.price); return m ? fmtPrice(m.price, currency) : ''; };
  const stops = [['any', 'Any', () => true], ['0', 'Non-stop', f => f.stops === 0], ['1', '1 stop', f => f.stops === 1], ['2', '2+ stops', f => f.stops >= 2]]
    .filter(([k, , t]) => k === 'any' || flights.some(t));
  const slots = (key, field) => `<div class="slots">${SLOTS.map(([label, icon], i) => {
    const n = flights.filter(f => f[field] && slotOf(f[field]) === i).length;
    return `<button type="button" class="slot" data-k="${key}" data-v="${i}" aria-pressed="${F.f[key].has(i)}"${n ? '' : ' disabled'}><span>${icon}</span><small>${label}</small></button>`;
  }).join('')}</div>`;
  const airlines = [...new Set(flights.flatMap(carriers))].sort();
  const prices = flights.map(f => f.price), lo = Math.min(...prices), hi = Math.max(...prices), cur = F.f.max || hi;
  return `
  <div class="fgrp"><h4>Stops</h4>${stops.map(([k, label, t]) => `<label class="frow"><input type="radio" name="fstops" value="${k}"${F.f.stops === k ? ' checked' : ''}><span>${label}</span><small>${k === 'any' ? '' : low('stops', t)}</small></label>`).join('')}</div>
  <div class="fgrp"><h4>Departure from ${esc(F.from.city)}</h4>${slots('dep', 'departAt')}</div>
  ${flights.some(f => f.arriveAt) ? `<div class="fgrp"><h4>Arrival in ${esc(F.to.city)}</h4>${slots('arr', 'arriveAt')}</div>` : ''}
  <div class="fgrp"><h4>Airlines</h4>${airlines.map(a => `<label class="frow"><input type="checkbox" name="fair" value="${esc(a)}"${F.f.air.has(a) ? ' checked' : ''}><span>${esc(a)}</span><small>${low('air', f => carriers(f).includes(a))}</small></label>`).join('')}</div>
  ${hi > lo ? `<div class="fgrp"><h4>Max price <b id="fmaxv" style="float:right">${fmtPrice(cur, currency)}</b></h4><input type="range" id="fmax" min="${lo}" max="${hi}" step="${Math.max(1, Math.round((hi - lo) / 50))}" value="${cur}" aria-label="Maximum price"></div>` : ''}`;
}

function render() {
  const {flights, calendar, currency, insights} = F.data;
  const depart = $('#f-depart').value;
  // lowest-fare calendar for the month (Travelpayouts only)
  const days = Object.entries(calendar || {}).sort();
  const low = Math.min(...days.map(d => d[1]));
  $('#calwrap').hidden = !days.length;
  $('#cal').innerHTML = days.map(([d, p]) => `<button type="button" class="day${d === depart ? ' on' : ''}${p === low ? ' low' : ''}" data-d="${d}">
    <small>${longDate(d)}</small><b>${fmtPrice(p, currency)}</b>${p === low ? '<em>Lowest</em>' : ''}</button>`).join('');
  const on = $('#cal .on'); if (on) on.scrollIntoView({inline: 'center', block: 'nearest'});
  // Google's price insight (SerpApi only)
  const lvl = {low: 'low 📉', typical: 'typical', high: 'high 📈'}[insights?.level];
  $('#insight').hidden = !lvl;
  if (lvl) $('#insight').innerHTML = `<span>💡</span><span>Prices are <b>${lvl}</b> for this route right now${insights.low ? `. Usually ${fmtPrice(insights.low, currency)} – ${fmtPrice(insights.high, currency)}` : ''}.</span>`;
  visaHint();
  if (!flights.length) {
    $('#tabs').innerHTML = $('#fbody').innerHTML = $('#count').textContent = '';
    $('#list').innerHTML = `<div class="unavail"><h2 style="font-size:28px">No flights found for this day.</h2><p class="lead" style="margin:10px auto 0">${days.length ? 'Pick another day from the calendar above.' : 'Try another date or a nearby airport.'}</p></div>`;
    return;
  }
  $('#fbody').innerHTML = filtersHTML();
  const list = flights.filter(f => passes(f));
  const cheap = minBy(flights, f => f.price), fast = minBy(flights, f => f.minutes || 1e9), best = flights.find(f => f.best);
  if (F.sort === 'best' && !best) F.sort = 'price';
  const tab = (k, label, f, sub) => f ? `<button type="button" role="tab" class="tab" data-s="${k}" aria-selected="${F.sort === k}"><small>${label}</small><b>${fmtPrice(f.price, currency)}</b><small>${sub}</small></button>` : '';
  $('#tabs').innerHTML = tab('best', 'Best', best, best && `${fmtDur(best.minutes)} · ${stopsText(best.stops)}`) + tab('price', 'Cheapest', cheap, `${fmtDur(cheap.minutes)} · ${stopsText(cheap.stops)}`) + tab('fast', 'Fastest', fast, `${fmtDur(fast.minutes)} · ${stopsText(fast.stops)}`);
  const sorters = {best: (a, b) => (b.best || 0) - (a.best || 0) || a.price - b.price, price: (a, b) => a.price - b.price, fast: (a, b) => a.minutes - b.minutes || a.price - b.price};
  list.sort(sorters[F.sort]);
  $('#count').textContent = `${list.length} of ${flights.length} flights`;
  $('#list').innerHTML = list.map(f => card(f, flights.indexOf(f), {cheap: f === cheap, fast: f === fast, currency})).join('')
    || `<div class="unavail"><h2 style="font-size:24px">No flights match these filters.</h2><p class="row"><button class="btn ghost" type="button" onclick="document.getElementById('f-reset').click()">Clear filters</button></p></div>`;
}

function card(f, i, {cheap, fast, currency}) {
  const plus = f.arriveAt ? plusDays(f.departAt, f.arriveAt) : 0;
  const delayed = f.segments?.some(s => s.delayed), overnight = f.layovers?.some(l => l.overnight);
  const tags = [f.best && '<span class="pill gold">Best</span>', cheap && '<span class="pill ok">Cheapest</span>', fast && '<span class="pill">Fastest</span>',
    overnight && '<span class="pill warn">🌙 Overnight layover</span>', delayed && '<span class="pill warn">Often delayed 30+ min</span>',
    f.co2?.diff != null && f.co2.diff <= -10 && `<span class="pill ok">🌱 ${-f.co2.diff}% less CO₂</span>`].filter(Boolean).join('');
  return `<article class="fl">
    <div class="fl-row">
      <div class="fl-air"><img src="${logo(f)}" alt="" width="36" height="36" loading="lazy"><div><b>${esc(f.airlineName)}</b><small>${esc(f.flight)}</small></div></div>
      <div class="fl-t"><b>${localTime(f.departAt)}</b><small>${f.from}</small></div>
      <div class="fl-mid"><small>${fmtDur(f.minutes)}</small><i class="ln" data-stops="${Math.min(f.stops, 2)}"></i><small class="${f.stops ? '' : 'ns'}">${stopsText(f.stops)}${f.via ? ' · ' + esc(f.via) : ''}</small></div>
      <div class="fl-t">${f.arriveAt ? `<b>${localTime(f.arriveAt)}${plus ? `<sup>+${plus}</sup>` : ''}</b>` : '<b>—</b>'}<small>${f.to}</small></div>
      <div class="fl-price"><b>${fmtPrice(f.price, currency)}</b><small>per adult${f.returnAt || F.data.roundTrip ? ', return trip' : ''}</small><button class="btn" type="button" data-i="${i}">Select</button></div>
    </div>
    <div class="fl-foot"><div class="fl-tags">${tags}</div>${f.segments ? `<button type="button" class="fl-more" data-x="${i}" aria-expanded="false">Flight details</button>` : ''}</div>
    <div class="fl-det" hidden></div>
  </article>`;
}

// full itinerary: every leg, airport, aircraft, cabin, legroom, amenities, layovers, emissions
function details(f) {
  if (!f.segments) return `<p class="muted small">${legText(f)}</p>`;
  const rows = f.segments.map((s, i) => {
    const lay = f.layovers?.[i];
    return `<li class="tl-pt"><time>${localTime(s.dep)}</time><div><b>${esc(s.fromName)} (${s.from})</b><small>${longDate(s.dep)}</small></div></li>
      <li class="tl-leg"><div class="tl-air"><img src="${s.logo || logo(f)}" alt="" width="20" height="20" loading="lazy"><b>${esc(s.airline)}</b> · ${esc(s.flight)} · ${fmtDur(s.minutes)}</div>
        <div class="chips">${[s.plane, s.cls, s.legroom && 'Legroom ' + s.legroom].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join('')}${s.perks.map(x => `<span>${esc(x)}</span>`).join('')}</div>
        ${s.delayed ? '<p class="warnline">⚠️ Often delayed by more than 30 min</p>' : ''}${s.overnight ? '<p class="warnline">🌙 Overnight flight</p>' : ''}</li>
      <li class="tl-pt"><time>${localTime(s.arr)}</time><div><b>${esc(s.toName)} (${s.to})</b><small>${longDate(s.arr)}</small></div></li>
      ${lay ? `<li class="tl-lay">⏱ <b>${fmtDur(lay.minutes)} layover</b> · ${esc(lay.name)} (${lay.id})${lay.overnight ? ' · <span class="warnline" style="display:inline">🌙 Overnight</span>' : ''}</li>` : ''}`;
  }).join('');
  const notes = [...(f.notes || []), f.co2 && `Carbon emissions ${f.co2.kg} kg${f.co2.diff != null ? ` (${f.co2.diff > 0 ? '+' : ''}${f.co2.diff}% vs typical)` : ''}`].filter(Boolean);
  return `<ol class="tl">${rows}</ol>${notes.length ? `<p class="tl-notes">${notes.map(esc).join(' · ')}</p>` : ''}`;
}

const logo = f => f.logo || `https://pics.avs.io/80/80/${f.airline}.png`;
const legText = f => `${longDate(f.departAt)} · ${localTime(f.departAt)}${f.arriveAt ? ' → ' + localTime(f.arriveAt) + (plusDays(f.departAt, f.arriveAt) ? `<sup>+${plusDays(f.departAt, f.arriveAt)}</sup>` : '') : ''} · ${f.from} → ${f.to} · ${fmtDur(f.minutes)} · ${stopsText(f.stops)}${f.via ? ' via ' + esc(f.via) : ''}`;

// interactions
$('#cal').onclick = e => { const b = e.target.closest('[data-d]'); if (!b) return; $('#f-depart').value = b.dataset.d; search(); };
$('#tabs').onclick = e => { const b = e.target.closest('[data-s]'); if (!b) return; F.sort = b.dataset.s; render(); };
$('#fbody').addEventListener('change', e => {
  const t = e.target;
  if (t.name === 'fstops') F.f.stops = t.value;
  if (t.name === 'fair') t.checked ? F.f.air.add(t.value) : F.f.air.delete(t.value);
  if (t.id === 'fmax') F.f.max = +t.value;
  render();
});
$('#fbody').addEventListener('input', e => { if (e.target.id === 'fmax') $('#fmaxv').textContent = fmtPrice(+e.target.value, F.data.currency); });
$('#fbody').addEventListener('click', e => { const b = e.target.closest('.slot'); if (!b) return; const set = F.f[b.dataset.k], v = +b.dataset.v; set.has(v) ? set.delete(v) : set.add(v); render(); });
$('#f-reset').onclick = () => { resetFilters(); if (F.data) render(); };
$('#f-open').onclick = () => { $('#filters').classList.add('open'); document.body.style.overflow = 'hidden'; };
$('#f-apply').onclick = () => { $('#filters').classList.remove('open'); document.body.style.overflow = ''; };

// review step, then hand-off: Travelpayouts = one partner link; SerpApi = pick return (round trip) then pick a seller.
const head = f => `<div class="rv-route"><img src="${logo(f)}" alt="" width="44" height="44"><div><b>${esc(F.from.city)} → ${esc(F.to.city)}</b><p class="muted small">${esc(f.airlineName)} · ${esc(f.flight)} · ${fmtDur(f.minutes)} · ${stopsText(f.stops)}</p></div></div>
  <details class="rv-det"><summary>Flight details</summary>${details(f)}</details>`;
const visaBox = () => $('#visa-hint').innerHTML ? `<div class="protect">🛂<span>${$('#visa-hint').innerHTML}</span></div>` : '';
const api = (path, token) => fetch(`/api/${path}?${F.q}&token=${encodeURIComponent(token)}`).then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.error); return j; });
const loading = t => `<div class="progress" style="margin-top:14px"><i></i></div><p class="muted small center" style="margin-top:8px">${t}</p><div class="skel" style="height:56px;margin-top:10px"></div><div class="skel" style="height:56px;margin-top:8px"></div>`;

$('#list').addEventListener('click', e => {
  const x = e.target.closest('[data-x]');
  if (x) {
    const det = x.closest('.fl').querySelector('.fl-det'), open = det.hidden;
    if (open && !det.innerHTML) det.innerHTML = details(F.data.flights[x.dataset.x]);
    det.hidden = !open; x.setAttribute('aria-expanded', open);
    return;
  }
  const b = e.target.closest('button[data-i]'); if (!b) return;
  const f = F.pick = F.data.flights[b.dataset.i], c = F.data.currency;
  $('#rv-body').onclick = null;
  $('#rv-go').hidden = !f.url;
  if (f.url) {
    $('#rv-body').innerHTML = head(f) + `${f.returnAt ? `<div class="lines"><div><span>Return</span><span>${longDate(f.returnAt)}, ${localTime(f.returnAt)}</span></div></div>` : ''}
      <div class="total"><span>From, per adult</span><b>${fmtPrice(f.price, c)}</b></div>${visaBox()}`;
    $('#rv-go').href = f.url;
  } else if (F.data.roundTrip && f.departureToken) chooseReturn(f);
  else sellers(f, head(f));
  $('#review').showModal();
});

async function chooseReturn(out) {
  $('#rv-body').innerHTML = head(out) + loading('Finding return flights…');
  try {
    const {flights, currency} = await api('returns', out.departureToken);
    F.rets = flights.sort((a, b) => a.price - b.price);
    $('#rv-body').innerHTML = head(out) + `<h3 style="margin:16px 0 8px">Choose your return</h3><div class="rv-list">${F.rets.map((r, i) => `
      <button type="button" class="rv-opt" data-r="${i}"><span><b>${esc(r.airlineName)}</b><small>${legText(r)}</small></span><b>${fmtPrice(r.price, currency)}</b></button>`).join('') || '<p class="muted">No return flights found. Try another date.</p>'}</div>`;
    $('#rv-body').onclick = e => { const x = e.target.closest('[data-r]'); if (x) { const r = F.rets[x.dataset.r]; sellers(r, head(out) + `<h3 style="margin:14px 0 4px">Return</h3><p class="small">${esc(r.airlineName)} · ${legText(r)}</p><details class="rv-det"><summary>Return flight details</summary>${details(r)}</details>`); } };
  } catch (err) { failed(err); }
}

async function sellers(f, summary) {
  $('#rv-body').onclick = null;
  $('#rv-body').innerHTML = summary + loading('Comparing airlines and travel sites for this fare…');
  try {
    const {options, currency} = await api('book', f.bookingToken);
    F.opts = options;
    $('#rv-body').innerHTML = summary + `<h3 style="margin:16px 0 8px">Where to book</h3><div class="rv-list">${options.map((o, i) => `
      <div class="rv-opt"><span><b>${esc(o.seller)}</b> ${o.airline ? '<span class="pill ok">Airline</span>' : ''}${o.split ? '<span class="pill">Separate tickets</span>' : ''}<small>${esc([o.title, ...o.perks].filter(Boolean).join(' · '))}</small></span>
      <span class="rv-buy"><b>${fmtPrice(o.price, currency)}</b>${o.url ? `<button class="btn" type="button" data-o="${i}">Book</button>` : `<a class="btn ghost" href="tel:${esc(o.phone)}">Call</a>`}</span></div>`).join('') || '<p class="muted">No sellers available for this fare right now.</p>'}</div>${visaBox()}`;
    $('#rv-body').onclick = e => { const x = e.target.closest('[data-o]'); if (x) go(F.opts[x.dataset.o]); };
  } catch (err) { failed(err); }
}

// Google hands the traveller to the seller via a form POST, exactly like google.com/travel does.
function go(o) {
  if (!/^https:\/\/www\.google\.[a-z.]+\//.test(o.url)) return;
  const form = Object.assign(document.createElement('form'), {method: 'POST', action: o.url});
  for (const [k, v] of new URLSearchParams(o.post || '')) form.append(Object.assign(document.createElement('input'), {type: 'hidden', name: k, value: v}));
  document.body.append(form);
  form.submit();
}
const failed = err => { $('#rv-body').querySelectorAll('.skel,.progress').forEach(n => n.remove()); $('#rv-body').insertAdjacentHTML('beforeend', `<p class="small" style="color:#b42318;margin-top:12px">${esc(err.message || 'Something went wrong.')} <a class="more" href="https://wa.me/971509518129">Ask our travel desk</a></p>`); };
$('#rv-close').onclick = () => $('#review').close();

// cross-sell: destination needs a visa we sell
function visaHint() {
  const country = F.to?.country || '';
  const d = country && typeof DEST !== 'undefined' && DEST.find(o => o.n.startsWith(country) || country.startsWith(o.n.replace(/ \(.*/, '')));
  $('#visa-hint').innerHTML = d ? `Need a ${esc(d.n.replace(/ \(.*/, ''))} visa? <a class="more" href="visa/${d.s}.html">Get it online from $${d.$}</a>` : '';
  $('#visa-hint').hidden = !d;
}

// Groq smart search
$('#ai-form').onsubmit = async e => {
  e.preventDefault();
  const q = $('#ai-q').value.trim(); if (!q) return;
  const btn = $('#ai-form button'); btn.disabled = true; $('#ai-msg').textContent = 'Reading your trip…';
  try {
    const r = await fetch('/api/parse', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({q})});
    const j = await r.json();
    if (!r.ok) throw new Error(j.error);
    if (j.from) setFrom(j.from);
    if (j.to) setTo(j.to);
    const day = s => s && /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : s && /^\d{4}-\d{2}$/.test(s) ? (s + '-01' < today ? today : s + '-01') : '';
    if (day(j.depart)) $('#f-depart').value = day(j.depart);
    $('#f-return').value = day(j.return);
    $('#f-direct').checked = !!j.direct;
    $('#ai-msg').textContent = j.from && j.to ? '' : 'Got part of it. Please complete the form below.';
    if (j.from && j.to && day(j.depart)) search();
  } catch (err) { $('#ai-msg').textContent = err.message || 'Please use the form below.'; }
  btn.disabled = false;
};

// popular routes + restore from URL (back/forward, shared links)
$$('[data-route]').forEach(b => b.onclick = () => {
  const [fc, fn, tc, tn] = b.dataset.route.split('|');
  setFrom({code: fc, city: fn}); setTo({code: tc, city: tn, country: b.dataset.country});
  if (!$('#f-depart').value) { const d = new Date(); d.setDate(d.getDate() + 14); $('#f-depart').value = d.toISOString().slice(0, 10); }
  search();
});
function restore() {
  const p = new URLSearchParams(location.search);
  if (!p.get('from') || !p.get('to')) return;
  setFrom({code: p.get('from'), city: p.get('fromName') || p.get('from')});
  setTo({code: p.get('to'), city: p.get('toName') || p.get('to'), country: p.get('toCountry') || ''});
  $('#f-depart').value = p.get('depart') || '';
  $('#f-return').value = p.get('return') || '';
  $('#f-cur').value = p.get('currency') || 'inr';
  $('#f-direct').checked = p.get('direct') === 'true';
  search(false);
}
addEventListener('popstate', restore);
restore();
