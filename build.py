"""Builds the static redesign into ./site from the data scraped off instaglobaltravel.com.

    python3 build.py && python3 -m http.server -d site 8765
"""
import html, json, math, re, shutil
from pathlib import Path

ROOT = Path(__file__).parent
V = hex(int(__import__('time').time()))[2:]  # cache-buster: browsers keep assets until the next build
OUT = ROOT / 'site'
LIVE = 'https://www.instaglobaltravel.com'
WA = 'https://wa.me/971509518129?text=Hi%2C%20I%E2%80%99d%20like%20help%20with%20a%20Visa%20application.'
H = html.escape

DEST = json.load(open(ROOT / 'data/destinations.json'))
DET = json.load(open(ROOT / 'data/details.json'))
BLOG = json.load(open(ROOT / 'data/blog.json'))
BYSLUG = {o['s']: o for o in DEST}
POPULAR = sorted([o for o in DEST if o['p']], key=lambda o: o['$'])
SITE_FAQ_WORDS = re.compile(r'reward|points|affiliate', re.I)

# Verified figures (reviews page) - keep in one place so the site never contradicts itself.
RATING, REVIEWS = '4.7', 59


def money(n):
    return f'${n:,.2f}'.replace('.00', '')


def days_from(text):
    """'48-72 Working Hours' -> 3, '7 to 10 Working Days' -> 10, 'Express 4 Hours' -> 0 (same day)."""
    nums = re.findall(r'\d+', text or '')
    if not nums:
        return None
    n = int(nums[-1])
    if 'hour' in text.lower():
        return 0 if n <= 8 else math.ceil(n / 24)
    return n


def dest_days(o):
    return math.ceil(o['h'] / 24) if o.get('h') else None


def paras(raw):
    """CMS html -> list of plain paragraphs (drops markup, keeps text)."""
    t = re.sub(r'<br\s*/?>|</p>|</li>|<p>', '\n', raw or '', flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    return [l.strip() for l in t.split('\n') if l.strip()]


def short(name):
    return name.replace(' (UAE)', '').replace(' (UK)', '').replace(' (USA)', '').replace(' of America', '')


# ---------------------------------------------------------------- layout

def nav(r, active):
    items = [('Visas', f'{r}destinations.html'), ('Flights', f'{r}flights.html'), ('Passport', f'{r}passport.html'), ('Attestation', f'{r}attestation.html'),
             ('Appointments', f'{r}appointments.html'), ('Track', f'{LIVE}/track'), ('Help', f'{r}help-center.html')]
    links = ''.join(f'<a href="{h}"{" aria-current=page" if t == active else ""}>{t}</a>' for t, h in items)
    return f'''<header class="nav"><div class="wrap">
  <a class="logo" href="{r}index.html"><i>IGT</i>Insta Global Travel</a>
  <nav class="links" aria-label="Main">{links}</nav>
  <a class="signin" href="{LIVE}/account">Sign in</a>
  <a class="btn" href="{r}destinations.html">Apply now</a>
  <details class="menu"><summary aria-label="Menu">☰</summary><nav>{links}<a href="{LIVE}/account">Sign in</a><a class="btn" href="{r}destinations.html">Apply now</a></nav></details>
</div></header>'''


def footer(r):
    col = lambda t, ls: f'<div><h4>{t}</h4>' + ''.join(f'<a href="{h}">{n}</a>' for n, h in ls) + '</div>'
    return f'''<footer><div class="wrap">
  <div class="fcols">
    <div>
      <a class="logo" href="{r}index.html" style="color:var(--ink)"><i>IGT</i>Insta Global Travel</a>
      <p style="margin:12px 0">Fast, transparent visa applications. Apply online in minutes with full clarity on price and documents.</p>
      <a href="mailto:contact@instaglobaltravel.com">contact@instaglobaltravel.com</a>
      <a href="tel:+971509518129">+971 50 951 8129</a>
      <div class="apps">
        <a href="https://apps.apple.com/us/app/instaglobaltravel-apply-visa/id6474402870">Download on the<b>App Store</b></a>
        <a href="https://play.google.com/store/apps/details?id=com.insta_global_app">Get it on<b>Google Play</b></a>
      </div>
    </div>
    {col('Company', [('About Us', f'{r}about.html'), ('Why Choose Us', f'{r}why-us.html'), ('Reviews', f'{r}reviews.html'), ('Blog', f'{r}blog.html'), ('Contact Us', f'{r}contact.html')])}
    {col('Services', [('Visa Destinations', f'{r}destinations.html'), ('Flights', f'{r}flights.html'), ('Passport Service', f'{r}passport.html'), ('Attestation Service', f'{r}attestation.html'), ('Appointment Booking', f'{r}appointments.html'), ('Track Application', f'{LIVE}/track'), ('Rewards Program', f'{r}rewards.html')])}
    {col('Partners', [('Affiliate Program', f'{LIVE}/affiliate'), ('Travel Agent Partners', f'{r}partners.html'), ('My Account', f'{LIVE}/account')])}
    {col('Help', [('Help Center', f'{r}help-center.html'), ('FAQ', f'{r}faq.html'), ('Terms of Use', f'{r}terms.html'), ('Privacy Policy', f'{r}privacy.html'), ('Affiliate Terms', f'{r}affiliate-terms.html')])}
  </div>
  <div class="badges">
    <img src="https://media.bmbota.com/public/images/iata-logo.webp" alt="IATA" loading="lazy">
    <img src="https://media.bmbota.com/public/images/pcidss-logo.webp" alt="PCI DSS" loading="lazy">
    <img src="https://media.bmbota.com/public/images/qfs-logo.webp" alt="QFS" loading="lazy">
    <img src="https://media.bmbota.com/public/images/hawkeye-logo.webp" alt="Hawkeye" loading="lazy">
  </div>
  <div class="flegal">
    <p>Insta Global Travel is a brand of Insta Tourism LLC, a UAE-licensed travel &amp; documentation company and an authorized UAE visa sponsor. We accept and process UAE visa applications directly through Dubai's GDRFA / Smart Channel systems. As a licensed agency we facilitate and submit applications on your behalf. We are not a government body or issuing authority, and every visa is granted solely at the discretion of the relevant authority.</p>
    <p>Registered with the Dubai Department of Economy and Tourism (DET) since 2022, licensed for Travel Agency and Inbound &amp; Outbound Tour Operator activities. Office: 201, M Square Commercial Building, near Double Tree Hotel, Bur Dubai, Dubai, UAE. Accepted: Visa · Mastercard · Amex · UPI.</p>
    <p>© 2026 Insta Global Travel. All rights reserved.</p>
  </div>
</div></footer>
<a class="wafab" href="{WA}" aria-label="Chat on WhatsApp"><svg width="28" height="28" viewBox="0 0 24 24" fill="#fff" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.5-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.8s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.4.6-.4.4c-.1.1-.3.3-.1.6.2.3.7 1.2 1.6 2 1.1 1 2 1.3 2.3 1.4.3.1.4.1.6-.1l.8-1c.2-.3.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.6-.1 1.1z"/></svg></a>'''


def page(path, title, desc, body, active='', dest=False, jsonld=None, body_class='', script=''):
    r = '../' * path.count('/')
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ''
    data = f'<script src="{r}assets/data.js?v={V}"></script>' if dest else ''
    doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{H(title)}</title>
<meta name="description" content="{H(desc)}">
<meta property="og:title" content="{H(title)}"><meta property="og:description" content="{H(desc)}">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="{r}assets/style.css?v={V}"><link rel="preconnect" href="https://www.gstatic.com"><link rel="preconnect" href="https://media.bmbota.com">{ld}
</head>
<body data-root="{r}"{f' class="{body_class}"' if body_class else ''}>
{nav(r, active)}
<main>
{body}
</main>
{footer(r)}
{data}<script src="{r}assets/app.js?v={V}"></script>{f'<script src="{r}assets/{script}?v={V}"></script>' if script else ''}
</body>
</html>
'''
    f = OUT / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(doc)


# ---------------------------------------------------------------- shared blocks

def search_form(placeholder='Where are you going?'):
    return f'''<form class="search" data-search role="search">
  <input type="text" placeholder="{placeholder}" aria-label="{placeholder}" role="combobox" aria-expanded="false" aria-controls="sugg" aria-autocomplete="list" autocomplete="off">
  <ul class="sugg" id="sugg" role="listbox" hidden></ul>
  <button class="btn" type="submit">→ <span>Find my visa</span></button>
</form>'''


def tiles(r, items):
    return ''.join(f'''<a class="tile" href="{r}visa/{o['s']}.html">
  <img src="{o['img']}" alt="" loading="lazy">
  <div class="top">{f'⚡ Visa by <span data-days="{dest_days(o)}"></span>' if o.get('h') else ''}</div>
  <div><h3>{H(short(o['n']))}</h3><p>{'E-Visa' if o['ft'] == 'evisa' else 'Visa'} · {o['st']}-day stay</p><p class="price">from {money(o['$'])}</p></div>
</a>''' for o in items)


def grid_block(limit=None, heading=True):
    return f'''{'<div class="head"><div><h2>Every destination.<br>One honest price.</h2><p class="lead">' + str(len(DEST)) + ' countries. Government and service fees shown before you pay.</p></div></div>' if heading else ''}
<div class="bar">
  <input class="find" id="find" type="search" placeholder="Search a country" aria-label="Search a country">
  <select id="sort" aria-label="Sort"><option value="pop">Popular first</option><option value="price">Lowest price</option><option value="fast">Fastest</option><option value="az">A – Z</option></select>
</div>
<div class="regions" id="regions" role="group" aria-label="Filter by region"></div>
<div class="grid" id="grid"{f' data-limit="{limit}"' if limit else ''}></div>
<div class="center mt"><button class="btn ghost" id="more" type="button" hidden></button></div>'''


def faq_block(qas):
    return '<div class="faq">' + ''.join(f'<details><summary>{H(q)}</summary><p>{H(a)}</p></details>' for q, a in qas) + '</div>'


def faq_ld(qas):
    return {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in qas]}


def posts(r, items):
    return ''.join(f'''<a class="post" href="{LIVE}/blog/{p['slug']}"><div class="ph"><img loading="lazy" src="{p['coverImageUrl']}" alt=""></div>
<small>{H(p['category'] or 'Guide')}</small><h3>{H(p['title'])}</h3>{f"<p>{H(p['excerpt'][:140])}…</p>" if p.get('excerpt') else ''}</a>''' for p in items)


def cta(r, title='Ready to travel?', text='Find your visa and apply in minutes, with clear pricing and human support at every step.'):
    return f'''<section class="cta"><div class="wrap">
  <h2>{title}</h2><p class="lead">{text}</p>
  <div class="row"><a class="btn lg" href="{r}destinations.html">Find my visa</a><a class="btn lg ghost" href="{WA}">Chat on WhatsApp</a></div>
  <div class="meta"><span>★ {RATING} from {REVIEWS} verified reviews</span><span>✓ 50,000+ visas processed</span><span>⚡ 98.7% on-time</span></div>
</div></section>'''


GUARANTEE = '''<div class="guarantee">
  <div><h2>Know your visa date before you pay.</h2>
  <p>Every application shows a guaranteed delivery date up front, so you can book flights and plan with confidence.</p></div>
  <ul>
    <li>Guaranteed delivery date on every visa</li>
    <li>Expert document check before submission</li>
    <li>Government and service fees shown separately</li>
    <li>Service Protect: if we cause a delay, your service fee is refunded</li>
  </ul>
</div>'''

STEPS3 = '''<div class="cols3">
  <div class="box"><div class="num">1</div><h3>Check &amp; pick</h3><p>Tell us your destination and passport. We show only the visas you're eligible for, with a clear price and delivery date.</p></div>
  <div class="box"><div class="num">2</div><h3>Apply online</h3><p>One simple form. Add travellers and upload documents securely, from anywhere. No embassy queues.</p></div>
  <div class="box"><div class="num">3</div><h3>Get your visa</h3><p>Our experts check and submit. Track every step, and we email your approved visa.</p></div>
</div>'''

REVIEW_ITEMS = [
    ('Fatoumata Diallo', 'Guinea', '14-day UAE eVisa', 'Excellent service from start to finish. The eVisa application was simple, fast and professional. I received my 14-day UAE eVisa successfully. Thank you for your assistance and support. Highly recommended!'),
    ('Heyru Usman Mussa', 'Ethiopia', '30-day eVisa', "It's amazing application, thanks for our service."),
    ('Yesuf', 'Ethiopia', '30-day eVisa', 'Good service 👍 👌 👏 🙌'),
]
BARS = [(5, 44), (4, 1), (3, 1), (2, 0), (1, 4)]


def reviews_block(r, full=False):
    tot = sum(c for _, c in BARS)
    bars = ''.join(f'<div><span>{s}★</span><i><b style="width:{c / tot * 100:.0f}%"></b></i><span>{c}</span></div>' for s, c in BARS)
    cards = ''.join(f'''<figure class="review"><div class="stars" aria-label="5 out of 5">★★★★★</div><q>{H(t)}</q>
<figcaption class="who"><span class="av">{n[0]}</span><span><b>{H(n)}</b><br><span class="muted">{c} · {v} · ✓ Verified</span></span></figcaption></figure>''' for n, c, v, t in REVIEW_ITEMS)
    return f'''<div class="rating"><div><div class="score">{RATING}</div><div class="stars">★★★★★</div><p class="muted small">Based on {REVIEWS} verified reviews</p></div><div class="bars">{bars}</div></div>
<div class="cols3 mt">{cards}</div>
{'' if full else f'<p class="mt"><a class="more" href="{r}reviews.html">Read all reviews</a></p>'}'''


# ---------------------------------------------------------------- pages

def home():
    r = ''
    general = [
        ('Are you a government agency?', 'No. Insta Global Travel is a brand of Insta Tourism LLC, a UAE-licensed travel & documentation company and authorized UAE visa sponsor. We facilitate and submit applications on your behalf; every visa is granted solely at the discretion of the relevant authority.'),
        ('When will I get my visa?', 'Every application shows a guaranteed delivery date up front, before you pay. Need it sooner? Express options are shown on each visa page.'),
        ('What does the price include?', 'You see the full price, with the government fee and our service fee shown separately, before you pay. No hidden charges, no surprises at checkout.'),
        ('What if my visa is delayed?', 'Every application includes Service Protect: handled by experts and tracked end to end. If we cause a delay, your service fee is refunded.'),
        ('Can I apply for my family together?', 'Yes. Add every traveller to one application. With 3 or more applicants you automatically get 10% off the service fee.'),
        ('How do I pay?', 'Pay safely with trusted gateways in your own currency. We accept Visa, Mastercard, Amex and UPI.'),
    ]
    body = f'''<section class="hero"><div class="wrap">
  <span class="eyebrow"><b>★ {RATING}</b> from {REVIEWS} verified reviews · Online since 2016</span>
  <h1>Your visa,<br><span class="grad">made simple.</span></h1>
  <p class="lead">Apply online in minutes. See the exact price, documents and your guaranteed visa date before you pay.</p>
  {search_form()}
  <div class="trustrow"><span>Guaranteed delivery date</span><span>No hidden fees</span><span>Expert document check</span><span>24/7 human support</span></div>
  <div class="quick">{''.join(f'<a class="chip" href="visa/{o["s"]}.html">{o["f"]} {H(short(o["n"]))}</a>' for o in POPULAR)}</div>
  <div class="heroimg"><img src="https://media.bmbota.com/uploads/filemanager/catalog/countries_image/united-arab-emirates-uae.jpg" alt="Museum of the Future, Dubai"></div>
  <div class="stats">
    <div><b>50,000+</b><span>Visas processed</span></div>
    <div><b>98.7%</b><span>On-time delivery</span></div>
    <div><b>{len(DEST)}</b><span>Destinations</span></div>
    <div><b>24/7</b><span>Human support</span></div>
  </div>
</div></section>

<section class="alt"><div class="wrap head"><div><h2>Popular right now.</h2><p class="lead">The visas travellers apply for most, with delivery dates updated live.</p></div><a class="more" href="destinations.html">All {len(DEST)} destinations</a></div>
<div class="rail">{tiles(r, POPULAR)}</div></section>

<section><div class="wrap">{GUARANTEE}</div></section>

<section class="alt" id="destinations"><div class="wrap">{grid_block(limit=12)}</div></section>

<section><div class="wrap"><div class="head"><div><h2>Three steps. No queues.</h2><p class="lead">No embassy visits, no printouts, no paperwork stress.</p></div></div>{STEPS3}</div></section>

<section class="alt"><div class="wrap">
  <div class="head"><div><h2>Save on every application.</h2><p class="lead">Live discounts, applied automatically. No codes to hunt for.</p></div></div>
  <div class="cols4">
    <div class="box offer"><div class="big">10%</div><h3>Family &amp; groups</h3><p>Off the service fee when 3 or more travellers apply together.</p><span class="note" style="margin-top:auto;padding-top:16px">✓ Auto-applied</span></div>
    <div class="box offer"><div class="big">10%</div><h3>First visa</h3><p>Off the service fee on your first application.</p><a class="more" href="{LIVE}/account">Sign in to unlock</a></div>
    <div class="box offer"><div class="big">8%</div><h3>Members</h3><p>Up to 8% off every order as you climb reward tiers.</p><a class="more" href="rewards.html">See rewards</a></div>
    <div class="box offer"><div class="big">100</div><h3>Welcome points</h3><p>Free on sign-up. Earn more on every booking and review.</p><a class="more" href="{LIVE}/account">Create free account</a></div>
  </div>
</div></section>

<section><div class="wrap"><div class="head"><div><h2>Loved by travellers.</h2></div></div>{reviews_block(r)}</div></section>

<section class="alt"><div class="wrap">
  <div class="head"><div><h2>More than visas.</h2><p class="lead">Flights and every travel document, with one trusted partner.</p></div></div>
  <div class="cols4">
    <div class="box"><div class="ic">✈️</div><h3>Flights</h3><p>Compare fares across airlines and travel sites, then book with the seller you choose.</p><a class="more" href="flights.html">Find cheap flights</a></div>
    <div class="box"><div class="ic">🛂</div><h3>Passport</h3><p>Renewals, new passports and police clearance. Doorstep pickup and live tracking.</p><a class="more" href="passport.html">Passport service</a></div>
    <div class="box"><div class="ic">📜</div><h3>Attestation</h3><p>Degree, birth, marriage and company documents through the full official chain.</p><a class="more" href="attestation.html">Attestation service</a></div>
    <div class="box"><div class="ic">📅</div><h3>Appointments</h3><p>We track scarce biometrics and interview slots and guide you through booking.</p><a class="more" href="appointments.html">Book an appointment</a></div>
  </div>
</div></section>

<section><div class="wrap"><div class="head"><div><h2>Travel guides.</h2></div><a class="more" href="blog.html">All {len(BLOG)} articles</a></div><div class="cols3">{posts(r, BLOG[:3])}</div></div></section>

<section class="alt"><div class="wrap narrow"><div class="head"><div><h2>Questions? Answered.</h2></div></div>{faq_block(general)}<p class="mt"><a class="more" href="faq.html">All FAQs</a></p></div></section>
{cta(r)}'''
    page('index.html', 'Insta Global Travel: Apply for your visa online, made simple',
         f'Apply online for e-visas to {len(DEST)} countries with transparent pricing, a guaranteed visa date and expert document checks. Rated {RATING}★ by travellers.',
         body, dest=True, jsonld=faq_ld(general))


def destinations():
    body = f'''<div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Home</a><span aria-hidden="true">/</span><span>Destinations</span></nav></div>
<section class="phero" style="padding-bottom:40px"><div class="wrap">
  <h1>Where to next?</h1>
  <p class="lead">E-visas for {len(DEST)} countries. Every price includes government and service fees, and every visa comes with a guaranteed delivery date.</p>
</div></section>
<section class="alt" style="padding-top:48px"><div class="wrap">{grid_block(heading=False)}</div></section>
{cta('')}'''
    page('destinations.html', f'Visa destinations: {len(DEST)} countries online | Insta Global Travel',
         f'Browse e-visas for {len(DEST)} countries. Compare prices, processing times and stay length, then apply online in minutes.', body, 'Visas', dest=True)


REJECTIONS = [('🛂', 'Expired or invalid passport', 'Passport expired or expiring within 6 months of travel.'),
              ('📄', 'Incomplete documents', 'Missing or unclear documents and photos.'),
              ('⚠️', 'Previous visa violations', "Overstays or breaches of a previous visa's terms.")]


def visa_page(o):
    r = '../'
    det = DET.get(o['s'], {'products': [], 'faq': []})
    name, sname = o['n'], short(o['n'])
    live = f"{LIVE}/v4/{o['s']}-visa"
    qas = [(q, a) for q, a in det['faq'] if not SITE_FAQ_WORDS.search(q)]
    guides = [p for p in BLOG if p.get('destinationSlug') == o['s']][:3] or BLOG[:3]
    others = [d for d in POPULAR + DEST if d['s'] != o['s']]
    others = list({d['s']: d for d in others}.values())[:4]

    prods = []
    for p in det['products']:
        pr = next((x for x in p['prices'] if x.get('isDefault')), (p['prices'] or [None])[0])
        if not pr:
            continue
        prods.append({
            'id': p['productId'], 'name': p['name'], 'entry': p['entryType'], 'stay': p['stayValidityDays'],
            'valid': p['visaValidityDays'], 'time': p['processingTime'], 'days': days_from(p['processingTime']) or 5,
            'total': pr['total'], 'govt': pr.get('govtFee') if pr.get('displayMode') == 'separated' else None,
            'svc': pr.get('serviceFee') or 0, 'refund': pr.get('refundType') or '', 'includes': pr.get('includes') or [],
            'addons': [{'code': a['code'], 'name': ' '.join(a['name'].split()), 'cat': a['category'], 'total': a['total'],
                        'days': days_from(a['name']) if a['category'] == 'express' else None} for a in p['addons']],
            '_src': p,
        })
    offer = next((p['groupOffer'] for p in det['products'] if p.get('groupOffer')), None)

    crumbs = f'<nav class="crumbs" aria-label="Breadcrumb"><a href="{r}index.html">Home</a><span aria-hidden="true">/</span><a href="{r}destinations.html">Destinations</a><span aria-hidden="true">/</span><span>{H(sname)} visa</span></nav>'
    hero = f'<div class="vhero"><img src="{o["img"]}" alt="{H(sname)}"></div>'

    if not prods:
        body = f'''<div class="wrap">{crumbs}{hero}
<div class="vhead"><div><span class="pill">{o['f']} {H(name)}</span><h1 style="margin-top:12px">{H(sname)} visa</h1></div></div>
<section style="padding:32px 0 96px"><div class="unavail">
  <h2>Not yet available for Indian passport holders.</h2>
  <p class="lead" style="margin:12px auto 0">Eligibility depends on your passport. Holders of other passports may be able to apply online{f", from {money(o['$'])}" if o.get('$') else ''}.</p>
  <div class="row"><a class="btn lg" href="{live}">Check with my passport</a><a class="btn lg wa" href="{WA}">Ask on WhatsApp</a></div>
</div>
<h2 class="mt" style="font-size:32px">Popular visas you can apply for</h2>
<div class="rail" style="padding-left:0;margin-top:24px">{tiles(r, POPULAR)}</div>
</section></div>
{cta(r)}'''
        page(f"visa/{o['s']}.html", f'{sname} visa: requirements & how to apply | Insta Global Travel',
             f'{sname} visa eligibility, price and documents. Check availability for your passport and apply online with Insta Global Travel.', body, 'Visas')
        return

    # Recommend the cheapest standard tourist visa (single entry, 30+ day stay); transit/extensions are niche.
    core = [p for p in prods if p['entry'] == 'single' and p['stay'] >= 30 and not re.search(r'transit|exten', p['name'], re.I)]
    rec = min(core or prods, key=lambda p: p['total'])
    cheapest = min(prods, key=lambda p: p['total'])
    default = rec

    def badge(p):
        b = []
        if p is rec and len(prods) > 1: b.append('<span class="pill gold">Recommended</span>')
        if p is cheapest and len(prods) > 1 and p is not rec: b.append('<span class="pill">Lowest price</span>')
        return ''.join(b)

    opts = ''.join(f'''<label class="opt"><input type="radio" name="pid" value="{p['id']}"{' checked' if p is default else ''}>
<span class="in"><span class="radio"></span><span><h3>{H(p['name'])} {badge(p)}</h3>
<p>{p['entry'].capitalize()} entry · stay {p['stay']} days · valid {p['valid']} days · {H(p['time'])}</p></span>
<span class="p">{money(p['total'])}<small>per traveller</small></span></span></label>''' for p in prods)

    def per_product(p):
        s = p['_src']
        docs = ''.join(f'<li>{H(d["name"])}<span>{"Required" if d.get("mandatory") else "Optional"}</span></li>' for d in s['documents'])
        desc = ''.join(f'<p>{H(x)}</p>' for x in paras(s['description']))
        elig = [x for e in s['eligibilityNotes'] for x in paras(e)]
        notes = list(s['notes'])
        if s.get('isExtendable') and s.get('extensionDays'):
            notes.append(f"This visa can be extended by {s['extensionDays']} days, up to {s['extensionMaxTimes']} time{'s' if (s['extensionMaxTimes'] or 1) > 1 else ''}, without leaving the country.")
        hidden = '' if p is default else ' hidden'
        return f'''<div data-pid="{p['id']}"{hidden}>
<section><h2>Documents you'll need</h2>{f'<ul class="docs">{docs}</ul>' if docs else "<p class='muted'>No specific documents are listed for this visa. We'll confirm exactly what's needed during your application.</p>"}
<p class="small muted" style="margin-top:12px">Upload photos or scans from your phone. Our experts check everything before submission.</p></section>
{f'<section><h2>About this visa</h2><div class="prose">{desc}</div></section>' if desc else ''}
{f'<section><h2>Eligibility</h2><div class="prose">' + ''.join(f'<p>{H(x)}</p>' for x in elig) + '</div></section>' if elig else ''}
{f'<section><h2>Good to know</h2><ul class="notes">' + ''.join(f'<li>{H(x)}</li>' for x in notes) + '</ul></section>' if notes else ''}
</div>'''

    vdata = {'slug': o['s'], 'offer': {'min': offer['minApplicants'], 'pct': offer['percent']} if offer and offer.get('appliesTo') == 'service_fee' else None,
             'products': [{k: v for k, v in p.items() if k != '_src'} for p in prods]}

    vjson = json.dumps(vdata, ensure_ascii=False).replace('</', '<\\/')
    body = f'''<div class="wrap">{crumbs}{hero}
<div class="vhead"><div><span class="pill">{o['f']} Prices for Indian passport holders · <a class="more" href="{live}">Other passport</a></span>
<h1 style="margin-top:12px">{H(sname)} visa</h1></div></div>
<div class="facts">
  <div class="ok"><small>Guaranteed by</small><b data-days="{default['days']}"></b></div>
  <div><small>From</small><b>{money(cheapest['total'])}</b></div>
  <div><small>Visa type</small><b>{'E-Visa · 100% online' if o['ft'] == 'evisa' else 'Visa'}</b></div>
  <div><small>Stay up to</small><b>{max(p['stay'] for p in prods)} days</b></div>
</div>
<div class="layout">
<div>
<section id="options"><h2>Choose your visa</h2><div class="opts">{opts}</div></section>
{''.join(per_product(p) for p in prods)}
<section><h2>How it works</h2><ol class="steps4">
  <li><em>STEP 1</em><b>Apply online</b><p>Fill a simple form and upload your documents. No embassy queues.</p></li>
  <li><em>STEP 2</em><b>We verify &amp; submit</b><p>We check everything and submit to the authority on your behalf.</p></li>
  <li><em>STEP 3</em><b>Visa gets processed</b><p>Track the status in real time while it's processed.</p></li>
  <li><em>STEP 4</em><b>Get your visa</b><p>We email your approved visa, ready to travel.</p></li>
</ol></section>
<section><h2>Avoid these rejection reasons</h2><ul class="docs">{''.join(f'<li style="display:block"><b>{i} {t}</b><br><span class="muted small" style="margin:0">{d}</span></li>' for i, t, d in REJECTIONS)}</ul></section>
{f'<section><h2>{H(sname)} visa FAQs</h2>{faq_block(qas)}</section>' if qas else ''}
<section><h2>Travel guides</h2><div class="cols3">{posts(r, guides)}</div></section>
</div>
<aside><div class="sum" id="calc">
  <div class="by"><small>🎉 Guaranteed visa by</small><b id="c-by"></b></div>
  <h3 id="c-name"></h3><p class="sub" id="c-sub"></p>
  <div id="speed"></div>
  <div class="fld stepper"><label for="c-n" style="margin:0">Travellers</label><div><button type="button" id="c-minus" aria-label="Remove traveller">−</button><output id="c-n">1</output><button type="button" id="c-plus" aria-label="Add traveller">+</button></div></div>
  <div id="extras"></div>
  <div class="lines" id="c-lines"></div>
  <p class="small" style="color:var(--ok)" id="c-hint"></p>
  <div class="total"><span>Total</span><b id="c-total"></b></div>
  <a class="btn lg block" href="{live}">Start application →</a>
  <div class="protect">🛡<span><b>Service Protect included.</b> If we cause a delay, your service fee is refunded.</span></div>
  <p class="fine">Includes visa fee, service fee and VAT. Final price confirmed for your passport on the next step.</p>
</div></aside>
</div>
</div>
<div class="mbar"><div><b id="m-total"></b><small id="m-by"></small></div><a class="btn" href="{live}">Start application →</a></div>
<section class="alt"><div class="wrap"><div class="head"><div><h2>Other popular visas.</h2></div><a class="more" href="{r}destinations.html">All destinations</a></div><div class="rail" style="padding:0">{tiles(r, others)}</div></div></section>
<script type="application/json" id="vdata">{vjson}</script>'''
    ld = [faq_ld(qas)] if qas else []
    ld.append({'@context': 'https://schema.org', '@type': 'Product', 'name': f'{sname} visa', 'image': o['img'],
               'offers': {'@type': 'AggregateOffer', 'priceCurrency': 'USD', 'lowPrice': cheapest['total'], 'highPrice': max(p['total'] for p in prods), 'offerCount': len(prods)}})
    page(f"visa/{o['s']}.html", f"{sname} visa for Indians: price, documents & apply online | Insta Global Travel",
         f"Apply for your {sname} visa online from {money(cheapest['total'])}. {rec['time']} processing, guaranteed delivery date, expert document check.",
         body, 'Visas', jsonld=ld, body_class='has-mbar')


# ---------------------------------------------------------------- service pages

def text_lines(name):
    s = (ROOT / f'data/pages/{name}.html').read_text()
    b = re.sub(r'<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>', '', s, flags=re.S)
    b = re.search(r'<main.*?</main>', b, flags=re.S).group(0)
    t = html.unescape(re.sub(r'<[^>]+>', '\n', b))
    return [l.strip() for l in t.split('\n') if l.strip()]


def service_rows(name):
    """Rows of the live service table: '✓', name, [badge], fields..., '$price', unit, summary."""
    L, rows, i = text_lines(name), [], 0
    while i < len(L):
        if L[i] == '✓':
            j = i + 1
            while j < len(L) and not L[j].startswith('$'):
                j += 1
            f = [x for x in L[i + 1:j] if x not in ('Cheapest', 'Urgent', 'Recommended')]
            if f and j < len(L):
                rows.append((f[0], f[-1], L[j]))
            i = j
        i += 1
    return list(dict.fromkeys(rows))


def service_page(path, live_path, title, h1, lead, cfg, steps, active, ic):
    rows = service_rows(live_path)
    table = ''.join(f'<tr><td>{H(n)}</td><td>{H(t)}</td><td>{H(p)}</td></tr>' for n, t, p in rows[:12])
    st = ''.join(f'<div class="box"><div class="num">{i}</div><h3>{H(a)}</h3><p>{H(b)}</p></div>' for i, (a, b) in enumerate(steps, 1))
    body = f'''<div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Home</a><span aria-hidden="true">/</span><span>{H(title)}</span></nav></div>
<section class="phero"><div class="wrap">
  <span class="pill">{ic} {H(title)}</span>
  <h1 style="margin-top:16px">{h1}</h1><p class="lead">{H(lead)}</p>
  <div class="row"><a class="btn lg" href="{LIVE}/{live_path}">Get started</a><a class="btn lg ghost" href="{WA}">Ask an expert</a></div>
</div></section>
<section class="alt"><div class="wrap">
  <div class="head"><div><h2>Clear prices.</h2><p class="lead">{H(cfg)} Government and service fees are shown separately at checkout.</p></div></div>
  <table class="tbl"><thead><tr><th>Service</th><th>Processing</th><th>Price</th></tr></thead><tbody>{table}</tbody></table>
  <p class="mt center"><a class="btn" href="{LIVE}/{live_path}">See all {len(rows)} options &amp; other countries</a></p>
</div></section>
<section><div class="wrap"><div class="head"><div><h2>How it works.</h2></div></div><div class="cols4">{st}</div>
<div class="protect" style="margin-top:28px;font-size:15px">🛡<span><b>Service Protect included.</b> Handled by experts, tracked end to end. If we cause a delay, your service fee is refunded.</span></div></div></section>
{cta('', 'Let us handle the paperwork.', 'Real experts, live tracking and honest pricing on every service.')}'''
    page(path, f'{title} | Insta Global Travel', lead[:155], body, active)


def flights():
    routes = [('DEL', 'Delhi', 'DXB', 'Dubai', 'United Arab Emirates'), ('BOM', 'Mumbai', 'DXB', 'Dubai', 'United Arab Emirates'),
              ('DEL', 'Delhi', 'BKK', 'Bangkok', 'Thailand'), ('BLR', 'Bengaluru', 'SIN', 'Singapore', 'Singapore'),
              ('DXB', 'Dubai', 'LON', 'London', 'United Kingdom'), ('DEL', 'Delhi', 'MCT', 'Muscat', 'Oman')]
    chips = ''.join(f'<button class="chip" type="button" data-route="{a}|{b}|{c}|{d}" data-country="{e}">{b} → {d}</button>' for a, b, c, d, e in routes)
    body = f'''<section class="hero" style="padding-bottom:56px"><div class="wrap">
  <span class="eyebrow">✈️ Flights · Compare airlines &amp; agencies</span>
  <h1 style="font-size:clamp(44px,8vw,88px)">Find the <span class="grad">lowest fare.</span></h1>
  <p class="lead">Compare fares, pick the cheapest day, and book in a few taps.</p>
  <form class="search" id="ai-form" style="margin-top:32px">
    <input id="ai-q" placeholder="Try: Delhi to Dubai next Friday, non-stop" aria-label="Describe your trip" autocomplete="off">
    <button class="btn" type="submit">✨ <span>Search</span></button>
  </form>
  <p class="small muted" id="ai-msg" style="margin-top:10px;min-height:20px" aria-live="polite"></p>
  <form class="fform" id="f-form" autocomplete="off">
    <div class="ff"><label for="f-from">From</label><input id="f-from" placeholder="City or airport" required><ul class="sugg" role="listbox" hidden></ul></div>
    <button class="swap" type="button" id="f-swap" aria-label="Swap origin and destination">⇄</button>
    <div class="ff"><label for="f-to">To</label><input id="f-to" placeholder="City or airport" required><ul class="sugg" role="listbox" hidden></ul></div>
    <div class="ff"><label for="f-depart">Depart</label><input id="f-depart" type="date" required></div>
    <div class="ff"><label for="f-return">Return <small>(optional)</small></label><input id="f-return" type="date"></div>
    <div class="ff opts2"><label class="addon"><input type="checkbox" id="f-direct"> Non-stop only</label>
      <select id="f-cur" aria-label="Currency"><option value="inr">₹ INR</option><option value="aed">AED</option><option value="usd">$ USD</option></select></div>
    <button class="btn lg" type="submit">Search flights</button>
  </form>
  <p class="small" id="f-msg" style="color:#b42318;margin-top:10px;min-height:20px" role="alert"></p>
  <div class="quick">{chips}</div>
</div></section>
<section class="alt" id="results" hidden style="padding:0 0 72px">
  <div class="rsum"><div class="wrap"><div><b id="rs-route"></b><small id="rs-meta"></small></div><button class="btn ghost" type="button" id="rs-edit">Modify search</button></div></div>
  <div class="wrap" style="padding-top:24px">
    <div id="calwrap" hidden><h2 style="font-size:24px;margin-bottom:12px">Cheapest days this month</h2><div class="cal" id="cal"></div></div>
    <p class="protect" id="insight" hidden style="font-size:15px;margin:0 0 12px"></p>
    <p class="protect" id="visa-hint" hidden style="margin:0 0 20px"></p>
    <div class="rgrid">
      <aside class="filters" id="filters" aria-label="Filters">
        <div class="fhead"><h3>Filters</h3><button type="button" class="linkbtn" id="f-reset">Reset all</button></div>
        <div id="fbody"></div>
        <button class="btn block fapply" type="button" id="f-apply">Show flights</button>
      </aside>
      <div>
        <div class="tabs" id="tabs" role="tablist" aria-label="Sort flights"></div>
        <div class="rbar"><span class="muted small" id="count"></span><button class="chip ffbtn" type="button" id="f-open">⚙︎ Filters</button></div>
        <div id="list" class="flist"></div>
        <p class="fine" style="text-align:left;margin-top:20px">Fares are the latest found and may change. The seller confirms the final price before you pay.</p>
      </div>
    </div>
  </div>
</section>
<section><div class="wrap"><div class="cols3">
  <div class="box"><div class="ic">📉</div><h3>Lowest fare, first</h3><p>We compare fares across airlines and agencies and show the cheapest day of the month.</p></div>
  <div class="box"><div class="ic">🔒</div><h3>Secure checkout</h3><p>You pay on our partner's secure booking page, directly with the airline or agency.</p></div>
  <div class="box"><div class="ic">🛂</div><h3>Visa sorted too</h3><p>Flying somewhere that needs a visa? Apply online with a guaranteed visa date.</p></div>
</div></div></section>
<dialog id="review" class="review-dlg" aria-labelledby="rv-title">
  <div class="rv-head"><h2 id="rv-title">Review your flight</h2><button type="button" id="rv-close" aria-label="Close">✕</button></div>
  <div id="rv-body"></div>
  <a class="btn lg block" id="rv-go" href="#" rel="noopener">Continue to secure booking →</a>
  <p class="fine">You'll enter passenger details and pay on our booking partner's secure page. The final price is confirmed there.</p>
</dialog>'''
    page('flights.html', 'Cheap flights: compare fares & book | Insta Global Travel',
         'Compare live flight fares, see the cheapest day of the month and book in a few taps.', body, 'Flights', dest=True, script='flights.js')


# ---------------------------------------------------------------- content pages

def simple(path, title, desc, inner, active='', jsonld=None, dest=False):
    page(path, f'{title} | Insta Global Travel', desc, inner, active, jsonld=jsonld, dest=dest)


def crumbs(t):
    return f'<div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Home</a><span aria-hidden="true">/</span><span>{t}</span></nav></div>'


def about():
    simple('about.html', 'About us', 'Dubai-based pioneers of online visas since 2016. Clear prices, clear documents and a date you can count on.', f'''{crumbs('About')}
<section class="phero"><div class="wrap"><h1>Visas, made effortless.</h1>
<p class="lead">We're Dubai-based travel technology specialists on a simple mission: take the queues, confusion and uncertainty out of visa applications, and replace them with clear prices, clear documents and a date you can count on.</p></div></section>
<section class="alt"><div class="wrap">
  <div class="head"><div><h2>Pioneers of online visas.<br>Since 2016.</h2><p class="lead">Back in 2016, a UAE visa simply couldn't be bought online. Applying meant security deposits, personal recommendations and a lot of friction. We set out to change that.</p></div></div>
  <div class="cols2">
    <div class="box"><span class="pill">2016 · The beginning</span><h3 style="margin-top:16px">instadubaivisa.com</h3><p>A single-destination service that made applying for a UAE visa genuinely simple: transparent pricing, no deposits, no gatekeeping. For many travellers, it was the first time a visa could be bought online.</p></div>
    <div class="box"><span class="pill dark">Today · Going global</span><h3 style="margin-top:16px">Insta Global Travel</h3><p>Many destinations and travel-document services under one roof, with the same simple, traveller-first process we pioneered.</p></div>
  </div>
</div></section>
<section><div class="wrap"><div class="stats" style="margin-top:0">
  <div><b>50,000+</b><span>Visas processed</span></div><div><b>100+</b><span>Partner countries</span></div><div><b>100%</b><span>Paperless</span></div><div><b>24/7</b><span>Tracking &amp; support</span></div>
</div></div></section>
<section class="alt"><div class="wrap">
  <div class="head"><div><h2>Three values.<br>Every booking.</h2></div></div>
  <div class="cols3">
    <div class="box"><div class="ic">💎</div><h3>Best available options</h3><p>Every visa type for your destination side by side: entry, stay, validity and price. You choose what fits, not what we push.</p></div>
    <div class="box"><div class="ic">🔍</div><h3>Transparent pricing</h3><p>Government fee and service fee shown separately, before you pay. No hidden charges, no surprises at checkout.</p></div>
    <div class="box"><div class="ic">🛡</div><h3>Premium experience</h3><p>A guaranteed delivery date on every application, real-time tracking, and our Visa Protect promise: if a service lapse is ours, you get up to a 100% refund.</p></div>
  </div>
</div></section>
<section><div class="wrap cols2" style="align-items:center">
  <div><h2>For business &amp; corporate travel.</h2><p class="lead">Run single or bulk visa applications for any destination with re-usable traveller profiles. A dedicated account manager comes standard.</p><p class="mt"><a class="btn" href="contact.html">Talk to us</a></p></div>
  <div class="box"><h3>Who we are</h3><p>Insta Global Travel is a Dubai-based travel company specialising in fast, reliable visa processing. With travel partners in more than 100 countries, we serve everyone from first-time tourists to corporate teams, combining deep industry experience with technology built in-house.</p></div>
</div></section>
{cta('')}''')


def why_us():
    reasons = [('📅', 'Guaranteed delivery date', 'Every application shows a clear delivery date up front, so you can book flights and plan with confidence.'),
               ('💎', 'Transparent pricing', 'The full price, government fee and our service fee, before you pay. No hidden charges.'),
               ('🛡️', 'Expert document check', 'We review your documents against current requirements for your nationality before submission, cutting the risk of rejection.'),
               ('⚡', '100% online in minutes', 'Apply from home in a few steps. Upload, pay and track it all online.'),
               ('📍', 'Live application tracking', 'Follow every stage in real time and get updates by email.'),
               ('🔒', 'Secure, flexible payments', 'Pay safely with trusted gateways in your own currency.'),
               ('💬', 'Real human support', 'Visa experts on chat, WhatsApp and email before, during and after you apply.'),
               ('🌍', 'More than visas', 'Passport, attestation and appointment services, all with one trusted partner.')]
    simple('why-us.html', 'Why choose us', 'Guaranteed delivery dates, honest pricing and expert checks on every application, plus rewards on every booking.', f'''{crumbs('Why us')}
<section class="phero center"><div class="wrap"><span class="eyebrow"><b>★ {RATING}</b> from {REVIEWS} verified reviews</span>
<h1 style="margin-top:20px">Why travellers choose us.</h1><p class="lead">A guaranteed delivery date, honest pricing and expert checks on every application, plus rewards that make every booking go further.</p>
<div class="row"><a class="btn lg" href="destinations.html">Find my visa</a><a class="btn lg ghost" href="{WA}">Talk to an expert</a></div></div></section>
<section class="alt"><div class="wrap"><div class="cols4">{''.join(f'<div class="box"><div class="ic">{i}</div><h3>{t}</h3><p>{d}</p></div>' for i, t, d in reasons)}</div></div></section>
<section><div class="wrap">{GUARANTEE}</div></section>
<section class="alt"><div class="wrap"><div class="head"><div><h2>What travellers say.</h2></div></div>{reviews_block('')}</div></section>
{cta('', 'Ready to apply the easy way?', 'Guaranteed dates, honest pricing, rewards on every order and real people to help.')}''', 'Why us')


def rewards():
    tiers = [('Bronze', '—', 'Starter tier. Earn points on every order.', '#a0703c'), ('Silver', '3%', 'From 5,000 lifetime points.', '#7d8590'),
             ('Gold', '5%', 'From 12,000 lifetime points. Priority support.', '#b68a00'), ('Platinum', '8%', 'From 25,000 lifetime points. Priority processing & support.', '#1d1d1f')]
    simple('rewards.html', 'Rewards program', 'Earn points on every booking and redeem them for real discounts. Join free and get 100 points.', f'''{crumbs('Rewards')}
<section class="phero center"><div class="wrap"><span class="pill gold">🏅 Rewards program</span><h1 style="margin-top:16px">Travel more.<br>Pay less.</h1>
<p class="lead">Join free, get 100 points to start, then earn every time you book and save at checkout.</p>
<div class="row"><a class="btn lg" href="{LIVE}/account">Create free account</a><a class="btn lg ghost" href="{LIVE}/account">Sign in</a></div></div></section>
<section class="alt"><div class="wrap"><div class="head"><div><h2>Ways to earn.</h2><p class="lead">Every 100 points = $0.27 off. Points never expire.</p></div></div>
<div class="cols4">
  <div class="box"><div class="big">100</div><h3>Create an account</h3><p>One-time welcome bonus, credited instantly.</p></div>
  <div class="box"><div class="big">1 pt</div><h3>Every $0.27 spent</h3><p>On visas, passport, attestation and more.</p></div>
  <div class="box"><div class="big">100</div><h3>Leave a review</h3><p>After any completed order.</p></div>
  <div class="box"><div class="big">1,500</div><h3>Refer a friend</h3><p>When they complete their first order. They get 1,000 too.</p></div>
</div></div></section>
<section><div class="wrap"><div class="head"><div><h2>Member tiers.</h2><p class="lead">The more you earn over time, the more you save, automatically.</p></div></div>
<div class="tiers">{''.join(f'<div class="tier" style="background:{c}"><b>{n}</b><div class="big">{p if p != "—" else "Start"}</div><p>{d}</p></div>' for n, p, d, c in tiers)}</div>
<p class="mt muted">Add your member card to Apple Wallet or Google Wallet. It updates as you earn.</p></div></section>
{cta('', 'Start earning today.', "It's free to join, and you'll get 100 points right away.")}''')


def partners():
    simple('partners.html', 'Travel agent partners', 'Book UAE visas for your clients at agent net rates with a prepaid wallet, self-service portal and VAT invoices.', f'''{crumbs('Partners')}
<section class="phero"><div class="wrap"><span class="pill">For travel agencies</span><h1 style="margin-top:16px">Grow your agency with us.</h1>
<p class="lead">Book UAE visas for your clients at agent net rates, with a prepaid wallet, a self-service portal and VAT tax invoices for your books.</p>
<div class="row"><a class="btn lg" href="{LIVE}/partners">Apply to partner</a><a class="btn lg ghost" href="{LIVE}/partners">Partner sign in</a></div></div></section>
<section class="alt"><div class="wrap"><div class="cols4">
  <div class="box"><div class="ic">💸</div><h3>Agent net rates</h3><p>Tiered pricing on every visa service. Government fees passed through at cost, 5% VAT added transparently.</p></div>
  <div class="box"><div class="ic">👛</div><h3>Prepaid wallet + credit</h3><p>Top up once and book instantly. Optional credit limits keep your team moving.</p></div>
  <div class="box"><div class="ic">🖥️</div><h3>Self-service portal</h3><p>Book for clients, track every application and download your Statement of Account any time.</p></div>
  <div class="box"><div class="ic">🧾</div><h3>UAE VAT tax invoices</h3><p>A proper tax invoice under Insta Tourism LLC for every booking.</p></div>
</div></div></section>
<section><div class="wrap"><div class="head"><div><h2>Three steps to start.</h2></div></div><div class="cols3">
  <div class="box"><div class="num">1</div><h3>Apply</h3><p>Send us your agency details.</p></div>
  <div class="box"><div class="num">2</div><h3>Get verified</h3><p>Upload your trade licence &amp; KYC and accept the Visa Services Agreement in your portal.</p></div>
  <div class="box"><div class="num">3</div><h3>Book &amp; manage</h3><p>We set your net rates; you book and manage everything online.</p></div>
</div><p class="mt muted small">Insta Tourism LLC is a DET-licensed travel agency. Partner terms follow the Visa Services Agreement, which you review and accept in your portal.</p></div></section>
{cta('', 'Run a travel page or community?', 'Join our affiliate programme and earn commission on every booking you send, for the lifetime of each customer.')}''')


def contact():
    simple('contact.html', 'Contact us', 'Talk to our visa experts on WhatsApp, phone or email. 24/7 online support.', f'''{crumbs('Contact')}
<section class="phero"><div class="wrap"><h1>We're here to help.</h1><p class="lead">Questions about a visa or your application? Real people answer, 24/7 online.</p></div></section>
<section class="alt" style="padding-top:56px"><div class="wrap cols2">
  <div class="contact-list">
    <a href="{WA}"><span class="ic">💬</span><span><small>WhatsApp · fastest</small><b>+971 50 951 8129</b></span></a>
    <a href="tel:+97145464650"><span class="ic">📞</span><span><small>Call · 10 AM – 7 PM Dubai time</small><b>+971 4 546 4650</b></span></a>
    <a href="mailto:contact@instaglobaltravel.com"><span class="ic">✉️</span><span><small>Email</small><b>contact@instaglobaltravel.com</b></span></a>
    <a href="{LIVE}/contact"><span class="ic">📝</span><span><small>Prefer a form?</small><b>Send us a message</b></span></a>
  </div>
  <div class="box"><h3>Office</h3><p>Insta Tourism LLC<br>201, M Square Commercial Building<br>Near Double Tree Hotel, Bur Dubai<br>Dubai, UAE · P.O. Box 120375</p>
  <h3 style="margin-top:24px">Call-support locations</h3><p>Dubai, United Arab Emirates · Delhi, India · Rajasthan, India</p>
  <h3 style="margin-top:24px">Already applied?</h3><p>Check live status with your order reference.</p><a class="btn" href="{LIVE}/track">Track application</a></div>
</div></section>''')


def help_center():
    cards = [('🔎', 'Track your application', 'Live status and next steps with your order reference.', f'{LIVE}/track'),
             ('🧾', 'My orders & account', 'Orders, payments, saved travellers and documents.', f'{LIVE}/account'),
             ('🛂', 'Apply for a service', 'Start a visa, passport, attestation or appointment application.', 'destinations.html'),
             ('📄', 'Documents & requirements', 'What to upload and per-destination requirements.', 'faq.html'),
             ('💳', 'Payments & refunds', 'Accepted methods, receipts and our refund policy.', 'terms.html'),
             ('❓', 'All FAQs', 'Answers to the questions customers ask most.', 'faq.html')]
    simple('help-center.html', 'Help Center', 'Track your application, find answers and reach our 24/7 support team.', f'''{crumbs('Help Center')}
<section class="phero center"><div class="wrap"><h1>How can we help?</h1><p class="lead">Find quick answers, track your application, or talk to a person.</p>
<div style="max-width:640px;margin:0 auto">{search_form('Search a destination')}</div></div></section>
<section class="alt"><div class="wrap"><div class="cols3">{''.join(f'<a class="box" href="{h}"><div class="ic">{i}</div><h3>{t}</h3><p>{d}</p></a>' for i, t, d, h in cards)}</div></div></section>
<section><div class="wrap center"><h2>Still need help?</h2><p class="lead" style="margin:12px auto 32px">Our team is online 24/7, with call support 10 AM – 7 PM Dubai time.</p>
<div class="phero center" style="padding:0"><div class="row"><a class="btn lg wa" href="{WA}">Chat on WhatsApp</a><a class="btn lg ghost" href="tel:+97145464650">Call +971 4 546 4650</a></div></div></div></section>''', 'Help', dest=True)


def faq_page():
    groups = []
    for o in DEST:
        qas = [(q, a) for q, a in DET.get(o['s'], {}).get('faq', []) if not SITE_FAQ_WORDS.search(q)]
        if qas:
            groups.append((o, qas))
    site = []
    for v in DET.values():
        for q, a in v['faq']:
            if SITE_FAQ_WORDS.search(q) and q not in dict(site):
                site.append((q, a))
    inner = ''.join(f'''<details class="fgroup" data-name="{H(o['n'].lower())}"><summary>{o['f']} {H(o['n'])} <span class="muted small">({len(q)})</span></summary>
{faq_block(q)}<p style="margin:12px 0 20px"><a class="more" href="visa/{o['s']}.html">{H(short(o['n']))} visa details</a></p></details>''' for o, q in groups)
    simple('faq.html', 'FAQ', 'Answers about visa applications, documents, processing times, payments and rewards.', f'''{crumbs('FAQ')}
<section class="phero"><div class="wrap"><h1>Questions? Answered.</h1><p class="lead">Pick a destination for visa-specific answers, or read about rewards and payments below.</p></div></section>
<section class="alt" style="padding-top:56px"><div class="wrap narrow">
<input class="find" id="faqfind" type="search" placeholder="Filter by country" aria-label="Filter by country" style="width:100%;margin-bottom:20px">
<div class="faq">{inner}</div>
<h2 class="mt" style="font-size:32px;margin-bottom:20px">Rewards, membership &amp; affiliates</h2>{faq_block(site)}
</div></section>
<script>document.getElementById('faqfind').oninput=e=>{{const q=e.target.value.toLowerCase();document.querySelectorAll('.fgroup').forEach(d=>d.hidden=!d.dataset.name.includes(q))}}</script>''', jsonld=faq_ld(site))


def reviews_page():
    simple('reviews.html', 'Reviews', f'Rated {RATING}★ from {REVIEWS} verified reviews. Only customers with a real order can post.', f'''{crumbs('Reviews')}
<section class="phero"><div class="wrap"><h1>What travellers say.</h1><p class="lead">Only customers who booked with us can post a review, so every review is tied to a real order. We publish every genuine review, good and constructive.</p></div></section>
<section class="alt" style="padding-top:56px"><div class="wrap">{reviews_block('', full=True)}
<div class="center mt"><a class="btn" href="{LIVE}/reviews">Read all {REVIEWS} reviews</a> <a class="btn ghost" href="{LIVE}/reviews">Write a review · earn 100 points</a></div></div></section>
{cta('')}''')


def blog_page():
    cats = sorted({p['category'] for p in BLOG if p['category']})
    chips = ''.join(f'<button class="chip" type="button" data-c="{H(c)}" aria-pressed="false">{H(c)}</button>' for c in cats)
    simple('blog.html', 'Travel guides & visa news', 'Guides, document help and visa news to make your trip effortless.', f'''{crumbs('Blog')}
<section class="phero"><div class="wrap"><h1>Travel guides.</h1><p class="lead">Tips, document help and visa news to make your trip effortless.</p></div></section>
<section style="padding-top:0"><div class="wrap">
<div class="regions" id="cats"><button class="chip" type="button" data-c="" aria-pressed="true">All</button>{chips}</div>
<div class="cols3" id="posts">{posts('', BLOG)}</div></div></section>
<script>
const P=[...document.querySelectorAll('#posts .post')];P.forEach((p,i)=>p.dataset.c=p.querySelector('small').textContent);
document.getElementById('cats').onclick=e=>{{const b=e.target.closest('[data-c]');if(!b)return;
document.querySelectorAll('#cats .chip').forEach(c=>c.setAttribute('aria-pressed',c===b));P.forEach(p=>p.hidden=b.dataset.c&&p.dataset.c!==b.dataset.c)}};
</script>''')


def legal(path, src, title):
    s = (ROOT / f'data/pages/{src}.html').read_text()
    m = re.search(r'<main.*?</main>', s, flags=re.S).group(0)
    m = re.sub(r'<script.*?</script>|<template.*?</template>|<nav.*?</nav>|<h1.*?</h1>', '', m, flags=re.S)
    m = re.sub(r'<(/?)(?:main|div|span)[^>]*>', '', m)
    def strip_attrs(x):
        href = re.search(r'href="[^"]*"', x.group(2))
        return f'<{x.group(1)} {href.group(0)}>' if href else f'<{x.group(1)}>'
    m = re.sub(r'<(\w+)(\s[^>]*)>', strip_attrs, m)
    m = m.replace('href="/terms"', 'href="terms.html"').replace('href="/privacy"', 'href="privacy.html"').replace('href="/', f'href="{LIVE}/')
    simple(path, title, f'{title} for Insta Global Travel, operated by Insta Tourism LLC.', f'''{crumbs(title)}
<section class="phero" style="padding-bottom:24px"><div class="wrap narrow"><h1 style="font-size:clamp(36px,6vw,56px)">{H(title)}</h1></div></section>
<section style="padding-top:0"><div class="wrap narrow legal-prose">{m}</div></section>''')


# ---------------------------------------------------------------- build

def selfcheck():
    assert days_from('48-72 Working Hours') == 3 and days_from('7 to 10 Working Days') == 10
    assert days_from('Express 4 Hours') == 0 and days_from('Priority Service 24 Hours') == 1 and days_from('') is None


def main():
    selfcheck()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'assets').mkdir(parents=True)
    for f in ('style.css', 'app.js', 'flights.js'):
        shutil.copy(ROOT / 'assets' / f, OUT / 'assets' / f)
    (OUT / 'assets/data.js').write_text('const DEST=' + json.dumps(DEST, ensure_ascii=False, separators=(',', ':')) + ';\n')

    home(); destinations()
    for o in DEST:
        visa_page(o)
    service_page('passport.html', 'passport-service', 'Passport Service', 'Passport renewal,<br>made effortless.',
                 "Document pickup, careful checking and live tracking, end to end. You can apply directly with the authority yourself; we're here to make the paperwork easier.",
                 'Shown for Indian passports, living in the UAE.',
                 [('Tell us about your passport', "Country, expiry and renewal type. We confirm exactly what's needed."), ('We collect your documents', 'Doorstep pickup or secure upload. No embassy queues.'),
                  ('Checked & lodged', 'Our experts review everything and lodge your application correctly.'), ('New passport delivered', 'Track every step until it reaches your door.')], 'Passport', '🛂')
    service_page('attestation.html', 'attestation-service', 'Attestation Service', 'Document attestation,<br>without the runaround.',
                 'Degree, birth, marriage or commercial documents. We coordinate every step of the official chain (Notary, MEA, Embassy, MOFA). The attestations are issued by those authorities; we make the process easy.',
                 'Shown for documents issued in India, to be used in the UAE. Price per document.',
                 [('Share your document', "Tell us the document and where it'll be used. We confirm the exact chain."), ('We collect it', 'Doorstep pickup or secure upload of your original.'),
                  ('Full chain managed', 'Notary, HRD/Chamber, MEA, Embassy and MOFA. We follow up on every step.'), ('Attested & returned', 'Delivered back to you, tracked all the way.')], 'Attestation', '📜')
    service_page('appointments.html', 'appointment-service', 'Appointment Booking', 'Get the slot<br>everyone wants.',
                 'Visa interview and biometrics slots are scarce and vanish in seconds. We track availability, prepare your paperwork and guide you through booking at the centre you prefer.',
                 'Shown for USA appointments at centres in India. Slot availability is controlled by the authority and cannot be guaranteed.',
                 [('Tell us what you need', 'Destination, appointment type and your preferred centre.'), ('We track availability', 'We monitor the official portal and tell you the moment a slot opens.'),
                  ('Booked with our guidance', 'We help you secure the slot and share the confirmation.'), ('You show up prepared', 'We brief you on documents and what to expect.')], 'Appointments', '📅')
    flights()
    about(); why_us(); rewards(); partners(); contact(); help_center(); faq_page(); reviews_page(); blog_page()
    legal('terms.html', 'terms', 'Terms of Use')
    legal('privacy.html', 'privacy', 'Privacy Policy')
    legal('affiliate-terms.html', 'affiliate-terms', 'Affiliate Terms')
    print(len(list(OUT.rglob('*.html'))), 'pages ->', OUT)


if __name__ == '__main__':
    main()
