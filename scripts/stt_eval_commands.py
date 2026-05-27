"""Generador de comandos Spanglish por PLANTILLA para el eval STT.

El eval anterior tenía solo 20 comandos a mano -> demasiado estrecho (pasaba el
test pero el user fallaba en uso real). Acá generamos cientos de comandos
combinando: verbos (muchas formas de hablar es/rioplatense/mexicano) × targets
(apps/servicios/artistas/canciones reales) × estructuras. Cada comando lleva su
ENTIDAD clave (nombre propio que debe sobrevivir) para medir Entity-Recall.

El ground truth = el texto exacto generado (alineación perfecta, sin etiquetar).
"""
from __future__ import annotations

# Verbos de "abrir/lanzar app" — muchas variantes naturales.
OPEN_VERBS = [
    "abre", "abrime", "abrí", "abre el", "andá a", "anda a", "lanzá", "lanza",
    "ejecutá", "ejecuta", "iniciá", "inicia", "arrancá", "arranca", "metete en",
    "dale a", "quiero", "quiero abrir", "ábreme", "ponme", "poné",
]
# Verbos de "reproducir media".
PLAY_VERBS = [
    "pon", "poné", "ponme", "reproduce", "reproducí", "tocá", "toca",
    "quiero escuchar", "quiero ver", "dale play a", "metele", "echa",
    "reproducime", "pone",
]
# Apps/servicios con nombre en inglés (la entidad = forma normalizada que buscamos).
APPS = [
    ("Steam", "steam"), ("Chrome", "chrome"), ("Google Chrome", "chrome"),
    ("Spotify", "spotify"), ("Discord", "discord"), ("Telegram", "telegram"),
    ("WhatsApp", "whatsapp"), ("Firefox", "firefox"), ("YouTube", "youtube"),
    ("Visual Studio Code", "visual studio code"), ("OBS", "obs"),
    ("OBS Studio", "obs"), ("Twitch", "twitch"), ("Slack", "slack"),
    ("Zoom", "zoom"), ("Epic Games", "epic"), ("Notion", "notion"),
    ("Microsoft Teams", "teams"), ("Skype", "skype"), ("Brave", "brave"),
    ("Microsoft Edge", "edge"), ("Photoshop", "photoshop"),
    ("Premiere", "premiere"), ("Blender", "blender"), ("Unity", "unity"),
    ("Visual Studio", "visual studio"), ("PyCharm", "pycharm"),
    ("IntelliJ", "intellij"), ("Word", "word"), ("Excel", "excel"),
    ("PowerPoint", "powerpoint"), ("Outlook", "outlook"), ("Signal", "signal"),
]
# Plataformas de streaming + título (entidad = la plataforma).
STREAMERS = [
    ("Netflix", "netflix"), ("Disney Plus", "disney"), ("Disney+", "disney"),
    ("HBO Max", "hbo"), ("Max", "max"), ("Prime Video", "prime"),
    ("Amazon Prime", "prime"), ("YouTube", "youtube"), ("Apple TV", "apple tv"),
    ("Crunchyroll", "crunchyroll"),
]
TITLES = [
    "Stranger Things", "Daredevil", "House of the Dragon", "The Boys",
    "Breaking Bad", "Loki", "The Last of Us", "Wednesday", "The Mandalorian",
    "Game of Thrones", "The Witcher", "Peaky Blinders", "Better Call Saul",
    "The Crown", "Black Mirror", "Squid Game", "Money Heist", "The Office",
]
# Artistas (entidad = artista) para "pon X de Y".
ARTISTS = [
    ("Bad Bunny", "bad bunny"), ("Benson Boone", "benson boone"),
    ("Taylor Swift", "taylor swift"), ("Bizarrap", "bizarrap"),
    ("Coldplay", "coldplay"), ("Queen", "queen"), ("Dua Lipa", "dua lipa"),
    ("The Weeknd", "weeknd"), ("Billie Eilish", "billie eilish"),
    ("Arctic Monkeys", "arctic monkeys"), ("Daft Punk", "daft punk"),
    ("Michael Jackson", "michael jackson"), ("Ed Sheeran", "ed sheeran"),
    ("Imagine Dragons", "imagine dragons"), ("Karol G", "karol g"),
    ("Rauw Alejandro", "rauw alejandro"), ("Feid", "feid"),
]
SONGS = [
    ("Bohemian Rhapsody", "bohemian rhapsody"), ("Despacito", "despacito"),
    ("Blinding Lights", "blinding lights"), ("Shape of You", "shape of you"),
    ("Bad Guy", "bad guy"), ("Levitating", "levitating"),
    ("Smells Like Teen Spirit", "smells like teen spirit"),
    ("Hotel California", "hotel california"), ("Billie Jean", "billie jean"),
    ("Stairway to Heaven", "stairway to heaven"),
]
# Comandos SIN anglicismo (control: no deben corromperse). Variados.
NO_ENTITY = [
    "sube el volumen", "baja el volumen", "qué hora es", "pausa la música",
    "cierra la ventana", "minimiza todo", "sube el volumen al máximo",
    "qué día es hoy", "apaga la música", "siguiente canción", "para la música",
    "reproduce la siguiente", "baja el brillo", "cuánta batería queda",
    "pon una canción", "pon música", "reproduce algo", "qué fecha es hoy",
    "cuánto espacio me queda en el disco", "qué procesador tengo",
    "sube el brillo", "silencia el sistema", "abre la calculadora",
    "qué tiempo hace hoy", "pon el temporizador en cinco minutos",
    "cierra todas las ventanas", "minimiza la ventana", "cuánta memoria tengo",
    "anterior canción", "reanuda la música", "pon el volumen a la mitad",
]

WAKE = "Hey Gemma, "


def build_commands(seed: int = 0, target: int = 1000):
    """Genera ~`target` comandos (texto, entidad) DETERMINISTAS y diversos,
    balanceados entre buckets. ~85% con anglicismo, ~15% control."""
    import random
    rng = random.Random(seed)
    out: list[tuple[str, str | None]] = []

    n_app = int(target * 0.40)
    n_stream = int(target * 0.25)
    n_artist = int(target * 0.12)
    n_song = int(target * 0.08)

    def pick(combos, k):
        rng.shuffle(combos)
        # con reposición si hace falta para llegar a k (diversidad por shuffle)
        if k <= len(combos):
            return combos[:k]
        return [combos[i % len(combos)] for i in range(k)]

    # App opens (verbo × app)
    combos = [(v, a, e) for v in OPEN_VERBS for (a, e) in APPS]
    for v, a, e in pick(combos, n_app):
        out.append((f"{WAKE}{v} {a}", e))

    # Streaming: "<play> <title> en <streamer>"
    combos = [(v, t, s, e) for v in PLAY_VERBS for t in TITLES for (s, e) in STREAMERS]
    for v, t, s, e in pick(combos, n_stream):
        out.append((f"{WAKE}{v} {t} en {s}", e))

    # Artist: "<play> <artist> en Spotify" (y variante "algo de <artist>")
    combos = []
    for v in PLAY_VERBS:
        for (a, e) in ARTISTS:
            combos.append((f"{v} {a} en Spotify", e))
            combos.append((f"{v} algo de {a}", e))
    for txt, e in pick(combos, n_artist):
        out.append((f"{WAKE}{txt}", e))

    # Song
    combos = [(f"{v} {s}", e) for v in PLAY_VERBS for (s, e) in SONGS]
    for txt, e in pick(combos, n_song):
        out.append((f"{WAKE}{txt}", e))

    # Control sin entidad (repetido para llegar a ~15%)
    n_ctrl = target - len(out)
    ctrl = NO_ENTITY[:]
    rng.shuffle(ctrl)
    for i in range(max(n_ctrl, len(NO_ENTITY))):
        out.append((f"{WAKE}{ctrl[i % len(ctrl)]}", None))

    rng.shuffle(out)
    return out[:target]


if __name__ == "__main__":
    cmds = build_commands()
    ents = sum(1 for _, e in cmds if e)
    print(f"{len(cmds)} comandos ({ents} con anglicismo, {len(cmds)-ents} control)")
    for t, e in cmds[:15]:
        print(f"  [{e}] {t}")
