"""A small corpus of realistic vibe-coded apps for measuring the scanner.

Each app comes as a "bad" version with planted problems and a "good" twin built the safe way.
Fake keys are built from pieces at run time so nothing here looks like a real secret.
Used by tests/test_corpus.py, and runnable on its own to print a precision and recall table:
    python3 tests/corpus.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "seatbelt", "scripts", "check_secrets.py")

OPENAI = "sk-" + "proj-" + "Zq7Lm2Pw" * 5
STRIPE_LIVE = "sk_" + "live_" + "51Hx9QwErTyUiOpAsDfGhJkL" + "zx"
STRIPE_PK = "pk_" + "live_" + "51Hx9QwErTyUiOpAsDfGhJkL"
WHSEC = "wh" + "sec_" + "Ab12Cd34Ef56Gh78Ij90Kl12"
GOOGLE = "AI" + "za" + "SyC" + "x7" * 16
PUBLISHABLE = "sb_" + "publishable_" + "Qm3x9LkP2wZr8TyU1vB4nA_7hJk"
SB_SECRET = "sb_" + "secret_" + "Hn5Kw2Lp9Qr4Xt7Zv1Bm8Cd3"
SUPA_URL = "https://abcdefghijklmnopqrst.supabase.co"

PKG_VITE = json.dumps({"name": "app", "private": True, "type": "module",
                       "dependencies": {"react": "^18.3.1", "@supabase/supabase-js": "^2.45.0", "openai": "^4.60.0"}}, indent=2)
PKG_NEXT = json.dumps({"name": "shop", "private": True,
                       "dependencies": {"next": "15.0.0", "react": "^18.3.1", "stripe": "^17.0.0", "@supabase/supabase-js": "^2.45.0"}}, indent=2)
GITIGNORE = "node_modules\ndist\n.env.local\n"
GITIGNORE_FULL = "node_modules\ndist\n.env\n.env.*\n!.env.example\n"

SUPA_CLIENT = f'''import {{ createClient }} from "@supabase/supabase-js";
const SUPABASE_URL = "{SUPA_URL}";
const SUPABASE_PUBLISHABLE_KEY = "{PUBLISHABLE}";
export const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
'''

# ---------- 1. Lovable + Supabase "habit tracker" ----------
LOVABLE_BAD = {
    "package.json": PKG_VITE,
    ".gitignore": GITIGNORE,
    ".env": f"VITE_SUPABASE_URL={SUPA_URL}\nVITE_SUPABASE_PUBLISHABLE_KEY={PUBLISHABLE}\nVITE_OPENAI_API_KEY={OPENAI}\n",
    "src/integrations/supabase/client.ts": SUPA_CLIENT,
    "src/lib/coach.ts": '''import OpenAI from "openai";
const openai = new OpenAI({ apiKey: import.meta.env.VITE_OPENAI_API_KEY, dangerouslyAllowBrowser: true });
export async function coach(habits: string[]) {
  const r = await openai.chat.completions.create({ model: "gpt-4o-mini", messages: [{ role: "user", content: habits.join(", ") }] });
  return r.choices[0].message.content;
}
''',
    "src/pages/Success.tsx": '''import { useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
export default function Success() {
  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      supabase.from("profiles").update({ is_pro: true }).eq("id", data.user?.id);
    });
  }, []);
  return <h1>Thanks for upgrading!</h1>;
}
''',
    "supabase/migrations/20261101000000_init.sql": '''create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text,
  is_pro boolean not null default false
);
alter table public.profiles enable row level security;
create policy "own profile" on public.profiles for all using (auth.uid() = id) with check (auth.uid() = id);

create table public.habits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users,
  title text
);

create table public.journal_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users,
  body text
);
alter table public.journal_entries enable row level security;
create policy "read entries" on public.journal_entries for select using (true);
''',
}
LOVABLE_BAD_EXPECT = [
    ("env-file-saved-in-git", ".env"), ("ai-key-in-browser", "src/lib/coach.ts"),
    ("secret-behind-public-prefix", ".env"), ("success-page-grant", "src/pages/Success.tsx"),
    ("user-can-edit-entitlement", None), ("table-without-rls", None), ("policy-allows-everyone", None),
]

LOVABLE_GOOD = {
    "package.json": PKG_VITE,
    ".gitignore": GITIGNORE,
    ".env": f"VITE_SUPABASE_PROJECT_ID=abcdefghijklmnopqrst\nVITE_SUPABASE_URL={SUPA_URL}\nVITE_SUPABASE_PUBLISHABLE_KEY={PUBLISHABLE}\n",
    "src/integrations/supabase/client.ts": SUPA_CLIENT,
    "src/lib/coach.ts": '''import { supabase } from "@/integrations/supabase/client";
export async function coach(habits: string[]) {
  const { data, error } = await supabase.functions.invoke("coach", { body: { habits } });
  if (error) throw error;
  return data.text;
}
''',
    "supabase/functions/coach/index.ts": '''import OpenAI from "npm:openai";
import { createClient } from "npm:@supabase/supabase-js";
const openai = new OpenAI({ apiKey: Deno.env.get("OPENAI_API_KEY") });
Deno.serve(async (req) => {
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: req.headers.get("Authorization")! } } });
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new Response("Please log in", { status: 401 });
  const { count } = await supabase.from("ai_usage").select("*", { count: "exact", head: true }).eq("user_id", user.id);
  if ((count ?? 0) >= 30) return new Response("Daily limit reached", { status: 429 });
  const { habits } = await req.json();
  const r = await openai.chat.completions.create({ model: "gpt-4o-mini", max_tokens: 300,
    messages: [{ role: "user", content: String(habits).slice(0, 2000) }] });
  return Response.json({ text: r.choices[0].message.content });
});
''',
    "supabase/migrations/20261101000000_init.sql": '''create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text
);
alter table public.profiles enable row level security;
grant select, insert, update on public.profiles to authenticated;
grant all on public.profiles to service_role;
create policy "own profile" on public.profiles for all to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

create table public.entitlements (
  user_id uuid primary key references auth.users on delete cascade,
  plan text not null default 'free'
);
alter table public.entitlements enable row level security;
revoke all on public.entitlements from anon, authenticated;
grant select on public.entitlements to authenticated;
grant all on public.entitlements to service_role;
create policy "read own plan" on public.entitlements for select to authenticated using ((select auth.uid()) = user_id);

create table public.habits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users,
  title text not null
);
alter table public.habits enable row level security;
grant select, insert, update, delete on public.habits to authenticated;
create policy "own habits" on public.habits for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create table public.quotes (id bigint generated always as identity primary key, text text);
alter table public.quotes enable row level security;
grant select on public.quotes to anon, authenticated;
create policy "quotes are public" on public.quotes for select using (true);
''',
}

# ---------- 2. Next.js + Stripe shop ----------
NEXT_BAD = {
    "package.json": PKG_NEXT,
    ".gitignore": GITIGNORE_FULL,
    ".env.local": f"NEXT_PUBLIC_STRIPE_SECRET_KEY={STRIPE_LIVE}\nSTRIPE_WEBHOOK_SECRET={WHSEC}\n",
    ".env.example": f"STRIPE_SECRET_KEY={STRIPE_LIVE}\n",
    "app/api/checkout/route.ts": '''import Stripe from "stripe";
const stripe = new Stripe(process.env.NEXT_PUBLIC_STRIPE_SECRET_KEY!);
export async function POST(req: Request) {
  const { price, name } = await req.json();
  const session = await stripe.checkout.sessions.create({ mode: "payment",
    line_items: [{ price_data: { currency: "gbp", unit_amount: price, product_data: { name } }, quantity: 1 }],
    success_url: "https://shop.example/success", cancel_url: "https://shop.example" });
  return Response.json({ url: session.url }, { headers: { "Access-Control-Allow-Origin": "*" } });
}
''',
    "app/api/webhook/route.ts": '''import { createClient } from "@supabase/supabase-js";
const admin = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SECRET_KEY!);
export async function POST(req: Request) {
  const event = await req.json();
  if (event.type === "checkout.session.completed") {
    await admin.from("orders").update({ paid: true }).eq("session_id", event.data.object.id);
  }
  return new Response("ok");
}
''',
    "app/admin/page.tsx": f'''"use client";
import Stripe from "stripe";
const stripe = new Stripe("{STRIPE_LIVE}");
export default function Admin() {{ return <div>Admin</div>; }}
''',
}
NEXT_BAD_EXPECT = [
    ("secret-behind-public-prefix", ".env.local"), ("real-key-in-example", ".env.example"),
    ("webhook-not-verified", "app/api/webhook/route.ts"), ("stripe-live-secret", "app/admin/page.tsx"),
    ("cors-open", "app/api/checkout/route.ts"), ("price-from-browser", "app/api/checkout/route.ts"),
]
NEXT_GOOD = {
    "package.json": PKG_NEXT,
    ".gitignore": GITIGNORE_FULL,
    ".env.local": f"STRIPE_SECRET_KEY={STRIPE_LIVE}\nSTRIPE_WEBHOOK_SECRET={WHSEC}\nNEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY={STRIPE_PK}\nSUPABASE_SECRET_KEY={SB_SECRET}\n",
    ".env.example": "STRIPE_SECRET_KEY=your-stripe-secret-key\nSTRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret\n",
    "app/api/checkout/route.ts": '''import Stripe from "stripe";
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const PRICES: Record<string, string> = { mug: "price_mug_gbp", poster: "price_poster_gbp" };
export async function POST(req: Request) {
  const { item } = await req.json();
  const price = PRICES[item];
  if (!price) return new Response("Unknown item", { status: 400 });
  const session = await stripe.checkout.sessions.create({ mode: "payment", line_items: [{ price, quantity: 1 }],
    success_url: "https://shop.example/success?session_id={CHECKOUT_SESSION_ID}", cancel_url: "https://shop.example" });
  return Response.json({ url: session.url });
}
''',
    "app/api/webhook/route.ts": '''import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const admin = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SECRET_KEY!);
export async function POST(req: Request) {
  const body = await req.text();
  const sig = req.headers.get("stripe-signature")!;
  let event: Stripe.Event;
  try { event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!); }
  catch { return new Response("Bad signature", { status: 400 }); }
  if (event.type === "checkout.session.completed") {
    await admin.from("orders").upsert({ session_id: event.data.object.id, paid: true }, { onConflict: "session_id" });
  }
  return new Response("ok");
}
''',
}

# ---------- 3. Firebase "recipe swap" ----------
FIREBASE_CONFIG = f'''import {{ initializeApp }} from "firebase/app";
const firebaseConfig = {{
  apiKey: "{GOOGLE}",
  authDomain: "recipe-swap.firebaseapp.com",
  projectId: "recipe-swap",
  storageBucket: "recipe-swap.appspot.com",
  appId: "1:123456789:web:abc123",
}};
export const app = initializeApp(firebaseConfig);
'''
FIREBASE_BAD = {
    "package.json": json.dumps({"name": "recipes", "dependencies": {"firebase": "^11.0.0", "react": "^18.3.1"}}),
    ".gitignore": GITIGNORE_FULL,
    "src/firebase.ts": FIREBASE_CONFIG,
    "src/gemini.ts": f'''const KEY = "{GOOGLE}";
export async function suggest(q: string) {{
  const r = await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + KEY,
    {{ method: "POST", body: JSON.stringify({{ contents: [{{ parts: [{{ text: q }}] }}] }}) }});
  return r.json();
}}
''',
    "firestore.rules": '''rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if request.time < timestamp.date(2026, 12, 31);
    }
  }
}
''',
    "storage.rules": '''rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} { allow read, write: if true; }
  }
}
''',
}
FIREBASE_BAD_EXPECT = [("firebase-test-mode", "firestore.rules"), ("firebase-open-rules", "storage.rules"),
                       ("google-api-key", "src/gemini.ts")]
FIREBASE_GOOD = {
    "package.json": json.dumps({"name": "recipes", "dependencies": {"firebase": "^11.0.0", "react": "^18.3.1"}}),
    ".gitignore": GITIGNORE_FULL,
    "src/firebase.ts": FIREBASE_CONFIG,
    "firestore.rules": '''rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /recipes/{id} {
      allow read: if true;
      allow create: if request.auth != null && request.resource.data.owner == request.auth.uid;
      allow update, delete: if request.auth != null && resource.data.owner == request.auth.uid;
    }
  }
}
''',
}

# ---------- 4. Bolt / Vite site on Netlify ----------
BOLT_BAD = {
    "package.json": json.dumps({"name": "portfolio", "dependencies": {"vite": "^5.4.0"}}),
    ".gitignore": GITIGNORE_FULL,
    "public/.env": f"RESEND_API_KEY=re_" + "Ab12Cd34" + "_" + "Ef56Gh78Ij90Kl12Mn34" + "\n",
    "dist/assets/index-abc123.js.map": '{"version":3,"sources":["src/main.ts"]}',
    "dist/assets/index-abc123.js": "console.log('hi')",
    "src/main.ts": "setInterval(() => fetch('/api/refresh'), 1000);\n",
    "server.py": f'''from flask import Flask
app = Flask(__name__)
ADMIN_PASSWORD = "hunter2-supersecret"
if __name__ == "__main__":
    app.run(debug=True)
''',
}
BOLT_BAD_EXPECT = [("env-file-public", "public/.env"), ("debug-mode", "server.py"), ("public-source-maps", None)]
BOLT_GOOD = {
    "package.json": json.dumps({"name": "portfolio", "dependencies": {"vite": "^5.4.0"}}),
    ".gitignore": GITIGNORE_FULL,
    "src/main.ts": "document.querySelector('#year')!.textContent = String(new Date().getFullYear());\n",
    "netlify/functions/contact.ts": '''import { Resend } from "resend";
const resend = new Resend(process.env.RESEND_API_KEY);
export default async (req: Request) => {
  const { email, message } = await req.json();
  if (!email || String(message).length > 2000) return new Response("Bad request", { status: 400 });
  await resend.emails.send({ from: "site@example.com", to: "me@example.com", subject: "Contact", text: message });
  return new Response("Sent");
};
''',
    "server.py": '''import os
from flask import Flask
app = Flask(__name__)
if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
''',
}

APPS = [
    ("lovable-supabase", LOVABLE_BAD, LOVABLE_BAD_EXPECT, LOVABLE_GOOD, [".env"]),
    ("nextjs-stripe", NEXT_BAD, NEXT_BAD_EXPECT, NEXT_GOOD, []),
    ("firebase", FIREBASE_BAD, FIREBASE_BAD_EXPECT, FIREBASE_GOOD, []),
    ("bolt-netlify", BOLT_BAD, BOLT_BAD_EXPECT, BOLT_GOOD, []),
]
BAD_TRACKED = {"lovable-supabase": [".env"]}


def build(files, tracked=()):
    root = tempfile.mkdtemp(prefix="seatbelt-corpus-")
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for rel in tracked:
        subprocess.run(["git", "add", "-f", rel], cwd=root, check=True)
    return root


def scan(root):
    r = subprocess.run([sys.executable, SCRIPT, root, "--json"], capture_output=True, text=True)
    return json.loads(r.stdout)["findings"]


def measure():
    """Return per-app results: (name, found_expected, missed, false_alarms_in_good, all_good_findings)."""
    rows = []
    for name, bad, expect, good, good_tracked in APPS:
        b = build(bad, BAD_TRACKED.get(name, []))
        g = build(good, good_tracked)
        try:
            fb, fg = scan(b), scan(g)
        finally:
            shutil.rmtree(b, ignore_errors=True)
            shutil.rmtree(g, ignore_errors=True)
        missed = [e for e in expect if not any(f["check"] == e[0] and (e[1] is None or f["file"] == e[1]) for f in fb)]
        alarms = [f for f in fg if f["severity"] in ("critical", "high", "medium")]
        rows.append((name, len(expect) - len(missed), missed, alarms, fg, fb))
    return rows


if __name__ == "__main__":
    total = hit = fa = 0
    for name, found, missed, alarms, fg, fb in measure():
        exp = found + len(missed)
        total += exp
        hit += found
        fa += len(alarms)
        print(f"{name:18} planted {exp:2}  caught {found:2}  missed {[m[0] for m in missed]}  "
              f"false alarms in safe twin {[(a['check'], a['severity']) for a in alarms]}  "
              f"tips in safe twin {[f['check'] for f in fg if f['severity'] == 'low']}")
        print(f"{'':18} all checks fired on bad version: {sorted({f['check'] for f in fb})}")
    print(f"\nRecall {hit}/{total}  false alarms (medium or worse) in safe twins: {fa}")
