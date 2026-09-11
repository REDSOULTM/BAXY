# Foco841 y primer OCR real

Enfocar una ventana ya normal o maximizada conserva ahora su estado. Sólo una ventana minimizada recibe la petición de restauración antes del foco. Se mantiene la verificación posterior del provider.

La raíz revisó el parche completo y obtuvo **20 pruebas aprobadas, cero fallos y cero omisiones**, en48ms. Fast terminó con salida0 y build Release de13,06s;55 archivos sellados sin cambios. El rojo conductual del agente tenía7 fallos. [Recibos y límites](ROOT_RESULT.json).

El intento real no ejecutó foco: la nueva resolución encontró Taskmgr ya activo y el diagnóstico evitó una acción innecesaria. No se atribuye esa activación a841 ni se cambia el veredicto de834/840. El Full839 sigue siendo la base anterior; no se ejecutó Full841 ni se cierra C03.

La captura posterior porCore se completó con1530×948 píxeles y sin recorte físico. El runner falló después al buscar una captura en un informe previo que sólo contenía resolución; ese error privado se corrigió conservando el original y sin repetir la captura. La raíz revisó la imagen: la vista deProcesos corta nombres y unidades por su tamaño/scroll internos. `window.maximize` falló con `action_failed`; se pidió una vez al dueño que maximizara esa ventana. La consulta sigue pendiente.

Otra captura→OCR permitió localizar el siguiente bloqueo: el journal guardó una respuestaOCR verificada de6532 unidadesUTF-16, pero `ProtocolJson` la rechazó por su límite4096 yCore terminó70 antes de entregar la respuesta. El productor yApp ya admiten48000. Se prepara843 para unificar ese contrato; imágenes yOCR reales permanecen privados. [Evidencia842 y diagnóstico843](../REAL_OBSERVATION834/OBSERVATION842_RESULT.json).

Encuesta36 cubiertos/706 abiertos/0NA; H0675 yC03 abiertos. No hubo modelo, ganador, UI/voz ni petición original acreditados. El worktree841 fue retirado después de preservar sus dos archivos y comprobar su igualdad con el árbol canónico.
