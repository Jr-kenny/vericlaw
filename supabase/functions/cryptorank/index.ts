/**
 * Keyless CryptoRank proxy for GenLayer validators (VeriClaw Token Intel service).
 *
 * A public GenLayer contract can't hold the CryptoRank key, so this Supabase Edge
 * Function holds CRYPTORANK_API_KEY as a secret and exposes a keyless endpoint each
 * validator calls via gl.nondet.web. Deployed alongside Tokenpost's `search` /
 * `relay` functions in the same project; it's a separate endpoint and does not
 * touch them.
 *
 * Output is normalized + bounded + stably ordered so independent validators
 * converge on the same surface (consensus). Secret: CRYPTORANK_API_KEY.
 *
 * NOTE: the exact CryptoRank v2 paths below are best-inference and are verified
 * live against the key (see `?probe=1`) before the Token Intel contract is wired.
 */

const BASE = "https://api.cryptorank.io/v2";

Deno.serve(async (req) => {
  const key = Deno.env.get("CRYPTORANK_API_KEY");
  if (!key) return json({ error: "cryptorank backend not configured" }, 500);
  const h = { "X-Api-Key": key, "Content-Type": "application/json" };

  const url = new URL(req.url);
  let symbol = "";
  let id = "";
  if (req.method === "POST") {
    const b = await req.json().catch(() => ({}));
    symbol = String(b.symbol ?? "").trim().toUpperCase().slice(0, 20);
    id = String(b.id ?? "").trim().slice(0, 20);
  } else {
    symbol = String(url.searchParams.get("symbol") ?? "").trim().toUpperCase().slice(0, 20);
    id = String(url.searchParams.get("id") ?? "").trim().slice(0, 20);
  }

  // probe mode: report which candidate endpoints respond, so we lock the real
  // paths against the live key without guessing in the contract.
  if (url.searchParams.get("probe") === "1") {
    const candidates = [
      `${BASE}/currencies?symbol=${symbol || "BTC"}`,
      `${BASE}/currencies/map?symbol=${symbol || "BTC"}`,
      `${BASE}/currencies/${id || "bitcoin"}`,
      `${BASE}/currencies/${id || "bitcoin"}/vesting`,
      `${BASE}/currencies/${id || "bitcoin"}/unlocks`,
      `${BASE}/vesting?keys=${id || "bitcoin"}`,
    ];
    const report: Record<string, number> = {};
    for (const c of candidates) {
      try {
        const r = await fetch(c, { headers: h });
        report[c] = r.status;
      } catch (_e) {
        report[c] = -1;
      }
    }
    return json({ probe: report });
  }

  // resolve symbol -> id when only a symbol was given
  try {
    if (id === "" && symbol !== "") {
      const lr = await fetch(`${BASE}/currencies?symbol=${symbol}`, { headers: h });
      const ld = await lr.json().catch(() => ({}));
      const first = (ld.data ?? ld.currencies ?? [])[0];
      if (first) id = String(first.id ?? first.key ?? first.slug ?? "");
    }
    if (id === "") return json({ error: "could not resolve token" }, 404);

    const vr = await fetch(`${BASE}/currencies/${id}/vesting`, { headers: h });
    const vd = await vr.json().catch(() => ({}));
    return json(normalizeVesting(id, vd));
  } catch (_e) {
    return json({ id, error: "cryptorank fetch failed" }, 502);
  }
});

// Bound + round + stably order so validators converge.
function normalizeVesting(id: string, raw: Record<string, unknown>) {
  const d = (raw.data ?? raw) as Record<string, unknown>;
  const allocsRaw = (d.allocations ?? []) as Record<string, unknown>[];
  const allocations = allocsRaw
    .map((a) => ({
      name: String(a.name ?? "").slice(0, 60),
      percentOfSupply: round(a.percentOfSupply ?? a.percent),
      unlockType: String(a.unlockType ?? a.type ?? "").slice(0, 30),
    }))
    .filter((a) => a.name !== "")
    .sort((a, b) => a.name.localeCompare(b.name))
    .slice(0, 15);
  return {
    id,
    unlockedPercent: round(d.unlockedPercent ?? d.unlocked),
    lockedPercent: round(d.lockedPercent ?? d.locked),
    nextUnlock: d.nextUnlock
      ? {
          date: String((d.nextUnlock as Record<string, unknown>).date ?? "").slice(0, 10),
          percentOfSupply: round((d.nextUnlock as Record<string, unknown>).percentOfSupply),
        }
      : null,
    allocations,
  };
}

function round(v: unknown): number | null {
  const n = Number(v);
  if (!isFinite(n)) return null;
  return Math.round(n * 100) / 100;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
