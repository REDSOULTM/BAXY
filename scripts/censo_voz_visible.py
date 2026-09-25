# -*- coding: utf-8 -*-
"""Censo de prosa visible fija — la medida de partida del goal 06.

Cuenta los literales de prosa en español que pueden llegar a la pantalla sin
pasar por el modelo. El objetivo del goal 06 es llevar este número a cero por
sustitución: cada literal se reemplaza por prosa que formula el modelo a partir
de lo que la verificación observó.

Qué NO cuenta, y por qué:

- `llm.py` — es el prompt. La personalidad vive ahí por decisión del goal 06:
  «cambiar el carácter tiene que ser editar un texto». Un literal en el prompt
  es la solución, no el defecto.
- `router_bank_sources.py`, `public_turn_corpus.py`, `semantic/request.py`,
  `UserMessagePhrases.cs` — son textos de ENTRADA (anclas de embeddings, corpus
  de turnos, lectura del pedido y marcas de defecto de un borrador), nunca salen
  por pantalla.
- `*Parser*.cs` — parsers de la petición del usuario, mismo motivo.
- Los docstrings de Python, igual que los comentarios `#` y `//`: documentan
  el código y no se publican nunca.

Uso:  py -3.12 scripts/censo_voz_visible.py [salida.json]
"""
import ast
import io
import json
import os
import re
import sys

FRASE = re.compile(r'"((?:[^"\\]|\\.){12,400}?)"')
PALABRAS_ES = re.compile(
    u'(?i)\\b(no pude|no puedo|listo|estoy|momento|revisa|puedes|qué|cómo|'
    u'acción|petición|misión|hola|intentarlo|reformular|conserv|detuve|'
    u'encontré)\\b')
REGEXISH = re.compile(r'[\^\$\|\[\]]')

FICHEROS_DE_ENTRADA = ('/llm.py', '/router_bank_sources.py',
                       '/public_turn_corpus.py', '/semantic/request.py',
                       '/UserMessagePhrases.cs')


def lineas_de_docstring(txt):
    # Un docstring documenta el codigo; no llega a la pantalla, igual que un
    # comentario. Se leen del arbol y no por comillas al principio de linea,
    # para no confundir el cierre de un literal normal con la apertura de uno.
    try:
        arbol = ast.parse(txt)
    except SyntaxError:
        return set()
    lineas = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        cuerpo = getattr(nodo, 'body', None)
        if not cuerpo:
            continue
        primero = cuerpo[0]
        if (isinstance(primero, ast.Expr)
                and isinstance(primero.value, ast.Constant)
                and isinstance(primero.value.value, str)):
            lineas.update(range(primero.lineno, primero.end_lineno + 1))
    return lineas


def censar(raiz='src'):
    hits = []
    for root, dirs, files in os.walk(raiz):
        dirs[:] = [d for d in dirs
                   if d not in ('bin', 'obj', 'node_modules', '__pycache__', 'dist')]
        for fn in files:
            if not fn.endswith(('.cs', '.py')):
                continue
            p = os.path.join(root, fn).replace(os.sep, '/')
            if 'Parser' in fn or p.endswith(FICHEROS_DE_ENTRADA):
                continue
            try:
                txt = io.open(p, encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                continue
            documentadas = lineas_de_docstring(txt) if fn.endswith('.py') else set()
            for i, line in enumerate(txt.splitlines(), 1):
                if i in documentadas:
                    continue
                st = line.lstrip()
                if st.startswith(('//', '#', '///', '*')):
                    continue
                for m in FRASE.finditer(line):
                    s = m.group(1)
                    if s.count(' ') < 2 or not PALABRAS_ES.search(s) or REGEXISH.search(s):
                        continue
                    hits.append([p, i, s])
    return hits


def main():
    hits = censar()
    por_fichero = {}
    for p, i, s in hits:
        por_fichero.setdefault(p, []).append((i, s))

    print('prosa visible fija: %d literales en %d ficheros'
          % (len(hits), len(por_fichero)))
    print('')
    for p in sorted(por_fichero, key=lambda k: (-len(por_fichero[k]), k)):
        print('%4d  %s' % (len(por_fichero[p]), p))

    if len(sys.argv) > 1:
        io.open(sys.argv[1], 'w', encoding='utf-8').write(
            json.dumps(hits, ensure_ascii=False, indent=1))
        print('')
        print('detalle en %s' % sys.argv[1])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
