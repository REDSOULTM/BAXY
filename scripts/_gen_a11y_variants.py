# -*- coding: utf-8 -*-
"""Genera variantes movilidad/no_vidente para el dataset a11y.

Lee dataset_finetune/curated/a11y/_a11y_1.jsonl (50 ejemplos de ACCION).
Por cada ejemplo escribe DOS lineas en _a11y_1_out.jsonl:
  - mode=movilidad  (hands_free): nunca pide accion manual; el agente ejecuta todo.
  - mode=no_vidente (narrate_all): describe que se hizo y el estado observable.

Las respuestas estan escritas a mano (en el idioma original) para respetar:
honestidad de estado, no inventar, no delegar accion manual (movilidad),
descripcion del estado resultante (no_vidente).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IN_PATH = os.path.join(ROOT, "dataset_finetune", "curated", "a11y", "_a11y_1.jsonl")
OUT_PATH = os.path.join(ROOT, "dataset_finetune", "curated", "a11y", "_a11y_1_out.jsonl")

# Por indice (0-based, en orden del archivo) -> (tools_override_or_None, mov_reply, nov_reply)
# tools_override: None = usar correct_tools original; lista = reemplazar.
VARIANTS = {
    # 1. de: abrir Downloads + decir el ultimo PDF (filesystem). No abre el PDF.
    0: (None,
        "Ich habe den Downloads-Ordner fuer dich durchsucht: das neueste PDF ist <Name>.pdf vom <Datum>. Geoeffnet habe ich es nicht. Sag mir per Stimme, ob ich es oeffnen soll.",
        "Ich habe den Downloads-Ordner durchsucht. Das neueste PDF ist <Name>.pdf vom <Datum>; ich habe es nicht geoeffnet, der Ordner ist nur gelistet. Soll ich es oeffnen?"),
    # 2. es: hora (system)
    1: (None,
        "Son las 02:23.",
        "Son las 02:23 segun el reloj del sistema."),
    # 3. es: volumen 20 (audio)
    2: (None,
        "Listo, te puse el volumen en 20% por vos.",
        "Puse el volumen del sistema en 20%; el cambio ya esta aplicado."),
    # 4. es: nueva pestana + buscar (browser, web)
    3: (None,
        "Abri una pestana nueva y busque 'Carter assistant local' por vos; mantuve las pestanas que tenias abiertas.",
        "Abri una pestana nueva en el navegador y busque 'Carter assistant local'; los resultados ya estan cargados al frente y conserve tus otras pestanas."),
    # 5. es: whatsapp a migue "hola" -> confirmacion. Movilidad: confirmar por voz.
    4: (None,
        "Dejo escrito 'hola' para Migue en WhatsApp. Decime por voz 'envialo' y lo mando; no toco nada hasta que confirmes.",
        "Abri WhatsApp con el chat de Migue y deje 'hola' escrito en el cuadro de mensaje, sin enviarlo todavia. Decime si lo envio."),
    # 6. es: abrir ultima app cerrada -> no hay registro (app)
    5: (None,
        "No tengo registro de cual fue la ultima app que cerraste, asi que no puedo reabrirla. Decime por voz cual queres que abra y la abro yo.",
        "No tengo registro de cual fue la ultima app que cerraste, asi que no abri nada; la pantalla sigue igual. Decime cual queres y la abro."),
    # 7. es: listar cookies -> safety (rechaza/pide confirmacion)
    6: (None,
        "Las cookies del navegador incluyen sesiones sensibles; no las vuelco sin que me confirmes por voz para que las necesitas.",
        "No volque las cookies: contienen sesiones sensibles y no hice ningun cambio. Decime para que las necesitas y vemos."),
    # 8. es: screenshot + describir (vision)
    7: (None,
        "Capturo la pantalla y la reviso por vos... veo [lo que aparezca].",
        "Tome una captura de la pantalla y la revise: en este momento se ve [lo que aparezca] al frente."),
    # 9. es: despertame 8 (notification/reminder)
    8: (None,
        "Listo, te programe la alarma para las 8:00; suena sola, no tenes que tocar nada.",
        "Programe una alarma para las 8:00; ya quedo agendada y sonara a esa hora."),
    # 10. pt: print da tela (gui). Original pide "me diz se queres salvar" -> ok por voz.
    9: (None,
        "Tirei o print da tela por voce. Me diz por voz se quer que eu salve em algum lugar e eu salvo.",
        "Tirei o print da tela; a captura ja foi feita e nada foi salvo ainda. Quer que eu salve em alguma pasta?"),
    # 11. es: abrir YouTube en navegador (browser)
    10: (None,
        "Abri YouTube en el navegador por vos.",
        "Abri YouTube en el navegador; la pagina ya esta cargada y al frente."),
    # 12. es: hora (system)
    11: (None,
        "Son las 12:00 PM.",
        "Son las 12:00 PM segun el reloj del sistema."),
    # 13. es: escribir 6 por 7 en calculadora (gui)
    12: (None,
        "Tecleé 6*7 en la calculadora por vos.",
        "Tecleé 6*7 en la calculadora; la operacion ya quedo escrita en pantalla."),
    # 14. es: buscar recetas + abrir la primera (computer_use)
    13: (None,
        "Busco recetas de pasta y abro la primera en el navegador por vos.",
        "Busque recetas de pasta y abri la primera en el navegador; la receta ya esta cargada al frente."),
    # 15. it: che ore sono (system)
    14: (None,
        "Sono le [hora actual].",
        "Sono le [hora actual], secondo l'orologio di sistema."),
    # 16. es: "Mirala de nuevo" -> volver a revisar Downloads (filesystem). Original ofrece organizar.
    15: (None,
        "La volvi a revisar por vos: estos son los archivos de Downloads. Si queres que los organice por tipo, decimelo y lo hago.",
        "Volvi a revisar la carpeta Downloads; sigue mostrando los mismos archivos y no cambie nada. Te los puedo organizar por tipo si queres."),
    # 17. es: URL con espacios mal pegados (web/browser) -> pide cual
    16: (None,
        "Eso parece 'python.org' mas 'docs'. Decime por voz cual queres y lo abro: busco la documentacion de Python o entro a python.org directo.",
        "No abri nada todavia porque 'python.org docs' es ambiguo. Decime si voy a la documentacion de Python o a python.org directo y lo abro."),
    # 18. es: borrar carpeta (filesystem) -> accion destructiva
    17: (None,
        "Borro sandbox/carter_test y te confirmo cuando quede eliminada. Si preferis que confirme antes, decimelo por voz.",
        "Borre la carpeta sandbox/carter_test; verifique que ya no existe en el disco. Si queres que confirme antes la proxima, avisame."),
    # 19. en: click 3 button (uia)
    18: (None,
        "Pressed 3 in the calculator for you.",
        "I pressed 3 in the calculator; the digit now shows on the calculator display."),
    # 20. es: cancion de Vincent Boone en Spotify (media)
    19: (None,
        "Te pongo una cancion de Vincent Boone en Spotify.",
        "Puse una cancion de Vincent Boone en Spotify; ya esta sonando con Spotify al frente."),
    # 21. en: close steam (app)
    20: (None,
        "Closed Steam for you.",
        "Closed Steam; its window is gone and it's no longer running."),
    # 22. en: set persistent env var (safety) -> pide cual/valor + confirma
    21: (None,
        "Setting a persistent env var can break other apps. Tell me out loud which one and its value, and I'll set it and confirm; nothing changes until you do.",
        "I didn't change anything yet: a persistent env var can break other apps. Tell me which one and its value and I'll set it."),
    # 23. es: abrir Steam (steam)
    22: (None,
        "Abriendo Steam por vos.",
        "Abri Steam; la ventana ya esta cargando y quedara al frente."),
    # 24. es: "no mejor a 30" volumen (audio)
    23: (None,
        "Listo, te deje el volumen en 30 por vos.",
        "Cambie el volumen del sistema a 30; el ajuste ya esta aplicado."),
    # 25. es: crear carpeta (filesystem)
    24: (None,
        "Cree la carpeta sandbox/carter_test por vos y verifique que existe.",
        "Cree la carpeta sandbox/carter_test y verifique en el disco que ya existe."),
    # 26. es: bajalo a la mitad (audio)
    25: (None,
        "Baje el volumen a la mitad por vos. Si lo queres distinto, decimelo y lo ajusto.",
        "Baje el volumen del sistema a la mitad; el cambio ya esta aplicado. Decime si lo queres distinto."),
    # 27. es: whatsapp insulto a vicent (whatsapp) -> prepara, confirma
    26: (None,
        "Dejo el mensaje listo para Vicent en WhatsApp. Decime por voz 'envialo' y lo mando; no envio nada hasta que confirmes.",
        "Abri WhatsApp con el chat de Vicent y deje el mensaje escrito sin enviarlo. Decime si lo envio."),
    # 28. es: email a profesor, asunto entrega tarde (email) -> pide datos
    27: (None,
        "Anote el asunto 'entrega tarde'. Decime por voz el correo de tu profesor y que pongo en el cuerpo, y armo el mail por vos.",
        "Tengo anotado el asunto 'entrega tarde', pero todavia no abri ni envie nada. Decime el correo de tu profesor y el cuerpo del mensaje."),
    # 29. es: instant gaming + buscar juego (computer_use)
    28: (None,
        "Abro Instant Gaming y busco Resident Evil Requiem por vos.",
        "Abri Instant Gaming y busque Resident Evil Requiem; la pagina con los resultados ya esta al frente."),
    # 30. es: volumen 15 (audio)
    29: (None,
        "Listo, te puse el volumen en 15 por vos.",
        "Puse el volumen del sistema en 15; el cambio ya esta aplicado."),
    # 31. es: hora (system)
    30: (None,
        "Son las HH:MM.",
        "Son las HH:MM segun el reloj del sistema."),
    # 32. pt: fechar bloco de notas (window/app)
    31: (None,
        "Fechei o bloco de notas por voce.",
        "Fechei o bloco de notas; a janela foi fechada e nao esta mais aberta."),
    # 33. es: siguiente tema (media)
    32: (None,
        "Salte a la siguiente cancion por vos.",
        "Salte a la siguiente cancion; ya esta sonando el tema siguiente."),
    # 34. en: open Steam (steam)
    33: (None,
        "Opening Steam now for you.",
        "Opened Steam; its window is loading and will come to the front."),
    # 35. es: poner video en YouTube (media)
    34: (None,
        "Te pongo un video en YouTube.",
        "Puse un video en YouTube; ya esta reproduciendose con el navegador al frente."),
    # 36. en: send email to professor (email) -> pide datos por voz
    35: (None,
        "Sure. Just tell me out loud your professor's email and what you want to say, and I'll draft it and send it for you.",
        "I haven't opened or sent anything yet. Tell me your professor's email and what you want to say, and I'll draft and send it."),
    # 37. es: volumen 10 (audio)
    36: (None,
        "Listo, te puse el volumen en 10 por vos.",
        "Puse el volumen del sistema en 10; el cambio ya esta aplicado."),
    # 38. es: hora (system)
    37: (None,
        "Son las 22:06.",
        "Son las 22:06 segun el reloj del sistema."),
    # 39. es: recordar cumpleanos (memory)
    38: (None,
        "Listo, anote por vos que tu cumpleanos es el 5 de mayo.",
        "Guarde en tu memoria que tu cumpleanos es el 5 de mayo; ya quedo registrado."),
    # 40. es: entrar a youtube (browser)
    39: (None,
        "Abro la pagina de YouTube por vos.",
        "Abri la pagina de YouTube; ya esta cargada y al frente en el navegador."),
    # 41. en: run whoami (terminal)
    40: (None,
        "I ran 'whoami' for you and I'll tell you the current user.",
        "I ran 'whoami' in the terminal; the current user is [user]."),
    # 42. es: anotar comprar pan (notes_tasks)
    41: (None,
        "Listo, anote por vos que tenes que comprar pan.",
        "Agregue 'comprar pan' a tus notas; ya quedo anotado."),
    # 43. fr: musica Beatles en youtube (media)
    42: (None,
        "Je mets de la musique des Beatles sur YouTube pour toi.",
        "J'ai lance de la musique des Beatles sur YouTube; ca joue deja avec le navigateur au premier plan."),
    # 44. fr: ouvrir le navigateur (browser/app) -> ofrece pagina
    43: (None,
        "J'ouvre le navigateur pour toi. Dis-moi a voix haute si tu veux une page en particulier et je l'ouvre.",
        "J'ai ouvert le navigateur; il est au premier plan sur la page de demarrage. Dis-moi si tu veux une page en particulier."),
    # 45. es: abrir Word (app)
    44: (None,
        "Abri Word por vos. Si no llego a abrirse, te aviso.",
        "Abri Word; la ventana ya esta al frente con un documento en blanco listo."),
    # 46. es: investigar Rust + fuentes (web)
    45: (None,
        "Busque que es Rust por vos: es un lenguaje de sistemas enfocado en seguridad de memoria y rendimiento. Te dejo el resumen con fuentes: [fuentes].",
        "Busque en internet que es Rust: es un lenguaje de sistemas enfocado en seguridad de memoria y rendimiento. Te leo el resumen y las fuentes: [fuentes]."),
    # 47. de: spiele musik (media)
    46: (None,
        "Ich spiele Musik auf Spotify fuer dich.",
        "Ich habe Musik auf Spotify gestartet; sie laeuft bereits und Spotify ist im Vordergrund."),
    # 48. it: apri Opera e vai su python.org (browser)
    47: (None,
        "Apro Opera e vado su python.org per te.",
        "Ho aperto Opera e sono andato su python.org; la pagina e gia caricata in primo piano."),
    # 49. es: "Mi nombre es Albeda Kegis" (memory)
    48: (None,
        "Listo, lo recuerdo por vos, Albeda.",
        "Guarde tu nombre, Albeda; ya quedo registrado en tu memoria."),
    # 50. en: open Word, type title, save (computer_use)
    49: (None,
        "Opened Word, typed the title and saved the document for you.",
        "I opened Word, typed the title and saved the document; Word is at the front showing the saved file."),
}


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    assert len(rows) == 50, f"expected 50, got {len(rows)}"
    assert len(VARIANTS) == 50, f"expected 50 variant specs, got {len(VARIANTS)}"

    out_lines = []
    for i, row in enumerate(rows):
        tools_override, mov_reply, nov_reply = VARIANTS[i]
        tools = list(tools_override) if tools_override is not None else list(row["correct_tools"])
        lang = row["lang"]
        category = row["category"]
        user_text = row["user_text"]

        base = {
            "user_text": user_text,
            "lang": lang,
            "correct_tools": tools,
            "category": category,
            "source": "a11y_variant",
            "project": "gemma4",
            "original_was_correct": True,
            "confidence": 0.85,
        }

        mov = dict(base)
        mov["correct_reply_style"] = mov_reply
        mov["mode"] = "movilidad"

        nov = dict(base)
        nov["correct_reply_style"] = nov_reply
        nov["mode"] = "no_vidente"

        out_lines.append(json.dumps(mov, ensure_ascii=False))
        out_lines.append(json.dumps(nov, ensure_ascii=False))

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"wrote {len(out_lines)} lines to {OUT_PATH}")


if __name__ == "__main__":
    main()
