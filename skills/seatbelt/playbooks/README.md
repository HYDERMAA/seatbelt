# Seatbelt playbooks

Stack-specific, copy-paste patterns. Read only the one that matches the task. Each starts with a
plain-English explanation to give the user, then the steps, then the mistakes to watch for.

| Playbook | Read it when |
| --- | --- |
| [supabase.md](supabase.md) | Any Supabase database, RLS, storage or Edge Function work; "permission denied"; checking database rules before launch (read-only audit queries) |
| [stripe-payments.md](stripe-payments.md) | Taking payments, subscriptions, Pro plans or credits; webhook problems |
| [auth.md](auth.md) | Adding logins, protecting pages, admin areas, password reset, Google sign-in |
| [firebase.md](firebase.md) | Firestore, Realtime Database, Firebase Storage or Firebase Auth |
| [hosting.md](hosting.md) | Putting an app online (Vercel, Netlify, Lovable, Replit), env vars, custom domains, Next.js or Vite secrets |
| [costs.md](costs.md) | Any paid API or service; setting spending caps and alerts; per-user limits |
| [privacy-uk-eu.md](privacy-uk-eu.md) | Collecting personal data from people in the UK or EU; privacy notice, cookies, data requests |

The SQL in `supabase.md` and the payment routes in `stripe-payments.md` are tested by the
Seatbelt test suite. Dashboard menu names change often; if a menu is not where a playbook says,
search the service's settings or docs for the feature name.
