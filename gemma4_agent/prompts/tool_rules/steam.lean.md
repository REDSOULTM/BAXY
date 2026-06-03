Steam: use steam(...) for Steam tasks, NOT a web browser (unless user explicitly asks for the browser).

Map intent -> action:
- juego instalado -> steam(action="launch_game", query="<game>")
- "abre Steam y ve a mi biblioteca" -> steam(action="library") [NOT action="open"]
- "busca X en mi biblioteca de Steam" -> steam(action="search_library", query="X")
- página de tienda de un juego/app -> steam(action="store_page", query="X") o steam(action="search_store", query="X")

NUNCA partas "ponme en la pagina de la tienda de X" en store + preguntar; abrí la página destino directo en el cliente Steam cuando se pueda.
