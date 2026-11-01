# BAXY Renew: generic agent tools, inventory, gaps and minimal set

Date: 2026-10-15. Read-only analysis. Nothing in the repo was changed.

## 1. What BAXY has today

**Source of truth.** `%LOCALAPPDATA%\BAXY\renew\catalog.configure.json`
- 109 KB file.
- **206 capabilities**, each with `name`, `description`, `argumentsSchema` and `risk`.
- `applicationCatalog`: about 11 K chars of Start-menu names.
- `gameCatalog`: about 2.4 K chars.

**How the kernel declares an operation.** Each one is a `Descriptor(name, Schema(...), OperationRisks.X, verifierContractId, ToolExposure.Public|Internal, description)` entry in `src\Baxy.Kernel\Operations\ProductCatalog.cs`.
- The file is 2,649 lines, with 207 descriptors (1 Internal).
- `ProductOperationDescriptor` sets `RequiresObservedEffect = risk != read_only`, so every effect needs a verifier contract.
- The catalog has no producer/consumer fields. Chaining is implicit: opaque ids such as `resourceId`, `windowId`, `trashId` and `confirmationId` are emitted by one op and required by another.

**How risk becomes a decision.**
- `ToPolicyRisk` maps the catalog labels to policy classes:
  - read_only maps to ReadOnly.
  - low_reversible and recoverable_delete map to Reversible.
  - privacy_sensitive maps to Sensitive.
  - external_communication maps to External.
  - work_loss, monetary, installation and session_disruption map to Irreversible.
- `Policy\RiskPolicy.cs` then decides per class in Normal mode:
  - ReadOnly, Reversible and Sensitive are allowed.
  - External is allowed, except `message.send`, `message.send.test`, `email.send` and `email.latest.reply`.
  - Irreversible requires confirmation.
  - Argument-level rules also force confirmation: click or key labels that send, pay or delete; an `overwrite` consequence; and `browser.control close_all`.

**Where providers live.** `src\Baxy.Providers.Windows`. The shell provider is `External\ShellCommandAdapter.cs`.

**What the model sees.** `src\baxy_mind\mind.py` sends **every** capability as a native tool on every turn, plus `ask_user`. Only `mission.computer.use` is skipped. The app list is appended to `app.open`.
- The warm prefix measured in `bench-r1-nb.log` is **34,082 tokens**.
- The per-slot context is 40,960 (`BAXY_RENEW_CTX`, `-c ctx*2 -np 2`).
- So about **83 % of the context is tool schemas before the person says anything**. It is cached, but it is still in attention for a 4B model.

### Inventory by area

Risk codes: RO = read_only, LR = low_reversible, PS = privacy_sensitive, EX = external_communication, RD = recoverable_delete, WL = work_loss, IN = installation, MO = monetary.

| Area (n) | Operations (risk): note |
|---|---|
| filesystem (22) | **Sandbox, with opaque ids:** list, search, read.text, hash (RO); copy, move (LR); trash.prepare (RO), trash.commit (RD), trash.restore (LR); sandbox.append.named, sandbox.move.named (LR); sandbox.diff.named (RO). **Known folders (desktop, documents, downloads):** known.list, known.search, known.duplicates, explorer.count (RO); known.trash.named (RD); create.directory, write.text (LR; overwriting needs the prior SHA-256); folder.open, file.open.latest (LR). **Other:** path.ensure.absent (RD). |
| file (2) / document (3) / office (2) | file.open, file.compress (LR). document.text.read, document.pdf.read (RO; by unique name in a known folder). document.presentation.create (LR). office.document.create (LR), office.document.read (RO). |
| shell (1) | **shell.command.run (LR)**: PowerShell `-NoProfile -ExecutionPolicy Bypass`, 60 s, cwd in a known folder or a scratch folder, regex denylist. |
| web (3) / browser (5) / weather (1) | **web.search (RO)**; web.news.headlines (RO); web.download (PS). browser.navigate, navigate.named (EX), control (LR), page.read, tabs.list (PS): all over a CDP Chromium profile. weather.current (RO). |
| task (9) | The **person's** to-do list: create, update, complete, reopen, delete (RD), restore, list, search, resolve.exact. |
| note (7) | create, update, read, list, search, trash (RD), restore. |
| reminder (5) / notification (7) | **Two reminder systems.** reminder.create/delete/list/resolve/restore is a local store. notification.schedule/list/list.due/cancel.at/cancel.latest/dismiss/diagnose is audible alarms through Windows tasks. |
| routine (7) | phrase.create, list, read, resolve, set.enabled, delete, restore. |
| memory (11) | save, sensitive.save (PS), recall, list, correct, forget (WL), session.clear, enable (PS), disable, export (PS), status. |
| system (11) | status, time, identity, process.list (RO); process.terminate.named, power, recyclebin.empty (WL); settings.status (RO), .set (PS), .adjust (LR); application.crash.diagnose (RO). |
| window (12) / app (3) / desktop, display (2) | resolve, active, application.status (RO); focus, maximize, minimize, minimize.all, restore, move, resize, snap (LR); close.all (WL). app.open (LR), app.close (WL), app.installed (RO). wallpaper.set (LR), display.status (RO). |
| input (10) / clipboard (4) / calculator, client (2) | visible.controls (RO), visible.click (EX), text.type (PS), key.press, scroll, select.all, pointer.control, keyboard.layout/open (LR), keyboard.status (RO). clipboard.copy, paste, read.text, write.text (PS). calculator.expression.evaluate, client.channel.locate (LR). **These click and type in the person's windows.** |
| audio (7) / media (6) / streaming (2) | Volume, mute and microphone (LR), status (RO). media.control/seek (LR), status (RO), play.exact/query/youtube (EX). streaming.navigate/play.named (EX). |
| network (5) / wifi (9) / bluetooth (4) / storage, peripheral (4) | dns, ip, port lists, ping and status (RO). wifi status, scan, profiles and ensure (RO); connect, connect.named, disconnect, radio.set (PS). bluetooth list and status (RO), radio.set (LR), pair (PS). removable.list, peripheral.list (RO); print, scan (PS). |
| message (4) / email (3) / calendar (2) | recipient.resolve (RO), draft (PS), send and send.test (EX, confirmed). latest.read (PS), send and latest.reply (EX, confirmed). event.list (RO), event.create (EX, **not** confirmed). |
| game (13) / package (3) / software (2) | Steam/Epic catalog, entitlement, install prepare/commit (IN), purchase prepare/commit (MO), uninstall and cancel (WL), launch, status. winget install prepare/commit (IN), uninstall (WL). python.status, python.package.status (RO). |
| backup (8) / capture, ocr, vision (4) / mission (1) | create, known.create, list, verify, restore (LR/RO). capture.screenshot and active.window, ocr.read, vision.describe (PS). mission.computer.use (LR, hidden from the mind). |

Risk totals: RO 77, LR 70, PS 25, EX 13, WL 10, RD 7, IN 3, MO 1.

## 2. What the evidence says

- **Generic agents converge on a small core.** The common set is: shell, read, write, edit, find/grep, web search, web fetch, a plan/todo tool, ask user, scheduling, and on-demand skills or tool search.
  - OpenClaw: `exec/process`, `read/write/edit/apply_patch`, `web_search/web_fetch`, `browser`, `cron`, `ask_user`, `sessions_*`, plus `tool_search/tool_describe` for large catalogs ([docs.openclaw.ai/tools](https://docs.openclaw.ai/tools)).
  - Claude Code: Bash/PowerShell, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, TodoWrite/Task*, Cron*, AskUserQuestion, Skill, ToolSearch ([tools reference](https://code.claude.com/docs/en/tools-reference)).
  - OpenCode: bash, read, write, edit, grep, glob, apply_patch, webfetch, websearch, skill, question ([opencode.ai/docs/tools](https://opencode.ai/docs/tools/)).
  - Codex CLI: shell, apply_patch, update_plan, read_file/list_dir ([philschmid.de](https://www.philschmid.de/openai-codex-cli)).
  - smolagents: web search, VisitWebpage, PythonInterpreter, UserInput, FinalAnswer ([HF docs](https://huggingface.co/docs/smolagents/reference/default_tools)).
  - Qwen-Agent: `code_interpreter` (Docker sandbox), plus MCP filesystem and memory servers ([GitHub](https://github.com/QwenLM/Qwen-Agent)).
- **Small models degrade with large tool lists.**
  - LongFuncEval measured a 7–85 % drop as the tool count grows ([arXiv 2505.10570](https://arxiv.org/abs/2505.10570v1)).
  - RAG-MCP, which retrieves tools before the call, raised selection accuracy from 13.6 % to 43.1 % and cut prompt tokens by more than half ([arXiv 2505.03275](https://arxiv.org/html/2505.03275v1)).
  - "Less is More" (edge devices, dynamic tool subsets) reports up to 70 % less latency and better success ([arXiv 2411.15399](https://arxiv.org/html/2411.15399v1)).
  - Anthropic: "More tools don't always lead to better outcomes"; consolidate overlapping tools ([writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)).
- **What Qwen3.5-4B can do.**
  - BFCL-V4 50.3, TAU2 79.9, but DeepPlanning 17.6 ([model card](https://huggingface.co/Qwen/Qwen3.5-4B)). Single calls are decent; long-horizon planning is weak.
  - For comparison, Qwen3-4B-2507 scores 22 % on BFCL multi-turn ([benchmarklist](https://benchmarklist.com/models/qwen3-4b-instruct-2507/)).
- **Skills on demand.** OpenClaw puts a bounded skill directory in the prompt (about 24 tokens per skill) and loads the full file with `skills_read` / `skills_search` ([docs.openclaw.ai/tools/skills](https://docs.openclaw.ai/tools/skills)).
- **Shell safety.**
  - OpenClaw exec modes are deny / allowlist / ask / full; approvals are bound to the exact argv and cwd; inline eval is strict ([exec approvals](https://docs.openclaw.ai/tools/exec-approvals)).
  - Claude Code auto-runs a fixed read-only command set and asks for everything else.
  - PowerShell JEA/restricted runspaces give real allowlists, but exposing the FileSystem provider, `Import-Module` or the `*-Job` cmdlets breaks them ([MS Learn](https://learn.microsoft.com/en-us/powershell/scripting/security/securing-restricted-sessions?view=powershell-7.5), [JEA role capabilities](https://learn.microsoft.com/powershell/scripting/security/remoting/jea/role-capabilities)).
  - Constrained Language Mode alone is weak: a new session escapes it ([practitioner guide](https://www.decryptiondigest.com/blog/powershell-constrained-language-mode-wdac-jea-enterprise-guide)).
  - Private data + untrusted web content + an outbound channel is the exfiltration "lethal trifecta" ([Willison](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)).

## 3. Gaps and redundancies

**Shell already exists but is miscalibrated.** It is labelled low_reversible, so it is never confirmed. Its denylist (`ShellCommandAdapter.IsDestructive`) misses several things:
- **Overwriting or emptying files:** `Set-Content`, `Out-File`, `>`, `Clear-Content`, `Copy-Item -Force`.
- **.NET deletes:** `[IO.File]::Delete(...)`.
- **Quoted deletes:** `cmd /c "del x"`. The regex needs whitespace before `del`.
- **Outbound traffic:** `Invoke-WebRequest/Invoke-RestMethod -Method Post`, `curl -d`, `Send-MailMessage`.

The egress case breaks "nothing leaves the machine". The overwrite cases break "confirm what destroys".

**Files.**
- BAXY can write to known folders: `filesystem.write.text` overwrites with a hash and no confirmation.
- It can read by unique name: `document.text.read`, `document.pdf.read`.
- It **lacks** a path-based read with line ranges, an **edit** (exact replace), and a content grep.
- The 12 sandbox/opaque-id `filesystem.*` ops duplicate the known-folder ones.

**Web.**
- `web.search` exists.
- There is **no standalone page reader**. `browser.page.read` needs a CDP browser navigated first (`browser.navigate`, EX). A `web.fetch` that does GET + readable text is missing.

**Own plan list.** None. `task.*` is the person's list, a different thing. Codex `update_plan` and Claude TodoWrite target long multi-step work. BAXY's loop caps at 6 steps and the 4B model is weak at planning, so the value is unproven here.

**Scheduling.** Two overlapping systems (`reminder.*` and `notification.*`). There is no "run a request later" equivalent of OpenClaw `cron`.

**Conflict with an owner rule.** These ops type or click into the person's window:
- `input.*` (10), `clipboard.copy`/`clipboard.paste`, `calculator.expression.evaluate`, `client.channel.locate`, `message.draft`.

All of them are still exposed to the mind.

**What the shell plus file tools would make redundant (read-only diagnostics):**
- network dns, ip, port and ping
- software.python.*
- system.identity, system.process.list, system.application.crash.diagnose
- display.status, storage.removable.list, peripheral.list
- filesystem.hash, filesystem.known.duplicates, filesystem.sandbox.diff.named, filesystem.explorer.count
- file.compress

That is about 18 ops. They can become **skills**: a short recipe whose vetted PowerShell runs through the shell tool, so coverage is unchanged. Keep typed ops where verification or privacy redaction matters: audio, window, wifi connect (SSID hiding), media, messaging, installs, trash.

## 4. Proposed minimal set (ranked)

| # | Name | Purpose | Args sketch | Risk; when the kernel confirms | Provider verifies | Subsumes | Evidence |
|---|---|---|---|---|---|---|---|
| 1 | `skill.read` (+ index in prompt) | Load a skill's full instructions/schema on demand. | `{name}` | RO; never | Skill exists, hash | Lets the about 34 K-token prefix shrink to about 15 core tools + a name index | RAG-MCP, Less-is-More, OpenClaw skills, Claude ToolSearch |
| 2 | `shell.run` (rework of shell.command.run) | Run one PowerShell command. | `{command, cwd?, timeoutSec≤60}` | Classified per invocation: read-only verbs/allowlist (Get-*, Test-*, Select-String, Measure-*…) run directly; anything that writes, deletes, kills or installs **confirms with the exact command**; network egress cmdlets, `iex`, new runspaces/jobs and `-EncodedCommand` are **denied** | Exit code, bounded stdout/stderr, cwd; before/after hash of files named in the args | About 18 diagnostic ops (as skills) | Claude Code read-only set, OpenClaw exec approvals, JEA guidance |
| 3 | `file.read` | Read text from any path under the profile (txt/md/code/json, PDF/DOCX text) with offset/limit. | `{path, offset?, limit?}` | RO; never (secrets folders denied) | Bytes read, SHA-256, truncation flag | document.text.read, document.pdf.read, filesystem.read.text, office.document.read | Read in all CLIs |
| 4 | `file.write` | Create or overwrite a text file. | `{path, text, expectedSha256?}` | LR on create; **confirm on overwrite**; deny outside profile | Re-read hash = written hash; prior version backed up | filesystem.write.text, sandbox.append.named, create.directory | Write in Claude Code/OpenCode |
| 5 | `file.edit` | Exact-string replace in a file. | `{path, old, new, all?}` | LR (prior copy kept for undo); confirm if it removes over N lines | Old string count matched; new hash | (new) | Edit in Claude Code/OpenCode/OpenClaw |
| 6 | `file.find` | Find files by name/glob and optionally by content. | `{query, folder?, content?, limit}` | RO; never | Re-stat each hit | filesystem.known.search, filesystem.search, filesystem.known.list, filesystem.list | Glob/Grep |
| 7 | `web.fetch` | GET a URL and return readable text. | `{url, maxChars}` | RO; GET only, no cookies or profile; **confirm when the URL did not come from the person or a web.search result** (exfiltration via query string) | Final URL, status, content hash | web.news.headlines (via search+fetch); browser.page.read stays for the person's own tabs | web_fetch / VisitWebpage / WebFetch; lethal trifecta |
| 8 | `schedule` | One reminder/alarm store with create, list and cancel. | `{action, title?, dueUtc?, recurrence?, id?}` | LR; never (cancel is reversible) | Windows task present or absent | reminder.* (5) + notification.* (7) | Anthropic consolidation; OpenClaw cron |
| — | `plan` (own todo) | Scratch checklist within a turn. | `{items[{text,status}]}` | RO | — | — | Codex update_plan, TodoWrite. **Defer:** a 6-step cap and DeepPlanning 17.6 give no evidence it helps a 4B model; measure first. |

Keep `ask_user` and `web.search` as they are. With skills on demand, the typed ops do not disappear: they move behind the index, and the mind sees the core plus the skill names.

## 5. Owner decisions (truly open)

1. **Raw PowerShell at all?** Choose one:
   - (a) A raw shell, classified per command with confirmation (the most coverage).
   - (b) An in-process restricted runspace with allowlisted cmdlets only (JEA-like, safest, needs curating).
   - (c) No free shell, only vetted skill commands.

   The current denylist is not a safe boundary either way.
2. **Should overwrite always confirm?** Today `filesystem.write.text` overwrites without asking. Alternatively, never confirm, because a backup is kept.
3. **web.fetch exfiltration rule:** confirm on any model-built URL, or only allow URLs from the person or from web.search results?
4. **The input./clipboard. ops that click and type** contradict "BAXY never clicks or types in your window". Remove them from the mind, or keep them as an explicit opt-in skill?
5. **"Run later" (cron for requests, unattended actions):** accept, or keep reminders only?
6. **Typed ops vs shell skills:** collapsing the read-only diagnostics into skills trades the two-observation verification and privacy redaction for fewer tools. Which families must stay typed?
