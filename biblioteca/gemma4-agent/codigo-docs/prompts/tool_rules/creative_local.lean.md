creative_local(...) bridges to a local ComfyUI server (default http://127.0.0.1:8188) for image generation. Actions: status, submit, result, wait, queue, interrupt, models.

Returns needs_dependency when the ComfyUI server is unreachable -> do NOT promise an image then.

Distinct from: web(...) (no image gen); media_edit(...) (post-processing of existing media). Use ONLY for local diffusion-style generation; do NOT invent an external API.
