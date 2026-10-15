"""baxy-mind (BAXY Renew): la conexión mínima entre el catálogo de BAXY y el modelo local.

Llamadas nativas con herramientas deciden el turno y escriben sus argumentos; tras cada resultado que el Core y el
proveedor verificaron, el modelo vuelve a llamar o responde. La autoridad sigue fuera de aquí: el kernel autoriza, el
proveedor verifica.
"""
