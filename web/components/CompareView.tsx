'use client';

import { useState } from 'react';

import type { CompareResult, Score } from '@/lib/types';

export default function CompareView({
  scoreA,
  scoreB,
  initialResult,
  comparisonId,
}: {
  scoreA: Score;
  scoreB: Score;
  initialResult: CompareResult;
  comparisonId: string;
}) {
  const [result, setResult] = useState(initialResult);
  const [impressionsA, setImpressionsA] = useState('');
  const [clicksA, setClicksA] = useState('');
  const [impressionsB, setImpressionsB] = useState('');
  const [clicksB, setClicksB] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function update() {
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch('/api/compare', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          comparison_id: comparisonId,
          impressions_a: Number(impressionsA) || 0,
          clicks_a: Number(clicksA) || 0,
          impressions_b: Number(impressionsB) || 0,
          clicks_b: Number(clicksB) || 0,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.error || `Update failed: ${resp.status}`);
      }
      const next = (await resp.json()) as CompareResult;
      setResult(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  const winner = result.verdict === 'a_wins' ? 'A' : result.verdict === 'b_wins' ? 'B' : null;

  return (
    <div className="space-y-8">
      <div className="grid md:grid-cols-2 gap-4">
        <VariantPanel score={scoreA} label="A" highlight={winner === 'A'} />
        <VariantPanel score={scoreB} label="B" highlight={winner === 'B'} />
      </div>

      <div className="border border-border rounded p-6 bg-surface">
        <h3 className="font-heading text-lg mb-4">Bayesian A/B Verdict</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Metric label="P(A wins)" value={`${(result.p_a_wins * 100).toFixed(1)}%`} />
          <Metric label="P(B wins)" value={`${(result.p_b_wins * 100).toFixed(1)}%`} />
          <Metric
            label="Expected lift"
            value={`${result.expected_lift_pct >= 0 ? '+' : ''}${result.expected_lift_pct.toFixed(1)}%`}
          />
          <Metric
            label="More impressions needed"
            value={
              result.sample_size_to_significance === 0
                ? 'Already significant'
                : result.sample_size_to_significance.toLocaleString()
            }
          />
        </div>
        <p className="text-xs text-muted mt-4">
          95% credible interval for lift: [{result.credible_interval_95[0].toFixed(1)}%,{' '}
          {result.credible_interval_95[1].toFixed(1)}%]
        </p>
      </div>

      <div className="border border-border rounded p-6">
        <h3 className="font-heading text-sm uppercase tracking-widest mb-4 text-muted">
          Update with real campaign data
        </h3>
        <div className="grid md:grid-cols-2 gap-4">
          <CampaignInputs
            label="Variant A"
            impressions={impressionsA}
            clicks={clicksA}
            setImpressions={setImpressionsA}
            setClicks={setClicksA}
          />
          <CampaignInputs
            label="Variant B"
            impressions={impressionsB}
            clicks={clicksB}
            setImpressions={setImpressionsB}
            setClicks={setClicksB}
          />
        </div>
        <button
          onClick={update}
          disabled={busy}
          className="mt-4 bg-accent text-bg font-heading font-bold px-6 py-2 text-xs uppercase tracking-widest disabled:opacity-50"
        >
          {busy ? 'Updating…' : 'Update verdict'}
        </button>
        {error && <p className="text-accent3 mt-2">{error}</p>}
      </div>
    </div>
  );
}

function VariantPanel({ score, label, highlight }: { score: Score; label: string; highlight: boolean }) {
  return (
    <div className={`border rounded p-4 ${highlight ? 'border-accent' : 'border-border'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-heading text-2xl font-bold">{label}</span>
        {highlight && <span className="text-xs text-accent uppercase tracking-widest">Predicted winner</span>}
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={score.creative_url} alt={score.creative_filename || ''} className="w-full rounded mb-2" />
      <div className="flex items-baseline justify-between">
        <span className="font-heading text-3xl font-bold text-accent">{score.engagement_score}</span>
        <span className="text-xs text-dim uppercase tracking-widest">Neuro Score</span>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-dim uppercase tracking-widest mb-1">{label}</div>
      <div className="font-heading text-xl font-bold">{value}</div>
    </div>
  );
}

function CampaignInputs({
  label,
  impressions,
  clicks,
  setImpressions,
  setClicks,
}: {
  label: string;
  impressions: string;
  clicks: string;
  setImpressions: (v: string) => void;
  setClicks: (v: string) => void;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-dim mb-2">{label}</div>
      <div className="grid grid-cols-2 gap-2">
        <input
          type="number"
          min={0}
          placeholder="Impressions"
          value={impressions}
          onChange={(e) => setImpressions(e.target.value)}
          className="bg-surface border border-border rounded px-3 py-2 text-text"
        />
        <input
          type="number"
          min={0}
          placeholder="Clicks"
          value={clicks}
          onChange={(e) => setClicks(e.target.value)}
          className="bg-surface border border-border rounded px-3 py-2 text-text"
        />
      </div>
    </div>
  );
}
