# ViLaMA 2026 workshop webpage

A complete, responsive, dependency-free HTML, CSS and JavaScript site. Open
`index.html` directly in a browser, or serve `dist/` with any static web server.
No package installation or framework build is required to view the site.

## Local preview

From this folder:

```sh
python3 -m http.server 8000 --directory dist
```

Visit `http://localhost:8000`.

## Files

- `index.html`: complete generated page, including every supplied paragraph.
- `styles.css`: theme tokens, layouts, breakpoints, focus and print styles.
- `script.js`: mobile navigation, current-section tracking, print enhancements.
- `assets/`: original vector artwork, the three portraits extracted from the
  proposal, favicon and a downloadable calendar event.
- `source-copy.json`: exact text extracted from the reference Word document.
- `event-details.json`: the additional dates, formatting information, publication
  update and links supplied by the organizer.
- `tools/build.py`: generates the HTML and copies the runnable site into `dist/`.
- `tools/extract_source.py`: reproducibly extracts the original source copy.
- `tools/verify_source.py`: independently compares the generated page to the DOCX.

## Edit and rebuild

Edit layout in `tools/build.py`, appearance in `styles.css`, interactions in
`script.js`, and organizer updates in `event-details.json`. Then run:

```sh
python3 tools/build.py
python3 tools/verify_source.py
```

The verifier expects the reference Word document in the parent directory. To
use a different location, see `python3 tools/verify_source.py --help`.

The page is also runnable directly after changing its generated HTML, but a
subsequent build will replace those manual edits. Edit the builder to retain
layout changes across builds.

When dates change, update both the verbatim display strings and the corresponding
ISO dates in `event-details.json`. The hero, venue, machine-readable dates and
calendar are derived from those ISO values. The source Word copy is always
retained independently.

## Source text policy

All 101 nonempty Word paragraphs appear once, unchanged, identified by
`data-source-id`. HTML escaping, visual line wrapping, links inside contact
paragraphs, and placement do not alter their text. Motivation, full biographies
and the tentative committee use native accessible expanders; their complete
text is in the HTML and expands when printing. Source spelling, source numbers,
tentative wording and the original ACM ICPS publication paragraph are retained.
The separately supplied Springer update remains visibly subject to approval.

The original DOCX is unchanged. Its organizer photos are retained without image
editing. The hero illustration and small logo are original SVG assets, and
the design uses system fonts with no third-party runtime requests.

## Final details to supply

Each update point is marked with `TODO:` in source comments, never shown as
developer instructions to visitors:

- Workshop-specific OpenReview URL: set `openreview_url` in `event-details.json`.
- Direct Word template URL: set `word_template_url` when one is available.
- Deadline time and timezone.
- Confirmed speaker names, portraits, talk titles and final program.
- Workshop room and accessibility details.
- Updated Springer approval status.

Missing event information is visibly labeled as a placeholder. There are no
invented speakers, partner logos, deadlines, venue rooms or publication approvals.
The calendar uses an all-day date until the session time is finalized.

## Accessibility and responsiveness

Semantic landmarks, one primary heading, labeled navigation, native details,
image descriptions, visible keyboard focus, a skip link, real table row headers,
reduced-motion support and print styles are included. The menu responds to
Escape and closes after section selection. Without JavaScript the navigation
and all expandable content remain usable.

## Deployment

`dist/` is the complete static deployment folder, suitable for any static host.
`.openai/hosting.json` links this checkout to its private Sites preview.
Sharing and access are controlled by the hosting service.
