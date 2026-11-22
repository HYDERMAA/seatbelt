"""Runs the SQL in skills/seatbelt/playbooks/supabase.md against a real PostgreSQL server with
Supabase-style roles, and checks the policies do what the playbook says.

Needs `psql` and a PostgreSQL server you can create databases on. Set SEATBELT_PG to a psql
connection string, for example:  SEATBELT_PG="host=/tmp port=54329 user=postgres"
Skipped when SEATBELT_PG is not set.
"""

import os
import re
import shutil
import subprocess
import unittest
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYBOOK = os.path.join(HERE, "..", "skills", "seatbelt", "playbooks", "supabase.md")
SHIM = os.path.join(HERE, "supabase_shim.sql")
PG = os.environ.get("SEATBELT_PG")

A = "00000000-0000-0000-0000-0000000000a1"
B = "00000000-0000-0000-0000-0000000000b2"
S = "00000000-0000-0000-0000-0000000000c3"


def blocks():
    with open(PLAYBOOK, encoding="utf-8") as fh:
        text = fh.read()
    return dict(re.findall(r"<!-- test: (\w+) -->\n```sql\n(.*?)```", text, re.S))


@unittest.skipUnless(PG and shutil.which("psql"), "set SEATBELT_PG to run the SQL tests")
class SupabasePlaybookSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocks = blocks()
        with open(SHIM, encoding="utf-8") as fh:
            cls.shim = fh.read()

    def setUp(self):
        self.db = "seatbelt_" + uuid.uuid4().hex[:10]
        self.psql_admin(f"create database {self.db}", db="postgres")
        self.sql(self.shim)
        self.sql(f"insert into auth.users (id, email) values ('{A}','a@x.test'),('{B}','b@x.test'),('{S}','s@x.test')")

    def tearDown(self):
        self.psql_admin(f"drop database if exists {self.db} with (force)", db="postgres")

    # --- helpers ---
    def psql_admin(self, sql, db):
        r = subprocess.run(["psql", f"{PG} dbname={db}", "-v", "ON_ERROR_STOP=1", "-qtA", "-c", sql],
                           capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(r.stderr)
        return r.stdout

    def run_sql(self, sql, role=None, user=None):
        pre = ""
        if user:
            pre += f"select set_config('request.jwt.claim.sub', '{user}', false);\n"
        if role:
            pre += f"set role {role};\n"
        return subprocess.run(["psql", f"{PG} dbname={self.db}", "-v", "ON_ERROR_STOP=1", "-qtA"],
                              input=pre + sql, capture_output=True, text=True)

    def sql(self, sql, role=None, user=None):
        r = self.run_sql(sql, role, user)
        if r.returncode:
            raise AssertionError(f"SQL failed: {r.stderr}\n{sql}")
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        if user:
            lines = lines[1:]  # drop set_config output
        return lines

    def fails(self, sql, role=None, user=None, msg=None):
        r = self.run_sql(sql, role, user)
        self.assertNotEqual(r.returncode, 0, f"expected failure: {sql}")
        if msg:
            self.assertIn(msg, r.stderr)

    def as_user(self, user, sql):
        return self.sql(sql, role="authenticated", user=user)

    def load(self, *names):
        for n in names:
            self.sql(self.blocks[n])

    # --- tests ---
    def test_every_block_is_tested(self):
        expected = {"private_rows", "public_read", "staff_bookings", "entitlements", "column_guard",
                    "signup_trigger", "storage_policies", "audit"}
        self.assertEqual(set(self.blocks), expected)

    def test_private_rows(self):
        self.load("private_rows")
        self.as_user(A, "insert into public.notes (body) values ('hello')")
        self.assertEqual(self.as_user(A, "select count(*) from public.notes"), ["1"])
        self.assertEqual(self.as_user(B, "select count(*) from public.notes"), ["0"])
        self.assertEqual(self.sql("select count(*) from public.notes", role="anon"), ["0"])
        self.assertEqual(self.as_user(B, "with u as (update public.notes set body='x' returning 1) select count(*) from u"), ["0"])
        self.fails(f"insert into public.notes (user_id, body) values ('{A}', 'sneaky')", role="authenticated", user=B,
                   msg="row-level security")

    def test_public_read(self):
        self.load("public_read")
        self.sql("insert into public.services (name, price_pence, active) values ('Cut', 3000, true), ('Old', 1, false)")
        self.assertEqual(self.sql("select name from public.services", role="anon"), ["Cut"])
        self.fails("insert into public.services (name, price_pence) values ('Free', 0)", role="anon", msg="row-level security")
        self.assertEqual(self.as_user(A, "with u as (update public.services set price_pence=0 returning 1) select count(*) from u"), ["0"])

    def test_staff_bookings(self):
        self.load("public_read", "staff_bookings")
        self.sql(f"insert into public.services (id, name, price_pence) values ('11111111-1111-1111-1111-111111111111','Cut',3000)")
        self.sql(f"insert into public.staff (user_id) values ('{S}')")
        svc = "'11111111-1111-1111-1111-111111111111'"
        self.as_user(A, f"insert into public.bookings (service_id, starts_at) values ({svc}, now())")
        self.fails(f"insert into public.bookings (service_id, starts_at, status) values ({svc}, now(), 'paid')",
                   role="authenticated", user=A, msg="row-level security")
        self.assertEqual(self.as_user(A, "with u as (update public.bookings set status='paid' returning 1) select count(*) from u"), ["0"])
        self.assertEqual(self.as_user(B, "select count(*) from public.bookings"), ["0"])
        self.assertEqual(self.as_user(S, "select count(*) from public.bookings"), ["1"])
        self.assertEqual(self.as_user(S, "with u as (update public.bookings set status='cancelled' returning 1) select count(*) from u"), ["1"])
        self.assertEqual(self.sql("with u as (update public.bookings set status='paid' returning 1) select count(*) from u", role="service_role"), ["1"])
        self.fails("select public.is_staff()", role="anon", msg="permission denied")

    def test_entitlements_cannot_be_self_granted(self):
        self.load("entitlements")
        self.sql(f"insert into public.entitlements (user_id) values ('{A}')")
        self.assertEqual(self.as_user(A, "select plan from public.entitlements"), ["free"])
        self.assertEqual(self.as_user(A, "with u as (update public.entitlements set plan='pro' returning 1) select count(*) from u"), ["0"])
        self.fails(f"insert into public.entitlements (user_id, plan) values ('{B}', 'pro')", role="authenticated", user=B,
                   msg="row-level security")
        self.assertEqual(self.as_user(B, "select count(*) from public.entitlements"), ["0"])
        self.sql(f"update public.entitlements set plan='pro' where user_id='{A}'", role="service_role")
        self.assertEqual(self.as_user(A, "select plan from public.entitlements"), ["pro"])

    def test_column_guard(self):
        self.load("column_guard")
        self.sql(f"insert into public.profiles (id, display_name) values ('{A}', 'Amy')")
        self.as_user(A, "update public.profiles set display_name='Amy B'")
        self.assertEqual(self.as_user(A, "select display_name, role from public.profiles"), ["Amy B|member"])
        self.fails("update public.profiles set role='admin'", role="authenticated", user=A, msg="permission denied")

    def test_signup_trigger(self):
        self.load("entitlements", "column_guard", "signup_trigger")
        new = "00000000-0000-0000-0000-0000000000d4"
        self.sql(f"""insert into auth.users (id, email, raw_user_meta_data) values ('{new}', 'd@x.test', '{{"display_name": "Dee"}}')""")
        self.assertEqual(self.as_user(new, "select display_name from public.profiles"), ["Dee"])
        self.assertEqual(self.as_user(new, "select plan from public.entitlements"), ["free"])

    def test_storage_policies(self):
        self.load("storage_policies")
        self.sql("insert into storage.buckets (id, name) values ('avatars', 'avatars')")
        self.as_user(A, f"insert into storage.objects (bucket_id, name) values ('avatars', '{A}/me.jpg')")
        self.fails(f"insert into storage.objects (bucket_id, name) values ('avatars', '{B}/me.jpg')",
                   role="authenticated", user=A, msg="row-level security")
        self.assertEqual(self.as_user(B, "select count(*) from storage.objects"), ["0"])
        self.assertEqual(self.as_user(A, "select count(*) from storage.objects"), ["1"])

    def audit(self):
        out = {}
        for part in re.split(r"\n(?=-- [A-H]\. )", "\n" + self.blocks["audit"]):
            m = re.match(r"\s*-- ([A-H])\. ", part)
            if m:
                out[m.group(1)] = self.sql(part)
        return out

    def test_audit_on_good_schema(self):
        self.load("private_rows", "public_read", "staff_bookings", "entitlements", "column_guard", "signup_trigger", "storage_policies")
        self.sql("insert into storage.buckets (id, name) values ('avatars', 'avatars')")
        res = self.audit()
        self.assertEqual(res["A"], [])
        self.assertEqual(res["B"], [])
        self.assertEqual(res["C"], [])
        self.assertEqual(res["D"], ["services|Anyone can see active services|SELECT"])
        self.assertEqual(res["E"], ["bookings|status|Customers create their own pending bookings|INSERT",
                                    "bookings|status|Staff can update bookings|UPDATE"])
        self.assertEqual(res["F"], [])
        self.assertEqual(sorted(res["G"]), ["handle_new_user", "is_staff"])
        self.assertEqual(res["H"], [])

    def test_audit_on_bad_schema(self):
        self.sql("""
            create table public.open_table (id int);
            create table public.no_policies (id int);
            alter table public.no_policies enable row level security;
            create table public.leaky (id int, user_id uuid);
            alter table public.leaky enable row level security;
            create policy "everyone" on public.leaky for select using (true);
            create table public.profiles_bad (id uuid primary key, is_pro boolean default false);
            alter table public.profiles_bad enable row level security;
            create policy "own" on public.profiles_bad for update to authenticated using (auth.uid() = id);
            create view public.all_profiles as select * from public.profiles_bad;
            create function public.dangerous() returns int language sql security definer as $$ select 1 $$;
            insert into storage.buckets (id, name, public) values ('uploads', 'uploads', true);
        """)
        res = self.audit()
        self.assertEqual(res["A"], ["open_table"])
        self.assertEqual(res["B"], ["no_policies"])
        self.assertEqual(res["C"], ["leaky|everyone|SELECT|{public}"])
        self.assertIn("leaky|everyone|SELECT", res["D"])
        self.assertEqual(res["E"], ["profiles_bad|is_pro|own|UPDATE"])
        self.assertEqual(res["F"], ["all_profiles"])
        self.assertEqual(res["G"], ["dangerous"])
        self.assertEqual(res["H"], ["uploads"])

    def test_rls_before_create_trap(self):
        # The bug from a public test of AI-written SQL: enabling RLS before the table exists.
        self.sql("alter table if exists public.notes2 enable row level security; create table public.notes2 (id int);")
        self.assertEqual(self.sql("select relrowsecurity from pg_class where relname='notes2'"), ["f"])


if __name__ == "__main__":
    unittest.main()
