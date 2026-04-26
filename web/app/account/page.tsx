import Nav from '@/components/Nav';
import { createClient } from '@/lib/supabase-server';
import type { Profile } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function AccountPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();
  const p = profile as Profile | null;

  return (
    <main>
      <Nav />
      <div className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="font-heading text-3xl font-bold mb-2">Account</h1>
        <p className="text-muted text-sm mb-12">{user.email}</p>

        <section className="border border-border rounded p-6 mb-8">
          <h2 className="font-heading text-sm uppercase tracking-widest text-muted mb-4">
            Current plan
          </h2>
          <div className="flex items-baseline justify-between mb-4">
            <span className="font-heading text-3xl font-bold capitalize">{p?.plan || 'free'}</span>
            <span className="text-muted text-xs">
              {p?.scores_used_this_period}/{p?.monthly_score_quota} scores used
            </span>
          </div>
          {p?.plan === 'free' && (
            <form action="/api/checkout" method="POST">
              <button
                type="submit"
                className="bg-accent text-bg font-heading font-bold px-6 py-2 text-xs uppercase tracking-widest"
              >
                Upgrade to Entry — $299/mo
              </button>
            </form>
          )}
          {p?.plan !== 'free' && p?.stripe_subscription_id && (
            <p className="text-muted text-xs">
              Manage your subscription in your Stripe customer portal (a link will be emailed on request).
            </p>
          )}
        </section>

        <section className="border border-border rounded p-6">
          <h2 className="font-heading text-sm uppercase tracking-widest text-muted mb-4">
            Plan tiers
          </h2>
          <div className="space-y-3 text-sm">
            <PlanRow name="Free" price="$0" features="5 scores/month · single user" />
            <PlanRow name="Entry" price="$299/mo" features="50 scores/month · A/B engine · share-link reports" current={p?.plan === 'entry'} />
            <PlanRow name="Agency" price="$999/mo" features="200 scores/month · multi-client (Phase 2)" disabled />
            <PlanRow name="White-label" price="$2,499/mo" features="unlimited · branded reports (Phase 2)" disabled />
          </div>
        </section>
      </div>
    </main>
  );
}

function PlanRow({
  name,
  price,
  features,
  current = false,
  disabled = false,
}: {
  name: string;
  price: string;
  features: string;
  current?: boolean;
  disabled?: boolean;
}) {
  return (
    <div
      className={`flex items-baseline justify-between border-l-2 pl-3 py-2 ${
        current ? 'border-accent' : 'border-border'
      } ${disabled ? 'opacity-50' : ''}`}
    >
      <div>
        <div className="font-heading font-bold">
          {name} {current && <span className="text-xs text-accent">· current</span>}
          {disabled && <span className="text-xs text-dim"> · coming Phase 2</span>}
        </div>
        <div className="text-xs text-muted">{features}</div>
      </div>
      <div className="font-heading font-bold">{price}</div>
    </div>
  );
}
