# Supabase playbook

Copy-paste patterns for the most common Supabase setups, plus read-only audit queries. The SQL
here is tested by Seatbelt's test suite against PostgreSQL with Supabase-style roles (`anon`,
`authenticated`, `service_role`) and `auth.uid()`.

## Contents

1. How Supabase security works (explain this to the user)
2. Pattern: private rows (each person sees only their own)
3. Pattern: public to read, only staff can change
4. Pattern: customers and staff (bookings)
5. Pattern: paid plans and credits users cannot fake
6. Pattern: create a profile when someone signs up
7. Pattern: private file uploads
8. Secret keys in Edge Functions
9. Read-only audit queries (paste into the SQL Editor)
10. Mistakes to watch for

## 1. How Supabase security works

Tell the user, in about these words:

> Your website talks to the database directly using a **public key** (the "anon" or
> "publishable" key). Anyone can find that key in your site, and that is fine **only because**
> each table has **Row Level Security** rules saying who may see or change which rows. A table
> without those rules is open to the world. There is also a **service role** (or secret) key that
> ignores all rules. It must only ever be used in server code, never in the website.

Where to run SQL: Supabase dashboard > **SQL Editor** > New query, paste, **Run**. If the project
uses migration files (`supabase/migrations/`), add the SQL as a new migration instead, so the
history is kept.

## 2. Pattern: private rows

For notes, saved items, personal records. Turn RLS on straight after creating the table, in the
same migration.

<!-- test: private_rows -->
```sql
create table public.notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  body text not null check (char_length(body) <= 5000),
  created_at timestamptz not null default now()
);
alter table public.notes enable row level security;

create policy "Read own notes" on public.notes
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "Add own notes" on public.notes
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "Edit own notes" on public.notes
  for update to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy "Delete own notes" on public.notes
  for delete to authenticated using ((select auth.uid()) = user_id);
```

Why `(select auth.uid())`: it is checked once per request instead of once per row, which keeps
big tables fast. `to authenticated` means logged-out visitors get nothing.

## 3. Pattern: public to read, only staff can change

For a menu, price list, services or opening hours shown to everyone.

<!-- test: public_read -->
```sql
create table public.services (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  price_pence integer not null check (price_pence >= 0),
  active boolean not null default true
);
alter table public.services enable row level security;

create policy "Anyone can see active services" on public.services
  for select to anon, authenticated using (active);
-- No insert, update or delete policies: change these in the dashboard Table Editor,
-- or from server code. Visitors cannot edit prices.
```

## 4. Pattern: customers and staff (bookings)

Customers see and create their own bookings; staff see all bookings. Staff are listed in a
table that only the owner edits (in the dashboard).

<!-- test: staff_bookings -->
```sql
create table public.staff (
  user_id uuid primary key references auth.users (id) on delete cascade
);
alter table public.staff enable row level security;
create policy "Staff can see their own staff row" on public.staff
  for select to authenticated using ((select auth.uid()) = user_id);

create or replace function public.is_staff()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.staff where user_id = (select auth.uid()));
$$;
revoke execute on function public.is_staff() from public, anon;
grant execute on function public.is_staff() to authenticated;

create table public.bookings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  service_id uuid not null references public.services (id),
  starts_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending', 'paid', 'cancelled')),
  created_at timestamptz not null default now()
);
alter table public.bookings enable row level security;

create policy "Customers see own bookings, staff see all" on public.bookings
  for select to authenticated
  using ((select auth.uid()) = user_id or (select public.is_staff()));
create policy "Customers create their own pending bookings" on public.bookings
  for insert to authenticated
  with check ((select auth.uid()) = user_id and status = 'pending');
create policy "Staff can update bookings" on public.bookings
  for update to authenticated
  using ((select public.is_staff())) with check ((select public.is_staff()));
-- Customers cannot mark their own booking as paid. Only the Stripe webhook (server code with
-- the service role) or staff can change status.
```

## 5. Pattern: paid plans and credits users cannot fake

The trap: putting `is_pro` or `credits` on the user's own `profiles` row and letting them update
their profile. Then anyone can make themselves Pro from the browser. Keep entitlements in a table
users can read and never write.

<!-- test: entitlements -->
```sql
create table public.entitlements (
  user_id uuid primary key references auth.users (id) on delete cascade,
  plan text not null default 'free' check (plan in ('free', 'pro')),
  credits integer not null default 0 check (credits >= 0),
  stripe_customer_id text,
  updated_at timestamptz not null default now()
);
alter table public.entitlements enable row level security;

create policy "Users can read their own plan" on public.entitlements
  for select to authenticated using ((select auth.uid()) = user_id);
-- No insert, update or delete policies on purpose. The Stripe webhook (server code using the
-- service role) is the only thing that changes plans or credits.
```

If a profile must stay editable but has one protected column, limit which columns users can
update instead:

<!-- test: column_guard -->
```sql
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 80),
  avatar_url text,
  role text not null default 'member'
);
alter table public.profiles enable row level security;
create policy "Read own profile" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "Edit own profile" on public.profiles
  for update to authenticated using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

revoke update on public.profiles from anon, authenticated;
grant update (display_name, avatar_url) on public.profiles to authenticated;
-- Users can change their name and picture, but not their role.
```

## 6. Pattern: create a profile when someone signs up

<!-- test: signup_trigger -->
```sql
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'display_name');
  insert into public.entitlements (user_id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
```

## 7. Pattern: private file uploads

Create the bucket as **private** (Storage > New bucket, leave "Public bucket" off). Each user
uploads into a folder named after their user ID, for example `avatars/<user id>/photo.jpg`.

<!-- test: storage_policies -->
```sql
create policy "Users read their own files" on storage.objects
  for select to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "Users upload to their own folder" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
```

Show files with signed links that expire (`createSignedUrl`), not public links.

## 8. Secret keys in Edge Functions

Edge Functions are small pieces of server code Supabase runs for you. They are the right place
for OpenAI, Stripe and other secret keys in a Lovable or Vite app.

```bash
supabase secrets set OPENAI_API_KEY=sk-...   # or Dashboard > Edge Functions > Secrets
```

```ts
// supabase/functions/ask-ai/index.ts
const apiKey = Deno.env.get("OPENAI_API_KEY"); // read on the server only
```

Check who is calling before doing anything costly: require the user's login token, look up the
user, and apply a per-user daily limit.

## 9. Read-only audit queries

These only read settings; they change nothing. Paste into **SQL Editor** and **Run**. Explain
each result in plain words. Empty results are good news.

<!-- test: audit -->
```sql
-- A. Tables anyone with your public key could read, because RLS is off
select c.relname as table_without_rls
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity
order by 1;

-- B. Tables with RLS on but no policies (nobody can use them from the app; often a sign of an
--    unfinished setup, and a temptation to turn RLS off)
select c.relname as table_with_no_policies
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity
  and not exists (select 1 from pg_policies p where p.schemaname = 'public' and p.tablename = c.relname)
order by 1;

-- C. Policies that let everyone through: using (true) or with check (true)
select tablename, policyname, cmd, roles
from pg_policies
where schemaname = 'public' and (qual = 'true' or with_check = 'true')
order by 1, 2;

-- D. Policies that apply to logged-out visitors (anon). Fine for public menus; not for private data
select tablename, policyname, cmd
from pg_policies
where schemaname = 'public' and ('anon' = any (roles) or 'public' = any (roles))
order by 1, 2;

-- E. Valuable columns (plan, credits, role...) in tables where users have an update or insert policy
select distinct col.table_name, col.column_name, p.policyname, p.cmd
from information_schema.columns col
join pg_policies p on p.schemaname = col.table_schema and p.tablename = col.table_name
where col.table_schema = 'public'
  and col.column_name in ('is_pro', 'pro', 'plan', 'tier', 'credits', 'balance', 'role',
                          'is_admin', 'admin', 'subscription_status', 'paid', 'status')
  and p.cmd in ('UPDATE', 'INSERT', 'ALL')
  and has_column_privilege('authenticated', format('%I.%I', col.table_schema, col.table_name), col.column_name, 'UPDATE')
order by 1, 2;

-- F. Views that may skip RLS (views run with their owner's rights unless security_invoker is on)
select c.relname as view_that_may_bypass_rls
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'v'
  and not coalesce(c.reloptions @> array['security_invoker=true'], false)
order by 1;

-- G. Functions that run with owner rights (security definer). Each needs a careful look
select p.proname as security_definer_function
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.prosecdef
order by 1;

-- H. Public storage buckets (anyone with the link can download)
select id as public_bucket from storage.buckets where public order by 1;
```

How to read query E: a row means a user might be able to change that column on their own row.
For `status` on bookings that may be fine if a check stops customers setting `paid` (as in
pattern 4); for `plan`, `credits` or `role` it is a hole. Use pattern 5.

## 10. Mistakes to watch for

- `alter table x enable row level security` placed **before** `create table x`: does nothing
  on a fresh database. Enable it after creating the table.
- `using (true)` on private data, or policies `to anon` on private tables.
- Turning RLS off to make "permission denied" go away. Write the missing policy instead.
- The service role key in the website, in a `VITE_` or `NEXT_PUBLIC_` variable, or in Lovable's
  frontend code.
- Server code using the service role without checking who the user is: it skips every rule, so
  it must do the ownership check itself.
- Views and `security definer` functions in the `public` schema that return other people's rows.
- Leaving email confirmation off for a public app, or redirect URLs still pointing at
  `localhost` (Authentication > URL Configuration).
