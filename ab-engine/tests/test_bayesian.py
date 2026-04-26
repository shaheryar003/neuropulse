"""Sanity tests for the Bayesian A/B engine."""
from __future__ import annotations

import pytest

from app.bayesian import (
    build_posterior,
    estimate_sample_size_to_significance,
    lift_distribution,
    neuro_score_to_prior_ctr,
    p_a_beats_b,
    verdict,
)


def test_neuro_score_mapping_is_monotonic():
    """Higher neuro scores must map to higher prior CTRs."""
    assert neuro_score_to_prior_ctr(0) < neuro_score_to_prior_ctr(50)
    assert neuro_score_to_prior_ctr(50) < neuro_score_to_prior_ctr(100)
    assert neuro_score_to_prior_ctr(100) <= 0.05  # Sanity: not absurdly high


def test_equal_priors_no_data_50_50():
    """Two equal priors with no data → ~50% probability either wins."""
    post = build_posterior(score=50)
    p = p_a_beats_b(post, post)
    assert 0.45 < p < 0.55


def test_data_overrides_prior():
    """If A has 100 impressions / 10 clicks (10% CTR) and B has 100/0, A should win convincingly
    even if A starts with a worse neuro score."""
    post_a = build_posterior(score=30, impressions=100, clicks=10)
    post_b = build_posterior(score=80, impressions=100, clicks=0)
    p_a = p_a_beats_b(post_a, post_b)
    assert p_a > 0.95


def test_neuro_prior_breaks_ties():
    """With zero campaign data, a higher neuro score should win with > 50% probability."""
    post_a = build_posterior(score=80)
    post_b = build_posterior(score=40)
    p_a = p_a_beats_b(post_a, post_b)
    assert p_a > 0.55


def test_verdict_thresholds():
    assert verdict(0.97) == "a_wins"
    assert verdict(0.03) == "b_wins"
    assert verdict(0.5) == "uncertain"
    assert verdict(0.84) == "uncertain"
    assert verdict(0.86) == "a_wins"


def test_sample_size_zero_when_already_significant():
    """If we already have a strong winner, no more samples needed."""
    post_a = build_posterior(score=50, impressions=10000, clicks=500)   # 5% CTR
    post_b = build_posterior(score=50, impressions=10000, clicks=100)   # 1% CTR
    n = estimate_sample_size_to_significance(post_a, post_b)
    assert n == 0


def test_credible_interval_contains_mean():
    post = build_posterior(score=70, impressions=500, clicks=20)
    lo, hi = post.credible_interval(0.95)
    assert lo < post.mean < hi


def test_lift_pct_directionally_correct():
    """If A has higher CTR, lift should be positive."""
    post_a = build_posterior(score=50, impressions=1000, clicks=50)   # 5%
    post_b = build_posterior(score=50, impressions=1000, clicks=20)   # 2%
    median_lift, (lo, hi) = lift_distribution(post_a, post_b)
    assert median_lift > 0
    assert lo < median_lift < hi
