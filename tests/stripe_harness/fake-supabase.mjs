// In-memory stand-in for the tiny part of @supabase/supabase-js the Stripe playbook uses.
export const db = globalThis.__db ?? (globalThis.__db = { bookings: [], stripe_events: [], users: {} });

function query(table) {
  const filters = [];
  let action = null;
  let payload = null;
  const api = {
    select() { action = action ?? "select"; return api; },
    eq(col, val) { filters.push([col, val]); return api; },
    insert(row) {
      if (table === "stripe_events" && db.stripe_events.some((e) => e.id === row.id)) {
        return Promise.resolve({ error: { code: "23505", message: "duplicate key" } });
      }
      db[table].push({ ...row });
      return Promise.resolve({ error: null });
    },
    update(obj) { action = "update"; payload = obj; return api; },
    single() {
      const row = db[table].find((r) => filters.every(([c, v]) => r[c] === v));
      return Promise.resolve({ data: row ?? null, error: row ? null : { message: "not found" } });
    },
    then(resolve) {
      if (action === "update") {
        db[table].filter((r) => filters.every(([c, v]) => r[c] === v)).forEach((r) => Object.assign(r, payload));
      }
      resolve({ error: null });
    },
  };
  return api;
}

export function createClient() {
  return {
    auth: {
      async getUser(token) {
        const user = db.users[token];
        return { data: user ? { user } : { user: null }, error: user ? null : { message: "bad token" } };
      },
    },
    from: query,
  };
}
