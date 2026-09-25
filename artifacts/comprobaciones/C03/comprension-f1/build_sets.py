"""F1 — singles and public conversations for DEV-A, DEV-B and FINAL (comprensión natural, 2026-09-25).

Never-seen text only: a candidate whose normalised text is in exclusion.txt (tandas, 742, reserve, layers, product
indices, MASSIVE train) or whose SHA-256 is in exclusion.sha256.txt is out; so is anything that could close, send,
buy, delete, call or cut the network when the set later runs in the official window.

Singles (per set): quotas per source, one per intent first so a set spreads over what people ask.
Public conversations (per set): PRESTO human follow-ups with ≥2 previous turns (correct-argument / correct-action /
cancel-action: the last turn depends on the one before), SGD test user turns (one service), oasst2 es threads that
depend on what came before. History is the source's own assistant turns.
Output (no gold yet): <OUT>/stage1/{singles,pubconv}_{A,B,F}.jsonl. Prints counts only.
usage: build_sets.py
"""
import glob
import hashlib
import json
import os
import pathlib
import random
import re
import sys

import pandas as pd

from exclusion import norm

HERE = pathlib.Path(__file__).resolve().parent
DS = HERE.parent / "ds"
PREV = pathlib.Path(r"C:/Users/usuario/AppData/Local/Temp/claude/C--Users-usuario-Desktop-ETC-Programacion-BAXY-Definitivo/"
                    r"6f29a6a5-6bd3-4363-bc79-bf1974e6d110/scratchpad")
PDATA = PREV / "datasets"
MASSIVE = pathlib.Path(r"D:/BAXYRuntime/assets/huggingface/hub/datasets--AmazonScience--massive/snapshots/"
                       r"ed58ac423a2f4121720918bf5301577edce4ffd3")
OUT = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "comprension-2026-09-25" / "stage1"
SEED = 20260925

RISKY = re.compile(
    r"\b(apag\w*|reinici\w*|cierr\w*|cerr\w*|sesi[oó]n|borr\w*|elimin\w*|env[ií]\w*|mand\w*|compr\w*|reserv\w*|"
    r"public\w*|llam\w*|suscrib\w*|pag[auoe]\w*|desinstal\w*|instal\w*|format\w*|shut\w*|restart|log ?off|delete|"
    r"remove|send|buy|order|book|booking|reserve|post|call|pay|payment|close|install|kill|suspend\w*|dorm\w*|sleep|"
    r"hibern\w*|bloque\w*|lock|wifi|wi-fi|bluetooth|avi[oó]n|airplane|desactiv\w*|disable|transfer\w*|password|"
    r"contraseña|tarjeta|card|bank|banco|text|texto|sms|mensaje|message|email|e-mail|correo|mail|desconect\w*|"
    r"disconnect\w*|network|internet|ethernet|red|purchase|tickets?|entradas?|rent|alquil\w*|venmo|paypal|whatsapp|"
    r"telegram|share|compart\w*|dial|marca(?:r|le)?|contact\w*|uninstall|quit|exit|salir|termina\w*|reply|respond\w*|"
    r"responde\w* a todos|vac[ií]a\w*|empty|print\w*|imprim\w*|papelera|recycle|trash|basura)\b",
    re.IGNORECASE,
)
TURN_OFF_DEVICE = re.compile(r"\b(turn\s+off|apag)\w*\b.*\b(pc|computer|computadora|compu|laptop|pantalla|screen|tele|tv)\b",
                             re.IGNORECASE)
MASSIVE_INTENTS = json.loads((PREV / "uso" / "massive_intents.json").read_text(encoding="utf-8"))
CLINC_NAMES = json.loads((PREV / "uso" / "clinc_intents.json").read_text(encoding="utf-8"))
CLINC_KEEP = {"timer", "alarm", "weather", "time", "reminder", "reminder_update", "calendar", "calendar_update",
              "todo_list", "todo_list_update", "play_music", "change_volume", "calculator", "translate", "definition",
              "fun_fact", "tell_joke", "what_is_your_name", "date", "next_song", "measurement_conversion",
              "who_made_you", "what_are_your_hobbies", "meaning_of_life", "spelling", "timezone", "exchange_rate",
              "current_location", "flip_coin", "roll_dice", "how_old_are_you", "are_you_a_bot", "greeting",
              "goodbye", "thank_you", "news", "traffic", "distance", "shopping_list", "shopping_list_update",
              "recipe", "cook_time", "nutrition_info", "calories", "whisper_mode", "repeat", "maybe", "yes", "no",
              "travel_suggestion", "weather", "what_can_i_ask_you", "who_do_you_work_for", "tell_joke", "fun_fact",
              "change_speed", "change_accent", "user_name", "change_user_name", "sync_device", "find_phone",
              "meeting_schedule", "next_holiday", "plug_type", "international_visa", "calculator", "smart_home",
              "spelling", "gas_type", "oil_change_how", "tire_pressure", "restaurant_suggestion", "ingredients_list",
              "food_last", "improve_credit_score", "pto_request", "w2", "insurance", "vaccines", "uber", "flight_status",
              "carry_on", "lost_luggage", "travel_alert", "timezone", "text"}
MTOP_DROP_DOMAINS = {"calling", "messaging"}
QUOTA = {  # per 125 singles; FINAL scales to 100
    "massive_es": 18, "massive_en": 10, "mtop_es": 14, "mtop_en": 8, "clinc_en": 12, "ilenia_es": 12, "cstop_mix": 20,
    "presto_es": 14, "presto_en": 7, "oasst_es": 10,
}
SIZES = {"A": 125, "B": 125, "F": 100}
PUBCONV_TURNS = {"A": 50, "B": 50, "F": 40}


def exclusion():
    folded = set((HERE / "exclusion.txt").read_text(encoding="utf-8").split("\n"))
    hashes = set((HERE / "exclusion.sha256.txt").read_text(encoding="utf-8").split())
    return folded, hashes


FOLDED, HASHES = exclusion()


def fresh(text: str) -> bool:
    text = " ".join(str(text).split())
    if not text or not 2 <= len(text.split()) <= 30:
        return False
    if RISKY.search(text) or TURN_OFF_DEVICE.search(text):
        return False
    if norm(text) in FOLDED:
        return False
    return hashlib.sha256(text.encode("utf-8")).hexdigest() not in HASHES


def singles_pool() -> dict[str, list[tuple[str, str, str]]]:
    """source -> [(source_id, text, intent)]"""
    pool: dict[str, list] = {k: [] for k in QUOTA}
    for locale, key in (("es-ES", "massive_es"), ("en-US", "massive_en")):
        frame = pd.read_parquet(MASSIVE / locale / "validation" / "0000.parquet")
        for row in frame.itertuples():
            pool[key].append((f"massive:{locale}:val:{row.id}", str(row.utt), MASSIVE_INTENTS[int(row.intent)]))
    for lang in ("es", "en"):
        for split in ("test", "eval"):
            frame = pd.read_parquet(DS / f"mtop_{split}_{lang}.parquet")
            for row in frame.itertuples():
                if str(row.domain).strip() in MTOP_DROP_DOMAINS:
                    continue
                pool[f"mtop_{lang}"].append((f"mtop:{lang}:{split}:{row.id}", str(row.utterance), str(row.intent).strip()))
    clinc = pd.read_parquet(PDATA / "clinc.parquet")
    for i, row in enumerate(clinc.itertuples()):
        name = CLINC_NAMES[int(row.intent)]
        if name in CLINC_KEEP or name == "oos":
            pool["clinc_en"].append((f"clinc:{i}", str(row.text), name))
    for i, row in enumerate(pd.read_parquet(PDATA / "ilenia.parquet").itertuples()):
        pool["ilenia_es"].append((f"ilenia:{i}", str(row.example), str(row.intent)))
    cstop = pd.read_parquet(PDATA / "cstop.parquet")
    for i, row in enumerate(cstop.itertuples()):
        if row.intent in {"IN:SLEEP", "IN:CLOSE_RESOURCE", "IN:CAMERA_FOLLOW", "IN:CAMERA_STOP_FOLLOWING"}:
            continue
        pool["cstop_mix"].append((f"cstop:{i}", str(row.utterance), str(row.intent)))
    for locale, key in (("es-ES", "presto_es"), ("en-US", "presto_en")):
        wanted = {"code-mixing", "disfluency", "within-turn-correction"}
        if locale == "en-US":
            wanted.discard("code-mixing")  # the en-US code-mixing partition mixes non-Latin scripts
        for line in open(DS / "presto" / "test_partitions" / locale / "test.jsonl", encoding="utf-8"):
            row = json.loads(line)
            phenomenon = row["metadata"].get("linguistic_phenomena")
            if phenomenon not in wanted:
                continue
            intent = row["targets"].split("(")[0].strip()
            pool[key].append((f"presto:{locale}:{row['metadata']['example_id'][:16]}", row["inputs"],
                              f"{phenomenon}:{intent}"))
    oa = pd.read_parquet(PDATA / "oasst_es.parquet")
    for row in oa[oa.parent_id.isna()].itertuples():
        text = str(row.text).strip()
        if 3 <= len(text.split()) <= 25 and "\n" not in text:
            pool["oasst_es"].append((f"oasst2:{row.message_id}", text, "open_chat"))
    return {k: [p for p in v if fresh(p[1])] for k, v in pool.items()}


def pick_singles(pool, rng) -> dict[str, list[dict]]:
    taken: set[str] = set()
    out: dict[str, list[dict]] = {s: [] for s in SIZES}
    for source, quota in QUOTA.items():
        candidates = list(pool[source])
        rng.shuffle(candidates)
        seen_intents, spread = set(), []
        for p in candidates:
            if p[2] not in seen_intents:
                seen_intents.add(p[2])
                spread.append(p)
        ordered = spread + [p for p in candidates if p not in spread]
        per_intent: dict[tuple[str, str], int] = {}
        # deal round-robin so the three sets share the same intent spread
        wanted = {s: round(quota * SIZES[s] / 125) for s in SIZES}
        index = 0
        while any(len([r for r in out[s] if r["source"] == source]) < wanted[s] for s in SIZES) and index < len(ordered):
            for s in ("A", "B", "F"):
                if len([r for r in out[s] if r["source"] == source]) >= wanted[s]:
                    continue
                while index < len(ordered) and (norm(ordered[index][1]) in taken
                                                 or (ordered[index][2] != "open_chat"
                                                     and per_intent.get((s, ordered[index][2]), 0) >= 3)):
                    index += 1
                if index >= len(ordered):
                    break
                sid, text, intent = ordered[index]
                index += 1
                taken.add(norm(text))
                per_intent[(s, intent)] = per_intent.get((s, intent), 0) + 1
                out[s].append({"source": source, "source_id": sid, "text": " ".join(text.split()), "source_intent": intent})
    for s in out:
        rng.shuffle(out[s])
    return out


_CONTINUES = re.compile(
    r"^(?:[¿¡]\s*)?(?:y|e|pero|entonces|ahora|tambi[eé]n|and|but|so|also|then|what about|how about)\b|"
    r"\b(?:eso|esto|esa|ese|esta|este|aquello|lo|la|le|las|los|m[aá]s|otr[oa]s?|mismo|anterior|dijiste|hiciste|"
    r"that|this|it|those|them|more|another|other|same|previous|you said)\b",
    re.IGNORECASE,
)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-záéíóúñü]{5,}", text.casefold()))


def presto_conversations() -> list[dict]:
    out = []
    for locale in ("es-ES", "en-US"):
        path = DS / "presto" / "test_partitions" / locale / "test.jsonl"
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            meta = row["metadata"]
            if meta.get("context") != "human" or meta.get("linguistic_phenomena") not in {
                    "correct-argument", "correct-action", "cancel-action"}:
                continue
            previous = meta.get("previous_turns") or []
            if not 2 <= len(previous) <= 5:
                continue
            users = [t["user_query"] for t in previous] + [row["inputs"]]
            if not all(fresh(u) for u in users[-1:]) or any(RISKY.search(u) or TURN_OFF_DEVICE.search(u) for u in users):
                continue
            if any(norm(u) in FOLDED for u in users):
                continue
            turns = [{"user": " ".join(t["user_query"].split()), "assistant": t["response_text"]} for t in previous]
            turns.append({"user": " ".join(row["inputs"].split()), "assistant": None})
            out.append({"source": f"presto_{locale[:2]}", "source_id": f"presto:{locale}:{meta['example_id'][:16]}",
                        "phenomenon": meta["linguistic_phenomena"], "turns": turns})
    return out


SGD_SERVICES = {"Weather_1", "Alarm_1", "Music_3", "Media_3", "Movies_3", "Events_3", "Travel_1", "Music_1",
                "Music_2", "Media_1", "Media_2", "Movies_1", "Events_1", "Events_2", "Calendar_1"}


def sgd_conversations() -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(PDATA / "sgd" / "dialogues_*.json"))):
        for dialogue in json.load(open(f, encoding="utf-8")):
            if len(dialogue["services"]) != 1 or dialogue["services"][0] not in SGD_SERVICES:
                continue
            turns: list[dict] = []
            for index, turn in enumerate(dialogue["turns"]):
                if turn["speaker"] == "USER":
                    text = " ".join(turn["utterance"].split())
                    if RISKY.search(text) or TURN_OFF_DEVICE.search(text) or norm(text) in FOLDED:
                        break
                    turns.append({"user": text, "assistant": None})
                elif turns:
                    turns[-1]["assistant"] = turn["utterance"]
                if len([t for t in turns if t["assistant"] is not None]) >= 5:
                    break
            turns = turns[:6]
            if len(turns) >= 3:
                turns[-1]["assistant"] = None
                out.append({"source": "sgd_en", "source_id": f"sgd:{dialogue['dialogue_id']}", "phenomenon": dialogue["services"][0],
                            "turns": turns})
    return out


def oasst_conversations(rng) -> list[dict]:
    oasst = next((PDATA / "hf" / "hub" / "datasets--OpenAssistant--oasst2" / "snapshots").glob("*/data/train-*.parquet"))
    d = pd.read_parquet(oasst, columns=["message_id", "parent_id", "role", "text", "lang", "rank"])
    d = d[d["lang"] == "es"]
    children: dict = {}
    for row in d.to_dict("records"):
        parent = None if pd.isna(row["parent_id"]) else row["parent_id"]
        children.setdefault(parent, []).append(row)
    out = []
    for root in children.get(None, []):
        if root["role"] != "prompter":
            continue
        turns, node = [], root
        while node is not None and node["role"] == "prompter" and len(turns) < 6:
            text = " ".join(str(node["text"]).split())
            if not (3 <= len(text) <= 300) or RISKY.search(text) or norm(text) in FOLDED:
                break
            replies = sorted(children.get(node["message_id"], []), key=lambda r: (r["rank"] if r["rank"] == r["rank"] else 99))
            if not replies:
                turns.append({"user": text, "assistant": None})
                break
            reply = replies[0]
            turns.append({"user": text, "assistant": " ".join(str(reply["text"]).split())[:1500]})
            follow = [c for c in children.get(reply["message_id"], []) if c["role"] == "prompter"]
            node = rng.choice(follow) if follow else None
        if len(turns) < 3:
            continue
        turns[-1]["assistant"] = None
        said: set[str] = set()
        dependent = True
        for index, turn in enumerate(turns):
            if index and not (_words(turn["user"]) & said or _CONTINUES.search(turn["user"])):
                dependent = False
            said |= _words(turn["user"]) | _words(turn["assistant"] or "")
        if dependent:
            out.append({"source": "oasst_es", "source_id": f"oasst2:{root['message_id']}", "phenomenon": "chat",
                        "turns": turns})
    return out


def pick_conversations(rng) -> dict[str, list[dict]]:
    pools = {"presto": presto_conversations(), "sgd": sgd_conversations(), "oasst": oasst_conversations(rng)}
    for p in pools.values():
        rng.shuffle(p)
    # per set: ~half PRESTO turns, ~30 % SGD, ~20 % oasst2
    share = {"presto": 0.45, "sgd": 0.33, "oasst": 0.22}
    out: dict[str, list[dict]] = {s: [] for s in SIZES}
    counts = {k: len(v) for k, v in pools.items()}
    for s in ("A", "B", "F"):
        for kind, fraction in share.items():
            target = round(PUBCONV_TURNS[s] * fraction)
            got = 0
            while got < target and pools[kind]:
                conv = pools[kind].pop()
                out[s].append(conv)
                got += len(conv["turns"])
    return out, counts


def main() -> None:
    rng = random.Random(SEED)
    pool = singles_pool()
    singles = pick_singles(pool, rng)
    conversations, conv_counts = pick_conversations(rng)
    OUT.mkdir(parents=True, exist_ok=True)
    for s in SIZES:
        with open(OUT / f"singles_{s}.jsonl", "w", encoding="utf-8", newline="\n") as sink:
            for row in singles[s]:
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(OUT / f"pubconv_{s}.jsonl", "w", encoding="utf-8", newline="\n") as sink:
            for row in conversations[s]:
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("pool sizes after exclusion:", {k: len(v) for k, v in pool.items()})
    print("public conversation pools:", conv_counts)
    for s in SIZES:
        by = {}
        for r in singles[s]:
            by[r["source"]] = by.get(r["source"], 0) + 1
        conv_turns = sum(len(c["turns"]) for c in conversations[s])
        kinds = {}
        for c in conversations[s]:
            kinds[c["source"]] = kinds.get(c["source"], 0) + 1
        print(f"set {s}: singles {len(singles[s])} {by}; public conversations {len(conversations[s])} "
              f"({conv_turns} turns) {kinds}")


if __name__ == "__main__":
    sys.exit(main())
