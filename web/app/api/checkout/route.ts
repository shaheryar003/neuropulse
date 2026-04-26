// POST /api/checkout
// Creates a Stripe Checkout session for the Entry plan and redirects there.

import { NextResponse } from 'next/server';

import { stripe, PLAN_TO_PRICE_ID } from '@/lib/stripe';
import { createClient, createServiceClient } from '@/lib/supabase-server';
import type { Profile } from '@/lib/types';

export async function POST() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const priceId = PLAN_TO_PRICE_ID.entry;
  if (!priceId) {
    return NextResponse.json({ error: 'Entry plan not configured' }, { status: 500 });
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

  // Create or reuse Stripe customer
  let customerId = profile.stripe_customer_id;
  if (!customerId) {
    const customer = await stripe().customers.create({
      email: profile.email,
      metadata: { supabase_user_id: user.id },
    });
    customerId = customer.id;
    const service = createServiceClient();
    await service.from('profiles').update({ stripe_customer_id: customerId }).eq('id', user.id);
  }

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000';
  const session = await stripe().checkout.sessions.create({
    mode: 'subscription',
    customer: customerId,
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: `${siteUrl}/account?checkout=success`,
    cancel_url: `${siteUrl}/account?checkout=cancelled`,
    metadata: { supabase_user_id: user.id, plan: 'entry' },
  });

  if (!session.url) {
    return NextResponse.json({ error: 'Stripe did not return a checkout URL' }, { status: 500 });
  }
  return NextResponse.redirect(session.url, { status: 303 });
}
