import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NeuroPulse — Predict Ad Performance Before You Spend',
  description:
    'Upload an ad creative, get a predicted engagement score, attention heatmap, and emotional response in seconds. Run two variants through the Bayesian A/B engine before launch.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
