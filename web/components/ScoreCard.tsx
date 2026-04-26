import Link from 'next/link';

import type { Score } from '@/lib/types';

const VALENCE_COLOR: Record<string, string> = {
  positive: 'text-accent',
  neutral: 'text-muted',
  negative: 'text-accent3',
};

export default function ScoreCard({ score }: { score: Score }) {
  return (
    <Link
      href={`/score/${score.id}`}
      className="block border border-border rounded p-4 hover:border-accent transition-colors"
    >
      <div className="aspect-video bg-surface mb-3 overflow-hidden rounded">
        {/* Use plain img to avoid Next.js Image domain config issues for arbitrary Supabase URLs */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={score.saliency_heatmap_url}
          alt={score.creative_filename || 'creative'}
          className="w-full h-full object-cover"
        />
      </div>
      <div className="flex items-baseline justify-between">
        <span className="font-heading text-2xl font-bold text-accent">{score.engagement_score}</span>
        <span className="text-xs text-dim uppercase tracking-widest">Engagement</span>
      </div>
      <div className="flex items-center gap-3 mt-2 text-xs text-muted">
        <span>{score.aesthetic_score.toFixed(1)}/10 aesthetic</span>
        <span>·</span>
        <span className={VALENCE_COLOR[score.emotion_valence]}>{score.emotion_dominant}</span>
      </div>
      <p className="text-xs text-dim mt-2 truncate">{score.creative_filename}</p>
    </Link>
  );
}
