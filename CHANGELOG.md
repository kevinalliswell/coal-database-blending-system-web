# CHANGELOG


## v1.0.1 (2026-07-02)

### Bug Fixes

- Serve SPA assets on Windows
  ([`154bbda`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/154bbda6bb42d62c267f559970d1637b77e90ce2))

### Continuous Integration

- Drop pip cache from release workflow to fix failing post-step
  ([`389b191`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/389b1913032755c32208c9bb38d22ab70d2d343d))

The release job installs no pip dependencies (python-semantic-release manages its own environment),
  so `cache: pip` on setup-python had nothing to cache and its cache-save post-step failed the whole
  job — every release run showed red despite the release and artifacts succeeding. Removing the
  cache directive makes the pipeline report accurately.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Documentation

- Add architecture, deployment, and user guide; optimize API reference
  ([`a0fdf73`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/a0fdf736ad88709ef395e381dac05c8df1d836f1))

- docs/ARCHITECTURE.md: system architecture (SPA + Flask single container), tech stack, request
  flow, backend layering, data model, NSGA-II overview, frontend architecture, directory tree,
  design trade-offs (with a diagram). - docs/DEPLOYMENT.md: Docker/compose/GHCR, env vars,
  SQLite/MySQL + migrations, local dev, gunicorn + nginx, CI and the semantic-release pipeline. -
  docs/USER_GUIDE.md: per-page operator guide (dashboard, coal DB, smart blending, replacement
  ratio, history), theme toggle and demo mode. - docs/API_REFERENCE.md: rewritten and verified
  against the actual routes and model serializers; every /api endpoint with request/response
  contracts. - README.md: documentation index.

Verified against the codebase via an adversarial review pass.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>


## v1.0.0 (2026-07-01)

### Features

- Rebuild frontend as Vite/React SPA with dual-theme console
  ([`2ac8218`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/2ac8218f391890d3f0a87e95f92bc7d57572ecc3))

Replace the server-rendered Jinja/Bootstrap frontend with a Vite + React + TypeScript single-page
  app (frontend/): a dark "Furnace Console" and light "Foundry Daylight" theme with one-click
  toggle, TanStack Query data layer, ECharts visualizations (interactive Pareto frontier), and a
  mock engine for backend-free demos. Flask now serves the built SPA (frontend/dist) via a catch-all
  route; the /api surface is unchanged.

Adds a full-stack Dockerfile, docker-compose, and extends the release workflow to build the image,
  attach it to the GitHub Release, and push to GHCR.

BREAKING CHANGE: the old server-rendered pages (templates/, static/js, static/css) are removed; page
  routes now serve the single-page app instead of Jinja templates, so deployments must build
  frontend/dist or run the Docker image.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Breaking Changes

- The old server-rendered pages (templates/, static/js, static/css) are removed; page routes now
  serve the single-page app instead of Jinja templates, so deployments must build frontend/dist or
  run the Docker image.


## v0.2.0 (2026-06-29)

### Features

- Add version management, conventional changelog, and CI workflow
  ([#9](https://github.com/kevinalliswell/coal-database-blending-system-web/pull/9),
  [`5776d5f`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/5776d5ff0c67f366c49d7b9965114bd58ab0ffa6))

* feat: add version management, conventional changelog, and CI workflow

- Add app/__version__.py tracking the current version (0.1.4); expose it via app.__init__ so it is
  importable from the package - Add pyproject.toml with python-semantic-release v9 config: reads
  conventional commits (feat→minor, fix→patch, breaking→major) to determine the next version,
  updates __version__.py and CHANGELOG.md, commits the change, creates an annotated tag, and
  publishes a GitHub release — all automatically on every push to main - Replace hand-rolled
  release-on-main.yml bash script with the official
  python-semantic-release/python-semantic-release@v9 action - Add .github/workflows/ci.yml that runs
  the full test suite on every PR targeting main (Python 3.11, pip cache) - Add CHANGELOG.md with
  hand-authored history for v0.1.0–v0.1.4; future entries will be generated automatically

* fix(ci): install pytest via requirements-dev.txt

CI was failing with 'No module named pytest' because pytest is not in requirements.txt. Add
  requirements-dev.txt that pulls in all prod deps plus pytest, and point the CI workflow at it.

---------

Co-authored-by: Claude <noreply@anthropic.com>


## v0.1.4 (2026-06-12)


## v0.1.3 (2026-06-10)


## v0.1.2 (2026-06-10)


## v0.1.1 (2026-04-25)


## v0.1.0 (2026-04-24)

### Bug Fixes

- Restore merged cell borders in export report
  ([`bff6159`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/bff6159222dcaf1fc88c2acdef2355c829cbfbf4))

- Sanitize optimization API JSON responses
  ([`dcffda3`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/dcffda3b7ac290f91c998c737b5f1e99ce918937))

### Chores

- Add PR template and release workflow
  ([`ad91219`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/ad91219e75a2b340a990240f851b9d0bf73ebb6e))

### Documentation

- Add API reference guide
  ([`b22f1f8`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/b22f1f8b335eb9001668e24b16815e32037f36a4))

- Add PCI GA optimization plan
  ([`a1edf9a`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/a1edf9a66ecd586676b6494e85b0af07f6d68340))

### Features

- Align PCI blending optimization with hard constraints
  ([`af8124f`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/af8124fa5ad97ccdb09bc0af92a967832931160d))

- Improve sharing copy and A4 export report layout
  ([`0d35268`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/0d352680a93adf497bcd3af58c690a419dbe5b13))
