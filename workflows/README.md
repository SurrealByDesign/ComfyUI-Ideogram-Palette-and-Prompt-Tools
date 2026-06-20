# Workflows

Load any of these via ComfyUI's **Workflow → Open** menu. Each one has an
on-canvas `Note` node with usage instructions, and the underlying nodes are
documented in the [main README](../README.md#nodes).

`ShowText|pysssss` nodes (from [ComfyUI-Custom-Scripts](https://github.com/pythongosssss/ComfyUI-Custom-Scripts))
appear in several workflows purely to display raw JSON for inspection — they're
optional and safe to delete if you don't have that package installed.

## Core examples

| File | Description |
| --- | --- |
| [`palette_reference_workflow.json`](palette_reference_workflow.json) | Minimal pipeline: Load Image → Extractor → Override → Palette→Global JSON. |
| [`palette_study_3way_workflow.json`](palette_study_3way_workflow.json) | Three reference images → three palettes, for recoloring the same seed+prompt three ways. |

## Showcase set

A progression from a single extraction up to full pipelines exercising multiple
nodes together. See the [main README](../README.md#showcase-workflows) for the
full breakdown of which nodes each one wires together.

| File | Description |
| --- | --- |
| [`showcase_01_palette_to_prompt_pipeline.json`](showcase_01_palette_to_prompt_pipeline.json) | Flagship: reference image → fully validated, embedded Ideogram 4 prompt. |
| [`showcase_02_blend_content_and_style.json`](showcase_02_blend_content_and_style.json) | Blend a content-reference palette with a style-reference palette. |
| [`showcase_03_vibrant_vs_frequency.json`](showcase_03_vibrant_vs_frequency.json) | Compare frequency ranking against three Vibrant Extractor modes. |
| [`showcase_04_masked_subject_and_global.json`](showcase_04_masked_subject_and_global.json) | Region-accurate per-element palette (masked subject) alongside a global palette. |
| [`showcase_05_embed_recover_roundtrip.json`](showcase_05_embed_recover_roundtrip.json) | Embed a prompt on save, then recover it from the saved PNG by path. |

## Validating changes

[`tests/test_workflows.py`](../tests/test_workflows.py) parses every workflow
here and checks that node types, output signatures, and widget counts match
the installed node classes, and that all links are internally consistent (no
dangling or missing references). Run it with a Python that can import the
package's dependencies (e.g. ComfyUI's embedded Python):

```
python tests/test_workflows.py
```
