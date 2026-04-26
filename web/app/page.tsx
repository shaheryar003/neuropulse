import { redirect } from 'next/navigation';

import { createServiceClient, createClient } from '@/lib/supabase-server';

export default async function LandingPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect('/dashboard');

  async function joinWaitlist(formData: FormData) {
    'use server';
    const email = (formData.get('email') as string)?.trim();
    if (!email) return;
    const service = createServiceClient();
    await service.from('waitlist').upsert({ email, source: 'landing' }, { onConflict: 'email' });
  }

  return (
    <main className="min-h-screen flex flex-col">
      <header className="px-6 py-6 flex items-center justify-between">
        <span className="font-heading font-bold text-lg bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
          NeuroPulse
        </span>
        <a href="/login" className="text-xs uppercase tracking-widest">Sign in</a>
      </header>

      <section className="flex-1 max-w-3xl mx-auto px-6 py-16 md:py-32">
        <div className="inline-flex items-center gap-2 border border-accent/30 bg-accent/5 text-accent text-xs uppercase tracking-widest px-3 py-1 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          Private beta · April 2026
        </div>

        <h1 className="font-heading text-5xl md:text-7xl font-extrabold leading-tight mb-6 bg-gradient-to-br from-white via-accent to-accent2 bg-clip-text text-transparent">
          Predict ad performance before you spend.
        </h1>

        <p className="font-serif italic text-muted text-lg leading-relaxed border-l-2 border-accent pl-4 mb-12 max-w-xl">
          Upload a creative. Get a predicted engagement score, attention heatmap, and emotional response in seconds. Run two variants through the Bayesian A/B engine to predict the winner before launch.
        </p>

        <form action={joinWaitlist} className="flex flex-col md:flex-row gap-3 max-w-md">
          <input
            type="email"
            name="email"
            required
            placeholder="you@agency.com"
            className="flex-1 bg-surface border border-border rounded px-4 py-3 text-text"
          />
          <button
            type="submit"
            className="bg-accent text-bg font-heading font-bold px-6 py-3 text-xs uppercase tracking-widest"
          >
            Join waitlist
          </button>
        </form>

        <div className="grid md:grid-cols-3 gap-6 mt-24">
          <Feature
            title="Neuroscience-grounded"
            body="Saliency models trained on real eye-tracking data. Emotion via SigLIP. Same methodology as Meta's Algonauts-winning research."
          />
          <Feature
            title="Bayesian A/B"
            body="Predict winners before launch using neuro priors. Update with real campaign data after launch — same model, no re-running tests."
          />
          <Feature
            title="Built for the mid-market"
            body="$299/mo. No procurement, no $50K studies, no two-week turnaround. Score in 5 seconds."
          />
        </div>
      </section>

      <footer className="border-t border-border px-6 py-6 text-xs text-dim flex items-center justify-between">
        <span>© NeuroPulse {new Date().getFullYear()}</span>
        <span>Confidential · Private beta</span>
      </footer>
    </main>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-l-2 border-accent pl-4">
      <h3 className="font-heading text-sm font-bold uppercase tracking-widest mb-2">{title}</h3>
      <p className="text-muted text-xs leading-relaxed">{body}</p>
    </div>
  );
}
