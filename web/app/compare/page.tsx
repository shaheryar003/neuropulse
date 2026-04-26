import Link from 'next/link';

import CompareView from '@/components/CompareView';
import Nav from '@/components/Nav';
import { callCompare } from '@/lib/api';
import { createClient, createServiceClient } from '@/lib/supabase-server';
import type { Score } from '@/lib/types';

export const dynamic = 'force-dynamic';

interface SearchParams {
  a?: string;
  b?: string;
}

export default async function ComparePage({ searchParams }: { searchParams: SearchParams }) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  const { a, b } = searchParams;

  if (!a || !b) {
    const { data: scores } = await supabase
      .from('scores')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(100);

    return (
      <main>
        <Nav />
        <div className="max-w-3xl mx-auto px-6 py-12">
          <h1 className="font-heading text-3xl font-bold mb-2">Compare two creatives</h1>
          <p className="text-muted text-sm mb-8">
            Pick two scored creatives to run through the Bayesian A/B engine.
          </p>
          {scores && scores.length >= 2 ? (
            <SelectForm scores={scores as Score[]} />
          ) : (
            <p className="text-muted">
              You need at least two scored creatives. <Link href="/upload" className="text-accent">Score one now.</Link>
            </p>
          )}
        </div>
      </main>
    );
  }

  // Both selected — load, run compare, persist
  const [{ data: scoreA }, { data: scoreB }] = await Promise.all([
    supabase.from('scores').select('*').eq('id', a).eq('user_id', user.id).single(),
    supabase.from('scores').select('*').eq('id', b).eq('user_id', user.id).single(),
  ]);

  if (!scoreA || !scoreB) {
    return (
      <main>
        <Nav />
        <div className="max-w-3xl mx-auto px-6 py-12">
          <p className="text-muted">One or both creatives not found.</p>
        </div>
      </main>
    );
  }

  const sA = scoreA as Score;
  const sB = scoreB as Score;

  const result = await callCompare({
    scoreA: sA.engagement_score,
    scoreB: sB.engagement_score,
  });

  // Upsert comparison row
  const service = createServiceClient();
  const comparisonId = `cmp_${a.slice(-6)}_${b.slice(-6)}`;
  await service.from('comparisons').upsert(
    {
      id: comparisonId,
      user_id: user.id,
      score_id_a: a,
      score_id_b: b,
      p_a_wins: result.p_a_wins,
      expected_lift_pct: result.expected_lift_pct,
      credible_interval_low: result.credible_interval_95[0],
      credible_interval_high: result.credible_interval_95[1],
      sample_size_to_significance: result.sample_size_to_significance,
      verdict: result.verdict,
      last_updated_at: new Date().toISOString(),
    },
    { onConflict: 'id' }
  );

  return (
    <main>
      <Nav />
      <div className="max-w-5xl mx-auto px-6 py-12">
        <h1 className="font-heading text-3xl font-bold mb-8">Variant comparison</h1>
        <CompareView scoreA={sA} scoreB={sB} initialResult={result} comparisonId={comparisonId} />
      </div>
    </main>
  );
}

function SelectForm({ scores }: { scores: Score[] }) {
  return (
    <form action="/compare" method="GET" className="space-y-4">
      <div>
        <label className="text-xs text-dim uppercase tracking-widest block mb-2">Variant A</label>
        <select name="a" required className="w-full bg-surface border border-border rounded px-3 py-2">
          {scores.map((s) => (
            <option key={s.id} value={s.id}>
              {s.creative_filename || s.id} (score {s.engagement_score})
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="text-xs text-dim uppercase tracking-widest block mb-2">Variant B</label>
        <select name="b" required className="w-full bg-surface border border-border rounded px-3 py-2">
          {scores.map((s) => (
            <option key={s.id} value={s.id}>
              {s.creative_filename || s.id} (score {s.engagement_score})
            </option>
          ))}
        </select>
      </div>
      <button
        type="submit"
        className="bg-accent text-bg font-heading font-bold px-6 py-2 text-xs uppercase tracking-widest"
      >
        Compare
      </button>
    </form>
  );
}
