from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-start159.py').read_text(encoding='utf-8').replace('159','160')
source=source.replace("        ready=engine.start('wake')", "        assert engine.speak('¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?')\n        ready=engine.start('wake')")
source=source.replace('No playback/volume mutation/App/LLM/Core or transcript routing.', 'Queue actual greeting then immediately start wake, matching App ordering. No volume mutation/App/LLM/Core or transcript routing; endpoint remains at its original muted state.')
exec(compile(source,str(__file__),'exec'))
