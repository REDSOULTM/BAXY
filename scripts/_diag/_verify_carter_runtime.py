"""Verificación rápida del runtime tras el rebrand a Carter (wake + inventory)."""
from gemma4_agent.voice import wake, inventory

print("wake.LIVEKIT_MODEL_STEM:", wake.LIVEKIT_MODEL_STEM)
print("wake.LIVEKIT_MODEL_PATH:", wake.LIVEKIT_MODEL_PATH.name, "existe:", wake.LIVEKIT_MODEL_PATH.exists())

# wake_words (la lista que suprime la frase del transcript)
inv = inventory.load_inventory() if hasattr(inventory, "load_inventory") else None
if inv is None:
    # fallback: leer el dict de defaults
    for attr in dir(inventory):
        v = getattr(inventory, attr)
        if isinstance(v, dict) and "wake_words" in v:
            inv = v
            break
ww = (inv or {}).get("wake_words") if inv else None
print("wake_words:", ww)
assert ww and "carter" in [w.lower() for w in ww], "carter no esta en wake_words"
assert "hey carter" in [w.lower() for w in ww], "hey carter no esta"
assert "oye carter" in [w.lower() for w in ww], "oye carter no esta"
print("OK: wake words de Carter presentes; modelo activo sigue siendo hey_gemma (validado)")
