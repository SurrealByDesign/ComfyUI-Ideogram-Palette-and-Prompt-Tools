# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `pytest.ini` with `consider_namespace_packages = true`, fixing `pytest`/`pytest tests/` collection, which previously failed with `ImportError: attempted relative import with no known parent package`. Root cause: pytest's package-collection walk tried to import the repo-root `__init__.py` (ComfyUI's node-registration entry point) and couldn't build a valid package name for it because this repo's directory name contains hyphens; `--import-mode=importlib` alone did not fix this, `consider_namespace_packages = true` does. Verified with a clean directory-name A/B test to rule out a false-positive fix. `pytest` now passes all 102 test functions across all 14 files.
- `assets/palette_batch_example.png` and a README example under Palette studies showing a real `tools/palette_batch.py` run: the same forest-path workflow and seed, run once per reference under `tests/test_images/` (logo, monochrome, painting, photograph), each producing a genuinely different extracted palette and recolored output. This was the one previously-untested code path in the project; the run confirmed auto-detection of the seed/prompt nodes, manifest generation, and graceful handling of a degenerate single-color extraction (the monochrome reference) all work correctly end-to-end against a live ComfyUI server.

### Changed
- `CONTRIBUTING.md`'s Running Tests and PR process sections updated to reflect that `pytest` now works (previously documented as actively broken).

<!--
When cutting a release, move the relevant entries above into a new dated
section below, then leave this Unreleased section with empty category
headers ready for the next round of changes:

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
-->

## [1.1.1] - 2026-06-21

### Added
- `.github/workflows/tests.yml` — CI running the torch-free tests on a Python 3.10-3.12 matrix and the torch-required tests with a CI-only CPU `torch` install, plus a Tests status badge in the README.
- Two tests in `test_metadata_reader.py` covering `IdeogramMetadataReader.read()` itself (previously only the private `_lookup_metadata` helper was tested): one demonstrating that a real IMAGE tensor always loses its metadata through the tensor-to-PIL conversion (the README's documented limitation, now actually exercised), and one confirming `read()` degrades gracefully on bad input instead of raising. This moves `test_metadata_reader.py` from the torch-free to the torch-required group, since building a real tensor needs `torch`.
- `dependencies = ["scikit-learn"]` to `pyproject.toml`'s `[project]` table — the registry reads this PEP 621 field directly (not `requirements.txt`), so it was previously showing an empty dependency list for the published package.

### Fixed
- Corrected the torch-free/torch-required test split in `CONTRIBUTING.md` and the new CI workflow. `test_extractor.py`, `test_palette_blend.py`, and `test_palette_override.py` were miscategorized as torch-free — each imports a `nodes/*.py` module that imports `torch` unconditionally, so they need it transitively even though the test file itself never mentions `torch`. The first CI run caught this immediately (it had previously gone unnoticed because every local dev environment used in this project already had torch installed). The split is now empirically verified by running each test with `torch` import-blocked.
- `CONTRIBUTING.md`'s PR process section said "there's no CI configured yet" — stale since the CI workflow above was added. Also documents that bare `pytest` currently fails to collect this repo's tests (a real, reproducible `ImportError` from the root `__init__.py`'s relative imports, confirmed not fixed by `--import-mode=importlib`), so contributors aren't surprised by it.
- The published `v1.1.0` registry artifact didn't match the `v1.1.0` git tag — 3 commits (CI workflow, the test-split fix, and registry publishing setup) landed after the tag without a version bump, so `git checkout v1.1.0` didn't reproduce what was actually live on the registry. This release closes that gap; going forward, `pyproject.toml`'s version is only bumped at the same time as a tag.

## [1.1.0] - 2026-06-21

### Added
- `IdeogramElementBuilder` and `IdeogramElementCollector` nodes for assembling Ideogram 4 `compositional_deconstruction` elements: build per-region element JSON (bbox, description, type, optional palette) and collect up to eight into a complete block, with text-box overlap detection. Includes a `showcase_06_per_element_palettes.json` workflow, a README example image (`assets/element_builder_example.png`) annotating a real scene's per-region bboxes and extracted palettes, and README documentation for the per-region palette pipeline.
- `CONTRIBUTING.md`, covering development setup, the torch-free vs. torch-required test split, the ComfyUI embedded Python requirement, code style conventions, PR process, and issue reporting.
- A second showcase composite (`assets/garden_courtyard_palettes.png`) demonstrating the same same-seed-and-prompt, palette-swapped technique on a different scene.
- A one-line project tagline and a `assets/social_preview.png` asset for GitHub's repo social preview card.
- `.gitattributes` normalizing line endings to LF for new commits.
- A README note stating the actual ComfyUI/Python version this was verified against.

### Changed
- Aligned the bbox coordinate-order documentation in `nodes/json_validator.py` to `[ymin, xmin, ymax, xmax]`, matching the official Ideogram 4 element schema and the new element nodes (the validator remains order-agnostic — no behavior change).
- Replaced `assets/colorway_study.png` with a new five-variant composite (warm, cool, vibrant, muted, fantasy) built from a forest-path scene chosen for palette-differentiation clarity, in place of the previous test-prompt imagery.
- Reworded internal documentation that referenced an undocumented external "project bible" (in `README.md`, `nodes/json_validator.py`, and `tests/test_extractor.py`) with self-contained explanations.
- Added `test_element_builder.py` to the README Testing section and CONTRIBUTING's torch-free test list, and added the element nodes to the unit-tested/pending-live-verification paragraph (both were missed when the nodes were first added).

### Fixed
- Removed `torch`, `numpy`, and `Pillow` from `requirements.txt`. ComfyUI-Manager installs this file automatically, and listing `torch` risked pulling a build mismatched to a user's CUDA/ComfyUI setup and breaking their install; only `scikit-learn` is a genuine extra dependency.

## [1.0.0] - 2026-06-20

### Added
- Initial public release.
- Palette extraction nodes: frequency-ranked, vibrancy-ranked, masked-region, and per-element.
- Palette blending and manual override nodes.
- Ideogram 4 JSON assembly and validation nodes.
- PNG metadata embed/recover nodes.
- A showcase set of five example workflows.

[Unreleased]: https://github.com/SurrealByDesign/ComfyUI-Ideogram-Palette-and-Prompt-Tools/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/SurrealByDesign/ComfyUI-Ideogram-Palette-and-Prompt-Tools/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/SurrealByDesign/ComfyUI-Ideogram-Palette-and-Prompt-Tools/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/SurrealByDesign/ComfyUI-Ideogram-Palette-and-Prompt-Tools/releases/tag/v1.0.0
