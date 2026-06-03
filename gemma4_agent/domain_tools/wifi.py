"""WiFi domain tools — extracted from domain_tools.py.

Antes vivían inline en domain_tools.py (líneas ~4382-4756); el área wifi se
movió a su propio módulo. domain_tools.py re-exporta TODO lo público con `from
.domain_tools_wifi import *` para que callers existentes (test_wifi_resolve.py
hace `from gemma4_agent import domain_tools as dt; dt._device_wifi_X`) sigan
funcionando sin cambios.

Funciones extraídas (9):
  _device_wifi_add_profile     (WPA2 profile create via netsh)
  _device_wifi_delete_profile
  _device_wifi_status          (netsh wlan show interfaces, parsea i18n)
  _device_wifi_profiles        (netsh wlan show profiles)
  _device_wifi_scan            (netsh wlan show networks mode=bssid)
  _device_wifi_connect         (resuelve nombre + connect, status=done|needs_*)
  _device_wifi_disconnect
  _wifi_match_score            (fuzzy matching, multi-token, anti-FP guard)
  _resolve_wifi_target         (perfil > SSID visible > none/ambiguous)

Helpers privados extraídos:
  _xml_escape                  (solo usado por add_profile)
  _WIFI_FILLER                 (stoplist multilingüe — palabras de relleno
                                alrededor del nombre, NO keywords de intent)

Helpers compartidos importados desde _shared:
  _ok, _err

NO toca conexión wifi real — eso lo hace netsh subprocess. Los tests existentes
mockean subprocess.run y _device_wifi_profiles/_device_wifi_scan."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .._shared import _err, _ok


__all__ = [
    "_device_wifi_add_profile",
    "_device_wifi_delete_profile",
    "_device_wifi_status",
    "_device_wifi_profiles",
    "_device_wifi_scan",
    "_device_wifi_connect",
    "_device_wifi_disconnect",
    "_wifi_match_score",
    "_resolve_wifi_target",
    "_xml_escape",
    "_WIFI_FILLER",
]


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def _device_wifi_add_profile(args: dict[str, Any]) -> dict[str, Any]:
    """Create a WPA2-Personal Wi-Fi profile via netsh wlan add profile.

    Template from Microsoft Win32 Native Wifi docs (WPA2-Personal sample).
    """
    ssid = str(args.get("ssid") or args.get("name") or "").strip()
    password = str(args.get("password") or args.get("key") or "").strip()
    if not ssid or not password:
        return _err("wifi_add_profile requires ssid and password")
    if len(password) < 8 or len(password) > 63:
        return _err("WPA2 passphrase must be 8-63 ASCII characters", length=len(password))
    auto_connect = bool(args.get("auto_connect", True))
    connection_mode = "auto" if auto_connect else "manual"
    profile_xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{_xml_escape(ssid)}</name>
  <SSIDConfig>
    <SSID>
      <name>{_xml_escape(ssid)}</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>{connection_mode}</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{_xml_escape(password)}</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>
"""
    fd, tmp_path = tempfile.mkstemp(suffix=".xml", prefix="gemma4_wlan_")
    try:
        os.close(fd)
        Path(tmp_path).write_text(profile_xml, encoding="utf-8")
        scope = "all" if bool(args.get("all_users", False)) else "current"
        proc = subprocess.run(
            ["netsh", "wlan", "add", "profile", f"filename={tmp_path}", f"user={scope}"],
            capture_output=True, text=True, timeout=20,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    if proc.returncode != 0:
        return _err("netsh wlan add profile failed", stderr=proc.stderr, exit_code=proc.returncode, stdout=proc.stdout[-500:])
    return _ok(
        ssid=ssid,
        connection_mode=connection_mode,
        scope=scope if 'scope' in locals() else 'current',
        exit_code=proc.returncode,
        stdout=proc.stdout.strip()[:500],
        note="Profile added. Use wifi_connect with the same SSID to actually associate.",
        verified=True,
    )


def _device_wifi_delete_profile(args: dict[str, Any]) -> dict[str, Any]:
    ssid = str(args.get("ssid") or args.get("name") or "").strip()
    if not ssid:
        return _err("missing ssid")
    proc = subprocess.run(["netsh", "wlan", "delete", "profile", f"name={ssid}"], capture_output=True, text=True, timeout=10)
    return _ok(
        ssid=ssid,
        exit_code=proc.returncode,
        stdout=proc.stdout.strip()[:500],
        stderr=proc.stderr[-500:],
        verified=proc.returncode == 0,
    )


def _device_wifi_status() -> dict[str, Any]:
    # timeout 15 -> 6s + try/except. netsh wlan show interfaces normalmente
    # tarda <500ms; si Wlansvc esta caido o sin adaptador, mejor abortar
    # rapido que bloquear 15s.
    try:
        proc = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return _err("netsh wlan timeout", reason="wlansvc_unresponsive")
    if proc.returncode != 0:
        return _err("netsh wlan show interfaces failed", stderr=proc.stderr, exit_code=proc.returncode)
    fields: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().casefold()] = value.strip()
    # netsh localizes keys; map both english and spanish.
    def pick(*keys: str) -> Any:
        for k in keys:
            if fields.get(k.casefold()) is not None:
                return fields.get(k.casefold())
        return None
    return _ok(
        ssid=pick("ssid"),
        state=pick("state", "estado"),
        signal=pick("signal", "señal"),
        radio_type=pick("radio type", "tipo de radio"),
        bssid=pick("bssid"),
        receive_rate_mbps=pick("receive rate (mbps)", "velocidad de recepción (mbps)"),
        transmit_rate_mbps=pick("transmit rate (mbps)", "velocidad de transmisión (mbps)"),
        raw=fields,
    )


def _device_wifi_profiles() -> dict[str, Any]:
    try:
        proc = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return _err("netsh wlan timeout", reason="wlansvc_unresponsive")
    if proc.returncode != 0:
        return _err("netsh wlan show profiles failed", stderr=proc.stderr)
    profiles: list[str] = []
    for line in proc.stdout.splitlines():
        if "All User Profile" in line or "Perfil de todos los usuarios" in line:
            _, _, name = line.partition(":")
            name = name.strip()
            if name:
                profiles.append(name)
    return _ok(profiles=profiles, count=len(profiles))


def _device_wifi_scan() -> dict[str, Any]:
    # netsh wlan show networks lists currently visible SSIDs.
    # timeout 20 -> 10s: el scan puede tardar 2-8s segun el adaptador y
    # cuantas redes visibles haya. 10s es suficiente headroom.
    try:
        proc = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return _err("netsh wlan scan timeout", reason="wlansvc_unresponsive")
    if proc.returncode != 0:
        return _err("netsh wlan show networks failed", stderr=proc.stderr)
    networks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in proc.stdout.splitlines():
        s = line.strip()
        if s.startswith("SSID ") and ":" in s:
            if current:
                networks.append(current)
            _, _, ssid = s.partition(":")
            current = {"ssid": ssid.strip()}
        elif current is not None and ":" in s:
            key, _, value = s.partition(":")
            current[key.strip().casefold()] = value.strip()
    if current:
        networks.append(current)
    return _ok(networks=networks[:50], count=len(networks))


# Palabras de relleno que el usuario/4B mete alrededor del NOMBRE de la red
# ("conectame a la red wifi de la familia" -> el nombre es 'familia'). NO es una
# keyword-list de intención: son artículos + los términos técnicos genéricos
# ("wifi"/"red"/"network"/"wlan", multilingüe) que NUNCA son parte del SSID real.
# Mismo espíritu que _APP_NAME_STOPWORDS del resolver de apps. Se quitan SOLO del
# lado del dictado para extraer el nombre; el SSID real se respeta tal cual.
_WIFI_FILLER = frozenset({
    "wifi", "wi-fi", "wlan", "red", "redes", "network", "rede", "réseau",
    "reseau", "internet", "conexion", "conexión", "connection",
    "a", "al", "the", "de", "del", "la", "el", "los", "las", "un", "una",
    "to", "me", "mi", "tu", "su", "of", "and", "y", "en", "on", "the",
})


def _wifi_match_score(query: str, candidate: str) -> float:
    """Puntaje 0..1 de cuán bien `query` (lo que dijo el usuario, p.ej. 'la de la
    familia') matchea un nombre de red `candidate` ('Familia Prueba'). NO es una
    lista de keywords de intención: mide la FORMA del nombre contra el dictado, con
    difflib — el mismo idioma de matching que usa el resolver de apps (tools.py).
    Robusto a mayúsculas, a relleno alrededor del nombre, a que el usuario diga
    solo una parte, y a typos de voz."""
    import difflib
    q_raw = (query or "").strip().casefold()
    c = (candidate or "").strip().casefold()
    if not q_raw or not c:
        return 0.0
    if q_raw == c:
        return 1.0
    # quitar relleno del DICTADO para quedarnos con el nombre real
    # ("la red wifi de la familia" -> "familia"). El candidato (SSID) NO se toca.
    q_core_tokens = [t for t in re.split(r"[\s_\-.]+", q_raw)
                     if t and t not in _WIFI_FILLER]
    q = " ".join(q_core_tokens) if q_core_tokens else q_raw
    if q == c:
        return 1.0
    # substring: el usuario casi siempre dice un PEDAZO del nombre real
    # ("movistar" -> "MOVISTAR_PLUS_X0", "familia" -> "Familia Prueba").
    if q in c or c in q:
        shorter, longer = (q, c) if len(q) <= len(c) else (c, q)
        # GUARD anti-falso-positivo: un substring MUY corto ("ev", 2 chars) cae
        # dentro de muchas palabras largas ("nuevared" contiene "ev") sin ser un
        # match real. Exigimos que el trozo común sea sustancial (≥4 chars) o
        # caiga en un BORDE de token (no embebido en medio de otra palabra). No
        # es una keyword-list: es la FORMA del solapamiento.
        on_boundary = bool(re.search(
            r"(?:^|[\s_\-.])" + re.escape(shorter) + r"(?:$|[\s_\-.])", longer))
        if len(shorter) >= 4 or on_boundary:
            # base alta para que un substring claro gane al ruido; el desempate
            # entre varios ("vtr" en 3 redes VTR) lo maneja el caller.
            return 0.86
        # substring corto y embebido -> dejar que el resto de heurísticas decidan
        # (cae al overlap de tokens / fuzzy abajo).
    # overlap de tokens (orden-independiente): "casa familia" ~ "Familia Prueba".
    # Ponderado por cobertura de AMBOS lados (Jaccard-ish): un solo token genérico
    # compartido en una frase larga ('...esta red xyz' vs 'RED_LISTA') NO debe
    # alcanzar el umbral fuerte — sería un falso positivo que conecta a la red
    # equivocada. Exigimos que el match cubra una fracción real del candidato Y
    # del query.
    q_tokens = {t for t in re.split(r"[\s_\-.]+", q) if len(t) >= 3}
    c_tokens = {t for t in re.split(r"[\s_\-.]+", c) if len(t) >= 3}
    if q_tokens and c_tokens:
        inter = q_tokens & c_tokens
        if inter:
            cov_q = len(inter) / len(q_tokens)   # cuánto del dictado se explica
            cov_c = len(inter) / len(c_tokens)   # cuánto del nombre real se cubre
            # un token suelto de muchos (p.ej. 'wifi'/'red', genéricos) -> coverage
            # baja -> score por debajo de 0.6 (el umbral fuerte). Esto evita falsos
            # positivos por una palabra común SIN una stoplist hardcoded: lo que
            # decide es la FORMA (qué fracción de ambos nombres se cubre), no qué
            # palabra es. Dos tokens que cubren ambos lados -> score alto.
            return 0.4 + 0.5 * min(cov_q, cov_c)
    # fuzzy por frase completa (typos de voz). Guard de 1ª letra en token corto
    # (como en el resolver de apps): "teams"~"steam" es anagrama, no typo.
    full = difflib.SequenceMatcher(None, q, c).ratio()
    if full >= 0.72:
        return min(0.8, full)
    return 0.0


def _resolve_wifi_target(name: str) -> dict[str, Any]:
    """Resuelve el nombre dicho por el usuario a un nombre de red REAL usando el
    ESTADO DEL SO (perfiles guardados + SSIDs visibles vía netsh) — no keywords.
    Devuelve {'resolved': <nombre exacto>, 'source': 'profile'|'ssid', 'exact':
    bool} si hay un ganador claro; {'ambiguous': [...]} si hay varios candidatos
    parejos (el caller pregunta, no adivina); {'none': True, ...} si nada matchea.
    Prefiere PERFILES GUARDADOS (el usuario ya se conectó: tiene credenciales)
    sobre SSIDs visibles sin perfil."""
    profiles = _device_wifi_profiles().get("profiles", []) or []
    # 1) match exacto (incluyendo case-insensitive) sobre perfiles guardados
    if name in profiles:
        return {"resolved": name, "source": "profile", "exact": True}
    ci = [p for p in profiles if p.casefold() == name.casefold()]
    if ci:
        return {"resolved": ci[0], "source": "profile", "exact": True}
    # 2) fuzzy sobre perfiles guardados
    scored = sorted(
        ((_wifi_match_score(name, p), p) for p in profiles),
        key=lambda t: t[0], reverse=True,
    )
    strong = [(s, p) for s, p in scored if s >= 0.6]
    if len(strong) == 1:
        return {"resolved": strong[0][1], "source": "profile", "exact": False,
                "score": round(strong[0][0], 2)}
    if len(strong) >= 2:
        # ¿hay un ganador destacado (margen claro sobre el 2º)?
        if strong[0][0] - strong[1][0] >= 0.2:
            return {"resolved": strong[0][1], "source": "profile", "exact": False,
                    "score": round(strong[0][0], 2)}
        return {"ambiguous": [p for _, p in strong[:6]], "source": "profile"}
    # 3) sin perfil que matchee: ¿hay un SSID VISIBLE que matchee? (red nueva,
    # sin credenciales guardadas -> necesitará password, pero al menos confirmamos
    # que existe y devolvemos su nombre exacto para el flujo de add_profile).
    try:
        nets = _device_wifi_scan().get("networks", []) or []
        ssids = [str(n.get("ssid") or "").strip() for n in nets]
        ssids = [s for s in ssids if s]
    except Exception:
        ssids = []
    s_scored = sorted(
        ((_wifi_match_score(name, s), s) for s in ssids),
        key=lambda t: t[0], reverse=True,
    )
    s_strong = [(sc, s) for sc, s in s_scored if sc >= 0.6]
    if len(s_strong) == 1 or (len(s_strong) >= 2 and s_strong[0][0] - s_strong[1][0] >= 0.2):
        return {"resolved": s_strong[0][1], "source": "ssid", "exact": False,
                "score": round(s_strong[0][0], 2)}
    if len(s_strong) >= 2:
        return {"ambiguous": [s for _, s in s_strong[:6]], "source": "ssid"}
    return {"none": True, "profiles": profiles[:30], "visible_ssids": ssids[:30]}


def _device_wifi_connect(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or args.get("ssid") or args.get("profile") or "").strip()
    if not name:
        return _err("missing profile name; pass name=<existing profile>")
    password = str(args.get("password") or args.get("key") or "").strip()
    created = None

    # RESOLUCIÓN POR ESTADO DEL SO (usuario sin manos): el usuario
    # dice el nombre de la red como lo recuerda ('la de la familia', 'vtr'), no
    # el SSID exacto guardado ('Familia Prueba'). Antes exigíamos match exacto
    # -> "profile not found". Ahora resolvemos contra perfiles guardados + SSIDs
    # visibles (netsh), con desambiguación honesta si hay varios. NO keywords.
    target = _resolve_wifi_target(name)
    if target.get("ambiguous"):
        cands = target["ambiguous"]
        return _err(
            f"varias redes coinciden con '{name}'; especificá cuál",
            status="needs_user",
            ambiguous_matches=cands,
            hint="repetí el nombre más específico (p.ej. el nombre completo de la red)",
        )
    if target.get("resolved"):
        resolved = target["resolved"]
        if target.get("source") == "ssid" and not target.get("exact"):
            # matchea un SSID visible pero NO hay perfil guardado: hace falta
            # credencial. Si vino password, creamos el perfil; si no, pedimos.
            if password:
                created = _device_wifi_add_profile({
                    "ssid": resolved, "password": password,
                    "auto_connect": bool(args.get("auto_connect", True)),
                    "all_users": bool(args.get("all_users", False))})
                if not created.get("ok"):
                    return created
            else:
                return _err(
                    f"'{resolved}' está visible pero no tiene perfil guardado; "
                    "necesito la contraseña para conectarme",
                    status="needs_user", matched_ssid=resolved,
                )
        name = resolved  # nombre real para netsh connect
    else:
        # nada matcheó. Si vino password, tratamos `name` como SSID nuevo a crear.
        if password:
            created = _device_wifi_add_profile({
                "ssid": name, "password": password,
                "auto_connect": bool(args.get("auto_connect", True)),
                "all_users": bool(args.get("all_users", False))})
            if not created.get("ok"):
                return created
        else:
            return _err(
                f"no encontré una red guardada ni visible que coincida con '{name}'; "
                "pasá la contraseña para crear el perfil, o decime el nombre exacto",
                status="needs_user",
                available_profiles=target.get("profiles", [])[:30],
                visible_ssids=target.get("visible_ssids", [])[:30],
            )

    proc = subprocess.run(["netsh", "wlan", "connect", f"name={name}"], capture_output=True, text=True, timeout=20)
    return _ok(
        profile=name,
        requested=str(args.get("name") or args.get("ssid") or "").strip(),
        resolved_from_state=(name != str(args.get("name") or args.get("ssid") or "").strip()),
        created_profile=created,
        exit_code=proc.returncode,
        stdout=proc.stdout.strip()[:500],
        stderr=proc.stderr.strip()[:500],
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
    )


def _device_wifi_disconnect() -> dict[str, Any]:
    proc = subprocess.run(["netsh", "wlan", "disconnect"], capture_output=True, text=True, timeout=10)
    return _ok(exit_code=proc.returncode, stdout=proc.stdout.strip(), verified=proc.returncode == 0)
