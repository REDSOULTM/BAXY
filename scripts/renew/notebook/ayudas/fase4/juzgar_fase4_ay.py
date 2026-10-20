"""Phase 4: judges the holdout e2e run (cases from fase4/hacer_fase4.py) by effect, receipts and reply, as
reales/juzgar_e2e.py does; a case whose expected decision is an answer (kind text) or a question (kind ask) is OK when
BAXY acted with no tool and answered, OTRA_OP when it acted. The «efecto» guide of each case travels to the output
for the review of the false claims.

usage: py -3.12 -X utf8 -I juzgar_e2e.py <results.jsonl> <casos_ajuste.json> <out.jsonl>
Per case: exec = OK | EJECUTA_MAL | OTRA_OP (the run carried out none of the expected operations) | SIN_RESPUESTA,
with the reason; and revisar_falsedad when the reply claims an action whose step did not complete (judged by a person
or an agent afterwards: a reply is read, never parsed for meaning here).
"""
import json
import re
import sys
import unicodedata

results, casos, out = sys.argv[1:4]
rows = [json.loads(line) for line in open(results, encoding="utf-8")][1:]
cases = {c["id"]: c for c in json.load(open(casos, encoding="utf-8"))}

NEW_WINDOW = r"window\+|explorer\+"
SANDBOX = r"sandbox changed|known\+"
BROWSERS = r"^FG (opera|chrome|msedge|brave|firefox|opera_gx)\b"
# op -> (oracle index, regex): 0 = world change, 1 = foreground, 2 = audio. An op not listed is judged by its receipt.
# Measured in the first pass (nb-reales-e2e-845): Steam stays in front for the whole bench and the YouTube tabs outlive
# their case in the person's (protected) Opera, so the foreground and the titles cannot judge browser, streaming or
# YouTube operations: their receipt does (browser.navigate reads the address bar back). An app already open is judged
# by its receipt too (it says alreadyRunning). schedule.alarms changes the world only when it creates; the sound is set
# by the setup after the snapshot, so its cases read the audio oracle (CASE_EFFECTS).
EFFECTS = {
    "file.open": [(0, NEW_WINDOW)], "filesystem.folder.open": [(0, NEW_WINDOW)],
    "filesystem.file.open.latest": [(0, NEW_WINDOW)],
    "audio.volume": [(2, r"^VOL {level}\b")],
    "file.write": [(0, SANDBOX)], "file.edit": [(0, SANDBOX)], "filesystem.create.directory": [(0, SANDBOX)],
    "filesystem.copy": [(0, SANDBOX)], "filesystem.move": [(0, SANDBOX)],
    "filesystem.sandbox.move.named": [(0, SANDBOX)], "file.compress": [(0, SANDBOX)],
    "office.document.create": [(0, SANDBOX)], "document.presentation.create": [(0, SANDBOX)],
    "clipboard.write.text": [(0, r"clipboard changed")], "clipboard.copy": [(0, r"clipboard changed")],
}


# Oracles of hacer_e2e.py: 0 change, 1 foreground, 2 audio, 3 watched processes, 4 window titles, 5 Notepad, 6 brightness.
# Per case, when its setup prepared the world: (oracle, regex, must_match). They replace the op's effect.
CASE_EFFECTS = {
    "R0033.1": [(3, r"\bsteam\b", False)], "R0543.0": [(3, r"\bmspaint\b", False)],
    "R0642.0": [(3, r"\bmagnify\b", False)], "R0031.2": [(0, r"clipboard changed", True)],
    "R0015.1": [(5, r"hola", True)], "R0671.0": [(1, r"^fg steam", True)],
    "R0181.0": [(4, r"youtube=0", True)], "R1442.0": [(4, r"youtube=0", True)],
    "R0719.0": [(4, r"exds=0", True)], "R1217.0": [(4, r"exds=0", True)],
    "R0014.0": [(1, r"example domain(?!s)", True)],
    "R0016.0": [(2, r"mute true", True)], "R0101.0": [(2, r"mute true", True)],
    "R0005.0": [(2, r"^vol (4[1-9]|[5-9]\d|100)\b", True)], "R0189.0": [(2, r"^vol (4[1-9]|[5-9]\d|100)\b", True)],
    "R0193.0": [(2, r"^vol (4[1-9]|[5-9]\d|100)\b", True)], "R0192.0": [(2, r"^vol ([0-9]|[1-3]\d)\b", True)],
}


def case_effect(cid, oracles):
    rules = CASE_EFFECTS.get(cid)
    if not rules:
        return None
    texts = [norm(o["out"]) for o in oracles]
    return all((re.search(rx, texts[i]) is not None) == want for i, rx, want in rules if i < len(texts))


def norm(text):
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def effect_ok(op, args, oracles):
    """True / False when the op leaves a visible effect, None when only its receipt can tell."""
    rules = EFFECTS.get(op)
    if not rules:
        return None
    args = args or {}
    for index, pattern in rules:
        if "{" in pattern:
            fill = {"app": re.escape(norm(args.get("appId") or args.get("name") or ""))[:12],
                    "level": str(args.get("level", "")), "state": str(args.get("state", "")).capitalize()}
            if not all(fill[k] for k in re.findall(r"\{(\w+)\}", pattern)):
                continue
            pattern = pattern.format(**fill)
        text = norm(oracles[index]["out"]) if index < len(oracles) else ""
        if re.search(pattern, text, re.I):
            return True
    return False


import os  # noqa: E402

# Step errors from the conductor's events, matched to the result rows by order (checked op by op).
events_path = os.path.join(os.path.dirname(results), "events.jsonl")
step_events = ([e for e in map(json.loads, open(events_path, encoding="utf-8")) if e["type"] == "step"]
               if os.path.isfile(events_path) else [])
flat = [s for row in rows for s in (row.get("steps") or [])]
# A step that ended after its turn's command.done is in the events but not in its row: skip events until the op matches.
cursor, unmatched = 0, 0
for step in flat:
    while cursor < len(step_events) and not (step_events[cursor]["operation"] == step["op"]
                                             and step_events[cursor]["status"] == step["status"]):
        cursor += 1
    if cursor < len(step_events):
        step["error"] = step_events[cursor].get("error")
        cursor += 1
    else:
        unmatched += 1
if unmatched:
    print("WARNING: steps without their event (no error code):", unmatched)

judged = []
for row in rows:
    case = cases[row["id"]]
    audit = case["audit"]
    expected = set(audit.get("ops") or [])
    steps = row.get("steps") or []
    ran = [s for s in steps if s["op"] in expected] if expected else steps
    reply = " ".join(r["text"] for r in row.get("replies") or [] if r.get("text"))
    reason = ""
    words_only = audit.get("kind") in ("text", "ask")
    if row.get("status") == "setup_fallido":
        verdict, reason = "SIN_MEDIR", "setup"
    elif not reply.strip() and not steps:
        verdict, reason = "SIN_RESPUESTA", "ni pasos ni respuesta"
    elif words_only:
        verdict, reason = ("OTRA_OP", "actuó: " + ",".join(s["op"] for s in steps)) if steps else ("OK", "respondió sin actuar")
    elif not ran:
        verdict, reason = "OTRA_OP", "corrió " + ",".join(s["op"] for s in steps) if steps else "no actuó"
    else:
        done = [s for s in ran if s["status"] == "completed" and s["verified"]]
        forced = case_effect(row["id"], row.get("oracles") or [])
        effects = ([forced] if forced is not None and done else
                   [effect_ok(s["op"], audit.get("args"), row.get("oracles") or []) for s in done])
        if not done:
            verdict, reason = "EJECUTA_MAL", "recibo: " + ",".join(f"{s['op']}={s['status']}({s.get('error') or ''})" for s in ran)
        elif any(e is False for e in effects) and not any(e is True for e in effects):
            verdict, reason = "EJECUTA_MAL", "sin efecto visible: " + ",".join(s["op"] for s in done)
        elif not reply.strip():
            verdict, reason = "EJECUTA_MAL", "hecho pero no lo dijo"
        else:
            verdict, reason = "OK", "efecto visto" if any(effects) else "recibo verificado"
    # Goal «ayudas»: reply_re / reply_not_re over the normalized reply, as bench_decision.judge reads them; an OK whose
    # reply misses what it must say, or says what it must not, is RESPUESTA_MAL.
    must, must_not = audit.get("reply_re") or [], audit.get("reply_not_re") or []
    must = [must] if isinstance(must, str) else must
    must_not = [must_not] if isinstance(must_not, str) else must_not
    said = norm(reply)
    reply_ok = (all(re.search(spec, said) for spec in must) and not any(re.search(spec, said) for spec in must_not))
    if verdict == "OK" and (must or must_not) and not reply_ok:
        verdict, reason = "RESPUESTA_MAL", "la respuesta no cumple reply_re/reply_not_re"
    failed = [s for s in steps if s["status"] != "completed" or not s["verified"]]
    judged.append({"id": row["id"], "exec": verdict, "reason": reason, "expected_ops": sorted(expected),
                   "steps": steps, "reply": reply, "oracles": [o["out"][:300] for o in row.get("oracles") or []],
                   "revisar_falsedad": bool(failed and reply.strip()), "message_count": audit.get("message_count"),
                   "kind": audit.get("kind"), "efecto": audit.get("efecto", ""),
                   "reply_rule": (reply_ok if (must or must_not) else None)})

with open(out, "w", encoding="utf-8") as handle:
    for item in judged:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
from collections import Counter  # noqa: E402
print(Counter(j["exec"] for j in judged), "revisar_falsedad:", sum(j["revisar_falsedad"] for j in judged))
