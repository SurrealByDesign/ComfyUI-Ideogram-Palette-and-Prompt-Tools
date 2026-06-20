"""Tests that every workflow JSON under workflows/ is structurally valid and
stays in sync with the node classes it wires together.

Catches the failure mode that bit the showcase workflows during manual
authoring: a node's outputs, widget count, or input names drifting from the
node module after an edit. Requires ComfyUI's runtime (torch et al.) on
sys.path to import the node package, so this is meant to be run with the
embedded/ComfyUI Python rather than a bare venv.
"""

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ROOT / "workflows"

sys.path.insert(0, str(ROOT.parent))
_PKG = importlib.import_module(ROOT.name)
NODE_CLASS_MAPPINGS = _PKG.NODE_CLASS_MAPPINGS

# Connection-typed slots are real wires (IMAGE/MASK/...), never widgets.
CONNECTION_TYPES = {"IMAGE", "MASK", "LATENT", "MODEL", "CLIP", "VAE", "CONDITIONING", "CONTROL_NET"}

# Non-package node types used by the example workflows, with their known
# output signature. "Note" and "MarkdownNote" are core frontend-only nodes
# with no Python class to introspect (no outputs, no widget count to check).
CORE_NODE_OUTPUTS = {
    "LoadImage": [("IMAGE", "IMAGE"), ("MASK", "MASK")],
    "PreviewImage": [],
    "ShowText|pysssss": [("STRING", "STRING")],
    "Note": None,
    "MarkdownNote": None,
}


def _all_workflow_paths():
    return sorted(WORKFLOWS_DIR.glob("*.json"))


def _node_param_spec(node_type):
    """Return (output_pairs, widget_param_names, all_param_names) for a package node type."""
    cls = NODE_CLASS_MAPPINGS[node_type]
    input_types = cls.INPUT_TYPES()
    params = []
    for section in ("required", "optional"):
        for name, value in input_types.get(section, {}).items():
            param_type = value[0] if not isinstance(value[0], list) else "COMBO"
            meta = value[1] if len(value) > 1 and isinstance(value[1], dict) else {}
            params.append((name, param_type, bool(meta.get("forceInput", False))))

    outputs = list(zip(cls.RETURN_NAMES, cls.RETURN_TYPES))
    widget_names = [p[0] for p in params if p[1] not in CONNECTION_TYPES and not p[2]]
    all_names = [p[0] for p in params]
    return outputs, widget_names, all_names


def _is_ui_graph(data):
    """True for litegraph UI-export workflows (have a top-level "nodes" list);
    False for API-format exports (e.g. the gitignored *_api.json), which use a
    different shape entirely and are out of scope for this check."""
    return isinstance(data.get("nodes"), list)


def _check_workflow(path):
    """Returns a list of error strings (empty list = valid) for one workflow file."""
    errors = []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not _is_ui_graph(data):
        return []
    nodes = {n["id"]: n for n in data["nodes"]}
    links = {link[0]: link for link in data.get("links", [])}

    if data["nodes"] and data["last_node_id"] < max(nodes):
        errors.append(f"last_node_id {data['last_node_id']} is below max node id {max(nodes)}")
    if links and data["last_link_id"] < max(links):
        errors.append(f"last_link_id {data['last_link_id']} is below max link id {max(links)}")

    produced, consumed = set(), set()
    for node in data["nodes"]:
        for output in node.get("outputs", []) or []:
            for link_id in output.get("links") or []:
                produced.add(link_id)
                if link_id not in links:
                    errors.append(f"node {node['id']} output {output['name']!r} references missing link {link_id}")
        for inp in node.get("inputs", []) or []:
            link_id = inp.get("link")
            if link_id is not None:
                consumed.add(link_id)
                if link_id not in links:
                    errors.append(f"node {node['id']} input {inp['name']!r} references missing link {link_id}")

    for link_id, (_id, src, src_slot, dst, dst_slot, link_type) in links.items():
        if src not in nodes:
            errors.append(f"link {link_id} source node {src} does not exist")
            continue
        if dst not in nodes:
            errors.append(f"link {link_id} destination node {dst} does not exist")
            continue
        src_outputs = nodes[src].get("outputs", []) or []
        dst_inputs = nodes[dst].get("inputs", []) or []
        if src_slot >= len(src_outputs):
            errors.append(f"link {link_id} source slot {src_slot} out of range on node {src}")
        elif link_id not in (src_outputs[src_slot].get("links") or []):
            errors.append(f"link {link_id} not listed on node {src} output slot {src_slot}")
        elif src_outputs[src_slot].get("type") != link_type:
            errors.append(f"link {link_id} type {link_type!r} != source output type {src_outputs[src_slot].get('type')!r}")
        if dst_slot >= len(dst_inputs):
            errors.append(f"link {link_id} destination slot {dst_slot} out of range on node {dst}")
        elif dst_inputs[dst_slot].get("link") != link_id:
            errors.append(f"link {link_id} not referenced by node {dst} input slot {dst_slot}")
        elif dst_inputs[dst_slot].get("type") != link_type:
            errors.append(f"link {link_id} type {link_type!r} != destination input type {dst_inputs[dst_slot].get('type')!r}")
        if link_id not in produced:
            errors.append(f"link {link_id} is never produced by any output")
        if link_id not in consumed:
            errors.append(f"link {link_id} is never consumed by any input")

    for node in data["nodes"]:
        node_type = node["type"]
        if node_type in CORE_NODE_OUTPUTS:
            expected_outputs = CORE_NODE_OUTPUTS[node_type]
            if expected_outputs is not None:
                actual = [(o["name"], o["type"]) for o in node.get("outputs", []) or []]
                if actual != expected_outputs:
                    errors.append(f"node {node['id']} ({node_type}) outputs {actual} != expected {expected_outputs}")
            continue

        if node_type not in NODE_CLASS_MAPPINGS:
            errors.append(f"node {node['id']} has unknown type {node_type!r}")
            continue

        outputs, widget_names, all_param_names = _node_param_spec(node_type)
        actual_outputs = [(o["name"], o["type"]) for o in node.get("outputs", []) or []]
        if actual_outputs != outputs:
            errors.append(f"node {node['id']} ({node_type}) outputs {actual_outputs} != class spec {outputs}")

        widgets_values = node.get("widgets_values", []) or []
        if len(widgets_values) != len(widget_names):
            errors.append(
                f"node {node['id']} ({node_type}) has {len(widgets_values)} widgets_values, "
                f"expected {len(widget_names)} ({widget_names})"
            )

        for inp in node.get("inputs", []) or []:
            if inp["name"] not in all_param_names:
                errors.append(f"node {node['id']} ({node_type}) has input {inp['name']!r} not in INPUT_TYPES")

    return errors


def test_all_workflows_are_valid_json():
    for path in _all_workflow_paths():
        json.loads(path.read_text(encoding="utf-8"))


def test_showcase_workflows_have_no_errors():
    """The hand-authored showcase_*.json files must be fully consistent --
    no dangling links, no drifted node signatures."""
    for path in _all_workflow_paths():
        if not path.name.startswith("showcase_"):
            continue
        errors = _check_workflow(path)
        assert not errors, f"{path.name}:\n  " + "\n  ".join(errors)


def test_at_least_one_showcase_workflow_present():
    showcase_paths = [p for p in _all_workflow_paths() if p.name.startswith("showcase_")]
    assert len(showcase_paths) >= 1


if __name__ == "__main__":
    test_all_workflows_are_valid_json()
    print("all_workflows_are_valid_json: OK")

    any_failures = False
    for path in _all_workflow_paths():
        errors = _check_workflow(path)
        label = "OK" if not errors else "FAIL"
        print(f"{label}: {path.name}")
        for error in errors:
            print(f"    - {error}")
        if errors and path.name.startswith("showcase_"):
            any_failures = True

    test_at_least_one_showcase_workflow_present()
    print("at_least_one_showcase_workflow_present: OK")

    if any_failures:
        print("\nFAILED: one or more showcase workflows have structural errors.")
        sys.exit(1)
    print("\nAll workflow tests passed.")
