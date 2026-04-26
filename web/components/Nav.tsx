import Link from 'next/link';

import { createClient } from '@/lib/supabase-server';

export default async function Nav() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <header className="border-b border-border px-6 py-4 flex items-center justify-between">
      <Link href={user ? '/dashboard' : '/'} className="font-heading font-bold text-lg bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
        NeuroPulse
      </Link>
      <nav className="flex items-center gap-6 text-xs uppercase tracking-widest">
        {user ? (
          <>
            <Link href="/dashboard" className="text-muted hover:text-text">Dashboard</Link>
            <Link href="/upload" className="text-muted hover:text-text">New Score</Link>
            <Link href="/compare" className="text-muted hover:text-text">Compare</Link>
            <Link href="/account" className="text-muted hover:text-text">Account</Link>
            <form action="/api/logout" method="post">
              <button type="submit" className="text-muted hover:text-text">Sign out</button>
            </form>
          </>
        ) : (
          <Link href="/login" className="text-accent hover:text-accent2">Sign in</Link>
        )}
      </nav>
    </header>
  );
}
