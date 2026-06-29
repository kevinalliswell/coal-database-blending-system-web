# CHANGELOG


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
