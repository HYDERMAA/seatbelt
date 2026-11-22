# Project memory (PROJECT.md) and the developer handoff brief

Non-developers lose hours when a new chat forgets everything. Keep a short `PROJECT.md` in the
project's main folder so any AI (or any developer) can pick up where you left off.

## Contents

1. Rules for PROJECT.md
2. PROJECT.md template
3. Developer handoff brief

## 1. Rules for PROJECT.md

- **Read it first** at the start of every session, then give a two-line recap and confirm the
  next step. Do not re-ask questions it already answers.
- **Create it** once the plan is agreed (Amber and Red projects; Green too if they will come back).
- **Update it after every finished step:** tick the step, add anything decided, note new
  accounts or services. Keep it under about 80 lines; it is a map, not a diary.
- **Never put secret values in it.** Name the secret and where it lives ("OPENAI_API_KEY in
  Supabase Edge Function secrets"), never the value.
- **In app builders** without files the user can see, keep the same content in the builder's
  project instructions (Lovable Instructions, Bolt Knowledge, `replit.md`) or ask the user to
  keep it in a note and paste it at the start of a new chat.
- **In chat only,** end a long session by giving them the updated PROJECT.md to save.

## 2. PROJECT.md template

```markdown
# Project: [name]

## What it is
[One or two sentences.] Risk level: [Green / Amber / Red] because [reason].

## Who uses it
[Who, roughly how many.]

## Built with
- Front end: [e.g. React + Vite, Next.js, Lovable]
- Database and logins: [e.g. Supabase, project name "salon-prod", region London]
- Payments: [e.g. Stripe, test mode until launch]
- Hosting: [e.g. Vercel, project "salon"]
- Paid services and caps: [e.g. OpenAI, monthly budget $20, alerts at 50%]

## Where things live
- [src/pages/Booking.tsx: the booking page]
- [supabase/migrations/: database changes, newest last]
- [supabase/functions/stripe-webhook: marks bookings paid]

## Secrets (names only, never values)
- [STRIPE_SECRET_KEY: Supabase Edge Function secrets]
- [STRIPE_WEBHOOK_SECRET: same]

## Plan
- [x] 1. Timetable page
- [x] 2. Logins
- [ ] 3. Booking and payment  <- next
- [ ] 4. Reminder emails

## Decisions
- [Prices come from Stripe Price IDs on the server, never from the page.]

## Known problems and ideas for later
- [The calendar looks cramped on small phones.]

## Last ship check
[Date: passed / problems found, see ship-report.md]

## How to run it
- [npm install, then npm run dev, open http://localhost:5173]
```

## 3. Developer handoff brief

Offer this when the user is stuck after a rollback and a fresh approach, before a Red launch, or
when they want to hire help. Write it to `HANDOFF.md` (or give it in the chat). Plain English,
one or two pages, so a freelancer can quote and start quickly.

```markdown
# Handoff brief: [app name]

## In one paragraph
[What the app does, who uses it, and what the owner needs from a developer.]

## What I need help with
1. [e.g. Payments sometimes do not mark bookings as paid.]
2. [e.g. A security review before real customers use it.]

## Current state
- Works: [list]
- Broken or unfinished: [list, with exact error messages]
- What was already tried: [list, with dates if known]

## How it is built
[Copy the "Built with", "Where things live" and "Secrets (names only)" sections of PROJECT.md.]

## Access the developer will need
- [GitHub repository (invite as collaborator), Supabase project (invite as developer),
  Vercel project, Stripe test mode.] Never send passwords or keys by email or chat; invite them
  to each service instead, and replace keys after the work ends.

## Ship check results
[Paste ship-report.md or the summary.]

## Questions to ask the developer
1. Can you reproduce the problem, and what is the cause in plain English?
2. Roughly how many hours, and what would it cost?
3. Will you work on a copy or a separate branch, so the live app keeps working?
4. Can you check every table's database rules and every server route for ownership checks?
5. Will you write down what you changed so my AI can keep working on it afterwards?
```

Remind the user: agree a fixed scope and price for small jobs, and get the work delivered as
save points (commits) so it can be reviewed and rolled back.
