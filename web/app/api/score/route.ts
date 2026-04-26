// POST /api/score
// Auth: Supabase session cookie (user must be logged in)
// Flow: validate user has quota → call inference API → persist to DB → return score id

import { NextRequest, NextResponse } from 'next/server';

import { callInference } from '@/lib/api';
import { createClient, createServiceClient } from '@/lib/supabase-server';
import type { Profile } from '@/lib/types';

export async function POST(req: NextRequest) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const body = (await req.json()) as { image_url?: string; filename?: string };
  if (!body.image_url) {
    return NextResponse.json({ error: 'image_url is required' }, { status: 400 });
  }

  const { data: profileRow } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();
  const profile = profileRow as Profile | null;
  if (!profile) {
    return NextResponse.json({ error: 'Profile not found' }, { status: 500 });
  }

  if (profile.scores_used_this_period >= profile.monthly_score_quota) {
    return NextResponse.json(
      { error: 'Monthly quota exhausted. Upgrade your plan.' },
      { status: 402 }
    );
  }

  let result;
  try {
    result = await callInference({
      imageUrl: body.image_url,
      userId: user.id,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Inference failed';
    return NextResponse.json({ error: msg }, { status: 502 });
  }

  // Persist via service-role client (so we can write the row even if RLS check would mismatch user_id types)
  const service = createServiceClient();
  const { error: insertErr } = await service.from('scores').insert({
    id: result.id,
    user_id: user.id,
    creative_url: body.image_url,
    creative_filename: body.filename ?? null,
    engagement_score: result.engagement_score,
    saliency_heatmap_url: result.saliency_heatmap_url,
    aesthetic_score: result.aesthetic_score,
    emotion_valence: result.emotion.valence,
    emotion_dominant: result.emotion.dominant,
    emotion_confidence: result.emotion.confidence,
    strengths: result.strengths,
    weaknesses: result.weaknesses,
    inference_ms: result.inference_ms,
  });
  if (insertErr) {
    return NextResponse.json({ error: insertErr.message }, { status: 500 });
  }

  return NextResponse.json({ id: result.id });
}
