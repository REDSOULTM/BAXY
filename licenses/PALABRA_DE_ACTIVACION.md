# Palabra de activación de BAXY: con qué se entrenó y bajo qué licencia va

El detector de «Baxy» (carpeta `wake`) es una red propia. Aprendió de los datos y los modelos de abajo; lo que se midió de su parecido con el codificador de Kroko está en el aviso. Se declara todo, también lo que tiene condiciones. Revisado el 2026-11-07 a partir de los registros de
entrenamiento y de las fichas de cada fuente; **no es asesoría legal**.

## Licencia del detector

El detector se publica bajo **[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)** por prudencia: imitó el
codificador de Kroko, que se declara CC BY-SA, y no está resuelto si imitarlo lo hace una adaptación (BAXY lo considera obra
propia: ver el aviso). BAXY licencia bajo CC BY-SA 4.0 los derechos que tenga sobre el modelo que entrenó, y no puede conceder derechos que pertenezcan a terceros sobre los datos y modelos de los que aprendió. En lo que BAXY puede conceder, puedes usarlo, copiarlo, modificarlo y redistribuirlo, siempre que des el crédito de esta página
y compartas lo que derives de él bajo la misma licencia. Ninguna otra condición de BAXY lo restringe. BAXY lo distribuye de forma oficial, también en las versiones que se venden (decisión de su titular, 2026-11-08).

## Aviso

- El detector no se entrenó con grabaciones de L2-ARCTIC: el 2,3 % de
  sus ejemplos de entrenamiento es audio sintético generado con una voz Piper de terceros (en_US-l2arctic-medium) que sí se
  entrenó con L2-ARCTIC (CC BY-NC 4.0, Texas A&M University e Iowa State University), una herencia indirecta, que se atribuye.
- Ocho voces Piper usadas (en_US-libritts_r-medium, en_GB-vctk-medium, en_US-l2arctic-medium, es_ES-sharvard-medium, en_US-arctic-medium, es_ES-davefx-medium, es_AR-daniela-high y pt_BR-faber-medium) se ajustaron a partir de la voz Piper lessac, y es_MX-ald-medium a partir de es_ES-davefx-medium; lessac se entrenó con datos Blizzard 2013 (Lessac Technologies y Voice Factory) cuya licencia es sólo para investigación. Esas nueve voces son el 50,1 % de sus 59.363 ejemplos de entrenamiento (48,96 % directo y 1,14 % a través de es_MX-ald-medium); v7a no se entrenó con esas grabaciones (herencia indirecta, como L2-ARCTIC). El 2026-11-08 se escribió a CSTR para que pase la petición de permiso a Lessac Technologies y Voice Factory, sus titulares. El 0,89 % de sus ejemplos (531) es audio sintético de las voces Piper es_ES-mls_10246-low y es_ES-mls_9972-low, ajustadas a partir de la voz Piper en_US-ryan-low, que se entrenó con RyanSpeech (Universidad de Denver), de licencia no comercial (CC BY-NC-SA 4.0 según la ficha de esa voz; el artículo de sus autores dice CC BY-NC-ND); v7a no se entrenó con esas grabaciones (herencia indirecta, que se atribuye), y BAXY no puede conceder los derechos de los titulares de RyanSpeech.
- Aprendió a imitar el codificador en español de Kroko ASR (Banafo), y se atribuye a Kroko; lo medido, el 2026-11-07, es que ninguno de sus 127 tensores de 64 valores o más es idéntico a uno de ese codificador (comparación exacta; los tensores más pequeños no se compararon). Kroko distingue modelos comunitarios (CC BY-SA) y comerciales (OEM); qué licencia tiene el codificador que
  se imitó no está confirmado.
- También aprendió de otras voces sintéticas (Piper y Chatterbox), cada una con su licencia y su crédito en la tabla de abajo, y de grabaciones del desarrollador y de amigos suyos, usadas con su permiso dado de palabra; el permiso por escrito está pendiente.
- Los detectores anteriores que llevaban Kroko o audio de una serie de televisión (k4, k5 y v3b2) ya no se distribuyen.
- BAXY considera el detector una obra propia, distinta de esos datos y modelos; esta interpretación no la ha revisado un abogado.

## Con qué se entrenó

| Fuente | Para qué | Licencia | Fuente de la licencia |
|---|---|---|---|
| Kroko ASR (codificador en español, comunitario) | El detector imitó su codificador; ninguno de sus tensores de 64 valores o más es idéntico a uno de ese codificador | CC BY-SA | [huggingface.co/Banafo/Kroko-ASR](https://huggingface.co/Banafo/Kroko-ASR) |
| YODAS2 | Habla de fondo | CC BY 3.0 | [huggingface.co/datasets/espnet/yodas2](https://huggingface.co/datasets/espnet/yodas2) |
| LibriSpeech | Habla de fondo | CC BY 4.0 | [openslr.org/12](https://www.openslr.org/12) |
| MUSAN | Música y ruido | Dominio público y CC según el fichero | [arXiv:1510.08484](https://arxiv.org/abs/1510.08484) |
| Corpus latinoamericanos de OpenSLR | Habla de fondo | CC BY-SA 4.0 | openslr.org (por confirmar) |
| Chatterbox | Ejemplos sintéticos de «Baxy» | MIT | [github.com/resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) (por confirmar) |
| Voces Piper (ejemplos sintéticos) | Ejemplos sintéticos de «Baxy» | Según cada voz: Apache-2.0, CC0, dominio público, Unlicense, CC BY 3.0 y 4.0, CC BY-SA 4.0; las 8 que se ajustaron desde `lessac` y `es_MX-ald-medium`, que se ajustó desde `es_ES-davefx-medium` (ver el aviso), heredan además sus datos Blizzard 2013, de sólo investigación (50,1 % de los ejemplos); las 2 `es_ES-mls_*-low` heredan RyanSpeech, no comercial (0,89 %) | Fichas `MODEL_CARD` de [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) |
| Voz Piper `en_US-l2arctic-medium` | 1.346 ejemplos sintéticos (2,3 %) | **CC BY-NC 4.0** (corpus L2-ARCTIC, Texas A&M e Iowa State) | [psi.engr.tamu.edu/l2-arctic-corpus](https://psi.engr.tamu.edu/l2-arctic-corpus/) |
| Voz Piper `en_US-arctic-medium` | Ejemplos sintéticos | Remite a otra licencia; se ajustó desde `lessac` (Blizzard 2013, sólo investigación) | Su `MODEL_CARD` |
| Voces Piper `es_ES-mls_10246-low` y `es_ES-mls_9972-low` | 531 ejemplos sintéticos (0,89 %) | Sus datos, CC BY 4.0 (MLS de OpenSLR); se ajustaron desde `en_US-ryan-low`, entrenada con RyanSpeech (Universidad de Denver), de licencia no comercial: CC BY-NC-SA 4.0 según la ficha de esa voz, CC BY-NC-ND según el artículo de sus autores | Sus `MODEL_CARD`; [arXiv:2106.08468](https://arxiv.org/abs/2106.08468) |
| Voz Piper `es_MX-claude-high` | 1.133 ejemplos sintéticos (1,91 %) | Apache-2.0 según su ficha; de dónde viene, desconocido: su ficha sólo dice «See URL above» (un Space de HirCoir en Hugging Face) | Su `MODEL_CARD` |
| Voz Piper `riccardo` | Ejemplos sintéticos | Entrenada desde cero; licencia de M-AILABS sin leer | Su `MODEL_CARD` |
| Grabaciones del desarrollador y de amigos suyos | Ejemplos reales de «Baxy» | Con su permiso, dado de palabra; por escrito, pendiente | — |

## Otras notas

- **L2-ARCTIC y Kroko:** el 2026-11-07 se escribió a los autores de L2-ARCTIC y a Banafo; sin respuesta todavía. Si responden,
  este documento se actualiza.
- **La serie de televisión:** el detector de BAXY es `v7_a`, que no aprendió de ella. El anterior, `k6r-v7b`, sí la usó a
  través de un modelo maestro, y eso no se cubre con créditos.

## Créditos

Kroko ASR, de Banafo. YODAS2, de ESPnet. LibriSpeech, de Vassil Panayotov, Guoguo Chen, Daniel Povey y Sanjeev Khudanpur.
MUSAN, de David Snyder, Guoguo Chen y Daniel Povey. L2-ARCTIC, de Texas A&M University e Iowa State University. Datos
Blizzard 2013, de Lessac Technologies y Voice Factory (a través de la voz Piper lessac). RyanSpeech, de Rohola Zandie,
Mohammad H. Mahoor, Julia Madsen y Eshrat S. Emamian, Universidad de Denver (a través de la voz Piper ryan). Voces de Piper, de sus autores
según cada ficha de rhasspy/piper-voices. Chatterbox, de Resemble AI.
