# Hosting and environment variables playbook

## Contents

1. Explain it to the user
2. Which variables are public?
3. Vercel
4. Netlify
5. Lovable, Bolt, Replit
6. Custom domains
7. Mistakes to watch for

## 1. Explain it to the user

> Putting the app online means a hosting service builds it and serves it. Your `.env` file stays
> on your computer, so you copy each setting into the host's **environment variables** page. Some
> settings end up inside the website itself (anyone can read them) and some stay on the server.
> The name decides which, so we have to get the names right.

## 2. Which variables are public?

| Framework | Copied into the website (public) | Server only (safe for secrets) |
| --- | --- | --- |
| Vite (React, Vue, Svelte) | Names starting `VITE_` | Vite apps have no server of their own: put secrets in Supabase Edge Functions or serverless functions |
| Next.js | Names starting `NEXT_PUBLIC_` | Every other name, used in server components, route handlers, server actions |
| Create React App | `REACT_APP_` | (no server) |
| Expo | `EXPO_PUBLIC_` | (no server) |
| Astro, SvelteKit | `PUBLIC_` | other names, in server code |

Public values are **baked in when the site is built**. After changing one on the host, redeploy.

Safe to be public: the Supabase URL and publishable (or legacy anon) key, a Stripe **publishable** key
(`pk_`), a Firebase web config, a Google Maps key restricted to your domain.
Never public: `sk_` keys, `service_role` or `sb_secret_` keys, OpenAI, Anthropic, Gemini or other
AI keys, database passwords, webhook secrets.

Next.js extra safety: add `import "server-only";` at the top of files that use secrets, so the
build fails if a page tries to include them.

## 3. Vercel

1. **Project > Settings > Environment Variables:** add each name and value, and choose which
   environments get it (Production, Preview, Development).
2. Redeploy (**Deployments > ... > Redeploy**) after adding or changing variables.
3. Preview deployments (one per change) get their own addresses. Check **Deployment Protection**
   so previews with test data are not public, and do not give previews live payment keys.
4. Check the build log for warnings about missing variables.

## 4. Netlify

1. **Site configuration > Environment variables:** add each name and value.
2. Trigger a new deploy after changes.
3. Netlify Functions (in `netlify/functions/`) are the place for secret keys.

## 5. Lovable, Bolt, Replit

- **Lovable:** secrets go in the Secrets settings or Supabase Edge Function secrets; publishing
  runs a Quick security scan. Ask Lovable to "read this key only in an edge function".
- **Bolt:** use its environment variable or backend secrets settings, not frontend code.
- **Replit:** the **Secrets** tool; check deployment privacy (public or private) deliberately.

## 6. Custom domains

- Buy the domain from a registrar, then add it in the host's **Domains** settings and follow the
  DNS steps it shows (usually one or two records). HTTPS (the padlock) is set up automatically.
- Update everything that mentions the old address: Supabase **URL Configuration**, Stripe
  webhook endpoint and success URLs, Google sign-in allowed origins, email links.

## 7. Mistakes to watch for

- A secret in a `VITE_` or `NEXT_PUBLIC_` variable "because it did not work otherwise". The fix is
  to move the code that needs it to the server, not to make the key public.
- Changing a variable and not redeploying.
- Live payment keys in Preview environments.
- `.env` uploaded with the project instead of using the host's settings.
- Source maps (files that let anyone read your original code) published by mistake. Fine for
  most apps, but never if code contains anything sensitive. Check the build settings.
