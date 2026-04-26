// POST /api/stripe-webhook
// Handles Stripe subscription lifecycle events. Updates plan + quota on the profile.

import { NextRequest, NextResponse } from 'next/server';
import type Stripe from 'stripe';

import { stripe, PLAN_QUOTAS } from '@/lib/stripe';
import { createServiceClient } from '@/lib/supabase-server';

// Stripe needs the raw body for signature verification — don't let Next.js parse it
export const runtime = 'nodejs';

export async function POST(req: NextRequest) {
  const sig = req.headers.get('stripe-signature');
  if (!sig) {
    return NextResponse.json({ error: 'Missing signature' }, { status: 400 });
  }
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) {
    return NextResponse.json({ error: 'Webhook secret not configured' }, { status: 500 });
  }

  const rawBody = await req.text();
  let event: Stripe.Event;
  try {
    event = stripe().webhooks.constructEvent(rawBody, sig, secret);
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'invalid signature';
    return NextResponse.json({ error: `Webhook verification failed: ${msg}` }, { status: 400 });
  }

  const service = createServiceClient();

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session;
      const userId = session.metadata?.supabase_user_id;
      const plan = session.metadata?.plan ?? 'entry';
      if (userId) {
        await service
          .from('profiles')
          .update({
            plan,
            stripe_subscription_id: session.subscription as string | null,
            monthly_score_quota: PLAN_QUOTAS[plan] ?? 50,
            scores_used_this_period: 0,
            period_start: new Date().toISOString(),
          })
          .eq('id', userId);
      }
      break;
    }
    case 'customer.subscription.deleted':
    case 'customer.subscription.paused': {
      const sub = event.data.object as Stripe.Subscription;
      await service
        .from('profiles')
        .update({
          plan: 'free',
          stripe_subscription_id: null,
          monthly_score_quota: PLAN_QUOTAS.free,
        })
        .eq('stripe_subscription_id', sub.id);
      break;
    }
    case 'invoice.payment_succeeded': {
      // Reset quota each successful billing cycle
      const invoice = event.data.object as Stripe.Invoice;
      const subscriptionId =
        typeof invoice.subscription === 'string' ? invoice.subscription : invoice.subscription?.id;
      if (subscriptionId) {
        await service
          .from('profiles')
          .update({
            scores_used_this_period: 0,
            period_start: new Date().toISOString(),
          })
          .eq('stripe_subscription_id', subscriptionId);
      }
      break;
    }
  }

  return NextResponse.json({ received: true });
}
