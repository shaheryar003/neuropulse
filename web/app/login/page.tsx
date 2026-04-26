'use client';

import { useState } from 'react';

import { createClient } from '@/lib/supabase-client';

export default function LoginPage() {
  const supabase = createClient();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/dashboard`,
      },
    });
    setBusy(false);
    if (error) setError(error.message);
    else setSent(true);
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        <a href="/" className="font-heading font-bold text-lg bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
          NeuroPulse
        </a>
        <h1 className="font-heading text-3xl font-bold mt-8 mb-2">Sign in</h1>
        <p className="text-muted text-sm mb-8">
          We&apos;ll email you a magic link. No passwords.
        </p>

        {sent ? (
          <div className="border-l-2 border-accent pl-4 py-2">
            <p className="text-text">Check your email.</p>
            <p className="text-xs text-muted mt-1">If you don&apos;t see it within a minute, check spam.</p>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (email) void send();
            }}
            className="space-y-4"
          >
            <input
              type="email"
              required
              placeholder="you@agency.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-surface border border-border rounded px-4 py-3"
            />
            <button
              type="submit"
              disabled={busy || !email}
              className="w-full bg-accent text-bg font-heading font-bold px-6 py-3 text-xs uppercase tracking-widest disabled:opacity-50"
            >
              {busy ? 'Sending…' : 'Send magic link'}
            </button>
            {error && <p className="text-accent3 text-xs">{error}</p>}
          </form>
        )}
      </div>
    </main>
  );
}
