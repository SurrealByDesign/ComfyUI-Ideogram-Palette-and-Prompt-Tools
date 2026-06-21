# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `IdeogramElementBuilder` and `IdeogramElementCollector` nodes for assembling Ideogram 4 `compositional_deconstruction` elements: build per-region element JSON (bbox, description, type, optional palette) and collect up to eight into a complete block, with text-box overlap detection. Includes a `showcase_06_per_element_palettes.json` workflow and README documentation for the per-region palette pipeline.
- A second showcase composite (`assets/garden_courtyard_palettes.png`) demonstrating the same same-seed-and-prompt, palette-swapped technique on a different scene.
- A one-line project tagline and a `assets/social_preview.png` asset for GitHub's repo social preview card.

### Changed
- Aligned the bbox coordinate-order documentation in `nodes/json_validator.py` to `[ymin, xmin, ymax, xmax]`, matching the official Ideogram 4 element schema and the new element nodes (the validator remains order-agnostic — no behavior change).
- Replaced `assets/colorway_study.png` with a new five-variant composite (warm, cool, vibrant, muted, fantasy) built from a forest-path scene chosen for palette-differentiation clarity, in place of the previous test-prompt imagery.
- Reworded internal documentation that referenced an undocumented external "project bible" (in `README.md`, `nodes/json_validator.py`, and `tests/test_extractor.py`) with self-contained explanations.

### Fixed
- Removed `torch`, `numpy`, and `Pillow` from `requirements.txt`. ComfyUI-Manager installs this file automatically, and listing `torch` risked pulling a build mismatched to a user's CUDA/ComfyUI setup and breaking their install; only `scikit-learn` is a genuine extra dependency.

<!--
When cutting a release, move the relevant entries above into a new dated
section below, then leave this Unreleased section with empty category
headers ready for the next round of changes:

## [Unreleased]

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
-->

## [1.0.0] - 2026-06-20

### Added
- Initial public release.
- Palette extraction nodes: frequency-ranked, vibrancy-ranked, masked-region, and per-element.
- Palette blending and manual override nodes.
- Ideogram 4 JSON assembly and validation nodes.
- PNG metadata embed/recover nodes.
- A showcase set of five example workflows.

[Unreleased]: https://github.com/SurrealByDesign/ComfyUI-Ideogram-Palette-and-Prompt-Tools/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SurrealByDesign/ComfyUI-Ideogram-Palette-and-Prompt-Tools/releases/tag/v1.0.0
