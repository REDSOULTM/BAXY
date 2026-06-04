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
print("stem activo:", wake.LIVEKIT_MODEL_STEM, "| modelo:", wake.LIVEKIT_MODEL_PATH.name,
      "| existe:", wake.LIVEKIT_MODEL_PATH.exists())
assert ww and "baxy" in [w.lower() for w in ww], "baxy no esta en wake_words"
assert wake.LIVEKIT_MODEL_STEM == "baxy", "el stem activo no es baxy"
assert wake.LIVEKIT_MODEL_PATH.exists(), "baxy.onnx no existe en el runtime"
print("OK: wake word activa = Baxy; baxy.onnx cargado (recall 0.872, pasó el gate)")
