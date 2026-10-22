"""System One: MASSIVE 1.1 (Amazon, CC BY 4.0; FitzGerald et al. 2022) requests as bank cases for Laya's training.

usage: py -3.12 -X utf8 scripts/renew/system_one/massive_cases.py MASSIVE_DATA_DIR EXCLUDED_IDS.json OUT.json
Only the train and dev partitions, and never a MASSIVE id that BAXY's public holdout uses (the source of decision2 and
of the sealed holdout; the same id is the same sentence in every locale, so it is left out in all of them). Only the
intents whose BAXY expectation is clear — the mapping decision2's author applied to its own MASSIVE rows, by intent —
and at most 250 rows per intent and locale, so no intent dominates. Spanish is taken whole; English at 30 %, for spanglish.
"""
import json
import random
import sys
from pathlib import Path

# MASSIVE intent → BAXY expectation (decision2 README: time-varying facts → web.search, stable chat → text; what BAXY
# cannot do — lights, coffee, ordering food, taxis — is answered in words).
CLEAR = {
    "alarm_query": {"kind": "call", "op": "notification.list"},
    "alarm_set": {"kind": "call", "op": "notification.schedule"},
    "audio_volume_down": {"kind": "call", "op": "audio.volume.adjust"},
    "audio_volume_up": {"kind": "call", "op": "audio.volume.adjust"},
    "audio_volume_mute": {"kind": "call", "op": "audio.mute"},
    "datetime_query": {"kind": "call", "op": "system.time"},
    "weather_query": {"kind": "call_any", "ops": ["weather.current", "web.search"]},
    "news_query": {"kind": "call_any", "ops": ["web.news.headlines", "web.search"]},
    "play_music": {"kind": "call_any", "ops": ["media.play.query", "media.play.exact"]},
    "calendar_query": {"kind": "call", "op": "calendar.event.list"},
    "qa_currency": {"kind": "call", "op": "web.search"},
    "qa_stock": {"kind": "call", "op": "web.search"},
    "recommendation_events": {"kind": "call", "op": "web.search"},
    "recommendation_locations": {"kind": "call", "op": "web.search"},
    "recommendation_movies": {"kind": "call", "op": "web.search"},
    "transport_traffic": {"kind": "call", "op": "web.search"},
    "general_joke": {"kind": "text"},
    "general_quirky": {"kind": "text"},
    "general_greet": {"kind": "text"},
}
CANNOT = ("iot_cleaning", "iot_coffee", "iot_hue_lightchange", "iot_hue_lightdim", "iot_hue_lightoff",
          "iot_hue_lighton", "iot_hue_lightup", "iot_wemo_off", "iot_wemo_on", "takeaway_order", "transport_taxi",
          "transport_ticket")
for intent in CANNOT:
    CLEAR[intent] = {"kind": "text"}
CAP = 250


def main():
    data, excluded_file, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    excluded = {str(i).split(":")[-1] for i in json.loads(Path(excluded_file).read_text(encoding="utf-8"))}
    rng = random.Random(20261022)
    cases = []
    for locale, share in (("es-ES", 1.0), ("en-US", 0.3)):
        by_intent = {}
        for line in open(data / f"{locale}.jsonl", encoding="utf-8"):
            row = json.loads(line)
            if row["partition"] not in ("train", "dev") or str(row["id"]) in excluded or row["intent"] not in CLEAR:
                continue
            by_intent.setdefault(row["intent"], []).append(row)
        for intent, rows in sorted(by_intent.items()):
            rng.shuffle(rows)
            for row in rows[:int(CAP * share)]:
                family = "massive_cannot" if intent in CANNOT else f"massive_{intent}"
                cases.append({"id": f"M-{locale}-{row['id']}", "family": family,
                              "source": f"massive-v1.1:{locale}:{row['id']}", "history": [], "text": row["utt"],
                              "expect": CLEAR[intent]})
    Path(out).write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    print(len(cases), "cases ->", out)


if __name__ == "__main__":
    main()
