// Static side-by-side: original creative + heatmap. The heatmap is a server-rendered overlay
// from the inference API, so the client just displays both images.

export default function HeatmapOverlay({
  originalUrl,
  heatmapUrl,
  filename,
}: {
  originalUrl: string;
  heatmapUrl: string;
  filename: string | null;
}) {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <figure>
        <figcaption className="text-xs uppercase tracking-widest text-dim mb-2">Original</figcaption>
        <div className="bg-surface rounded overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={originalUrl} alt={filename || 'creative'} className="w-full" />
        </div>
      </figure>
      <figure>
        <figcaption className="text-xs uppercase tracking-widest text-dim mb-2">
          Predicted Attention
        </figcaption>
        <div className="bg-surface rounded overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={heatmapUrl} alt="attention heatmap" className="w-full" />
        </div>
      </figure>
    </div>
  );
}
