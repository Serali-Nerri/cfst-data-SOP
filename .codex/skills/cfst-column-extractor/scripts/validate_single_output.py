#!/usr/bin/env python3
"""Validate one CFST extraction JSON against schema and semantic rules."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


GROUP_ORDER = ("Group_A", "Group_B", "Group_C", "Group_D")

PAPER_KEYS = {
    "ref_info",
    "validity",
    "data_sources",
    "defaults",
    "default_consistency",
    "default_notes",
    "notes",
}
VALIDITY_KEYS = {"is_valid", "reason"}
DATA_SOURCE_KEYS = {"source_id", "type", "name", "description"}
PAPER_DEFAULT_KEYS = {"fco", "fc_type", "loading_mode", "condition", "material"}
DEFAULT_CONSISTENCY_KEYS = {"fco", "fc_type", "loading_mode", "condition", "material"}
DEFAULT_NOTES_KEYS = {"fco", "fc_type", "loading_mode", "condition", "material"}
GROUP_KEYS = {"shared", "specimens", "note"}
DATA_KEYS = {
    "fco",
    "fc_type",
    "fy",
    "r_ratio",
    "b",
    "h",
    "t",
    "r0",
    "L",
    "e1",
    "e2",
    "n_exp",
    "loading_mode",
    "condition",
    "material",
}
SPECIMEN_KEYS = {"specimen_label", "note", *DATA_KEYS}
MATERIAL_KEYS = {"steel", "concrete"}

SOURCE_TYPES = {"table", "figure", "section", "text", "other"}
STEEL_TYPES = {"carbon_steel", "stainless_steel", "other"}
CONCRETE_TYPES = {"normal", "SCC", "UHPC", "UHSC", "recycled_concrete", "other"}
LOADING_MODE_TYPES = {"monotonic", "cyclic", "sustained", "dynamic", "thermal", "other"}
CONDITION_TYPES = {
    "normal",
    "corrosion",
    "freeze_thaw",
    "thermal",
    "long_term",
    "defect",
    "damage",
    "strengthened",
    "other",
}

FC_TYPE_PATTERN = re.compile(
    r"^(cube|cube_[0-9]+|cylinder|cylinder_[0-9]+x[0-9]+|prism|prism_[0-9]+x[0-9]+x[0-9]+|unknown|[A-Za-z0-9_\-x]+)$"
)
FC_TYPE_DISALLOWED_SYMBOL_PATTERN = re.compile(r"^(f'?c|fc'|fcu|fck|fcm|fcd)$", re.IGNORECASE)
ROUNDED_NOTE_PATTERN = re.compile(r"(rounded|round[- ]?corner|corner radius|圆角)", re.IGNORECASE)
LOCAL_NOTE_SOURCE_PATTERN = re.compile(
    r"("
    r"\b(?:source|evidence|quote|quoted|table|figure|fig\.)\b"
    r"|source\s+S\d+\b|\bS\d+\s+(?:reports|states|lists|gives)\b"
    r"|source_id|data_sources"
    r"|derived\s+from|derivation|calculated\s+from|computed\s+from|converted\s+from"
    r"|表\s*\d+|图\s*\d+|来源|证据|引用|引文|原文|推导|换算"
    r")",
    re.IGNORECASE,
)
EPS = 1e-3


class ValidationContext:
    def __init__(self, strict_rounding: bool) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.strict_rounding = strict_rounding

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def _assert_sandbox() -> None:
    if os.environ.get("CFST_SANDBOX") != "1":
        print("[FAIL] This script must run inside worker_sandbox.py (CFST_SANDBOX=1 not set).", file=sys.stderr)
        raise SystemExit(1)


def _as_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _load_schema() -> dict[str, Any]:
    schema_path = Path(__file__).with_name("cfst-extraction-schema.json")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _format_json_path(path: Any) -> str:
    parts = ["payload"]
    for item in path:
        if isinstance(item, int):
            parts[-1] = f"{parts[-1]}[{item}]"
        else:
            parts.append(str(item))
    return ".".join(parts)


def _format_schema_error(error: Any) -> str:
    return f"`{_format_json_path(error.path)}` schema violation: {error.message}"


def validate_schema(payload: Any) -> list[str]:
    """Validate static JSON shape, types, enums, patterns, and ranges."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["`jsonschema` package is required for schema validation."]

    try:
        schema = _load_schema()
    except OSError as exc:
        return [f"Unable to read bundled schema: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"Bundled schema is not valid JSON: {exc}"]

    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"Bundled schema is not a valid Draft 2020-12 schema: {exc}"]

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda item: (tuple(str(part) for part in item.path), tuple(str(part) for part in item.schema_path)),
    )
    return [_format_schema_error(error) for error in errors]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _number(value: Any) -> float:
    return float(value)


def _roughly_equal(a: float, b: float, tol: float = EPS) -> bool:
    return abs(float(a) - float(b)) <= tol


def _has_3dp(value: float) -> bool:
    return abs(round(float(value), 3) - float(value)) <= 1e-6


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value and "\r" not in value


def _note_mentions_rounded(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    if "not rounded" in lowered or "non-rounded" in lowered or "无圆角" in value or "直角" in value:
        return False
    return ROUNDED_NOTE_PATTERN.search(value) is not None


def _check_keys(obj: dict[str, Any], allowed: set[str], required: set[str], tag: str, ctx: ValidationContext) -> None:
    missing = sorted(required - set(obj))
    if missing:
        ctx.error(f"`{tag}` missing keys: {missing}")
    unknown = sorted(set(obj) - allowed)
    if unknown:
        ctx.error(f"`{tag}` has unsupported keys: {unknown}")


def _validate_string_or_null(value: Any, tag: str, ctx: ValidationContext) -> None:
    if value is not None and not isinstance(value, str):
        ctx.error(f"`{tag}` must be string or null.")


def _validate_local_exception_note(value: Any, tag: str, ctx: ValidationContext) -> None:
    _validate_string_or_null(value, tag, ctx)
    if isinstance(value, str) and LOCAL_NOTE_SOURCE_PATTERN.search(value):
        ctx.error(
            f"`{tag}` must only describe a local exception; put source names, quotes, and derivation basis in paper-level fields."
        )


def _validate_nonempty_string(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not _nonempty_string(value):
        ctx.error(f"`{tag}` must be a non-empty single-line string.")


def _validate_trimmed_nonempty_string(value: Any, tag: str, ctx: ValidationContext) -> None:
    if isinstance(value, str) and (value != value.strip() or not _nonempty_string(value)):
        ctx.error(f"`{tag}` must be a non-empty trimmed single-line string.")


def _validate_string_list(value: Any, tag: str, ctx: ValidationContext, *, require_nonempty: bool = False) -> None:
    if not isinstance(value, list):
        ctx.error(f"`{tag}` must be list.")
        return
    if require_nonempty and not value:
        ctx.error(f"`{tag}` must contain at least one item.")
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            ctx.error(f"`{tag}[{idx}]` must be string.")
        elif item != item.strip() or not _nonempty_string(item):
            ctx.error(f"`{tag}[{idx}]` must be a non-empty trimmed single-line string.")


def _validate_number(
    value: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
    check_rounding: bool = True,
) -> None:
    if not _is_number(value):
        ctx.error(f"`{tag}` must be numeric.")
        return
    number = float(value)
    if positive and number <= 0:
        ctx.error(f"`{tag}` must be > 0.")
    if minimum is not None and number < minimum:
        ctx.error(f"`{tag}` must be >= {minimum}.")
    if maximum is not None and number > maximum:
        ctx.error(f"`{tag}` must be <= {maximum}.")
    if check_rounding and not _has_3dp(number):
        message = f"`{tag}` is not rounded to 0.001: {value}"
        if ctx.strict_rounding:
            ctx.error(message)
        else:
            ctx.warning(message)


def _validate_ref_info(value: Any, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        return
    for key in ("title", "journal"):
        if key in value:
            _validate_trimmed_nonempty_string(value[key], f"paper.ref_info.{key}", ctx)
    if "authors" in value:
        _validate_string_list(value["authors"], "paper.ref_info.authors", ctx, require_nonempty=True)


def _validate_validity(value: Any, ctx: ValidationContext) -> bool | None:
    if not isinstance(value, dict):
        ctx.error("`paper.validity` must be object.")
        return None
    _check_keys(value, VALIDITY_KEYS, VALIDITY_KEYS, "paper.validity", ctx)
    is_valid = value.get("is_valid")
    if not isinstance(is_valid, bool):
        ctx.error("`paper.validity.is_valid` must be boolean.")
        is_valid = None
    reason = value.get("reason")
    if is_valid is False:
        _validate_nonempty_string(reason, "paper.validity.reason", ctx)
    elif reason is not None:
        _validate_string_or_null(reason, "paper.validity.reason", ctx)
    return is_valid if isinstance(is_valid, bool) else None


def _validate_data_sources(value: Any, ctx: ValidationContext, *, is_valid: bool | None) -> None:
    if not isinstance(value, list):
        ctx.error("`paper.data_sources` must be list.")
        return
    if is_valid is True and not value:
        ctx.warning("`paper.data_sources` is empty for a valid paper.")
    seen: set[str] = set()
    for idx, item in enumerate(value):
        tag = f"paper.data_sources[{idx}]"
        if not isinstance(item, dict):
            ctx.error(f"`{tag}` must be object.")
            continue
        _check_keys(item, DATA_SOURCE_KEYS, DATA_SOURCE_KEYS, tag, ctx)
        source_id = item.get("source_id")
        if _nonempty_string(source_id):
            if source_id in seen:
                ctx.error(f"Duplicate data source id `{source_id}`.")
            seen.add(source_id)
        elif "source_id" in item:
            ctx.error(f"`{tag}.source_id` must be a non-empty single-line string.")
        source_type = item.get("type")
        if isinstance(source_type, str):
            if source_type not in SOURCE_TYPES:
                ctx.error(f"`{tag}.type` invalid: {source_type}.")
        elif "type" in item:
            ctx.error(f"`{tag}.type` must be string.")
        for key in ("name", "description"):
            if key in item:
                _validate_nonempty_string(item[key], f"{tag}.{key}", ctx)


def _validate_fc_type(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not isinstance(value, str):
        ctx.error(f"`{tag}` must be string.")
        return
    if value != value.strip() or not value:
        ctx.error(f"`{tag}` must be a non-empty trimmed string.")
        return
    if FC_TYPE_DISALLOWED_SYMBOL_PATTERN.fullmatch(value):
        ctx.error(f"`{tag}` must describe the stored strength basis, not a symbol such as fcu/fck/f'c.")
    if FC_TYPE_PATTERN.fullmatch(value) is None:
        ctx.error(f"`{tag}` does not match the validator pattern.")


def _validate_material(
    value: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    note: Any,
    require_other_note: bool = True,
) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, MATERIAL_KEYS, MATERIAL_KEYS, tag, ctx)
    steel = value.get("steel")
    concrete = value.get("concrete")
    if not isinstance(steel, str) or steel not in STEEL_TYPES:
        ctx.error(f"`{tag}.steel` invalid: {steel}.")
    if not isinstance(concrete, str) or concrete not in CONCRETE_TYPES:
        ctx.error(f"`{tag}.concrete` invalid: {concrete}.")
    if require_other_note and (steel == "other" or concrete == "other") and not _nonempty_string(note):
        ctx.warning(f"`{tag}` uses `other`; explain it in the nearest applicable note.")


def _note_for_field(note: Any, field: str) -> Any:
    if isinstance(note, dict):
        return note.get(field)
    return note


def _validate_loading_mode(
    value: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    note: Any,
    require_other_note: bool = True,
) -> None:
    if not isinstance(value, str) or value not in LOADING_MODE_TYPES:
        ctx.error(f"`{tag}` invalid: {value}.")
    elif require_other_note and value == "other" and not _nonempty_string(note):
        ctx.warning(f"`{tag}` is `other`; explain it in the nearest applicable note.")


def _validate_condition(
    value: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    note: Any,
    require_other_note: bool = True,
) -> None:
    if not isinstance(value, str) or value not in CONDITION_TYPES:
        ctx.error(f"`{tag}` invalid: {value}.")
    elif require_other_note and value == "other" and not _nonempty_string(note):
        ctx.warning(f"`{tag}` is `other`; explain it in the nearest applicable note.")


def _validate_data_fields(
    value: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    allowed: set[str],
    required: set[str] | None = None,
    note: Any = None,
    require_other_notes: bool = True,
) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, allowed, required or set(), tag, ctx)
    if "fco" in value:
        _validate_number(value["fco"], f"{tag}.fco", ctx, positive=True)
    if "fy" in value:
        _validate_number(value["fy"], f"{tag}.fy", ctx, positive=True)
    if "r_ratio" in value:
        _validate_number(value["r_ratio"], f"{tag}.r_ratio", ctx, minimum=0.0, maximum=100.0)
    for key in ("b", "h", "t", "L", "n_exp"):
        if key in value:
            _validate_number(value[key], f"{tag}.{key}", ctx, positive=True)
    if "r0" in value:
        _validate_number(value["r0"], f"{tag}.r0", ctx, minimum=0.0)
    for key in ("e1", "e2"):
        if key in value:
            _validate_number(value[key], f"{tag}.{key}", ctx)
    if "fc_type" in value:
        _validate_fc_type(value["fc_type"], f"{tag}.fc_type", ctx)
    if "loading_mode" in value:
        _validate_loading_mode(
            value["loading_mode"],
            f"{tag}.loading_mode",
            ctx,
            note=_note_for_field(note, "loading_mode"),
            require_other_note=require_other_notes,
        )
    if "condition" in value:
        _validate_condition(
            value["condition"],
            f"{tag}.condition",
            ctx,
            note=_note_for_field(note, "condition"),
            require_other_note=require_other_notes,
        )
    if "material" in value:
        _validate_material(
            value["material"],
            f"{tag}.material",
            ctx,
            note=_note_for_field(note, "material"),
            require_other_note=require_other_notes,
        )


def _validate_default_consistency(value: Any, ctx: ValidationContext) -> dict[str, bool]:
    result: dict[str, bool] = {}
    if not isinstance(value, dict):
        ctx.error("`paper.default_consistency` must be object.")
        return result
    _check_keys(value, DEFAULT_CONSISTENCY_KEYS, DEFAULT_CONSISTENCY_KEYS, "paper.default_consistency", ctx)
    for key in DEFAULT_CONSISTENCY_KEYS:
        item = value.get(key)
        if not isinstance(item, bool):
            ctx.error(f"`paper.default_consistency.{key}` must be boolean.")
        else:
            result[key] = item
    return result


def _validate_default_notes(value: Any, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error("`paper.default_notes` must be object.")
        return
    _check_keys(value, DEFAULT_NOTES_KEYS, DEFAULT_NOTES_KEYS, "paper.default_notes", ctx)
    for key in DEFAULT_NOTES_KEYS:
        if key in value:
            _validate_string_or_null(value[key], f"paper.default_notes.{key}", ctx)


def _validate_paper(value: Any, ctx: ValidationContext) -> tuple[dict[str, Any] | None, bool | None]:
    if not isinstance(value, dict):
        ctx.error("`paper` must be object.")
        return None, None
    _check_keys(value, PAPER_KEYS, PAPER_KEYS, "paper", ctx)

    if "ref_info" in value:
        _validate_ref_info(value["ref_info"], ctx)
    is_valid = _validate_validity(value.get("validity"), ctx) if "validity" in value else None
    if "data_sources" in value:
        _validate_data_sources(value["data_sources"], ctx, is_valid=is_valid)
    if "defaults" in value:
        default_notes = value.get("default_notes")
        _validate_data_fields(
            value["defaults"],
            "paper.defaults",
            ctx,
            allowed=PAPER_DEFAULT_KEYS,
            note=default_notes if isinstance(default_notes, dict) else None,
        )
    consistency = _validate_default_consistency(value.get("default_consistency"), ctx) if "default_consistency" in value else {}
    if "default_notes" in value:
        _validate_default_notes(value["default_notes"], ctx)
    if "notes" in value:
        _validate_string_or_null(value["notes"], "paper.notes", ctx)

    defaults = value.get("defaults") if isinstance(value.get("defaults"), dict) else {}
    for key, applies_to_all in consistency.items():
        if applies_to_all and key not in defaults and is_valid is not False:
            ctx.error(f"`paper.default_consistency.{key}=true` requires `paper.defaults.{key}`.")
    return value, is_valid


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        result = deepcopy(base)
        for key, value in override.items():
            if key in result:
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    return deepcopy(override)


def _specimen_data(specimen: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in specimen.items() if key in DATA_KEYS}


def _effective_data(paper: dict[str, Any], group: dict[str, Any], specimen: dict[str, Any]) -> dict[str, Any]:
    effective: dict[str, Any] = {}
    defaults = paper.get("defaults")
    shared = group.get("shared")
    if isinstance(defaults, dict):
        effective = _deep_merge(effective, defaults)
    if isinstance(shared, dict):
        effective = _deep_merge(effective, shared)
    effective = _deep_merge(effective, _specimen_data(specimen))
    return effective


def _values_equal(left: Any, right: Any) -> bool:
    if _is_number(left) and _is_number(right):
        return _roughly_equal(_number(left), _number(right))
    return left == right


def _check_default_overrides(
    data: dict[str, Any],
    tag: str,
    ctx: ValidationContext,
    *,
    paper: dict[str, Any],
    note: Any,
) -> None:
    defaults = paper.get("defaults") if isinstance(paper.get("defaults"), dict) else {}
    consistency = paper.get("default_consistency") if isinstance(paper.get("default_consistency"), dict) else {}
    for key in ("fco", "fc_type", "loading_mode", "condition", "material"):
        if key not in data or key not in defaults:
            continue
        if _values_equal(data[key], defaults[key]):
            continue
        applies_to_all = consistency.get(key)
        if applies_to_all is True:
            ctx.error(f"`{tag}.{key}` overrides `paper.defaults.{key}` even though `paper.default_consistency.{key}=true`.")
        elif applies_to_all is False and not _nonempty_string(note):
            ctx.error(f"`{tag}.{key}` overrides `paper.defaults.{key}`; explain the special case in `note`.")


def _check_group_shared_overrides(data: dict[str, Any], tag: str, ctx: ValidationContext, *, group: dict[str, Any]) -> None:
    shared = group.get("shared") if isinstance(group.get("shared"), dict) else {}
    for key, value in data.items():
        if key not in shared:
            continue
        if _values_equal(value, shared[key]):
            ctx.warning(f"`{tag}.{key}` repeats the same value from group shared data; omit redundant specimen fields.")
        else:
            ctx.error(f"`{tag}.{key}` overrides group shared `{key}`; remove the shared value or move the differing value out of shared.")


def _require_effective_fields(value: dict[str, Any], tag: str, ctx: ValidationContext) -> None:
    for key in ("fco", "fc_type", "fy", "r_ratio", "b", "h", "t", "r0", "L", "e1", "e2", "n_exp", "loading_mode", "condition", "material"):
        if key not in value:
            ctx.error(f"`{tag}.{key}` is required after inheritance.")
    if isinstance(value.get("material"), dict):
        for key in ("steel", "concrete"):
            if key not in value["material"]:
                ctx.error(f"`{tag}.material.{key}` is required after inheritance.")


def _validate_effective_geometry(value: dict[str, Any], tag: str, ctx: ValidationContext, *, group_key: str, note: Any) -> None:
    b = value.get("b")
    h = value.get("h")
    t = value.get("t")
    r0 = value.get("r0")

    if _is_number(b) and _is_number(h) and _number(b) + EPS < _number(h):
        ctx.error(f"`{tag}` must satisfy b >= h.")
    if _is_number(b) and _is_number(h) and _is_number(t) and _number(t) >= min(_number(b), _number(h)) / 2.0:
        ctx.error(f"`{tag}.t` must be smaller than min(b, h)/2.")

    if group_key == "Group_A":
        if _is_number(b) and _is_number(h) and not _roughly_equal(_number(b), _number(h)):
            ctx.error(f"`{tag}` in Group_A must satisfy b == h.")
        if _is_number(h) and _is_number(r0):
            rounded = _note_mentions_rounded(note)
            if rounded and _number(r0) <= 0:
                ctx.error(f"`{tag}.r0` in rounded-corner Group_A must be > 0.")
            if not rounded and _number(r0) != 0:
                ctx.error(f"`{tag}.r0` in non-rounded Group_A must be 0.")
            if _number(r0) > 0 and _number(r0) >= _number(h) / 2.0:
                ctx.error(f"`{tag}.r0` in rounded-corner Group_A must be smaller than h/2.")

    if group_key == "Group_B":
        if _is_number(b) and _is_number(h) and _roughly_equal(_number(b), _number(h)):
            ctx.warning(f"`{tag}` in Group_B has b == h; verify it should not be Group_A.")
        if _is_number(h) and _is_number(r0):
            rounded = _note_mentions_rounded(note)
            if rounded and _number(r0) <= 0:
                ctx.error(f"`{tag}.r0` in rounded-corner Group_B must be > 0.")
            if not rounded and _number(r0) != 0:
                ctx.error(f"`{tag}.r0` in non-rounded Group_B must be 0.")
            if _number(r0) > 0 and _number(r0) >= _number(h) / 2.0:
                ctx.error(f"`{tag}.r0` in rounded-corner Group_B must be smaller than h/2.")

    if group_key == "Group_C":
        if _is_number(b) and _is_number(h) and not _roughly_equal(_number(b), _number(h)):
            ctx.error(f"`{tag}` in Group_C must satisfy b == h.")
        if _is_number(h) and _is_number(r0) and not _roughly_equal(_number(r0), _number(h) / 2.0):
            ctx.error(f"`{tag}.r0` in Group_C must equal h/2.")

    if group_key == "Group_D":
        if _is_number(b) and _is_number(h) and not _number(b) > _number(h) + EPS:
            ctx.error(f"`{tag}` in Group_D must satisfy b > h.")
        if _is_number(h) and _is_number(r0) and not _roughly_equal(_number(r0), _number(h) / 2.0):
            ctx.error(f"`{tag}.r0` in Group_D must equal h/2.")


def _validate_specimen(
    specimen: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    paper: dict[str, Any],
    group: dict[str, Any],
    group_key: str,
    labels: dict[str, str],
) -> None:
    if not isinstance(specimen, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(specimen, SPECIMEN_KEYS, {"specimen_label"}, tag, ctx)

    label = specimen.get("specimen_label")
    if not _nonempty_string(label):
        ctx.error(f"`{tag}.specimen_label` must be a non-empty single-line string.")
    else:
        if label in labels:
            ctx.error(f"Duplicate specimen_label `{label}` in {labels[label]} and {tag}.")
        labels[label] = tag

    if "note" in specimen:
        _validate_local_exception_note(specimen["note"], f"{tag}.note", ctx)

    specimen_note = specimen.get("note")
    group_note = group.get("note") if isinstance(group, dict) else None
    note_for_geometry = " ".join(
        note for note in (group_note, specimen_note) if _nonempty_string(note)
    ) or None
    _validate_data_fields(specimen, tag, ctx, allowed=SPECIMEN_KEYS, required={"specimen_label"}, note=specimen_note)

    data = _specimen_data(specimen)
    _check_default_overrides(data, tag, ctx, paper=paper, note=specimen_note)
    _check_group_shared_overrides(data, tag, ctx, group=group)

    effective = _effective_data(paper, group, specimen)
    effective_tag = f"{tag}.effective_data"
    _require_effective_fields(effective, effective_tag, ctx)
    _validate_data_fields(
        effective,
        effective_tag,
        ctx,
        allowed=DATA_KEYS,
        note=note_for_geometry,
        require_other_notes=False,
    )
    _validate_effective_geometry(effective, effective_tag, ctx, group_key=group_key, note=note_for_geometry)


def _validate_group(
    group: Any,
    group_key: str,
    ctx: ValidationContext,
    *,
    paper: dict[str, Any],
    labels: dict[str, str],
) -> int:
    tag = group_key
    if not isinstance(group, dict):
        ctx.error(f"`{tag}` must be object.")
        return 0
    _check_keys(group, GROUP_KEYS, GROUP_KEYS, tag, ctx)

    if "note" in group:
        _validate_local_exception_note(group["note"], f"{tag}.note", ctx)

    shared = group.get("shared")
    if not isinstance(shared, dict):
        ctx.error(f"`{tag}.shared` must be object.")
        shared = {}
    else:
        _validate_data_fields(shared, f"{tag}.shared", ctx, allowed=DATA_KEYS, note=group.get("note"))
        _check_default_overrides(shared, f"{tag}.shared", ctx, paper=paper, note=group.get("note"))

    specimens = group.get("specimens")
    if not isinstance(specimens, list):
        ctx.error(f"`{tag}.specimens` must be list.")
        return 0

    if not specimens and shared:
        ctx.error(f"`{tag}.shared` must be empty when the group has no specimens.")

    for idx, specimen in enumerate(specimens):
        _validate_specimen(
            specimen,
            f"{tag}.specimens[{idx}]",
            ctx,
            paper=paper,
            group=group,
            group_key=group_key,
            labels=labels,
        )
    return len(specimens)


def validate_semantics(
    payload: Any,
    expect_valid: bool | None,
    strict_rounding: bool,
    expect_count: int | None,
) -> tuple[list[str], list[str], int]:
    ctx = ValidationContext(strict_rounding=strict_rounding)

    if not isinstance(payload, dict):
        return [], [], 0

    paper, is_valid = _validate_paper(payload.get("paper"), ctx) if "paper" in payload else (None, None)
    if expect_valid is not None and is_valid is not None and is_valid != expect_valid:
        ctx.error(f"`paper.validity.is_valid` expected {expect_valid}, got {is_valid}.")

    total = 0
    labels: dict[str, str] = {}
    if paper is not None:
        for group_key in GROUP_ORDER:
            if group_key in payload:
                total += _validate_group(payload[group_key], group_key, ctx, paper=paper, labels=labels)

    if expect_count is not None and total != expect_count:
        ctx.error(f"Specimen total expected {expect_count}, got {total}.")
    if is_valid is True and total == 0:
        ctx.error("`paper.validity.is_valid=true` requires at least one extracted specimen.")
    if is_valid is False and total > 0:
        ctx.error("`paper.validity.is_valid=false` requires all specimen lists to be empty.")

    return ctx.errors, ctx.warnings, total


def validate_payload(
    payload: Any,
    expect_valid: bool | None,
    strict_rounding: bool,
    expect_count: int | None,
) -> tuple[list[str], list[str], int]:
    """Validate payload through the same schema and semantic checks as the CLI."""
    schema_errors = validate_schema(payload)
    semantic_errors, warnings, total = validate_semantics(
        payload,
        expect_valid,
        strict_rounding,
        expect_count,
    )
    return schema_errors + semantic_errors, warnings, total


def main() -> int:
    _assert_sandbox()
    parser = argparse.ArgumentParser(description="Validate single-paper CFST extraction JSON 2.0.0-draft. Requires CFST_SANDBOX=1.")
    parser.add_argument("--json-path", required=True, help="Path to extraction JSON file.")
    parser.add_argument(
        "--expect-valid",
        default=None,
        type=_as_bool,
        help="Optional expected value for `paper.validity.is_valid` (true/false).",
    )
    parser.add_argument(
        "--strict-rounding",
        action="store_true",
        help="Fail when extracted numeric fields are not rounded to 0.001.",
    )
    parser.add_argument(
        "--expect-count",
        type=int,
        default=None,
        help="Optional expected total extracted specimen count across all groups.",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path)
    if not json_path.exists():
        print(f"[FAIL] JSON file not found: {json_path}")
        return 1

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[FAIL] Invalid JSON: {exc}")
        return 1

    schema_errors = validate_schema(payload)
    semantic_errors, warnings, total = validate_semantics(
        payload,
        args.expect_valid,
        args.strict_rounding,
        args.expect_count,
    )
    errors = schema_errors + semantic_errors

    print(f"[INFO] Extracted CFST specimen count: {total}")
    if warnings:
        print("[WARN] Validation warnings:")
        for msg in warnings:
            print(f"- {msg}")

    if errors:
        print("[FAIL] Validation errors:")
        for msg in errors:
            print(f"- {msg}")
        return 1

    print("[OK] Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
