# Diagnóstico — el referente ausente se contesta como identidad propia

De los nueve fallos juzgados de 1025, tres son la misma causa: H0424, H0645 y la variante inglesa
del grupo `absent_referent` respondieron hablando de la identidad de BAXY en vez de preguntar de
quién se hablaba. El panel sellado exigía lo contrario: «sesión independiente sin antecedente debe
preguntar quién, no inventarlo».

Esto no es un defecto del modelo ni de la fluidez. **La ruta de aclaración por referente ausente
existe y no se alcanza.** Medido en `ed305c38`, sin GPU y sin modelo, ejecutando las funciones puras
con el intérprete del runtime de la mente:

```
'¿Cuál es su identidad secreta?'   _deictic_open_request = False   intents = []
'¿Quién es de verdad?'             _deictic_open_request = False   intents = []
'abrelo'                           _deictic_open_request = True    intents = []
'abre esto'                        _deictic_open_request = True    intents = []
```

## La primera transformación incorrecta

`src/baxy_mind/__main__.py:5831` calcula `missing_open_referent` y, cuando es cierto,
`__main__.py:5843` llama a `llm.clarify_missing_referent` y marca el camino de decisión
`deictic_referent_clarification`. El mecanismo ya está construido, ya tiene su contrato JSON en
`llm.py:8487` con validación de la pregunta, y ya funciona.

El último término de esa conjunción es `_deictic_open_request(objective)`, definido en
`__main__.py:2818`, y su docstring lo dice: *«Recognize an opening whose operand is a reference, not
a catalog name»*. Sólo reconoce **aperturas** —«ábrelo», «abre esto»—: si
`_application_open_request` no encuentra una petición de apertura, el único patrón alternativo que
acepta es `abre|abri` con clítico. Una **pregunta** en tercera persona sin antecedente no es una
apertura, así que devuelve `False`, `missing_open_referent` queda en `False`, y el turno sigue por la
ruta de conversación, donde el modelo hace lo único que puede hacer con «su» sin referente: suponer
que es él.

Lo que **no** es la causa, y conviene descartarlo por escrito: `nothing_to_clarify`
(`__main__.py:5825`) veta la aclaración cuando la lectura de la petición trae
`INTENT_CAPABILITY`, `INTENT_REFUSE` o `INTENT_CONTINUE_CONSTRAINT`. Para estos dos literales
`read_request(...).intents` sale **vacío**, luego ese veto no interviene. Tampoco intervienen
`content_drafting`, `explicit_non_action` ni el idioma. La ruta no se bloquea: no se llega.

## Reparación mínima que se propone, y por qué no se integra hoy

La forma más simple es ampliar el reconocedor de referente ausente para admitir una **pregunta**
cuyo referente en tercera persona no tiene antecedente, y encaminarla al mismo
`llm.clarify_missing_referent` que ya existe. Ni una capa nueva, ni un compositor nuevo, ni una
regla por literal, ni una respuesta fija: se reutiliza la ruta y su validación. Las guardas que ya
acompañan a `missing_open_referent` —sin aclaración pendiente, sin petición previa del usuario en el
historial, idioma objetivo, no redacción de contenido, no marco de no-acción— se conservan tal cual.

**No se integra sin medirla, y no es cautela decorativa: hay una ambigüedad real que puede romper
otra categoría.** En español «su» es a la vez tercera persona y tratamiento formal. «¿Cuál es su
identidad secreta?» pide un referente, pero «¿Cuál es su nombre?» dirigido a BAXY debe contestarse
con el nombre de BAXY. Una regla amplia sobre «su» convertiría respuestas correctas de identidad en
preguntas innecesarias, y la categoría «Identidad y capacidades del asistente» tiene 19 casos con 7
ya cubiertos: exactamente lo que no se puede perder por acelerar. Una aclaración innecesaria es un
fallo igual que una invención.

Por eso la tanda que mida esto necesita, además de los literales y sus pares:

- **Controles negativos de segunda persona:** «¿Quién eres?», «¿Cuál es tu nombre?» y su variante
  inglesa deben seguir contestándose como identidad de BAXY, sin preguntar referente.
- **Control negativo de tratamiento formal:** una pregunta con «su» que sí se dirige a BAXY.
- **Control positivo con antecedente:** la misma pregunta después de un turno que sí nombra a
  alguien debe responderse sobre ese alguien, no preguntar de nuevo.
- **Control de idioma:** la variante inglesa del referente ausente, que falló igual.

## Estado

Diagnóstico demostrado, reparación **no** escrita. Ningún fichero de `src/` modificado. El sellado
de esa tanda espera los literales exactos del registro privado
(`C03-survey-requirements336-private/requirements.jsonl`), que no está en este PC; ver
`OPUS5_DESTINO/SOLICITUD_TRASLADO.md`. Los literales de H0424 y H0645 usados en la sonda salen de
`KNOWLEDGE1025/PLAN.md`, que es panel sellado y versionado, no del registro.

Fila de matriz afectada: `G04.01` y `G03.08`/`G03C.09`, los tres ceros sobre población abierta.
Siguen CONTRADICHO; esto no las cambia, sólo nombra una de sus causas.
