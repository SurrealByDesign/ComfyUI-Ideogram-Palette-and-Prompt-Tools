"""Batch palette-study generator.

Generates the *same image with different color palettes*: takes one base
ComfyUI workflow (API format) and a set of reference images, extracts a palette
from each reference, injects it into the prompt, and queues one generation per
reference with an identical, locked seed so only the palette varies.

This runs entirely against the ComfyUI HTTP API — it does not need to be a
ComfyUI node and pulls in no GPU/torch dependencies of its own (palette
extraction uses only PIL + numpy + scikit-learn via utils/extract.py).

Usage
-----
Run with the Python that can reach your ComfyUI server, from the package root:

    python tools/palette_batch.py \
        --workflow workflows/ideogram4_studio_api.json \
        --images refs/ \
        --seed 1078 \
        --out out/palette_study

Key options:
    --prompt-node-id   Node id holding the prompt to inject into (auto-detected
                       from the KSampler's positive conditioning if omitted).
    --seed-node-id     Node id holding the seed (auto-detected KSampler if omitted).
    --num-colors       Target palette size (default 8).
    --min-delta-e      Min perceptual distance between kept colors (default 10.0).
    --inject-mode      'json' (set style_description.color_palette in an Ideogram
                       JSON prompt) or 'append' (append a textual palette hint to
                       a plain-text prompt). Default 'auto' picks per prompt.
    --server           ComfyUI base URL (default http://127.0.0.1:8188).

Outputs one PNG per reference image plus a manifest.json mapping each reference
to its extracted palette and output file.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Make the package importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from utils.extract import extract_palette

MAX_GLOBAL_COLORS = 16
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


# --------------------------------------------------------------------------- #
# ComfyUI API helpers
# --------------------------------------------------------------------------- #

def _post_prompt(server: str, graph: dict) -> str:
    payload = json.dumps({"prompt": graph}).encode("utf-8")
    req = urllib.request.Request(
        f"{server}/prompt", data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if data.get("node_errors"):
        raise RuntimeError(f"ComfyUI rejected the prompt: {data['node_errors']}")
    return data["prompt_id"]


def _wait_for(server: str, prompt_id: str, timeout_s: int = 600, poll_s: float = 3.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{server}/history/{prompt_id}", timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if prompt_id in data:
                status = data[prompt_id].get("status", {})
                if status.get("completed") or status.get("status_str") == "success":
                    return data[prompt_id]
                if status.get("status_str") == "error":
                    raise RuntimeError(f"Generation errored: {status}")
        except urllib.error.URLError:
            pass
        time.sleep(poll_s)
    raise TimeoutError(f"Timed out waiting for prompt {prompt_id}")


def _download_images(server: str, history_entry: dict, out_path: Path, stem: str):
    saved = []
    outputs = history_entry.get("outputs", {})
    for node_id, node_out in outputs.items():
        for idx, img in enumerate(node_out.get("images", [])):
            params = urllib.parse.urlencode(
                {"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")}
            )
            with urllib.request.urlopen(f"{server}/view?{params}", timeout=30) as resp:
                blob = resp.read()
            suffix = f"_{idx}" if idx else ""
            dest = out_path / f"{stem}{suffix}.png"
            dest.write_bytes(blob)
            saved.append(str(dest))
    return saved


# --------------------------------------------------------------------------- #
# Graph inspection / mutation
# --------------------------------------------------------------------------- #

def _find_seed_node(graph: dict, explicit_id: str | None) -> str:
    if explicit_id:
        return explicit_id
    for node_id, node in graph.items():
        inputs = node.get("inputs", {})
        if "seed" in inputs or "noise_seed" in inputs:
            return node_id
    raise ValueError("Could not auto-detect a seed node; pass --seed-node-id.")


def _find_prompt_node(graph: dict, explicit_id: str | None, seed_node_id: str) -> str:
    """Trace KSampler.positive -> CLIPTextEncode -> its text source node."""
    if explicit_id:
        return explicit_id

    sampler = graph.get(seed_node_id, {})
    positive = sampler.get("inputs", {}).get("positive")
    if isinstance(positive, list):
        encode_node = graph.get(positive[0], {})
        text_src = encode_node.get("inputs", {}).get("text")
        if isinstance(text_src, list):
            return text_src[0]

    # Fallback: a node with a string 'prompt' input.
    for node_id, node in graph.items():
        if isinstance(node.get("inputs", {}).get("prompt"), str):
            return node_id
    raise ValueError("Could not auto-detect a prompt node; pass --prompt-node-id.")


def _prompt_field_key(node: dict) -> str:
    inputs = node.get("inputs", {})
    for key in ("prompt", "text"):
        if isinstance(inputs.get(key), str):
            return key
    raise ValueError("Prompt node has no string 'prompt' or 'text' input to inject into.")


def _inject_palette(prompt_text: str, palette: list, mode: str) -> str:
    """Return prompt_text with the palette applied. mode: 'json' | 'append' | 'auto'."""
    parsed = None
    if mode in ("json", "auto"):
        try:
            parsed = json.loads(prompt_text)
        except (json.JSONDecodeError, TypeError):
            parsed = None

    if parsed is not None and isinstance(parsed, dict):
        style = parsed.setdefault("style_description", {})
        if isinstance(style, dict):
            style["color_palette"] = palette[:MAX_GLOBAL_COLORS]
            return json.dumps(parsed)

    if mode == "json":
        raise ValueError(
            "Prompt is not Ideogram JSON with a style_description; "
            "use --inject-mode append or fix the prompt node."
        )

    # append / auto-fallback: tack a textual palette hint onto the end.
    hint = "Color palette: " + ", ".join(palette[:MAX_GLOBAL_COLORS]) + "."
    sep = "" if prompt_text.endswith(("\n", " ")) else "\n"
    return f"{prompt_text}{sep}{hint}"


def _collect_images(image_args: list) -> list:
    paths = []
    for arg in image_args:
        p = Path(arg)
        if p.is_dir():
            paths.extend(sorted(c for c in p.iterdir() if c.suffix.lower() in IMAGE_EXTS))
        elif p.is_file():
            paths.append(p)
        else:
            print(f"  ! skipping missing path: {p}", file=sys.stderr)
    return paths


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description="Batch palette-study generator for ComfyUI + Ideogram.")
    ap.add_argument("--workflow", required=True, help="Base workflow JSON in API format.")
    ap.add_argument("--images", required=True, nargs="+", help="Reference image files and/or folders.")
    ap.add_argument("--seed", type=int, required=True, help="Fixed seed shared across all generations.")
    ap.add_argument("--out", default="out/palette_study", help="Output directory.")
    ap.add_argument("--prompt-node-id", default=None)
    ap.add_argument("--seed-node-id", default=None)
    ap.add_argument("--num-colors", type=int, default=8)
    ap.add_argument("--min-delta-e", type=float, default=10.0)
    ap.add_argument("--inject-mode", choices=["auto", "json", "append"], default="auto")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    args = ap.parse_args()

    server = args.server.rstrip("/")
    base_graph = json.loads(Path(args.workflow).read_text(encoding="utf-8"))

    seed_node_id = _find_seed_node(base_graph, args.seed_node_id)
    prompt_node_id = _find_prompt_node(base_graph, args.prompt_node_id, seed_node_id)
    seed_key = "seed" if "seed" in base_graph[seed_node_id]["inputs"] else "noise_seed"
    prompt_key = _prompt_field_key(base_graph[prompt_node_id])
    base_prompt_text = base_graph[prompt_node_id]["inputs"][prompt_key]

    print(f"seed node:   {seed_node_id} (key '{seed_key}')")
    print(f"prompt node: {prompt_node_id} (key '{prompt_key}')")

    images = _collect_images(args.images)
    if not images:
        print("No reference images found.", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest = []

    for n, img_path in enumerate(images, 1):
        print(f"\n[{n}/{len(images)}] {img_path.name}")
        try:
            palette = extract_palette(Image.open(img_path), args.num_colors, args.min_delta_e)
        except Exception as e:
            print(f"  ! extraction failed ({e}); skipping", file=sys.stderr)
            continue
        print(f"  palette: {palette}")

        graph = json.loads(json.dumps(base_graph))  # deep copy per run
        graph[seed_node_id]["inputs"][seed_key] = args.seed
        try:
            graph[prompt_node_id]["inputs"][prompt_key] = _inject_palette(
                base_prompt_text, palette, args.inject_mode
            )
        except ValueError as e:
            print(f"  ! {e}", file=sys.stderr)
            return 1

        try:
            prompt_id = _post_prompt(server, graph)
            print(f"  queued {prompt_id}, waiting...")
            entry = _wait_for(server, prompt_id)
            saved = _download_images(server, entry, out_path, stem=img_path.stem)
        except Exception as e:
            print(f"  ! generation failed ({e}); skipping", file=sys.stderr)
            continue

        print(f"  saved: {saved}")
        manifest.append({"reference": str(img_path), "palette": palette, "outputs": saved})

    (out_path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDone. {len(manifest)} generation(s). Manifest: {out_path / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
