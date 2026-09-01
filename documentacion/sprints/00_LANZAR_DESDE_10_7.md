# Lanzador pendiente de BAXY — desde 10.7 hasta 11.16

Este es el mapa operativo para el dueño. **No se pega este mapa en Grok.** Abre
un solo enlace, copia el MD enlazado entero y envíalo en una sesión nueva de
**Grok 4.6 High** como una única entrada: `/goal ` seguido inmediatamente por el
contenido completo. No resumas, no reformules y no pegues un protocolo aparte.

Estado publicado al crear este mapa: 09.5, 10.0, 10.1, 10.2 y 10.2.5 están
cerrados. 10.3–10.6 fueron retirados por decisión del dueño y dicen `NO LANZAR`.
El siguiente goal real es **10.7**.

## Regla para avanzar

Lanza sólo un goal a la vez. Si aparece un defecto o falta un criterio, Grok lo
corrige y revalida **dentro del mismo `/goal`**; no pegues de nuevo el MD. Avanza
al enlace siguiente únicamente cuando el cierre demuestre todos sus checks, el
handoff esté actualizado, el commit esté publicado, `HEAD == origin/main` y el
árbol esté limpio. `FALLO_DE_AMBIENTE` conserva el cursor y pausa esa misma meta:
no es pass y no habilita el siguiente goal.

No hay turnos, entradas ni veredictos que deba proporcionar el dueño. Los agentes
generan las misiones por la entrada pública de BAXY y un oráculo independiente las
adjudica. Una llamada interna sirve para diagnosticar, no para acreditar E2E.

## Fase 10 — certificar antes del uso diario

1. **SIGUIENTE:** [10.7 — Conversación, aclaración y no-efecto](10.7_CONVERSACION.md)
2. [10.8 — Hechos locales](10.8_HECHOS_LOCALES.md)
3. [10.9 — Web y actualidad](10.9_WEB_Y_ACTUALIDAD.md)
4. [10.10 — Apps, ventanas y visión](10.10_APPS_VENTANAS_VISION.md)
5. [10.11 — Audio](10.11_AUDIO.md)
6. [10.12 — Media, streaming y juegos](10.12_MEDIA_STREAMING_JUEGOS.md)
7. [10.13 — Sistema y conectividad](10.13_SISTEMA_CONECTIVIDAD.md)
8. [10.14 — Productividad y memoria](10.14_PRODUCTIVIDAD_MEMORIA.md)
9. [10.15 — Comunicación y navegación](10.15_COMUNICACION_NAVEGACION.md)
10. [10.16 — Misiones compuestas](10.16_MISIONES_COMPUESTAS.md)
11. [10.17 — Identidad viva](10.17_IDENTIDAD_VIVA.md)
12. [10.18 — Certificación autónoma e integración](10.18_INTEGRACION.md)

10.18 cierra cuatro checkpoints internos A–D de 50 turnos frescos cada uno: 200
en total. Son checkpoints de una sola meta; no requieren cuatro sesiones ni que
el dueño vuelva a pegar el prompt.

## Fase 11 — validación y cierre

13. [11.1 — Congelar la cola de cierre](11.1_COLA_DE_CIERRE.md)
14. [11.2 — Contratos runtime](11.2_CONTRATOS_RUNTIME.md)
15. [11.3 — Requisitos A](11.3_REQUISITOS_A.md)
16. [11.4 — Requisitos B](11.4_REQUISITOS_B.md)
17. [11.5 — Requisitos C](11.5_REQUISITOS_C.md)
18. [11.6 — Requisitos D](11.6_REQUISITOS_D.md)
19. [11.7 — Requisitos E](11.7_REQUISITOS_E.md)
20. [11.8 — Requisitos F](11.8_REQUISITOS_F.md)
21. [11.9 — No-runtime A](11.9_NO_RUNTIME_A.md)
22. [11.10 — No-runtime B](11.10_NO_RUNTIME_B.md)
23. [11.11 — Errores de mente y kernel](11.11_ERRORES_MENTE_KERNEL.md)
24. [11.12 — Errores de providers y estado](11.12_ERRORES_PROVIDERS_ESTADO.md)
25. [11.13 — Regresión de Goals 01–06](11.13_REGRESION_01_06.md)
26. [11.14 — Regresión de Goals 07–10](11.14_REGRESION_07_10.md)
27. [11.15 — Higiene e identidad](11.15_HIGIENE_IDENTIDAD.md)
28. [11.16 — Full y cierre final](11.16_FULL_Y_CIERRE.md)

Cuando 11.16 cierre todos sus criterios, BAXY queda listo para uso diario dentro
del alcance vigente. No hay otra tanda humana ni un goal oculto después.

## Referencia — no se pega como goal

- [Orden histórico y trazabilidad desde 09.5](00_ORDEN_DESDE_09_5.md)
- [Decisión de replanificación autónoma](10_REPLANIFICACION_AUTONOMA.md)
- [Mapa del Goal 10](10_USO_DIARIO.md)
- [Protocolo 10.x para Grok 4.6](10_PROTOCOLO_GROK46.md)
- [Mapa del Goal 11](11_VALIDACION.md)
- [Protocolo 11.x para Grok 4.6](11_PROTOCOLO_GROK46.md)
