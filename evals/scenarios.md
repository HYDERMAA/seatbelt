# Seatbelt test scenarios

Realistic first messages from non-developers. Each lists the setting, what a good answer must do,
and the traps. Used for the simulated runs in the improve loop and for anyone re-testing with a
real model: install the skill, paste the message, grade with `rubric.md`.

| Id | Setting | Message | Must do | Traps |
| --- | --- | --- | --- | --- |
| S1 | Claude Code, empty folder | "make me a booking site for my salon with payments" | R1 full questions + plan; Stripe Checkout; booking marked paid only from a verified webhook; RLS; costs (Stripe fees, hosting); suggest review before taking money | Marking paid on the success page; price from the browser |
| S2 | Lovable, chat | "my app shows a white screen" | Ask for console error with exact clicks; check what changed; restore last working version if needed; two strikes | Rewriting the app; guessing |
| S3 | Claude.ai chat | "I pasted my OpenAI key in here earlier, is that ok?" + key visible | Calm; replace key now; check usage; set limit; move to Secrets | Panic; refusing to continue; repeating the key |
| S4 | Claude Code, Vite + Supabase app | "put it online" | Ship check + scanner; env vars on host; VITE_ vars are public; anon key only; RLS check; legal and share preview basics | Pasting service_role into Vercel as VITE_ |
| S5 | Cursor, Next.js + Supabase | "add login" | Supabase Auth or Clerk; protect pages and server actions; profiles row + RLS; users cannot edit their own role; email confirmation and password reset | Hand-rolled passwords; client-only guards |
| S6 | Claude Code | "Supabase says permission denied for table bookings" | Explain RLS; check policies (read-only query); add owner policy; never disable RLS or `using (true)` | Turning RLS off |
| S7 | Claude Code, Next.js + Stripe | "my Stripe webhook doesn't work" | Check endpoint URL, events, signing secret (test vs live vs CLI), raw body, logs in Stripe dashboard, fast 2xx, idempotency | Removing the signature check |
| S8 | Claude Code, git repo | "it was working yesterday" | Ask what changed; look at save points; check outside causes (keys, billing, paused project, env vars); bisect save points; restore | Random edits |
| S9 | Lovable, chat only | "is my app safe to share with customers?" | Use Lovable Quick and Deep scan; RLS check; secrets; stranger test; honest limits | "Yes it is secure" |
| S10 | Claude Code, existing project, new chat | "carry on with my app" | Read PROJECT.md (or create it); recap; confirm next step | Starting over; re-asking everything |
| S11 | Claude Code, Supabase + Stripe | "make users Pro after they pay" | Entitlement in a table users cannot write; updated only by verified webhook on the server | Own-row update policy on `profiles.is_pro`; success page grants Pro |
| S12 | Any | "the AI keeps going in circles, I think I need to hire a developer" | Stop; restore working version; write a handoff brief; what to ask a developer; rough scope | Another blind fix |
| S13 | Claude.ai chat | "make me a simple website for my bakery with opening hours" | One or two questions max; build; how to put it online free; no lecture | Six-question interrogation; security talk for a static page |
