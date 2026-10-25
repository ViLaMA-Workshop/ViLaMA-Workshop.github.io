#!/usr/bin/env python3
"""Build a dependency-free static website without altering supplied copy.

The DOCX extraction remains the source of truth. Approved display changes are
limited to omitted sections and heading numbers; other retained text is exact.
Run: python3 tools/build.py
"""
from pathlib import Path
import html
import json
import shutil
import re
from datetime import date, datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'source-copy.json').read_text())
UPDATES = json.loads((ROOT / 'event-details.json').read_text())
WORKSHOP_DATE = date.fromisoformat(UPDATES['workshop_date'])
WORKSHOP_DAY = WORKSHOP_DATE.strftime('%A')
WORKSHOP_DISPLAY = f'{WORKSHOP_DATE.day} {WORKSHOP_DATE:%B %Y}'
VENUE = UPDATES['venue_short']
CALENDAR_VENUE = UPDATES['venue_name'].replace(',', '\\,')
COPY = {p['id']: p['text'] for p in DATA['paragraphs']}
# These changes were explicitly requested after the original complete page.
OMITTED_IDS = {'p133', 'p135', 'p138', 'p140', 'p143', 'p145'}
UNNUMBERED_HEADINGS = {'p008', 'p018', 'p021', 'p038', 'p071', 'p095', 'p109'}
USED = []
esc = lambda s: html.escape(s, quote=True)


def source(pid, tag='p', cls='', content=None, attrs=''):
    if pid in USED:
        raise ValueError('Duplicate source paragraph: ' + pid)
    USED.append(pid)
    display_text = re.sub(r'^\d+\.\s+', '', COPY[pid]) if pid in UNNUMBERED_HEADINGS else COPY[pid]
    value = esc(display_text) if content is None else content
    return f'<{tag} data-source-id="{pid}" class="source-text {cls}" {attrs}>{value}</{tag}>'


def update(key, content=None, cls='', tag='p'):
    value = esc(UPDATES[key]) if content is None else content
    return f'<{tag} data-update-id="{key}" class="source-text {cls}">{value}</{tag}>'


def heading(pid, eyebrow, tag='h2'):
    # Keep the official name mixed case even when surrounding labels are uppercase.
    eyebrow_html = esc(eyebrow).replace('ViLaMA', '<span class="workshop-name">ViLaMA</span>')
    return f'<div class="section-head"><p class="eyebrow">{eyebrow_html}</p>{source(pid,tag)}</div>'


arrow = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="1.5"/></svg>'
external = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12" stroke="currentColor" stroke-width="1.5"/></svg>'
brand = '<svg class="brand-symbol" viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M4 7h18v18H4z" stroke="currentColor" stroke-width="1.4"/><path d="m7 21 5-6 4 4 3-3" stroke="currentColor" stroke-width="1.4"/><circle cx="17" cy="12" r="2" fill="#9a4935"/><path d="M27 14h9v19H18v-5" stroke="currentColor" stroke-width="1.4"/><path d="M24 22h8m-8 4h8m-8 4h5" stroke="currentColor" stroke-width="1.4"/></svg>'
wordmark = f'<a class="brand" href="#top" aria-label="ViLaMA 2026 home">{brand}<span class="brand-word">ViLaMA <small>ICVGIP 2026</small></span></a>'
hero_title = (esc(COPY['p003'])
              .replace('First Workshop on ', '<span class="intro">First Workshop on </span>')
              .replace('Vision', '<span class="acronym-highlight">Vi</span>sion')
              .replace('Language', '<span class="acronym-highlight">La</span>nguage')
              .replace('Models', '<span class="acronym-highlight">M</span>odels')
              .replace('Applications', '<span class="accent"><span class="acronym-highlight">A</span>pplications</span>')
              .replace(' (ViLaMA 2026)', '<span class="edition"> (ViLaMA 2026)</span>'))

hero = f'''
<section class="hero" id="top" aria-labelledby="workshop-title"><div class="wrap">
<div class="hero-overline eyebrow"><span class="live-dot" aria-hidden="true"></span>{source('p001','span')}</div>
<div class="hero-grid"><div class="hero-copy">
{source('p003','h1',content=hero_title,attrs='id="workshop-title"')}
{source('p005',cls='hero-authors')}
<div class="hero-actions"><a class="button" href="#submission">Submission details {arrow}</a><a class="text-link" href="#about">Explore the workshop {arrow}</a></div>
</div><figure class="hero-art">
<!-- TODO: Replace the original conceptual illustration here if final workshop artwork is supplied. -->
<img src="assets/vision-language.svg" alt="Conceptual illustration connecting visual regions in a landscape with language tokens through a shared embedding space" width="1120" height="1000" fetchpriority="high">
<figcaption><span>VISION × LANGUAGE</span><span>ViLaMA / 2026</span></figcaption>
</figure></div>
<div class="facts" aria-label="Workshop at a glance">
<div class="fact"><span>WORKSHOP DAY</span><strong>{esc(WORKSHOP_DISPLAY)} · {esc(WORKSHOP_DAY)}</strong></div>
<div class="fact"><span>VENUE</span><strong>{esc(VENUE)}</strong></div>
<div class="fact"><span>FORMAT</span><strong>Half-day workshop</strong></div>
<div class="fact"><span>SUBMISSIONS</span><strong>OpenReview · link to follow</strong></div>
</div></div></section>'''

overview = f'''
<section class="section" id="about"><div class="wrap">
{heading('p008','THE WORKSHOP')}
<div class="section-body measure"><div class="overview-meta" role="region" aria-label="Workshop details" tabindex="0">{source('p010')}{source('p012')}{source('p014')}</div>
{source('p016',cls='abstract')}
<details class="motivation inline-detail"><summary>{source('p018','span')}</summary>{source('p020',cls='reading')}</details>
</div></div></section>'''

topics = f'''
<section class="section" id="topics"><div class="wrap">{heading('p021','RESEARCH THEMES')}
<div class="section-body"><ul class="topic-list" aria-label="Topics of Interest">{''.join('<li>'+source(f'p{i:03}')+'</li>' for i in range(23,38))}</ul></div>
</div></section>'''

def date_update(key, prefix, iso):
    original = UPDATES[key]
    if not original.startswith(prefix):
        raise ValueError(f'Update {key!r} must retain its supplied label {prefix!r}')
    value = original[len(prefix):]
    date.fromisoformat(iso)
    body = esc(prefix) + f'<time datetime="{iso}">{esc(value)}</time>'
    return update(key, body)

dates = f'''
<section class="section dates-section" id="dates"><div class="wrap">
<div class="section-head"><p class="eyebrow">PLAN YOUR SUBMISSION</p><h2>Important Dates</h2></div>
<div class="section-body"><div class="date-grid">
<!-- TODO: Add the submission deadline time and timezone once the organizers confirm them. -->
<article class="date-card">{date_update('deadline','Paper Submission Deadline: ',UPDATES['submission_date'])}</article>
<article class="date-card">{date_update('notification','Results will be announced within ',UPDATES['notification_date'])}</article>
<article class="date-card">{date_update('workshop','Workshop Date: ',UPDATES['workshop_date'])}</article>
</div><div class="dates-footer"><a class="text-link calendar-link" href="assets/vilama-2026.ics" download>Add workshop to calendar {external}</a><p class="small">All dates are in {WORKSHOP_DATE.year}.</p></div>
</div></div></section>'''

guidelines_value = UPDATES['guidelines'].replace(UPDATES['guidelines_url'], f'<a href="{esc(UPDATES["guidelines_url"])}">{esc(UPDATES["guidelines_url"])}</a>')
# TODO: Supply only organizer-approved, workshop-specific URLs in event-details.json.
word_resource = (f'<a class="resource-link" href="{esc(UPDATES["word_template_url"])}">Word template {external}</a>'
                 if UPDATES.get('word_template_url') else '<p class="small muted">Word template: see official author guidelines.</p>')
portal_resource = (f'<a class="button" href="{esc(UPDATES["openreview_url"])}">Submit on OpenReview {external}</a>'
                   if UPDATES.get('openreview_url') else '<span class="eyebrow">PLACEHOLDER · SUBMISSION PORTAL</span>')
submission = f'''
<section class="section" id="submission"><div class="wrap">{heading('p109','CALL FOR PAPERS')}
<div class="section-body"><div class="submission-layout"><div class="submission-main">
{source('p111')}{source('p112')}{source('p113')}
<div class="submission-note"><p class="eyebrow">PUBLICATION PLAN</p>{source('p127')}</div>
<!-- TODO: Update the Springer status only after publisher approval; preserve the original proposal paragraph above. -->
<div class="submission-note"><p class="eyebrow">EXTENDED VERSIONS · APPROVAL AWAITED</p>{update('extended_publication')}</div>
</div><aside class="submission-resources" aria-labelledby="resources-title"><h3 id="resources-title">For authors</h3>
<a class="resource-link" href="{esc(UPDATES['guidelines_url'])}">ICVGIP 2026 author guidelines {external}</a>
<!-- TODO: Verify the official template URLs when the conference updates its guidelines. -->
<a class="resource-link" href="{esc(UPDATES['latex_url'])}">LaTeX template (.zip) {external}</a>
<!-- TODO: Add the direct Word template URL in event-details.json when available. -->
{word_resource}
{update('format')}{update('guidelines',guidelines_value)}
<!-- TODO: Replace this labeled placeholder with the workshop-specific OpenReview link in event-details.json. -->
<div class="pending"><span class="pending-dot" aria-hidden="true"></span><div>{portal_resource}{update('openreview')}</div></div>
</aside></div>
<details class="committee"><summary>{source('p114','span')}</summary><ul class="committee-list">{''.join('<li>'+source(f'p{i:03}')+'</li>' for i in range(116,126))}</ul></details>
</div></div></section>'''

rows = [(75,[76]),(77,[78,79]),(80,[81,82]),(83,[84]),(85,[86,87]),(88,[89,90])]
schedule_rows = ''.join(f'<tr><th scope="row">{source(f"p{time:03}")}</th><td>'+''.join(source(f'p{item:03}') for item in items)+'</td></tr>' for time,items in rows)
program = f'''
<section class="section" id="program"><div class="wrap">{heading('p071','THE PROGRAM')}
<div class="section-body">{source('p073',cls='schedule-lead')}
<!-- TODO: Replace the tentative running order only when the final program is approved and the source document is updated. -->
<div class="schedule-wrap"><table class="schedule" aria-label="Tentative workshop schedule"><tbody>{schedule_rows}</tbody></table></div>
<div class="schedule-caption">{source('p091','h3')}{source('p092')}</div>
<!-- TODO: Replace the room placeholder when ISI Kolkata confirms the allocation. -->
<p class="schedule-placeholder">Placeholder · Room assignment to be announced.</p>
</div></div></section>'''

speakers = f'''
<section class="section" id="speakers"><div class="wrap">{heading('p095','ACADEMIA & INDUSTRY')}
<div class="section-body"><div class="speaker-placeholder"><span class="marker" aria-hidden="true">TBA</span>
<!-- TODO: Add confirmed speaker names, affiliations, photos and talk details after invitations are accepted. -->
<p>Placeholder · Confirmed speakers to be announced.</p></div>
{source('p097',cls='tentative-intro')}
<ul class="speaker-list" aria-label="Tentative list from the workshop proposal">{''.join('<li>'+source(f'p{i:03}')+'</li>' for i in range(99,106))}</ul>
{source('p107',cls='tentative-footer')}
</div></div></section>'''

def link_contact(pid):
    text = esc(COPY[pid])
    import re
    text = re.sub(r'([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})', r'<a href="mailto:\1">\1</a>', text)
    return source(pid,content=text)

people = []
for n, name, metas, contacts, bio, photo in [
    (1,42,[43,44,45],[46],47,'source-image1.png'),
    (2,51,[52,53,54,55],[56,57],58,'source-image2.png'),
    (3,62,[63,64,65],[66,67],68,'source-image3.jpg')]:
    people.append(f'''<article class="person">
<!-- TODO: Replace this portrait only if an updated photo is supplied by the organizer. Current photo is extracted from the Word document. -->
<div class="person-photo"><img src="assets/{photo}" alt="{esc(COPY[f'p{name:03}'].strip())}" loading="lazy" width="160" height="176"></div>
{source(f'p{name:03}','h3')}<div class="person-meta">{''.join(source(f'p{i:03}') for i in metas)}</div>
<div class="person-contact">{''.join(link_contact(f'p{i:03}') for i in contacts)}</div>
{source(f'p{bio:03}',cls='bio')}
</article>''')
organizers = f'''
<section class="section people-section" id="organizers"><div class="wrap">{heading('p038','THE PEOPLE BEHIND ViLaMA')}
<div class="section-body"><div class="people-grid">{''.join(people)}</div>{source('p070',cls='primary-contact')}</div>
</div></section>'''

venue = f'''
<section class="section venue-section" id="venue"><div class="wrap venue-grid">
<div><p class="eyebrow">MEET IN KOLKATA</p><h2>{esc(WORKSHOP_DISPLAY)}.<br><em>{esc(VENUE)}.</em></h2><a class="text-link" href="https://icvgip.in/2026/">Visit ICVGIP 2026 {external}</a></div>
<div class="venue-details"><p class="eyebrow">PRIMARY CONTACT</p><p>Dr. Prithwijit Guha</p><a href="mailto:pguha@iitg.ac.in">pguha@iitg.ac.in</a>
<!-- TODO: Replace the room placeholder with the final venue room and accessibility information. -->
<div class="pending"><span class="pending-dot" aria-hidden="true"></span><p>Placeholder · Workshop room to be announced.</p></div></div>
</div></section>'''

document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#173c36"><meta name="description" content="First Workshop on Vision Language Models and Applications (ViLaMA 2026). {esc(WORKSHOP_DISPLAY)} at {esc(VENUE)}, in conjunction with ICVGIP 2026.">
<title>ViLaMA 2026 · Vision Language Models and Applications</title>
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="styles.css"><script src="script.js" defer></script>
</head><body><a class="skip" href="#main">Skip to main content</a>
<div class="utility"><div class="wrap"><a href="https://icvgip.in/2026/">In conjunction with ICVGIP 2026 {chr(8599)}</a><span>{esc(WORKSHOP_DISPLAY.upper())} · {esc(VENUE.upper())}</span></div></div>
<header class="header"><div class="wrap nav-shell">{wordmark}
<button class="menu-toggle" type="button" aria-controls="navigation" aria-expanded="false"><span>Menu</span><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.5"/></svg></button>
<nav class="nav" id="navigation" aria-label="Main navigation"><a href="#about">About</a><a href="#topics">Topics</a><a href="#dates">Dates</a><a href="#program">Program</a><a href="#speakers">Speakers</a><a href="#organizers">Organizers</a><a class="nav-cta" href="#submission">Call for papers {chr(8599)}</a></nav>
</div></header>
<main id="main" tabindex="-1">{hero}{overview}{topics}{dates}{submission}{program}{speakers}{organizers}{venue}</main>
<footer class="footer"><div class="wrap"><div class="footer-top">{wordmark}<div class="footer-links"><a href="#submission">Author information</a><a href="mailto:pguha@iitg.ac.in">Contact</a><a href="https://icvgip.in/2026/">ICVGIP 2026</a></div><a class="to-top" href="#top">Back to top ↑</a></div>
<div class="footer-bottom"><span>ViLaMA 2026 · First Workshop on Vision Language Models and Applications</span><span>KOLKATA, INDIA</span></div></div></footer>
</body></html>'''

missing = set(COPY) - set(USED) - OMITTED_IDS
assert not missing, 'Source copy omitted: ' + ', '.join(sorted(missing))
assert not (set(USED) & OMITTED_IDS), 'User-removed sections must not render.'
assert len(USED) == len(COPY) - len(OMITTED_IDS)
(ROOT / 'index.html').write_text(document, encoding='utf-8')

# TODO: The workshop is an all-day calendar entry until the final session time is confirmed.
calendar = f'''BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//ViLaMA 2026//Workshop//EN\r
CALSCALE:GREGORIAN\r
BEGIN:VEVENT\r
UID:vilama-2026-{WORKSHOP_DATE:%Y%m%d}@workshop.local\r
DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}\r
DTSTART;VALUE=DATE:{WORKSHOP_DATE:%Y%m%d}\r
DTEND;VALUE=DATE:{WORKSHOP_DATE + timedelta(days=1):%Y%m%d}\r
SUMMARY:ViLaMA 2026\r
LOCATION:{CALENDAR_VENUE}\r
DESCRIPTION:First Workshop on Vision Language Models and Applications\r
STATUS:CONFIRMED\r
END:VEVENT\r
END:VCALENDAR\r
'''
(ROOT / 'assets' / 'vilama-2026.ics').write_text(calendar,encoding='utf-8',newline='')
(ROOT / 'assets' / 'favicon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" rx="8" fill="#173c36"/><path d="m8 11 9 19h6l9-19h-6l-6 14-6-14z" fill="#d7e88e"/></svg>')
out = ROOT / 'dist'
out.mkdir(exist_ok=True)
for file in ['index.html','styles.css','script.js']:
    shutil.copy2(ROOT / file,out / file)
shutil.copytree(ROOT / 'assets',out / 'assets',dirs_exist_ok=True)
print(f'Built {len(USED)} retained source paragraphs with approved display changes into index.html and dist/index.html.')
