# Corrección exigida por el build

El primer build del candidato de72fe3a falló con CA1822 y CA1859 en el nuevo método privado Inventory: no usa estado de instancia y devuelve siempre List. Se cambia únicamente su firma a `private static List<InstalledApplicationObservation>`. La API pública y la conducta no cambian. Build original y shutdown se conservan en C:/Users/usuario/AppData/Local/BAXY/C03-repairs1064-build; salida de build 1 y shutdown 0. La repetición necesaria va en una carpeta nueva. No se ejecutaron suites ni Full.
