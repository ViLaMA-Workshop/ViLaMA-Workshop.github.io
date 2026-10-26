# Publish ViLaMA with GitHub Pages

The prepared repository is `https://github.com/ViLaMA-Workshop/ViLaMA`.
Place this folder's contents at the repository root: `.github/`, `tools/`,
`assets/`, `index.html`, the styles/scripts, JSON files and documentation.
Do not nest everything inside another `vilama-2026/` folder.

## Choose the address

| GitHub owner | Repository name | Default website address |
| --- | --- | --- |
| `ViLaMA-Workshop` | `ViLaMA` (the supplied repository) | `https://vilama-workshop.github.io/ViLaMA/` |
| `ViLaMA-Workshop` | `ViLaMA-Workshop.github.io` | `https://vilama-workshop.github.io/` |
| `ViLaMA` | `ViLaMA.github.io` | `https://vilama.github.io/` |

The exact address `vilama.github.io` requires ownership of the `ViLaMA` account
or organization. Renaming only the current repository cannot give another
account's `github.io` address. Do not put `vilama.github.io` in a `CNAME` file.
A custom domain would need to be a domain the organizers own.

All page assets and internal links use relative URLs, so this site works at
either a repository path or an account's root address without code changes.

## First publication

1. Upload/commit the prepared files to the repository's `main` branch. Include
   `.github/workflows/pages.yml` and `.gitignore`; a workflow hidden inside a
   ZIP file will not run. GitHub Desktop or Git will include these hidden files.
2. Open [Settings → Pages](https://github.com/ViLaMA-Workshop/ViLaMA/settings/pages).
   Under **Build and deployment → Source**, select **GitHub Actions**.
3. Open [Actions](https://github.com/ViLaMA-Workshop/ViLaMA/actions) and select
   **Website CI and Pages**. If the first run happened before Pages was enabled,
   choose **Run workflow → main → Run workflow**, or rerun the failed job.
4. Wait for both **Validate and build** and **Deploy GitHub Pages** to succeed.
   Open the website URL shown by the deployment. For the supplied repository,
   the expected address is `https://vilama-workshop.github.io/ViLaMA/`.
5. Return to **Settings → Pages** and enable **Enforce HTTPS** if it is available
   and not already enabled.

The repository must be eligible for Pages under the account's plan. Public
repositories support Pages on GitHub Free. A private source repository requires
a supported paid plan; repository privacy does not automatically make the
published website private.

No personal access token, custom Actions secret, npm install, or `gh-pages`
branch is required by this workflow. GitHub supplies the deployment token.
Organization policies may require an owner to allow GitHub Actions and the
official actions used in this workflow.

## What CI/CD does

- Pull requests to `main`: build, compare all retained proposal text against
  `source-copy.json`, verify markup/local assets/internal anchors, and run the
  theme behavior tests. Pull requests do not publish.
- Pushes to `main`: perform the same checks, then upload only `dist/` and deploy
  that exact build to GitHub Pages.
- Manual runs on `main`: repeat the checks and deployment.
- A failed build or validation prevents deployment; the last successful site
  remains published.

CI uses explicit archive verification. It does not claim to reopen the Word
document. Organizers can still run direct Word verification locally:

```sh
python3 tools/build.py
python3 tools/verify_source.py --source /path/to/ICVGIP_WorkshopProposal_ViLaMA_2026_V2.docx
```

The original document and local Sites settings are not needed in the GitHub
repository or the published artifact. The text archive and source assets are
needed and should remain committed.

## Make future changes

Edit `tools/build.py` for layout, `styles.css` for appearance, `script.js` or
`theme.js` for behavior, and `event-details.json` for approved event updates.
`index.html` is generated; editing it directly will be overwritten by CI.

Check locally before committing:

```sh
python3 tools/build.py
python3 tools/verify_source.py --archive source-copy.json
node tools/test_theme.cjs
```

Then commit the source changes and push to `main`. CI rebuilds `dist/`, so it
does not need to be committed. If generated or local files were committed in an
older checkout, `.gitignore` alone will not stop tracking them. This command
removes only those paths from Git's index, leaving the files on disk:

```sh
git rm -r --cached --ignore-unmatch dist .openai qa
```

For collaboration, create a branch, open a pull request, wait for the
**Validate and build** check, and merge it into `main`. You may make that check
required through **Settings → Rules → Rulesets** if the repository plan permits.
If `main` is renamed, update the branch filters and `refs/heads/main` conditions
in `.github/workflows/pages.yml`.

## Troubleshooting

- **No workflow appears:** check that `.github/workflows/pages.yml` is at the
  repository root and committed to `main`; confirm Actions is enabled.
- **Pages is not configured:** select **GitHub Actions** in Settings → Pages,
  then rerun the workflow.
- **Build fails:** open the failing step under Actions. Update the approved
  source/markup rather than skipping exact-text checks.
- **404:** use the full `/ViLaMA/` URL for this repository, check that deployment
  succeeded, and allow a few minutes for the first publication.
- **Permission/environment failure:** ask an organization owner to check Actions
  policies and deployment rules for the `github-pages` environment. The workflow
  grants publication permissions only to the deploy job.

## Official documentation

- [GitHub Pages site types and addresses](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [Configure the publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- [Use a custom GitHub Pages workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
