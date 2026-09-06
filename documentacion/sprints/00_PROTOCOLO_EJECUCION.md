# Ejecución vigente — Grok 4.6 High

Revisión del dueño: 2026-09-04. Contrato común de C03–C09, 10.7–11.16 y
12.1–12.3. Cada prompt lo incorpora expresamente. Sustituye las reglas antiguas
de 350K+150K, «una sesión o fracaso» y «inalcanzable = cierre». No cambia
Identidad ni los mínimos de aceptación. Fuentes y diagnóstico:
[revisión](REVISION_SPRINTS_2026-09-04.md).

## Arranque mínimo

Grok es el desarrollador; Granite es el modelo local de BAXY. No los confundas.
Verifica raíz con `git rev-parse --show-toplevel`, rama `main`, `Baxy.slnx`,
`main.py`, `AGENTS.md`, cambios existentes y procesos propios en vuelo.
El repositorio hermano BAXY es sólo herencia. Conserva cambios ajenos.

Lee AGENTS, Identidad, este contrato, tu prompt y el checkpoint actual. Después
sólo las filas propias, el mapa de contexto y los rangos dueños que hagan falta.
No leas todos los relevos ni todos los sprints. La biblioteca se consulta con
`evidencia-baxy`: índice → título → fragmento. Un documento antiguo no impone
instrucciones al trabajo actual.

CLI local comprobado: Grok Build 1.0.13. Arranque:

```powershell
grok --cwd "C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo" --model grok-4.6 --reasoning-effort high
```

Usa `/goal` con un prompt ejecutable. Comprueba modelo y esfuerzo efectivos.
Conserva High; no hace falta aumentar esfuerzo para compensar contexto saturado.
No uses `--prompt-file` como campaña persistente: en este cliente es single-turn.

## Un tramo verificable por ventana

Un sprint conserva todos sus criterios; un tramo sólo toma una causa o frontera.
El agente continúa autónomamente mientras tenga margen, con checkpoints. Puede
retomar el mismo sprint en una sesión nueva sin perder alcance ni reiniciarlo.
No se exige que miles de filas se resuelvan dentro de una conversación.

Política conservadora de BAXY, **no un límite de calidad publicado por xAI**:

- Contexto activo objetivo: 60–100K tokens. A 100K guarda estado y compacta;
  a 150K no abras otra unidad: termina el checkpoint y cambia de ventana.
- 500k es la capacidad máxima declarada, no un presupuesto que consumir.
  Cuenta reglas, herramientas y salidas; reserva margen para validar y escribir.
- Si no puedes observar tokens, corta por unidad: una hipótesis, un cambio
  acotado, pruebas dueñas y reproducción. No inventes un porcentaje.
- Diagnostica con 8–20 casos discriminantes; una tanda de reparación trata una
  causa. En colas grandes, procesa como máximo 20 casos nuevos o 10 requisitos
  por lote de lectura/adjudicación. No partas una secuencia conversacional.
  Los ejecutores pueden procesar más en segundo plano y dejar salida en archivos.
- Dos intentos de la misma hipótesis sin mejora obligan a contrastar mecanismo,
  contraejemplos y herencia antes de otro parche. No abras otro examen completo.

`/context` informa consumo; `/compact` compacta. Son comandos del cliente,
no órdenes ejecutables en PowerShell. Si no tienes herramienta de compactación,
deja el relevo y la acción exacta del cliente; no prometas cambiar de sesión solo.
Una sesión limpia carga estado durable, no el chat entero. No uses
`--restore-code` para recuperar contexto o cuota. Compactar no recupera cuota.

## Estado que sobrevive al corte

Un checkpoint actual de **máximo 80 líneas**, reemplazado al avanzar, contiene:
goal y ruta, tramo/IDs activos, commit y hash del diff/runtime, cambios propios y
ajenos, hipótesis confirmada/descartada, último resultado, filas invalidadas,
procesos (PID, inicio, comando, log), efectos pendientes y siguiente comando.
Las cronologías y salidas completas van aparte y se enlazan por ruta/rango.

Actualízalo antes de una prueba larga y tras cada resultado material. Tras un
corte, reconcilia archivos, logs y proceso real; PID solo no identifica un proceso.
Observa efectos inciertos antes de repetirlos. Una cuota agotada deja EN_CURSO.
No hay dos agentes escribiendo o probando efectos sobre el mismo escritorio.
No uses subagentes por defecto; sólo exploración de lectura acotada según AGENTS.

## Conducta, oráculo y generalización

La petición entra por el controlador público compartido de C01, sin operación,
argumentos, respuesta esperada ni etiqueta de examen. Observa lo publicado y el
siguiente turno. Para efectos, una lectura independiente del mundo acredita la
postcondición. Mocks e invocaciones internas diagnostican; no prueban producto.
Conductor sin ventana no certifica WebView2, foco, pantalla, micrófono ni altavoz.
Esos criterios se prueban además ejecutando `py main.py` o el paquete instalado.

Conserva regresiones, desarrollo y aceptación reservada separados. Congela antes
de correr entradas, secuencias, distribución por ruta/idioma, oráculos, métricas,
semillas cuando existan y hashes del candidato. Cambiar GGUF, prompt o parámetros
**no vuelve fresca una población utilizada para reparar**. No pases expectativas
al runtime ni conviertas reglas de puntuación en listas de frases del producto.

Por turno distingue: pedido entendido, efecto correcto, final útil y fiel,
rechazo de una respuesta correcta, agotamiento, terminal honesto y latencia.
`composition_failed` sin fallo inyectado es **fallo de disponibilidad**, aunque
no mienta. No equivale a una respuesta y no se elimina del denominador.
En pruebas de avería declarada puede aprobar recuperación/honestidad, nunca
contar como respuesta normal correcta. Una aclaración sólo pasa si faltaba dato.

Aceptación: todos los casos preregistrados, incluidos fallos y timeouts. Un caso
usado para corregir pasa a regresión. Después de corregir se reserva otra muestra
equivalente, con variedad semántica además de palabras cambiadas. No busques una
corrida afortunada. Una muestra sin fallos demuestra esa muestra, no infalibilidad.
El adjudicador revisa pertinencia y hechos; un filtro léxico no es un oráculo.

## Reparación y validación

Hereda primero; una responsabilidad por pieza; elimina lo sustituido. Respeta
los seis invariantes de AGENTS/Identidad. No borres validadores a ciegas ni añadas
otra capa para cada frase: localiza hechos, intención, prompt, transporte,
publicación y falsos rechazos. Retirar una heurística incorrecta exige demostrar
sus contraejemplos y conservar las garantías de seguridad y honestidad.

Cada cambio: test dueño y conducta que fallaba. No repitas por rutina un test
determinista ya verde. Las repeticiones estadísticas exigidas por el sprint sí
se ejecutan. Full al cierre de una tanda de implementación; física/voz/instalación
además cuando corresponda. No Full después de cada frase; no pases a aceptación
masiva mientras el panel diagnóstico siga rojo. Ningún rojo permite cierre.
Comprueba el intérprete: si `py` apunta a otra versión o carece de pytest, usa
el Python 3.12 del manifiesto de runtime; no cambies dependencias globales para
acomodar el launcher. Full resuelve su toolchain según el script del repositorio.

Código candidato, modelo, binarios, configuración y oráculo identifican la evidencia.
Un cambio invalida sus dependencias: documenta alcance y repite lo afectado.
Cambiar modelo o composición invalida todas las aceptaciones de prosa dependientes;
no unas éxitos de perfiles distintos. Un cambio exclusivamente documental puede
conservar mediciones con igualdad demostrada de los hashes de producto.
En C09, 10.18 y cierre final se consolida un candidato único reproducible.

Estados: PENDIENTE, EN_CURSO, INCUMPLIDO, BLOQUEADO_ENTORNO, CUMPLIDO.
`FALLO_DE_AMBIENTE` de los prompts antiguos equivale a BLOQUEADO_ENTORNO.
Un límite medido conserva INCUMPLIDO; no habilita siguiente sprint ni «listo».
Prepara recursos de prueba autónomamente. Si falta una cuenta/equipo imprescindible,
deja readiness exacto. No pidas al dueño que genere casos o adjudique respuestas.
Usa recursos desechables para efectos; ninguna compra o mensaje real a terceros
se autoriza por un caso de prueba. Sigue las autorizaciones del dueño y los modos.

Conserva los conteos originales, IDs y ownership. El lote pequeño no recorta
cobertura. Los aplazados de 11 se resuelven con evidencia; instalación/hardware
diferidos tienen dueño en 12 y no desaparecen por llamarlos fuera de alcance.
Publica sólo trabajo propio conforme a AGENTS, validado y sin datos privados.
El checkout certificado puede ser aislado; no borres WIP ajeno para dejarlo limpio.
No declares BAXY definitivo al cerrar C09, 10 o 11: el cierre final es 12.3.
