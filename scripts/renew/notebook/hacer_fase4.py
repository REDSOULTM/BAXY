"""Phase 4 (FT/proveedores goal): the new holdout's decision cases the PC chose (right on both GPUs and marked safe;
ids only) -> bench_e2e cases, with hacer_e2e.py's generic setups, its world-recording oracles, its quarantine and its
exclusions, plus the ones by operation (nothing sent, bought, installed, powered off, deleted outside the sandbox, no
system tool). The case format (PC, 2026-10-19 01:07): {id, family, history[{role,content}], text,
expect{kind, op?|ops?, args?}, nota, e2e{segura, efecto}}. A history's own person turns are said first, in order, as
earlier turns of the same conversation (BAXY answers them too); a confirmation is answered «sí».

usage: py -3.12 -X utf8 -I hacer_fase4.py <holdout.json> <ids.json> <out_cases.json> <out_audit.json>
out_audit.json is the judge's view of each case (its expected ops, args, kind and the «efecto» guide)."""
import json
import sys

sys.path.insert(0, r"C:\Users\usuario\AppData\Local\Temp\claude\nb\reales")
import hacer_e2e  # noqa: E402

# Never run, whatever the case says: what reaches other people, money, the PC's software or power, files outside the
# bench sandbox, and the protected system tools (the 2026-10-15 incident).
EXCLUDED_OPS = {
    "message.send", "message.send.test", "message.draft", "email.send", "mail.send",
    "store.purchase", "game.install.named", "game.uninstall.named", "package.install", "package.uninstall",
    "winget.install", "winget.uninstall", "system.power", "system.process.terminate.named",
    "filesystem.known.trash.named", "filesystem.delete", "file.delete", "shell.command.run",
    "peripheral.print", "backup.restore", "input.keyboard.layout",
}
EXCLUDED_APPS = ("spotify", "discord", "outlook", "msconfig", "regedit", "services", "taskschd", "gpedit")
SOUND = {"audio.mute", "audio.volume", "audio.volume.adjust", "media.control"}


def expected_ops(expect):
    ops = [expect["op"]] if expect.get("op") else []
    return ops + list(expect.get("ops") or [])


def why_excluded(case):
    expect = case.get("expect") or {}
    ops = set(expected_ops(expect))
    if not (case.get("e2e") or {}).get("segura"):
        return "no marcado seguro"
    if ops & EXCLUDED_OPS:
        return "operación excluida: " + ",".join(sorted(ops & EXCLUDED_OPS))
    args = json.dumps(expect.get("args") or {}, ensure_ascii=False).lower()
    for app in EXCLUDED_APPS:
        if app in args:
            return "app excluida: " + app
    return None


holdout = {c["id"]: c for c in json.load(open(sys.argv[1], encoding="utf-8"))}
ids = json.load(open(sys.argv[2], encoding="utf-8"))
chosen, audit, skipped = [], {}, {}
for cid in ids:
    case = holdout[cid]
    reason = why_excluded(case)
    if reason:
        skipped[cid] = reason
        continue
    expect = case.get("expect") or {}
    ops = expected_ops(expect)
    person = [h["content"] for h in case.get("history") or [] if h.get("role") == "user"]
    audit[cid] = {"text": case["text"], "turns": person + [case["text"]],
                  "audit": {"label": case.get("family", ""), "ops": ops, "args": expect.get("args"),
                            "kind": expect.get("kind"), "efecto": (case.get("e2e") or {}).get("efecto", ""),
                            "message_count": len(person) + 1}}
    if set(ops) & SOUND:
        hacer_e2e.SETUPS.setdefault(cid, [])[:0] = hacer_e2e.SOUND_ON
    if "system.settings.adjust" in ops:
        hacer_e2e.BRIGHT.add(cid)
    chosen.append(cid)

hacer_e2e.EXCLUDED.clear()
out, _ = hacer_e2e.build(audit, chosen)
for case in out:
    turns = audit[case["id"]]["turns"]
    case["turns"] = [{"text": t, "reply_if_confirmation": "sí"} for t in turns]
    case["timeout_s"] = 150 + 60 * (len(turns) - 1)
json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump([{"id": k, **v} for k, v in audit.items()], open(sys.argv[4], "w", encoding="utf-8"), ensure_ascii=False,
          indent=0)
print(len(out), "e2e cases;", len(skipped), "excluded:", json.dumps(skipped, ensure_ascii=False))
