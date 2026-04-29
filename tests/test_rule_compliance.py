"""Stream rule compliance test.

Enforces the markdown ⇄ code ⇄ test triangle:

  musical_rules.md        — human-readable source of truth with RULE-* IDs
  thelmic/stream_rules.py — code-side registry of implemented rules
  tests/test_*            — behavioural tests proving each rule works

Fails if:
  - a RULE-* ID in the markdown has no declaration in stream_rules.py
  - a declaration in stream_rules.py has no RULE-* ID in the markdown
  - a rule is declared "implemented" but its test_name cannot be found
  - duplicate RULE-* IDs appear in the markdown
  - duplicate rule_id values appear in the registry

Scope: only RULE-* IDs found in musical_rules.md and stream_rules.py are
checked. Legacy reference material without RULE-* IDs is ignored.

Run with:
  pytest tests/test_rule_compliance.py -v
"""

from __future__ import annotations

import pathlib
import re

import pytest

from thelmic.stream_rules import ALL_RULES, RuleDeclaration

# ---------------------------------------------------------------------------
# Locate files
# ---------------------------------------------------------------------------

_REPO_ROOT   = pathlib.Path(__file__).parent.parent
_RULES_MD    = _REPO_ROOT / "musical_rules.md"
_TESTS_DIR   = _REPO_ROOT / "tests"

assert _RULES_MD.exists(),  f"musical_rules.md not found at {_RULES_MD}"
assert _TESTS_DIR.exists(), f"tests/ directory not found at {_TESTS_DIR}"


# ---------------------------------------------------------------------------
# Parse musical_rules.md for RULE-* IDs
# ---------------------------------------------------------------------------

_RULE_ID_PATTERN = re.compile(r"\bRULE-[A-Z]+-\d{3}\b")


def _parse_doc_rule_ids() -> dict[str, int]:
    """Return {rule_id: occurrence_count} for every RULE-* ID in the markdown."""
    text = _RULES_MD.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    for match in _RULE_ID_PATTERN.finditer(text):
        rule_id = match.group()
        counts[rule_id] = counts.get(rule_id, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Parse test files for test class / function names
# ---------------------------------------------------------------------------

def _collect_test_names() -> frozenset[str]:
    """Return the set of all test class and function names found in tests/."""
    names: set[str] = set()
    for path in _TESTS_DIR.glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        # class names: 'class TestFoo:'
        for m in re.finditer(r"class\s+(Test\w+)", text):
            names.add(m.group(1))
        # function names: 'def test_foo'
        for m in re.finditer(r"def\s+(test_\w+)", text):
            names.add(m.group(1))
    return frozenset(names)


# ---------------------------------------------------------------------------
# Registry validation
# ---------------------------------------------------------------------------

def _registry_rule_ids() -> list[str]:
    return [r.rule_id for r in ALL_RULES]


def _implemented_rules() -> tuple[RuleDeclaration, ...]:
    return tuple(r for r in ALL_RULES if r.status == "implemented")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMarkdownRuleIds:
    """Markdown integrity: every RULE-* ID must appear at least once and be unique."""

    def test_markdown_contains_at_least_one_rule_id(self):
        ids = _parse_doc_rule_ids()
        assert ids, "No RULE-* IDs found in musical_rules.md"

    def test_no_duplicate_rule_ids_in_markdown(self):
        counts = _parse_doc_rule_ids()
        # Each ID may appear multiple times in the same section header + body,
        # but the header line (### RULE-*) should appear exactly once.
        header_pattern = re.compile(r"^###\s+(RULE-[A-Z]+-\d{3})\b", re.MULTILINE)
        text = _RULES_MD.read_text(encoding="utf-8")
        header_counts: dict[str, int] = {}
        for m in header_pattern.finditer(text):
            rid = m.group(1)
            header_counts[rid] = header_counts.get(rid, 0) + 1
        duplicates = {rid: n for rid, n in header_counts.items() if n > 1}
        assert not duplicates, (
            f"Duplicate rule section headers in musical_rules.md: {duplicates}"
        )


class TestRegistryIntegrity:
    """Registry integrity: no duplicates, valid fields."""

    def test_no_duplicate_rule_ids_in_registry(self):
        ids = _registry_rule_ids()
        seen: set[str] = set()
        duplicates: list[str] = []
        for rid in ids:
            if rid in seen:
                duplicates.append(rid)
            seen.add(rid)
        assert not duplicates, f"Duplicate rule_id in stream_rules.py: {duplicates}"

    def test_all_implemented_rules_have_module(self):
        for rule in _implemented_rules():
            assert rule.module, f"{rule.rule_id}: module is empty"

    def test_all_implemented_rules_have_test_name(self):
        for rule in _implemented_rules():
            assert rule.test_name, f"{rule.rule_id}: test_name is empty"


class TestDocCodeAlignment:
    """Every registry rule must appear in the markdown, and vice versa."""

    def test_all_registry_rules_appear_in_markdown(self):
        doc_ids = _parse_doc_rule_ids()
        missing = [r.rule_id for r in ALL_RULES if r.rule_id not in doc_ids]
        assert not missing, (
            f"Rules declared in stream_rules.py but missing from musical_rules.md:\n"
            + "\n".join(f"  {r}" for r in missing)
        )

    def test_all_markdown_rules_appear_in_registry(self):
        # Only check IDs that appear as section headers (### RULE-*)
        header_pattern = re.compile(r"^###\s+(RULE-[A-Z]+-\d{3})\b", re.MULTILINE)
        text = _RULES_MD.read_text(encoding="utf-8")
        doc_header_ids = frozenset(m.group(1) for m in header_pattern.finditer(text))
        registry_ids   = frozenset(_registry_rule_ids())
        missing = doc_header_ids - registry_ids
        assert not missing, (
            f"Rules with section headers in musical_rules.md but missing from "
            f"stream_rules.py registry:\n"
            + "\n".join(f"  {r}" for r in sorted(missing))
        )


class TestImplementedRulesHaveTests:
    """Every 'implemented' rule must reference a test that exists."""

    def test_all_implemented_rule_test_names_exist(self):
        available = _collect_test_names()
        missing: list[tuple[str, str]] = []
        for rule in _implemented_rules():
            # test_name may be "ClassName::method_name" or just "ClassName"
            # or just "function_name" — check the first component
            first = rule.test_name.split("::")[0].strip()
            if first not in available:
                missing.append((rule.rule_id, first))
        assert not missing, (
            f"Implemented rules reference tests that do not exist:\n"
            + "\n".join(f"  {rid}: {tname}" for rid, tname in missing)
        )


class TestNoDeprecatedRulesInRuntime:
    """Deprecated rules must not be referenced in active stream voice modules."""

    def test_deprecated_rule_ids_not_in_stream_voices(self):
        from thelmic.stream_rules import DEPRECATED_RULE_IDS
        if not DEPRECATED_RULE_IDS:
            return  # nothing to check yet
        # Check that deprecated IDs don't appear as strings in active stream modules
        stream_files = [
            _REPO_ROOT / "thelmic" / "stream_drums.py",
            _REPO_ROOT / "thelmic" / "stream_hooks.py",
            _REPO_ROOT / "thelmic" / "stream_voices.py",
        ]
        for path in stream_files:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for rid in DEPRECATED_RULE_IDS:
                assert rid not in text, (
                    f"Deprecated rule {rid} still referenced in {path.name}"
                )


# ---------------------------------------------------------------------------
# Smoke test: registry imports cleanly
# ---------------------------------------------------------------------------

def test_stream_rules_module_imports():
    from thelmic.stream_rules import (
        ALL_RULES, IMPLEMENTED_RULE_IDS, PLANNED_RULE_IDS, DEPRECATED_RULE_IDS,
    )
    assert ALL_RULES
    assert IMPLEMENTED_RULE_IDS
    # Sets should be disjoint
    assert IMPLEMENTED_RULE_IDS.isdisjoint(PLANNED_RULE_IDS)
    assert IMPLEMENTED_RULE_IDS.isdisjoint(DEPRECATED_RULE_IDS)
