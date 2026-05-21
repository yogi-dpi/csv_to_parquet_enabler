# Changelog

This folder records every released version of `csv_to_parquet_enabler`.

## Convention

- One file per version, named `vMAJOR.MINOR.PATCH.md` (e.g. `v0.2.0.md`).
- Versions follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
  - **MAJOR** — breaking changes (CLI flags removed, output format changed, etc.)
  - **MINOR** — new functionality, backwards-compatible.
  - **PATCH** — bug fixes only, no behavior changes for correct inputs.
- The version in [`pyproject.toml`](../pyproject.toml) must match the latest file in this folder.

## File format

Each file follows the [Keep a Changelog](https://keepachangelog.com/) structure:

```markdown
# vX.Y.Z — YYYY-MM-DD

One-sentence summary of what this release is about.

## Added
- New features or files.

## Changed
- Behavioral or API changes for existing features.

## Fixed
- Bug fixes.

## Removed
- Features, files, or flags taken away.

## Notes
- Anything that doesn't fit above: rationale, migration tips, known issues.
```

Omit any section that has no entries for a given release.

## Index

| Version | Date | Headline |
|---|---|---|
| [v0.2.0](v0.2.0.md) | 2026-05-21 | Installable as a `csv2parquet` console command |
| [v0.1.0](v0.1.0.md) | 2026-05-21 | Initial release — CSV → Parquet + Athena DDL |

## When making future changes

1. Decide the new version number using semver.
2. Bump `version = "..."` in `pyproject.toml`.
3. Create `changelog/vX.Y.Z.md` describing the changes.
4. Add a row to the Index table above.
5. Commit both files together.
