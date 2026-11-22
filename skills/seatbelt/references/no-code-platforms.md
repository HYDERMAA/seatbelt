# Using Seatbelt with app builders and coding tools

App builders change their menus often. If a menu named here has moved, tell the user to search the
tool's settings or help for "instructions", "knowledge", "rules" or "skills".

## Contents

1. How to prompt any app builder
2. Lovable
3. Bolt
4. Replit
5. v0
6. Cursor
7. Claude Code (CLAUDE.md)
8. Codex and other agents (AGENTS.md)
8b. Moving off an app builder
9. The short rules text to paste

## 1. How to prompt any app builder

When the user is in an app builder, write prompts for them to paste, one change per prompt:

```
Change one thing: [what].
Do not change anything else.
Keep all secret keys on the server (use the built-in secrets or env vars, never in frontend code).
Keep Row Level Security on for every table.
When done, tell me in plain English how to check it works.
```

Before each prompt, remind them to note or bookmark the current working version.

## 2. Lovable

- **Instructions (previously called Knowledge):** open **Project settings > Instructions** and
  paste the rules text from section 9 (there is room for about 10,000 characters). Workspace
  owners can also set workspace-wide instructions that apply to every project.
- **Secrets:** with Supabase or Lovable Cloud connected, put secret keys in the Supabase Edge
  Function secrets or the platform's secrets settings, never in the code. Ask Lovable to "move
  this API call into an edge function that reads the key from secrets".
- **Security scans:** Lovable offers a **Quick scan** (database rules, packages and connected
  tools) and a deeper scan of the app's code. Run the deeper scan before sharing with customers
  and fix the most serious findings first. Seatbelt's `check_live.py --mine` is a useful second
  opinion once the app is published: it asks each table, as a stranger, whether it will answer.
- **Versions:** use the version history to restore an earlier version.

## 3. Bolt

- **Project Knowledge:** open the project's settings, find **Knowledge**, paste the rules text
  into the project instructions and save. Account-wide (global) instructions apply to every
  project.
- **Skills:** Bolt can import skills in the project settings (**Skills**). Importing this
  repository's `skills/seatbelt` folder gives Bolt the full skill.
- **agents.md:** Bolt reads an `agents.md` file in the project. You can add the `AGENTS.md` from
  this repository, or attach it with the **+** button in the prompt box.
- **Secrets:** use environment variables or the connected backend's secrets, not frontend code.
- **Versions:** use the project's version history to go back.

## 4. Replit

- Replit Agent reads `replit.md` in the project's root folder. Add the rules text from section 9
  to it (keep anything Replit already wrote).
- Workspace-wide: **Settings > Customization > Custom Instructions** (where available).
- **Secrets:** use the **Secrets** tool (padlock icon) and read them as environment variables.
- **Checkpoints:** use **Rollback to here** on an Agent checkpoint to go back.
- Check whether the deployed app is public or private, and set it deliberately.
- **Security Center** (in the Tools pane): Level 1 basic checks are free; the deeper levels
  (a code scan, and an AI test of the running preview) need a paid plan and use Agent credits,
  so mention the cost before suggesting them.

## 5. v0

- Click **+** in the prompt bar, **Instructions > New Instruction**, title it "Seatbelt", paste
  the rules text, click **Add**, and keep it checked when prompting.
- v0 also has a built-in **Plan Mode** instruction; turning it on matches Seatbelt's
  plan-first habit.
- Put secret keys in the Vercel project's **Environment Variables**, used only in server code.

## 6. Cursor

Best: Cursor supports Agent Skills, so install the full skill into `~/.agents/skills/seatbelt/`
(all projects) or the project's `.agents/skills/seatbelt/` (`npx skills add HYDERMAA/seatbelt`
does this). Lighter option: copy `.cursor/rules/seatbelt.mdc` from this repository into the
project's `.cursor/rules/` folder; it is set to always apply. Cursor also reads `AGENTS.md`.

## 7. Claude Code (CLAUDE.md)

Best: install the skill itself (see the README). Alternatively, add the rules text to the
project's `CLAUDE.md`, or add a line to it: `Follow the rules in AGENTS.md.`

## 8. Codex and other agents (AGENTS.md)

Codex, Cursor, Bolt and many other agents read `AGENTS.md` in the project root. Copy the
`AGENTS.md` from this repository into the project, or append its contents to an existing one.
Codex can also install the full skill into `~/.agents/skills/seatbelt/`.

## 8b. Moving off an app builder (for example Lovable to Vercel)

1. Keep the builder version live until the new one fully works.
2. Connect the project to GitHub from the builder (Lovable and Bolt both offer this), so the code
   lives in a repository you own.
3. Import the repository into the new host (Vercel, Netlify). Add every environment variable from
   the builder's Secrets to the host's settings; public ones keep their prefix, secret ones never
   get one. Redeploy after adding them.
4. In Supabase **Authentication > URL Configuration**, add the new address to the redirect URLs,
   or logins will fail. Update any Stripe webhook address too.
5. Test logins, payments in test mode and the stranger test on the new address, then point your
   domain at it.

## 9. The short rules text to paste

This matches `paste-into-app-builders.md` in the repository root:

```
I am not a developer. Please work like a careful senior developer and explain things simply.
1. Explain any technical word in one plain sentence the first time you use it.
2. Before building something new, ask me a few simple questions, then show me a short plan and wait for my yes.
3. Build one small step at a time, only change what I asked for, and after each step tell me exactly how to check it works.
4. Before every change, make sure I can go back to the last working version, and tell me how.
5. Never put secret keys (API keys, Supabase secret or service_role keys, passwords) in frontend code or in files uploaded to GitHub. Keep them in secrets or environment variables, used only on the server.
6. Turn on Row Level Security for every database table, so each person only sees their own data, and grant only the access each table needs. Never turn it off or grant everything to fix an error.
7. For payments, only unlock paid features from a verified Stripe webhook, and store who has paid in a table users cannot edit.
8. Add rate limits to anything that costs money (including AI features), and remind me to set spending limits on paid services.
9. If a fix fails twice, stop, explain the problem in plain English, go back to the last working version, and try a different approach.
10. Before I publish, run your security scan and check: no secrets exposed, logins required for private pages, each user can only see their own data, inputs checked, friendly error messages, spending limits set.
11. Be honest with me rather than agreeable, and tell me when something is risky enough that a real developer should review it.
```
