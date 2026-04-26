'use client';

export default function PrintButton() {
  return (
    <button
      onClick={() => window.print()}
      className="border border-border px-4 py-2 text-xs uppercase tracking-widest text-muted hover:text-text"
    >
      Print / Save PDF
    </button>
  );
}
