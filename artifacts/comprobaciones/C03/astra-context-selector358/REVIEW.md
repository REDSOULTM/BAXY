# 358 — el recorte adicional pierde el referente personal

Mismo selector nativo y modeloQwen3.5, catálogo28, template/sampling, envoltorio y
petición35520. Cambia sólo últimos6 por historial ya acotado12mensajes/6000chars.
Baseline y reconstrucción de los seis últimos mensajes comprobados idénticos.

| Control | Últimos6 | Historial acotado |
|---|---|---|
| quien soy después de declarar Emmanuel | system.identity, incorrecto | Sin lectura, correcto |
| Cuenta de Windows explícita | system.identity | system.identity |
| quien soy fresco, criterio heredado | system.identity | system.identity |
| quién es BAXY | Sin lectura | Sin lectura |
| ambas identidades, variante sintética | system.identity, incorrecto | system.identity, incorrecto |
| Who am I tras Jordan | Sin lectura, texto niega saber | Sin lectura, texto reconoce Jordan |
| nombre de hermana Olivia | Sin lectura, texto niega saber | Sin lectura, texto recuerda Olivia |
| ventana activa solicitada | window.active | window.active |

Selección correcta6/8→7/8, sin regresión en el panel. La prosa del selector no
es la respuesta pública: Hola Emmanuel ante quien soy no prueba que la etapa
conversacional posterior dé una respuesta completa. La variante de ambas
identidades sigue fallando y requiere solución; no se excluye del alcance C03.
Todas las salidas literales están en replies.jsonl; payloads/huellas en PREREG.json
y archivo privado posts.jsonl. GPU3175,56MiB, RAM3315,59MiB,12,42s: nativo aislado,
sin voz/UI ni mínimo de recursos. Registro intacto, cero efectos ejecutados.

Decisión: retirar sólo el recorte redundante del selector nativo. El sanitizador
existente sigue limitando roles, número de mensajes y caracteres. No aumentar
límites, inventar recuerdos, cambiar roles/prompt ni introducir otra capa. Se
justifica por pérdida de información demostrada y mejora nativa; después de tests
dueños/Fast se debe verificar en producto. No promover el modelo por este panel.

Herencia y contraste: Carter_v2 LLM_CONTEXT_MEMORY_REPORT.md R1–R4 conserva origen
y evita contaminación de identidad. Experimentos316/317/65 mostraron que borrar
historia o cambiar roles no era una solución general. Investigación exacta de
Qwen3.5/template77/350 reutilizada; no se repite una búsqueda general.
