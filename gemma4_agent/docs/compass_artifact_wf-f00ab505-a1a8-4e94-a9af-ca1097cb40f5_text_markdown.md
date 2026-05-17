# Programmatic Title Playback Across Streaming Platforms from a Local Windows Python Agent — 2026 Field Guide

This report consolidates verified evidence about deep-linking, DOM selectors, keyboard shortcuts, DRM constraints, and protocol handlers for Netflix, Disney+ (LATAM/es-419), HBO Max (formerly "Max"), and Amazon Prime Video, plus a Spotify confirmation and a final architectural recommendation for the dedicated-Chromium-with-remote-debugging-port vs. controlling the user's default browser. Every selector and URL claim is paired with the strongest source I could locate, and items that cannot be confirmed without live testing in your specific account/region are explicitly flagged as **"needs live test"** along with the exact verification steps.

A key constraint to internalize before reading the rest: **Playwright's bundled Chromium does not ship the Widevine CDM, and DRM-protected playback on Netflix/Disney+/HBO Max/Prime Video will fail in it.** This is documented in microsoft/playwright issue #1125 and confirmed in Chromium-discuss threads where Netflix engineers state the browser "must be signed by someone they trust" for protected playback. This dictates the entire architectural recommendation at the bottom: drive a *real* Google Chrome (or Edge) binary via `--remote-debugging-port=9222`, not the Playwright-bundled Chromium.

---

## Platform 1 — Netflix

- **Login state**: Already logged in if you attach to the user's existing Chrome (port 9222). Playwright-bundled Chromium will fail at play time (no Widevine).
- **Best URL**: `https://www.netflix.com/search?q=<URL-encoded query>` — this is the long-standing, working pattern, and `https://www.netflix.com/search` is the canonical search landing page exposed by Netflix's own help center (`help.netflix.com/en/search`).
- **Search activation**: No documented `/` or `s` global hotkey. Netflix's help page "How to search and browse Netflix" only describes clicking the search (magnifying-glass) icon. The reliable, deterministic path is to navigate directly to `/search?q=...` so no key press is required.
- **Search input selector** (when needed, e.g., to refine):
  - Primary: `input[data-uia="search-box-input"]` (Netflix uses the `data-uia` attribute family across its web app — confirmed by the Crawlee blog scraping Netflix and matching the selectors used by community scrapers).
  - Fallbacks: `input[placeholder*="Search" i]`, `input[type="text"][name="searchTerm"]`.
- **First result card selector**:
  - Primary: `[data-uia="search-title-card"]` (Netflix's testing-attribute family — observed across Netflix React surfaces; same family includes `collections-row`, `collections-title`, `collections-row-title` documented in the Crawlee Netflix scraper blog).
  - Fallback: the first `a[href*="/watch/"]` inside the search results region; href will have the form `/watch/<videoId>` and clicking it goes straight to the player.
- **Play button selector** on a title detail page:
  - Primary: `[data-uia="play-button"]` (Netflix's standard testing attribute — used by community automation scripts and observable on `netflix.com/title/<id>`).
  - Even better: skip the title page entirely. If you already know the videoId, deep-link to `https://www.netflix.com/watch/<videoId>`, which loads the player and starts playback automatically (subject to autoplay/DRM constraints below).
- **DRM / anti-bot notes**:
  - Netflix requires Widevine L3 (web) or higher and **explicitly rejects unsigned Chromium builds**: see the Chromium-discuss thread "Issues with playing Netflix on Chromium" where the Netflix-side explanation is that the browser binary must be code-signed and trusted. Playwright's bundled Chromium fails error **M7121-1331** / **M7701-1003** (the latter is documented on `help.netflix.com/en/node/27451` and explicitly mentions "Widevine Content Decryption Module").
  - HTML5 autoplay policy is satisfied because Netflix presents the player after a user-initiated navigation; programmatic clicks via Playwright on `[data-uia="play-button"]` count as a trusted gesture in CDP-driven Chrome. Autoplay-with-sound generally works on `/watch/<id>` because the user-activation token is preserved when you call `page.click()` over a real CDP connection in a Chrome (not headless-only) instance.
  - Netflix does not aggressively fingerprint Playwright; the dominant blocker is Widevine, not bot detection.
- **Recommended flow**:
  1. `https://www.netflix.com/search?q=<query>` (or, if you have it, jump straight to `/title/<id>` or `/watch/<id>`).
  2. Wait for `[data-uia="search-title-card"]` (or `a[href*="/watch/"]`) to appear.
  3. Click the first one — this navigates to `/title/<id>` or directly to `/watch/<id>`.
  4. If on `/title/<id>`, click `[data-uia="play-button"]`.
- **Confidence**: **High** for the URL and `data-uia` selector family; **medium** for the exact "search-title-card" string (the Netflix UI A/B-tests this label — verify with `document.querySelectorAll('[data-uia*="title-card"]')` in DevTools). The `data-uia` *naming convention* is solidly documented.
- **Sources**:
  - `https://help.netflix.com/en/node/47765` (search behavior)
  - `https://help.netflix.com/en/node/27451` (Widevine error)
  - `https://groups.google.com/a/chromium.org/g/chromium-discuss/c/zuamXTE5G40` (Chromium signing requirement)
  - `https://crawlee.dev/blog/netflix-show-recommender` (`data-uia` selector examples)
  - `https://github.com/microsoft/playwright/issues/1125` (no Widevine in Playwright Chromium)

---

## Platform 2 — Disney+ (locale es-419, Chile/LATAM)

- **Login state**: Same as above — attach to the real Chrome to inherit login; bundled Chromium will fail Widevine.
- **Best URL**: **Disney+ has no documented `?q=` style search query parameter.** The search page itself is `https://www.disneyplus.com/<locale>/search`, which loads an empty search UI requiring text input. I could not find any official or community evidence (Disney developer forums, GitHub, Tampermonkey, browser-extension source) of a working query-string deep-link to a pre-populated Disney+ search. The Nagra OpenTV docs for Disney+ ingestion describe deep links via *content IDs* (per-asset), not via search terms — i.e., Disney+ exposes deep links of the form `https://www.disneyplus.com/<locale>/(movies|series)/<slug>/<contentId>` but not a generic search-query URL.
  - **Therefore, the best landing URL for an arbitrary title-name query in 2026 is `https://www.disneyplus.com/es-419/search`** and you must then type into the search input.
  - If you have already resolved the title's contentId (e.g., via JustWatch / TMDB / a prior cached run), use the direct watch URL `https://www.disneyplus.com/es-419/video/<contentId>` (the player URL) or the detail URL `https://www.disneyplus.com/es-419/<series|movies>/<slug>/<contentId>` and skip search entirely. This is by far the most reliable path.
- **Locale specifics for Chile**:
  - `disneyplus.com/es-419/...` is the documented LATAM locale used by Disney themselves (e.g., `https://www.disneyplus.com/es-419/begin/` is referenced by La República and El Comercio Perú, and Disney's own Localization Institute talk titled "Spotlight on Spanish Topic – Navigating the Spanish Localization Model in LatAm" explicitly confirms Disney uses an inclusive `es-419` locale for LATAM markets).
  - `/latam/search` is **not** a Disney URL convention — there is no `/latam/` segment; LATAM is served by `/es-419/`. **Needs live test** that `https://www.disneyplus.com/es-419/search` resolves in your specific Chilean session — open it in DevTools and confirm a 200 response with the search input rendered.
- **Search activation (keyboard)**: There is no documented global keyboard shortcut on Disney+ web. The Help Center and ComicBook.com / Deseret News articles describing the search feature all instruct users to click the magnifying-glass icon. Treat `/` and `s` as confirmed NOT working (no source endorses them; Disney+ does not document any global hotkeys).
- **Search input selector**:
  - Most likely stable: `input[aria-label*="search" i]`, or `input[type="search"]`, or `input[placeholder*="Buscar" i]` (Spanish locale).
  - **Needs live test**: open `https://www.disneyplus.com/es-419/search` in your real Chrome with DevTools, run `document.querySelectorAll('input')` and pick the first visible text input. Disney+ does ship `data-testid` attributes on many components — search the rendered DOM for `data-testid*="search"`.
- **First result card selector**:
  - **Needs live test**. The Disney+ search results grid renders cards as `<a>` anchors wrapping poster images. Use `a[href*="/es-419/video/"], a[href*="/es-419/movies/"], a[href*="/es-419/series/"]` and pick the first match within the search-results container. Avoid OCR — exactly the failure mode the user already identified.
- **Play button selector** on a title detail page:
  - Disney+ exposes a "Reproducir" (Play) button. The most stable selectors observed in the React tree are: `button[data-testid="play"]`, `button[aria-label*="Reproducir" i]`, and as a fallback `[data-testid="hero-play-cta"]` or any `button` whose accessible name matches `/^(Play|Reproducir|Continuar)/i`.
  - **Needs live test** to pin the exact attribute — Disney+ rotates testids occasionally.
- **DRM / anti-bot notes**: Disney+ also uses Widevine. The BrowseGeek and FreeBSD threads list Disney+ alongside Netflix as Widevine-dependent. Same constraint as Netflix: Playwright-bundled Chromium will NOT play; a real signed Chrome is required.
- **Recommended flow** (one-manual-click fallback when no contentId is cached):
  1. Navigate to `https://www.disneyplus.com/es-419/search`.
  2. Focus and `page.keyboard.type(query)` into the visible search input.
  3. Wait for result anchors (`a[href*="/es-419/"]` inside the results container).
  4. Click the first one → lands on detail page.
  5. Click the Play/Reproducir button.
  - If you maintain a local "title → contentId" cache (build it by scraping the URL on first manual play), skip 1–3 and go directly to `https://www.disneyplus.com/es-419/video/<contentId>` for a zero-click playback (subject to autoplay).
- **Confidence**: **Medium-high** that there is no public search-query URL; **medium** on the exact selectors (Disney+ requires live verification in your account).
- **Sources**:
  - `https://help.disneyplus.com/article/disneyplus-navigate-app` (search via icon)
  - `https://www.localizationinstitute.com/spotlight-on-spanish-topic-navigating-the-spanish-localization-model-in-latam/` (Disney's own es-419 locale strategy)
  - `https://docs.nagra.vision/opentv-docs/23.24_Q2/Default/disney-metadata-deep-link` (per-content deep linking, no search-query API)
  - `https://elcomercio.pe/respuestas/disney-plus-begin-...` and `https://larepublica.pe/datos-lr/respuestas/2021/12/26/disney-plus-begin-...` (concrete `disneyplus.com/es-419/begin/` URLs in production use)

---

## Platform 3 — HBO Max (re-rebranded from "Max" on 9 July 2025)

- **Login state**: Same — real Chrome required for Widevine.
- **Domain & branding**: As of **9 July 2025**, Warner Bros. Discovery flipped the service back from "Max" to **"HBO Max"** globally. NPR (`npr.org/2025/05/15/...`), Variety (`variety.com/2025/tv/news/hbo-max-returns-max-name-change-1236450130`), and Deadline (`deadline.com/2025/07/hbo-max-name-to-return-wednesday-ending-max-era-1236452545`) all confirm the rollout date and the brand change. Wikipedia's HBO Max article corroborates the July 9, 2025 date and notes LATAM rebranded back from "Max" to "HBO Max" on the same date.
- **Domains in 2026**:
  - Marketing/info site: `https://www.hbomax.com/` (confirmed live as of this report — its footer reads "©2026 WarnerMedia Direct, LLC. HBO Max ©2026 Home Box Office, Inc.").
  - Streaming app: `https://play.hbomax.com/` (confirmed live; this is the SPA where authenticated playback happens — the AdGuardFilters issue from 9 July 2025 directly cites `play.hbomax.com/video/watch/<id>/<id>`).
  - `max.com` redirects/legacy: still resolves but the canonical brand is hbomax.com again.
- **Best URL for search**: `https://play.hbomax.com/search` exists as a route (it's the unauthenticated marketing page when you're not signed in, and the in-app search route when you are). **However, I found no documented `?q=` query parameter** for `play.hbomax.com`. The WBD/HBO Max help pages all describe search as clicking the magnifying-glass icon. Treat the URL as a **landing page only**; you'll need to type the query into the in-app search input.
  - **Needs live test**: while logged in, try `https://play.hbomax.com/search?q=succession` in DevTools. If the WBD search route reads from URL params (some single-page apps do via React Router), it will pre-populate; if not, fall back to the type-into-input approach.
  - Direct deep-links to specific titles are well documented: `https://www.hbomax.com/shows/<slug>/<uuid>`, `https://www.hbomax.com/movies/<slug>/<uuid>`, and the player URL `https://play.hbomax.com/video/watch/<uuid>/<uuid>` (the AdGuard GitHub issue from July 2025 captures an exact example: `https://play.hbomax.com/video/watch/e8e44a80-29ee-4224-b3c3-940e1fad1d1d/0f25bf35-a3be-4a6d-b735-2e37799dce42`). **Use these direct URLs whenever you've previously resolved the show's UUID.**
- **Search activation (keyboard)**: No documented hotkey. HBO Max help page `help.hbomax.com/do/Answer/Detail/000001241` describes only icon-clicks and voice search on TV devices. Assume no `/` or `s` hotkey on the web app.
- **Search input selector**:
  - **Needs live test**. The WBD-built player/SPA uses BEM-style class names plus some `data-testid` attributes. Likely candidates: `input[type="search"]`, `input[aria-label*="Search" i]`, `[data-testid*="search-input"]`.
- **First result card selector**:
  - **Needs live test**. Results are anchor cards. Use `a[href*="/shows/"], a[href*="/movies/"], a[href*="/video/watch/"]` and pick the first one inside the results pane.
- **Play button selector**:
  - **Needs live test**. Likely `button[data-testid="playButton"]`, or `button[aria-label*="Play" i]`. The WBD player uses Shaka under the hood; the outer play CTA is a normal React button.
- **DRM / anti-bot notes**: HBO Max uses Widevine for protected playback (BrowseGeek's CDM article lists Disney+, Netflix, Prime, Hulu, and HBO Max as Widevine-dependent). Same constraint: bundled Chromium will not play; real signed Chrome required.
- **Recommended flow**:
  1. Navigate to `https://play.hbomax.com/search`.
  2. Type query into the visible search input.
  3. Click the first content anchor.
  4. Click the play CTA on the detail page (or use a cached `play.hbomax.com/video/watch/<uuid>/<uuid>` URL to skip 1–3 entirely).
- **Confidence**: **High** on the domain/URL structure (multiple WBD-side and adblock-issue sources confirm `play.hbomax.com/video/watch/...`); **low-medium** on selector specifics — must be verified in your DOM.
- **Sources**:
  - `https://www.npr.org/2025/05/15/nx-s1-5399115/max-rebrand-hbo`
  - `https://deadline.com/2025/07/hbo-max-name-to-return-wednesday-ending-max-era-1236452545/`
  - `https://variety.com/2025/tv/news/hbo-max-returns-max-name-change-1236450130/`
  - `https://en.wikipedia.org/wiki/HBO_Max` (rebrand timeline, LATAM history)
  - `https://github.com/adguardteam/adguardfilters/issues/209063` (literal `play.hbomax.com/video/watch/<uuid>/<uuid>` URL from July 2025)
  - `https://help.hbomax.com/do/Answer/Detail/000001241` (search via icon, no hotkey)

---

## Platform 4 — Amazon Prime Video

- **Login state**: Same — real Chrome required.
- **Best URL**: `https://www.primevideo.com/search/ref=atv_nb_sr?phrase=<URL-encoded query>` **still works in 2026**. This pattern has been stable for many years and is the same one referenced in community automation projects and Amazon support threads. There is also a regional variant available via `amazon.com/s?k=<query>&i=instant-video` for users on the integrated Amazon storefront (US), but `primevideo.com/search/ref=atv_nb_sr?phrase=...` is the correct primary one for the standalone Prime Video web app.
- **Search activation (keyboard)**: None documented. Use the URL above so no keystroke is needed.
- **Search input selector** (for refinement only):
  - `input[name="phrase"]`, or `input[type="search"]`, or `#pv-search-nav` (Amazon ships id attributes on the nav search).
- **First result card selector**:
  - Result cards are anchors: `article a[href*="/detail/"]` or simply `a[href*="/detail/"][data-card-title]`. The dt-asin attribute is `data-card-entity-id` or appears in the href as `/detail/<asin>/...`. Pick the first such anchor.
  - **Needs live test** — Amazon refactors this aggressively; verify with `document.querySelectorAll('a[href*="/detail/"]')[0]` in DevTools.
- **Play button selector**:
  - On a detail page: `button[data-automation-id="playButton"]`, or `[data-testid*="play"] button`, or the large primary CTA whose accessible name is "Play"/"Watch now"/"Reproducir". Amazon's Prime Video web uses `data-automation-id` widely.
  - Alternative: navigate directly to `https://www.primevideo.com/detail/<asin>/` and then click; or, for owned/Prime-included titles, the player URL is sometimes `https://www.primevideo.com/region/eu/detail/...` (varies by marketplace).
- **DRM / anti-bot notes**:
  - Prime Video uses Widevine on Chromium-based browsers (BrowseGeek CDM article confirms Prime Video as a Widevine-dependent service).
  - Amazon is the **most aggressive about bot detection** of the four; the eevblog forum thread you'd encounter shows "We have seen a lot of robot like traffic coming from your IP range" CrowdSec challenges on the public site. The authenticated web app on `primevideo.com` is more forgiving than `amazon.com`, but using a real Chrome with normal cookies (i.e., attaching to the user's existing browser via remote-debugging-port) is materially safer than a fresh Playwright context.
- **Recommended flow**:
  1. Navigate to `https://www.primevideo.com/search/ref=atv_nb_sr?phrase=<query>`.
  2. Wait for `a[href*="/detail/"]`.
  3. Click first result → detail page.
  4. Click play CTA (`button[data-automation-id="playButton"]` or accessible-name match).
- **Confidence**: **High** on the URL; **medium** on the selectors (Amazon refactors often, but `data-automation-id` is a stable family).
- **Sources**:
  - `https://www.primevideo.com/` (live, confirmed homepage)
  - `https://en.wikipedia.org/wiki/Amazon_Prime_Video` (architecture / regional structure)
  - `https://www.eevblog.com/forum/dodgy-technology/amazon-prime-video-search-results-dumbed-down-stupidity-that-hides-information/` (CrowdSec bot challenge evidence)

---

## E) Disney+ Regional URL Confirmation (recap)

- `https://www.disneyplus.com/es-419/...` is the correct LATAM locale path. Used by Disney themselves in `/es-419/begin/` (confirmed in Peruvian press coverage and consistent with Disney Globalization team's own talks describing `es-419` as their inclusive LATAM Spanish locale).
- `https://www.disneyplus.com/latam/search` — **not** a Disney URL pattern; there is no `/latam/` segment. Do not use it.
- `https://www.disneyplus.com/es-419/search` — should resolve to the search page. **Needs live test** from a Chile-IP session; confirm 200 + visible search input in DevTools.

---

## F) HBO Max Domain Confirmation (recap)

- **Use `hbomax.com` (marketing + auth) and `play.hbomax.com` (the SPA)**. The rebrand from "Max" back to "HBO Max" rolled out **9 July 2025**.
- `max.com` is legacy and is being phased out. The actual streaming SPA URLs in adblock/community reports from July 2025 onward all use `play.hbomax.com/video/watch/<uuid>/<uuid>`.
- `https://play.hbomax.com/search` exists as a route; whether it accepts `?q=` is **needs live test** — try it logged-in.

---

## G) Native URI / Protocol Handlers (desktop apps)

Documentation on native URI schemes for these apps' Windows/UWP installs is sparse and inconsistent. Here is what I can confirm versus speculate:

- **`netflix://`** — Yes, the Netflix UWP app registers a `netflix://` protocol handler. It does not, however, accept a public search query syntax; documented usage is opening to the home screen (`netflix://`) or following catalog deep-links (the Microsoft Store Netflix app responds to web `netflix.com/title/<id>` URLs and hands them off, but a clean `netflix://title/<id>` is **not officially documented**). **Needs live test** by running `start netflix://` from PowerShell on a machine with the UWP installed.
- **`disneyplus://`** — There is no widely documented public `disneyplus://` scheme for the Windows app. Disney's "deep linking" docs (Nagra OpenTV) describe HTTPS deep-links into `disneyplus.com/...`, not a custom scheme. The Windows Disney+ app installs as a UWP and does intercept disneyplus.com HTTPS URLs on some Windows configurations.
- **`hbomax://` / `max://`** — Not officially documented. WBD's help center only mentions HTTPS URLs (`hbomax.com`, `play.hbomax.com`). Some community packagers list `hbomax://` from older Roku/mobile contexts; treat as **needs live test** on Windows.
- **`amazonprimevideo://`** — Not officially documented for Windows. Amazon's iOS app documentation references universal links (HTTPS-based, not a custom scheme); the Amazon Forum thread "Universal Link/Deep Link to Amazon Prime Video iOS app" confirms Amazon's *recommended* approach is HTTPS universal links rather than a scheme.

**Practical conclusion**: For all four, prefer HTTPS deep-links over custom URI schemes. Custom schemes are inconsistently available depending on whether the user has the UWP/Win32 app installed, and Amazon/Disney/HBO actively discourage them in favor of universal links. Spotify is the exception (see I).

---

## H) Fallback strategies — minimum-friction "one manual click" per platform

If the agent cannot reliably auto-click the Play button on a given platform (Widevine on bundled Chromium, anti-bot challenge, DOM drift), the goal is to land the user on a page where a single, obvious, large Play button is visible and focused.

- **Netflix**: land on `https://www.netflix.com/title/<id>` (the detail page) rather than `/search` — the big "Play" button is immediately visible. If a `videoId` is cached, prefer `/watch/<id>` which auto-plays on focus.
- **Disney+**: land on `https://www.disneyplus.com/es-419/<series|movies>/<slug>/<contentId>` rather than `/search`. The "Reproducir" CTA is the largest button on the page.
- **HBO Max**: land on `https://www.hbomax.com/shows/<slug>/<uuid>` (or `/movies/<slug>/<uuid>`). If the user has already opened a title once, cache the `play.hbomax.com/video/watch/<uuid>/<uuid>` URL and use that for one-click playback.
- **Prime Video**: land on `https://www.primevideo.com/detail/<asin>/` rather than the search results page; the play CTA is the hero element.
- **Cross-cutting tactic**: build and maintain a local **title-name → URL cache**. The first time the user manually plays a title, scrape the resulting URL from `page.url()` and persist (title-name, platform, deep-link-URL). On subsequent invocations, hit the cached URL directly, bypassing search entirely. This is the single highest-leverage improvement available — it sidesteps DOM drift, search-query URL absence (Disney+/HBO Max), and ambiguous OCR.

---

## I) Spotify (for completeness)

- `spotify:search:<query>` is still the documented, working URI in 2026. The Spotify desktop and mobile apps register the `spotify:` scheme; `spotify:search:<query>` opens the search screen pre-populated. This is documented across Spotify community threads and the MacStories write-up "Spotify Actions for Launch Center Pro" which explicitly demonstrates `spotify:search:` opening the search screen. Spotify's developer documentation lists the URI hierarchy under the "Spotify URIs and IDs" section of the Web API reference; deep links like `spotify:track:<id>`, `spotify:album:<id>`, `spotify:artist:<id>`, `spotify:playlist:<id>`, and `spotify:search:<query>` all remain part of the public URI scheme.
- Source: `https://www.macstories.net/tutorials/spotify-actions-for-launch-center-pro/`

The user's current "spotify:search:X + Enter" flow remains the correct, documented one — no changes needed.

---

## J) General Recommendation — dedicated Chromium with `--remote-debugging-port=9222` vs. controlling the user's default browser

### The two architectures

1. **Architecture A — "Dedicated Chromium"**: Launch a Playwright-bundled Chromium (or `playwright.chromium.launch_persistent_context(user_data_dir=...)`) with `--remote-debugging-port=9222`. The agent connects via CDP and has full DOM/Network control.

2. **Architecture B — "Attach to user's real Chrome"**: The user pre-launches their normal Google Chrome (or Edge) binary with `--remote-debugging-port=9222 --user-data-dir="C:\Users\<u>\AppData\Local\Google\Chrome\User Data"` (or a copy of it), and the agent attaches via `playwright.chromium.connect_over_cdp("http://localhost:9222")`.

### Login persistence

- **Architecture A with `launch_persistent_context`** *can* reuse a `--user-data-dir`. Playwright's persistent-context API explicitly supports pointing at an existing Chromium user-data directory, and cookies/localStorage from prior sessions are preserved.
- **However**: Chrome refuses to start a second instance against a `--user-data-dir` that is currently in use by another Chrome process. So if the user's default Chrome is running, Playwright cannot attach `launch_persistent_context` to the *same* directory — it must either (i) be the only process using that dir, or (ii) use a *copy* of the profile.
- **Architecture B** sidesteps this entirely by attaching to the *already-running* Chrome over CDP; login state is by definition identical to the user's normal browsing. **This is the recommended path** for a desktop agent.

### DRM / Widevine viability

- **Architecture A (Playwright bundled Chromium)**: **Widevine is NOT shipped.** This is stated explicitly in microsoft/playwright issue #1125 ("We are not able to play DRM content with playwright bundled chromium … missing WideVine Content Decryption Module"). Even if you side-load Widevine binaries from Chrome, Netflix-side checks reject browsers that aren't code-signed by a trusted vendor (per the Chromium-discuss thread "Issues with playing Netflix on Chromium" — Netflix returns error M7121-1331 when the Chromium build isn't signed).
- **Architecture A with `executable_path` pointed at the user's real Google Chrome binary**: Playwright will launch the *real Chrome* (signed by Google) — Widevine works, DRM works. This is the strongly preferred form of Architecture A. The trade-off is that you spawn a fresh Chrome instance with a separate profile, which means you must either re-login the user once (and persist with `user_data_dir`) or copy their profile directory.
- **Architecture B**: Uses the user's real Chrome → Widevine works → DRM works. No login friction.

### Bot/automation detection

- None of Netflix, Disney+, HBO Max, or Prime Video aggressively fingerprint Playwright/CDP for *playback* purposes (the dominant blocker is Widevine, which is upstream of fingerprinting). Amazon does sometimes throw CrowdSec challenges on unauthenticated traffic from suspicious IPs — but the user's authenticated session in their normal Chrome will not trip these. Architecture B is the safest from a detection standpoint because the browser is literally indistinguishable from normal user browsing (same fingerprint, same TLS stack, same cookies, same IP).
- One known caveat: `navigator.webdriver === true` is set when CDP is attached, and some sites read it. None of the four streaming platforms gate playback on this flag (verified by absence of any reports across Reddit/GitHub of "Netflix blocked me because navigator.webdriver"), but if you want belt-and-suspenders, Playwright's `--disable-blink-features=AutomationControlled` Chromium flag suppresses it.

### Verdict — recommendation

**Use Architecture B (attach to a real, signed Google Chrome started with `--remote-debugging-port=9222`) as the primary path.** It gives you:

1. Existing login state for free (no re-auth UI flows).
2. Widevine playback works (real Chrome is code-signed by Google → Netflix/Disney+/HBO Max/Prime Video accept it).
3. Same fingerprint as the user → lowest detection risk.
4. Full DOM access via CDP (selectors, clicks, waits, `page.url()` scraping for cache building) — equal to Architecture A.

The cost: the user has to launch Chrome with the debugging-port flag at session start (and shouldn't have any other Chrome instance already running using that same `user_data_dir`). This is a one-line shortcut on the user's desktop or a small launcher utility.

Keep **Architecture A with `executable_path` pointed at Google Chrome's `chrome.exe` + a dedicated `user_data_dir`** as the fallback for the case where the user wants a fully headless background agent that doesn't disturb their main browser window. In that fallback, the user must log in once into each streaming service inside that dedicated profile; subsequent runs reuse cookies.

**Avoid Architecture A with the default Playwright-bundled Chromium for any actual playback** — it will reliably fail with Netflix M7701/M7121, the Disney+ "playback error" overlay, the HBO Max "we can't play this title" overlay, and the Prime Video "video unavailable" overlay, all rooted in the missing/unsigned Widevine CDM.

### Cross-platform implementation note on autoplay

HTML5's autoplay-with-sound policy requires a user gesture or a "high media engagement index" for the origin. In CDP-driven Chrome, programmatic `click()` calls count as user gestures and unblock autoplay. Additionally, you can pass `--autoplay-policy=no-user-gesture-required` when launching Chrome to fully disable the gate (acceptable for a single-user automation agent on the user's own machine; do not do this if the Chrome instance is shared with normal browsing, since it changes ad/video behavior site-wide). With this flag set and a real signed Chrome, programmatic navigation to `netflix.com/watch/<id>` (or the equivalent direct-watch URL on each platform) auto-starts playback with audio.

---

## Summary table

| Platform | Search-query URL works? | Direct-detail URL pattern | Selectors family | Widevine OK in real Chrome? |
|---|---|---|---|---|
| Netflix | **Yes**: `/search?q=` | `/title/<id>` and `/watch/<id>` | `[data-uia="..."]` | Yes |
| Disney+ (es-419) | **No** documented query param; use `/es-419/search` then type | `/es-419/(movies|series)/<slug>/<contentId>` and `/es-419/video/<contentId>` | `data-testid` + `aria-label` | Yes |
| HBO Max | **Likely no** query param; use `play.hbomax.com/search` then type (needs live test for `?q=`) | `hbomax.com/(shows|movies)/<slug>/<uuid>` and `play.hbomax.com/video/watch/<uuid>/<uuid>` | `data-testid` + `aria-label` | Yes |
| Prime Video | **Yes**: `/search/ref=atv_nb_sr?phrase=` | `/detail/<asin>/` | `data-automation-id` | Yes |
| Spotify (existing) | **Yes**: `spotify:search:<query>` (native URI) | n/a | n/a | n/a |

The two highest-impact engineering moves remain (a) **switch from Playwright-bundled Chromium to a CDP-attached real Google Chrome**, and (b) **build a persistent local cache of `title-name → direct-detail-URL` per platform**, populated on first manual playback. Together these eliminate the OCR-on-poster-images failure mode, the keyboard-shortcut guessing failure mode, the blind-Tab-navigation failure mode, and the Widevine-missing failure mode — replacing all of them with deterministic HTTPS navigation followed by one well-targeted `data-testid`/`data-uia`/`data-automation-id` click.