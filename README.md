# ViLaMA 2026 Workshop Website

Official website for the **First Workshop on Vision Language Models and Applications (ViLaMA 2026)**, held in conjunction with **ICVGIP 2026** at the **Indian Statistical Institute (ISI), Kolkata** on **December 21, 2026**.

Website URL: **[https://vilama-workshop.github.io/ViLaMA/](https://vilama-workshop.github.io/ViLaMA/)**

---

## Structure

This is a clean, static, dependency-free website ready to host directly on GitHub Pages:

- `index.html`: Complete workshop webpage (overview, topics, dates, CFP, schedule, speakers, organizers, venue).
- `styles.css`: Responsive typography, layout, CSS variables, and light/dark theme styles.
- `script.js`: Navigation menu toggle, active section tracking, and accessibility utilities.
- `theme.js`: Instant appearance detection (Light / Dark / Auto) without layout flash.
- `assets/`: Vector artwork, speaker portraits, icons, and calendar invite (`vilama-2026.ics`).

---

## Deployment & CI/CD

The website is continuously deployed to GitHub Pages using GitHub Actions (`.github/workflows/pages.yml`).

- Every push to the `main` branch automatically deploys the latest version to GitHub Pages.
- To edit any content or appearance, edit `index.html` or `styles.css` directly and push to `main`.
