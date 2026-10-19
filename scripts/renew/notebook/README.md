# Notebook measurement tools (REDNOTE, goal FT + proveedores, 2026-10-19)

These are copies of the tools the notebook ran from its scratch directory
(`C:\Users\usuario\AppData\Local\Temp\claude\nb`). They keep the absolute paths they ran with. The banks themselves are
not in git; they live in `D:\BAXYeval\renew_v1` on the notebook and `F:\BAXYeval\renew_v1` on the PC.

## Desktop checks

Since 06:11 a hidden GameInputSvc window had held the front, and e2e runs measured on that desktop do not count.

| Tool | What it does |
|---|---|
| `frente_ahora.ps1` | Prints the window in front and its program. Exits 1 if the window is invisible or belongs to GameInputSvc. Run it before each seed. |
| `e2e_frente.py <events.jsonl>` | Counts, after a seed, the `app.open` asked in front that ended behind another window. Exits 1 if one was behind GameInputSvc. |
| `e2e_frente_casos.py <events.jsonl> <cases.json>` | Does the same per case id. It matches turn texts without printing them, so it can run on a sealed holdout. |

## The queue and its gates

| Tool | What it does |
|---|---|
| `pri.sh <job id> <remote checkpoint dir>` | Runs a queued job ahead of the others once its checkpoint has its `.done`. |
| `puerta_escenas.sh <name> <floor>` | Averages the four scene runs (unchanged, pA, pB, pC). If the mean falls below the floor, it marks the checkpoint rejected. |

## Phase 4

| Tool | What it does |
|---|---|
| `correr_fase4b.sh <holdout> <ids> <worktree> <HEAD> <label>` | Runs the holdout's eligible cases once through the real, rebuilt product. It checks the desktop before the run and per case after it. |
| `hacer_fase4.py` | Builds the e2e cases. It excludes operations and apps that send messages, buy, install, power off, end processes, delete outside the sandbox, or change system settings. |
| `juzgar_fase4.py` | Judges each case as OK, EJECUTA_MAL, OTRA_OP or SIN_RESPUESTA, plus revisar_falsedad. |

## The W1 case

`vivo_ft_W1.json` is the W1 case as it now stands in the notebook's `vivo_ft.json`. Its preparation wins the right to
the front the way ForegroundRight does: it registers an unused key as a hotkey, presses it, then calls
`SetForegroundWindow`. It then checks that WINWORD holds the front. If not, the case is `setup_failed` and the message
names the program in front.

Before this change, the harness's `AppActivate` sometimes left Word behind, because the harness runs in the background.
That is where W1's 2/3 came from. With the change, W1 scores 3/3 on e0a7d9923.
