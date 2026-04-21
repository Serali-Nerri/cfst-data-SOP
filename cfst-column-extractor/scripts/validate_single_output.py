#!/usr/bin/env python3
"""Validate one CFST extraction JSON against schema-v2.3 rules.

This strict skill variant requires the validator to run inside worker_sandbox.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal Python envs
    yaml = None


def _assert_sandbox() -> None:
    if os.environ.get("CFST_SANDBOX") != "1":
        print("[FAIL] This script must run inside worker_sandbox.py (CFST_SANDBOX=1 not set).", file=sys.stderr)
        raise SystemExit(1)


EPS = 1e-3
SCHEMA_VERSION = "cfst-paper-extractor-v2.3"

TOP_LEVEL_KEYS = {
    "schema_version",
    "paper_id",
    "is_valid",
    "is_ordinary_cfst",
    "reason",
    "ordinary_filter",
    "ref_info",
    "paper_level",
    "shared_context",
    "series_definitions",
    "Group_A",
    "Group_B",
    "Group_C",
}

SPECIMEN_REQUIRED_KEYS = {
    "ref_no",
    "specimen_label",
    "is_ordinary",
    "ordinary_exclusion_reasons",
    "fc_value",
    "fy",
    "fcy150",
    "r_ratio",
    "b",
    "h",
    "t",
    "r0",
    "L",
    "e1",
    "e2",
    "n_exp",
    "source_evidence",
}

ROW_CONTEXT_KEYS = {
    "section_shape",
    "loading_mode",
    "loading_pattern",
    "boundary_condition",
    "fc_type",
    "fc_basis",
    "steel_type",
    "concrete_type",
    "material_modifiers",
}

INHERITABLE_CONTEXT_KEYS = ROW_CONTEXT_KEYS | {"test_temperature", "loading_regime"}

SPECIMEN_OPTIONAL_KEYS = ROW_CONTEXT_KEYS | {
    "reported_group_label",
    "replicate_index",
    "quality_flags",
    "series_id",
    "context_overrides",
    "specimen_note",
}

SERIES_DEFINITION_KEYS = {"series_id", "shared_context", "description", "notes"}
CONTEXT_KEYS = INHERITABLE_CONTEXT_KEYS

NUMERIC_FIELDS = {"fc_value", "fy", "r_ratio", "b", "h", "t", "r0", "L", "e1", "e2", "n_exp"}
NULLABLE_NUMERIC_FIELDS = {"fcy150"}

SECTION_SHAPES = {
    "square",
    "rectangular",
    "circular",
    "elliptical",
    "round-ended",
    "obround",
}
PAPER_LOADING_MODES = {"axial", "eccentric", "mixed", "unknown"}
ROW_LOADING_MODES = {"axial", "eccentric", "unknown"}
TEST_TEMPERATURES = {"ambient", "elevated", "post_fire", "unknown"}
LOADING_REGIMES = {"static", "dynamic", "impact", "unknown"}
LOADING_PATTERNS = {"monotonic", "cyclic", "repeated", "mixed", "unknown"}
ROW_LOADING_PATTERNS = {"monotonic", "cyclic", "repeated", "unknown"}
FC_BASIS_ALLOWED = {"cube", "cylinder", "prism", "unknown"}
STEEL_TYPES = {"carbon_steel", "stainless_steel", "other", "unknown"}
CONCRETE_TYPES = {
    "normal",
    "high_strength",
    "lightweight",
    "recycled",
    "self_consolidating",
    "alkali_activated",
    "geopolymer",
    "expansive",
    "uhpc",
    "other",
    "unknown",
}
GROUP_TO_SHAPES = {
    "Group_A": {"square", "rectangular"},
    "Group_B": {"circular"},
    "Group_C": {"elliptical", "round-ended", "obround"},
}
ORDINARY_ALLOWED_SHAPES = {"square", "rectangular", "circular", "round-ended"}
ORDINARY_ALLOWED_CONCRETE_TYPES = {
    "normal",
    "high_strength",
    "recycled",
    "lightweight",
    "self_consolidating",
    "alkali_activated",
    "geopolymer",
    "expansive",
}
ORDINARY_ALLOWED_SPECIAL_FACTORS = {
    "high_strength_concrete",
    "lightweight_concrete",
    "recycled_aggregate",
    "self_consolidating_concrete",
    "alkali_activated_concrete",
    "geopolymer_concrete",
    "expansive_concrete",
}

NON_ORDINARY_MATERIAL_MODIFIERS = {
    "rubber_concrete",
    "reactive_powder",
    "fiber_reinforced",
    "polymer_modified",
    "foamed_concrete",
    "other_modified_concrete",
}

ALKALI_ACTIVATED_FAMILY_MODIFIERS = {
    "alkali_activated",
    "alkali_activated_slag",
    "alkali_activated_fly_ash",
    "alkali_activated_metakaolin",
    "alkali_activated_calcined_clay",
    "alkali_activated_natural_pozzolan",
    "alkali_activated_blend",
    "alkali_activated_hybrid",
}
GEOPOLYMER_FAMILY_MODIFIERS = {
    "geopolymer",
    "fly_ash_geopolymer",
    "slag_geopolymer",
    "metakaolin_geopolymer",
    "calcined_clay_geopolymer",
    "natural_pozzolan_geopolymer",
    "blended_geopolymer",
}
EXPANSIVE_FAMILY_MODIFIERS = {
    "expansive_concrete",
    "shrinkage_compensating_concrete",
    "self_stressing_concrete",
    "type_k_expansive",
    "type_m_expansive",
    "type_s_expansive",
    "calcium_sulfoaluminate_expansive",
    "cao_expansive",
    "mgo_expansive",
    "composite_expansive",
}
ALL_KNOWN_MATERIAL_MODIFIERS = (
    NON_ORDINARY_MATERIAL_MODIFIERS
    | ALKALI_ACTIVATED_FAMILY_MODIFIERS
    | GEOPOLYMER_FAMILY_MODIFIERS
    | EXPANSIVE_FAMILY_MODIFIERS
)

FC_TYPE_ALLOWED_SHAPE_ONLY = {"cube", "cylinder", "prism", "unknown"}
FC_TYPE_SIZED_PATTERN = re.compile(
    r"^(cube|cylinder|prism)\s+\d+(\.\d+)?(?:\s*[x×*]\s*\d+(\.\d+)?){0,2}\s*(mm)?$",
    re.IGNORECASE,
)
FC_TYPE_DISALLOWED_SYMBOL_PATTERN = re.compile(r"\b(f'?c|fc'|fcu|fck|fcm|fcd)\b", re.IGNORECASE)
GROUP_AVERAGE_HINT_PATTERN = re.compile(r"(group\s*average|average|avg|mean|平均|均值)", re.IGNORECASE)
PAGE_LOCATOR_PATTERN = re.compile(r"(?:\bpage\b|页)", re.IGNORECASE)
SOURCE_LOCATOR_PATTERN = re.compile(
    r"(?:\btable\b|\bfig\b|\bfigure\b|\btext\s+section\b|\btext\b|\bsection\b|表|图|正文|第?\s*[0-9一二三四五六七八九十]+(?:\.[0-9]+)*\s*节)",
    re.IGNORECASE,
)
SCRATCH_DECISION_KEYS = {
    "label",
    "section_shape",
    "steel_type",
    "concrete_type",
    "loading_pattern",
    "test_temperature",
    "loading_regime",
    "durability_conditioning",
    "member_modifiers",
    "material_modifiers",
    "is_ordinary",
    "exclusion_reasons",
}

SCRATCH_DURABILITY_CONDITIONING = {
    "fire_exposure",
    "corrosion_conditioning",
    "freeze_thaw_conditioning",
    "other_durability_conditioning",
}
SCRATCH_MEMBER_MODIFIERS = {
    "strengthened_section",
    "confinement_device",
}


def _as_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _roughly_equal(a: float, b: float, tol: float = EPS) -> bool:
    return abs(float(a) - float(b)) <= tol


def _has_3dp(value: float) -> bool:
    return abs(round(float(value), 3) - float(value)) <= 1e-6


def _has_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 for ch in value)


def _canonical_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _validate_canonical_string(
    value: Any,
    tag: str,
    errors: list[str],
    *,
    allow_null: bool = False,
) -> str | None:
    if value is None:
        if allow_null:
            return None
        errors.append(f"`{tag}` must be string.")
        return None
    if not isinstance(value, str):
        errors.append(f"`{tag}` must be string.")
        return None
    normalized = value.strip()
    if not normalized:
        errors.append(f"`{tag}` must be non-empty.")
        return None
    if value != normalized:
        errors.append(f"`{tag}` must not have leading or trailing whitespace.")
    return normalized


def _validate_string_list(value: Any, tag: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"`{tag}` must be list.")
        return
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"`{tag}[{idx}]` must be string.")
            continue
        if item != item.strip():
            errors.append(f"`{tag}[{idx}]` must not have leading or trailing whitespace.")


def _validate_nonempty_line(value: Any, tag: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"`{tag}` must be string.")
        return
    if not value.strip():
        errors.append(f"`{tag}` must be non-empty.")
    if "\n" in value or "\r" in value:
        errors.append(f"`{tag}` must be single-line.")
    if _has_control_chars(value):
        errors.append(f"`{tag}` must not contain control characters.")


def _validate_nonempty_string_list(
    value: Any,
    tag: str,
    errors: list[str],
    *,
    require_unique: bool = False,
    require_sorted: bool = False,
) -> None:
    if not isinstance(value, list):
        errors.append(f"`{tag}` must be list.")
        return
    normalized: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"`{tag}[{idx}]` must be string.")
            continue
        stripped = item.strip()
        if not stripped:
            errors.append(f"`{tag}[{idx}]` must be non-empty.")
            continue
        if item != stripped:
            errors.append(f"`{tag}[{idx}]` must not have leading or trailing whitespace.")
        normalized.append(stripped)
    if require_unique and len(set(normalized)) != len(normalized):
        errors.append(f"`{tag}` must not contain duplicates.")
    if require_sorted and normalized != sorted(normalized):
        errors.append(f"`{tag}` must be sorted in ascending order.")


def _trimmed_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    trimmed: list[str] = []
    for item in value:
        if isinstance(item, str):
            normalized = item.strip()
            if normalized:
                trimmed.append(normalized)
    return trimmed


def _normalize_modifier_token(value: str) -> str:
    lowered = value.strip().lower()
    lowered = lowered.replace("×", "x")
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered


def _material_modifier_nonordinary_reasons(value: str) -> set[str]:
    normalized = _normalize_modifier_token(value)
    reasons: set[str] = set()
    if not normalized:
        return reasons

    if normalized in NON_ORDINARY_MATERIAL_MODIFIERS:
        reasons.add(normalized)

    if (
        "reactive_powder" in normalized
        or normalized in {"rpc", "rpc_concrete", "uhrpc"}
        or normalized.startswith("rpc_")
        or normalized.endswith("_rpc")
    ):
        reasons.add("reactive_powder")
    if (
        "fiber_reinforced" in normalized
        or "fibre_reinforced" in normalized
        or "steel_fiber" in normalized
        or "steel_fibre" in normalized
        or normalized in {"sfrc", "steelfiber", "steelfibre"}
    ):
        reasons.add("fiber_reinforced")
    if (
        "rubber" in normalized
        or "crumb_rubber" in normalized
        or "rubberized" in normalized
        or "rubberised" in normalized
    ):
        reasons.add("rubber_concrete")
    if (
        "polymer_modified" in normalized
        or normalized.startswith("polymer_")
        or normalized.endswith("_polymer")
        or "latex_modified" in normalized
        or "epoxy_modified" in normalized
    ):
        reasons.add("polymer_modified")
    if "foamed" in normalized or "foam_concrete" in normalized:
        reasons.add("foamed_concrete")
    return reasons


def _material_modifier_family_factors(value: str) -> set[str]:
    normalized = _normalize_modifier_token(value)
    factors: set[str] = set()
    if not normalized:
        return factors

    if (
        normalized in ALKALI_ACTIVATED_FAMILY_MODIFIERS
        or normalized in {"aam", "aam_concrete", "aam_binder"}
        or ("alkali" in normalized and "activated" in normalized)
    ):
        factors.add("alkali_activated_concrete")
    if normalized in GEOPOLYMER_FAMILY_MODIFIERS or "geopolymer" in normalized:
        factors.add("geopolymer_concrete")
    if (
        normalized in EXPANSIVE_FAMILY_MODIFIERS
        or "expansive" in normalized
        or "shrinkage_compensating" in normalized
        or "self_stressing" in normalized
    ):
        factors.add("expansive_concrete")
    return factors


def _unknown_material_modifiers(values: list[str]) -> list[str]:
    unknown: list[str] = []
    for value in values:
        normalized = _normalize_modifier_token(value)
        if not normalized:
            continue
        if normalized in ALL_KNOWN_MATERIAL_MODIFIERS:
            continue
        if _material_modifier_nonordinary_reasons(value):
            continue
        if _material_modifier_family_factors(value):
            continue
        unknown.append(value)
    return unknown


def _warn_if_locator_missing(value: str, tag: str, warnings: list[str]) -> None:
    if PAGE_LOCATOR_PATTERN.search(value) is None:
        warnings.append(f"`{tag}` should include page localization.")
    if SOURCE_LOCATOR_PATTERN.search(value) is None:
        warnings.append(f"`{tag}` should include table/figure/text locator.")


def _is_valid_fc_type(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered in FC_TYPE_ALLOWED_SHAPE_ONLY:
        return True
    return FC_TYPE_SIZED_PATTERN.fullmatch(text) is not None


def _fc_type_implied_basis(fc_type_str: str) -> str | None:
    lowered = fc_type_str.strip().lower()
    if not lowered or lowered == "unknown":
        return None
    for basis in ("cube", "cylinder", "prism"):
        if lowered.startswith(basis):
            return basis
    return None


def _validate_ref_info(obj: Any, errors: list[str]) -> None:
    if not isinstance(obj, dict):
        errors.append("`ref_info` must be an object.")
        return

    required = ("title", "authors", "journal", "year", "citation_tag")
    for key in required:
        if key not in obj:
            errors.append(f"`ref_info.{key}` is required.")

    if "title" in obj and not isinstance(obj["title"], str):
        errors.append("`ref_info.title` must be string.")
    if "authors" in obj:
        if not isinstance(obj["authors"], list):
            errors.append("`ref_info.authors` must be list.")
        else:
            for idx, author in enumerate(obj["authors"]):
                if not isinstance(author, str):
                    errors.append(f"`ref_info.authors[{idx}]` must be string.")
    if "journal" in obj and not isinstance(obj["journal"], str):
        errors.append("`ref_info.journal` must be string.")
    if "year" in obj and not isinstance(obj["year"], int):
        errors.append("`ref_info.year` must be integer.")
    if "citation_tag" in obj and not isinstance(obj["citation_tag"], str):
        errors.append("`ref_info.citation_tag` must be string.")
    if "doi" in obj and obj["doi"] is not None and not isinstance(obj["doi"], str):
        errors.append("`ref_info.doi` must be string or null.")
    if "language" in obj and obj["language"] is not None and not isinstance(obj["language"], str):
        errors.append("`ref_info.language` must be string or null.")


def _validate_ordinary_filter(
    obj: Any,
    is_valid: bool | None,
    is_ordinary_cfst: bool | None,
    errors: list[str],
) -> None:
    if not isinstance(obj, dict):
        errors.append("`ordinary_filter` must be an object.")
        return

    for key in ("include_in_dataset", "ordinary_count", "total_count", "special_factors", "exclusion_reasons"):
        if key not in obj:
            errors.append(f"`ordinary_filter.{key}` is required.")

    include = obj.get("include_in_dataset")
    if include is not None and not isinstance(include, bool):
        errors.append("`ordinary_filter.include_in_dataset` must be boolean.")

    ordinary_count = obj.get("ordinary_count")
    if ordinary_count is not None and not isinstance(ordinary_count, int):
        errors.append("`ordinary_filter.ordinary_count` must be integer.")
    total_count = obj.get("total_count")
    if total_count is not None and not isinstance(total_count, int):
        errors.append("`ordinary_filter.total_count` must be integer.")

    if isinstance(ordinary_count, int) and isinstance(total_count, int):
        if ordinary_count < 0:
            errors.append("`ordinary_filter.ordinary_count` must be >= 0.")
        if total_count < 0:
            errors.append("`ordinary_filter.total_count` must be >= 0.")
        if ordinary_count > total_count:
            errors.append("`ordinary_filter.ordinary_count` cannot exceed `total_count`.")

    if "special_factors" in obj:
        _validate_nonempty_string_list(
            obj["special_factors"],
            "ordinary_filter.special_factors",
            errors,
            require_unique=True,
            require_sorted=True,
        )
        if isinstance(obj["special_factors"], list):
            for idx, item in enumerate(obj["special_factors"]):
                if isinstance(item, str) and item.strip() and item not in ORDINARY_ALLOWED_SPECIAL_FACTORS:
                    allowed = ", ".join(sorted(ORDINARY_ALLOWED_SPECIAL_FACTORS))
                    errors.append(
                        f"`ordinary_filter.special_factors[{idx}]` invalid: {item}. Allowed values: {allowed}."
                    )
    if "exclusion_reasons" in obj:
        _validate_string_list(obj["exclusion_reasons"], "ordinary_filter.exclusion_reasons", errors)

    if isinstance(is_ordinary_cfst, bool) and isinstance(include, bool):
        if is_ordinary_cfst and not include:
            errors.append("`is_ordinary_cfst=true` requires `ordinary_filter.include_in_dataset=true`.")
        if not is_ordinary_cfst and include:
            errors.append("`ordinary_filter.include_in_dataset=true` requires `is_ordinary_cfst=true`.")
    if is_valid is False and include is True:
        errors.append("Invalid paper cannot be included in dataset.")


def _validate_setup_figure(obj: Any, errors: list[str]) -> None:
    if not isinstance(obj, dict):
        errors.append("`paper_level.setup_figure` must be an object.")
        return
    for key in ("figure_id", "image_path", "page"):
        if key not in obj:
            errors.append(f"`paper_level.setup_figure.{key}` is required.")
    if "figure_id" in obj and obj["figure_id"] is not None and not isinstance(obj["figure_id"], str):
        errors.append("`paper_level.setup_figure.figure_id` must be string or null.")
    if "image_path" in obj and obj["image_path"] is not None and not isinstance(obj["image_path"], str):
        errors.append("`paper_level.setup_figure.image_path` must be string or null.")
    if "page" in obj and obj["page"] is not None and not isinstance(obj["page"], int):
        errors.append("`paper_level.setup_figure.page` must be integer or null.")


def _validate_paper_level(obj: Any, errors: list[str]) -> None:
    if not isinstance(obj, dict):
        errors.append("`paper_level` must be an object.")
        return

    for key in (
        "loading_mode",
        "boundary_condition",
        "test_temperature",
        "loading_regime",
        "loading_pattern",
        "setup_figure",
        "expected_specimen_count",
        "notes",
    ):
        if key not in obj:
            errors.append(f"`paper_level.{key}` is required.")

    loading_mode = obj.get("loading_mode")
    if loading_mode is not None and loading_mode not in PAPER_LOADING_MODES:
        errors.append(f"`paper_level.loading_mode` invalid: {loading_mode}")
    test_temperature = obj.get("test_temperature")
    if test_temperature is not None and test_temperature not in TEST_TEMPERATURES:
        errors.append(f"`paper_level.test_temperature` invalid: {test_temperature}")
    loading_regime = obj.get("loading_regime")
    if loading_regime is not None and loading_regime not in LOADING_REGIMES:
        errors.append(f"`paper_level.loading_regime` invalid: {loading_regime}")
    loading_pattern = obj.get("loading_pattern")
    if loading_pattern is not None and loading_pattern not in LOADING_PATTERNS:
        errors.append(f"`paper_level.loading_pattern` invalid: {loading_pattern}")
    if "boundary_condition" in obj and obj["boundary_condition"] is not None and not isinstance(obj["boundary_condition"], str):
        errors.append("`paper_level.boundary_condition` must be string or null.")
    if "notes" in obj:
        _validate_string_list(obj["notes"], "paper_level.notes", errors)
    if "expected_specimen_count" in obj and obj["expected_specimen_count"] is not None:
        if not isinstance(obj["expected_specimen_count"], int):
            errors.append("`paper_level.expected_specimen_count` must be integer or null.")
        elif obj["expected_specimen_count"] < 0:
            errors.append("`paper_level.expected_specimen_count` must be >= 0.")
    if "setup_figure" in obj:
        _validate_setup_figure(obj["setup_figure"], errors)


def _validate_context_fragment(value: Any, tag: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"`{tag}` must be an object.")
        return

    unknown_keys = sorted(set(value.keys()) - CONTEXT_KEYS)
    if unknown_keys:
        errors.append(f"`{tag}` has unsupported keys: {unknown_keys}")

    if "section_shape" in value:
        section_shape = value["section_shape"]
        if not isinstance(section_shape, str):
            errors.append(f"`{tag}.section_shape` must be string.")
        elif section_shape not in SECTION_SHAPES:
            errors.append(f"`{tag}.section_shape` invalid: {section_shape}")

    if "loading_mode" in value:
        loading_mode = value["loading_mode"]
        if not isinstance(loading_mode, str):
            errors.append(f"`{tag}.loading_mode` must be string.")
        elif loading_mode not in ROW_LOADING_MODES:
            errors.append(f"`{tag}.loading_mode` invalid: {loading_mode}")

    if "loading_pattern" in value:
        loading_pattern = value["loading_pattern"]
        if not isinstance(loading_pattern, str):
            errors.append(f"`{tag}.loading_pattern` must be string.")
        elif loading_pattern not in ROW_LOADING_PATTERNS:
            errors.append(f"`{tag}.loading_pattern` invalid: {loading_pattern}")

    if "boundary_condition" in value and value["boundary_condition"] is not None and not isinstance(value["boundary_condition"], str):
        errors.append(f"`{tag}.boundary_condition` must be string or null.")

    if "fc_type" in value:
        fc_type = value["fc_type"]
        if not isinstance(fc_type, str):
            errors.append(f"`{tag}.fc_type` must be string.")
        else:
            normalized = fc_type.strip()
            if not normalized:
                errors.append(f"`{tag}.fc_type` must be non-empty.")
            elif FC_TYPE_DISALLOWED_SYMBOL_PATTERN.search(normalized):
                errors.append(
                    f"`{tag}.fc_type` must not use symbolic notation like f'c/fcu/fck. Use cube/cylinder/prism or Unknown."
                )
            elif not _is_valid_fc_type(normalized):
                errors.append(
                    f"`{tag}.fc_type` invalid. Allowed forms: cube/cylinder/prism/Unknown or sized forms like `Cylinder 100x200`."
                )

    if "fc_basis" in value:
        fc_basis = value["fc_basis"]
        if not isinstance(fc_basis, str):
            errors.append(f"`{tag}.fc_basis` must be string.")
        elif fc_basis not in FC_BASIS_ALLOWED:
            errors.append(f"`{tag}.fc_basis` invalid: {fc_basis}")

    if "fc_type" in value and "fc_basis" in value and isinstance(value.get("fc_type"), str) and isinstance(value.get("fc_basis"), str):
        implied = _fc_type_implied_basis(value["fc_type"])
        if implied is not None and value["fc_basis"] != "unknown" and implied != value["fc_basis"]:
            errors.append(
                f"`{tag}.fc_type` '{value['fc_type']}' implies basis '{implied}' but `fc_basis` is '{value['fc_basis']}'."
            )

    if "steel_type" in value:
        steel_type = value["steel_type"]
        if not isinstance(steel_type, str):
            errors.append(f"`{tag}.steel_type` must be string.")
        elif steel_type not in STEEL_TYPES:
            errors.append(f"`{tag}.steel_type` invalid: {steel_type}")

    if "concrete_type" in value:
        concrete_type = value["concrete_type"]
        if not isinstance(concrete_type, str):
            errors.append(f"`{tag}.concrete_type` must be string.")
        elif concrete_type not in CONCRETE_TYPES:
            errors.append(f"`{tag}.concrete_type` invalid: {concrete_type}")

    if "material_modifiers" in value:
        _validate_string_list(value["material_modifiers"], f"{tag}.material_modifiers", errors)

    if "test_temperature" in value:
        test_temperature = value["test_temperature"]
        if not isinstance(test_temperature, str):
            errors.append(f"`{tag}.test_temperature` must be string.")
        elif test_temperature not in TEST_TEMPERATURES:
            errors.append(f"`{tag}.test_temperature` invalid: {test_temperature}")

    if "loading_regime" in value:
        loading_regime = value["loading_regime"]
        if not isinstance(loading_regime, str):
            errors.append(f"`{tag}.loading_regime` must be string.")
        elif loading_regime not in LOADING_REGIMES:
            errors.append(f"`{tag}.loading_regime` invalid: {loading_regime}")


def _validate_series_definitions(obj: Any, errors: list[str]) -> None:
    if not isinstance(obj, list):
        errors.append("`series_definitions` must be list.")
        return

    series_ids: set[str] = set()
    for idx, item in enumerate(obj):
        tag = f"series_definitions[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"`{tag}` must be object.")
            continue

        unknown_keys = sorted(set(item.keys()) - SERIES_DEFINITION_KEYS)
        if unknown_keys:
            errors.append(f"`{tag}` has unsupported keys: {unknown_keys}")

        series_id = _validate_canonical_string(item.get("series_id"), f"{tag}.series_id", errors)
        if series_id is not None:
            if series_id in series_ids:
                errors.append(f"`series_definitions` duplicated series_id: {series_id}")
            series_ids.add(series_id)

        if "shared_context" not in item:
            errors.append(f"`{tag}.shared_context` is required.")
        else:
            _validate_context_fragment(item["shared_context"], f"{tag}.shared_context", errors)

        if "description" in item and item["description"] is not None and not isinstance(item["description"], str):
            errors.append(f"`{tag}.description` must be string or null.")
        if "notes" in item:
            _validate_string_list(item["notes"], f"{tag}.notes", errors)


def _build_series_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    series_map: dict[str, dict[str, Any]] = {}
    definitions = payload.get("series_definitions", [])
    if not isinstance(definitions, list):
        return series_map
    for item in definitions:
        if not isinstance(item, dict):
            continue
        series_id = _canonical_string(item.get("series_id"))
        if series_id is not None:
            series_map[series_id] = item
    return series_map


def _resolve_context_value(
    field: str,
    payload: dict[str, Any],
    specimen: dict[str, Any],
    series_map: dict[str, dict[str, Any]],
) -> Any:
    if field in specimen and specimen[field] is not None:
        return specimen[field]

    context_overrides = specimen.get("context_overrides")
    if isinstance(context_overrides, dict) and field in context_overrides and context_overrides[field] is not None:
        return context_overrides[field]

    series_id = _canonical_string(specimen.get("series_id"))
    if series_id is not None:
        series_def = series_map.get(series_id)
        if isinstance(series_def, dict):
            shared = series_def.get("shared_context")
            if isinstance(shared, dict) and field in shared and shared[field] is not None:
                return shared[field]

    shared_context = payload.get("shared_context")
    if isinstance(shared_context, dict) and field in shared_context and shared_context[field] is not None:
        return shared_context[field]

    if field in {"loading_mode", "loading_pattern", "boundary_condition", "test_temperature", "loading_regime"}:
        paper_level = payload.get("paper_level")
        if isinstance(paper_level, dict) and field in paper_level and paper_level[field] is not None:
            paper_level_value = paper_level[field]
            if field == "loading_mode" and paper_level_value == "mixed":
                return None
            if field == "loading_pattern" and paper_level_value == "mixed":
                return None
            return paper_level_value

    if field == "section_shape":
        group_name = specimen.get("__group_name__")
        if isinstance(group_name, str):
            allowed_shapes = GROUP_TO_SHAPES.get(group_name)
            if allowed_shapes == {"circular"}:
                return "circular"

    return None


def _resolve_specimen_context(
    payload: dict[str, Any],
    specimen: dict[str, Any],
    series_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        field: _resolve_context_value(field, payload, specimen, series_map)
        for field in INHERITABLE_CONTEXT_KEYS
    }


def _validate_context_override_conflicts(specimen: dict[str, Any], tag: str, errors: list[str]) -> None:
    context_overrides = specimen.get("context_overrides")
    if not isinstance(context_overrides, dict):
        return
    for field in ROW_CONTEXT_KEYS:
        if field in specimen and field in context_overrides and specimen[field] != context_overrides[field]:
            errors.append(
                f"`{tag}` defines `{field}` both directly and in `context_overrides` with different values."
            )


def _validate_effective_context(
    group_name: str,
    tag: str,
    effective: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    section_shape = effective.get("section_shape")
    if not isinstance(section_shape, str):
        errors.append(f"`{tag}` cannot resolve `section_shape` from row/shared/series context.")
    elif section_shape not in SECTION_SHAPES:
        errors.append(f"`{tag}.section_shape` invalid after context resolution: {section_shape}")
    elif section_shape not in GROUP_TO_SHAPES[group_name]:
        errors.append(f"`{tag}.section_shape` incompatible with {group_name} after context resolution.")

    loading_mode = effective.get("loading_mode")
    if not isinstance(loading_mode, str):
        errors.append(f"`{tag}` cannot resolve `loading_mode` from row/shared/series context.")
    elif loading_mode not in ROW_LOADING_MODES:
        errors.append(f"`{tag}.loading_mode` invalid after context resolution: {loading_mode}")

    loading_pattern = effective.get("loading_pattern")
    if not isinstance(loading_pattern, str):
        errors.append(f"`{tag}` cannot resolve `loading_pattern` from row/shared/series context.")
    elif loading_pattern not in ROW_LOADING_PATTERNS:
        errors.append(f"`{tag}.loading_pattern` invalid after context resolution: {loading_pattern}")

    boundary_condition = effective.get("boundary_condition")
    if boundary_condition is not None and not isinstance(boundary_condition, str):
        errors.append(f"`{tag}.boundary_condition` invalid after context resolution.")

    fc_type = effective.get("fc_type")
    if not isinstance(fc_type, str):
        errors.append(f"`{tag}` cannot resolve `fc_type` from row/shared/series context.")
    else:
        normalized_fc_type = fc_type.strip()
        if not normalized_fc_type:
            errors.append(f"`{tag}.fc_type` must be non-empty after context resolution.")
        elif FC_TYPE_DISALLOWED_SYMBOL_PATTERN.search(normalized_fc_type):
            errors.append(
                f"`{tag}.fc_type` must not use symbolic notation like f'c/fcu/fck. Use cube/cylinder/prism or Unknown."
            )
        elif not _is_valid_fc_type(normalized_fc_type):
            errors.append(
                f"`{tag}.fc_type` invalid after context resolution. Allowed forms: cube/cylinder/prism/Unknown or sized forms like `Cylinder 100x200`."
            )

    fc_basis = effective.get("fc_basis")
    if not isinstance(fc_basis, str):
        errors.append(f"`{tag}` cannot resolve `fc_basis` from row/shared/series context.")
    elif fc_basis not in FC_BASIS_ALLOWED:
        errors.append(f"`{tag}.fc_basis` invalid after context resolution: {fc_basis}")

    if isinstance(fc_type, str) and isinstance(fc_basis, str):
        implied = _fc_type_implied_basis(fc_type)
        if implied is not None and fc_basis != "unknown" and implied != fc_basis:
            errors.append(
                f"`{tag}.fc_type` '{fc_type}' implies basis '{implied}' but `fc_basis` is '{fc_basis}'."
            )

    steel_type = effective.get("steel_type")
    if not isinstance(steel_type, str):
        errors.append(f"`{tag}` cannot resolve `steel_type` from row/shared/series context.")
    elif steel_type not in STEEL_TYPES:
        errors.append(f"`{tag}.steel_type` invalid after context resolution: {steel_type}")

    concrete_type = effective.get("concrete_type")
    if not isinstance(concrete_type, str):
        errors.append(f"`{tag}` cannot resolve `concrete_type` from row/shared/series context.")
    elif concrete_type not in CONCRETE_TYPES:
        errors.append(f"`{tag}.concrete_type` invalid after context resolution: {concrete_type}")

    material_modifiers = effective.get("material_modifiers")
    if not isinstance(material_modifiers, list):
        errors.append(f"`{tag}` cannot resolve `material_modifiers` from row/shared/series context.")
    else:
        _validate_string_list(material_modifiers, f"{tag}.material_modifiers", errors)
        unknown_modifiers = _unknown_material_modifiers(_trimmed_string_list(material_modifiers))
        if unknown_modifiers:
            warnings.append(
                f"`{tag}.material_modifiers` contains unnormalized or unknown subtype tags: {unknown_modifiers}. Keep family-level `concrete_type` correct and normalize the tags when defensible."
            )

    test_temperature = effective.get("test_temperature")
    if not isinstance(test_temperature, str):
        errors.append(f"`{tag}` cannot resolve `test_temperature` from shared/series/paper context.")
    elif test_temperature not in TEST_TEMPERATURES:
        errors.append(f"`{tag}.test_temperature` invalid after context resolution: {test_temperature}")

    loading_regime = effective.get("loading_regime")
    if not isinstance(loading_regime, str):
        errors.append(f"`{tag}` cannot resolve `loading_regime` from shared/series/paper context.")
    elif loading_regime not in LOADING_REGIMES:
        errors.append(f"`{tag}.loading_regime` invalid after context resolution: {loading_regime}")


def _expected_nonordinary_reasons(effective: dict[str, Any]) -> set[str]:
    reasons: set[str] = set()
    if effective.get("section_shape") not in ORDINARY_ALLOWED_SHAPES and effective.get("section_shape") in SECTION_SHAPES:
        reasons.add("non_ordinary_shape")
    if effective.get("steel_type") == "stainless_steel":
        reasons.add("stainless_steel")
    if effective.get("concrete_type") == "uhpc":
        reasons.add("uhpc")
    if effective.get("loading_pattern") == "cyclic":
        reasons.add("cyclic_loading")
    if effective.get("loading_pattern") == "repeated":
        reasons.add("repeated_loading")
    if effective.get("test_temperature") not in {None, "ambient", "unknown"}:
        reasons.add("non_ambient_temperature")
    if effective.get("loading_regime") not in {None, "static", "unknown"}:
        reasons.add("non_static_loading_regime")
    for modifier in _trimmed_string_list(effective.get("material_modifiers")):
        reasons.update(_material_modifier_nonordinary_reasons(modifier))
    return reasons


def _ordinary_verdict_details(
    effective: dict[str, Any],
    *,
    durability_conditioning: list[str] | None = None,
    member_modifiers: list[str] | None = None,
) -> tuple[bool, set[str]]:
    reasons = set(_expected_nonordinary_reasons(effective))
    reasons.update(durability_conditioning or [])
    reasons.update(member_modifiers or [])
    return len(reasons) == 0, reasons


def _validate_specimen(
    group_name: str,
    idx: int,
    specimen: Any,
    payload: dict[str, Any],
    series_map: dict[str, dict[str, Any]],
    errors: list[str],
    warnings: list[str],
    strict_rounding: bool,
) -> None:
    tag = f"{group_name}[{idx}]"
    if not isinstance(specimen, dict):
        errors.append(f"`{tag}` must be object.")
        return

    missing = SPECIMEN_REQUIRED_KEYS - set(specimen.keys())
    if missing:
        errors.append(f"`{tag}` missing keys: {sorted(missing)}")

    unknown_keys = sorted(set(specimen.keys()) - (SPECIMEN_REQUIRED_KEYS | SPECIMEN_OPTIONAL_KEYS | {"__group_name__"}))
    if unknown_keys:
        errors.append(f"`{tag}` has unsupported keys: {unknown_keys}")

    for key in NUMERIC_FIELDS:
        if key in specimen and not _is_number(specimen[key]):
            errors.append(f"`{tag}.{key}` must be numeric.")
    for key in NULLABLE_NUMERIC_FIELDS:
        if key in specimen and specimen[key] is not None and not _is_number(specimen[key]):
            errors.append(f"`{tag}.{key}` must be numeric or null.")

    if "ref_no" in specimen:
        if not isinstance(specimen["ref_no"], str):
            errors.append(f"`{tag}.ref_no` must be string.")
        elif specimen["ref_no"] != "":
            errors.append(f"`{tag}.ref_no` must be empty string.")

    specimen_label = None
    if "specimen_label" in specimen:
        specimen_label = _validate_canonical_string(specimen["specimen_label"], f"{tag}.specimen_label", errors)

    reported_group_label = None
    if "reported_group_label" in specimen:
        reported_group_label = _validate_canonical_string(
            specimen["reported_group_label"],
            f"{tag}.reported_group_label",
            errors,
            allow_null=True,
        )

    if "replicate_index" in specimen:
        value = specimen["replicate_index"]
        if value is not None and not isinstance(value, int):
            errors.append(f"`{tag}.replicate_index` must be integer or null.")
        elif isinstance(value, int) and value <= 0:
            errors.append(f"`{tag}.replicate_index` must be >= 1 when provided.")

    if specimen_label is not None and reported_group_label is not None and isinstance(specimen.get("replicate_index"), int):
        expected_label = f"{reported_group_label}-{specimen['replicate_index']}"
        if specimen_label != expected_label:
            warnings.append(
                f"`{tag}` has `reported_group_label`/`replicate_index`, but `specimen_label` is not the canonical `{expected_label}` form."
            )

    if "series_id" in specimen:
        series_id = _validate_canonical_string(specimen["series_id"], f"{tag}.series_id", errors, allow_null=True)
        if series_id is not None and series_id not in series_map:
            errors.append(f"`{tag}.series_id` refers to unknown series_id `{series_id}`.")

    if "specimen_note" in specimen and specimen["specimen_note"] is not None and not isinstance(specimen["specimen_note"], str):
        errors.append(f"`{tag}.specimen_note` must be string or null.")

    if "quality_flags" in specimen:
        _validate_string_list(specimen["quality_flags"], f"{tag}.quality_flags", errors)

    if "context_overrides" in specimen:
        _validate_context_fragment(specimen["context_overrides"], f"{tag}.context_overrides", errors)

    for field in ROW_CONTEXT_KEYS:
        if field in specimen:
            _validate_context_fragment({field: specimen[field]}, tag, errors)

    _validate_context_override_conflicts(specimen, tag, errors)

    if "is_ordinary" in specimen and not isinstance(specimen["is_ordinary"], bool):
        errors.append(f"`{tag}.is_ordinary` must be boolean.")

    if "ordinary_exclusion_reasons" in specimen:
        _validate_string_list(specimen["ordinary_exclusion_reasons"], f"{tag}.ordinary_exclusion_reasons", errors)
        reasons = specimen["ordinary_exclusion_reasons"]
        is_ord = specimen.get("is_ordinary")
        if is_ord is True and isinstance(reasons, list) and len(reasons) > 0:
            errors.append(f"`{tag}.is_ordinary=true` must have empty `ordinary_exclusion_reasons`.")
        if is_ord is False and isinstance(reasons, list) and len(reasons) == 0:
            errors.append(f"`{tag}.is_ordinary=false` must have non-empty `ordinary_exclusion_reasons`.")

    if "source_evidence" in specimen:
        _validate_nonempty_line(specimen["source_evidence"], f"{tag}.source_evidence", errors)
        if isinstance(specimen["source_evidence"], str):
            _warn_if_locator_missing(specimen["source_evidence"], f"{tag}.source_evidence", warnings)

    specimen["__group_name__"] = group_name
    effective = _resolve_specimen_context(payload, specimen, series_map)
    _validate_effective_context(group_name, tag, effective, errors, warnings)

    raw_flags = specimen.get("quality_flags")
    flags = raw_flags if isinstance(raw_flags, list) else []
    if any(flag == "group_average_n_exp" for flag in flags):
        source_evidence = specimen.get("source_evidence")
        if isinstance(source_evidence, str) and GROUP_AVERAGE_HINT_PATTERN.search(source_evidence) is None:
            warnings.append(f"`{tag}.source_evidence` should state that `n_exp` is a reported group average.")

    for key in ("fc_value", "fy", "b", "h", "t", "L", "n_exp"):
        if key in specimen and _is_number(specimen[key]) and specimen[key] <= 0:
            errors.append(f"`{tag}.{key}` must be > 0.")
    if "fcy150" in specimen and _is_number(specimen["fcy150"]) and specimen["fcy150"] <= 0:
        errors.append(f"`{tag}.fcy150` must be > 0 when populated.")
    if "r_ratio" in specimen and _is_number(specimen["r_ratio"]):
        if specimen["r_ratio"] < 0 or specimen["r_ratio"] > 100:
            errors.append(f"`{tag}.r_ratio` must be between 0 and 100.")
    if all(k in specimen and _is_number(specimen[k]) for k in ("b", "h", "t")):
        if specimen["t"] >= min(specimen["b"], specimen["h"]) / 2.0:
            errors.append(f"`{tag}.t` must be smaller than min(b, h)/2.")
    if "r0" in specimen and _is_number(specimen["r0"]) and specimen["r0"] < 0:
        errors.append(f"`{tag}.r0` must be >= 0.")

    if group_name == "Group_B":
        if all(k in specimen and _is_number(specimen[k]) for k in ("b", "h")) and not _roughly_equal(specimen["b"], specimen["h"]):
            errors.append(f"`{tag}` must satisfy b == h for Group_B.")
        if all(k in specimen and _is_number(specimen[k]) for k in ("h", "r0")) and not _roughly_equal(specimen["r0"], specimen["h"] / 2.0):
            errors.append(f"`{tag}.r0` must equal h/2 for Group_B.")

    if group_name == "Group_C":
        if all(k in specimen and _is_number(specimen[k]) for k in ("b", "h")) and specimen["b"] + EPS < specimen["h"]:
            errors.append(f"`{tag}` must satisfy b >= h for Group_C.")
        if all(k in specimen and _is_number(specimen[k]) for k in ("h", "r0")) and not _roughly_equal(specimen["r0"], specimen["h"] / 2.0):
            errors.append(f"`{tag}.r0` must equal h/2 for Group_C.")

    loading_mode = effective.get("loading_mode")
    if isinstance(loading_mode, str) and all(k in specimen and _is_number(specimen[k]) for k in ("e1", "e2")):
        if loading_mode == "axial":
            if not (_roughly_equal(specimen["e1"], 0.0) and _roughly_equal(specimen["e2"], 0.0)):
                errors.append(f"`{tag}` axial row must have e1=e2=0.")
        elif loading_mode == "eccentric":
            if _roughly_equal(specimen["e1"], 0.0) and _roughly_equal(specimen["e2"], 0.0):
                errors.append(f"`{tag}` eccentric row cannot have both e1 and e2 equal to 0.")

    for key in NUMERIC_FIELDS | NULLABLE_NUMERIC_FIELDS:
        if key in specimen and _is_number(specimen[key]) and not _has_3dp(specimen[key]):
            msg = f"`{tag}.{key}` is not rounded to 0.001: {specimen[key]}"
            if strict_rounding:
                errors.append(msg)
            else:
                warnings.append(msg)


def _iter_specimens(payload: dict[str, Any]):
    for group_name in ("Group_A", "Group_B", "Group_C"):
        group = payload.get(group_name, [])
        if isinstance(group, list):
            for idx, specimen in enumerate(group):
                if isinstance(specimen, dict):
                    yield group_name, idx, specimen


def _payload_label_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for _, _, specimen in _iter_specimens(payload):
        label = _canonical_string(specimen.get("specimen_label"))
        if label is not None:
            rows[label] = specimen
    return rows


def validate_payload_against_scratch(payload: Any, scratch_payload: Any) -> list[str]:
    errors: list[str] = []

    if not isinstance(payload, dict):
        return ["Top-level JSON must be object."]
    if not isinstance(scratch_payload, dict):
        return ["Scratch YAML must decode to an object."]

    decisions = scratch_payload.get("ordinary_decisions")
    if not isinstance(decisions, list):
        return ["`ordinary_decisions` is required in scratch YAML and must be a list."]

    series_map = _build_series_map(payload)
    payload_rows = _payload_label_map(payload)
    payload_labels = set(payload_rows)
    scratch_labels: set[str] = set()
    scratch_ordinary_count = 0
    derived_special_factors: set[str] = set()

    for idx, decision in enumerate(decisions):
        tag = f"ordinary_decisions[{idx}]"
        if not isinstance(decision, dict):
            errors.append(f"`{tag}` must be an object.")
            continue

        missing = SCRATCH_DECISION_KEYS - set(decision.keys())
        if missing:
            errors.append(f"`{tag}` missing keys: {sorted(missing)}")

        label = _validate_canonical_string(decision.get("label"), f"{tag}.label", errors)
        if label is None:
            continue
        if label in scratch_labels:
            errors.append(f"`ordinary_decisions` duplicated label: {label}")
            continue
        scratch_labels.add(label)

        section_shape = decision.get("section_shape")
        if not isinstance(section_shape, str) or section_shape not in SECTION_SHAPES:
            errors.append(f"`{tag}.section_shape` invalid: {section_shape}")
            continue

        steel_type = decision.get("steel_type")
        if not isinstance(steel_type, str) or steel_type not in STEEL_TYPES:
            errors.append(f"`{tag}.steel_type` invalid: {steel_type}")
            continue

        concrete_type = decision.get("concrete_type")
        if not isinstance(concrete_type, str) or concrete_type not in CONCRETE_TYPES:
            errors.append(f"`{tag}.concrete_type` invalid: {concrete_type}")
            continue
        if concrete_type == "high_strength":
            derived_special_factors.add("high_strength_concrete")
        if concrete_type == "lightweight":
            derived_special_factors.add("lightweight_concrete")
        if concrete_type == "recycled":
            derived_special_factors.add("recycled_aggregate")
        if concrete_type == "self_consolidating":
            derived_special_factors.add("self_consolidating_concrete")
        if concrete_type == "alkali_activated":
            derived_special_factors.add("alkali_activated_concrete")
        if concrete_type == "geopolymer":
            derived_special_factors.add("geopolymer_concrete")
        if concrete_type == "expansive":
            derived_special_factors.add("expansive_concrete")

        loading_pattern = decision.get("loading_pattern")
        if not isinstance(loading_pattern, str) or loading_pattern not in ROW_LOADING_PATTERNS:
            errors.append(f"`{tag}.loading_pattern` invalid: {loading_pattern}")
            continue

        test_temperature = decision.get("test_temperature")
        if not isinstance(test_temperature, str) or test_temperature not in TEST_TEMPERATURES:
            errors.append(f"`{tag}.test_temperature` invalid: {test_temperature}")
            continue

        loading_regime = decision.get("loading_regime")
        if not isinstance(loading_regime, str) or loading_regime not in LOADING_REGIMES:
            errors.append(f"`{tag}.loading_regime` invalid: {loading_regime}")
            continue

        _validate_nonempty_string_list(
            decision.get("durability_conditioning"),
            f"{tag}.durability_conditioning",
            errors,
            require_unique=True,
        )
        scratch_durability = _trimmed_string_list(decision.get("durability_conditioning"))
        invalid_durability = [item for item in scratch_durability if item not in SCRATCH_DURABILITY_CONDITIONING]
        if invalid_durability:
            errors.append(f"`{tag}.durability_conditioning` invalid values: {invalid_durability}.")

        _validate_nonempty_string_list(
            decision.get("member_modifiers"),
            f"{tag}.member_modifiers",
            errors,
            require_unique=True,
        )
        scratch_member_modifiers = _trimmed_string_list(decision.get("member_modifiers"))
        invalid_member_modifiers = [item for item in scratch_member_modifiers if item not in SCRATCH_MEMBER_MODIFIERS]
        if invalid_member_modifiers:
            errors.append(f"`{tag}.member_modifiers` invalid values: {invalid_member_modifiers}.")

        _validate_nonempty_string_list(
            decision.get("material_modifiers"),
            f"{tag}.material_modifiers",
            errors,
            require_unique=True,
        )
        scratch_modifiers = _trimmed_string_list(decision.get("material_modifiers"))
        for modifier in scratch_modifiers:
            derived_special_factors.update(_material_modifier_family_factors(modifier))

        is_ordinary = decision.get("is_ordinary")
        if not isinstance(is_ordinary, bool):
            errors.append(f"`{tag}.is_ordinary` must be boolean.")
            continue

        _validate_nonempty_string_list(
            decision.get("exclusion_reasons"),
            f"{tag}.exclusion_reasons",
            errors,
            require_unique=True,
        )
        scratch_reasons = _trimmed_string_list(decision.get("exclusion_reasons"))

        specimen = payload_rows.get(label)
        if specimen is None:
            errors.append(f"`{tag}` label `{label}` is not present in `Group_A`/`Group_B`/`Group_C`.")
            continue

        effective = _resolve_specimen_context(payload, specimen, series_map)
        if effective.get("section_shape") != section_shape:
            errors.append(
                f"`{tag}.section_shape` is {section_shape} but JSON row `{label}` resolves to {effective.get('section_shape')}."
            )
        if effective.get("steel_type") != steel_type:
            errors.append(
                f"`{tag}.steel_type` is {steel_type} but JSON row `{label}` resolves to {effective.get('steel_type')}."
            )
        if effective.get("concrete_type") != concrete_type:
            errors.append(
                f"`{tag}.concrete_type` is {concrete_type} but JSON row `{label}` resolves to {effective.get('concrete_type')}."
            )
        if effective.get("loading_pattern") != loading_pattern:
            errors.append(
                f"`{tag}.loading_pattern` is {loading_pattern} but JSON row `{label}` resolves to {effective.get('loading_pattern')}."
            )
        if effective.get("test_temperature") != test_temperature:
            errors.append(
                f"`{tag}.test_temperature` is {test_temperature} but JSON row `{label}` resolves to {effective.get('test_temperature')}."
            )
        if effective.get("loading_regime") != loading_regime:
            errors.append(
                f"`{tag}.loading_regime` is {loading_regime} but JSON row `{label}` resolves to {effective.get('loading_regime')}."
            )
        if _trimmed_string_list(effective.get("material_modifiers")) != scratch_modifiers:
            errors.append(f"`{tag}.material_modifiers` does not match JSON row `{label}` after context resolution.")

        effective_gate = {
            "section_shape": section_shape,
            "steel_type": steel_type,
            "concrete_type": concrete_type,
            "loading_pattern": loading_pattern,
            "test_temperature": test_temperature,
            "loading_regime": loading_regime,
            "material_modifiers": scratch_modifiers,
        }
        expected_is_ordinary, expected_reason_set = _ordinary_verdict_details(
            effective_gate,
            durability_conditioning=scratch_durability,
            member_modifiers=scratch_member_modifiers,
        )

        if is_ordinary:
            scratch_ordinary_count += 1
            if scratch_reasons:
                errors.append(f"`{tag}.exclusion_reasons` must be empty when `is_ordinary=true`.")
            if not expected_is_ordinary:
                errors.append(
                    f"`{tag}.is_ordinary=true` is inconsistent with the gate inputs; implied non-ordinary reasons: {sorted(expected_reason_set)}."
                )
            if specimen.get("is_ordinary") is not True:
                errors.append(f"JSON row `{label}` must have `is_ordinary=true` to match `{tag}`.")
            if _trimmed_string_list(specimen.get("ordinary_exclusion_reasons")):
                errors.append(f"JSON row `{label}` must have empty `ordinary_exclusion_reasons` to match `{tag}`.")
        else:
            if not scratch_reasons:
                errors.append(f"`{tag}.exclusion_reasons` must be non-empty when `is_ordinary=false`.")
            missing_expected_reasons = sorted(expected_reason_set - set(scratch_reasons))
            if missing_expected_reasons:
                errors.append(
                    f"`{tag}.exclusion_reasons` must include reasons implied by the gate inputs: {missing_expected_reasons}."
                )
            if specimen.get("is_ordinary") is not False:
                errors.append(f"JSON row `{label}` must have `is_ordinary=false` to match `{tag}`.")
            if set(_trimmed_string_list(specimen.get("ordinary_exclusion_reasons"))) != set(scratch_reasons):
                errors.append(f"`{tag}.exclusion_reasons` does not match JSON row `{label}` reasons.")

    missing_in_json = sorted(scratch_labels - payload_labels)
    if missing_in_json:
        errors.append("Scratch YAML labels are not fully represented in JSON: " + ", ".join(missing_in_json))

    missing_in_scratch = sorted(payload_labels - scratch_labels)
    if missing_in_scratch:
        errors.append("JSON labels are missing from `ordinary_decisions`: " + ", ".join(missing_in_scratch))

    ordinary_filter = payload.get("ordinary_filter")
    if isinstance(ordinary_filter, dict):
        ordinary_count = ordinary_filter.get("ordinary_count")
        total_count = ordinary_filter.get("total_count")
        if isinstance(ordinary_count, int) and ordinary_count != scratch_ordinary_count:
            errors.append(
                f"`ordinary_filter.ordinary_count` is {ordinary_count} but scratch YAML records {scratch_ordinary_count} ordinary decisions."
            )
        if isinstance(total_count, int) and total_count != len(scratch_labels):
            errors.append(
                f"`ordinary_filter.total_count` is {total_count} but scratch YAML records {len(scratch_labels)} kept CFST specimens."
            )
        scratch_special_factors = sorted(derived_special_factors)
        if _trimmed_string_list(ordinary_filter.get("special_factors")) != scratch_special_factors:
            errors.append(
                "`ordinary_filter.special_factors` must equal the sorted paper-level tags derived from scratch YAML ordinary decisions: "
                f"{scratch_special_factors}."
            )

    paper_level = payload.get("paper_level")
    if isinstance(paper_level, dict):
        expected_specimen_count = paper_level.get("expected_specimen_count")
        if isinstance(expected_specimen_count, int) and expected_specimen_count != len(scratch_labels):
            errors.append(
                f"`paper_level.expected_specimen_count` is {expected_specimen_count} but scratch YAML records {len(scratch_labels)} kept CFST specimens."
            )

    return errors


def _validate_specimen_ordinary(
    tag: str,
    specimen: dict[str, Any],
    effective: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    is_ord = specimen.get("is_ordinary")
    if not isinstance(is_ord, bool):
        return

    expected_is_ordinary, expected_reasons = _ordinary_verdict_details(effective)

    if is_ord is True:
        if not expected_is_ordinary:
            errors.append(
                f"`{tag}.is_ordinary=true` is inconsistent with resolved context; implied non-ordinary reasons: {sorted(expected_reasons)}."
            )
        concrete_type = effective.get("concrete_type")
        r_ratio = specimen.get("r_ratio")
        if concrete_type == "recycled":
            if not _is_number(r_ratio) or (isinstance(r_ratio, (int, float)) and r_ratio <= 0):
                errors.append(f"`{tag}.is_ordinary=true` recycled concrete must have r_ratio > 0.")
        modifiers = _trimmed_string_list(effective.get("material_modifiers"))
        unknown_modifiers = _unknown_material_modifiers(modifiers)
        if unknown_modifiers:
            warnings.append(
                f"`{tag}.material_modifiers` contains unnormalized or unknown subtype tags: {unknown_modifiers}. Keep family-level `concrete_type` correct and normalize the tags when defensible."
            )
    else:
        reasons = _trimmed_string_list(specimen.get("ordinary_exclusion_reasons"))
        if not reasons:
            errors.append(f"`{tag}.is_ordinary=false` must have non-empty `ordinary_exclusion_reasons`.")
        missing = sorted(expected_reasons - set(reasons))
        if missing:
            warnings.append(
                f"`{tag}.ordinary_exclusion_reasons` is missing some reasons implied by resolved context: {missing}."
            )

    r_ratio = specimen.get("r_ratio")
    concrete_type = effective.get("concrete_type")
    if concrete_type != "recycled" and _is_number(r_ratio) and isinstance(r_ratio, (int, float)) and r_ratio > 0:
        warnings.append(
            f"`{tag}.r_ratio` > 0 but resolved `concrete_type` is {concrete_type}; use `recycled` when recycled aggregate is the primary type."
        )


def _validate_ordinary_scope(payload: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    actual_ordinary_count = 0
    total_count = 0
    series_map = _build_series_map(payload)
    for group_name, idx, specimen in _iter_specimens(payload):
        tag = f"{group_name}[{idx}]"
        specimen["__group_name__"] = group_name
        effective = _resolve_specimen_context(payload, specimen, series_map)
        total_count += 1
        _validate_specimen_ordinary(tag, specimen, effective, errors, warnings)
        if specimen.get("is_ordinary") is True:
            actual_ordinary_count += 1

    has_ordinary = actual_ordinary_count > 0
    is_ordinary_cfst = payload.get("is_ordinary_cfst")
    if isinstance(is_ordinary_cfst, bool):
        if is_ordinary_cfst and not has_ordinary:
            errors.append("`is_ordinary_cfst=true` but no specimen has `is_ordinary=true`.")
        if not is_ordinary_cfst and has_ordinary:
            errors.append("`is_ordinary_cfst=false` but some specimens have `is_ordinary=true`.")

    ordinary_filter = payload.get("ordinary_filter")
    if isinstance(ordinary_filter, dict):
        of_count = ordinary_filter.get("ordinary_count")
        if isinstance(of_count, int) and of_count != actual_ordinary_count:
            errors.append(
                f"`ordinary_filter.ordinary_count` is {of_count} but actual count of `is_ordinary=true` specimens is {actual_ordinary_count}."
            )
        of_total = ordinary_filter.get("total_count")
        if isinstance(of_total, int) and of_total != total_count:
            errors.append(
                f"`ordinary_filter.total_count` is {of_total} but actual specimen count is {total_count}."
            )


def validate_payload(
    payload: Any,
    expect_valid: bool | None,
    strict_rounding: bool,
    expect_count: int | None,
) -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        return ["Top-level JSON must be object."], warnings, 0

    missing_top = TOP_LEVEL_KEYS - set(payload.keys())
    if missing_top:
        errors.append(f"Missing top-level keys: {sorted(missing_top)}")

    if "schema_version" in payload:
        if not isinstance(payload["schema_version"], str):
            errors.append("`schema_version` must be string.")
        elif payload["schema_version"] != SCHEMA_VERSION:
            errors.append(f"`schema_version` must be `{SCHEMA_VERSION}`, got `{payload['schema_version']}`.")
    if "paper_id" in payload:
        _validate_canonical_string(payload["paper_id"], "paper_id", errors)

    if "is_valid" in payload and not isinstance(payload["is_valid"], bool):
        errors.append("`is_valid` must be boolean.")
    if "is_ordinary_cfst" in payload and not isinstance(payload["is_ordinary_cfst"], bool):
        errors.append("`is_ordinary_cfst` must be boolean.")
    if "reason" in payload:
        _validate_nonempty_line(payload["reason"], "reason", errors)

    for group_name in ("Group_A", "Group_B", "Group_C"):
        if group_name in payload and not isinstance(payload[group_name], list):
            errors.append(f"`{group_name}` must be list.")

    if "ordinary_filter" in payload:
        _validate_ordinary_filter(payload["ordinary_filter"], payload.get("is_valid"), payload.get("is_ordinary_cfst"), errors)
    if "ref_info" in payload:
        _validate_ref_info(payload["ref_info"], errors)
    if "paper_level" in payload:
        _validate_paper_level(payload["paper_level"], errors)
    if "shared_context" in payload:
        _validate_context_fragment(payload["shared_context"], "shared_context", errors)
    if "series_definitions" in payload:
        _validate_series_definitions(payload["series_definitions"], errors)

    if expect_valid is not None and "is_valid" in payload and payload["is_valid"] != expect_valid:
        errors.append(f"`is_valid` expected {expect_valid}, got {payload['is_valid']}.")

    series_map = _build_series_map(payload)
    total = 0
    label_index: dict[str, list[str]] = defaultdict(list)
    for group_name in ("Group_A", "Group_B", "Group_C"):
        group = payload.get(group_name, [])
        if isinstance(group, list):
            total += len(group)
            for idx, specimen in enumerate(group):
                _validate_specimen(group_name, idx, specimen, payload, series_map, errors, warnings, strict_rounding)
                tag = f"{group_name}[{idx}]"
                if isinstance(specimen, dict):
                    label = _canonical_string(specimen.get("specimen_label"))
                    if label is not None:
                        label_index[label].append(tag)

    for label, tags in label_index.items():
        if len(tags) > 1:
            errors.append(f"`specimen_label` duplicated across rows: '{label}' in {tags}.")

    paper_level = payload.get("paper_level")
    if isinstance(paper_level, dict):
        expected_from_payload = paper_level.get("expected_specimen_count")
        if isinstance(expected_from_payload, int) and expected_from_payload != total:
            errors.append(f"`paper_level.expected_specimen_count` expected {expected_from_payload}, got {total}.")

    if expect_count is not None and total != expect_count:
        errors.append(f"`specimen` total expected {expect_count}, got {total}.")

    if payload.get("is_valid") is True and total == 0:
        errors.append("`is_valid=true` but kept CFST specimen count is 0.")
    if payload.get("is_valid") is False and total > 0:
        errors.append("`is_valid=false` requires `Group_A`/`Group_B`/`Group_C` to be empty.")
    if payload.get("is_valid") is False and payload.get("is_ordinary_cfst") is True:
        errors.append("Invalid paper cannot be marked as ordinary CFST.")

    _validate_ordinary_scope(payload, errors, warnings)

    return errors, warnings, total


def main() -> int:
    _assert_sandbox()
    parser = argparse.ArgumentParser(
        description="Validate single-paper CFST extraction JSON v2.3. Requires CFST_SANDBOX=1."
    )
    parser.add_argument("--json-path", required=True, help="Path to extraction JSON file.")
    parser.add_argument(
        "--scratch-yaml-path",
        required=True,
        help="Path to the authoritative extraction_draft.yaml used to build the JSON.",
    )
    parser.add_argument(
        "--expect-valid",
        default=None,
        type=_as_bool,
        help="Optional expected value for `is_valid` (true/false).",
    )
    parser.add_argument(
        "--strict-rounding",
        action="store_true",
        help="Fail when numeric fields are not rounded to 0.001.",
    )
    parser.add_argument(
        "--expect-count",
        type=int,
        default=None,
        help="Optional expected total kept CFST specimen count across Group_A/B/C.",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path)
    if not json_path.exists():
        print(f"[FAIL] JSON file not found: {json_path}")
        return 1
    scratch_yaml_path = Path(args.scratch_yaml_path)
    if not scratch_yaml_path.exists():
        print(f"[FAIL] Scratch YAML file not found: {scratch_yaml_path}")
        return 1
    if yaml is None:
        print("[FAIL] PyYAML is required to validate scratch YAML consistency.")
        return 1

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[FAIL] Invalid JSON: {exc}")
        return 1

    try:
        scratch_payload = yaml.safe_load(scratch_yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"[FAIL] Invalid scratch YAML: {exc}")
        return 1

    errors, warnings, total = validate_payload(
        payload,
        args.expect_valid,
        args.strict_rounding,
        args.expect_count,
    )
    errors.extend(validate_payload_against_scratch(payload, scratch_payload))

    print(f"[INFO] Kept CFST specimen count: {total}")
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
