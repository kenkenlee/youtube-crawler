# YouTube Transcript Acquisition — Resilience & Anti-Block Solution Plan

> **Audience:** AI coding agent (e.g., OpenClaw / autonomous code-gen system)
**Goal:** Generate a production-grade Python system that reliably captures YouTube
video transcripts from a user PC (WSL2, residential IP) with near-zero risk of
IP blocks, and graceful multi-tier fallback when blocks occur.
**Non-goals:** Defeating authentication, accessing private/members-only content,
or violating account security. All tiers operate on publicly available captions.
> 

---

## 1. Threat Model — Why Requests Get Blocked

YouTube's blocking is **behavioral and reputation-based**, not tool-based:

| Signal | Trigger | Mitigation Tier |
| --- | --- | --- |
| IP reputation | Datacenter/cloud IPs, prior abuse on shared IP | Residential IP (default), rotating residential proxy (fallback) |
| Request rate / burstiness | Fixed intervals, parallelism, >~300 req/hr guest | Adaptive token-bucket throttle + jitter |
| Client fingerprint | Missing/stale headers, no PO token, odd TLS | yt-dlp impersonation + PO Token provider plugin |
| Session anomalies | No cookies + high volume, repeated identical fetches | Cache-first design, optional browser cookies |
| Retry hammering | Immediate retries after 429/RequestBlocked | Circuit breaker with cool-down persistence |

Key fact: on a **residential IP in WSL2** (shares the Windows host's network), the
baseline block risk is already low. The system's primary job is to *never convert a
good IP into a flagged one*.

---

## 2. Architecture — Tiered Fallback Chain ("Ladder of Escalation")

Implement as a **strategy chain**. Each tier is attempted only if the previous tier
fails with a *retriable* error class. Success at any tier short-circuits the chain
and writes to cache.

Tier 0 Local cache (SQLite + JSON blobs) — always first, never expires by default
Tier 1 youtube-transcript-api (direct, throttled) — cheapest network path
Tier 2 yt-dlp subtitle extraction — hardened: player_client rotation,
PO Token provider plugin, optional cookies
Tier 3 yt-dlp via rotating residential proxy — only if Tier 1–2 blocked; env-configured
Tier 4 Official YouTube Data API captions.list — metadata/owned-video path (quota-based)
Tier 5 ASR fallback: yt-dlp audio → faster-whisper — guaranteed output even with zero captions

### 2.1 Tier 0 — Persistent Cache & State Store (SQLite)

- Tables: `transcripts(video_id, lang, source_tier, json, fetched_at)`,
`failures(video_id, error_class, tier, ts)`, `throttle_state(key, value)`.
- **Never** re-fetch a cached video. Cache negative results (`TranscriptsDisabled`,
`NoTranscriptFound`) with a TTL (e.g., 7 days) to avoid re-probing dead videos.
- Store circuit-breaker state here so cool-downs survive process restarts.

### 2.2 Tier 1 — `youtube-transcript-api` (v1.x instance API)

- `api = YouTubeTranscriptApi()`; `api.fetch(video_id, languages=[...])`.
- Wrap in the global rate governor (§3). Classify exceptions:
    - `RequestBlocked` / `IpBlocked` → open circuit breaker, escalate to Tier 2.
    - `TranscriptsDisabled` / `NoTranscriptFound` → negative-cache, try Tier 5 if
    ASR is enabled, else return None.
    - Network/parse errors → bounded retry (max 2) with full-jitter exponential backoff.

### 2.3 Tier 2 — `yt-dlp` Hardened Subtitle Extraction

- Always run latest yt-dlp (`pip install -U yt-dlp` check at startup; log version).
- Use the Python API with:
    - `skip_download=True`, `writesubtitles=True`, `writeautomaticsub=True`,
    `subtitleslangs`, `sleep_interval_requests≥2`.
    - **Client rotation:** try `player_client=web,mweb,android` (NOT `ios` — it drops
    cookies). Rotate on failure.
    - **PO Token provider:** install `bgutil-ytdlp-pot-provider` plugin (+ Deno/Node
    runtime for BotGuard attestation). YouTube binds PO tokens to video IDs, so
    manual tokens are obsolete — the plugin auto-generates per request.
    - **Optional cookies:** `cookies_from_browser` (e.g., `("firefox",)`) raises the
    guest rate ceiling (~300/hr → ~2000/hr) and fixes `LOGIN_REQUIRED` errors.
    Make this opt-in via config; warn user about account risk on heavy volume.
- Parse resulting `.vtt`/`.srt` into the same normalized segment schema as Tier 1.

### 2.4 Tier 3 — Rotating Residential Proxy (opt-in, env-driven)

- Read `YT_WEBSHARE_USER` / `YT_WEBSHARE_PASS` (Webshare `WebshareProxyConfig` for
youtube-transcript-api) or generic `YT_PROXY_HTTP(S)` URLs for yt-dlp.
- Only activate when the circuit breaker for direct access is OPEN.
    
    write a most robust, intelligent and sophiscated solution to by pass youtube ban on capturing video transcript. The solution plan shall written in .md format for AI system like openclaw to generate a most suitable solution.
    
- Must be **residential/rotating** class; datacenter proxies are pre-flagged.

### 2.5 Tier 4 — Official YouTube Data API (`captions.list` / `captions.download`)

- Requires API key/OAuth; `captions.download` only works for videos the
authenticated user owns — so treat this tier as: (a) legitimate path for own
content, (b) metadata verification that captions exist before spending Tier 5 effort.

### 2.6 Tier 5 — ASR Fallback (`faster-whisper`)

- `yt-dlp -x --audio-format m4a` (respecting the same throttle), then transcribe
locally with `faster-whisper` (`small`/`medium` model; auto-select by available
RAM/GPU in WSL2). Emits identical segment schema with `source_tier="asr"`.
- This tier makes the system **unblockable in the limit**: worst case it costs one
audio download per video.

---

## 3. Rate Governor (Global, Shared by All Tiers)

- **Token bucket:** default capacity 10, refill 1 token / 20 s (≈ 180 req/hr,
safely under the ~300/hr guest ceiling). Configurable.
- **Jitter:** every inter-request delay = `base + uniform(0, base×0.6)`; never
fixed intervals; never parallel requests to YouTube from the same IP.
- **Adaptive backoff:** on any 429/`RequestBlocked`, multiply base delay ×2
(cap 15 min) and persist; decay ×0.9 per hour of clean operation.
- **Circuit breaker per tier:** CLOSED → OPEN after 2 consecutive block-class
errors; OPEN holds for 45 min (persisted in SQLite); HALF-OPEN probes with a
single request before closing.
- **Hard stop rule:** if Tiers 1–3 are all OPEN, do not hammer — drain the queue
into a "deferred" state, optionally proceed with Tier 5 only, and print a clear
resume ETA.

---

## 4. Error Taxonomy (Drive All Control Flow From This)

| Class | Examples | Action |
| --- | --- | --- |
| `BLOCKED` | `IpBlocked`, `RequestBlocked`, HTTP 429, "Sign in to confirm you're not a bot" | Open breaker, escalate tier |
| `UNAVAILABLE` | `TranscriptsDisabled`, `NoTranscriptFound`, private/deleted | Negative-cache; Tier 5 if enabled |
| `TRANSIENT` | Timeouts, ConnectionReset, 5xx | Retry ≤2 with full-jitter backoff |
| `TOOL_ROT` | Parse errors, extractor failures, schema changes | Log loudly, self-update yt-dlp, escalate tier |
| `FATAL` | Bad video ID, config errors | Fail fast with actionable message |

---

## 5. Interfaces & Deliverables the Agent Must Generate

1. `transcript_engine/` package:
    - `store.py` (SQLite cache + state), `governor.py` (rate limiter + breakers),
    - `tiers/` (one module per tier, common `TranscriptTier` ABC:
    `fetch(video_id, langs) -> list[Segment] | Unavailable | Blocked`),
    - `engine.py` (chain orchestrator), `errors.py` (taxonomy),
    - `cli.py`: `fetch <id|url>...`, `batch <file>`, `status` (breaker/queue state),
    `resume`, flags `-langs`, `-asr`, `-cookies-from-browser`, `-proxy`.
2. Normalized output schema:
`{"video_id", "lang", "source_tier", "segments":[{"text","start","duration"}]}`.
3. `pyproject.toml` with pinned minimums: `youtube-transcript-api>=1.0`,
`yt-dlp` (always-latest policy), optional extras `[proxy]`, `[asr]`, `[pot]`.
4. Startup self-check: yt-dlp version freshness, PO-token plugin presence,
Deno/Node availability, WSL2 network sanity, proxy env detection.
5. Structured JSON logging of every YouTube request: tier, latency, outcome,
current bucket level — this is the data needed to tune throttle values.
6. `README.md` with WSL2 setup, cookie export instructions, and an explicit
Terms-of-Service note (personal/research use, no redistribution of captions).

---

## 6. Operating Principles (Encode as Comments/Assertions)

1. **Cache is the best anti-ban technology.** A request never sent cannot be blocked.
2. **Sequential only.** One in-flight YouTube request process-wide (use a lock).
3. **Escalate, don't retry-in-place**, on block-class errors.
4. **Stop means stop.** Persisted cool-downs; restarting the script must not reset them.
5. **Freshness is survival.** yt-dlp older than 30 days is presumed broken; warn/update.
6. **Residential IP is an asset.** The proxy tier exists to *protect* the home IP,
not because the home IP is insufficient.
7. **ASR is the floor.** With Tier 5 enabled, the pipeline's success rate is
decoupled from YouTube's anti-bot posture entirely.

---

## 7. Acceptance Tests

- 50-video batch on residential IP completes with 0 block events (Tier 1/2 only).
- Simulated `RequestBlocked` (mocked) → breaker opens,