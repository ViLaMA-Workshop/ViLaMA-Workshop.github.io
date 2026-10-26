# ViLaMA 2026 Workshop Website

Official website for the **First Workshop on Vision Language Models and Applications (ViLaMA 2026)**, held in conjunction with **ICVGIP 2026** at the **Indian Statistical Institute (ISI), Kolkata** on **December 21, 2026**.

🌐 **Live Website**: [https://vilama-workshop.github.io/](https://vilama-workshop.github.io/)

---

## Repository Structure

A lightweight, dependency-free static website hosted on GitHub Pages:

- `index.html` — Workshop webpage (About, Topics, Dates, CFP, Program, Speakers, Organizers, Venue).
- `styles.css` — Responsive layout and light/dark theme styling.
- `script.js` — Mobile menu toggle and section navigation.
- `theme.js` — Instant appearance detection (Light / Dark / Auto).
- `assets/` — Speaker portraits, vector artwork, and icons.
- `.github/workflows/pages.yml` — Automated GitHub Pages deployment workflow.

---

## Making Updates

To update the website:

1. Edit `index.html` (content & links) or `styles.css` (design).
2. Commit and push to `main`:
   ```bash
   git add .
   git commit -m "Update workshop details"
   git push origin main
   ```
GitHub Actions will automatically build and publish the changes to the live website within seconds.
