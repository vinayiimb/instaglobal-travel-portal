// Serves ./site plus the flight API. Zero dependencies (Node 18+).
//   node server.mjs            -> http://localhost:8765
//   node server.mjs --selftest -> runs the checks at the bottom
// Keys live in .env (see .env.example): TRAVELPAYOUTS_TOKEN, TRAVELPAYOUTS_MARKER, GROQ_API_KEY.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {existsSync, readFileSync} from 'node:fs';
import {extname, join, normalize} from 'node:path';
import {gzipSync} from 'node:zlib';

const DIR = new URL('.', import.meta.url).pathname;
if (existsSync(join(DIR, '.env'))) {
  for (const line of readFileSync(join(DIR, '.env'), 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}
const {TRAVELPAYOUTS_TOKEN: TOKEN, TRAVELPAYOUTS_MARKER: MARKER = '', GROQ_API_KEY: GROQ, SERPAPI_KEY: SERP, PORT = 8765} = process.env;
const SITE = join(DIR, 'site');
const TP = 'https://api.travelpayouts.com';
const MARKETS = {inr: 'in', usd: 'us', aed: 'ae'};
// Free Groq models, tried in order; the next one is used when a model is rate-limited or retired.
const GROQ_MODELS = ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b', 'llama-3.1-8b-instant'];

// ponytail: in-memory cache, fine for one process; move to Redis/KV if you run several instances.
const cache = new Map();
async function cached(key, ttlMs, fn) {
  const hit = cache.get(key);
  if (hit && hit.until > Date.now()) return hit.value;
  const value = await fn();
  cache.set(key, {value, until: Date.now() + ttlMs});
  if (cache.size > 2000) cache.delete(cache.keys().next().value);
  return value;
}

const airlines = () => cached('airlines', 864e5, async () => {
  const list = await (await fetch(`${TP}/data/en/airlines.json`)).json();
  return Object.fromEntries(list.map(a => [a.code, a.name_translations?.en || a.name || a.code]));
});

const places = term => cached('p:' + term.toLowerCase(), 864e5, async () => {
  const u = new URL('https://autocomplete.travelpayouts.com/places2');
  u.search = new URLSearchParams({term, locale: 'en'}) + '&types[]=city&types[]=airport';
  const list = await (await fetch(u)).json();
  return list.slice(0, 8).map(p => ({code: p.code, type: p.type, name: p.name, city: p.city_name || p.name, country: p.country_name}));
});

export function bookingUrl(link, marker = MARKER) {
  const u = new URL(link, 'https://www.aviasales.com');
  if (marker) u.searchParams.set('marker', marker);
  return u.href;
}

export function mapFlight(f, names = {}, marker = MARKER) {
  return {
    price: f.price, airline: f.airline, airlineName: names[f.airline] || f.airline, flight: `${f.airline} ${f.flight_number}`,
    from: f.origin_airport || f.origin, to: f.destination_airport || f.destination,
    departAt: f.departure_at, returnAt: f.return_at || null,
    stops: f.transfers ?? 0, returnStops: f.return_transfers ?? null,
    minutes: f.duration_to || f.duration, returnMinutes: f.duration_back || null,
    url: bookingUrl(f.link, marker),
  };
}

async function tp(path, params) {
  const u = new URL(TP + path);
  u.search = new URLSearchParams(params);
  const r = await fetch(u, {headers: {'X-Access-Token': TOKEN}});
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.success === false) throw new Error(j.error || `Travelpayouts ${r.status}`);
  return j.data || [];
}

const IATA = /^[A-Z]{3}$/, DAY = /^\d{4}-\d{2}(-\d{2})?$/;

async function searchFlights(q) {
  const origin = (q.get('origin') || '').toUpperCase(), destination = (q.get('destination') || '').toUpperCase();
  const depart = q.get('depart') || '', ret = q.get('return') || '';
  const currency = MARKETS[q.get('currency')] ? q.get('currency') : 'inr';
  if (!IATA.test(origin) || !IATA.test(destination) || !DAY.test(depart) || (ret && !DAY.test(ret))) throw Object.assign(new Error('Pick a valid origin, destination and date.'), {status: 400});
  const base = {origin, destination, currency, market: MARKETS[currency], sorting: 'price', limit: 100, direct: q.get('direct') === 'true'};
  const exact = depart.length === 10;
  const key = JSON.stringify([base, depart, ret]);
  return cached(key, 10 * 60e3, async () => {
    const names = await airlines();
    // Ask for the whole month both ways: one_way=true gives the cheapest fare per day, one_way=false gives more
    // offers per day (per the docs). Merge, keep the right trip type, then narrow to the chosen day.
    const params = {...base, departure_at: depart.slice(0, 7)};
    if (ret) params.return_at = ret.slice(0, 7);
    const runs = await Promise.all(['true', 'false'].map(one_way => tp('/aviasales/v3/prices_for_dates', {...params, one_way})));
    const all = [...new Map(runs.flat().map(f => [f.link, f])).values()]
      .map(f => mapFlight(f, names)).filter(f => !ret === !f.returnAt);
    const days = {};
    for (const f of all) {
      const d = f.departAt.slice(0, 10);
      if (!days[d] || f.price < days[d]) days[d] = f.price;
    }
    let list = all;
    if (exact) list = list.filter(f => f.departAt.startsWith(depart) && (ret.length < 10 || f.returnAt.startsWith(ret)));
    return {currency, flights: list.sort((a, b) => a.price - b.price).slice(0, 50), calendar: days};
  });
}

// ---------- SerpApi (Google Flights). Used instead of Travelpayouts when SERPAPI_KEY is set.
// Free plan = 250 searches/month; SerpApi's own cached repeats are free. Each search, return-leg and booking lookup costs one.
const SERP_PER_IP_DAY = 15;
const spend = new Map();
function budget(ip) {
  const day = new Date().toISOString().slice(0, 10), k = ip + day, n = (spend.get(k) || 0) + 1;
  if (spend.size > 5000) spend.clear();
  spend.set(k, n);
  if (n > SERP_PER_IP_DAY) throw Object.assign(new Error('Daily search limit reached. Our travel desk can search for you on WhatsApp.'), {status: 429});
}

async function serp(params, ip) {
  const key = 's:' + JSON.stringify(params);
  return cached(key, 60 * 60e3, async () => {
    budget(ip);
    const u = new URL('https://serpapi.com/search.json');
    u.search = new URLSearchParams({engine: 'google_flights', hl: 'en', ...params, api_key: SERP});
    const j = await (await fetch(u)).json().catch(() => ({error: 'Bad response'}));
    if (j.error && !/hasn't returned any results/i.test(j.error)) throw new Error('SerpApi: ' + j.error);
    return j;
  });
}

const serpTime = t => t ? t.replace(' ', 'T') : null; // "2026-11-14 06:10" -> local ISO-ish, no offset

export function mapSerp(o, cur) {
  const seg = o.flights || [], first = seg[0] || {}, last = seg[seg.length - 1] || {};
  const names = [...new Set(seg.map(x => x.airline).filter(Boolean))];
  return {
    price: o.price, airline: (first.flight_number || '').split(' ')[0], airlineName: names.join(' + '), logo: o.airline_logo || first.airline_logo,
    flight: seg.map(x => x.flight_number).join(', '), from: first.departure_airport?.id, to: last.arrival_airport?.id,
    departAt: serpTime(first.departure_airport?.time), arriveAt: serpTime(last.arrival_airport?.time), returnAt: null,
    stops: Math.max(0, seg.length - 1), via: (o.layovers || []).map(l => l.id).join(', '), minutes: o.total_duration,
    bookingToken: o.booking_token || null, departureToken: o.departure_token || null, currency: cur,
    segments: seg.map(x => ({
      from: x.departure_airport?.id, fromName: x.departure_airport?.name, dep: serpTime(x.departure_airport?.time),
      to: x.arrival_airport?.id, toName: x.arrival_airport?.name, arr: serpTime(x.arrival_airport?.time),
      minutes: x.duration, airline: x.airline, logo: x.airline_logo, flight: x.flight_number, plane: x.airplane || '',
      cls: x.travel_class || '', legroom: x.legroom || '', delayed: !!x.often_delayed_by_over_30_min, overnight: !!x.overnight,
      perks: (x.extensions || []).filter(e => !/^carbon emissions|legroom/i.test(e)),
    })),
    layovers: (o.layovers || []).map(l => ({minutes: l.duration, name: l.name, id: l.id, overnight: !!l.overnight})),
    co2: o.carbon_emissions?.this_flight ? {kg: Math.round(o.carbon_emissions.this_flight / 1000), diff: o.carbon_emissions.difference_percent ?? null} : null,
    notes: o.extensions || [],
  };
}

function serpBase(q) {
  const origin = (q.get('origin') || '').toUpperCase(), destination = (q.get('destination') || '').toUpperCase();
  const depart = q.get('depart') || '', ret = q.get('return') || '';
  const currency = MARKETS[q.get('currency')] ? q.get('currency') : 'inr';
  const ok = /^\d{4}-\d{2}-\d{2}$/;
  if (!IATA.test(origin) || !IATA.test(destination) || !ok.test(depart) || (ret && !ok.test(ret))) throw Object.assign(new Error('Pick a valid origin, destination and date.'), {status: 400});
  const p = {departure_id: origin, arrival_id: destination, outbound_date: depart, type: ret ? '1' : '2', currency: currency.toUpperCase(), gl: MARKETS[currency]};
  if (ret) p.return_date = ret;
  if (q.get('direct') === 'true') p.stops = '1';
  return {p, currency};
}

const insights = pi => pi && {level: pi.price_level || null, low: pi.typical_price_range?.[0] ?? null, high: pi.typical_price_range?.[1] ?? null};

async function serpSearch(q, ip) {
  const {p, currency} = serpBase(q);
  const j = await serp(p, ip);
  const flights = [...(j.best_flights || []).map(o => ({...mapSerp(o, currency), best: true})), ...(j.other_flights || []).map(o => mapSerp(o, currency))].filter(f => f.price);
  return {provider: 'serpapi', currency, roundTrip: p.type === '1', flights: flights.sort((a, b) => a.price - b.price).slice(0, 50), calendar: {}, insights: insights(j.price_insights)};
}

async function serpReturns(q, ip) {
  const {p, currency} = serpBase(q);
  const token = q.get('token') || '';
  if (!token) throw Object.assign(new Error('Missing flight.'), {status: 400});
  const j = await serp({...p, departure_token: token}, ip);
  return {currency, flights: [...(j.best_flights || []).map(o => ({...mapSerp(o, currency), best: true})), ...(j.other_flights || []).map(o => mapSerp(o, currency))].filter(f => f.price)};
}

export function mapBooking(b) {
  const o = b.together || b;
  const req = o.booking_request;
  return {seller: o.book_with, airline: !!o.airline, price: o.price ?? null, title: o.option_title || '', perks: (o.extensions || []).slice(0, 3),
    url: req?.url || null, post: req?.post_data || null, phone: o.booking_phone || null, split: !!b.separate_tickets};
}

async function serpBook(q, ip) {
  const {p, currency} = serpBase(q);
  const token = q.get('token') || '';
  if (!token) throw Object.assign(new Error('Missing flight.'), {status: 400});
  const j = await serp({...p, booking_token: token}, ip);
  const options = (j.booking_options || []).map(mapBooking).filter(o => o.price && (o.url || o.phone));
  return {currency, options: options.sort((a, b) => b.airline - a.airline || a.price - b.price)};
}

// Groq turns "cheapest Delhi to Dubai next Friday, non-stop" into a structured search.
async function parseTrip(text) {
  if (!GROQ) throw Object.assign(new Error('Smart search is not configured yet (GROQ_API_KEY).'), {status: 503});
  const today = new Date().toISOString().slice(0, 10);
  const system = `Today is ${today}. Extract a flight search from the user's message. Reply with JSON only:
{"from":"city or airport name","to":"city or airport name","depart":"YYYY-MM-DD or YYYY-MM","return":"YYYY-MM-DD, YYYY-MM or null","direct":true|false,"adults":1}
Resolve relative dates ("next Friday", "in December") from today. Use null for anything not mentioned. Never invent prices.`;
  let last;
  for (const model of GROQ_MODELS) {
    const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST', headers: {Authorization: `Bearer ${GROQ}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({model, temperature: 0, response_format: {type: 'json_object'}, messages: [{role: 'system', content: system}, {role: 'user', content: text.slice(0, 500)}]}),
    });
    if (r.status === 429 || r.status === 404 || r.status === 400 || r.status >= 500) { last = `${model}: ${r.status}`; continue; }
    if (!r.ok) throw new Error(`Groq ${r.status}`);
    const out = JSON.parse((await r.json()).choices[0].message.content);
    const [from, to] = await Promise.all([out.from && places(out.from), out.to && places(out.to)]);
    return {...out, from: from?.[0] || null, to: to?.[0] || null};
  }
  throw Object.assign(new Error('Smart search is busy, please use the form. (' + last + ')'), {status: 503});
}

const TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon'};
// Assets are requested as ?v=<build> by build.py, so they can be cached for a year; HTML and API answers are not cached.
const send = (res, status, body, type = 'application/json', req, cache = 'no-store') => {
  let buf = Buffer.from(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body));
  const headers = {'Content-Type': type, 'Cache-Control': cache, Vary: 'Accept-Encoding'};
  if (buf.length > 1024 && /text|javascript|json|svg/.test(type) && /gzip/.test(req?.headers['accept-encoding'] || '')) {
    buf = gzipSync(buf); headers['Content-Encoding'] = 'gzip';
  }
  res.writeHead(status, headers);
  res.end(buf);
};

async function handle(req, res) {
  const url = new URL(req.url, 'http://x');
  try {
    if (url.pathname === '/api/places') return send(res, 200, await places((url.searchParams.get('term') || '').slice(0, 60)), undefined, req, 'public, max-age=86400');
    const ip = req.headers['x-forwarded-for']?.split(',')[0].trim() || req.socket.remoteAddress;
    if (url.pathname === '/api/flights') {
      if (SERP) return send(res, 200, await serpSearch(url.searchParams, ip), undefined, req);
      if (!TOKEN) return send(res, 503, {error: 'Flight prices are not configured yet (SERPAPI_KEY or TRAVELPAYOUTS_TOKEN).'});
      return send(res, 200, {provider: 'travelpayouts', ...await searchFlights(url.searchParams)}, undefined, req);
    }
    if (SERP && url.pathname === '/api/returns') return send(res, 200, await serpReturns(url.searchParams, ip), undefined, req);
    if (SERP && url.pathname === '/api/book') return send(res, 200, await serpBook(url.searchParams, ip), undefined, req);
    if (url.pathname === '/api/parse' && req.method === 'POST') {
      let body = '';
      for await (const c of req) { body += c; if (body.length > 2000) break; }
      return send(res, 200, await parseTrip(String(JSON.parse(body || '{}').q || '')));
    }
    let file = normalize(join(SITE, decodeURIComponent(url.pathname)));
    if (!file.startsWith(SITE)) return send(res, 403, 'Forbidden', 'text/plain');
    if (file.endsWith('/')) file += 'index.html';
    return send(res, 200, await readFile(file), TYPES[extname(file)] || 'application/octet-stream', req, url.searchParams.has('v') ? 'public, max-age=31536000, immutable' : 'no-cache');
  } catch (e) {
    if (e.code === 'ENOENT' || e.code === 'EISDIR') return send(res, 404, 'Not found', 'text/plain');
    console.error(e.message);
    send(res, e.status || 502, {error: e.status ? e.message : 'Flight search is temporarily unavailable. Please try again.'});
  }
}

if (process.argv.includes('--selftest')) {
  const assert = (await import('node:assert')).default;
  // Sample from the Travelpayouts docs.
  const f = mapFlight({origin: 'MAD', destination: 'BCN', origin_airport: 'MAD', destination_airport: 'BCN', price: 5929, airline: 'IB', flight_number: '3002',
    departure_at: '2023-07-28T07:00:00+02:00', return_at: '2023-08-26T14:30:00+02:00', transfers: 0, return_transfers: 0, duration: 165, duration_to: 80, duration_back: 85,
    link: '/search/MAD2807BCN26081?t=IB169&search_date=11052023'}, {IB: 'Iberia'}, 'TESTMARKER');
  assert.equal(f.airlineName, 'Iberia');
  assert.equal(f.minutes, 80);
  assert.equal(f.url, 'https://www.aviasales.com/search/MAD2807BCN26081?t=IB169&search_date=11052023&marker=TESTMARKER');
  assert.equal(bookingUrl('/search/X?a=1', ''), 'https://www.aviasales.com/search/X?a=1');
  // Shapes from the SerpApi Google Flights docs.
  const s = mapSerp({flights: [
    {departure_airport: {id: 'DEL', time: '2026-11-14 06:10'}, arrival_airport: {id: 'BOM', time: '2026-11-14 08:20'}, airline: 'Air India', flight_number: 'AI 887', airline_logo: 'L'},
    {departure_airport: {id: 'BOM', time: '2026-11-14 10:00'}, arrival_airport: {id: 'DXB', time: '2026-11-14 11:45'}, airline: 'Emirates', flight_number: 'EK 501'}],
    layovers: [{id: 'BOM'}], total_duration: 365, price: 14250, booking_token: 'BT'}, 'inr');
  assert.deepEqual([s.from, s.to, s.stops, s.via, s.airlineName, s.departAt, s.arriveAt, s.bookingToken], ['DEL', 'DXB', 1, 'BOM', 'Air India + Emirates', '2026-11-14T06:10', '2026-11-14T11:45', 'BT']);
  const b = mapBooking({together: {book_with: 'IndiGo', airline: true, price: 9870, booking_request: {url: 'https://www.google.com/travel/clk/f', post_data: 'u=abc'}}});
  assert.deepEqual([b.seller, b.airline, b.price, b.url, b.post], ['IndiGo', true, 9870, 'https://www.google.com/travel/clk/f', 'u=abc']);
  assert.equal(mapBooking({together: {book_with: 'X', price: 1, booking_phone: '+1'}}).phone, '+1');
  // Real Google Flights item (DEL->DXB) captured 2026-10-10, trimmed.
  const real = mapSerp({flights: [{departure_airport: {name: 'Indira Gandhi International Airport', id: 'DEL', time: '2026-11-04 10:55'},
    arrival_airport: {name: 'Dubai International Airport', id: 'DXB', time: '2026-11-04 13:35'}, duration: 250, airplane: 'Boeing 737', airline: 'flydubai',
    airline_logo: 'L', travel_class: 'Economy', flight_number: 'FZ 442', legroom: '30 in',
    extensions: ['Average legroom (30 in)', 'In-seat USB outlet', 'On-demand video', 'Carbon emissions estimate: 207 kg'], often_delayed_by_over_30_min: true}],
    total_duration: 250, carbon_emissions: {this_flight: 207000, typical_for_this_route: 228000, difference_percent: -9}, price: 18815}, 'inr');
  assert.deepEqual(real.segments[0].perks, ['In-seat USB outlet', 'On-demand video']);
  assert.deepEqual([real.segments[0].plane, real.segments[0].delayed, real.segments[0].fromName, real.co2.kg, real.co2.diff], ['Boeing 737', true, 'Indira Gandhi International Airport', 207, -9]);
  console.log('selftest ok');
} else {
  http.createServer(handle).listen(PORT, () => console.log(`http://localhost:${PORT}  prices:${SERP ? 'serpapi' : TOKEN ? 'travelpayouts' : 'OFF'}  groq:${GROQ ? 'on' : 'OFF'}`));
}
