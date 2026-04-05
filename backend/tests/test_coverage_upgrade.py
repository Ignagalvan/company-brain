"""
test_coverage_upgrade.py

Unit tests for the coverage upgrade logic in message_service.

Tests the pure function _should_upgrade_to_full, which decides whether a
'partial' coverage judgment from the LLM judge should be upgraded to 'full'.

No DB, no mocks, no network — pure logic only.
"""

import pytest

from src.services.message_service import (
    _MAX_TOLERATED_MISSING,
    _UPGRADE_THRESHOLD_MULTI,
    _UPGRADE_THRESHOLD_SINGLE,
    _should_upgrade_to_full,
)


# ─── 1. Single-fragment cases (lower threshold) ──────────────────────────────

def test_single_fragment_no_missing_upgrades():
    """1 fragment + high score + no missing → upgrade to full."""
    assert _should_upgrade_to_full("partial", 0.75, 1, []) is True


def test_single_fragment_one_minor_missing_upgrades():
    """1 fragment + high score + 1 tangential missing point → still upgrades."""
    assert _should_upgrade_to_full("partial", 0.70, 1, ["detalle secundario"]) is True


def test_single_fragment_at_threshold_upgrades():
    """Score exactly at the single-fragment threshold → upgrades."""
    assert _should_upgrade_to_full("partial", _UPGRADE_THRESHOLD_SINGLE, 1, []) is True


def test_single_fragment_below_threshold_no_upgrade():
    """Score just below the single-fragment threshold → does NOT upgrade."""
    score = round(_UPGRADE_THRESHOLD_SINGLE - 0.01, 4)
    assert _should_upgrade_to_full("partial", score, 1, []) is False


# ─── 2. Multi-fragment cases (higher threshold) ───────────────────────────────

def test_multi_fragment_at_threshold_upgrades():
    """Score exactly at the multi-fragment threshold → upgrades."""
    assert _should_upgrade_to_full("partial", _UPGRADE_THRESHOLD_MULTI, 2, []) is True


def test_multi_fragment_above_threshold_upgrades():
    assert _should_upgrade_to_full("partial", 0.80, 3, []) is True


def test_multi_fragment_below_threshold_no_upgrade():
    """Score between single and multi threshold with 2 fragments → no upgrade."""
    score = round(_UPGRADE_THRESHOLD_MULTI - 0.01, 4)
    assert _should_upgrade_to_full("partial", score, 2, []) is False


def test_multi_fragment_single_threshold_not_enough():
    """_UPGRADE_THRESHOLD_SINGLE < _UPGRADE_THRESHOLD_MULTI for 2+ fragments."""
    # score is above single threshold but below multi threshold
    score = (_UPGRADE_THRESHOLD_SINGLE + _UPGRADE_THRESHOLD_MULTI) / 2
    if _UPGRADE_THRESHOLD_SINGLE < score < _UPGRADE_THRESHOLD_MULTI:
        assert _should_upgrade_to_full("partial", score, 2, []) is False
    else:
        pytest.skip("Thresholds are equal — test not meaningful")


# ─── 3. Missing points tolerance ─────────────────────────────────────────────

def test_two_missing_points_within_tolerance_upgrades():
    """2 missing points ≤ _MAX_TOLERATED_MISSING=2 + good score → upgrades."""
    assert _should_upgrade_to_full("partial", 0.70, 1, ["punto A", "punto B"]) is True


def test_three_missing_points_no_upgrade():
    """3 missing points > _MAX_TOLERATED_MISSING → always stays partial."""
    assert _should_upgrade_to_full("partial", 0.99, 2, ["A", "B", "C"]) is False


def test_exactly_max_tolerated_missing_can_upgrade():
    """Exactly _MAX_TOLERATED_MISSING missing points → eligible if score ok."""
    missing = ["tangential point"] * _MAX_TOLERATED_MISSING
    assert _should_upgrade_to_full("partial", 0.70, 1, missing) is True


def test_one_over_max_tolerated_no_upgrade():
    missing = ["point"] * (_MAX_TOLERATED_MISSING + 1)
    assert _should_upgrade_to_full("partial", 0.90, 1, missing) is False


# ─── 4. No evidence → no upgrade ─────────────────────────────────────────────

def test_no_evidence_chunks_no_upgrade():
    """evidence_count=0 → never upgrade regardless of score."""
    assert _should_upgrade_to_full("partial", 0.99, 0, []) is False


# ─── 5. Non-partial coverage → no change ─────────────────────────────────────

def test_full_coverage_not_touched():
    """Already 'full' → function returns False (no change needed)."""
    assert _should_upgrade_to_full("full", 0.90, 2, []) is False


def test_none_coverage_not_upgraded():
    """'none' → no upgrade."""
    assert _should_upgrade_to_full("none", 0.90, 1, []) is False


# ─── 6. Edge / boundary values ───────────────────────────────────────────────

def test_zero_score_no_upgrade():
    assert _should_upgrade_to_full("partial", 0.0, 1, []) is False


def test_perfect_score_no_evidence_no_upgrade():
    assert _should_upgrade_to_full("partial", 1.0, 0, []) is False


def test_perfect_score_with_evidence_upgrades():
    assert _should_upgrade_to_full("partial", 1.0, 1, []) is True
