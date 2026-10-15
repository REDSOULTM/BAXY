"""Autoprueba del medidor de molestia SIN BAXY (dura ~1 min).

Cinco corridas, cada una con su propio medidor y sólo ventanas propias:
  limpia  nadie molesta: todo en 0, ventana y cursor del usuario al frente al final.
  carga   como limpia, con todos los núcleos ocupados por procesos propios: el gancho del simulador llega tarde y
          aun así ningún movimiento suyo cuenta como salto ajeno (el simulador anota sus puntos antes de mandarlos).
  fuera   el BAXY falso roba el foco 2 s, salta el cursor y teclea 5 letras sin marca y una 0xB9 sin marca (fuente
          «uia») en la ventana del usuario.
  pausa   el BAXY falso actúa dentro de una pausa del simulador y restaura foco y cursor (marca BAXY): la vuelta del
          cursor es restauración, no movimiento.
  tarde   como pausa, pero devuelve cursor y foco 0,6 s después de que el simulador vuelve: «restaurada tarde».
Si el dueño usa el PC durante una corrida (input real), ésta no vale y se repite más tarde.
Uso: py -3.12 autoprueba.py [--dir CARPETA] [--solo limpia,carga,fuera,pausa,tarde]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NOWINDOW = 0x08000000


def expectations(name, r):
    f = r.get("final", {})
    c = r.get("contadores", {})
    checks = [("medido", r.get("medido") is True),
              ("frente al final", f.get("frente_usuario") is True),
              ("cursor en su posición al final", f.get("cursor_en_su_posicion") is True),
              ("el simulador tecleó", r["simulador"]["tecleados"] > 0)]
    if name in ("limpia", "carga"):
        checks += [(k + "=0", r[k] == 0) for k in ("perdidos", "insertados", "teclas_baxy_en_ventana_usuario",
                                                   "robos_foco", "ms_robados", "movimientos_cursor", "clics",
                                                   "actos", "actos_fuera_de_pausa", "rafagas")]
        checks.append(("entregados == tecleados", r["simulador"]["entregados"] == r["simulador"]["tecleados"]))
    elif name == "fuera":
        checks += [("robos_foco=1", r["robos_foco"] == 1),
                   ("ms_robados en 1600..2600", 1600 <= r["ms_robados"] <= 2600),
                   ("cursor_saltado>=1", r["cursor_saltado"] >= 1),
                   ("teclas_baxy_en_ventana_usuario=6 (sin marca, una de UIA)", r["teclas_baxy_en_ventana_usuario"] == 6
                    and r["teclas_baxy_en_ventana_usuario_marca_baxy"] == 0
                    and r["teclas_baxy_en_ventana_usuario_uia"] == 1),
                   ("insertados=5", r["insertados"] == 5),
                   ("perdidos = tragados durante el robo (>=1)", r["perdidos_tragados"] >= 1
                    and r["perdidos_en_texto"] == 0),
                   ("actos fuera de pausa >=1", r["actos_fuera_de_pausa"] >= 1),
                   ("alguna ráfaga sin restaurar", r["rafagas"] > r["rafagas_restauradas"])]
    elif name == "pausa":
        checks += [("robos_foco=1", r["robos_foco"] == 1),
                   ("0 actos fuera de pausa", r["actos_fuera_de_pausa"] == 0),
                   ("cursor_saltado=1 (la ida; la vuelta es restauración)", r["cursor_saltado"] == 1
                    and r["cursor_vueltas_restauradas"] == 1),
                   ("3 teclas con marca BAXY en otra ventana", c.get("tecla_otra_ventana_baxy") == 3),
                   ("0 teclas en la ventana del usuario", r["teclas_baxy_en_ventana_usuario"] == 0),
                   ("perdidos=0 insertados=0", r["perdidos"] == 0 and r["insertados"] == 0),
                   ("1 ráfaga, restaurada", r["rafagas"] == 1 and r["rafagas_restauradas"] == 1)]
    elif name == "tarde":
        late = r.get("retrasos_restauracion_tarde_ms") or []
        checks += [("robos_foco=1", r["robos_foco"] == 1),
                   ("movimientos_cursor=1 (la ida)", r["movimientos_cursor"] == 1),
                   ("1 vuelta del cursor como restauración", r["cursor_vueltas_restauradas"] == 1),
                   ("1 ráfaga sin restaurar a tiempo y restaurada tarde", r["rafagas"] == 1
                    and r["rafagas_restauradas"] == 0 and r["rafagas_restauradas_tarde"] == 1),
                   ("retraso de la restauración tardía en 300..2000 ms", len(late) == 1 and 300 <= late[0] <= 2000)]
    return checks


def external_noise(r):
    """Ventanas que tomaron el frente y no son de esta prueba (otra sesión o el dueño moviendo cosas por voz):
    el medidor las mide bien, pero la corrida ya no sirve para comprobar las cuentas esperadas."""
    return [f"{e['titulo']} ({e['proceso']})" for e in r.get("primer_plano", [])
            if not e["usuario"] and e["titulo"] != "BAXY falso prueba molestia"]


def cpu_load():
    """Un proceso propio que gira por núcleo (se cierran por PID exacto al terminar la corrida)."""
    code = "import time\nend = time.time() + 120\nwhile time.time() < end:\n    pass\n"
    return [subprocess.Popen([sys.executable, "-c", code], creationflags=NOWINDOW) for _ in range(os.cpu_count() or 4)]


def run_once(name, base):
    d = os.path.join(base, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    out = os.path.join(d, "molestia.json")
    med = subprocess.Popen([sys.executable, os.path.join(HERE, "medidor.py"), "medir", "--control", d,
                            "--salida", out, "--inicio", "ahora", "--pausa", "2", "--espera-max", "120",
                            "--max-s", "180"], creationflags=NOWINDOW)
    fake = None
    load = []
    try:
        deadline = time.time() + 130
        while not os.path.exists(os.path.join(d, "midiendo.json")):
            if med.poll() is not None or time.time() > deadline:
                return None, "el medidor no llegó a medir (¿dueño usando el PC?)"
            time.sleep(0.1)
        time.sleep(1.5)
        if name == "limpia":
            time.sleep(7)
        elif name == "carga":
            load = cpu_load()
            time.sleep(9)
        else:
            fake = subprocess.Popen([sys.executable, os.path.join(HERE, "baxy_falso.py"), name, "--control", d,
                                     "--salida", os.path.join(d, "falso.json")], creationflags=NOWINDOW)
            fake.wait(60)
            time.sleep(2.5)
        open(os.path.join(d, "parar"), "w").close()
        med.wait(30)
    finally:
        for p in [fake, med] + load:
            if p is not None and p.poll() is None:  # cierre por PID exacto de un proceso propio
                subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)
    if not os.path.exists(out):
        return None, "sin molestia.json"
    with open(out, encoding="utf-8") as f:
        return json.load(f), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(tempfile.gettempdir(), "baxy-molestia-autoprueba"))
    ap.add_argument("--solo", default="limpia,carga,fuera,pausa,tarde")
    ap.add_argument("--intentos", type=int, default=4)
    a = ap.parse_args()
    ok_all = True
    for name in a.solo.split(","):
        for attempt in range(1, a.intentos + 1):
            r, err = run_once(name, a.dir)
            noise = external_noise(r) if r is not None else []
            if r is not None and not r.get("dueno_activo") and not noise:
                break
            why = err or ("el dueño usó el PC durante la corrida" if r.get("dueno_activo") else
                          "ruido externo: otra ventana tomó el frente: " + "; ".join(noise))
            print(f"[{name}] intento {attempt}: no vale ({why}); repito en 20 s", flush=True)
            r = None
            time.sleep(20)
        if r is None:
            print(f"[{name}] SIN RESULTADO VÁLIDO")
            ok_all = False
            continue
        checks = expectations(name, r)
        bad = [c for c, ok in checks if not ok]
        print(f"[{name}] {'PASA' if not bad else 'FALLA'}  {r['resumen']}")
        for c in bad:
            print(f"    falla: {c}")
        ok_all &= not bad
    print("AUTOPRUEBA:", "PASA" if ok_all else "FALLA", "evidencia:", a.dir)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
