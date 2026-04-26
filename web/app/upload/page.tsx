import Nav from '@/components/Nav';
import UploadDropzone from '@/components/UploadDropzone';
import { createClient } from '@/lib/supabase-server';
import type { Profile } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function UploadPage() {
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
  const remaining = p ? p.monthly_score_quota - p.scores_used_this_period : 0;

  return (
    <main>
      <Nav />
      <div className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="font-heading text-4xl font-bold mb-2">Score a creative</h1>
        <p className="text-muted text-sm mb-8">
          PNG or JPG, under 10 MB. {remaining > 0 ? `${remaining} scores remaining.` : 'Quota exhausted — upgrade your plan.'}
        </p>

        {remaining > 0 ? (
          <UploadDropzone userId={user.id} />
        ) : (
          <div className="border border-accent3/40 bg-accent3/5 rounded p-6">
            <h2 className="font-heading text-lg mb-2 text-accent3">Quota reached</h2>
            <p className="text-muted text-sm mb-4">
              You&apos;ve used all {p?.monthly_score_quota} scores in your current period.
            </p>
            <a
              href="/account"
              className="inline-block bg-accent text-bg font-heading font-bold px-6 py-2 text-xs uppercase tracking-widest"
            >
              Upgrade plan
            </a>
          </div>
        )}
      </div>
    </main>
  );
}
