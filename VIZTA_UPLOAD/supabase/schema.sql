create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text unique not null,
    login text unique not null,
    slug text unique not null,
    card_code text unique,
    full_name text not null,
    headline text,
    title text,
    company text default 'VIZTA',
    location text,
    bio text,
    accent text default '#d0d0cb',
    avatar_url text,
    must_change_password boolean not null default true,
    is_featured boolean not null default false,
    display_order integer not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists public.profile_links (
    id bigint generated always as identity primary key,
    user_id uuid not null references public.profiles(id) on delete cascade,
    platform text not null,
    label text not null,
    url text not null,
    position integer not null default 0,
    created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.profile_links enable row level security;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public'
          and tablename = 'profiles'
          and policyname = 'public can read profiles'
    ) then
        create policy "public can read profiles"
        on public.profiles
        for select
        to anon, authenticated
        using (true);
    end if;
end
$$;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public'
          and tablename = 'profiles'
          and policyname = 'user can read own profile'
    ) then
        create policy "user can read own profile"
        on public.profiles
        for select
        to authenticated
        using ((select auth.uid()) = id);
    end if;
end
$$;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public'
          and tablename = 'profiles'
          and policyname = 'user can update own profile'
    ) then
        create policy "user can update own profile"
        on public.profiles
        for update
        to authenticated
        using ((select auth.uid()) = id)
        with check ((select auth.uid()) = id);
    end if;
end
$$;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public'
          and tablename = 'profile_links'
          and policyname = 'user can read own links'
    ) then
        create policy "user can read own links"
        on public.profile_links
        for select
        to authenticated
        using ((select auth.uid()) = user_id);
    end if;
end
$$;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public'
          and tablename = 'profile_links'
          and policyname = 'user can manage own links'
    ) then
        create policy "user can manage own links"
        on public.profile_links
        for all
        to authenticated
        using ((select auth.uid()) = user_id)
        with check ((select auth.uid()) = user_id);
    end if;
end
$$;
