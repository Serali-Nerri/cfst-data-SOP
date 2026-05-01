#!/usr/bin/env python3
"""Validate one CFST extraction JSON against schema 1.0.0 rules."""

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


SCHEMA_VERSION = "1.0.0"
TOP_LEVEL_KEYS = {"schema_version", "paper", "section_groups"}
PAPER_KEYS = {"ref_info", "validity", "paper_evidence", "paper_shared_defaults", "notes"}
REF_INFO_KEYS = {"title", "authors", "journal", "year", "doi", "language"}
VALIDITY_KEYS = {"is_valid", "reason"}
SECTION_GROUP_KEYS = {"square", "rectangular", "circular", "round_ended"}
GROUP_KEYS = {"has_data", "shared", "specimens", "group_notes"}
SPECIMEN_KEYS = {"specimen_id", "data", "evidence", "quality_flags", "notes"}
SHARED_DEFAULT_KEYS = {"data", "evidence"}
EXTRACTION_DATA_KEYS = {
    "fco_mpa",
    "fc_type",
    "fy_mpa",
    "recycled_aggregate_ratio_percent",
    "geometry",
    "eccentricity",
    "n_exp_kn",
    "material",
    "loading_mode",
    "condition",
}
GEOMETRY_KEYS = {"b_mm", "h_mm", "t_mm", "r0_mm", "l_mm"}
ECCENTRICITY_KEYS = {"e1_mm", "e2_mm", "top_components_mm", "bottom_components_mm"}
ECCENTRICITY_COMPONENT_KEYS = {"x", "y"}
MATERIAL_KEYS = {"steel", "concrete"}
MATERIAL_PART_KEYS = {"type", "note"}
LOADING_MODE_KEYS = {"type", "description"}
CONDITION_KEYS = {"tags", "description"}
EVIDENCE_BLOCK_KEYS = {"source_locations", "field_evidence", "description"}
SOURCE_LOCATION_KEYS = {"page", "table", "figure", "section", "quote"}
FIELD_EVIDENCE_KEYS = {"source_locations", "basis", "derivation", "raw_value", "normalized_value"}

STEEL_TYPES = {"carbon_steel", "stainless_steel", "other"}
CONCRETE_TYPES = {"normal", "UHPC", "recycled_concrete", "other"}
LOADING_MODE_TYPES = {"monotonic", "cyclic", "sustained", "dynamic", "thermal", "other"}
CONDITION_TAGS = {
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
QUALITY_FLAGS = {
    "reported_group_average",
    "figure_derived",
    "formula_derived",
    "text_derived",
    "table_derived",
    "ambiguous_source",
    "unit_converted",
    "partially_unknown",
}
FC_TYPE_PATTERN = re.compile(
    r"^(cube|cube_[0-9]+|cylinder|cylinder_[0-9]+x[0-9]+|prism|prism_[0-9]+x[0-9]+x[0-9]+|unknown|[A-Za-z0-9_\-x]+)$"
)
FC_TYPE_DISALLOWED_SYMBOL_PATTERN = re.compile(r"^(f'?c|fc'|fcu|fck|fcm|fcd)$", re.IGNORECASE)
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


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _roughly_equal(a: float, b: float, tol: float = EPS) -> bool:
    return abs(float(a) - float(b)) <= tol


def _number(value: Any) -> float:
    return float(value)


def _has_3dp(value: float) -> bool:
    return abs(round(float(value), 3) - float(value)) <= 1e-6


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value and "\r" not in value


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


def _validate_nonempty_reason(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not _nonempty_string(value):
        ctx.error(f"`{tag}` must be a non-empty single-line string.")


def _validate_string_list(value: Any, tag: str, ctx: ValidationContext, *, allowed: set[str] | None = None, min_items: int = 0) -> None:
    if not isinstance(value, list):
        ctx.error(f"`{tag}` must be list.")
        return
    if len(value) < min_items:
        ctx.error(f"`{tag}` must contain at least {min_items} item(s).")
    seen: set[str] = set()
    for idx, item in enumerate(value):
        item_tag = f"{tag}[{idx}]"
        if not isinstance(item, str):
            ctx.error(f"`{item_tag}` must be string.")
            continue
        if item != item.strip() or not item.strip():
            ctx.error(f"`{item_tag}` must be a non-empty trimmed string.")
        if allowed is not None and item not in allowed:
            ctx.error(f"`{item_tag}` invalid: {item}.")
        if item in seen:
            ctx.error(f"`{tag}` must not contain duplicates: {item}.")
        seen.add(item)


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


def _validate_source_location(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, SOURCE_LOCATION_KEYS, set(), tag, ctx)
    if "page" in value and value["page"] is not None:
        if not isinstance(value["page"], int) or value["page"] < 1:
            ctx.error(f"`{tag}.page` must be integer >= 1 or null.")
    has_non_page_locator = False
    for key in ("table", "figure", "section", "quote"):
        if key in value:
            _validate_string_or_null(value[key], f"{tag}.{key}", ctx)
            if _nonempty_string(value[key]):
                has_non_page_locator = True
    if not has_non_page_locator:
        ctx.warning(f"`{tag}` should cite a table, figure, section, or original quote; page-only evidence is not sufficient.")


def _validate_field_evidence(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, FIELD_EVIDENCE_KEYS, set(), tag, ctx)
    if "source_locations" in value:
        if not isinstance(value["source_locations"], list):
            ctx.error(f"`{tag}.source_locations` must be list.")
        else:
            for idx, item in enumerate(value["source_locations"]):
                _validate_source_location(item, f"{tag}.source_locations[{idx}]", ctx)
    for key in ("basis", "derivation"):
        if key in value:
            _validate_string_or_null(value[key], f"{tag}.{key}", ctx)
    for key in ("raw_value", "normalized_value"):
        if key in value and value[key] is not None and not isinstance(value[key], (str, int, float)):
            ctx.error(f"`{tag}.{key}` must be string, number, or null.")


def _validate_evidence_block(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, EVIDENCE_BLOCK_KEYS, set(), tag, ctx)
    if "source_locations" in value:
        if not isinstance(value["source_locations"], list):
            ctx.error(f"`{tag}.source_locations` must be list.")
        else:
            for idx, item in enumerate(value["source_locations"]):
                _validate_source_location(item, f"{tag}.source_locations[{idx}]", ctx)
    if "field_evidence" in value:
        if not isinstance(value["field_evidence"], dict):
            ctx.error(f"`{tag}.field_evidence` must be object.")
        else:
            for key, item in value["field_evidence"].items():
                if not isinstance(key, str) or not key.strip():
                    ctx.error(f"`{tag}.field_evidence` keys must be non-empty strings.")
                _validate_field_evidence(item, f"{tag}.field_evidence.{key}", ctx)
    if "description" in value:
        _validate_string_or_null(value["description"], f"{tag}.description", ctx)


def _validate_ref_info(value: Any, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error("`paper.ref_info` must be object.")
        return
    _check_keys(value, REF_INFO_KEYS, REF_INFO_KEYS, "paper.ref_info", ctx)
    for key in ("title", "journal", "doi", "language"):
        if key in value:
            _validate_string_or_null(value[key], f"paper.ref_info.{key}", ctx)
    if "authors" in value:
        _validate_string_list(value["authors"], "paper.ref_info.authors", ctx)
    if "year" in value and value["year"] is not None:
        if not isinstance(value["year"], int) or isinstance(value["year"], bool):
            ctx.error("`paper.ref_info.year` must be integer or null.")
        elif value["year"] < 1800 or value["year"] > 2100:
            ctx.error("`paper.ref_info.year` must be between 1800 and 2100.")


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
        _validate_nonempty_reason(reason, "paper.validity.reason", ctx)
    elif reason is not None:
        _validate_string_or_null(reason, "paper.validity.reason", ctx)
    return is_valid if isinstance(is_valid, bool) else None


def _validate_shared_defaults(value: Any, tag: str, ctx: ValidationContext, *, group_key: str | None = None) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, SHARED_DEFAULT_KEYS, set(), tag, ctx)
    if "data" in value:
        _validate_extraction_data(value["data"], f"{tag}.data", ctx, group_key=group_key, require_complete=False)
    if "evidence" in value:
        _validate_evidence_block(value["evidence"], f"{tag}.evidence", ctx)


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
        ctx.error(f"`{tag}` does not match the schema pattern.")


def _validate_geometry(value: Any, tag: str, ctx: ValidationContext, *, group_key: str | None, require_complete: bool) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, GEOMETRY_KEYS, GEOMETRY_KEYS if require_complete else set(), tag, ctx)
    for key in ("b_mm", "h_mm", "t_mm", "l_mm"):
        if key in value:
            _validate_number(value[key], f"{tag}.{key}", ctx, positive=True)
    if "r0_mm" in value:
        _validate_number(value["r0_mm"], f"{tag}.r0_mm", ctx, minimum=0)

    b = value.get("b_mm")
    h = value.get("h_mm")
    t = value.get("t_mm")
    r0 = value.get("r0_mm")
    if _is_number(b) and _is_number(h) and _number(b) + EPS < _number(h):
        ctx.error(f"`{tag}` must satisfy b_mm >= h_mm.")
    if _is_number(b) and _is_number(h) and _is_number(t) and _number(t) >= min(_number(b), _number(h)) / 2.0:
        ctx.error(f"`{tag}.t_mm` must be smaller than min(b_mm, h_mm)/2.")

    if group_key == "square" and _is_number(b) and _is_number(h) and not _roughly_equal(_number(b), _number(h)):
        ctx.error(f"`{tag}` in square group must satisfy b_mm == h_mm.")
    if group_key == "circular":
        if _is_number(b) and _is_number(h) and not _roughly_equal(_number(b), _number(h)):
            ctx.error(f"`{tag}` in circular group must satisfy b_mm == h_mm.")
        if _is_number(h) and _is_number(r0) and not _roughly_equal(_number(r0), _number(h) / 2.0):
            ctx.error(f"`{tag}.r0_mm` in circular group must equal h_mm/2.")
    if group_key == "round_ended":
        if _is_number(b) and _is_number(h) and not _number(b) > _number(h) + EPS:
            ctx.error(f"`{tag}` in round_ended group must satisfy b_mm > h_mm.")
        if _is_number(h) and _is_number(r0) and not _roughly_equal(_number(r0), _number(h) / 2.0):
            ctx.error(f"`{tag}.r0_mm` in round_ended group must equal h_mm/2.")
    if group_key in {"square", "rectangular"} and _is_number(r0) and _number(r0) > 0:
        ctx.warning(f"`{tag}.r0_mm` is nonzero in a Group A section; ensure notes or field evidence explain rounded corners.")


def _validate_eccentricity_components(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, ECCENTRICITY_COMPONENT_KEYS, set(), tag, ctx)
    for key in ("x", "y"):
        if key in value and value[key] is not None:
            _validate_number(value[key], f"{tag}.{key}", ctx)


def _validate_eccentricity(value: Any, tag: str, ctx: ValidationContext, *, require_complete: bool) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    required = {"e1_mm", "e2_mm"} if require_complete else set()
    _check_keys(value, ECCENTRICITY_KEYS, required, tag, ctx)
    for key in ("e1_mm", "e2_mm"):
        if key in value:
            _validate_number(value[key], f"{tag}.{key}", ctx)
    for key in ("top_components_mm", "bottom_components_mm"):
        if key in value:
            _validate_eccentricity_components(value[key], f"{tag}.{key}", ctx)

    component_pairs = (("e1_mm", "top_components_mm"), ("e2_mm", "bottom_components_mm"))
    for eccentricity_key, component_key in component_pairs:
        eccentricity = value.get(eccentricity_key)
        components = value.get(component_key)
        if not (_is_number(eccentricity) and isinstance(components, dict)):
            continue
        x = components.get("x")
        y = components.get("y")
        if _is_number(x) and _is_number(y):
            magnitude = math.sqrt(_number(x) ** 2 + _number(y) ** 2)
            if not _roughly_equal(abs(_number(eccentricity)), magnitude):
                ctx.warning(f"`{tag}.{eccentricity_key}` does not match sqrt(x^2+y^2) from `{component_key}`.")


def _validate_material_part(value: Any, tag: str, ctx: ValidationContext, *, allowed: set[str]) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, MATERIAL_PART_KEYS, {"type"}, tag, ctx)
    item_type = value.get("type")
    if not isinstance(item_type, str) or item_type not in allowed:
        ctx.error(f"`{tag}.type` invalid: {item_type}.")
    if "note" in value:
        _validate_string_or_null(value["note"], f"{tag}.note", ctx)
    if item_type == "other" and not _nonempty_string(value.get("note")):
        ctx.error(f"`{tag}.note` is required when `{tag}.type` is other.")


def _validate_material(value: Any, tag: str, ctx: ValidationContext, *, require_complete: bool) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, MATERIAL_KEYS, MATERIAL_KEYS if require_complete else set(), tag, ctx)
    if "steel" in value:
        _validate_material_part(value["steel"], f"{tag}.steel", ctx, allowed=STEEL_TYPES)
    if "concrete" in value:
        _validate_material_part(value["concrete"], f"{tag}.concrete", ctx, allowed=CONCRETE_TYPES)


def _validate_loading_mode(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, LOADING_MODE_KEYS, {"type"}, tag, ctx)
    mode_type = value.get("type")
    if not isinstance(mode_type, str) or mode_type not in LOADING_MODE_TYPES:
        ctx.error(f"`{tag}.type` invalid: {mode_type}.")
    if "description" in value:
        _validate_string_or_null(value["description"], f"{tag}.description", ctx)
    if mode_type == "other" and not _nonempty_string(value.get("description")):
        ctx.error(f"`{tag}.description` is required when loading mode type is other.")


def _validate_condition(value: Any, tag: str, ctx: ValidationContext) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, CONDITION_KEYS, {"tags"}, tag, ctx)
    tags = value.get("tags")
    _validate_string_list(tags, f"{tag}.tags", ctx, allowed=CONDITION_TAGS, min_items=1)
    if isinstance(tags, list) and "normal" in tags and len(tags) > 1:
        ctx.warning(f"`{tag}.tags` contains `normal` with other condition tags; verify this is intended.")
    if "description" in value:
        _validate_string_or_null(value["description"], f"{tag}.description", ctx)
    if isinstance(tags, list) and "other" in tags and not _nonempty_string(value.get("description")):
        ctx.error(f"`{tag}.description` is required when condition tags contain other.")


def _validate_extraction_data(
    value: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    group_key: str | None,
    require_complete: bool,
) -> None:
    if not isinstance(value, dict):
        ctx.error(f"`{tag}` must be object.")
        return
    _check_keys(value, EXTRACTION_DATA_KEYS, set(), tag, ctx)

    if "fco_mpa" in value:
        _validate_number(value["fco_mpa"], f"{tag}.fco_mpa", ctx, positive=True)
    elif require_complete:
        ctx.error(f"`{tag}.fco_mpa` is required after inheritance.")

    if "fy_mpa" in value:
        _validate_number(value["fy_mpa"], f"{tag}.fy_mpa", ctx, positive=True)
    elif require_complete:
        ctx.error(f"`{tag}.fy_mpa` is required after inheritance.")

    if "recycled_aggregate_ratio_percent" in value:
        _validate_number(
            value["recycled_aggregate_ratio_percent"],
            f"{tag}.recycled_aggregate_ratio_percent",
            ctx,
            minimum=0.0,
            maximum=100.0,
        )
    elif require_complete:
        ctx.error(f"`{tag}.recycled_aggregate_ratio_percent` is required after inheritance.")

    if "n_exp_kn" in value:
        _validate_number(value["n_exp_kn"], f"{tag}.n_exp_kn", ctx, positive=True)
    elif require_complete:
        ctx.error(f"`{tag}.n_exp_kn` is required after inheritance.")

    if "fc_type" in value:
        _validate_fc_type(value["fc_type"], f"{tag}.fc_type", ctx)
    elif require_complete:
        ctx.error(f"`{tag}.fc_type` is required after inheritance.")

    if "geometry" in value:
        _validate_geometry(value["geometry"], f"{tag}.geometry", ctx, group_key=group_key, require_complete=require_complete)
    elif require_complete:
        ctx.error(f"`{tag}.geometry` is required after inheritance.")

    if "eccentricity" in value:
        _validate_eccentricity(value["eccentricity"], f"{tag}.eccentricity", ctx, require_complete=require_complete)
    elif require_complete:
        ctx.error(f"`{tag}.eccentricity` is required after inheritance.")

    if "material" in value:
        _validate_material(value["material"], f"{tag}.material", ctx, require_complete=require_complete)
    elif require_complete:
        ctx.error(f"`{tag}.material` is required after inheritance.")

    if "loading_mode" in value:
        _validate_loading_mode(value["loading_mode"], f"{tag}.loading_mode", ctx)
    elif require_complete:
        ctx.error(f"`{tag}.loading_mode` is required after inheritance.")

    if "condition" in value:
        _validate_condition(value["condition"], f"{tag}.condition", ctx)
    elif require_complete:
        ctx.error(f"`{tag}.condition` is required after inheritance.")


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


def _shared_data(shared: Any) -> dict[str, Any]:
    if not isinstance(shared, dict):
        return {}
    data = shared.get("data")
    return deepcopy(data) if isinstance(data, dict) else {}


def _effective_data(paper: dict[str, Any], group: dict[str, Any], specimen: dict[str, Any]) -> dict[str, Any]:
    effective: dict[str, Any] = {}
    effective = _deep_merge(effective, _shared_data(paper.get("paper_shared_defaults")))
    effective = _deep_merge(effective, _shared_data(group.get("shared")))
    if isinstance(specimen.get("data"), dict):
        effective = _deep_merge(effective, specimen["data"])
    return effective


def _has_evidence(*blocks: Any) -> bool:
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("description"):
            return True
        if isinstance(block.get("source_locations"), list) and block["source_locations"]:
            return True
        if isinstance(block.get("field_evidence"), dict) and block["field_evidence"]:
            return True
    return False


def _validate_specimen(
    specimen: Any,
    tag: str,
    ctx: ValidationContext,
    *,
    paper: dict[str, Any],
    group: dict[str, Any],
    group_key: str,
) -> str | None:
    if not isinstance(specimen, dict):
        ctx.error(f"`{tag}` must be object.")
        return None
    _check_keys(specimen, SPECIMEN_KEYS, {"specimen_id", "data"}, tag, ctx)

    specimen_id = specimen.get("specimen_id")
    if not _nonempty_string(specimen_id):
        ctx.error(f"`{tag}.specimen_id` must be a non-empty single-line string.")
        specimen_id = None

    if "data" in specimen:
        _validate_extraction_data(specimen["data"], f"{tag}.data", ctx, group_key=group_key, require_complete=False)

    effective = _effective_data(paper, group, specimen)
    _validate_extraction_data(effective, f"{tag}.effective_data", ctx, group_key=group_key, require_complete=True)

    if "evidence" in specimen:
        _validate_evidence_block(specimen["evidence"], f"{tag}.evidence", ctx)
    if not _has_evidence(specimen.get("evidence"), group.get("shared", {}).get("evidence") if isinstance(group.get("shared"), dict) else None, paper.get("paper_evidence")):
        ctx.warning(f"`{tag}` has no specimen, group, or paper evidence block.")

    if "quality_flags" in specimen:
        _validate_string_list(specimen["quality_flags"], f"{tag}.quality_flags", ctx, allowed=QUALITY_FLAGS)
    if "notes" in specimen:
        _validate_string_or_null(specimen["notes"], f"{tag}.notes", ctx)

    return specimen_id if isinstance(specimen_id, str) else None


def _validate_section_group(
    group: Any,
    group_key: str,
    ctx: ValidationContext,
    *,
    paper: dict[str, Any],
    labels: dict[str, str],
) -> int:
    tag = f"section_groups.{group_key}"
    if not isinstance(group, dict):
        ctx.error(f"`{tag}` must be object.")
        return 0
    _check_keys(group, GROUP_KEYS, {"has_data", "shared", "specimens"}, tag, ctx)

    if "has_data" in group and not isinstance(group["has_data"], bool):
        ctx.error(f"`{tag}.has_data` must be boolean.")
    if "shared" in group:
        _validate_shared_defaults(group["shared"], f"{tag}.shared", ctx, group_key=group_key)
    if "group_notes" in group:
        _validate_string_or_null(group["group_notes"], f"{tag}.group_notes", ctx)

    specimens = group.get("specimens")
    if not isinstance(specimens, list):
        ctx.error(f"`{tag}.specimens` must be list.")
        return 0

    if group.get("has_data") is True and not specimens:
        ctx.error(f"`{tag}.has_data=true` requires at least one specimen.")
    if group.get("has_data") is False and specimens:
        ctx.error(f"`{tag}.has_data=false` requires an empty specimens list.")

    for idx, specimen in enumerate(specimens):
        specimen_tag = f"{tag}.specimens[{idx}]"
        label = _validate_specimen(specimen, specimen_tag, ctx, paper=paper, group=group, group_key=group_key)
        if label is not None:
            if label in labels:
                ctx.error(f"Duplicate specimen_id `{label}` in {labels[label]} and {specimen_tag}.")
            labels[label] = specimen_tag
    return len(specimens)


def _validate_paper(value: Any, ctx: ValidationContext) -> tuple[dict[str, Any] | None, bool | None]:
    if not isinstance(value, dict):
        ctx.error("`paper` must be object.")
        return None, None
    _check_keys(value, PAPER_KEYS, {"ref_info", "validity", "paper_evidence"}, "paper", ctx)

    if "ref_info" in value:
        _validate_ref_info(value["ref_info"], ctx)
    is_valid = _validate_validity(value.get("validity"), ctx) if "validity" in value else None
    if "paper_evidence" in value:
        _validate_evidence_block(value["paper_evidence"], "paper.paper_evidence", ctx)
    if "paper_shared_defaults" in value:
        _validate_shared_defaults(value["paper_shared_defaults"], "paper.paper_shared_defaults", ctx)
    if "notes" in value:
        _validate_string_or_null(value["notes"], "paper.notes", ctx)
    return value, is_valid


def validate_payload(
    payload: Any,
    expect_valid: bool | None,
    strict_rounding: bool,
    expect_count: int | None,
) -> tuple[list[str], list[str], int]:
    ctx = ValidationContext(strict_rounding=strict_rounding)

    if not isinstance(payload, dict):
        return ["Top-level JSON must be object."], [], 0

    _check_keys(payload, TOP_LEVEL_KEYS, TOP_LEVEL_KEYS, "payload", ctx)
    if payload.get("schema_version") != SCHEMA_VERSION:
        ctx.error(f"`schema_version` must be `{SCHEMA_VERSION}`.")

    paper, is_valid = _validate_paper(payload.get("paper"), ctx) if "paper" in payload else (None, None)
    if expect_valid is not None and is_valid is not None and is_valid != expect_valid:
        ctx.error(f"`paper.validity.is_valid` expected {expect_valid}, got {is_valid}.")

    total = 0
    labels: dict[str, str] = {}
    section_groups = payload.get("section_groups")
    if not isinstance(section_groups, dict):
        ctx.error("`section_groups` must be object.")
    else:
        _check_keys(section_groups, SECTION_GROUP_KEYS, SECTION_GROUP_KEYS, "section_groups", ctx)
        if paper is not None:
            for group_key in ("square", "rectangular", "circular", "round_ended"):
                if group_key in section_groups:
                    total += _validate_section_group(section_groups[group_key], group_key, ctx, paper=paper, labels=labels)

    if expect_count is not None and total != expect_count:
        ctx.error(f"Specimen total expected {expect_count}, got {total}.")
    if is_valid is True and total == 0:
        ctx.error("`paper.validity.is_valid=true` requires at least one extracted specimen.")
    if is_valid is False and total > 0:
        ctx.error("`paper.validity.is_valid=false` requires all specimen lists to be empty.")

    return ctx.errors, ctx.warnings, total


def main() -> int:
    _assert_sandbox()
    parser = argparse.ArgumentParser(description="Validate single-paper CFST extraction JSON 1.0.0. Requires CFST_SANDBOX=1.")
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
        help="Optional expected total extracted specimen count across all section groups.",
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

    errors, warnings, total = validate_payload(
        payload,
        args.expect_valid,
        args.strict_rounding,
        args.expect_count,
    )

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
