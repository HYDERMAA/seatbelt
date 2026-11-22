# Going live: the ship check

Run this before the app is shared with anyone beyond the builder. Report results as a short list:
passed, problems (worst first), and left for later. Never call the app "secure"; say it "passed
the ship check" and list what was checked.

## 1. Automatic scan (if you can run commands)

From the project folder:

```bash
python3 /path/to/seatbelt/scripts/check_secrets.py .
```

It reads files only, changes nothing, and needs only Python 3. Exit code 0 means no serious
findings, 1 means something must be fixed. Add `--json` for machine-readable output. It cannot
see the hosting dashboard, the live database settings, or anything outside the folder, so the
manual checks below still matter.

## 2. Manual checks

Tick each one, explaining in plain words:

**Secrets**
- [ ] No secret keys in frontend code or behind public prefixes (`NEXT_PUBLIC_`, `VITE_` and so on)
- [ ] `.env` is in `.gitignore`, and no `.env` was ever uploaded to GitHub
- [ ] Every key that was ever exposed has been replaced
- [ ] Keys are set in the hosting platform's environment variables for the live site

**Logins and data**
- [ ] Private pages and server actions require login
- [ ] Each person can only see and change their own data (tested with two accounts)
- [ ] Supabase: RLS on for every table, with policies; Firebase: no `if true` rules
- [ ] Storage buckets are private unless deliberately public
- [ ] Admin features check admin rights on the server

**Abuse and money**
- [ ] Rate limits on AI calls, sign-up, email or SMS sending, and anything else that costs money
- [ ] Spending limits and billing alerts set on every paid service
- [ ] Payments use Stripe Checkout or similar, prices set on the server, webhooks verified,
      tested in test mode first

**Quality**
- [ ] Inputs checked on the server
- [ ] Friendly error messages for users, no technical details or keys shown
- [ ] Works on a phone and a computer
- [ ] Main journeys tested start to finish (sign up, the main task, log out)
- [ ] Debug or test modes turned off

**Privacy and safety nets**
- [ ] Only necessary personal data collected; a simple privacy notice exists
- [ ] Database backups switched on, or a way to export data
- [ ] A final save point named "launched version 1"

## 3. The stranger test

Open the live site in a private or incognito window (not logged in) and try:

1. Visiting private pages directly by address. You should be sent to log in.
2. Signing up as a second person and trying to see the first person's data (change IDs in the
   address bar). You should see nothing.
3. Viewing the page source (**right-click > View page source**) and searching for `sk-`,
   `secret`, `service_role` and `key`. Nothing secret should appear.

## 4. When to stop and get a developer review

Recommend a review by an experienced developer before launch if the app takes payments, stores
sensitive personal data (health, finance, children), is for a business, or will have many users.
Give them this checklist and the scan output as a starting point.

## 5. After launch

- Check billing pages weekly for the first month.
- Keep making save points before every change, even small ones.
- Re-run this check after big changes.
