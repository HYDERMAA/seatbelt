# Costs and spending caps playbook

## Contents

1. Explain it to the user
2. Before adding any paid service
3. Caps at the provider
4. Caps inside the app
5. Cheap by default
6. If a bill spikes

## 1. Explain it to the user

> Some services charge per use: every AI message, text message or map load costs a little. That
> is fine until a bug, a bot or a leaked key uses it thousands of times. We set limits in two
> places: at the provider (a budget and alerts) and inside the app (a cap per person per day).

## 2. Before adding any paid service

Tell the user, in money:
1. What it costs at their expected use (rough monthly figure, from the provider's pricing page,
   checked today, not from memory).
2. What makes it grow (more users, longer AI answers, bigger files, more texts).
3. The free tier, if any, and what happens when it runs out (stops, or starts charging).
4. How we will cap it (sections 3 and 4).

## 3. Caps at the provider

Look in each provider's **Billing**, **Usage** or **Limits** settings. For each one, write down
in PROJECT.md what was set.

- **AI APIs (OpenAI, Anthropic, Google Gemini and others):** set a monthly budget or spend limit
  if offered, and usage alerts by email. If the account uses **prepaid credits**, keep the
  balance small and turn **auto-reload** (automatic top-up) off or set a low top-up limit. Create
  a separate API key (or project) per app, so one app cannot spend another's budget and a leak is
  easy to switch off.
- **Google Cloud (including Gemini keys made there, and Firebase on the Blaze plan):** create a
  **budget with alerts** in Billing. Budgets send alerts; they **do not stop spending** on their
  own. Also restrict each API key to the APIs and websites that need it.
- **AWS:** AWS Budgets sends alerts; it does not stop spending by default.
- **Hosting and databases (Vercel, Netlify, Supabase):** check the plan's usage limits and any
  spend management or spend cap setting, and what happens when a limit is reached.
- **Text messages and email (Twilio, Resend, SendGrid):** set usage alerts, and protect sign-up
  and "send code" forms with rate limits and CAPTCHA, because bots abuse them to send messages
  at your cost.

Always tell the user honestly whether a setting **stops** spending or only **warns**.

## 4. Caps inside the app

Provider caps are a safety net. The real control is in your server code:

- **Per-user daily limit** for anything that costs money (for example 30 AI messages per user per
  day). Store a count per user per day in the database and refuse politely when it is reached.
- **Logged-in users only** for paid features, so anonymous bots cannot run up the bill.
- **Limit size:** set a maximum AI answer length (`max_tokens` or similar) and maximum input
  length; limit upload sizes.
- **Rate limit** sign-up, login, password reset and "send code" routes (for example a few tries
  per minute per address).
- **Never** let the browser call a paid API directly with your key.

Example message to show users at the limit: "You have used today's 30 AI replies. They reset at
midnight."

## 5. Cheap by default

- Start on free tiers for version one.
- Use the provider's smaller, cheaper model for simple jobs; switch to a bigger one only where it
  clearly helps.
- Cache answers that do not change (for example a daily summary) instead of asking the AI again.
- Compress images before upload.

## 6. If a bill spikes

1. Switch off or replace the key involved straight away.
2. Check the usage page for when it started and from where.
3. Find the cause: leaked key (run the scanner, check GitHub), a loop in the code, a bot abusing
   a form.
4. Fix, add the missing caps, then contact the provider's billing support quickly with dates and
   evidence. Providers sometimes reduce or waive charges from abuse, but there is no guarantee.
