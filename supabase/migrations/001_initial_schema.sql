-- NeuroPulse — initial schema
-- Run with: psql $SUPABASE_DB_URL -f supabase/migrations/001_initial_schema.sql

-- ============================================================
-- USERS PROFILE
-- Mirror of auth.users with billing/quota state. Linked 1:1.
-- ============================================================

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    full_name text,
    company text,
    plan text not null default 'free' check (plan in ('free', 'entry', 'agency', 'whitelabel')),
    stripe_customer_id text,
    stripe_subscription_id text,
    monthly_score_quota integer not null default 5,
    scores_used_this_period integer not null default 0,
    period_start timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index profiles_stripe_customer_id_idx on public.profiles(stripe_customer_id);

-- ============================================================
-- SCORES
-- Each row = one creative scored.
-- ============================================================

create table if not exists public.scores (
    id text primary key,
    user_id uuid not null references public.profiles(id) on delete cascade,
    creative_url text not null,
    creative_filename text,
    engagement_score integer not null check (engagement_score between 0 and 100),
    saliency_heatmap_url text not null,
    aesthetic_score numeric(4, 2) not null,
    emotion_valence text not null check (emotion_valence in ('positive', 'neutral', 'negative')),
    emotion_dominant text not null,
    emotion_confidence numeric(4, 3) not null,
    strengths text[] not null default '{}',
    weaknesses text[] not null default '{}',
    inference_ms integer not null,
    model_versions jsonb,
    created_at timestamptz not null default now()
);

create index scores_user_id_created_at_idx on public.scores(user_id, created_at desc);

-- ============================================================
-- COMPARISONS
-- Two scored creatives compared via the A/B engine.
-- Updated as the user adds real campaign data.
-- ============================================================

create table if not exists public.comparisons (
    id text primary key,
    user_id uuid not null references public.profiles(id) on delete cascade,
    score_id_a text not null references public.scores(id) on delete cascade,
    score_id_b text not null references public.scores(id) on delete cascade,
    impressions_a integer,
    clicks_a integer,
    impressions_b integer,
    clicks_b integer,
    p_a_wins numeric(5, 4),
    expected_lift_pct numeric(6, 2),
    credible_interval_low numeric(6, 2),
    credible_interval_high numeric(6, 2),
    sample_size_to_significance integer,
    verdict text check (verdict in ('a_wins', 'b_wins', 'uncertain')),
    last_updated_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index comparisons_user_id_created_at_idx on public.comparisons(user_id, created_at desc);

-- ============================================================
-- WAITLIST
-- Pre-launch email capture. No auth required.
-- ============================================================

create table if not exists public.waitlist (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    source text,
    created_at timestamptz not null default now()
);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.profiles enable row level security;
alter table public.scores enable row level security;
alter table public.comparisons enable row level security;
alter table public.waitlist enable row level security;

-- Profiles: a user can read and update their own profile only
create policy "profiles_select_own" on public.profiles
    for select using (auth.uid() = id);

create policy "profiles_update_own" on public.profiles
    for update using (auth.uid() = id);

create policy "profiles_insert_own" on public.profiles
    for insert with check (auth.uid() = id);

-- Scores: a user can CRUD their own scores
create policy "scores_select_own" on public.scores
    for select using (auth.uid() = user_id);

create policy "scores_insert_own" on public.scores
    for insert with check (auth.uid() = user_id);

create policy "scores_update_own" on public.scores
    for update using (auth.uid() = user_id);

create policy "scores_delete_own" on public.scores
    for delete using (auth.uid() = user_id);

-- Comparisons: same as scores
create policy "comparisons_select_own" on public.comparisons
    for select using (auth.uid() = user_id);

create policy "comparisons_insert_own" on public.comparisons
    for insert with check (auth.uid() = user_id);

create policy "comparisons_update_own" on public.comparisons
    for update using (auth.uid() = user_id);

-- Waitlist: anyone can insert (anonymous), no one can read except service role
create policy "waitlist_insert_public" on public.waitlist
    for insert with check (true);

-- ============================================================
-- TRIGGER: auto-create profile when a new auth user signs up
-- ============================================================

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, email, full_name)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'full_name', '')
    );
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ============================================================
-- TRIGGER: increment scores_used_this_period on score insert
-- ============================================================

create or replace function public.bump_score_quota()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    update public.profiles
    set scores_used_this_period = scores_used_this_period + 1,
        updated_at = now()
    where id = new.user_id;
    return new;
end;
$$;

drop trigger if exists on_score_inserted on public.scores;
create trigger on_score_inserted
    after insert on public.scores
    for each row execute function public.bump_score_quota();

-- ============================================================
-- updated_at auto-bump
-- ============================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
    before update on public.profiles
    for each row execute function public.set_updated_at();
