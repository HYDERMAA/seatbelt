# Going live: the ship check

Run this before the app is shared with anyone beyond the builder. Report results as a short list:
passed, problems (worst first), left for later. Never call the app "secure"; say it "passed the
ship check" and list what was checked. Scale it to the risk level: Green apps need sections 1,
2 (secrets and quality) and 4; Amber and Red need everything.

## Contents

1. Automatic scans
2. Manual checks
3. The stranger test
4. Launch-day basics
5. When to stop and get a developer review
6. After launch

## 1. Automatic scans

**Seatbelt scanner** (if you can run commands; Python 3 only, reads files, changes nothing):

```bash
python3 /path/to/seatbelt/scripts/check_secrets.py . --report ship-report.md
```

- Exit code 0: no critical or high findings. 1: something must be fixed first.
- `--report ship-report.md` (or `.html`) writes a plain-English report to keep with the project.
- `--audit` also runs `npm audit` if the project has a `package-lock.json` (needs internet).
- `--json` gives machine-readable output.
- Run it on the **build output** too if there is one (`dist/`, `build/`, `.next/`), because that
  is exactly what visitors download.

The report ends with **Paid services found**: every paid API the code uses and where to set its
spending cap. Tick each one off. It also flags AI calls with no per-person limit, AI calls inside
loops, and timers or scheduled jobs that run very often.

It cannot see the hosting dashboard, the live database settings, or anything outside the folder,
so the live check and the checks below still matter.

**Seatbelt live check** (once the site is online, and only on a site the user owns):

```bash
python3 /path/to/seatbelt/scripts/check_live.py https://their-site.com --mine --report live-report.md
```

- It only reads (GET and HEAD requests). It never logs in, never sends data, never changes anything.
- It looks at what every visitor receives: keys inside the page and its JavaScript files, an
  exposed `.env` or `.git` folder, source maps, HTTPS and basic security headers.
- With `--mine` it also asks the database the stranger's question. It finds the Supabase address
  and **public** key in the site's own code, then asks each table the code uses for one row. It
  reports how many rows a stranger can read and which columns, never the data itself. It does the
  same for Firebase Realtime Database and Firestore collections.
- Anything it can read, anyone can read. Fix those first, then run it again.
- It cannot test logged-in access (for example whether user A can see user B's rows): do that
  by hand with two test accounts (section 3).

**Chat only (Claude.ai, ChatGPT) with a code sandbox:** ask the user to zip the project folder
(without `node_modules`) and upload it; unzip it and run the scanner there. Remind them to
replace any key the report finds, since it has now been shared.

**Builder and platform scans** (free or included):
- Lovable: the Quick scan, and the deeper code scan before customers use it.
- Replit: Security Center (Tools pane), Level 1 is free.
- Supabase: **Advisors > Security Advisor** in the dashboard lists tables without RLS and other
  risky settings.
- Supabase database rules, from the inside: the read-only audit queries in
  [playbooks/supabase.md](../playbooks/supabase.md), pasted into the SQL Editor.

## 2. Manual checks

Explain each in plain words and tick it off.

**Secrets**
- [ ] No secret keys in frontend code, build output, or public-prefixed variables
- [ ] `.env` is in `.gitignore`, and no `.env` was ever uploaded to GitHub
- [ ] Every key that was ever exposed has been replaced
- [ ] Keys are set in the host's environment variables, and the site was redeployed after

**Logins and data**
- [ ] Private pages and server actions require login (checked on the server, not just hidden)
- [ ] Each person can only see and change their own data (tested with two accounts)
- [ ] Every table has RLS on with policies; no `using (true)` on private data; Firebase has no
      `if true` rules
- [ ] Users cannot change their own plan, credits, role or admin flag
- [ ] Storage buckets private unless deliberately public
- [ ] Sign-up: email confirmation on; password reset works; Supabase leaked-password protection
      on if your plan offers it; redirect URLs set to the real domain

**Money**
- [ ] Payments through Stripe Checkout or similar; prices set on the server
- [ ] Access granted only from a verified webhook, never from the success page
- [ ] Tested end to end in test mode (Stripe test card 4242 4242 4242 4242), then switched to live
      keys and a live webhook endpoint with its own signing secret
- [ ] Spending caps and billing alerts on every paid service; rate limits on AI calls, sign-up,
      and email or SMS sending

**Quality**
- [ ] Main journeys work start to finish (sign up, the main task, pay, log out)
- [ ] Empty states (no bookings yet) and error states (wrong password, network down) are friendly
- [ ] Inputs checked on the server; no technical details or keys in error messages
- [ ] Works on a phone (try it on a real one) and with the keyboard; images have alt text;
      text is readable (good contrast, not tiny)
- [ ] Debug or test modes off; no test data left in the live database

**Privacy and safety nets**
- [ ] Only necessary personal data collected; a privacy notice says what and why
- [ ] Terms or booking conditions if taking money (refunds, cancellations)
- [ ] Cookie banner only if using non-essential cookies such as analytics (UK and EU rules)
- [ ] Database backups on, or a way to export data; a final save point "launched version 1"

## 3. The stranger test

Open the live site in a private or incognito window (not logged in):

1. Visit private pages directly by address. You should be sent to log in.
2. Sign up as a second person and try to see the first person's data (change IDs in the address
   bar). You should see nothing.
3. **Right-click > View page source**, and open the browser's developer tools **Sources** tab,
   then search for `sk-`, `sk_live`, `secret`, `sb_secret_`, `service_role` and `key`. Nothing secret should
   appear.
4. Try the main form with nonsense: empty, very long text, `<script>` tags. It should refuse
   politely, not break.

## 4. Launch-day basics

- [ ] Custom domain connected, `https://` works, the old preview address redirects or is private
- [ ] Page title, description and a share image, so links look right in WhatsApp and social media
- [ ] A favicon (the little icon in the browser tab)
- [ ] A contact method for users who have problems
- [ ] Emails (confirmations, resets) arrive and do not land in spam; use a proper email-sending
      service with your domain set up if sending many

### Putting a simple (Green) site online for free

For a site with no logins, database or payments (just pages and pictures):

- **Netlify Drop:** go to app.netlify.com/drop, drag the site's folder onto the page, and it is
  live at a free address in seconds. Make a free account to keep it.
- **GitHub Pages** or **Cloudflare Pages:** free, good if the project is already on GitHub.
- App builders (Lovable, Bolt, Replit, v0) have a **Publish** or **Deploy** button.

Then connect a custom domain if they have one (section 4).

## 5. When to stop and get a developer review

Recommend a review by an experienced developer before launch for Red apps: payments, sensitive
personal data (health, finance, children), a business's customers, or many users. Offer the
handoff brief from `project-memory.md` with the ship report attached.

## 6. After launch

- Check billing and usage pages weekly for the first month.
- Keep making save points before every change, even small ones.
- Re-run the ship check after big changes, and update PROJECT.md.
