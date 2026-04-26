// PUT /api/compare
// Update a comparison with real campaign data and re-run the Bayesian update.

import { NextRequest, NextResponse } from 'next/server';

import { callCompare } from '@/lib/api';
import { createClient, createServiceClient } from '@/lib/supabase-server';
import type { Comparison, Score } from '@/lib/types';

export async function PUT(req: NextRequest) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const body = (await req.json()) as {
    comparison_id: string;
    impressions_a: number;
    clicks_a: number;
    impressions_b: number;
    clicks_b: number;
  };

  if (!body.comparison_id) {
    return NextResponse.json({ error: 'comparison_id is required' }, { status: 400 });
  }
  if (body.clicks_a > body.impressions_a || body.clicks_b > body.impressions_b) {
    return NextResponse.json(
      { error: 'Clicks cannot exceed impressions' },
      { status: 400 }
    );
  }

  const { data: comparisonRow } = await supabase
    .from('comparisons')
    .select('*')
    .eq('id', body.comparison_id)
    .eq('user_id', user.id)
    .single();
  const comparison = comparisonRow as Comparison | null;
  if (!comparison) {
    return NextResponse.json({ error: 'Comparison not found' }, { status: 404 });
  }

  const [{ data: scoreA }, { data: scoreB }] = await Promise.all([
    supabase.from('scores').select('*').eq('id', comparison.score_id_a).single(),
    supabase.from('scores').select('*').eq('id', comparison.score_id_b).single(),
  ]);
  if (!scoreA || !scoreB) {
    return NextResponse.json({ error: 'Scores not found' }, { status: 404 });
  }

  let result;
  try {
    result = await callCompare({
      scoreA: (scoreA as Score).engagement_score,
      scoreB: (scoreB as Score).engagement_score,
      campaignA:
        body.impressions_a > 0 ? { impressions: body.impressions_a, clicks: body.clicks_a } : undefined,
      campaignB:
        body.impressions_b > 0 ? { impressions: body.impressions_b, clicks: body.clicks_b } : undefined,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Compare failed';
    return NextResponse.json({ error: msg }, { status: 502 });
  }

  const service = createServiceClient();
  await service
    .from('comparisons')
    .update({
      impressions_a: body.impressions_a,
      clicks_a: body.clicks_a,
      impressions_b: body.impressions_b,
      clicks_b: body.clicks_b,
      p_a_wins: result.p_a_wins,
      expected_lift_pct: result.expected_lift_pct,
      credible_interval_low: result.credible_interval_95[0],
      credible_interval_high: result.credible_interval_95[1],
      sample_size_to_significance: result.sample_size_to_significance,
      verdict: result.verdict,
      last_updated_at: new Date().toISOString(),
    })
    .eq('id', body.comparison_id);

  return NextResponse.json(result);
}
