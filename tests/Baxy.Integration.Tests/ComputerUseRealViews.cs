namespace Baxy.Integration.Tests;

/// <summary>
/// Views read live by the engine, copied from the mission journal of the test profile
/// (%LOCALAPPDATA%\BAXY\cu-universal-perfil\journal\missions.jsonl) as the provider returned them: the window, the
/// controls listed and the written text. Twins of the computer-use loop are judged on what the screen really showed.
/// </summary>
internal static class ComputerUseRealViews
{
    // Pasada v3 r9, v3-42 «en el panel de control anda a programas y caracteristicas y busca chrome» (2026-10-08).
    internal const string V342Check1 =
        "control:programas y caracteristicas:current|title:programas y caracteristicas|page:programas y caracteristicas"
        + "|mark:programas y caracteristicas";

    internal const string V342Check2 =
        "title:chrome&stepDone:input.key.press:enter|title:chrome&stepDone:input.visible.click:chrome"
        + "|stepDone:input.text.type&stepDone:input.key.press:enter&text:chrome";

    // Journal seq 494: after the click on the link «Programas» of the Control Panel's home. The page «Programas» lists
    // the link «Programas y características» alone on its row at the top left; that page was never opened.
    internal const string V342ProgramsPage = """
        {"window": {"title": "Programas", "process": "explorer", "requested": true, "foreground": false, "rect": {"x": 266, "y": 145, "w": 1408, "h": 742}, "coveredBy": {"title": "Configuración", "process": "WindowsTerminal"}, "focused": {"kind": "Hyperlink", "name": "Programas y características", "nameSource": "", "value": "", "i": 19}}, "controls": [
          {"i": 0, "kind": "Button", "name": "Atrás a Panel de control (Alt + Flecha izquierda)", "state": "", "rect": {"x": 272, "y": 195, "w": 44, "h": 41}, "zone": "TL", "color": "black"},
          {"i": 1, "kind": "Button", "name": "Ubicaciones recientes", "state": "", "rect": {"x": 360, "y": 195, "w": 26, "h": 41}, "zone": "TL", "color": "black"},
          {"i": 2, "kind": "Button", "name": "Subir a \"Panel de control\" (Alt + Flecha arriba)", "state": "", "rect": {"x": 393, "y": 195, "w": 41, "h": 41}, "zone": "TL", "color": "black"},
          {"i": 3, "kind": "SplitButton", "name": "Todas las ubicaciones", "state": "", "rect": {"x": 448, "y": 193, "w": 43, "h": 43}, "zone": "TL", "color": "black"},
          {"i": 4, "kind": "SplitButton", "name": "Panel de control", "state": "", "rect": {"x": 491, "y": 193, "w": 134, "h": 43}, "zone": "TL", "color": "black"},
          {"i": 5, "kind": "SplitButton", "name": "Programas", "state": "", "rect": {"x": 625, "y": 193, "w": 98, "h": 43}, "zone": "TL", "color": "black"},
          {"i": 6, "kind": "Button", "name": "Ubicaciones anteriores", "state": "", "rect": {"x": 1309, "y": 193, "w": 43, "h": 43}, "zone": "TR", "color": "black"},
          {"i": 7, "kind": "Button", "name": "Actualizar \"Programas\" (F5)", "state": "", "rect": {"x": 1352, "y": 193, "w": 43, "h": 43}, "zone": "TR", "color": "black"},
          {"i": 8, "kind": "Edit", "name": "Cuadro de búsqueda", "state": "", "value": "", "rect": {"x": 1414, "y": 205, "w": 198, "h": 20}, "zone": "TR", "color": "black"},
          {"i": 9, "kind": "Button", "name": "Buscar", "state": "readonly", "value": "", "rect": {"x": 1616, "y": 192, "w": 38, "h": 46}, "zone": "TR", "color": "black"},
          {"i": 10, "kind": "Hyperlink", "name": "Ventana principal del Panel de control", "state": "readonly", "value": "", "rect": {"x": 301, "y": 266, "w": 208, "h": 40}, "zone": "TL", "color": "white"},
          {"i": 11, "kind": "Hyperlink", "name": "Sistema y seguridad", "state": "readonly", "value": "", "rect": {"x": 301, "y": 325, "w": 137, "h": 20}, "zone": "TL", "color": "white"},
          {"i": 12, "kind": "Hyperlink", "name": "Redes e Internet", "state": "readonly", "value": "", "rect": {"x": 301, "y": 353, "w": 111, "h": 20}, "zone": "TL", "color": "white"},
          {"i": 13, "kind": "Hyperlink", "name": "Hardware y sonido", "state": "readonly", "value": "", "rect": {"x": 301, "y": 381, "w": 129, "h": 20}, "zone": "TL", "color": "white"},
          {"i": 14, "kind": "Hyperlink", "name": "Cuentas de usuario", "state": "readonly", "value": "", "rect": {"x": 301, "y": 437, "w": 129, "h": 20}, "zone": "L", "color": "white"},
          {"i": 15, "kind": "Hyperlink", "name": "Apariencia y personalización", "state": "readonly", "value": "", "rect": {"x": 301, "y": 465, "w": 194, "h": 20}, "zone": "L", "color": "white"},
          {"i": 16, "kind": "Hyperlink", "name": "Reloj y región", "state": "readonly", "value": "", "rect": {"x": 301, "y": 493, "w": 96, "h": 20}, "zone": "L", "color": "white"},
          {"i": 17, "kind": "Hyperlink", "name": "Accesibilidad", "state": "readonly", "value": "", "rect": {"x": 301, "y": 521, "w": 93, "h": 20}, "zone": "L", "color": "white"},
          {"i": 18, "kind": "Button", "name": "Icono", "state": "readonly", "value": "", "rect": {"x": 536, "y": 271, "w": 45, "h": 48}, "zone": "TL", "color": "white", "repeated": 1},
          {"i": 19, "kind": "Hyperlink", "name": "Programas y características", "state": "readonly focused", "value": "", "rect": {"x": 592, "y": 271, "w": 241, "h": 28}, "zone": "TL", "color": "white"}
        ], "text": {"TL": ["Programas", "> Panel de control > Programas >", "Ventana principal del Panel de", "Programas y características", "control", "Sistema y seguridad", "Ver actualizaciones instaladas", "Cómo instalar un programa", "Redes e Internet"], "T": ["Desinstalar un programa S Activar o desactivar las características de Windows", "Desinstalar un programa Activar o desactivar las características de Windows", "Ejecutar programas creados para versiones anteriores de Windows"], "TR": ["Buscar en el Panel de control", "p"], "L": ["Hardware y sonido", "Programas predeterminados", "•", "Cuentas de usuario", "Apariencia y personalización", "Reloj y región", "Accesibilidad"], "C": ["Cambiar la configuración predeterminada de medios o dispositivos"]}}
        """;

    // Journal seq 506: «chrome» typed into the page's search box and Enter pressed. The title repeated the query as soon
    // as it was typed («chrome - Programas», the typing step's own receipt) and the window says nothing matched.
    internal const string V342SearchedNothing = """
        {"window": {"title": "chrome - Programas", "process": "explorer", "requested": true, "foreground": true, "rect": {"x": 266, "y": 145, "w": 1408, "h": 742}, "focused": {"kind": "Edit", "name": "Cuadro de búsqueda", "nameSource": "", "value": "chrome", "i": 8}}, "controls": [
          {"i": 0, "kind": "Button", "name": "Atrás a Programas (Alt + Flecha izquierda)", "state": "", "rect": {"x": 272, "y": 195, "w": 44, "h": 41}, "zone": "TL", "color": "black"},
          {"i": 1, "kind": "Button", "name": "Ubicaciones recientes", "state": "", "rect": {"x": 360, "y": 195, "w": 26, "h": 41}, "zone": "TL", "color": "black"},
          {"i": 2, "kind": "Button", "name": "Subir a \"Panel de control\" (Alt + Flecha arriba)", "state": "", "rect": {"x": 393, "y": 195, "w": 41, "h": 41}, "zone": "TL", "color": "black"},
          {"i": 3, "kind": "SplitButton", "name": "Todas las ubicaciones", "state": "", "rect": {"x": 448, "y": 193, "w": 43, "h": 43}, "zone": "TL", "color": "black"},
          {"i": 4, "kind": "SplitButton", "name": "Panel de control", "state": "", "rect": {"x": 491, "y": 193, "w": 134, "h": 43}, "zone": "TL", "color": "black"},
          {"i": 5, "kind": "MenuItem", "name": "Programas", "state": "", "rect": {"x": 625, "y": 193, "w": 79, "h": 43}, "zone": "TL", "color": "black"},
          {"i": 6, "kind": "Button", "name": "Ubicaciones anteriores", "state": "", "rect": {"x": 1309, "y": 193, "w": 43, "h": 43}, "zone": "TR", "color": "black"},
          {"i": 7, "kind": "Button", "name": "Actualizar \"Programas\" (F5)", "state": "", "rect": {"x": 1352, "y": 193, "w": 43, "h": 43}, "zone": "TR", "color": "black"},
          {"i": 8, "kind": "Edit", "name": "Cuadro de búsqueda", "state": "focused", "value": "chrome", "rect": {"x": 1414, "y": 205, "w": 198, "h": 20}, "zone": "TR", "color": "black"},
          {"i": 9, "kind": "Button", "name": "Borrar", "state": "readonly", "value": "", "rect": {"x": 1616, "y": 196, "w": 38, "h": 38}, "zone": "TR", "color": "black"},
          {"i": 10, "kind": "Hyperlink", "name": "Ventana principal del Panel de control", "state": "readonly", "value": "", "rect": {"x": 301, "y": 266, "w": 208, "h": 40}, "zone": "TL", "color": "white"},
          {"i": 11, "kind": "Hyperlink", "name": "Sistema y seguridad", "state": "readonly", "value": "", "rect": {"x": 301, "y": 325, "w": 137, "h": 20}, "zone": "TL", "color": "white"},
          {"i": 12, "kind": "Hyperlink", "name": "Redes e Internet", "state": "readonly", "value": "", "rect": {"x": 301, "y": 353, "w": 111, "h": 20}, "zone": "TL", "color": "white"},
          {"i": 13, "kind": "Hyperlink", "name": "Hardware y sonido", "state": "readonly", "value": "", "rect": {"x": 301, "y": 381, "w": 129, "h": 20}, "zone": "TL", "color": "white"},
          {"i": 14, "kind": "Hyperlink", "name": "Programas", "state": "readonly", "value": "", "rect": {"x": 301, "y": 409, "w": 75, "h": 20}, "zone": "L", "color": "white"},
          {"i": 15, "kind": "Hyperlink", "name": "Cuentas de usuario", "state": "readonly", "value": "", "rect": {"x": 301, "y": 437, "w": 129, "h": 20}, "zone": "L", "color": "white"},
          {"i": 16, "kind": "Hyperlink", "name": "Apariencia y personalización", "state": "readonly", "value": "", "rect": {"x": 301, "y": 465, "w": 194, "h": 20}, "zone": "L", "color": "white"},
          {"i": 17, "kind": "Hyperlink", "name": "Reloj y región", "state": "readonly", "value": "", "rect": {"x": 301, "y": 493, "w": 96, "h": 20}, "zone": "L", "color": "white"},
          {"i": 18, "kind": "Hyperlink", "name": "Accesibilidad", "state": "readonly", "value": "", "rect": {"x": 301, "y": 521, "w": 93, "h": 20}, "zone": "L", "color": "white"},
          {"i": 19, "kind": "Hyperlink", "name": "Icono", "state": "readonly", "value": "", "rect": {"x": 536, "y": 329, "w": 20, "h": 20}, "zone": "TL", "color": "blue"}
        ], "text": {"TL": ["chrome - Pro ramas", "chrome - Programas", "> Panel de control > Programas", "Ventana principal del Panel de", "control", "Sistema y seguridad", "Redes e Internet"], "T": ["Ningún elemento coincide con el criterio de búsqueda.", "O Buscar \"chrome\" en Ayuda y soporte técnico de Windows"], "TR": ["chrome"], "L": ["Hardware y sonido", "Programas", "Cuentas de usuario", "Apariencia y personalización", "Reloj y región", "Accesibilidad"]}}
        """;

    // Ronda 23, live r21 v2-s01 «en la calculadora calculá 37*12» (2026-10-09): the sub-goal's planned check.
    internal const string V2S01Check =
        "stepDone:input.key.press:enter&result:37*12|stepDone:input.visible.click:igual&result:37*12"
        + "|stepDone:input.visible.click:=&result:37*12|stepDone:input.text.type:=&result:37*12";

    // Journal seq 2090: the look after «37*12» typed and Enter pressed (both receipts ok). The Enter evaluated nothing:
    // the expression reads «37 ×», the display «Se muestra 12» (the second operand typed), the history is empty and 444
    // shows nowhere. The model's «done» cited «Se muestra 12» and the sub-goal closed over the false «result:37*12».
    internal const string V2S01AfterEnter = """
        {"window": {"title": "Calculadora", "process": "CalculatorApp", "processId": 62108, "hwnd": 32510658, "requested": true, "root": 32510658, "foreground": true, "rect": {"x": 41, "y": 0, "w": 732, "h": 793}, "focused": {"kind": "Text", "name": "Se muestra 12", "nameSource": "", "value": null, "i": 39}}, "controls": [
          {"i": 0, "kind": "MenuItem", "name": "Sistema", "id": "42.11866826.4.65535", "state": "collapsed", "value": null, "rect": null, "zone": "", "color": "", "repeated": 1},
          {"i": 1, "kind": "Button", "name": "Minimizar Calculadora", "id": "42.11866826.4.1", "state": "", "value": null, "rect": {"x": 601, "y": 1, "w": 57, "h": 40}, "zone": "TR", "color": "black"},
          {"i": 2, "kind": "Button", "name": "Maximizar Calculadora", "id": "42.11866826.4.2", "state": "", "value": null, "rect": {"x": 658, "y": 1, "w": 57, "h": 40}, "zone": "TR", "color": "black"},
          {"i": 3, "kind": "Button", "name": "Cerrar Calculadora", "id": "42.11866826.4.3", "state": "", "value": null, "rect": {"x": 715, "y": 1, "w": 57, "h": 40}, "zone": "TR", "color": "black"},
          {"i": 4, "kind": "Button", "name": "Abrir navegación", "id": "42.12325176.4.4", "state": "", "value": null, "rect": {"x": 47, "y": 49, "w": 50, "h": 45}, "zone": "TL", "color": "black"},
          {"i": 5, "kind": "Button", "name": "Sumar memoria", "id": "42.12325176.4.14", "state": "", "value": null, "rect": {"x": 211, "y": 252, "w": 79, "h": 48}, "zone": "L", "color": "black"},
          {"i": 6, "kind": "Button", "name": "Restar la memoria", "id": "42.12325176.4.16", "state": "", "value": null, "rect": {"x": 293, "y": 252, "w": 79, "h": 48}, "zone": "C", "color": "black"},
          {"i": 7, "kind": "Button", "name": "Almacén de la memoria", "id": "42.12325176.4.18", "state": "", "value": null, "rect": {"x": 375, "y": 252, "w": 79, "h": 48}, "zone": "C", "color": "black"},
          {"i": 8, "kind": "Button", "name": "Por ciento", "id": "42.12325176.4.21", "state": "", "value": null, "rect": {"x": 47, "y": 303, "w": 101, "h": 79}, "zone": "L", "color": "black"},
          {"i": 9, "kind": "Button", "name": "Quitar entrada", "id": "42.12325176.4.23", "state": "", "value": null, "rect": {"x": 151, "y": 303, "w": 99, "h": 79}, "zone": "L", "color": "black"},
          {"i": 10, "kind": "Button", "name": "Borrar", "id": "42.12325176.4.25", "state": "", "value": null, "rect": {"x": 252, "y": 303, "w": 101, "h": 79}, "zone": "C", "color": "black"},
          {"i": 11, "kind": "Button", "name": "Retroceso", "id": "42.12325176.4.27", "state": "", "value": null, "rect": {"x": 355, "y": 303, "w": 99, "h": 79}, "zone": "C", "color": "black"},
          {"i": 12, "kind": "Button", "name": "Recíproco", "id": "42.12325176.4.30", "state": "", "value": null, "rect": {"x": 47, "y": 384, "w": 101, "h": 78}, "zone": "L", "color": "black"},
          {"i": 13, "kind": "Button", "name": "Cuadrado", "id": "42.12325176.4.32", "state": "", "value": null, "rect": {"x": 151, "y": 384, "w": 99, "h": 78}, "zone": "L", "color": "black"},
          {"i": 14, "kind": "Button", "name": "Raíz cuadrada", "id": "42.12325176.4.34", "state": "", "value": null, "rect": {"x": 252, "y": 384, "w": 101, "h": 78}, "zone": "C", "color": "black"},
          {"i": 15, "kind": "Button", "name": "Dividido por", "id": "42.12325176.4.37", "state": "", "value": null, "rect": {"x": 356, "y": 384, "w": 99, "h": 78}, "zone": "C", "color": "black"},
          {"i": 16, "kind": "Button", "name": "Multiplicar por", "id": "42.12325176.4.39", "state": "", "value": null, "rect": {"x": 356, "y": 465, "w": 99, "h": 79}, "zone": "C", "color": "black"},
          {"i": 17, "kind": "Button", "name": "Menos", "id": "42.12325176.4.41", "state": "", "value": null, "rect": {"x": 356, "y": 546, "w": 99, "h": 79}, "zone": "B", "color": "black"},
          {"i": 18, "kind": "Button", "name": "Más", "id": "42.12325176.4.43", "state": "", "value": null, "rect": {"x": 356, "y": 627, "w": 99, "h": 79}, "zone": "B", "color": "black"},
          {"i": 19, "kind": "Button", "name": "Es igual a", "id": "42.12325176.4.45", "state": "", "value": null, "rect": {"x": 356, "y": 708, "w": 99, "h": 79}, "zone": "B", "color": "blue"},
          {"i": 20, "kind": "Button", "name": "Cero", "id": "42.12325176.4.48", "state": "", "value": null, "rect": {"x": 149, "y": 708, "w": 101, "h": 79}, "zone": "BL", "color": "gray"},
          {"i": 21, "kind": "Button", "name": "Uno", "id": "42.12325176.4.50", "state": "", "value": null, "rect": {"x": 47, "y": 627, "w": 101, "h": 79}, "zone": "BL", "color": "gray"},
          {"i": 22, "kind": "Button", "name": "Dos", "id": "42.12325176.4.52", "state": "", "value": null, "rect": {"x": 149, "y": 627, "w": 101, "h": 79}, "zone": "BL", "color": "gray"},
          {"i": 23, "kind": "Button", "name": "Tres", "id": "42.12325176.4.54", "state": "", "value": null, "rect": {"x": 253, "y": 627, "w": 99, "h": 79}, "zone": "B", "color": "gray"},
          {"i": 24, "kind": "Button", "name": "Cuatro", "id": "42.12325176.4.56", "state": "", "value": null, "rect": {"x": 47, "y": 546, "w": 101, "h": 79}, "zone": "BL", "color": "gray"},
          {"i": 25, "kind": "Button", "name": "Cinco", "id": "42.12325176.4.58", "state": "", "value": null, "rect": {"x": 149, "y": 546, "w": 101, "h": 79}, "zone": "BL", "color": "gray"},
          {"i": 26, "kind": "Button", "name": "Seis", "id": "42.12325176.4.60", "state": "", "value": null, "rect": {"x": 253, "y": 546, "w": 99, "h": 79}, "zone": "B", "color": "gray"},
          {"i": 27, "kind": "Button", "name": "Siete", "id": "42.12325176.4.62", "state": "", "value": null, "rect": {"x": 47, "y": 465, "w": 101, "h": 79}, "zone": "L", "color": "gray"},
          {"i": 28, "kind": "Button", "name": "Ocho", "id": "42.12325176.4.64", "state": "", "value": null, "rect": {"x": 149, "y": 465, "w": 101, "h": 79}, "zone": "L", "color": "gray"},
          {"i": 29, "kind": "Button", "name": "Nueve", "id": "42.12325176.4.66", "state": "", "value": null, "rect": {"x": 253, "y": 465, "w": 99, "h": 79}, "zone": "C", "color": "gray"},
          {"i": 30, "kind": "Button", "name": "Separador decimal", "id": "42.12325176.4.68", "state": "", "value": null, "rect": {"x": 253, "y": 708, "w": 99, "h": 79}, "zone": "B", "color": "gray"},
          {"i": 31, "kind": "Button", "name": "Positivo negativo", "id": "42.12325176.4.71", "state": "", "value": null, "rect": {"x": 47, "y": 708, "w": 101, "h": 79}, "zone": "BL", "color": "gray"},
          {"i": 32, "kind": "TabItem", "name": "No hay historial todavía. Historial", "id": "42.12325176.4.73", "state": "selected", "value": null, "rect": {"x": 459, "y": 37, "w": 94, "h": 60}, "zone": "T", "color": "black"},
          {"i": 33, "kind": "TabItem", "name": "No hay nada guardado en la memoria. Memoria", "id": "42.12325176.4.74", "state": "", "value": null, "rect": {"x": 553, "y": 37, "w": 100, "h": 60}, "zone": "TR", "color": "black"},
          {"i": 34, "kind": "Button", "name": "Mantener visible", "id": "42.12325176.4.80", "state": "", "value": null, "rect": {"x": 212, "y": 51, "w": 40, "h": 40}, "zone": "TL", "color": "black"},
          {"i": 35, "kind": "Window", "name": "Calculadora", "id": "42.11866826", "state": "readonly", "value": "Calculadora", "rect": {"x": 539, "y": 1, "w": 233, "h": 40}, "zone": "TR", "color": "black", "repeated": 1},
          {"i": 36, "kind": "MenuBar", "name": "Sistema", "id": "42.11866826.4.0", "state": "", "value": null, "shortcut": "Alt+Space", "rect": null, "zone": "", "color": ""},
          {"i": 37, "kind": "Text", "name": "Calculadora", "id": "42.12325176.4.2", "state": "", "value": null, "rect": {"x": 102, "y": 11, "w": 80, "h": 20}, "zone": "TL", "color": "black"},
          {"i": 38, "kind": "Text", "name": "La expresión es 37 ×", "id": "42.12325176.4.5", "state": "", "value": null, "rect": {"x": 65, "y": 112, "w": 372, "h": 24}, "zone": "TL", "color": "black"},
          {"i": 39, "kind": "Text", "name": "Se muestra 12", "id": "42.12325176.4.8", "state": "focused", "value": null, "rect": {"x": 42, "y": 136, "w": 417, "h": 115}, "zone": "TL", "color": "black"},
          {"i": 40, "kind": "Group", "name": "Controles de la memoria", "id": "42.12325176.4.19", "state": "", "value": null, "rect": {"x": 47, "y": 252, "w": 407, "h": 48}, "zone": "L", "color": "black"},
          {"i": 41, "kind": "Group", "name": "Control de pantalla", "id": "42.12325176.4.28", "state": "", "value": null, "rect": {"x": 47, "y": 303, "w": 407, "h": 79}, "zone": "L", "color": "black"},
          {"i": 42, "kind": "Group", "name": "Funciones estándar", "id": "42.12325176.4.35", "state": "", "value": null, "rect": {"x": 47, "y": 384, "w": 306, "h": 78}, "zone": "L", "color": "black"},
          {"i": 43, "kind": "Group", "name": "Operadores estándar", "id": "42.12325176.4.46", "state": "", "value": null, "rect": {"x": 356, "y": 384, "w": 99, "h": 402}, "zone": "B", "color": "black"},
          {"i": 44, "kind": "Group", "name": "Teclado numérico", "id": "42.12325176.4.69", "state": "", "value": null, "rect": {"x": 47, "y": 465, "w": 306, "h": 322}, "zone": "BL", "color": "gray"},
          {"i": 45, "kind": "Group", "name": "Listas e historial de la memoria", "id": "42.12325176.4.76", "state": "", "value": null, "rect": {"x": 459, "y": 37, "w": 313, "h": 755}, "zone": "R", "color": "black"},
          {"i": 46, "kind": "Text", "name": "No hay historial todavía.", "id": "42.12325176.4.72", "state": "", "value": null, "rect": {"x": 474, "y": 120, "w": 267, "h": 672}, "zone": "R", "color": "black"},
          {"i": 47, "kind": "Text", "name": "Modo de calculadora Estándar", "id": "42.12325176.4.78", "state": "", "value": null, "rect": {"x": 102, "y": 52, "w": 98, "h": 34}, "zone": "TL", "color": "black"},
          {"i": 48, "kind": "TitleBar", "name": "Calculadora", "id": "4.32510658.0", "state": "", "value": null, "rect": {"x": 42, "y": 9, "w": 730, "h": 29}, "zone": "T", "color": "black"},
          {"i": 49, "kind": "MenuBar", "name": "Barra de menús del sistema", "id": "1.32510658.131909", "state": "", "value": null, "rect": {"x": 42, "y": 9, "w": 28, "h": 28}, "zone": "TL", "color": "black", "systemMenu": true}
        ], "text": {"TL": ["Calculadora", "Estándar"], "T": ["Historial", "37 x", "12"], "TR": ["Historial Memoria", "Memoria", "No hay historial todavía."], "L": ["MC", "MR", "CE"], "C": ["MS"]}}
        """;
}
