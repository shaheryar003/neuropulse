'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { createClient } from '@/lib/supabase-client';

export default function UploadDropzone({ userId }: { userId: string }) {
  const supabase = createClient();
  const router = useRouter();
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>('');

  async function handleFile(file: File) {
    setError(null);
    setBusy(true);
    try {
      if (!file.type.startsWith('image/')) {
        throw new Error('Only image files are supported in this version.');
      }
      if (file.size > 10 * 1024 * 1024) {
        throw new Error('Image must be under 10 MB.');
      }

      setProgress('Uploading creative...');
      const path = `${userId}/${Date.now()}_${file.name}`;
      const { error: upErr } = await supabase.storage
        .from('creatives')
        .upload(path, file, { contentType: file.type, upsert: false });
      if (upErr) throw upErr;

      const {
        data: { publicUrl },
      } = supabase.storage.from('creatives').getPublicUrl(path);

      setProgress('Scoring (this takes ~5 seconds)...');
      const resp = await fetch('/api/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: publicUrl, filename: file.name }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.error || `Score failed: ${resp.status}`);
      }

      const { id } = await resp.json();
      router.push(`/score/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
      setBusy(false);
      setProgress('');
    }
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) void handleFile(f);
        }}
        className={`border border-dashed rounded p-12 text-center transition-colors ${
          dragging ? 'border-accent bg-surface' : 'border-border'
        } ${busy ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <p className="text-muted mb-4">
          {busy ? progress : 'Drop an image here, or click to choose a file'}
        </p>
        <input
          type="file"
          accept="image/*"
          className="hidden"
          id="file-input"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFile(f);
          }}
        />
        <label
          htmlFor="file-input"
          className="inline-block bg-accent text-bg font-heading font-bold px-6 py-2 text-xs uppercase tracking-widest cursor-pointer"
        >
          {busy ? 'Working…' : 'Choose file'}
        </label>
      </div>
      {error && <p className="mt-4 text-accent3">{error}</p>}
    </div>
  );
}
