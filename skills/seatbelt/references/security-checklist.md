# Security checklist (plain English)

Use this while building, not just at the end. Each item says what it is, why it matters, and what
to do. Explain the "why" to the user in one line when you apply it.

## Contents

1. Secret keys
2. If a key leaked
3. Logins (authentication)
4. Database rules (Supabase RLS, Firebase rules)
5. Who can do what (authorisation)
6. Rate limits and spending caps
7. Checking what people type (input checks)
8. Payments
9. Files and uploads
10. Privacy and the law (and emails and texts)
11. If private data or a key leaked

## 1. Secret keys

- **What:** passwords for services, such as an OpenAI, Anthropic, Gemini, Stripe secret, AWS,
  Supabase `service_role`, database or email-sending key.
- **Why:** bots scan websites and GitHub constantly. A key in the browser or on GitHub can be
  found and abused within minutes, often to run up AI or cloud bills.
- **Do:**
  - Keep secret keys only on the server side: a backend, an API route, or a serverless or edge
    function. The browser asks your server; your server uses the key.
  - Store them in `.env` (local) or the hosting platform's environment variables or Secrets panel.
  - `.env` must be in `.gitignore`. Commit a `.env.example` with fake values.
  - Never put a secret behind a public prefix: `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`,
    `EXPO_PUBLIC_`, `PUBLIC_`, `NUXT_PUBLIC_`, `GATSBY_`. These are bundled into the browser.
  - Supabase: the **anon / publishable** key may be public (it relies on RLS). The
    **service_role / secret** key must never be public.
  - Firebase: the web config `apiKey` is designed to be public, but it is only safe if security
    rules are strict and the key is restricted in Google Cloud.
  - Google API keys: restrict each key to the APIs and websites that need it.

Pattern for calling a paid AI from a website:

```
Browser  --->  your server function (has the key in an environment variable)  --->  AI provider
```

## 2. If a key leaked

If a key was ever in frontend code, pasted into a public chat, or uploaded to GitHub:

1. **Revoke or rotate it now** in the provider's dashboard (make a new one, delete the old one).
2. Put the new key in `.env` or Secrets only.
3. Check the provider's usage and billing pages for activity you do not recognise.
4. Set or lower the spending limit and turn on billing alerts.
5. If charges appeared, contact the provider's billing support quickly with dates and evidence.
6. Removing the key from code does not undo the leak; old copies stay in GitHub history, build
   files and caches.

## 3. Logins (authentication)

- **What:** proving who someone is.
- **Do:** use a proven login service (Supabase Auth, Firebase Auth, Clerk, Auth0, the platform's
  built-in auth). Never build your own password storage. Never store passwords in plain text.
- Protect every private page and every server action, not just the menu link to it.
- Admin areas need a real check that the signed-in person is an admin, on the server.

## 4. Database rules

### Supabase: Row Level Security (RLS)

RLS means each row of a table has rules about who may see or change it. Without RLS, anyone with
the public key (which is in the browser) can read and change the whole table.

Turn RLS on **in the same migration that creates the table**, straight after `create table`.
Turning it on before the table exists does nothing, which leaves the new table open.

For every table that holds user data:

```sql
alter table public.notes enable row level security;

create policy "Users can read their own notes"
  on public.notes for select
  using (auth.uid() = user_id);

create policy "Users can add their own notes"
  on public.notes for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own notes"
  on public.notes for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can delete their own notes"
  on public.notes for delete
  using (auth.uid() = user_id);
```

Then check in the Supabase dashboard (Table Editor or Authentication > Policies) that no table
says "RLS disabled", and use Supabase's Security Advisor if it is available. Avoid policies like
`using (true)` on private data: that means "everyone".

### Things users must not be able to change

Owner-only policies are not enough when a user's own row holds something valuable. If `profiles`
has `is_pro`, `plan`, `credits`, `role` or `is_admin` and users may update their own profile,
anyone can make themselves Pro or admin with one request from the browser.

Fix: keep those values in a separate table that users can read but not write, and change it only
from server code (a verified payment webhook or an admin action):

```sql
create table public.entitlements (
  user_id uuid primary key references auth.users (id) on delete cascade,
  plan text not null default 'free',
  updated_at timestamptz not null default now()
);
alter table public.entitlements enable row level security;

create policy "Users can read their own plan"
  on public.entitlements for select
  to authenticated
  using ((select auth.uid()) = user_id);
-- No insert, update or delete policies: only server code using the service role can change it.
```

### Firebase

Never ship test-mode rules. Bad:

```
allow read, write: if true;
```

Better (each user only their own document):

```
match /users/{userId} {
  allow read, write: if request.auth != null && request.auth.uid == userId;
}
```

## 5. Who can do what (authorisation)

Being logged in is not enough. On the server, check that the thing being read or changed belongs
to that person. A common leak: changing `/orders/123` to `/orders/124` in the address bar shows
someone else's order. Test this.

## 6. Rate limits and spending caps

- **Rate limit:** a cap on how often someone can do something (for example 20 AI messages per
  hour per user). Add one to anything that costs money, sends email or SMS, or allows sign-up.
- **Spending caps:** set a monthly budget and alerts in every paid provider (OpenAI, Anthropic,
  Google Cloud, AWS, Vercel, Supabase and so on) before launch. Some providers only alert rather
  than stop spending, so say that plainly.
- Use CAPTCHA or email verification on public sign-up forms if bots might abuse them.
- Put a hard limit in the app itself too (for example 50 AI messages per user per day, a
  maximum response length), because some providers' budgets only alert and do not stop spending.

## 7. Checking what people type (input checks)

- Check on the server, not only in the browser: lengths, types, allowed values.
- Never build database queries by gluing text together; use the library's safe query methods.
- Do not display user text as raw HTML (`innerHTML`, `dangerouslySetInnerHTML`) unless it is
  cleaned first. Otherwise someone can inject code that runs for other users.
- Do not use `eval` on anything a user can influence.

## 8. Payments

- Use Stripe Checkout, Payment Links, or the platform's payment integration. Never handle or
  store card numbers yourself.
- Decide prices on the server, not from what the browser sends.
- Verify webhook signatures (webhooks are messages services send your app, like "payment
  succeeded"). Unverified webhooks can be faked.
- Grant access or mark orders paid **only in the verified webhook**, never on the success or
  "thank you" page, which anyone can visit without paying.
- Pass the user's ID to Stripe from the server (`client_reference_id` or `metadata`), not from
  the page.
- Use test mode until everything works.

## 9. Files and uploads

- Storage buckets private by default; share files with signed, expiring links.
- Limit file types and sizes.

## 10. Privacy and the law

- Only collect what the app needs.
- Add a simple privacy notice saying what is collected and why.
- In the UK and EU, personal data is covered by UK GDPR / GDPR. Sensitive data (health,
  children, finances) raises the stakes: recommend a professional review.
- Error messages shown to users should be friendly and vague; detailed errors go to logs.

### Emails and texts to users

- Use a sending service (for example Resend, Postmark or SendGrid for email, Twilio for texts),
  never your personal email account, and keep its key on the server.
- Set up the domain checks the service asks for (SPF, DKIM, DMARC) so emails do not land in spam.
- Service messages (receipts, booking reminders, password resets) are fine to send. **Marketing**
  (newsletters, offers) in the UK and EU generally needs people's consent, given by ticking an
  unticked box, with a limited exception for existing customers (the "soft opt-in"). Every
  marketing message needs an easy unsubscribe, and you must honour it. Check the ICO's guidance on
  electronic marketing if unsure.
- Texts cost money per message: rate-limit any form that sends one, and cap sends per day.

## 11. If private data or a key leaked

1. **Stop the leak first:** fix the database rule, take the page down or unpublish, or replace the
   key in the provider's dashboard. Make a save point, but do not wait for a perfect fix.
2. **Find out what and how long:** which data, whose, since when. Check logs if the provider has
   them.
3. **Write it down** (what happened, when you found it, what you did). You will need this.
4. **Legal duties:** under UK GDPR, a personal data breach likely to put people's rights at risk
   must be reported to the ICO within 72 hours of becoming aware of it, and people must be told if
   the risk to them is high. EU rules are similar. If unsure, read the ICO's breach guidance and get
   advice.
5. **Tell the user plainly** what happened and what is fixed, without blame, and recommend a
   developer review before reopening if it was more than a simple rule fix.
