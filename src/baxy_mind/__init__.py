"""baxy-mind (BAXY Renew): la conexión mínima entre el catálogo de BAXY y el modelo local.

Llamadas nativas con herramientas deciden el turno y escriben sus argumentos; tras cada resultado que el Core y el
proveedor verificaron, el modelo vuelve a llamar o responde. La autoridad sigue fuera de aquí: el kernel autoriza, el
proveedor verifica.
"""
import os

# uso-116: OpenBLAS reads these when numpy loads, and starts one thread with its committed buffer per core: 750 MB of
# commit on 24 cores (21 MB with one), and the PC of the owner's real use had 1 GB left when the voice died loading. They
# were set in voice.py after voice_echo had loaded numpy. The mind has no matrix worth a second thread.
for _variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")
