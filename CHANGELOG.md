# Changelog

All notable changes to this project are documented in this file.
Starting from v0.1.5, releases and changelog entries are generated automatically by
[python-semantic-release](https://python-semantic-release.readthedocs.io/) from
[Conventional Commits](https://www.conventionalcommits.org/).

<!-- next-version-start -->
<!-- next-version-end -->

## [0.1.4] – 2026-06-11

### Added

- Add optimization and replacement ratio history persistence — DB-backed history
  for blending optimization and replacement ratio calculations, history pages with
  navbar dropdown, new Alembic migration
  ([bc54f1c](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/bc54f1c))

### Fixed

- Export route for optimization history now reads from DB instead of removed
  file-based history directory; inject constraints into exported Excel report
- Defensive `_loads_json`, `_safe_float`, and `or {}` guards across history models
  and parameter-summary helpers

## [0.1.3] – 2026-04-30

### Added

- NSGA-II Pareto blending optimization with early stopping — multi-objective
  optimizer generating a Pareto front of candidate solutions with a recommended
  solution surfaced to the UI
  ([c35466f](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/c35466f))

## [0.1.2] – 2026-04-25

### Fixed

- Review findings from PR #5 — various correctness and robustness fixes
  ([0ec7b3b](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/0ec7b3b))

## [0.1.1] – 2026-04-24

### Changed

- Refine smart blending frontend workflow — improved UI interaction and result
  display
  ([81244d4](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/81244d4))

## [0.1.0] – 2026-04-24

Initial release.

### Added

- PCI blending optimization with genetic algorithm and hard constraints
- A4 export report layout (Excel) for blending results
- Replacement ratio (theory & actual) calculation API and UI
- Coal data management (CSV upload, database storage)
- PR template and release-on-main CI workflow
- API reference documentation

### Fixed

- Merged cell borders in export report
- Sanitized optimization API JSON responses (NaN/Inf handling)
