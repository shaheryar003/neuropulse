import { notFound } from 'next/navigation';

import HeatmapOverlay from '@/components/HeatmapOverlay';
import Nav from '@/components/Nav';
import PrintButton from '@/components/PrintButton';
import { createClient } from '@/lib/supabase-server';
import type { Score } from '@/lib/types';

export const dynamic = 'force-dynamic';

const VALENCE_COLOR: Record<string, string> = {
  positive: 'text-accent',
  neutral: 'text-muted',
  negative: 'text-accent3',
};

export default async function ScorePage({ params }: { params: { id: string } }) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  const { data: scoreRow } = await supabase
    .from('scores')
    .select('*')
    .eq('id', params.id)
    .eq('user_id', user.id)
    .single();
  if (!scoreRow) notFound();

  const s = scoreRow as Score;

  return (
    <main>
      <Nav />
      <div className="max-w-5xl mx-auto px-6 py-12 print:py-4">
        <header className="flex items-end justify-between mb-8 no-print">
          <div>
            <h1 className="font-heading text-3xl font-bold">{s.creative_filename || 'Untitled creative'}</h1>
            <p className="text-muted text-xs">
              Scored {new Date(s.created_at).toLocaleString()} · {s.inference_ms} ms
            </p>
          </div>
          <PrintButton />
        </header>

        <section className="grid md:grid-cols-4 gap-6 mb-12">
          <Stat label="Engagement Score" value={`${s.engagement_score}`} accent />
          <Stat label="Aesthetic" value={`${s.aesthetic_score.toFixed(1)}/10`} />
          <Stat label="Emotion" value={s.emotion_dominant} className={VALENCE_COLOR[s.emotion_valence]} />
          <Stat label="Confidence" value={`${(s.emotion_confidence * 100).toFixed(0)}%`} />
        </section>

        <section className="mb-12">
          <HeatmapOverlay
            originalUrl={s.creative_url}
            heatmapUrl={s.saliency_heatmap_url}
            filename={s.creative_filename}
          />
        </section>

        <section className="grid md:grid-cols-2 gap-8">
          <Bullets title="Strengths" items={s.strengths} accent />
          <Bullets title="Weaknesses" items={s.weaknesses} />
        </section>
      </div>
    </main>
  );
}

function Stat({
  label,
  value,
  accent = false,
  className = '',
}: {
  label: string;
  value: string;
  accent?: boolean;
  className?: string;
}) {
  return (
    <div className="border border-border rounded p-4">
      <div className="text-xs text-dim uppercase tracking-widest mb-2">{label}</div>
      <div
        className={`font-heading text-3xl font-bold ${accent ? 'text-accent' : ''} ${className}`}
      >
        {value}
      </div>
    </div>
  );
}

function Bullets({ title, items, accent = false }: { title: string; items: string[]; accent?: boolean }) {
  return (
    <div>
      <h2 className={`font-heading text-sm uppercase tracking-widest mb-4 ${accent ? 'text-accent' : 'text-accent3'}`}>
        {title}
      </h2>
      <ul className="space-y-3">
        {items.map((item, i) => (
          <li key={i} className="text-text leading-relaxed pl-4 relative">
            <span className={`absolute left-0 ${accent ? 'text-accent' : 'text-accent3'}`}>→</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
