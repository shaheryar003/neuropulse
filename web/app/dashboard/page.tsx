import Link from 'next/link';

import Nav from '@/components/Nav';
import ScoreCard from '@/components/ScoreCard';
import { createClient } from '@/lib/supabase-server';
import type { Profile, Score } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function DashboardPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null; // middleware will redirect

  const [{ data: profile }, { data: scores }] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase
      .from('scores')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(50),
  ]);

  const p = profile as Profile | null;
  const remaining = p ? p.monthly_score_quota - p.scores_used_this_period : 0;

  return (
    <main>
      <Nav />
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="flex items-end justify-between mb-12">
          <div>
            <h1 className="font-heading text-4xl font-bold mb-2">Dashboard</h1>
            <p className="text-muted text-sm">
              {p ? (
                <>
                  Plan: <span className="text-text">{p.plan}</span> · Scores remaining this period:{' '}
                  <span className={remaining > 0 ? 'text-accent' : 'text-accent3'}>
                    {Math.max(0, remaining)}/{p.monthly_score_quota}
                  </span>
                </>
              ) : (
                'Loading…'
              )}
            </p>
          </div>
          <Link
            href="/upload"
            className="bg-accent text-bg font-heading font-bold px-6 py-3 text-xs uppercase tracking-widest"
          >
            New score
          </Link>
        </div>

        {scores && scores.length > 0 ? (
          <div className="grid md:grid-cols-3 gap-6">
            {(scores as Score[]).map((s) => (
              <ScoreCard key={s.id} score={s} />
            ))}
          </div>
        ) : (
          <div className="border border-dashed border-border rounded p-16 text-center">
            <p className="text-muted mb-4">No scores yet.</p>
            <Link
              href="/upload"
              className="inline-block bg-accent text-bg font-heading font-bold px-6 py-3 text-xs uppercase tracking-widest"
            >
              Score your first creative
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
