# Contributing

Thanks for considering a contribution. This is a small project maintained
in spare time — keep that in mind when sizing pull requests and expectations
for response time.

## Development setup

1. Clone this repo into a ComfyUI install's `custom_nodes/` directory (see
   [README → Installation](README.md#installation)), or clone it anywhere if
   you only need to run the torch-free tests (see below).
2. Install the one genuine extra dependency:
   ```
   pip install scikit-learn
   ```
3. For anything that touches `IMAGE`/`MASK` tensors, you'll also need
   `torch`, `numpy`, and `Pillow` importable — these ship with ComfyUI, so
   the simplest path is running against ComfyUI's own Python rather than
   installing a separate torch build (see below).

## ComfyUI embedded Python requirement

A standard ComfyUI Windows install ships its own Python at
`ComfyUI\python_embeded\python.exe` (or `python_embeded\python.exe` next to
wherever ComfyUI lives). On Linux/macOS, use whichever Python environment
ComfyUI itself runs under (its venv/conda env). Several tests and one
import path in `tests/test_workflows.py` need `torch` available, and that
Python already has it correctly matched to your GPU/CUDA setup — don't
`pip install torch` into a separate environment for this, you'll likely get
a mismatched build.

## Running tests

Tests are plain scripts (no pytest dependency) — run any of them directly:
```
python tests/test_color_utils.py
```

If you have `pytest` installed, `pytest` (or `pytest tests/`) also works and
runs all 102 test functions across all 14 files. This needs the
`consider_namespace_packages = true` setting in `pytest.ini` — without it,
collection fails with `ImportError: attempted relative import with no known
parent package`, because pytest's package-collection walk tries to import
the repo-root `__init__.py` (ComfyUI's required node-registration entry
point, not a test artifact) and can't build a valid package name for it
(this repo's directory name contains hyphens). `--import-mode=importlib`
alone does not fix this; the `pytest.ini` setting does. `python -m unittest
discover` doesn't error, but silently finds and runs zero tests (these are
plain `assert`-based functions, not `unittest.TestCase` subclasses) — don't
use it.

They split into two groups. The split is by what the test transitively
imports, not just what it imports directly — several of these import a
`nodes/*.py` module that imports `torch` itself, so the test file doesn't
need to mention `torch` to require it.

**Torch-free** — run in any Python with `Pillow`, `numpy`, and
`scikit-learn`:
`test_color_utils.py`, `test_element_builder.py`, `test_json_validator.py`,
`test_palette_to_json.py`, `test_prompt_assembler.py`.

**Require `torch`** (run with ComfyUI's Python — see above):
`test_extractor.py`, `test_masked_palette_extractor.py`,
`test_metadata_embedder.py`, `test_metadata_file_reader.py`,
`test_metadata_reader.py` (its `read()` tests build a real IMAGE tensor),
`test_palette_blend.py`, `test_palette_override.py`,
`test_vibrant_palette_extractor.py`, and `test_workflows.py` (it imports
the full node package, which pulls in `torch` transitively).

If you change anything under `nodes/` or `utils/`, run at minimum the tests
for the file(s) you touched. If you change a workflow JSON under
`workflows/`, run `test_workflows.py`.

`tools/palette_batch.py` isn't unit-tested — it talks to a live ComfyUI
server over HTTP. Test changes to it manually against a running instance.

## Code style expectations

There's no linter/formatter configured, so match the existing conventions
by hand:
- Every node class gets a docstring describing its Inputs and Outputs, in
  the same style as the existing nodes.
- Default to no comments; add one only when the *why* isn't obvious from
  the code (a workaround, a non-obvious constraint).
- Nodes should fail gracefully — never raise out of a node's main function.
  Follow the existing fallback pattern (e.g. a flat gray swatch) rather than
  letting a bad input crash the graph.
- New nodes go under `CATEGORY = "Ideogram/Palette"` and follow the
  `Ideogram<Name>` class-naming convention, registered in `__init__.py`'s
  `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS`.
- Tests follow the existing plain-function-plus-`assert` style with an
  `if __name__ == "__main__":` block — no need to introduce pytest.

## Pull request process

- Keep PRs focused — one logical change per PR is much easier to review
  than a bundle.
- Run the relevant tests locally before opening the PR (see above); note in
  the PR description which ones you ran and which you couldn't (e.g. no
  GPU/ComfyUI available).
- Add an entry to `CHANGELOG.md`'s `[Unreleased]` section describing the
  change, following [Keep a Changelog](https://keepachangelog.com/) style.
- Update `README.md` if you're changing documented behavior, inputs/outputs,
  or adding a node.
- CI (`.github/workflows/tests.yml`) runs automatically on every push and PR
  and covers all 14 test files, split across a torch-free job and a
  torch-required job, via the script-style invocations documented above
  (not `pytest`, even though `pytest` itself now works too — see Running
  Tests). Still report what you ran locally in the PR description — CI is
  a backstop, not a replacement for you actually having run the tests
  yourself.

## Reporting issues

There's no issue template yet, so please include, where applicable:
- ComfyUI version and OS.
- Which node(s) are involved.
- The minimal reproduction: a workflow JSON (or just the node + inputs) and
  what you expected vs. what happened.
- Whether it reproduces with a fresh `custom_nodes` install (rules out a
  conflict with another custom node package).

By contributing, you agree your contribution is licensed under this
project's [MIT License](LICENSE).
