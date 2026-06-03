# Handoff: Carter · Gemma 4 · Field UI

## Overview

This is a complete redesign of the Carter desktop client for the **gemma 4** local AI agent. It fuses three reference aesthetics into a single original interface:

1. **High information density** (your existing PyQt6 GUI) — left rail of system metrics, dense activity log
2. **Neural mesh visualization** (synapse-style) — organic graph of agent subsystems with animated signal pulses
3. **Calm cosmic aesthetic** (gemma-field-style) — particle clusters, starfield, slow rotating galaxy nebula

The result is a three-column dark UI organized around a glowing central **core** orbited by an asymmetric neural mesh, on a rotating starfield/nebula background. The whole interface responds in real time to the agent's state (`standby` / `idle` / `listening` / `thinking` / `speaking`).

## About the Design Files

The files in `prototype/` are **design references created in HTML/React-via-Babel** — a high-fidelity working prototype showing the intended look, motion, and behavior. They are **not production code to copy verbatim**. The task is to recreate these designs in **Carter's existing environment**, using its established patterns and libraries.

The prototype is built as inline JSX transpiled in-browser by Babel. Your real implementation should be a normal React app (or whatever framework Carter uses), with the same component decomposition but properly bundled, with TypeScript types added, with the SVG animation logic possibly moved to a canvas/WebGL renderer if performance matters in your environment, and with the mock state machine replaced by the real agent's IPC/WebSocket events.

If Carter doesn't have a frontend environment yet: React + Vite + TypeScript is recommended. The whole UI is SVG + CSS — no heavy 3D libraries needed.

## Fidelity

**High-fidelity (hifi).** Colors, typography, spacing, motion timings, easings, and interactions are all final. Recreate pixel-perfectly using your codebase's React + CSS conventions.

---

## Architecture

### Layout — three columns

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TOP BAR (36 px)  field · {state}   |  core·net·build  ⚙ buttons   clock│
├─────────────────────────────────────────────────────────────────────────┤
│ LEFT 240 px      │  CENTER fluid                  │  RIGHT 360 px       │
│ Substrate panel  │  state · focal · graph meta    │  Activity log       │
│  - logomark      │  ─────────────────────         │   - vertical entries│
│  - cpu/mem/gpu   │                                │   - editorial style │
│  - net/dsk/tmp   │     STARFIELD                  │                     │
│  - ctx budget    │     NEBULA BANDS               │                     │
│  - profile chips │     NEURAL MESH (mesh of 26    │                     │
│  - field k/v     │       nodes, 45 edges)         │                     │
│  - uptime/tokens │     GLOWING CORE (state-tinted)│                     │
│                  │     ORBIT RING (64 particles)  │                     │
│                  │     SIGNAL PULSES + TRAIL      │                     │
│                  │     TRACER (path follower)     │                     │
│                  │     Core label: Idle/Thinking..│                     │
│                  │  ─────────────────────         │  ─────────────      │
│                  │  field {verb} · {readout}      │  surfaces 2×2 grid  │
│                  │  > chat input + mic/attach/send│   sessions/memory/.. │
├─────────────────────────────────────────────────────────────────────────┤
│  BOTTOM BAR (22 px)  ⌖ coord · session id     |    date · clock · stable│
└─────────────────────────────────────────────────────────────────────────┘
```

Grid: `grid-template-rows: 36px 1fr 22px` outer shell; `grid-template-columns: 240px 1fr 360px` for the middle row.

### State machine

The agent has 5 visual states. Almost everything in the UI is state-driven.

| State | Trigger | Core color | Subgraph lit | Pulse spawn |
|---|---|---|---|---|
| `standby` | mic disabled | Gray (#5B6580) | none | 0/s |
| `idle` | default w/ mic on | Carmine (#B83A4A) | none | 0.8/s |
| `listening` | user typing / wake word | Bright carmine (#E55366) | voice, core | 5/s |
| `thinking` | post-submit, agent reasoning | Prussian (#2E4BA0) | core, memory, context, agent | 12/s |
| `speaking` | agent emitting reply | Gold (#C9A66B) | voice, tools, core | 7/s |

State transitions are managed by the parent (`App`) component. In production, replace the mock setTimeout-based turn machine in `app.jsx` with real agent events (e.g., a WebSocket from the Carter daemon).

---

## Design Tokens

### Colors

```css
--bg-base:     #0A0E14;  /* deep dark blue-black */
--bg-panel:    #0F1419;  /* panel surface */
--bg-elev:     #161B22;  /* elevated cards */
--hair:        #1F2733;  /* 1px dividers */

/* Prussian blue family (mesh / thinking) */
--p-blue:      #2E4BA0;
--p-blue-deep: #1B2A5E;
--p-blue-hi:   #5B7FDB;
--edge:        #2A3550;  /* default mesh edge color */

/* Carmine family (primary accent / idle / listening / red core) */
--carmine:      #B83A4A;
--carmine-deep: #7A1E2B;
--carmine-hi:   #E55366;
--carmine-pale: #F5C6CC;

/* Text */
--t-bone:   #D8DCE6;  /* primary body */
--t-second: #8B95A8;  /* secondary */
--t-muted:  #5B6580;  /* muted labels */
--t-dim:    #3F4860;  /* very dim — timestamps */

/* Activity log source tags */
--tag-tool:    #9B8DD9;  /* lavender */
--tag-mem:     #C9A66B;  /* gold */
--tag-boot:    #6FA8B0;  /* teal */
--tag-you:     #D8DCE6;  /* bone-white */
--tag-ai:      #7B95D9;  /* blue */
--tag-trig:    #B83A4A;  /* carmine */
--tag-thot:    #7B95D9;  /* blue */
--tag-sys:     #6FA8B0;  /* teal */

/* Core color sets (one per state) */
standby:   { halo: #3F4860,  mid: #5B6580,  inner: #8B95A8, hot: #D8DCE6 }
idle:      { halo: #7A1E2B,  mid: #B83A4A,  inner: #E55366, hot: #F5C6CC }
listening: { halo: #B83A4A,  mid: #E55366,  inner: #F5C6CC, hot: #FFE9EC }
thinking:  { halo: #1B2A5E,  mid: #2E4BA0,  inner: #5B7FDB, hot: #B8C6E8 }
speaking:  { halo: #6B5A2F,  mid: #C9A66B,  inner: #E8C98E, hot: #F5E6C0 }

/* Nebula tints (always contrast with core) */
standby:   gray gray
idle:      blue + faint red
listening: amber + blue
thinking:  red + amber
speaking:  blue + red
```

**Never use:** cyan, neon, pure white (#FFFFFF), saturated greens, drop shadows beyond what's specified, gradients outside the core and ctx-bar.

### Typography

```css
--sans: 'Inter', system-ui, sans-serif;
--mono: 'JetBrains Mono', ui-monospace, Menlo, monospace;
```

Size scale (px):
- **9** — micro UPPERCASE source tags (TOOL, YOU, GEMMA, …), profile-card numbers
- **10** — section headers (`substrate`, `profile`, `field`, …), bar values, footer text, hints
- **11** — bar segment values, profile chips, secondary body
- **12** — log message body, toggle labels
- **13** — primary body, metric labels, chat input
- **14** — left-header name "gemma 4"
- **15** — big metric numeric value
- **18–40** (responsive) — center "Idle"/"Thinking"/"Speaking" label below core

Weights: **400** for body text, **500** for labels and section headers. **Never** use 700+.

Letter-spacing: section headers `0.1em`, source tags `0.12–0.14em`, core state label `0.28em`. Otherwise `0.01–0.02em`.

Case: lowercase throughout; **ALL CAPS only** for activity-log source tags (`TOOL`, `YOU`, `GEMMA`, `MEMORY`, `TRIGGER`, `BOOT`, `THOUGHT`, `SYSTEM`, `CONTEXT`).

Tabular figures: `font-feature-settings: "tnum"` on all monospace numbers and timestamps.

### Spacing & layout

- Column padding: 14–18 px
- Gap between sections: 12–14 px
- Hair dividers: 1 px, color `var(--hair)`
- Border radius: 2 px (everywhere — chips, cards, buttons, inputs)
- Icon button size: 24 × 24 px (chat actions), 26 × 26 px (topbar actions)
- Surface card: 60 × 54 px

### Motion

- Universal panel/component fade-in: 240 ms ease
- Modal panel slide-in: 200 ms ease (translateY -6 → 0)
- Color/border hover transitions: 120 ms
- Logomark rearrange on state change: 600 ms `cubic-bezier(.4, 1.4, .5, 1)`
- Core halo pulse: sine, 0.8–3.4 Hz depending on state
- Orbit ring rotation: 1.5–22 °/s depending on state
- Galaxy (starfield) rotation: 0.15–1.20 °/s depending on state
- Nebula counter-drift: galaxy speed × −0.4
- Signal pulse traversal: 1.1–2.2 s end-to-end per edge
- Tracer traversal: 5 s total across full path with ease-in-out
- Last-turn afterglow on edges: 5 s linear fade

---

## Components

### `<LogoMark size state>`
8 small particles in a tiny SVG box (14 px). Positions are deterministic per state seed; circles transition with a bouncy cubic-bezier (`cx`, `cy`, `fill`) over 600 ms when state changes. Carmine in idle, gray in standby, bright in listening, blue in thinking, gold in speaking.

### `<ParticleCluster value seed size color>`
40 × 40 or 28 × 28 px SVG. 12–18 small dots clustered around 2–3 random anchors using a seeded gaussian. Number of dots and overall opacity scale with `value` (0..1). Used as a row icon on each substrate metric — visually communicates "how full" without a literal bar.

### `<SubstratePanel>` (left rail)

- **Header**: `<LogoMark>` + `gemma 4` + `···` + `7.2b · local · q4_k_m`
- **Substrate section** (overall system % on the right of the header)
  - 3 big rows: cpu / mem / gpu — particle cluster + label + spec + value + 1 px progress bar
  - 3 small rows: net / dsk / tmp — same layout, smaller cluster, no spec
- **Ctx budget** — `ctx · budget   15.6k / 34.0k` + 2 px gradient bar (Prussian → carmine)
- **Profile chips** — 4 chips in one row (perf / bal / light / stdby), 26 px tall, carmine border + inset shadow when selected
- **Field key/value list** — entropy / temperature / ctx · used / tokens/s / draw · w
- **Footer** (margin-top auto): uptime / tokens / peers

### `<NeuralGraph state>` (center)

The core visualization. Renders 8 layers in this order:

1. **Nebula bands** — 3 wavy SVG paths with `stroke-width: 50–90`, opacity 0.5, state-tinted gradient. Slowly counter-rotates the galaxy.
2. **Starfield** — ~300+ static dots positioned in a 1.5× viewport square so rotation never reveals empty corners. Twinkle via `sin(time)`. Mostly bone-white, ~10% carmine, ~8% blue. Slowly rotates around the core.
3. **Mesh edges** — 1 px straight lines between nodes, stroke `#2A3550` normally, `#3F4F7A` when their tag is lit by the current state. After a turn ends, edges from the turn's tags glow carmine-deep `#7A1E2B` for 5 s with linear fade.
4. **Core feed lines** — 1 px dashed `2 3` lines from 4 inner-ring nodes (n17–n20) toward the center, tinted with the current core halo color.
5. **Orbit ring particles** — 64 particles rotating around the core in an annulus between `coreR * 2.4` and `coreR * 3.6`. 70% tinted to a state color, 30% to its contrast. Rotation speed: 1.5–22 °/s.
6. **Central core** — concentric circles: outer halo (gradient, slow pulse), mid disc, dense nucleus, hot pixel (fast pulse). Below: state label (`Idle`/`Thinking`/etc.) in JetBrains Mono at `coreR * 0.72` size, letter-spacing 0.28em. All colors from the core state palette.
7. **Mesh nodes** — 26 total. 6 are labeled hubs (context, router, agent, tools, memory, voice) with a glow gradient. Hub colors track the state palette.
8. **Signal pulses** — small dots moving along random edges from `STATE_EDGES[state]`. Each has a 7-segment trail behind (shrinking, fading). Color matches the state pulse palette (carmine / blue / gold).
9. **Tracer** — fires when state transitions to `thinking`. Travels a fixed path `voice → router → context → memory → router → agent → tools → voice` over 5 s with ease-in-out. Much bigger than normal pulses (r=5 solid + r=18 halo), ivory `#FFF6E0` color for universal contrast against all states. 22-segment trail. Fades in/out at endpoints.

Layout: node positions are stored as normalized 0..1 coords; rendered with 24 px padding inside the SVG. Resized via `ResizeObserver`.

### `<FieldCenter>`

- **State line** (top, 26 px): status dot + `state · {state}` + `focal · {focal}` on the left; `graph · 26 nodes · 45 edges` on the right.
- **Neural graph** (fills remaining space).
- **Readout**: `· field {verb} · {readout}` (e.g., "field traversing · 47 paths active")
- **Chat hint row**: `enter sends · / focus · ⌘K history · shift+enter newline` left, `draft · N ch` right
- **Chat input line**: chevron `›` (carmine) + text input + tokens counter + chat-actions block (mic toggle, attach button, send button)
- **Attachments row**: pills with file icon + name (truncated 180 px max) + size + × button, or "no attachments" placeholder

### `<ActivityPanel>` (right rail)

- **Header**: `activity` + `{N} entries · #{session}`
- **Activity scroll** — vertical entries; each is a 2-row block:
  - Row 1: timestamp (mono, dim) + UPPERCASE source tag (colored per source type)
  - Row 2: message body (bone-white, 12 px, line-height 1.45, `text-wrap: pretty`)
  - 14 px gap between entries
  - Newest at top; auto-scroll to top on new entry
- **Surfaces section**: 2 × 2 grid of cards (sessions / memory / triggers / tools). Each card: UPPERCASE label (9 px muted) on top, count value below. Active card: carmine border + inset shadow + carmine label.
- **Right footer**: `local · no telemetry` + clock

### Top bar (36 px)

- **Left**: `field · {state}` — state name in carmine
- **Right**: three segment chips (`core: active` carmine, `net: local`, `build: carter`) + a bordered action group { sessions icon, plus icon, **settings (labeled, carmine border, very prominent)**, help icon } + clock

### Bottom bar (22 px)

- **Left**: `⌖ 51.5074° N · 0.1278° W · local` + session id
- **Right**: date + `{clock} · stable`

### `<SettingsPanel>` (modal)

Full-screen-ish modal (820 × 720 px, max 95vw) with 11 horizontal tabs:

1. **connection** — llama-server URL, model alias, GGUF path (with browse button), context size, max tokens per reply
2. **agent** — agent mode, persona, max turns, safety filter (with carmine warning tip)
3. **sampling** — temperature, top_p, top_k, min_p, repeat penalty, seed, allow CoT, parallel tool_calls
4. **behaviour** — summarization cooldown, fact cooldown, phrase-trigger timeout, llm timeout, max experience records
5. **transcript** — STT/TTS providers, voices, languages, wake word, wake word enabled
6. **voice** — enable voice (master), wake words, wake feedback (beep/hud/tts), input device, follow-up window, close phrases textarea, mute tts
7. **profiles** — VRAM detected, recommended profile, auto-switch toggles + watchlist textarea, profile chips, profile capabilities table
8. **toggles** — 8 feature toggles, each with its env var name aligned right
9. **paths** — 5 path inputs each with a browse button
10. **prompt** — system prompt readonly preview in a monospace code block
11. **about** — version info + "local AI agent · carter build · runs entirely offline"

Footer: `↻ restart agent` (ghost, left) — `cancel` (ghost) + `apply` (carmine, right). All form primitives are reusable: `<Field>`, `<STInput>`, `<STNumber>`, `<STText>`, `<STCheck>`, `<STBrowse>`, `<STTip>`, `<STSection>`. Click outside or × closes.

### `<SessionsPanel>` (modal)

Smaller modal (480 px). Search input with magnifying glass icon. Vertical list of sessions: id (mono dim) + label + timestamp; current session has a 2 px carmine left border and a `CURRENT` tag. Footer: count + "+ new session" button.

---

## Interactions

- **Click `⚙ settings` in top bar** → opens SettingsPanel modal
- **Click `≡ sessions`** → opens SessionsPanel modal
- **Click `+ new`** → clears activity log, pushes a SYSTEM entry "new session started · context cleared"
- **Click `? help`** → pushes a SYSTEM entry listing shortcuts
- **Click `🎙 mic` button** → toggles always-listening mode. When off, app forces `standby` and logs "voice channel disabled · standby mode". When on, returns to `idle`.
- **Click `📎 attach`** → opens native file picker; selected files appear as pills below the input; badge on button shows count
- **Type in input + Enter (or click send)** → triggers conversation turn:
  - With mic on: YOU → listening → thinking → speaking → idle (with intermediate THOUGHT/TOOL entries)
  - With mic off (standby): YOU → thinking → speaking → standby (no listening stage)
- **Click profile chip** → switches active profile, biases drifting metrics
- **Click surface card** → marks as active
- **Click anywhere in panel shroud** → closes that panel
- **Hover any `.ibtn`** → tooltip via `data-tip` attribute (CSS `::after`)

All interactions update the in-memory state immediately; no async delays except the simulated turn.

---

## Mock Activity Log

The initial entries seeded in `INITIAL_ENTRIES` (in `app.jsx`) are illustrative. In production, replace with real events streamed from the agent. Each entry has shape:

```ts
{ id: string, src: SourceTag, msg: string, ts: 'HH:MM:SS' }
type SourceTag = 'TOOL' | 'YOU' | 'GEMMA' | 'MEMORY' | 'TRIGGER' | 'BOOT' | 'THOUGHT' | 'SYSTEM' | 'CONTEXT'
```

Activity log keeps the last 80 entries in memory (newest first).

---

## State Management

In the prototype, all state lives in the top-level `App` component using React `useState`/`useEffect`/`useRef`. For Carter, recommended:

- **App-level conv state**: source of truth for `convState`, fed by real agent events.
- **Metrics** (cpu/mem/gpu/net/dsk/tmp): subscribe to a system-monitor channel; replace `useDriftingMetric` with real readings (every 1–2 s).
- **Tokens counter**: increment from llama-server's token stream.
- **Activity log**: an append-only ring buffer (cap 80–500) subscribed to the agent's event log.
- **Settings**: persist via the same JSON file the PyQt6 GUI uses (`~/.gemma4/gui.json`) so both clients stay in sync; the SettingsPanel reads on mount and writes on `apply`.
- **Mic enabled / profile / activeSurface / openPanel**: local UI state, persisted in localStorage by feature.

---

## Files in this bundle

```
prototype/
├── index.html                     # Entry point; loads React + Babel + scripts
├── styles.css                     # All styling — design tokens at top
├── app.jsx                        # Root App component + state machine + mock data
└── components/
    ├── icons.jsx                  # SVG icon set (Icon name="...")
    ├── cluster.jsx                # ParticleCluster + LogoMark (state-animated)
    ├── substrate.jsx              # Left rail (SubstratePanel)
    ├── graph.jsx                  # NeuralGraph + starfield + core + tracer
    ├── field.jsx                  # Center column (FieldCenter)
    ├── activity.jsx               # Right rail (ActivityPanel)
    ├── panels.jsx                 # Shared Panel chrome + SessionsPanel
    └── settings-panel.jsx         # SettingsPanel + 11 tabs + form primitives
```

To preview: open `prototype/index.html` in a browser. Everything is local except the Google Fonts link and the pinned React/Babel CDNs.

---

## Assets

- **Fonts**: Inter (400, 500) + JetBrains Mono (400, 500) — both from Google Fonts.
- **Icons**: all custom SVGs, monoline 1.25 stroke width, designed inline in `icons.jsx`. No external icon library.
- **Imagery**: none. Starfield + nebula + particle clusters are all generated mathematically with seeded RNG (`seededRng`). The "galaxy" rotates by transforming SVG groups.

---

## Implementation Notes

1. **Don't reach for canvas/WebGL** unless you measure a real performance problem. SVG with a single requestAnimationFrame loop handles all of this comfortably at 60fps on integrated graphics — the prototype proves it.
2. **Keep the layered structure of NeuralGraph.** Eight SVG groups in stacking order keeps everything testable and easy to tweak independently.
3. **Use refs, not state, for animation values.** Position, rotation, pulse trails — all stored in `useRef`. A single `forceUpdate()` per RAF tick is much cheaper than hundreds of `setState` calls.
4. **All particle positions are deterministic.** `seededRng()` ensures stars and clusters look the same across reloads. Don't switch to `Math.random()` directly in the render path.
5. **Respect motion reduction.** Wrap the RAF loop in a check for `prefers-reduced-motion`; fall back to a static frame or a much slower spawn rate. (Not implemented in the prototype — please add it.)
6. **Accessibility**: the prototype is keyboard-friendly (focus on chat input, tab through icon buttons, enter submits) but missing aria labels on the SVG. Add `aria-label="agent state visualization"` on the main `<svg>` and `role="status"` `aria-live="polite"` on the state line. Source tags in the activity log are color-coded — pair color with the visible label text (which is already there).
7. **Carter-specific naming**: the top bar says `build · carter`. The settings/about page says `carter build`. Avoid any "mark i", "JARVIS", "Iron Man", or similar references — they're forbidden by the design brief and have been scrubbed.

Good luck — and tell Carter we said hi. 🔴
