# Logins playbook

## Contents

1. Explain it to the user
2. Pick a login service
3. Supabase Auth checklist (and Google sign-in)
4. Protect pages and actions on the server
5. Admin areas
6. Mistakes to watch for

## 1. Explain it to the user

> A login proves who someone is. Hiding a page from the menu is not protection: anyone can type
> the address. The server has to check who is asking every time it shows or changes private
> information. We will use a proven login service, so we never store passwords ourselves.

## 2. Pick a login service

- **Already on Supabase or Lovable Cloud:** Supabase Auth.
- **Next.js with no database yet, or you want ready-made sign-in screens:** Clerk.
- **Firebase project:** Firebase Auth.
- **App builders:** use the builder's built-in login option.

Never write your own password storage or "remember me" tokens.

## 3. Supabase Auth checklist

- [ ] **Authentication > Sign In / Providers:** turn on email (and Google if wanted). Keep
      **Confirm email** on for public apps, so people prove they own the address.
- [ ] **Authentication > URL Configuration:** set **Site URL** to the real domain and add the
      redirect URLs you use (live domain and `http://localhost:3000` for testing). Wrong values
      here are the usual reason login links and password resets "do nothing".
- [ ] Password reset page exists and works end to end.
- [ ] Leaked-password protection (blocks passwords known from data breaches) on, if your
      Supabase plan offers it; a sensible minimum password length.
- [ ] A profile and an entitlements row are created on sign-up with a trigger
      (`supabase.md` pattern 6), not from the browser.
- [ ] Every table has RLS with policies `to authenticated` (`supabase.md` patterns 2 to 5).
- [ ] Custom email sending (SMTP) set up before launch if you expect many sign-ups, because the
      built-in sender is limited and meant for testing.

### Google sign-in with Supabase

1. In Google Cloud console, **APIs & Services > OAuth consent screen**: set the app name, support
   email and your domain.
2. **APIs & Services > Credentials > Create credentials > OAuth client ID**, type **Web
   application**. Under **Authorised redirect URIs**, add the callback address that Supabase shows
   on its Google provider page (it looks like `https://<your-project>.supabase.co/auth/v1/callback`).
3. Copy the **client ID** and **client secret** into Supabase **Authentication > Sign In /
   Providers > Google**. The client secret (starts `GOCSPX-`) lives only there, never in your
   code or a public variable.
4. Add your real domain and `http://localhost:3000` to Supabase's redirect URLs, then test both.
5. Publish the consent screen when ready, otherwise only test users can sign in.

## 4. Protect pages and actions on the server

**Next.js with Supabase:** use the `@supabase/ssr` package so the login is available in server
code. In server components, route handlers and server actions, check the user with
`supabase.auth.getUser()` (or `getClaims()` in newer versions), which checks the login with
Supabase. Do not rely on `getSession()` in server code, because it reads what the browser sent
without checking it. Redirect to the login page when there is no user.

**Next.js with Clerk:** add `clerkMiddleware()` in `middleware.ts` and protect private routes;
in server code, read the user with `auth()` and refuse when there is no `userId`.

**Vite or React only (no server):** all data protection must come from RLS or Firebase rules,
because there is no server of your own. Anything secret (keys, admin actions) goes into Supabase
Edge Functions that check the login token first.

**Every server action or API route** that reads or changes private data:
1. Gets the user from the login, never from an ID sent by the page.
2. Checks the data belongs to that user (or that they are staff).
3. Only then reads or writes.

## 5. Admin areas

- Keep the list of admins in a table users cannot write (`supabase.md` pattern 4 `staff`, or
  column guard in pattern 5). Never trust an `isAdmin` flag sent by the browser.
- Check admin rights on the server for every admin action, not just when showing the admin page.
- The Supabase service role key is for server code only, and server code using it must do its own
  checks, because it skips RLS.

## 6. Mistakes to watch for

- Protecting pages only in the browser (`if (!user) hide()`), with the data still readable.
- Users able to edit their own `role` or `is_admin`.
- `getSession()` trusted in server code.
- Redirect URLs still pointing at `localhost` after launch.
- Email confirmation off on a public app (lets bots and fake accounts in).
- Login state stored in `localStorage` by hand-written code instead of the auth library.
