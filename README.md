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

- `index.html`: complete generated page, including all 95 retained source paragraphs.
- `styles.css`: theme tokens, layouts, breakpoints, focus and print styles.
- `script.js`: mobile navigation, current-section tracking, print enhancements.
- `theme.js`: early appearance selection, saved preference, device appearance
  changes and accessible Light / Dark / Auto controls.
- `assets/`: original vector artwork, the three portraits extracted from the
  proposal, favicon and a downloadable calendar event.
- `source-copy.json`: unchanged archive of all 101 nonempty paragraphs extracted
  from the reference Word document, including content omitted from the webpage.
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

The webpage follows the organizer's revised content policy. It omits the Expected
Audience, Publicity Plan and Previous Editions headings and paragraphs: source IDs
`p133`, `p135`, `p138`, `p140`, `p143` and `p145`. Leading numeric section prefixes
are removed only from heading IDs `p008`, `p018`, `p021`, `p038`, `p071`, `p095` and
`p109`. The remaining 95 source paragraphs each appear once, identified by
`data-source-id`, with every other character retained exactly. This includes
punctuation, whitespace, contact details, dates within the proposal, tentative
wording and the original ACM ICPS publication paragraph.

The title's full text is unchanged. Four inline `acronym-highlight` spans emphasize
`Vi`, `La`, `M` and `A` within Vision, Language, Models and Applications. Numbered
section decorations and date indexes are absent. Organizer portraits use a
smaller presentation, and all three complete biographies are always displayed
without a Read biography expander. Abstract: and Motivation and Scope appear as
matching subtitles with both complete texts displayed in full. Splitting the
Abstract: label from its body preserves the original paragraph's combined text,
including the space after the colon. Only the tentative committee retains a
native accessible expander. The separately supplied Springer update remains
visibly subject to approval.

`tools/verify_source.py` independently reopens the original DOCX and validates both
the root page and `dist/index.html`. It enforces exactly these six omissions and
seven heading-prefix changes, exact text for all retained paragraphs, visible
biography markup, the Abstract and Motivation subtitle structure and visibility,
the committee-only expander, the four title highlights, and removal of the omitted
sections and numbered decorations. It also checks contacts, local asset links and internal
anchors, and inventories TODO comments separately from visible status labels.
The results are written to `qa/source-verification.json`. This structural check
does not replace visual review of the rendered page.

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

Semantic landmarks, one primary heading, labeled navigation, a native committee expander,
image descriptions, visible keyboard focus, a skip link, real table row headers,
reduced-motion support and print styles are included. The menu responds to
Escape and closes after section selection. Without JavaScript the navigation
and the committee expander remain usable.

Light / Dark / Auto controls appear in the top utility bar. Auto is the default
and follows the device's appearance, including device-scheduled evening changes.
An explicit selection is remembered in local storage (`vilama-theme`) and synced
between tabs. The small theme script runs before styles to avoid an initial
appearance flash. If storage is unavailable, the choice still works for the
current visit. With JavaScript disabled, CSS follows the device appearance and
the inactive controls stay hidden. Printing always uses light colors. The SVG
illustration has a matching dark palette that follows the page's color scheme.

Run the dependency-free theme behavior checks with `node tools/test_theme.cjs`.

## Deployment

`dist/` is the complete static deployment folder, suitable for any static host.
`.openai/hosting.json` links this checkout to its private Sites preview.
Sharing and access are controlled by the hosting service.
