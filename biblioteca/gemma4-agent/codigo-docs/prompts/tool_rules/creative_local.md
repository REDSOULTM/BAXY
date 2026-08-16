Creative-local rule: creative_local(...) bridges to a local ComfyUI server (default http://127.0.0.1:8188) for image generation. Actions: status, submit, result, wait, queue, interrupt, models.

Returns needs_dependency when the ComfyUI server is not reachable — do not promise an image when this happens.

Distinct from web(...) (no image generation) and from media_edit(...) (post-processing of existing media). Use this only for local diffusion-style generation; do not invent an external API.
