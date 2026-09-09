# Revisión posterior de llama.cpp

La publicación estable sigue siendo[v0.4.0/b10809](https://github.com/ggml-org/llama.cpp/releases/tag/v0.4.0). Apareció[b10867](https://github.com/ggml-org/llama.cpp/releases/tag/b10867) después de la b10865 ya evaluada.

El[delta exacto](https://github.com/ggml-org/llama.cpp/compare/d4389a4dd920d24c9592f1dc3badbd69be23bd09...f3f1a8f2760f28325a5ec20c05b171e5b7c83a29) sólo contiene dos cambios: una condición de compilador en ARM NEON, y desactivar carga diferida AUTO cuando algún dispositivo seleccionado no admite mmap. La fuente CUDA del mismo commit anuncia mmap para dispositivos distintos de IGPU. La RTX3060Laptop usada aquí es discreta y la compilación es x64; además la rama nueva no cambia lazy ON explícito.

Por inspección del código, esos cambios no deberían alterar los perfiles CUDA observados. Esto no es una medición de b10867 ni una afirmación sobre otros dispositivos. No hay una causa nueva para descargar y repetir toda la batería en esta máquina; registro, binarios y modelos permanecen intactos. Si se elige una iGPU u otro backend sin mmap, esta revisión sí será pertinente.
