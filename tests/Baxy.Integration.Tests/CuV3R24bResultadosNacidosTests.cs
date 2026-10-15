using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24b, palanca «resultados de búsqueda son lo nacido tras buscar» (banco r23, v1 falso éxito): a search's proof
/// counts only the places born after the search started (the look the typing of the query was decided on, recorded
/// as <c>viewBeforeTyping</c>). Measured on the journal of v2-v1: the home page's banner bearing the query kept its
/// runtime ids and rect before the typing (seq 5738) and after the Enter that never reached the box (seq 5746), and
/// passed for the search's results. Counter-cases: a results page with new ids, a filter in place (read by OCR or a
/// list that narrows), a title the search changed.
/// </summary>
[TestFixture]
public sealed class CuV3R24bResultadosNacidosTests
{
    private const string Check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:Spotify";

    // The real look the typing was decided on (journal seq 5738: the box opened with its history, the home page).
    private const string BeforeTyping = """
        {"window": {"title": "Microsoft Store", "process": "WinStore.App", "foreground": false, "rect": {"x": 0, "y": 0, "w": 1920, "h": 1020}, "focused": null},
         "controls": [
          {"i": 0, "kind": "ListItem", "name": "Spotify. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.359", "state": "", "rect": {"x": 595, "y": 52, "w": 731, "h": 73}, "zone": "T"},
          {"i": 1, "kind": "ListItem", "name": "WhatsApp. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.363", "state": "", "rect": {"x": 595, "y": 124, "w": 731, "h": 74}, "zone": "T"},
          {"i": 2, "kind": "ListItem", "name": "speedtest. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.367", "state": "", "rect": {"x": 595, "y": 197, "w": 731, "h": 73}, "zone": "T"},
          {"i": 3, "kind": "ListItem", "name": "geforce now. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.371", "state": "", "rect": {"x": 595, "y": 269, "w": 731, "h": 74}, "zone": "T"},
          {"i": 4, "kind": "ListItem", "name": "ubuntu. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.375", "state": "", "rect": {"x": 595, "y": 342, "w": 731, "h": 74}, "zone": "C"},
          {"i": 5, "kind": "MenuItem", "name": "Sistema", "id": "42.2689890.4.65535", "state": "collapsed", "zone": ""},
          {"i": 6, "kind": "Button", "name": "Minimizar Microsoft Store", "id": "42.2689890.4.1", "state": "", "rect": {"x": 1749, "y": 0, "w": 57, "h": 40}, "zone": "TR"},
          {"i": 7, "kind": "Button", "name": "Restaurar Microsoft Store", "id": "42.2689890.4.2", "state": "", "rect": {"x": 1806, "y": 0, "w": 57, "h": 40}, "zone": "TR"},
          {"i": 8, "kind": "Button", "name": "Cerrar Microsoft Store", "id": "42.2689890.4.3", "state": "", "rect": {"x": 1863, "y": 0, "w": 57, "h": 40}, "zone": "TR"},
          {"i": 9, "kind": "Edit", "name": "Buscar", "id": "42.1117594.4.13", "state": "", "value": "", "rect": {"x": 585, "y": 9, "w": 750, "h": 42}, "zone": "T"},
          {"i": 10, "kind": "Button", "name": "Perfil de usuario", "id": "42.1117594.4.18", "state": "", "rect": {"x": 1645, "y": 11, "w": 37, "h": 37}, "zone": "TR"},
          {"i": 11, "kind": "ListItem", "name": "Inicio", "id": "42.1117594.4.19", "state": "selected", "rect": {"x": 0, "y": 60, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 12, "kind": "ListItem", "name": "Aplicaciones", "id": "42.1117594.4.21", "state": "", "rect": {"x": 0, "y": 138, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 13, "kind": "ListItem", "name": "Juegos", "id": "42.1117594.4.23", "state": "", "rect": {"x": 0, "y": 216, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 14, "kind": "ListItem", "name": "Temas", "id": "42.1117594.4.27", "state": "", "rect": {"x": 0, "y": 294, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 15, "kind": "ListItem", "name": "Novedades", "id": "42.1117594.4.33", "state": "", "rect": {"x": 0, "y": 786, "w": 90, "h": 78}, "zone": "BL"},
          {"i": 16, "kind": "ListItem", "name": "Descargas", "id": "42.1117594.4.37", "state": "", "rect": {"x": 0, "y": 864, "w": 90, "h": 78}, "zone": "BL"},
          {"i": 17, "kind": "ListItem", "name": "Biblioteca", "id": "42.1117594.4.39", "state": "", "rect": {"x": 0, "y": 942, "w": 90, "h": 78}, "zone": "BL"},
          {"i": 18, "kind": "Button", "name": "Claude, Obtener", "id": "42.1117594.4.55", "state": "", "rect": {"x": 181, "y": 394, "w": 150, "h": 40}, "zone": "L"},
          {"i": 19, "kind": "Hyperlink", "name": "Clasificación por edades: 3+. Haz clic para más información.", "id": "42.1117594.4.59", "state": "", "rect": {"x": 238, "y": 468, "w": 31, "h": 22}, "zone": "L"},
          {"i": 20, "kind": "Button", "name": "Página 1", "id": "42.1117594.4.73", "state": "", "rect": {"x": 605, "y": 662, "w": 15, "h": 25}, "zone": "L"},
          {"i": 21, "kind": "Button", "name": "Página 2", "id": "42.1117594.4.75", "state": "", "rect": {"x": 620, "y": 662, "w": 15, "h": 25}, "zone": "L"},
          {"i": 22, "kind": "Button", "name": "Página 3", "id": "42.1117594.4.77", "state": "", "rect": {"x": 635, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 23, "kind": "Button", "name": "Página 4", "id": "42.1117594.4.79", "state": "", "rect": {"x": 650, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 24, "kind": "Button", "name": "Página 5", "id": "42.1117594.4.81", "state": "", "rect": {"x": 665, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 25, "kind": "Button", "name": "Página 6", "id": "42.1117594.4.83", "state": "", "rect": {"x": 680, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 26, "kind": "Button", "name": "Página 7", "id": "42.1117594.4.85", "state": "", "rect": {"x": 695, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 27, "kind": "Button", "name": "Spotify - Music and Podcasts", "id": "42.1117594.4.94", "state": "", "rect": {"x": 1194, "y": 76, "w": 680, "h": 382}, "zone": "TR"},
          {"i": 28, "kind": "Button", "name": "Spotify: Música y podcasts, Abrir", "id": "42.1117594.4.92", "state": "", "rect": {"x": 1234, "y": 295, "w": 150, "h": 40}, "zone": "TR"},
          {"i": 29, "kind": "Button", "name": "Call of Duty: Modern Warfare 4", "id": "42.1117594.4.97", "state": "", "rect": {"x": 1194, "y": 474, "w": 332, "h": 188}, "zone": "R"},
          {"i": 30, "kind": "Button", "name": "Overwatch: S5", "id": "42.1117594.4.100", "state": "", "rect": {"x": 1542, "y": 474, "w": 332, "h": 188}, "zone": "R"},
          {"i": 31, "kind": "Hyperlink", "name": "Ver todo Tendencias de juegos", "id": "42.1117594.4.107", "state": "", "rect": {"x": 186, "y": 751, "w": 296, "h": 35}, "zone": "BL"},
          {"i": 32, "kind": "Button", "name": "Desplazarse hacia delante", "id": "42.1117594.4.111", "state": "", "rect": {"x": 905, "y": 735, "w": 57, "h": 65}, "zone": "B"},
          {"i": 33, "kind": "Button", "name": "Roblox - Windows. 437 clasificaciones totales. Clasificación ... strellas. Gratis", "id": "42.1117594.4.117", "state": "", "rect": {"x": 186, "y": 854, "w": 373, "h": 141}, "zone": "BL"},
          {"i": 34, "kind": "Button", "name": "Minecraft Launcher. Incluido con Game Pass Premium • Ultimat ... strellas. Gratis", "id": "42.1117594.4.125", "state": "", "rect": {"x": 186, "y": 1011, "w": 373, "h": 8}, "zone": "BL"},
          {"i": 35, "kind": "Button", "name": "Minecraft: Java & Bedrock Edition for PC. Incluido con Game ... trellas. $32.490", "id": "42.1117594.4.141", "state": "", "rect": {"x": 574, "y": 854, "w": 373, "h": 141}, "zone": "B"},
          {"i": 36, "kind": "Button", "name": "eFootball™. 149 clasificaciones totales. Clasificación media ... strellas. Gratis", "id": "42.1117594.4.147", "state": "", "rect": {"x": 574, "y": 1011, "w": 373, "h": 8}, "zone": "B"},
          {"i": 37, "kind": "Hyperlink", "name": "Ver todo Tendencias en aplicaciones", "id": "42.1117594.4.161", "state": "", "rect": {"x": 1063, "y": 751, "w": 358, "h": 35}, "zone": "B"},
          {"i": 38, "kind": "Button", "name": "Power BI Desktop. Clasificación media de 4,9 sobre 5 estrellas. Gratis", "id": "42.1117594.4.171", "state": "", "rect": {"x": 1063, "y": 854, "w": 373, "h": 141}, "zone": "B"},
          {"i": 39, "kind": "Button", "name": "Adobe Acrobat Reader DC. 75 clasificaciones totales. Clasifi ... strellas. Gratis", "id": "42.1117594.4.177", "state": "", "rect": {"x": 1063, "y": 1011, "w": 373, "h": 8}, "zone": "B"},
          {"i": 40, "kind": "Button", "name": "Canva. Clasificación media de 4,9 sobre 5 estrellas. Gratis", "id": "42.1117594.4.189", "state": "", "rect": {"x": 1451, "y": 854, "w": 373, "h": 141}, "zone": "BR"},
          {"i": 41, "kind": "Button", "name": "Netflix. Clasificación media de 4,2 sobre 5 estrellas. Gratis", "id": "42.1117594.4.196", "state": "", "rect": {"x": 1451, "y": 1011, "w": 373, "h": 8}, "zone": "BR"},
          {"i": 42, "kind": "Window", "name": "Host de ventanas emergentes", "id": "42.2690532", "state": "", "rect": {"x": 572, "y": 46, "w": 776, "h": 398}, "zone": "T"},
          {"i": 43, "kind": "Window", "name": "Ventana emergente", "id": "42.2690532.4.377", "state": "", "rect": {"x": 585, "y": 49, "w": 751, "h": 372}, "zone": "T"},
          {"i": 44, "kind": "Group", "name": "Spotify. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.358", "state": "", "rect": {"x": 606, "y": 64, "w": 711, "h": 49}, "zone": "T"},
          {"i": 45, "kind": "Group", "name": "WhatsApp. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.362", "state": "", "rect": {"x": 606, "y": 137, "w": 711, "h": 50}, "zone": "T"},
          {"i": 46, "kind": "Group", "name": "speedtest. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.366", "state": "", "rect": {"x": 606, "y": 210, "w": 711, "h": 50}, "zone": "T"},
          {"i": 47, "kind": "Group", "name": "geforce now. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.370", "state": "", "rect": {"x": 606, "y": 282, "w": 711, "h": 50}, "zone": "T"},
          {"i": 48, "kind": "Group", "name": "ubuntu. Presione la tecla Suprimir para borrar el historial de búsqueda.", "id": "42.2690532.4.374", "state": "", "rect": {"x": 606, "y": 355, "w": 711, "h": 50}, "zone": "C"},
          {"i": 49, "kind": "Window", "name": "Microsoft Store", "id": "42.2689890", "state": "readonly", "value": "Microsoft Store", "rect": {"x": 1687, "y": 0, "w": 233, "h": 40}, "zone": "TR"},
          {"i": 50, "kind": "MenuBar", "name": "Sistema", "id": "42.2689890.4.0", "state": "", "zone": ""},
          {"i": 51, "kind": "Text", "name": "Microsoft Store", "id": "42.1117594.4.7", "state": "", "rect": {"x": 70, "y": 25, "w": 103, "h": 11}, "zone": "TL"},
          {"i": 52, "kind": "Group", "name": "Buscar", "id": "42.1117594.4.14", "state": "", "rect": {"x": 585, "y": 9, "w": 751, "h": 412}, "zone": "T"},
          {"i": 53, "kind": "Custom", "name": "MosaicHeroLayout", "id": "42.1117594.4.102", "state": "", "rect": {"x": 136, "y": 61, "w": 1738, "h": 626}, "zone": "C"},
          {"i": 54, "kind": "Text", "name": "Enfréntate a problemas complejos", "id": "42.1117594.4.52", "state": "", "rect": {"x": 181, "y": 227, "w": 387, "h": 106}, "zone": "TL"},
          {"i": 55, "kind": "Text", "name": "Ahora en tu escritorio de Windows", "id": "42.1117594.4.53", "state": "", "rect": {"x": 136, "y": 334, "w": 402, "h": 28}, "zone": "L"},
          {"i": 56, "kind": "Text", "name": "Claude, Obtener", "id": "42.1117594.4.54", "state": "", "rect": {"x": 223, "y": 401, "w": 65, "h": 23}, "zone": "L"},
          {"i": 57, "kind": "Group", "name": "Claude", "id": "42.1117594.4.56", "state": "", "rect": {"x": 181, "y": 382, "w": 300, "h": 65}, "zone": "L"},
          {"i": 58, "kind": "Text", "name": "Compras incluidas en la aplicación", "id": "42.1117594.4.60", "state": "", "rect": {"x": 244, "y": 490, "w": 198, "h": 15}, "zone": "L"},
          {"i": 59, "kind": "Menu", "name": "Buscapersonas", "id": "42.1117594.4.88", "state": "", "rect": {"x": 605, "y": 662, "w": 105, "h": 25}, "zone": "C"},
          {"i": 60, "kind": "Text", "name": "Spotify - Music and Podcasts", "id": "42.1117594.4.90", "state": "", "rect": {"x": 1234, "y": 187, "w": 300, "h": 79}, "zone": "TR", "reserved": true},
          {"i": 61, "kind": "Text", "name": "Spotify: Música y podcasts, Abrir", "id": "42.1117594.4.91", "state": "", "rect": {"x": 1289, "y": 302, "w": 39, "h": 23}, "zone": "TR", "reserved": true},
          {"i": 62, "kind": "Group", "name": "Spotify: Música y podcasts", "id": "42.1117594.4.93", "state": "", "rect": {"x": 1234, "y": 282, "w": 320, "h": 65}, "zone": "TR", "reserved": true}
         ],
         "controlCount": 77,
         "text": {"TL": ["Microsoft Store", "la", "Aplicaciones", "Enfréntate a", "Juegos", "problemas..."], "T": ["Buscar aplicaciones, juegos y mucho más"], "TR": ["x", "Spotify - Music and", "Podcasts", "Spotify", "Abrir"], "L": ["Temas", "Ahora en tu escritorio de Windows", "Obtener", "1 ARC", "3+", "Compras incluidas en la aplicación"], "C": ["Claude"], "R": ["Call of Duty: Modern Warfare 4", "Overwatch: S5"], "BL": ["Tendencias de juegos >", "Tendencias de juegos", "Novedades", "Game Pass", "e Pass", "Roblox - Windows", "Descargas", "Gratis", "Biblioteca"], "B": ["Tendencias en aplicaciones >", "Tendencias en aplicaciones", "Minecraft: Java &", "Bedrock Edition for PC", "$32.490", "$32A90", "Desktop"], "BR": ["Power Bl Desktop", "Canva"]}}
        """;

    // The real look after the Enter (journal seq 5746): the carousel turned, the banner kept its ids and rect.
    private const string AfterEnter = """
        {"window": {"title": "Microsoft Store", "process": "WinStore.App", "foreground": false, "rect": {"x": 0, "y": 0, "w": 1920, "h": 1020}, "focused": null},
         "controls": [
          {"i": 0, "kind": "MenuItem", "name": "Sistema", "id": "42.2689890.4.65535", "state": "collapsed", "zone": ""},
          {"i": 1, "kind": "Button", "name": "Minimizar Microsoft Store", "id": "42.2689890.4.1", "state": "", "rect": {"x": 1749, "y": 0, "w": 57, "h": 40}, "zone": "TR"},
          {"i": 2, "kind": "Button", "name": "Restaurar Microsoft Store", "id": "42.2689890.4.2", "state": "", "rect": {"x": 1806, "y": 0, "w": 57, "h": 40}, "zone": "TR"},
          {"i": 3, "kind": "Button", "name": "Cerrar Microsoft Store", "id": "42.2689890.4.3", "state": "", "rect": {"x": 1863, "y": 0, "w": 57, "h": 40}, "zone": "TR"},
          {"i": 4, "kind": "Edit", "name": "Buscar", "id": "42.1117594.4.13", "state": "", "value": "Spotify", "rect": {"x": 585, "y": 9, "w": 750, "h": 42}, "zone": "T"},
          {"i": 5, "kind": "Button", "name": "Perfil de usuario", "id": "42.1117594.4.18", "state": "", "rect": {"x": 1645, "y": 11, "w": 37, "h": 37}, "zone": "TR"},
          {"i": 6, "kind": "ListItem", "name": "Inicio", "id": "42.1117594.4.19", "state": "selected", "rect": {"x": 0, "y": 60, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 7, "kind": "ListItem", "name": "Aplicaciones", "id": "42.1117594.4.21", "state": "", "rect": {"x": 0, "y": 138, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 8, "kind": "ListItem", "name": "Juegos", "id": "42.1117594.4.23", "state": "", "rect": {"x": 0, "y": 216, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 9, "kind": "ListItem", "name": "Temas", "id": "42.1117594.4.27", "state": "", "rect": {"x": 0, "y": 294, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 10, "kind": "ListItem", "name": "Novedades", "id": "42.1117594.4.33", "state": "", "rect": {"x": 0, "y": 786, "w": 90, "h": 78}, "zone": "BL"},
          {"i": 11, "kind": "ListItem", "name": "Descargas", "id": "42.1117594.4.37", "state": "", "rect": {"x": 0, "y": 864, "w": 90, "h": 78}, "zone": "BL"},
          {"i": 12, "kind": "ListItem", "name": "Biblioteca", "id": "42.1117594.4.39", "state": "", "rect": {"x": 0, "y": 942, "w": 90, "h": 78}, "zone": "BL"},
          {"i": 13, "kind": "Button", "name": "WhatsApp, Abrir", "id": "42.1117594.4.65", "state": "", "rect": {"x": 181, "y": 402, "w": 150, "h": 40}, "zone": "L"},
          {"i": 14, "kind": "Button", "name": "Página 1", "id": "42.1117594.4.73", "state": "", "rect": {"x": 605, "y": 662, "w": 15, "h": 25}, "zone": "L"},
          {"i": 15, "kind": "Button", "name": "Página 2", "id": "42.1117594.4.75", "state": "", "rect": {"x": 620, "y": 662, "w": 15, "h": 25}, "zone": "L"},
          {"i": 16, "kind": "Button", "name": "Página 3", "id": "42.1117594.4.77", "state": "", "rect": {"x": 635, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 17, "kind": "Button", "name": "Página 4", "id": "42.1117594.4.79", "state": "", "rect": {"x": 650, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 18, "kind": "Button", "name": "Página 5", "id": "42.1117594.4.81", "state": "", "rect": {"x": 665, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 19, "kind": "Button", "name": "Página 6", "id": "42.1117594.4.83", "state": "", "rect": {"x": 680, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 20, "kind": "Button", "name": "Página 7", "id": "42.1117594.4.85", "state": "", "rect": {"x": 695, "y": 662, "w": 15, "h": 25}, "zone": "C"},
          {"i": 21, "kind": "Button", "name": "Spotify - Music and Podcasts", "id": "42.1117594.4.94", "state": "", "rect": {"x": 1194, "y": 76, "w": 680, "h": 382}, "zone": "TR"},
          {"i": 22, "kind": "Button", "name": "Spotify: Música y podcasts, Abrir", "id": "42.1117594.4.92", "state": "", "rect": {"x": 1234, "y": 295, "w": 150, "h": 40}, "zone": "TR"},
          {"i": 23, "kind": "Button", "name": "Call of Duty: Modern Warfare 4", "id": "42.1117594.4.97", "state": "", "rect": {"x": 1194, "y": 474, "w": 332, "h": 188}, "zone": "R"},
          {"i": 24, "kind": "Button", "name": "Overwatch: S5", "id": "42.1117594.4.100", "state": "", "rect": {"x": 1542, "y": 474, "w": 332, "h": 188}, "zone": "R"},
          {"i": 25, "kind": "Hyperlink", "name": "Ver todo Tendencias de juegos", "id": "42.1117594.4.107", "state": "", "rect": {"x": 186, "y": 751, "w": 296, "h": 35}, "zone": "BL"},
          {"i": 26, "kind": "Button", "name": "Desplazarse hacia delante", "id": "42.1117594.4.111", "state": "", "rect": {"x": 905, "y": 735, "w": 57, "h": 65}, "zone": "B"},
          {"i": 27, "kind": "Button", "name": "Roblox - Windows. 437 clasificaciones totales. Clasificación ... strellas. Gratis", "id": "42.1117594.4.117", "state": "", "rect": {"x": 186, "y": 854, "w": 373, "h": 141}, "zone": "BL"},
          {"i": 28, "kind": "Button", "name": "Minecraft Launcher. Incluido con Game Pass Premium • Ultimat ... strellas. Gratis", "id": "42.1117594.4.125", "state": "", "rect": {"x": 186, "y": 1011, "w": 373, "h": 8}, "zone": "BL"},
          {"i": 29, "kind": "Button", "name": "Minecraft: Java & Bedrock Edition for PC. Incluido con Game ... trellas. $32.490", "id": "42.1117594.4.141", "state": "", "rect": {"x": 574, "y": 854, "w": 373, "h": 141}, "zone": "B"},
          {"i": 30, "kind": "Button", "name": "eFootball™. 149 clasificaciones totales. Clasificación media ... strellas. Gratis", "id": "42.1117594.4.147", "state": "", "rect": {"x": 574, "y": 1011, "w": 373, "h": 8}, "zone": "B"},
          {"i": 31, "kind": "Hyperlink", "name": "Ver todo Tendencias en aplicaciones", "id": "42.1117594.4.161", "state": "", "rect": {"x": 1063, "y": 751, "w": 358, "h": 35}, "zone": "B"},
          {"i": 32, "kind": "Button", "name": "Power BI Desktop. Clasificación media de 4,9 sobre 5 estrellas. Gratis", "id": "42.1117594.4.171", "state": "", "rect": {"x": 1063, "y": 854, "w": 373, "h": 141}, "zone": "B"},
          {"i": 33, "kind": "Button", "name": "Adobe Acrobat Reader DC. 75 clasificaciones totales. Clasifi ... strellas. Gratis", "id": "42.1117594.4.177", "state": "", "rect": {"x": 1063, "y": 1011, "w": 373, "h": 8}, "zone": "B"},
          {"i": 34, "kind": "Button", "name": "Canva. Clasificación media de 4,9 sobre 5 estrellas. Gratis", "id": "42.1117594.4.189", "state": "", "rect": {"x": 1451, "y": 854, "w": 373, "h": 141}, "zone": "BR"},
          {"i": 35, "kind": "Button", "name": "Netflix. Clasificación media de 4,2 sobre 5 estrellas. Gratis", "id": "42.1117594.4.196", "state": "", "rect": {"x": 1451, "y": 1011, "w": 373, "h": 8}, "zone": "BR"},
          {"i": 36, "kind": "Window", "name": "Microsoft Store", "id": "42.2689890", "state": "readonly", "value": "Microsoft Store", "rect": {"x": 1687, "y": 0, "w": 233, "h": 40}, "zone": "TR"},
          {"i": 37, "kind": "MenuBar", "name": "Sistema", "id": "42.2689890.4.0", "state": "", "zone": ""},
          {"i": 38, "kind": "Text", "name": "Microsoft Store", "id": "42.1117594.4.7", "state": "", "rect": {"x": 70, "y": 25, "w": 103, "h": 11}, "zone": "TL"},
          {"i": 39, "kind": "Group", "name": "Buscar", "id": "42.1117594.4.14", "state": "", "rect": {"x": 584, "y": 9, "w": 751, "h": 518}, "zone": "T"},
          {"i": 40, "kind": "Custom", "name": "MosaicHeroLayout", "id": "42.1117594.4.102", "state": "", "rect": {"x": 136, "y": 61, "w": 1738, "h": 626}, "zone": "C"},
          {"i": 41, "kind": "Group", "name": "WhatsApp", "id": "42.1117594.4.66", "state": "", "rect": {"x": 181, "y": 389, "w": 299, "h": 65}, "zone": "L"},
          {"i": 42, "kind": "Text", "name": "Mensajes y llamadas privadas", "id": "42.1117594.4.63", "state": "", "rect": {"x": 136, "y": 341, "w": 402, "h": 28}, "zone": "L"},
          {"i": 43, "kind": "Text", "name": "WhatsApp", "id": "42.1117594.4.62", "state": "", "rect": {"x": 181, "y": 288, "w": 387, "h": 53}, "zone": "TL"},
          {"i": 44, "kind": "Text", "name": "WhatsApp, Abrir", "id": "42.1117594.4.64", "state": "", "rect": {"x": 236, "y": 409, "w": 39, "h": 23}, "zone": "L"},
          {"i": 45, "kind": "Text", "name": "Dale vida a tu escritorio", "id": "42.1117594.4.69", "state": "", "rect": {"x": 1179, "y": 318, "w": 0, "h": 28}, "zone": "T"},
          {"i": 46, "kind": "Menu", "name": "Buscapersonas", "id": "42.1117594.4.88", "state": "", "rect": {"x": 605, "y": 662, "w": 105, "h": 25}, "zone": "C"},
          {"i": 47, "kind": "Text", "name": "Spotify - Music and Podcasts", "id": "42.1117594.4.90", "state": "", "rect": {"x": 1234, "y": 187, "w": 300, "h": 79}, "zone": "TR"},
          {"i": 48, "kind": "Text", "name": "Spotify: Música y podcasts, Abrir", "id": "42.1117594.4.91", "state": "", "rect": {"x": 1289, "y": 302, "w": 39, "h": 23}, "zone": "TR"},
          {"i": 49, "kind": "Group", "name": "Spotify: Música y podcasts", "id": "42.1117594.4.93", "state": "", "rect": {"x": 1234, "y": 282, "w": 320, "h": 65}, "zone": "TR"},
          {"i": 50, "kind": "Text", "name": "Call of Duty: Modern Warfare 4", "id": "42.1117594.4.96", "state": "", "rect": {"x": 1214, "y": 616, "w": 292, "h": 26}, "zone": "R"},
          {"i": 51, "kind": "Text", "name": "Overwatch: S5", "id": "42.1117594.4.99", "state": "", "rect": {"x": 1562, "y": 616, "w": 292, "h": 26}, "zone": "R"},
          {"i": 52, "kind": "Custom", "name": "ResponsiveColumnedGridLayout", "id": "42.1117594.4.206", "state": "", "rect": {"x": 136, "y": 710, "w": 1738, "h": 309}, "zone": "B"},
          {"i": 53, "kind": "Custom", "name": "Tendencias de juegos", "id": "42.1117594.4.156", "state": "", "rect": {"x": 136, "y": 710, "w": 1432, "h": 309}, "zone": "B"},
          {"i": 54, "kind": "Group", "name": "Tendencias de juegos", "id": "42.1117594.4.155", "state": "", "rect": {"x": 186, "y": 735, "w": 1382, "h": 284}, "zone": "B"},
          {"i": 55, "kind": "Text", "name": "Tendencias de juegos", "id": "42.1117594.4.105", "state": "", "rect": {"x": 187, "y": 752, "w": 241, "h": 33}, "zone": "BL"},
          {"i": 56, "kind": "Text", "name": "Gratis", "id": "42.1117594.4.115", "state": "", "rect": {"x": 478, "y": 945, "w": 60, "h": 30}, "zone": "BL"},
          {"i": 57, "kind": "Text", "name": "Game Pass Premium • Ultimate • PC", "id": "42.1117594.4.123", "state": "", "rect": {"x": 197, "y": 1017, "w": 74, "h": 2}, "zone": "BL"},
          {"i": 58, "kind": "Text", "name": "$32.490", "id": "42.1117594.4.137", "state": "", "rect": {"x": 853, "y": 945, "w": 73, "h": 30}, "zone": "B"},
          {"i": 59, "kind": "Custom", "name": "Tendencias en aplicaciones", "id": "42.1117594.4.205", "state": "", "rect": {"x": 1013, "y": 710, "w": 861, "h": 309}, "zone": "BR"}
         ],
         "controlCount": 64,
         "text": {"TL": ["Microsoft Store", "Spotify", "la", "Aplicaciones", "Juegos", "WhatsApp"], "T": ["O"], "TR": ["x", "Q", "Spotify - Music and", "Podcasts"], "L": ["Temas", "Mensajes y llamadas privadas", "Abrir"], "R": ["Call of Duty: Modern Warfare 4", "Overwatch: S5"], "BL": ["Tendencias de juegos >", "Tendencias de juegos", "Novedades", "Game Pass", "e Pass", "Roblox - Windows", "Descargas", "Gratis", "Biblioteca"], "B": ["Tendencias en aplicaciones >", "Tendencias en aplicaciones", "Minecraft: Java &", "Bedrock Edition for PC", "$32.490", "$32A90", "Desktop"], "BR": ["Power Bl Desktop", "Canva"]}}
        """;

    private static JsonObject View(string json) => (JsonObject)JsonNode.Parse(json)!;

    private static JsonArray Steps(string text, string into) => new()
    {
        new JsonObject
        {
            ["step"] = 3, ["operation"] = "input.text.type", ["text"] = text, ["into"] = into, ["ok"] = true,
            ["changed"] = true,
        },
        new JsonObject { ["step"] = 4, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
    };

    // The look after the search, carrying what the view showed right before the typing (step 3), as the loop does.
    private static JsonObject Started(JsonObject after, JsonObject before)
    {
        after["viewBeforeTyping"] = new JsonObject { ["3"] = ComputerUseSuccessCheck.ViewBeforeTyping(before) };
        return after;
    }

    [Test]
    public void TheHomePageBannerTheViewAlreadyShowedIsNoResultOfTheSearch()
    {
        JsonObject judged = Started(View(AfterEnter), View(BeforeTyping));
        JsonArray steps = Steps("Spotify", "Buscar");
        Assert.Multiple(() =>
        {
            // Without the view the search started from (the old reading), the banner passed: the false success of v1.
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", View(AfterEnter), steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", judged, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("spotify", judged, steps)!.Filtered, Is.False,
                "a carousel that turned brought new controls: no filter in place");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, judged, steps, out _), Is.False);
        });
    }

    [Test]
    public void AResultsPageWithANewItemNamedAsTheBannerPasses()
    {
        // Counter-case 1: the same store's results page lists «Spotify - Music and Podcasts» under a NEW id, and the
        // home page is gone.
        JsonObject results = View("""
            {"window": {"title": "Microsoft Store", "process": "WinStore.App", "focused": null},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "42.1117594.4.13", "value": "Spotify", "rect": {"x": 585, "y": 9, "w": 750, "h": 42}, "zone": "T"},
              {"i": 1, "kind": "ListItem", "name": "Inicio", "id": "42.1117594.4.19", "state": "", "rect": {"x": 0, "y": 60, "w": 90, "h": 78}, "zone": "TL"},
              {"i": 2, "kind": "Text", "name": "Resultados", "id": "42.1117594.9.3", "rect": {"x": 136, "y": 70, "w": 300, "h": 40}, "zone": "TL"},
              {"i": 3, "kind": "ListItem", "name": "Spotify - Music and Podcasts", "id": "42.1117594.9.40", "rect": {"x": 136, "y": 150, "w": 400, "h": 120}, "zone": "L"},
              {"i": 4, "kind": "Button", "name": "Spotify - Music and Podcasts, Abrir", "id": "42.1117594.9.41", "rect": {"x": 300, "y": 230, "w": 120, "h": 30}, "zone": "L"}
             ],
             "text": {"T": ["Spotify"], "TL": ["Resultados"], "L": ["Spotify - Music and Podcasts", "Abrir"]}}
            """);
        JsonObject judged = Started(results, View(BeforeTyping));
        JsonArray steps = Steps("Spotify", "Buscar");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", judged, steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, judged, steps, out _), Is.True);
        });
    }

    [Test]
    public void ALibraryReadByOcrThatNarrowsPassesAsAFilterInPlace()
    {
        // Counter-case 2 (a box drawn without a tree): the entry already shown stays, the others leave, nothing arrives.
        JsonObject before = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"T": ["Buscar por nombre"], "L": ["Cuphead", "Hollow Knight", "Celeste", "Hades"]}}
            """);
        JsonObject narrowed = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"T": ["Cuphead"], "L": ["Cuphead"]}}
            """);
        JsonObject unchanged = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"T": ["Cuphead"], "L": ["Cuphead", "Hollow Knight", "Celeste", "Hades"]}}
            """);
        JsonArray steps = Steps("Cuphead", "Buscar por nombre");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", Started(narrowed, before), steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("cuphead", narrowed, steps)!.Filtered, Is.True);
            // Must fail: the list as it was, with only the box repeating the query.
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", Started(unchanged, before), steps), Is.True);
        });
    }

    [Test]
    public void AListOfControlsThatNarrowsPassesAsAFilterInPlace()
    {
        // Counter-case 2 (a tree): the settings' list keeps the item (same id) and drops the others; nothing arrives.
        JsonObject before = View("""
            {"window": {"title": "Configuración", "process": "settings"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "ListItem", "name": "Calculadora", "id": "7.10", "rect": {"x": 100, "y": 100, "w": 600, "h": 40}, "zone": "C"},
              {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 140, "w": 600, "h": 40}, "zone": "C"},
              {"i": 3, "kind": "ListItem", "name": "Reloj", "id": "7.12", "rect": {"x": 100, "y": 180, "w": 600, "h": 40}, "zone": "C"}
             ]}
            """);
        JsonObject narrowed = View("""
            {"window": {"title": "Configuración", "process": "settings"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "Fotos", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Button", "name": "Borrar", "id": "7.2", "rect": {"x": 370, "y": 55, "w": 20, "h": 20}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 100, "w": 600, "h": 40}, "zone": "C"}
             ],
             "text": {"C": ["Fotos"]}}
            """);
        JsonArray steps = Steps("Fotos", "Buscar aplicaciones");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Fotos", Started(narrowed, before), steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", narrowed, steps)!.Filtered, Is.True,
                "the box's own clear button arrives with any typing");
        });
    }

    [Test]
    public void ATitleTheSearchChangedIsAPlaceOfItsResults()
    {
        // Counter-case 3: a site whose title becomes «Spotify - Búsqueda»; the banner bearing the query was already there.
        JsonObject before = View("""
            {"window": {"title": "Inicio - Sitio", "process": "browser"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "9.1", "value": "", "rect": {"x": 100, "y": 10, "w": 400, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Hyperlink", "name": "Spotify Premium gratis", "id": "9.5", "rect": {"x": 100, "y": 300, "w": 400, "h": 30}, "zone": "C"}
             ]}
            """);
        JsonObject titled = View("""
            {"window": {"title": "Spotify - Búsqueda", "process": "browser"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "9.1", "value": "Spotify", "rect": {"x": 100, "y": 10, "w": 400, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Hyperlink", "name": "Spotify Premium gratis", "id": "9.5", "rect": {"x": 100, "y": 300, "w": 400, "h": 30}, "zone": "C"},
              {"i": 2, "kind": "Text", "name": "Ningún otro resultado destacado", "id": "9.40", "rect": {"x": 100, "y": 400, "w": 400, "h": 30}, "zone": "C"}
             ],
             "text": {"T": ["Spotify"]}}
            """);
        JsonObject sameTitle = View("""
            {"window": {"title": "Inicio - Sitio", "process": "browser"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "9.1", "value": "Spotify", "rect": {"x": 100, "y": 10, "w": 400, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Hyperlink", "name": "Spotify Premium gratis", "id": "9.5", "rect": {"x": 100, "y": 300, "w": 400, "h": 30}, "zone": "C"},
              {"i": 2, "kind": "Text", "name": "Ningún otro resultado destacado", "id": "9.40", "rect": {"x": 100, "y": 400, "w": 400, "h": 30}, "zone": "C"}
             ],
             "text": {"T": ["Spotify"]}}
            """);
        JsonArray steps = Steps("Spotify", "Buscar");
        Assert.Multiple(() =>
        {
            // The new title and the box's echo are two places; the link was there before and is none.
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("spotify", Started(titled, before), steps)!.OldTitle("spotify - busqueda"), Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", titled, steps), Is.False);
            // Must fail: the same title as before, the old link and the echo only.
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", Started(sameTitle, before), steps), Is.True);
        });
    }

    [Test]
    public void RecentSearchesAlreadyShowingTheQueryWithAnEnterThatDoesNotNavigateFail()
    {
        // Must fail: a «recientes» list that already named the query, and an Enter that changed nothing but the box.
        JsonObject before = View("""
            {"window": {"title": "Explorar", "process": "client"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "5.1", "value": "", "rect": {"x": 100, "y": 10, "w": 400, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Text", "name": "Búsquedas recientes", "id": "5.2", "rect": {"x": 100, "y": 60, "w": 400, "h": 30}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Spotify", "id": "5.3", "rect": {"x": 100, "y": 100, "w": 400, "h": 30}, "zone": "C"},
              {"i": 3, "kind": "ListItem", "name": "Spotify podcasts", "id": "5.4", "rect": {"x": 100, "y": 140, "w": 400, "h": 30}, "zone": "C"}
             ],
             "text": {"T": ["Buscar", "Búsquedas recientes"], "C": ["Spotify", "Spotify podcasts"]}}
            """);
        JsonObject after = View("""
            {"window": {"title": "Explorar", "process": "client"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "5.1", "value": "Spotify", "rect": {"x": 100, "y": 10, "w": 400, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Text", "name": "Búsquedas recientes", "id": "5.2", "rect": {"x": 100, "y": 60, "w": 400, "h": 30}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Spotify", "id": "5.3", "rect": {"x": 100, "y": 100, "w": 400, "h": 30}, "zone": "C"},
              {"i": 3, "kind": "ListItem", "name": "Spotify podcasts", "id": "5.4", "rect": {"x": 100, "y": 140, "w": 400, "h": 30}, "zone": "C"}
             ],
             "text": {"T": ["Spotify", "Búsquedas recientes"], "C": ["Spotify", "Spotify podcasts"]}}
            """);
        JsonArray steps = Steps("Spotify", "Buscar");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", View(after.ToJsonString()), steps), Is.False,
                "the old reading counted the recent searches as results");
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", Started(after, before), steps), Is.True);
        });
    }

    [Test]
    public void AResultInAnotherOrderThatTheViewAlreadyShowedIsNoResult()
    {
        // ResultInAnyOrder reads the same start: a control named with the query's words in another order counts only
        // when it was born after the search started.
        JsonObject before = View("""
            {"window": {"title": "Mapa de caracteres", "process": "charmap"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "3.1", "value": "", "rect": {"x": 10, "y": 10, "w": 200, "h": 20}, "zone": "T"},
              {"i": 1, "kind": "ListItem", "name": "Letra griega mayúscula Omega", "id": "3.20", "rect": {"x": 10, "y": 100, "w": 200, "h": 20}, "zone": "C"}
             ]}
            """);
        string after = """
            {"window": {"title": "Mapa de caracteres", "process": "charmap"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "3.1", "value": "omega mayúscula", "rect": {"x": 10, "y": 10, "w": 200, "h": 20}, "zone": "T"},
              {"i": 1, "kind": "ListItem", "name": "Letra griega mayúscula Omega", "id": "__ID__", "rect": {"x": 10, "y": 100, "w": 200, "h": 20}, "zone": "C"}
             ]}
            """;
        JsonArray steps = Steps("omega mayúscula", "Buscar");
        ((JsonObject)steps[1]!)["appeared"] = new JsonArray("letra griega mayuscula omega");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ResultInAnyOrder("omega mayúscula", Started(View(after.Replace("__ID__", "3.20")), before), steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.ResultInAnyOrder("omega mayúscula", Started(View(after.Replace("__ID__", "3.77")), before), steps), Is.True);
        });
    }

    [Test]
    public void TheViewBeforeTypingKeepsItsPlacesLinesAndTitle()
    {
        JsonObject before = ComputerUseSuccessCheck.ViewBeforeTyping(View(BeforeTyping));
        Assert.Multiple(() =>
        {
            Assert.That((string?)before["title"], Is.EqualTo("Microsoft Store"));
            Assert.That(((JsonArray)before["places"]!).Count, Is.EqualTo(63));
            Assert.That(((JsonArray)before["zones"]!["TR"]!).Select(line => (string?)line), Does.Contain("spotify - music and"));
            Assert.That(ComputerUseSuccessCheck.PlaceKey(View(BeforeTyping)["controls"]![27]!.AsObject()),
                Is.EqualTo("id:42.1117594.4.94|spotify - music and podcasts"));
        });
    }

    [Test]
    public void ALibraryReadByOcrWithItsCounterNarrowedIsAFilterInPlace()
    {
        // Revision 1 of r24b (finding 4, P1): a library read by OCR, its counter re-read («TODOS (12)» → «TODOS (1/12)»)
        // and the box's placeholder giving way to the query with the magnifier read as «Q».
        JsonObject before = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"TL": ["BIBLIOTECA", "Buscar por nombre", "TODOS (12)"], "L": ["Celeste", "Cuphead", "Hades", "Hollow Knight"]}}
            """);
        JsonObject narrowed = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"TL": ["BIBLIOTECA", "Q Cuphead", "TODOS (1/12)"], "L": ["Cuphead"]}}
            """);
        JsonObject unchanged = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"TL": ["BIBLIOTECA", "Q Cuphead", "TODOS (12)"], "L": ["Celeste", "Cuphead", "Hades", "Hollow Knight"]}}
            """);
        JsonArray steps = Steps("Cuphead", "Buscar por nombre");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("cuphead", Started(narrowed, before), steps)!.Filtered, Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", Started(narrowed, before), steps), Is.False);
            // Must fail: nothing left, the box repeats the query and the list is as it was.
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", Started(unchanged, before), steps), Is.True);
        });
    }

    [Test]
    public void AnOcrReReadingInAnotherZoneDoesNotUndoAFilter()
    {
        // P2: the same filter without a counter; another zone's line re-read with a stray mark («Juegos recientes >»).
        JsonObject before = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"TL": ["Buscar por nombre"], "L": ["Celeste", "Cuphead", "Hades", "Hollow Knight"], "C": ["Juegos recientes"]}}
            """);
        JsonObject narrowed = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"TL": ["Cuphead"], "L": ["Cuphead"], "C": ["Juegos recientes >"]}}
            """);
        JsonObject another = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"TL": ["Cuphead"], "L": ["Cuphead"], "C": ["Ofertas de la semana"]}}
            """);
        JsonArray steps = Steps("Cuphead", "Buscar por nombre");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", Started(narrowed, before), steps), Is.False);
            // Counter-case: a line of other content that arrived where another left is no re-reading: no filter.
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("cuphead", Started(another, before), steps)!.Filtered, Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", Started(another, before), steps), Is.True);
        });
    }

    [Test]
    public void AListWhoseCounterTextKeepsItsIdIsAFilterInPlace()
    {
        // P3: a settings list; «Fotos» keeps id 7.11 and the counter text keeps its id with another name.
        JsonObject before = View("""
            {"window": {"title": "Configuración", "process": "settings"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Text", "name": "Se encontraron 3 aplicaciones", "id": "7.5", "rect": {"x": 100, "y": 85, "w": 300, "h": 15}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Calculadora", "id": "7.10", "rect": {"x": 100, "y": 100, "w": 600, "h": 40}, "zone": "C"},
              {"i": 3, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 140, "w": 600, "h": 40}, "zone": "C"},
              {"i": 4, "kind": "ListItem", "name": "Reloj", "id": "7.12", "rect": {"x": 100, "y": 180, "w": 600, "h": 40}, "zone": "C"}
             ],
             "text": {"T": ["Buscar aplicaciones", "Se encontraron 3 aplicaciones"], "C": ["Calculadora", "Fotos", "Reloj"]}}
            """);
        JsonObject narrowed = View("""
            {"window": {"title": "Configuración", "process": "settings"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "Fotos", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Text", "name": "Se encontró 1 aplicación", "id": "7.5", "rect": {"x": 100, "y": 85, "w": 300, "h": 15}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 100, "w": 600, "h": 40}, "zone": "C"}
             ],
             "text": {"T": ["Fotos", "Se encontró 1 aplicación"], "C": ["Fotos"]}}
            """);
        JsonObject turned = View("""
            {"window": {"title": "Configuración", "process": "settings"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "Fotos", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Text", "name": "Se encontraron 3 aplicaciones", "id": "7.5", "rect": {"x": 100, "y": 85, "w": 300, "h": 15}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 140, "w": 600, "h": 40}, "zone": "C"},
              {"i": 3, "kind": "ListItem", "name": "Mapas", "id": "7.30", "rect": {"x": 100, "y": 180, "w": 600, "h": 40}, "zone": "C"},
              {"i": 4, "kind": "ListItem", "name": "Correo", "id": "7.31", "rect": {"x": 100, "y": 220, "w": 600, "h": 40}, "zone": "C"}
             ],
             "text": {"T": ["Fotos", "Se encontraron 3 aplicaciones"], "C": ["Fotos", "Mapas", "Correo"]}}
            """);
        JsonArray steps = Steps("Fotos", "Buscar aplicaciones");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", Started(narrowed, before), steps)!.Filtered, Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Fotos", Started(narrowed, before), steps), Is.False);
            // Counter-case: other items arrived where others left (a list that turned, not one that narrowed).
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", Started(turned, before), steps)!.Filtered, Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Fotos", Started(turned, before), steps), Is.True);
        });
    }

    [Test]
    public void TheSameLettersAreOneReadingAndOtherWordsAreNot()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.SameReading("todos (12)", "todos (1/12)"), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchStart.SameReading("juegos recientes", "juegos recientes >"), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchStart.SameReading("power bi desktop", "power bl desktop"), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchStart.SameReading("juegos recientes", "ofertas de la semana"), Is.False);
            Assert.That(ComputerUseSuccessCheck.SearchStart.SameReading("claude", "whatsapp"), Is.False);
        });
    }

    [Test]
    public void TheModelIsToldTheSearchShowedNothingNew()
    {
        // Revision 1 of r24b (finding 2): v1's Enter that never reached the box; the step after which it is seen is marked.
        JsonArray steps = Steps("Spotify", "Buscar");
        var enter = (JsonObject)steps[1]!;
        ComputerUseSuccessCheck.MarkSearchNothingNew(enter, Started(View(AfterEnter), View(BeforeTyping)), steps);
        Assert.That((bool?)enter["searchNothingNew"], Is.True);
        Assert.That(ComputerUseMission.HistoryForMind(steps, 0)[1]!["searchNothingNew"]?.GetValue<bool>(), Is.True);
    }

    [Test]
    public void AResultsPageOrAViewWithoutStartIsNotMarked()
    {
        // Counter-cases: the results page with a new item, and a look that carries no start (judged as before).
        JsonObject results = View("""
            {"window": {"title": "Microsoft Store", "process": "WinStore.App", "focused": null},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "42.1117594.4.13", "value": "Spotify", "rect": {"x": 585, "y": 9, "w": 750, "h": 42}, "zone": "T"},
              {"i": 1, "kind": "ListItem", "name": "Spotify - Music and Podcasts", "id": "42.1117594.9.40", "rect": {"x": 136, "y": 150, "w": 400, "h": 120}, "zone": "L"},
              {"i": 2, "kind": "Button", "name": "Spotify - Music and Podcasts, Abrir", "id": "42.1117594.9.41", "rect": {"x": 300, "y": 230, "w": 120, "h": 30}, "zone": "L"}
             ],
             "text": {"T": ["Spotify"], "L": ["Spotify - Music and Podcasts", "Abrir"]}}
            """);
        JsonArray steps = Steps("Spotify", "Buscar");
        var enter = (JsonObject)steps[1]!;
        enter["searchNothingNew"] = true;
        ComputerUseSuccessCheck.MarkSearchNothingNew(enter, Started(results, View(BeforeTyping)), steps);
        Assert.That(enter.ContainsKey("searchNothingNew"), Is.False, "a later look that shows new results drops the mark");
        ComputerUseSuccessCheck.MarkSearchNothingNew(enter, View(AfterEnter), steps);
        Assert.That(enter.ContainsKey("searchNothingNew"), Is.False);
    }

    // Revision 2 of r24b (P2): v1's look before the typing (seq 5738) after an Enter that never reached the box, with
    // no carousel turning (animations off, the pointer over it, or a fixed banner): only the box's drop-down of past
    // searches closed. Its rows sat inside the box's own frame (Group «Buscar» 4.14) and the pop-up window that closed.
    private static JsonObject DropDownClosedOnly()
    {
        JsonObject view = View(BeforeTyping);
        var controls = (JsonArray)view["controls"]!;
        foreach (JsonObject control in controls.OfType<JsonObject>().ToList())
        {
            control.Remove("reserved");
            if (((string?)control["id"] ?? string.Empty).StartsWith("42.2690532", StringComparison.Ordinal))
                controls.Remove(control);
            else if ((string?)control["id"] == "42.1117594.4.13")
                control["value"] = "Spotify";
            else if ((string?)control["id"] == "42.1117594.4.14")
                control["rect"] = new JsonObject { ["x"] = 585, ["y"] = 9, ["w"] = 751, ["h"] = 42 };
        }

        view["controlCount"] = 64;
        view["text"]!["T"] = new JsonArray("Spotify");
        return view;
    }

    [Test]
    public void ClosingTheBoxDropDownIsNoFilterAndTheOldBannerIsNoResult()
    {
        JsonArray steps = Steps("Spotify", "Buscar");
        JsonObject judged = Started(DropDownClosedOnly(), View(BeforeTyping));
        var enter = (JsonObject)steps[1]!;
        ComputerUseSuccessCheck.MarkSearchNothingNew(enter, judged, steps);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("spotify", judged, steps)!.Filtered, Is.False,
                "what left the box's frame and the closed pop-up narrows nothing");
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", judged, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, judged, steps, out _), Is.False);
            Assert.That((bool?)enter["searchNothingNew"], Is.True);
        });
    }

    // Revision 4 of r24b (finding 1, the reviewer's probe on v1's own look 5738): the Enter reached nothing, the box's
    // drop-down closed and the carousel was half turned: the outgoing slide (Button «Claude, Obtener» 4.55, its texts,
    // its group and its age link) was gone and the incoming one not yet listed. Those tiles shared rows with the banner
    // across the mosaic, never its columns: they were no rows of a list the banner is in, so nothing narrowed and the
    // old banner (4.94/4.90/4.93) is no result.
    private static JsonObject SlideHalfTurned()
    {
        JsonObject after = DropDownClosedOnly();
        var controls = (JsonArray)after["controls"]!;
        foreach (JsonObject control in controls.OfType<JsonObject>()
            .Where(control => (string?)control["id"] is "42.1117594.4.52" or "42.1117594.4.53" or "42.1117594.4.54"
                or "42.1117594.4.55" or "42.1117594.4.56" or "42.1117594.4.59" or "42.1117594.4.60").ToList())
            controls.Remove(control);
        return after;
    }

    [Test]
    public void ASlideHalfTurnedBesideTheBannerIsNoFilterAndTheOldBannerIsNoResult()
    {
        JsonArray steps = Steps("Spotify", "Buscar");
        JsonObject judged = Started(SlideHalfTurned(), View(BeforeTyping));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("spotify", judged, steps)!.Filtered, Is.False,
                "tiles that only shared rows with the banner are no rows of its list");
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", judged, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, judged, steps, out _), Is.False);
        });
    }

    [Test]
    public void WhatLeavesOutsideTheBoxFrameStillNarrows()
    {
        // Counter-case: the same closing of the drop-down while the tiles stacked under the banner (outside the box's
        // frame and the pop-up, in the banner's columns, of its kind) left and nothing arrived: that still narrows.
        JsonObject after = DropDownClosedOnly();
        var controls = (JsonArray)after["controls"]!;
        foreach (JsonObject control in controls.OfType<JsonObject>()
            .Where(control => (string?)control["id"] is "42.1117594.4.97" or "42.1117594.4.100").ToList())
            controls.Remove(control);
        JsonArray steps = Steps("Spotify", "Buscar");
        Assert.That(ComputerUseSuccessCheck.SearchStart.Of("spotify", Started(after, View(BeforeTyping)), steps)!.Filtered, Is.True);
    }

    // Revision 4 of r24b: a grid of results wraps its rows across, so inside a list container that stayed a tile
    // beside the result (sharing only its rows) is a row of that list. Counter-case: the same tiles without the
    // container (a mosaic of a home page) narrow nothing.
    private const string GridBefore = """
        {"window": {"title": "Biblioteca", "process": "library"},
         "controls": [
          {"i": 0, "kind": "Edit", "name": "Buscar", "id": "5.1", "value": "", "rect": {"x": 100, "y": 20, "w": 400, "h": 30}, "zone": "T"},
          {"i": 1, "kind": "List", "name": "Juegos", "id": "5.2", "rect": {"x": 100, "y": 80, "w": 900, "h": 200}, "zone": "C"},
          {"i": 2, "kind": "ListItem", "name": "Cuphead", "id": "5.10", "rect": {"x": 100, "y": 80, "w": 280, "h": 180}, "zone": "C"},
          {"i": 3, "kind": "ListItem", "name": "Celeste", "id": "5.11", "rect": {"x": 400, "y": 80, "w": 280, "h": 180}, "zone": "C"},
          {"i": 4, "kind": "ListItem", "name": "Hades", "id": "5.12", "rect": {"x": 700, "y": 80, "w": 280, "h": 180}, "zone": "C"}
         ]}
        """;

    private static JsonObject GridNarrowed(bool withList)
    {
        JsonObject view = View(GridBefore);
        var controls = (JsonArray)view["controls"]!;
        ((JsonObject)controls[0]!)["value"] = "Cuphead";
        controls.RemoveAt(4);
        controls.RemoveAt(3);
        if (!withList)
            controls.RemoveAt(1);
        return view;
    }

    [Test]
    public void TilesBesideTheResultInsideAListThatStayedNarrow()
    {
        JsonArray steps = Steps("Cuphead", "Buscar");
        Assert.That(ComputerUseSuccessCheck.SearchStart.Of("cuphead", Started(GridNarrowed(withList: true), View(GridBefore)), steps)!
            .Filtered, Is.True);
    }

    [Test]
    public void TilesBesideTheResultWithoutAListNarrowNothing()
    {
        JsonObject before = View(GridBefore);
        ((JsonArray)before["controls"]!).RemoveAt(1);
        JsonArray steps = Steps("Cuphead", "Buscar");
        Assert.That(ComputerUseSuccessCheck.SearchStart.Of("cuphead", Started(GridNarrowed(withList: false), before), steps)!
            .Filtered, Is.False);
    }

    // Revision 2 of r24b (P1): a filter in place on a list taller than the window. «Fotos» keeps id 7.11, the other
    // rows leave, and the footer's links that lay below the window's bottom come up under the list.
    private const string ListTallerThanTheWindow = """
        {"window": {"title": "Configuración", "process": "settings", "rect": {"x": 0, "y": 0, "w": 800, "h": __H__}},
         "controls": [
          {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
          {"i": 1, "kind": "ListItem", "name": "Calculadora", "id": "7.10", "rect": {"x": 100, "y": 100, "w": 600, "h": 40}, "zone": "C"},
          {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 140, "w": 600, "h": 40}, "zone": "C"},
          {"i": 3, "kind": "ListItem", "name": "Reloj", "id": "7.12", "rect": {"x": 100, "y": 180, "w": 600, "h": 40}, "zone": "C"},
          {"i": 4, "kind": "ListItem", "name": "Mapas", "id": "7.13", "rect": {"x": 100, "y": 220, "w": 600, "h": 80}, "zone": "C"}
         ],
         "controlCount": __N__,
         "text": {"T": ["Buscar aplicaciones"], "C": ["Calculadora", "Fotos", "Reloj", "Mapas"]}}
        """;

    private static JsonObject Narrowed(string arrivingKind) => View("""
        {"window": {"title": "Configuración", "process": "settings", "rect": {"x": 0, "y": 0, "w": 800, "h": 300}},
         "controls": [
          {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "Fotos", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
          {"i": 1, "kind": "Button", "name": "Borrar", "id": "7.2", "rect": {"x": 370, "y": 55, "w": 20, "h": 20}, "zone": "T"},
          {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 100, "w": 600, "h": 40}, "zone": "C"},
          {"i": 3, "kind": "__K__", "name": "Obtener ayuda", "id": "7.40", "rect": {"x": 100, "y": 160, "w": 150, "h": 20}, "zone": "C"},
          {"i": 4, "kind": "__K__", "name": "Enviar comentarios", "id": "7.41", "rect": {"x": 100, "y": 190, "w": 180, "h": 20}, "zone": "C"}
         ],
         "controlCount": 5,
         "text": {"T": ["Fotos"], "C": ["Fotos", "Obtener ayuda", "Enviar comentarios"]}}
        """.Replace("__K__", arrivingKind, StringComparison.Ordinal));

    private static JsonObject Taller(int height, int count) => View(ListTallerThanTheWindow
        .Replace("__H__", height.ToString(System.Globalization.CultureInfo.InvariantCulture), StringComparison.Ordinal)
        .Replace("__N__", count.ToString(System.Globalization.CultureInfo.InvariantCulture), StringComparison.Ordinal));

    [Test]
    public void AListTallerThanTheWindowThatNarrowsUncoversItsFooterAndPasses()
    {
        const string check = "stepDone:input.text.type&text:Fotos";
        JsonArray steps = Steps("Fotos", "Buscar aplicaciones");
        JsonObject judged = Started(Narrowed("Hyperlink"), Taller(300, 5));
        var enter = (JsonObject)steps[1]!;
        ComputerUseSuccessCheck.MarkSearchNothingNew(enter, judged, steps);
        Assert.Multiple(() =>
        {
            // The old reading, without the view the search started from, passed: no regression against it.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, Narrowed("Hyperlink"), steps, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", judged, steps)!.Filtered, Is.True,
                "the footer's links were below the window's bottom: uncovered, not born");
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Fotos", judged, steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, judged, steps, out _), Is.True);
            Assert.That(enter.ContainsKey("searchNothingNew"), Is.False, "the filter worked: the model is not told otherwise");
            // The listing's cap: a view that listed fewer controls than it had (no window rect to tell) is cut too.
            JsonObject capped = Taller(300, 9);
            ((JsonObject)capped["window"]!).Remove("rect");
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", Started(Narrowed("Hyperlink"), capped), steps)!.Filtered, Is.True);
        });
    }

    [Test]
    public void WhatArrivesUnderAListThatShowedItAllOrRowsOfItsKindAreBorn()
    {
        JsonArray steps = Steps("Fotos", "Buscar aplicaciones");
        Assert.Multiple(() =>
        {
            // Counter-case 1: the list ended above the window's bottom and the listing was whole: the links are new.
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", Started(Narrowed("Hyperlink"), Taller(600, 5)), steps)!.Filtered, Is.False);
            // Counter-case 2: rows of the list's own kind not bearing the query arrived: the list did not narrow to it.
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", Started(Narrowed("ListItem"), Taller(300, 5)), steps)!.Filtered, Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Fotos", Started(Narrowed("ListItem"), Taller(300, 5)), steps), Is.True);
        });
    }

    [Test]
    public void APageWideContainerHoldingTheBoxIsNoFrameOfIt()
    {
        // Counter-case of the box's frame: a pane holding the box and the list (twice as wide as the box) does not
        // hide what left the list.
        JsonObject before = Taller(600, 6);
        ((JsonArray)before["controls"]!).Add((JsonNode)new JsonObject
        {
            ["i"] = 5,
            ["kind"] = "Pane",
            ["name"] = "Aplicaciones",
            ["id"] = "7.0",
            ["rect"] = new JsonObject { ["x"] = 90, ["y"] = 40, ["w"] = 620, ["h"] = 270 },
        });
        JsonObject after = View("""
            {"window": {"title": "Configuración", "process": "settings", "rect": {"x": 0, "y": 0, "w": 800, "h": 600}},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar aplicaciones", "id": "7.1", "value": "Fotos", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 100, "w": 600, "h": 40}, "zone": "C"},
              {"i": 2, "kind": "Pane", "name": "Aplicaciones", "id": "7.0", "rect": {"x": 90, "y": 40, "w": 620, "h": 110}, "zone": "C"}
             ],
             "controlCount": 3,
             "text": {"T": ["Fotos"], "C": ["Fotos"]}}
            """);
        JsonArray steps = Steps("Fotos", "Buscar aplicaciones");
        Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", Started(after, before), steps)!.Filtered, Is.True);
    }

    // Revision 3 of r24b (finding 1, P1): a library read by OCR (g1). The entry was already shown before typing; the
    // filter adds a header and re-reads the counter. That is a filter in place: the check holds and the model is not
    // told the search brought nothing.
    [Test]
    public void AFilterThatAddsAHeaderOverItsResultsStillPasses()
    {
        const string check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:Cuphead";
        JsonObject before = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"T": ["Buscar por nombre"], "L": ["JUEGOS (1418)", "Celeste", "Cuphead", "Hades", "Hollow Knight"]}}
            """);
        JsonObject after = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"T": ["Cuphead"], "L": ["Resultados de la búsqueda", "JUEGOS (1/1418)", "Cuphead"]}}
            """);
        JsonArray steps = Steps("Cuphead", "Buscar por nombre");
        JsonObject judged = Started(after, before);
        var enter = (JsonObject)steps[1]!;
        ComputerUseSuccessCheck.MarkSearchNothingNew(enter, judged, steps);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("cuphead", judged, steps)!.Filtered, Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", judged, steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, judged, steps, out _), Is.True);
            Assert.That(enter.ContainsKey("searchNothingNew"), Is.False);
        });
    }

    // Counter-case: the zone lost as many lines as it gained (a slide that turned), so it was not filtered.
    [Test]
    public void AZoneThatGainedAsManyLinesAsItLostTurnedAndIsNoFilter()
    {
        JsonObject before = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"T": ["Buscar por nombre"], "L": ["Celeste", "Cuphead", "Hades"]}}
            """);
        JsonObject after = View("""
            {"window": {"title": "Biblioteca", "process": "client"}, "controls": [],
             "text": {"T": ["Cuphead"], "L": ["Ofertas de la semana", "Cuphead", "Novedades destacadas"]}}
            """);
        JsonArray steps = Steps("Cuphead", "Buscar por nombre");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("cuphead", Started(after, before), steps)!.Filtered, Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Cuphead", Started(after, before), steps), Is.True);
        });
    }

    // Revision 3 of r24b (finding 1, P2): a UIA list narrows to «Fotos» (same id) and a counter text is born over it with
    // a new id. Counter-case: the same counter is born, but only a text beside the list left and every row stayed.
    private const string SettingsBefore = """
        {"window": {"title": "Configuración", "process": "settings"},
         "controls": [
          {"i": 0, "kind": "Edit", "name": "Buscar", "id": "7.1", "value": "", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
          {"i": 1, "kind": "ListItem", "name": "Calculadora", "id": "7.10", "rect": {"x": 100, "y": 120, "w": 600, "h": 40}, "zone": "C"},
          {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 160, "w": 600, "h": 40}, "zone": "C"},
          {"i": 3, "kind": "ListItem", "name": "Reloj", "id": "7.12", "rect": {"x": 100, "y": 200, "w": 600, "h": 40}, "zone": "C"},
          {"i": 4, "kind": "Text", "name": "Sugerencia del día", "id": "7.20", "rect": {"x": 750, "y": 120, "w": 200, "h": 30}, "zone": "R"}
         ],
         "text": {"T": ["Buscar"], "C": ["Calculadora", "Fotos", "Reloj"], "R": ["Sugerencia del día"]}}
        """;

    [Test]
    public void AListThatNarrowsWithANewCounterOverItPasses()
    {
        const string check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:Fotos";
        JsonObject after = View("""
            {"window": {"title": "Configuración", "process": "settings"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "7.1", "value": "Fotos", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Text", "name": "1 aplicación encontrada", "id": "7.30", "rect": {"x": 100, "y": 90, "w": 300, "h": 20}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 120, "w": 600, "h": 40}, "zone": "C"},
              {"i": 3, "kind": "Text", "name": "Sugerencia del día", "id": "7.20", "rect": {"x": 750, "y": 120, "w": 200, "h": 30}, "zone": "R"}
             ],
             "text": {"T": ["Fotos", "1 aplicación encontrada"], "C": ["Fotos"], "R": ["Sugerencia del día"]}}
            """);
        JsonArray steps = Steps("Fotos", "Buscar");
        JsonObject judged = Started(after, View(SettingsBefore));
        var enter = (JsonObject)steps[1]!;
        ComputerUseSuccessCheck.MarkSearchNothingNew(enter, judged, steps);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", judged, steps)!.Filtered, Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, judged, steps, out _), Is.True);
            Assert.That(enter.ContainsKey("searchNothingNew"), Is.False);
        });
    }

    [Test]
    public void ANewCounterWhileOnlyATextBesideTheListLeftIsNoFilter()
    {
        const string check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:Fotos";
        JsonObject after = View("""
            {"window": {"title": "Configuración", "process": "settings"},
             "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar", "id": "7.1", "value": "Fotos", "rect": {"x": 100, "y": 50, "w": 300, "h": 30}, "zone": "T"},
              {"i": 1, "kind": "Text", "name": "1 aplicación encontrada", "id": "7.30", "rect": {"x": 100, "y": 90, "w": 300, "h": 20}, "zone": "T"},
              {"i": 2, "kind": "ListItem", "name": "Calculadora", "id": "7.10", "rect": {"x": 100, "y": 120, "w": 600, "h": 40}, "zone": "C"},
              {"i": 3, "kind": "ListItem", "name": "Fotos", "id": "7.11", "rect": {"x": 100, "y": 160, "w": 600, "h": 40}, "zone": "C"},
              {"i": 4, "kind": "ListItem", "name": "Reloj", "id": "7.12", "rect": {"x": 100, "y": 200, "w": 600, "h": 40}, "zone": "C"}
             ],
             "text": {"T": ["Fotos", "1 aplicación encontrada"], "C": ["Calculadora", "Fotos", "Reloj"]}}
            """);
        JsonArray steps = Steps("Fotos", "Buscar");
        JsonObject judged = Started(after, View(SettingsBefore));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("fotos", judged, steps)!.Filtered, Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, judged, steps, out _), Is.False);
        });
    }

    // Revision 3 of r24b (finding 2, P3): the Enter never reached the box; only a tooltip the pointer showed over the
    // rail went away. A tooltip is no row of the list the banner is in: no filter, and the old banner is no result.
    // Counter-case: a tile stacked under the banner (same kind, its columns) left, the list the banner is in narrowed.
    private const string StoreBefore = """
        {"window": {"title": "Tienda", "process": "store"},
         "controls": [
          {"i": 0, "kind": "Edit", "name": "Buscar", "id": "1.13", "value": "", "rect": {"x": 585, "y": 9, "w": 750, "h": 42}, "zone": "T"},
          {"i": 1, "kind": "ListItem", "name": "Inicio", "id": "1.19", "rect": {"x": 0, "y": 60, "w": 90, "h": 78}, "zone": "TL"},
          {"i": 2, "kind": "ToolTip", "name": "Inicio", "id": "9.1", "rect": {"x": 95, "y": 80, "w": 60, "h": 30}, "zone": "TL"},
          {"i": 3, "kind": "Hyperlink", "name": "Spotify - Music and Podcasts", "id": "1.50", "rect": {"x": 1194, "y": 76, "w": 680, "h": 382}, "zone": "TR"},
          {"i": 4, "kind": "Hyperlink", "name": "Netflix", "id": "1.51", "rect": {"x": 1194, "y": 474, "w": 332, "h": 188}, "zone": "R"}
         ]}
        """;

    [Test]
    public void ATooltipThatLeftIsNoFilterAndTheOldBannerIsNoResult()
    {
        JsonObject after = View(StoreBefore);
        var controls = (JsonArray)after["controls"]!;
        controls.RemoveAt(2);
        ((JsonObject)controls[0]!)["value"] = "Spotify";
        JsonArray steps = Steps("Spotify", "Buscar");
        JsonObject judged = Started(after, View(StoreBefore));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchStart.Of("spotify", judged, steps)!.Filtered, Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("Spotify", judged, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, judged, steps, out _), Is.False);
        });
    }

    [Test]
    public void ATileLinedUpWithTheBannerThatLeftNarrows()
    {
        JsonObject after = View(StoreBefore);
        var controls = (JsonArray)after["controls"]!;
        controls.RemoveAt(4);
        ((JsonObject)controls[0]!)["value"] = "Spotify";
        JsonArray steps = Steps("Spotify", "Buscar");
        Assert.That(ComputerUseSuccessCheck.SearchStart.Of("spotify", Started(after, View(StoreBefore)), steps)!.Filtered, Is.True);
    }
}
