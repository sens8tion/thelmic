"""Stream rule declarations — code-side registration of musical rules.

Every rule with status="implemented" must:
  1. Have a stable RULE-* ID in musical_rules.md
  2. Be declared here with module and test_name references
  3. Have at least one behavioural test that verifies the rule

The compliance test (tests/test_rule_compliance.py) parses musical_rules.md,
compares against this registry, and fails on any drift.

Allowed statuses
----------------
  implemented — rule is active in runtime; requires code + test
  planned     — documented; code/tests may be absent
  deprecated  — must not be active in runtime
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleDeclaration:
    """Single rule entry in the code-side registry.

    rule_id   : matches the RULE-* ID in musical_rules.md exactly
    module    : dotted path to the implementing class/method
    test_name : test class or function name (used to verify tests exist)
    status    : implemented | planned | deprecated
    """
    rule_id:   str
    module:    str
    test_name: str
    status:    str = "implemented"

    def __post_init__(self) -> None:
        assert self.rule_id.startswith("RULE-"), (
            f"rule_id must start with RULE-: {self.rule_id}"
        )
        assert self.status in ("implemented", "planned", "deprecated"), (
            f"invalid status '{self.status}' for {self.rule_id}"
        )
        if self.status == "implemented":
            assert self.module, f"{self.rule_id}: module required for implemented rule"
            assert self.test_name, f"{self.rule_id}: test_name required for implemented rule"


# ---------------------------------------------------------------------------
# Kick rules
# ---------------------------------------------------------------------------

KICK_RULES: tuple[RuleDeclaration, ...] = (
    RuleDeclaration(
        rule_id="RULE-KICK-001",
        module="stream_drums.KickIntentStream._pattern_for_frame",
        test_name="TestOakKickPattern",
    ),
    RuleDeclaration(
        rule_id="RULE-KICK-002",
        module="stream_drums.KickIntentStream._pattern_for_frame",
        test_name="TestChaosKickPattern::test_chaos_scales_with_density",
    ),
    RuleDeclaration(
        rule_id="RULE-KICK-003",
        module="stream_drums.KickIntentStream.intents_for_frame",
        test_name="TestSilenceGate",
    ),
    RuleDeclaration(
        rule_id="RULE-KICK-004",
        module="stream_drums.KickIntentStream._drop_intent",
        test_name="TestDropAndRelockAlwaysFire",
    ),
    RuleDeclaration(
        rule_id="RULE-KICK-005",
        module="stream_drums.KickIntentStream._velocity",
        test_name="TestTerritoryDifference::test_velocity_profile_differs_by_territory",
    ),
)

# ---------------------------------------------------------------------------
# Hat rules
# ---------------------------------------------------------------------------

HAT_RULES: tuple[RuleDeclaration, ...] = (
    RuleDeclaration(
        rule_id="RULE-HAT-001",
        module="stream_drums.HatIntentStream.intents_for_frame",
        test_name="test_stream_hat_uses_structure_frame_step_and_density",
    ),
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_RULES: tuple[RuleDeclaration, ...] = KICK_RULES + HAT_RULES

IMPLEMENTED_RULE_IDS: frozenset[str] = frozenset(
    r.rule_id for r in ALL_RULES if r.status == "implemented"
)

PLANNED_RULE_IDS: frozenset[str] = frozenset(
    r.rule_id for r in ALL_RULES if r.status == "planned"
)

DEPRECATED_RULE_IDS: frozenset[str] = frozenset(
    r.rule_id for r in ALL_RULES if r.status == "deprecated"
)
