"""Set 2 de comandos guiados para el A/B de voz real (probar_parakeet_mic.py).

42 comandos DISTINTOS al set 1 (los del propio script). Objetivo: ampliar la
cobertura del held-out de VOZ REAL hacia los casos que MÁS estresan a Parakeet
y al corrector, sin solapar con el set 1.

Criterios de diversidad (qué busca cada bloque):
  - apps_dificiles : nombres propios que el encoder tiende a FUSIONAR
    (sílabas poco frecuentes en español: Audacity, Krita, qBittorrent...).
    Es el caso crítico del proyecto (Boone→Moon). Acá medimos Entity-Recall.
  - juegos         : títulos con palabras inglesas mezcladas / multi-token.
  - streaming      : título inglés + plataforma, verbos variados.
  - artistas       : nombres de pila ingleses cortos (los que más se funden).
  - control_es     : español PURO con tildes/ñ — NO debe corromperse el
    corrector (non-regression). Verbos e intenciones distintos al set 1.

Cada entry: (texto_a_decir, entidad_clave_o_None). La entidad es lo que el
comando NECESITA preservar para ejecutarse; None = solo medimos que no se
corrompa (no hay nombre propio inglés que rescatar).
"""
from __future__ import annotations

# (texto, entidad_clave|None). entidad en minúsculas, como la mide _norm.
GUIDED_COMMANDS_SET2 = [
    # --- apps difíciles: nombres que el encoder suele fusionar -------------
    ("abre Audacity", "audacity"),
    ("abre Krita", "krita"),
    ("abre Blender", "blender"),
    ("abre GIMP", "gimp"),
    ("abre qBittorrent", "qbittorrent"),
    ("abre Thunderbird", "thunderbird"),
    ("abre VLC", "vlc"),
    ("abre Audible", "audible"),
    ("abre Edge", "edge"),
    ("abre Outlook", "outlook"),
    ("abre PowerPoint", "powerpoint"),
    ("abre Excel", "excel"),
    ("abre Zoom", "zoom"),
    ("abre Reddit", "reddit"),
    # --- juegos: títulos ingleses multi-palabra ----------------------------
    ("lanzá League of Legends", "league of legends"),
    ("abre Grand Theft Auto", "grand theft auto"),
    ("pon Red Dead Redemption", "red dead redemption"),
    ("abre Baldur's Gate", "baldur"),
    ("lanzá Elden Ring", "elden ring"),
    ("abre Stardew Valley", "stardew"),
    # --- streaming: título + plataforma, verbos variados -------------------
    ("reproduce The Last of Us en HBO Max", "the last of us"),
    ("pon Wednesday en Netflix", "wednesday"),
    ("quiero ver The Mandalorian en Disney Plus", "mandalorian"),
    ("ponme Loki en Disney", "loki"),
    ("reproduce The Witcher en Netflix", "witcher"),
    ("busca Arcane en Netflix", "arcane"),
    # --- artistas / canciones: nombres de pila cortos ingleses -------------
    ("pon una canción de Billie Eilish", "billie eilish"),
    ("reproduce Dua Lipa", "dua lipa"),
    ("pon Taylor Swift", "taylor swift"),
    ("reproduce Coldplay en Spotify", "coldplay"),
    ("pon Sabrina Carpenter", "sabrina carpenter"),
    ("reproduce Hozier", "hozier"),
    # --- español puro (control: NO debe corromperse) -----------------------
    ("apagá la computadora", None),
    ("subí el brillo de la pantalla", None),
    ("silenciá el micrófono", None),
    ("reproducí la canción anterior", None),
    ("cuánto falta para que termine", None),
    ("recordame comprar pan mañana", None),
    ("poné una alarma a las siete", None),
    ("cerrá todas las ventanas", None),
    ("qué tiempo hace afuera", None),
    ("leéme las notificaciones", None),
]
