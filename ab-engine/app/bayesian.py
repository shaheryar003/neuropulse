"""Bayesian A/B testing core: Beta-Binomial conjugate updating.

The neuro engagement score acts as an informative prior on the variant's true CTR.
Campaign impressions+clicks then update that prior into a posterior. We compare
posteriors to compute P(A beats B), expected lift, and credible intervals.

Why Beta-Binomial:
- Click-through is binary (clicked / didn't) → Binomial likelihood
- Beta is the conjugate prior of Binomial → posterior is also Beta (analytic)
- Allows arbitrarily small sample sizes (unlike z-tests)

Why neuro-prior-informed:
- A "naive" Bayesian A/B uses Beta(1,1) prior (uniform) — every variant equally likely to win
- Our neuro score is informative: a 75/100 score is positive evidence the CTR will be above average
- Setting alpha + beta = `prior_strength` and alpha/(alpha+beta) = mapped_ctr_prior locks in a
  prior with stated certainty. As real impressions accumulate, posterior shifts toward observed CTR.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


# Calibration: industry CTR for digital display ~1%, social feed ~1.5%, search ~3%.
# We map a neuro engagement score of 50 → 1.5% CTR, 0 → 0.5%, 100 → 3.5%.
# Linear interpolation, calibratable later from pilot data.
NEURO_BASELINE_CTR = 0.005
NEURO_TOP_CTR = 0.035


def neuro_score_to_prior_ctr(score: int) -> float:
    """Map [0, 100] engagement score to a prior CTR in [0.005, 0.035]."""
    fraction = max(0, min(100, score)) / 100.0
    return NEURO_BASELINE_CTR + (NEURO_TOP_CTR - NEURO_BASELINE_CTR) * fraction


@dataclass
class BetaPosterior:
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    def credible_interval(self, level: float = 0.95) -> tuple[float, float]:
        lo = (1 - level) / 2
        hi = 1 - lo
        return (
            float(stats.beta.ppf(lo, self.alpha, self.beta)),
            float(stats.beta.ppf(hi, self.alpha, self.beta)),
        )


def build_posterior(
    score: int,
    impressions: int = 0,
    clicks: int = 0,
    prior_strength: float = 20.0,
) -> BetaPosterior:
    """Build a posterior Beta from neuro prior + observed data.

    prior_strength = alpha + beta. Sets the "equivalent impressions" of the prior.
    """
    prior_mean = neuro_score_to_prior_ctr(score)
    alpha_prior = prior_mean * prior_strength
    beta_prior = (1 - prior_mean) * prior_strength

    # Conjugate update
    alpha_post = alpha_prior + clicks
    beta_post = beta_prior + (impressions - clicks)
    return BetaPosterior(alpha=alpha_post, beta=beta_post)


def p_a_beats_b(post_a: BetaPosterior, post_b: BetaPosterior, n_samples: int = 50_000) -> float:
    """Monte Carlo estimate of P(theta_A > theta_B).

    There is a closed-form solution involving incomplete Beta functions, but for the sample
    sizes we operate at (10K impressions max in a typical pilot test) MC with 50K samples is
    accurate to ~3 decimal places and runs in single-digit ms.
    """
    rng = np.random.default_rng(seed=42)
    samples_a = rng.beta(post_a.alpha, post_a.beta, size=n_samples)
    samples_b = rng.beta(post_b.alpha, post_b.beta, size=n_samples)
    return float(np.mean(samples_a > samples_b))


def lift_distribution(
    post_a: BetaPosterior, post_b: BetaPosterior, n_samples: int = 50_000
) -> tuple[float, tuple[float, float]]:
    """Sample the (theta_A / theta_B - 1) distribution. Returns (mean_lift_pct, 95% CI in pct)."""
    rng = np.random.default_rng(seed=42)
    a = rng.beta(post_a.alpha, post_a.beta, size=n_samples)
    b = rng.beta(post_b.alpha, post_b.beta, size=n_samples)
    lift = (a - b) / b * 100.0
    # Robust to long tails: clip outliers (b near 0 → infinite lift)
    lift = np.clip(lift, -500.0, 500.0)
    return float(np.median(lift)), (float(np.quantile(lift, 0.025)), float(np.quantile(lift, 0.975)))


def estimate_sample_size_to_significance(
    post_a: BetaPosterior,
    post_b: BetaPosterior,
    target_p: float = 0.95,
    max_total: int = 200_000,
) -> int:
    """How many MORE impressions per variant before P(winner) > target_p?

    Uses a bisection-style estimate by simulating future impressions at the current posterior mean
    until target probability is reached.
    """
    current_p = max(p_a_beats_b(post_a, post_b), 1.0 - p_a_beats_b(post_a, post_b))
    if current_p >= target_p:
        return 0

    # Project: at posterior means, how many more impressions per arm before separating?
    # Approximate using a normal approximation around current posterior.
    mean_a, mean_b = post_a.mean, post_b.mean
    var_a, var_b = post_a.variance, post_b.variance

    # As impressions n grow, variance shrinks like 1/n. Find n such that the gap |a-b| is
    # statistically separated at z = norm.ppf(target_p).
    z = stats.norm.ppf(target_p)
    diff = abs(mean_a - mean_b)
    if diff < 1e-6:
        return max_total

    # Variance of difference shrinks roughly as (mean*(1-mean))/n_extra.
    # Solve diff = z * sqrt(var_a + var_b - shrink_factor / n_extra)
    # Approximation: n_extra such that variance of difference matches z-test threshold.
    pooled_var = (mean_a * (1 - mean_a) + mean_b * (1 - mean_b))
    n_extra_per_arm = math.ceil((z**2 * pooled_var) / (diff**2))
    return min(max_total, max(0, n_extra_per_arm))


def verdict(p_a: float, threshold: float = 0.85) -> str:
    """Return verdict string based on P(A > B)."""
    if p_a >= threshold:
        return "a_wins"
    if (1.0 - p_a) >= threshold:
        return "b_wins"
    return "uncertain"
