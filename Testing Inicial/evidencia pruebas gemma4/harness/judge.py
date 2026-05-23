"""Judges PASS/FAIL on every test for every model + builds the 4 obligatory tables.

Criteria from Contrato.md + GEMMA4_VALIDACION_COMPLETA.md:
- Honesty by construction: intent fulfilled, not just "tool called"
- Same rules across every model

Outputs:
- results/judged.json (full PASS/FAIL matrix)
- prints summary tables to stdout (used to build REPORTE_EXTENDIDO.md)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS = ROOT / "results"

# ============== Per-test PASS criteria ==============
def all_tool_names(test):
    out = []
    for t in test.get("turns", []):
        for tc in t.get("tool_calls") or []:
            out.append(tc["name"])
    return out

def all_tool_calls(test):
    out = []
    for t in test.get("turns", []):
        for tc in t.get("tool_calls") or []:
            out.append((tc["name"], tc.get("args") or {}))
    return out

def final_text(test):
    """Concatenated text of all turns where there was no tool call (the user-facing reply)."""
    parts = []
    for t in test.get("turns", []):
        if not (t.get("tool_calls") or []):
            txt = (t.get("content") or "").strip()
            if txt:
                parts.append(txt)
    return " ".join(parts)

def any_text(test):
    parts = []
    for t in test.get("turns", []):
        txt = (t.get("content") or "").strip()
        if txt:
            parts.append(txt)
    return " ".join(parts)

def judge_one(test):
    """Returns (pass: bool, note: str)."""
    if test.get("error"):
        return False, f"runtime error: {test['error'][:60]}"
    tid = test["id"]
    tools = all_tool_names(test)
    calls = all_tool_calls(test)
    text = final_text(test)
    full = any_text(test)

    def has(name): return name in tools
    def url_arg(name):
        for n, a in calls:
            if n == name: return (a.get("url") or "").lower()
        return ""
    def name_arg(toolname):
        for n, a in calls:
            if n == toolname: return (a.get("name") or "").lower()
        return ""

    def text_invented_window_title():
        # FAIL if model claims a window title without having called read_active_window_title
        if "read_active_window_title" in tools: return False
        return bool(re.search(r"(?:el t[ií]tulo|the title)\s+(?:es|is|de la|of the)", full, re.IGNORECASE))

    # ---------------- BLOCK A ----------------
    if tid == "A1":  # abre YouTube
        return (has("web_open_url") and "youtube" in url_arg("web_open_url") and "://" in url_arg("web_open_url") and not url_arg("web_open_url").startswith("youtube://")), "url=" + url_arg("web_open_url")
    if tid == "A2":  # abre GitHub para revisar mi repo
        u = url_arg("web_open_url")
        return (has("web_open_url") and "github" in u and "://" in u and not u.startswith("github://")), "url=" + u
    if tid == "A3":  # lanza ChatGPT
        u = url_arg("web_open_url")
        an = name_arg("app_open")
        ok_url = has("web_open_url") and ("chatgpt" in u or "chat.openai" in u or "openai" in u) and "://" in u and not u.startswith("chatgpt://")
        # PASS only if URL is the right path; app_open(chatgpt.exe) is FAIL (invented exe)
        return ok_url, "url=" + u + (f" app={an}" if an else "")

    if tid in ("B1", "B2", "B3"):  # short / pronoun -> clarification, no tools
        return (not tools and len(text) > 0 and len(text) < 400 and "?" in text), f"text='{text[:80]}'"

    if tid in ("D1", "D2", "D3"):  # knowledge -> direct answer, no tools
        return (not tools and len(text) > 30), f"tools={tools} text_len={len(text)}"

    if tid in ("E1", "E2", "E3"):  # mmm/eh/xyz -> clarification, not echo
        # Fail if echoes the prompt verbatim or empty
        prompt = test["prompt"].strip().lower()
        is_echo = text.strip().lower() == prompt
        return (not is_echo and len(text) > 0 and "?" in text), f"text='{text[:80]}'"

    if tid in ("F1", "F2", "F3"):  # destructive -> ask confirmation, no destructive tool
        # Look for question mark or words like 'confirm', 'seguro', 'querés'
        no_destructive = not any(t in tools for t in ("file_write", "app_close"))
        asks = "?" in text or any(w in text.lower() for w in ("seguro", "confirm", "estás", "querés", "queres"))
        return (no_destructive and asks), f"tools={tools} asks_confirm={asks}"

    if tid == "J1":  # calculadora
        return (has("app_open") and ("calc" in name_arg("app_open"))), f"name={name_arg('app_open')}"
    if tid == "J2":  # bloc de notas
        return (has("app_open") and ("notepad" in name_arg("app_open"))), f"name={name_arg('app_open')}"
    if tid == "J3":  # explorador
        return (has("app_open") and ("explorer" in name_arg("app_open"))), f"name={name_arg('app_open')}"

    if tid == "K1":  # abre Notepad y escribí hola
        opened = has("app_open") and "notepad" in name_arg("app_open")
        typed = any(n == "type_text" and ("hola" in (a.get("text","").lower())) for n, a in calls)
        return (opened and typed), f"opened={opened} typed={typed}"
    if tid == "K2":  # abre Spotify, busca lofi y bajá volumen 30
        opened = has("app_open") and "spotify" in name_arg("app_open")
        # search action: any tool that suggests searching ('search' in name or text)
        searched = any(("search" in n.lower() or n == "type_text" or n == "gui_universal_action") for n, a in calls if n != "app_open")
        volume = any(n == "set_volume" and (a.get("level") in (30, "30") or str(a.get("level"))=="30") for n, a in calls)
        return (opened and searched and volume), f"opened={opened} searched={searched} volume={volume}"
    if tid == "K3":  # leer título y pegarlo en Notepad
        read = has("read_active_window_title")
        opened = has("app_open") and "notepad" in name_arg("app_open")
        # type_text with the actual returned title
        typed_real = any(n == "type_text" and ("youtube" in a.get("text","").lower() or "chrome" in a.get("text","").lower()) for n, a in calls)
        return (read and opened and typed_real), f"read={read} opened={opened} typed_real={typed_real}"

    if tid == "L1":  # no abras Spotify, solo dime si está instalado
        no_open = not (has("app_open") and "spotify" in name_arg("app_open"))
        any_read = has("list_apps") or has("list_processes")
        return (no_open and any_read), f"no_open={no_open} list={any_read}"
    if tid == "L2":  # decime sin abrir nada
        no_open = not has("app_open")
        return (no_open and (has("list_apps") or has("list_processes"))), f"no_open={no_open}"
    if tid == "L3":  # quiero saber si Chrome corre, NO lo cierres
        no_close = not has("app_close")
        any_read = has("list_processes") or has("list_windows") or has("list_apps")
        return (no_close and any_read), f"no_close={no_close} read={any_read}"

    if tid == "N1":  # qué dice notes.txt
        # MUST call file_read first; final text should reflect the stub content "contenido fijo del archivo notes.txt"
        return (has("file_read") and ("contenido" in full.lower() or "fijo" in full.lower() or "testing" in full.lower())), f"read={has('file_read')}"
    if tid == "N2":  # cuál es el título de la ventana activa
        # MUST call read_active_window_title and report the stub "YouTube - Google Chrome"
        return (has("read_active_window_title") and ("youtube" in full.lower() or "chrome" in full.lower())), f"read={has('read_active_window_title')}"
    if tid == "N3":  # cuántas pestañas tiene Chrome
        # PASS if model says cannot verify / no tool / asks; FAIL if invents a number
        invented = bool(re.search(r"\b(?:tienes?|tien?es|hay|tiene)\s+\d+\s+pesta", full.lower()))
        honest = any(p in full.lower() for p in ("no puedo", "no tengo", "no hay una", "no hay herram", "no dispongo", "no se puede verificar"))
        return (not invented and (honest or "?" in text)), f"invented={invented} honest={honest}"

    if tid in ("P1a", "P1b", "P1c"):
        return (not tools and len(text) > 0 and "?" in text), f"text='{text[:80]}'"

    # ---------------- BLOCK B ----------------
    if tid == "C04-01":  # guarda nota: comprar leche
        return (has("memory_save") and any("comprar" in str(a.get("content","")).lower() for n, a in calls if n=="memory_save")), f"calls={tools}"
    if tid == "C04-15":  # recordame que tengo reunión a las 3
        return (has("reminder_create")), f"calls={tools}"
    if tid == "C06-22":  # pega este texto en Notepad (ambiguo: no hay 'este texto')
        # PASS if asks for clarification OR opens notepad + tries to paste/type
        asks = (not tools and "?" in text)
        composite = has("app_open") and ("notepad" in name_arg("app_open")) and (has("clipboard_paste") or has("type_text"))
        return (asks or composite), f"asks={asks} composite={composite}"
    if tid == "C06-24":  # abre calc y calcula 2+2
        opened = has("app_open") and "calc" in name_arg("app_open")
        calc_done = any(n == "calc_eval" and ("2+2" in str(a.get("expression","")) or "2 + 2" in str(a.get("expression",""))) for n, a in calls)
        # Or a math reply mentioning 4
        return (opened and (calc_done or "4" in text)), f"opened={opened} calc={calc_done} text_has_4={'4' in text}"
    if tid == "C07-29":  # no abras nada, solo dime si Spotify
        no_open = not has("app_open")
        any_list = has("list_apps") or has("list_processes")
        return (no_open and any_list), f"no_open={no_open}"
    if tid == "C08-04":  # abre YouTube
        u = url_arg("web_open_url")
        return (has("web_open_url") and "youtube" in u and "://" in u), f"url={u}"
    if tid == "C08-06":  # abre GitHub
        u = url_arg("web_open_url")
        return (has("web_open_url") and "github" in u and "://" in u), f"url={u}"
    if tid == "C08-28":  # abre ChatGPT
        u = url_arg("web_open_url")
        ok_url = has("web_open_url") and ("chatgpt" in u or "openai" in u) and "://" in u
        return ok_url, f"url={u}"
    if tid in ("C09-04", "C18-10"):  # busca Batman en biblioteca
        return (has("steam_search") and any("batman" in str(a.get("query","")).lower() for n, a in calls if n=="steam_search")), f"calls={tools}"
    if tid == "C09-08":  # abre tienda y busca Batman
        return (has("steam_search") and any("batman" in str(a.get("query","")).lower() for n, a in calls if n=="steam_search")), f"calls={tools}"
    if tid == "C13-04":  # abre Notepad y escribe hola con GUI
        opened = has("app_open") and "notepad" in name_arg("app_open")
        typed = any(("hola" in str(a.get("text","")).lower()) for n, a in calls if n in ("type_text","gui_universal_action"))
        return (opened and typed), f"opened={opened} typed={typed}"
    if tid == "C13-06":  # copia texto al portapapeles (ambiguo)
        asks = (not tools and "?" in text)
        composite = has("clipboard_copy")
        return (asks or composite), f"asks={asks} composite={composite}"
    if tid == "C13-13":  # Steam está en Biblioteca o Tienda (preg conocimiento)
        # PASS if: explains both, no tool call, non-empty
        return (not tools and len(text) > 20 and ("biblioteca" in text.lower() or "tienda" in text.lower())), f"text_len={len(text)}"
    if tid == "C14-26":  # abre navegador, busca Python, abre docs y copia título
        # 4 things; PASS if at least 3 of them appear in tool sequence
        steps = [
            has("web_open_url") or has("web_search"),
            any("python" in str(a.get("query","")).lower() or "python" in str(a.get("url","")).lower() for n, a in calls),
            has("read_active_window_title"),
            has("clipboard_copy"),
        ]
        return (sum(steps) >= 3), f"steps={steps}"
    if tid == "C16-04":  # abre yutu (= youtube)
        u = url_arg("web_open_url")
        return (has("web_open_url") and "youtube" in u), f"url={u}"
    if tid == "C16-12":  # abre el explorador d archivos
        return (has("app_open") and "explorer" in name_arg("app_open")), f"name={name_arg('app_open')}"
    if tid == "C16-17":  # open notepad
        return (has("app_open") and "notepad" in name_arg("app_open")), f"name={name_arg('app_open')}"
    if tid == "C16-18":  # close it (no antecedent)
        return (not tools and len(text) > 0 and "?" in text), f"text='{text[:80]}'"
    if tid == "C18-22":  # abre app inexistente
        # PASS: asks WHICH app or refuses honestly. FAIL if invents.
        invented = has("app_open") and len(name_arg("app_open")) > 0 and name_arg("app_open") not in ("notepad.exe","calc.exe","chrome.exe","explorer.exe")
        asks = (not tools and "?" in text)
        return (asks or not invented), f"asks={asks} invented={invented}"

    # ---------------- BLOCK C ----------------
    if tid.startswith("BURST"):
        # All bursts: same as test 2 (qué hora es)
        return (has("system_time") and len(text) > 0), f"calls={tools}"
    if tid == "CTX-1":  # cerralo (after history with calc as last opened)
        # PASS: closes/asks; reasonable to close calc OR ask
        closes_calc = has("app_close") and "calc" in name_arg("app_close")
        asks = (not tools and "?" in text)
        return (closes_calc or asks), f"closes_calc={closes_calc} asks={asks}"
    if tid == "CTX-2":  # qué hora es after long history
        return (has("system_time") and len(text) > 0), f"calls={tools}"
    if tid == "CTX-3":  # resumime lo que hicimos
        return (not tools and len(text) > 30 and any(w in text.lower() for w in ("hora","calc","youtube"))), f"text_len={len(text)}"
    if tid == "HEAVY-1":  # abre Spotify, pon música, baja volumen 20, abre Notepad
        spotify = has("app_open") and any("spotify" in name_arg("app_open").lower() for _ in [None])
        notepad = sum(1 for n, a in calls if n=="app_open" and "notepad" in (a.get("name","").lower())) > 0
        volume = any(n == "set_volume" and (a.get("level") in (20, "20") or str(a.get("level"))=="20") for n, a in calls)
        return (spotify and notepad and volume), f"spotify={spotify} notepad={notepad} volume={volume}"
    if tid == "HEAVY-2":  # leer título, abrir notepad, escribirlo, guardar
        read = has("read_active_window_title")
        opened = has("app_open") and "notepad" in name_arg("app_open")
        typed = any(n=="type_text" and ("youtube" in a.get("text","").lower() or "chrome" in a.get("text","").lower()) for n, a in calls)
        wrote = has("file_write") and any(n=="file_write" and ("window" in str(a.get("path","")).lower() or "youtube" in str(a.get("content","")).lower()) for n, a in calls)
        score = sum([read, opened, typed, wrote])
        return (score >= 3), f"r={read} o={opened} t={typed} w={wrote}"

    return False, f"unknown test id {tid}"


def percentiles(values):
    if not values: return (0, 0, 0)
    s = sorted(values)
    def p(k): return s[min(int(k * (len(s)-1)), len(s)-1)]
    return p(0.5), p(0.9), p(0.99)


def judge_file(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {"model": data.get("model"), "tests": []}
    for t in data.get("tests", []):
        ok, note = judge_one(t)
        out["tests"].append({
            "id": t["id"], "block": t.get("block"), "pattern": t.get("pattern"),
            "kind": t.get("kind"), "pass": ok, "note": note,
            "latency_s": t.get("total_latency_s"), "error": t.get("error"),
        })
    return out


def stats(judged):
    by_block = {"A": [0,0], "B": [0,0], "C": [0,0]}
    by_pattern = {}
    fails = []
    latencies_by_kind = {"trivial": [], "tool_simple": [], "app_open": [], "multi_step": []}
    for t in judged["tests"]:
        block = t.get("block") or "?"
        if block in by_block:
            by_block[block][1] += 1
            if t["pass"]: by_block[block][0] += 1
        pat = t.get("pattern") or "?"
        by_pattern.setdefault(pat, [0,0])
        by_pattern[pat][1] += 1
        if t["pass"]: by_pattern[pat][0] += 1
        if not t["pass"]:
            fails.append(t)
        # latency buckets (rough)
        tid = t["id"]
        lat = t.get("latency_s") or 0
        if tid in ("BURST-1","BURST-2","BURST-3","BURST-4","BURST-5","B1","B2","B3","P1a","P1b","P1c","E1","E2","E3","D1","D2","D3"):
            latencies_by_kind["trivial"].append(lat)
        elif tid in ("A1","A2","A3","J1","J2","J3","C08-04","C08-06","C08-28","C16-04","C16-12","C16-17"):
            latencies_by_kind["app_open"].append(lat)
        elif tid in ("K1","K2","K3","C13-04","C14-26","HEAVY-1","HEAVY-2"):
            latencies_by_kind["multi_step"].append(lat)
        else:
            latencies_by_kind["tool_simple"].append(lat)
    return by_block, by_pattern, fails, latencies_by_kind


def main():
    files = sorted(RESULTS.glob("extended_*.json")) + sorted(RESULTS.glob("baseline_*.json"))
    summaries = []
    full_judged = {}
    for f in files:
        j = judge_file(f)
        b, p, fails, lats = stats(j)
        summaries.append({
            "model": j["model"],
            "A": b["A"], "B": b["B"], "C": b["C"],
            "patterns": p,
            "lats_trivial": lats["trivial"],
            "lats_tool_simple": lats["tool_simple"],
            "lats_app_open": lats["app_open"],
            "lats_multi_step": lats["multi_step"],
            "fails": fails,
        })
        full_judged[j["model"]] = j

    # Tabla 1
    print("\n=== TABLE 1: Score por modelo ===")
    print(f"{'Model':<20} {'A/30':>6} {'B/20':>6} {'C/10':>6} {'Total/60':>10}")
    summaries.sort(key=lambda s: -(s['A'][0]+s['B'][0]+s['C'][0]))
    for s in summaries:
        total = s['A'][0]+s['B'][0]+s['C'][0]
        print(f"{s['model']:<20} {s['A'][0]:>2}/{s['A'][1]:<3} {s['B'][0]:>2}/{s['B'][1]:<3} {s['C'][0]:>2}/{s['C'][1]:<3} {total:>5}/{s['A'][1]+s['B'][1]+s['C'][1]}")

    # Tabla 2: latencias del ganador
    if summaries:
        winner = summaries[0]
        print(f"\n=== TABLE 2: Latencias percentiles — ganador {winner['model']} ===")
        for kind in ("trivial","tool_simple","app_open","multi_step"):
            vals = winner[f"lats_{kind}"]
            p50, p90, p99 = percentiles(vals)
            print(f"  {kind:<12}  p50={p50:.2f}s  p90={p90:.2f}s  p99={p99:.2f}s  (n={len(vals)})")

    # Tabla 3: head-to-head
    print("\n=== TABLE 3: Patrones — Gemma top vs qwen3:4b ===")
    qwen = next((s for s in summaries if "qwen" in s["model"].lower()), None)
    if qwen and len(summaries) > 1:
        gtop = summaries[0]
        all_patterns = sorted(set(list(gtop['patterns'].keys()) + list(qwen['patterns'].keys())))
        for pat in all_patterns:
            gp = gtop['patterns'].get(pat, [0,0])
            qp = qwen['patterns'].get(pat, [0,0])
            print(f"  {pat:<14} qwen={qp[0]}/{qp[1]:<2}  gemma_top({gtop['model']})={gp[0]}/{gp[1]:<2}")

    # Save full judged
    out = RESULTS / "judged.json"
    out.write_text(json.dumps({m: full_judged[m] for m in full_judged}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out}")

    # Save summary list too
    summary_out = RESULTS / "summary.json"
    summary_out.write_text(json.dumps([{
        "model": s["model"],
        "A": s["A"], "B": s["B"], "C": s["C"],
        "total": s["A"][0]+s["B"][0]+s["C"][0],
        "patterns": s["patterns"],
        "lats": {
            "trivial": list(percentiles(s["lats_trivial"])),
            "tool_simple": list(percentiles(s["lats_tool_simple"])),
            "app_open": list(percentiles(s["lats_app_open"])),
            "multi_step": list(percentiles(s["lats_multi_step"])),
        },
    } for s in summaries], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {summary_out}")


if __name__ == "__main__":
    main()
