"""Mata procesos que estan escuchando en 8080 (router) y 5916 (child vram4-text).
Usa psutil para evitar pasar por Stop-Process / taskkill (bloqueados por harness).
"""
import sys
import psutil

TARGET_PORTS = {8080, 5916}

killed = []
for proc in psutil.process_iter(attrs=["pid", "name"]):
    try:
        conns = proc.net_connections(kind="tcp")
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        continue
    for c in conns:
        if c.laddr and c.laddr.port in TARGET_PORTS and c.status == psutil.CONN_LISTEN:
            try:
                pid = proc.pid
                name = proc.info.get("name", "?")
                proc.terminate()
                try:
                    proc.wait(timeout=4)
                except psutil.TimeoutExpired:
                    proc.kill()
                killed.append((pid, name, c.laddr.port))
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                print(f"skip pid={proc.pid} port={c.laddr.port}: {e}")
            break

if not killed:
    print("nothing to kill (ports free)")
    sys.exit(0)
for pid, name, port in killed:
    print(f"killed pid={pid} name={name} port={port}")
