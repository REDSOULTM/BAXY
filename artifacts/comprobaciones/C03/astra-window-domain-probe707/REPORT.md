# Diagnóstico de dominio de ventanas: número gramatical

Sonda técnica aislada de 60 textos sintéticos. No ejecuta operaciones ni llama a un modelo.

{"cases": 60, "positive": 40, "negative": 20, "baseline_correct": 28, "candidate_correct": 42, "gains": 15, "losses": 1, "remaining_false_vetoes": 17, "remaining_false_domains": 1}

| Caso | Texto | Dominio esperado | Antes | Propuesta |
|---|---|---|---|---|
| P01 | Enumera las ventanas. | True | False | True |
| P02 | Muéstrame las ventanas. | True | False | True |
| P03 | Lista mis ventanas. | True | False | True |
| P04 | Dime cuántas ventanas hay abiertas. | True | False | False |
| P05 | ¿Cuáles son las ventanas abiertas? | True | False | False |
| P06 | Las ventanas abiertas, muéstramelas. | True | False | False |
| P07 | Quiero ver todas las ventanas del escritorio. | True | False | False |
| P08 | Enséñame las ventanas que tengo abiertas. | True | False | False |
| P09 | ¿Qué ventanas están visibles ahora? | True | False | False |
| P10 | Cuenta las ventanas de mi PC. | True | False | False |
| P11 | Muestra las ventanas de Opera. | True | False | True |
| P12 | ¿Hay varias ventanas del navegador? | True | False | True |
| P13 | Lista las ventanas y luego dime la hora. | True | False | True |
| P14 | ¿Cuántas ventanas de la aplicación están abiertas? | True | True | True |
| P15 | Busca la ventana titulada "Atlas 42". | True | True | True |
| P16 | ¿Qué ventana está activa? | True | True | True |
| P17 | Muéstrame la ventana actual. | True | True | True |
| P18 | Lista las ventanas minimizadas. | True | False | False |
| P19 | Necesito los títulos de las ventanas abiertas. | True | False | False |
| P20 | Dime qué ventanas tengo en este escritorio. | True | False | False |
| P21 | List my windows. | True | False | True |
| P22 | Show all open windows. | True | False | True |
| P23 | Which windows are open? | True | False | False |
| P24 | How many windows are visible right now? | True | False | False |
| P25 | List the windows and then tell me the time. | True | False | True |
| P26 | Show the browser windows. | True | False | True |
| P27 | Find the window titled "Cedar 73". | True | True | True |
| P28 | Which window is active? | True | True | True |
| P29 | What are the titles of my open windows? | True | False | True |
| P30 | Show windows on this desktop. | True | False | False |
| P31 | Baxy, lista mis windows. | True | False | True |
| P32 | Muéstrame las open windows. | True | False | True |
| P33 | Which ventanas tengo abiertas? | True | False | False |
| P34 | Dime los titles de las ventanas abiertas. | True | False | False |
| P35 | Las windows del navegador, list them. | True | False | True |
| P36 | Show las ventanas del escritorio. | True | False | False |
| P37 | Cuenta mis ventanas, please. | True | False | False |
| P38 | List las ventanas y luego dime la hora. | True | False | True |
| P39 | Find la ventana titulada "Maple 19". | True | True | True |
| P40 | Qué window está active? | True | True | True |
| N01 | Explica cómo sellar las ventanas de la cocina. | False | False | False |
| N02 | Quiero pintar las ventanas de mi casa. | False | False | False |
| N03 | Enumera los tipos de ventanas de aluminio. | False | False | False |
| N04 | ¿Por qué las ventanas de doble vidrio aíslan mejor? | False | False | False |
| N05 | Cuenta las ventanas dibujadas en este plano arquitectónico. | False | False | False |
| N06 | ¿Qué significa una ventana de oportunidad? | False | False | False |
| N07 | Describe las ventanas de oportunidad para una empresa. | False | False | False |
| N08 | Explícame Windows 11, el sistema operativo. | False | False | False |
| N09 | ¿Cómo está la red neuronal? | False | False | False |
| N10 | Haz una captura del ladrón. | False | False | False |
| N11 | How do I clean the windows in my kitchen? | False | False | False |
| N12 | List the windows shown on this house floor plan. | False | False | False |
| N13 | What is a window of opportunity? | False | False | False |
| N14 | Explain the Windows operating system. | False | False | False |
| N15 | Why does glass fog up on house windows? | False | False | True |
| N16 | Quiero clean las ventanas de mi cocina. | False | False | False |
| N17 | Explain las ventanas de oportunidad en negocios. | False | False | False |
| N18 | Lista los tipos de house windows para construir. | False | False | False |
| N19 | Compare Windows 11 con Linux como sistemas operativos. | False | False | False |
| N20 | Show me window insulation techniques for my house. | False | False | False |

La fuente productiva no cambia. Esta sonda no acredita cobertura ni respuesta veraz del producto.

La hipótesis se rechaza como corrección completa: quedan17lecturas válidas bloqueadas y aparece una aceptación errónea para ventanas de una casa. Antes de modificar el producto hay que medir la recuperación semántica existente con sus tres controles; el verificador débil de identidad no autoriza ejecución.

Diagnóstico posterior708: window.resolve exige un proceso o título; no hay inventario global tipado. Los positivos de esta sonda indican dominio, no compatibilidad ejecutable. Antes de probar recuperación semántica de listados completos se necesita la lectura real; véase ../astra-window-inventory-gap708/REPORT.md.
