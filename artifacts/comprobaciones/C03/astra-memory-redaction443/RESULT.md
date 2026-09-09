# 443 — estado de ocultación tipado no mejora la respuesta

Tres casos protegidos/mixtos: 1/3 útil tanto baseline como variante. Inglés
describe correctamente el registro oculto; ES sigue negando acceso y la mezcla
se atribuye el color favorito a BAXY. Los siete controles conservan payload y
respuesta idénticos; dos nombres ES siguen incorrectos, no cuentan como verdes.
No adoptar fuente/proyección ni relajar la ocultación. Todos stop;13,328s,
GPU3175,5625MiB/RAM1208,7578125MiB, sin violaciones, registro intacto, cerrado.

444 cambia de familia reutilizando el GGUF Gemma publicado ya presente. Referencia
histórica astra-gemma-published midió otros nueve mensajes con prompt/historial de
entonces:4/9 bajo aquella adjudicación, nunca aceptación. No se borra ese rechazo.
El nuevo dato son once payloads de memoria actuales que fallan antes de guardas
con ambos tamaños de Qwen. No se descarga otra colección ni se cambian prompts.
La ficha oficial google/gemma-4-E2B-it, leída2026-09-08, documenta system nativo y
2,3B efectivos/5,1B con embeddings. No demuestra calidad ni consumo del GGUF
publicado por BAXY. Se reutilizan hash/revisión/perfil de astra-gemma-published;
no se incorpora adapter separado ni se presume equivalencia con el LoRA local.
https://huggingface.co/google/gemma-4-E2B-it
