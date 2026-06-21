# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- A second showcase composite (`assets/garden_courtyard_palettes.png`) demonstrating the same same-seed-and-prompt, palette-swapped technique on a different scene.
- A one-line project tagline and a `assets/social_preview.png` asset for GitHub's repo social preview card.

### Changed
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
