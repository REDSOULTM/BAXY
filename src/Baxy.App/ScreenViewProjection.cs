using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// How the model reads a look at an application window (<c>input.visible.controls</c>): one line per control with the
/// index it clicks by, its kind, name, zone of the window (when the reader gave it) and state, after one line with the
/// place of the application the reader said is in sight and one with the controls the reader marked as selected or on,
/// then the text on screen grouped top, middle and bottom in reading
/// order. The reader's own bookkeeping is left out: version, ok, elapsedMs, authority, the name of the text's reader
/// (textAuthority; only its absence or its cut is said), and of the window its processId, its family of processes and the
/// process of the window covering it. The model acts by index or label, and a 4B reads a short text view far better
/// than a long JSON one (AgentOccam, ICLR 2025: the same agent +161 % from the observation alone; OSWorld and UFO2
/// filter the tree to visible, enabled, named controls).
/// Presentation only: every control the reader returned is kept, one it found several times once with «×N», N the
/// times it found it (the worker's «repeated» counts the copies after the first); every line of text the reader
/// returned is kept in its zone, a line that repeats included (a chat read by its lines repeats a bubble's text, and
/// two «ok» are two messages), except one that only repeats a listed control's name, left out and counted; nothing is
/// ranked or chosen, and what the reader said about its own reading stays said: a cut walk, a frame without content, a
/// tree it could not read, text it could not read, the disabled controls, the window being a modal dialog, protected or
/// run as administrator (audit 2026-10-15: those were dropped, and a cut walk read as «(ninguno)» with no cause).
/// </summary>
internal static class ScreenViewProjection
{
    /// <summary>
    /// The most places an application may have for a look to list its other places by name (sight_places). The data
    /// (ApplicationPlaces) give Discord 1, Epic Games Launcher and Spotify 3, Steam 5 and Configuración 52: 8 lists every
    /// launcher's few places on one short line, with room for a couple more, and never a list like Settings'.
    /// </summary>
    internal const int MaximumListedPlaces = 8;

    private static readonly (string Label, string[] Zones)[] Bands =
    [
        ("arriba", ["TL", "T", "TR"]),
        ("centro", ["L", "C", "R"]),
        ("abajo", ["BL", "B", "BR"]),
    ];

    // BAXY Renew al máximo 7.3 (A11y-Compressor; OSWorld, UFO2): where a control's centre sits in the window's 3×3
    // grid, in the words of the text's bands, so two «Buscar» or «el primer resultado» are told apart.
    private static readonly Dictionary<string, string> Zones = new(StringComparer.Ordinal)
    {
        ["TL"] = "arriba izq.", ["T"] = "arriba", ["TR"] = "arriba der.",
        ["L"] = "centro izq.", ["C"] = "centro", ["R"] = "centro der.",
        ["BL"] = "abajo izq.", ["B"] = "abajo", ["BR"] = "abajo der.",
    };

    /// <param name="message">The kernel's visible facts of the look (status, error, cause, effectUncertain).</param>
    /// <param name="result">The look's receipt: the whole view the reader returned.</param>
    /// <param name="asked">The application and place this turn's app.open asked for (Baxy.App.TurnPlace), if any.</param>
    internal static bool TryCreate(
        string message, JsonElement result, out string projected, (string Application, string Place)? asked = null)
    {
        projected = string.Empty;
        JsonObject? facts;
        JsonObject? view;
        try
        {
            facts = JsonNode.Parse(message) as JsonObject;
            view = JsonNode.Parse(result.GetRawText()) as JsonObject;
        }
        catch (JsonException)
        {
            return false;
        }

        if (facts is null || view?["controls"] is not JsonArray controls)
        {
            return false;
        }

        var text = new StringBuilder();
        if (view["window"] is JsonObject window)
        {
            // Its number is what the acting tools take as window, so they act in it and not in the person's window.
            text.Append("Ventana «").Append((string?)window["title"]).Append("» (").Append((string?)window["process"])
                .Append(", window ").Append((long?)window["hwnd"]).Append(')');
            // Said only as observed: a reader that did not report the front says nothing about it.
            text.Append((bool?)window["foreground"] switch
            {
                true => ", al frente",
                false => ", no está al frente",
                null => string.Empty,
            });
            if (window["coveredBy"] is JsonObject cover)
            {
                text.Append(", tapada por «").Append((string?)cover["title"]).Append('»');
            }

            if ((bool?)window["modal"] == true)
            {
                text.Append(", es el diálogo modal que bloquea la ventana");
            }

            // Ronda final 22 (regla 3): the look itself showed a minimized window; said, as it stays shown.
            if ((bool?)window["shownFromMinimized"] == true)
            {
                text.Append(", estaba minimizada: la mirada la mostró detrás de la de delante, sin activarla, y queda así");
            }

            if ((bool?)window["systemTool"] == true)
            {
                // Incidente del 2026-10-15: no name opens a system configuration tool to acts.
                text.Append(", herramienta de configuración del sistema (BAXY no pulsa ni escribe en ella: lo hace la persona)");
            }
            else if ((bool?)window["protected"] == true)
            {
                text.Append(", ventana protegida (no se actúa en ella; si es un editor o una terminal, sí cuando una mirada la nombra por su aplicación; la de BAXY, nunca)");
            }

            if ((bool?)window["elevated"] == true)
            {
                // The reader marks it when the window's process runs with more rights than BAXY or that could not be
                // read (VisibleControlSurface.RunsAboveUs).
                text.Append((bool?)window["reopensUnraised"] == true
                    ? ", corre como administrador o no se pudo comprobar (se puede reabrir sin permisos de administrador)"
                    : ", corre como administrador o no se pudo comprobar");
            }

            text.Append('\n');
            if (window["focused"] is JsonObject focused)
            {
                text.Append("Foco: ").Append(Control(focused));
                // Práctica V5E023: «agrega al final» typed at the start of the text, with nothing read saying where the
                // caret was. Where the reader found it, beside the focus; nothing when it did not read it.
                if (Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.CaretPlace)
                    && CaretNote((string?)focused["caret"]) is { } caret)
                {
                    text.Append(' ').Append(caret);
                }

                text.Append('\n');
                // Encargo 18 (banco de uso, U45): what the focused control that is no field shows (a console's output),
                // as the reader read it by accessibility, line by line; its cut keeps the last lines.
                if ((string?)focused["text"] is { Length: > 0 } shown)
                {
                    text.Append((bool?)focused["textCut"] == true
                            ? "Lo que muestra el foco (cortado: sólo sus últimas líneas):\n"
                            : "Lo que muestra el foco:\n")
                        .Append(shown).Append('\n');
                }
            }

            // Ajuste c3 (E017): Windows' common file dialog, as the provider read it by its structure (window.fileDialog).
            if (window["fileDialog"] is JsonObject fileDialog
                && Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.SaveDialogNext))
            {
                text.Append(FileDialogLine(fileDialog)).Append('\n');
            }
        }

        // BAXY Renew al máximo (F019, E015: Steam's library home, «Página principal», told «la página principal de
        // Steam» or «la tienda»): the place of the application the reader said is in sight, by the text only it shows.
        if (view["place"] is JsonObject place)
        {
            string? inSight = (string?)place["name"];
            text.Append("Lugar a la vista: ").Append(inSight).Append(" de ")
                .Append((string?)place["application"]).Append(" (sólo ahí sale «").Append((string?)place["shown"])
                .Append("»)");
            // Práctica e2e E014 («abre la configuración de sonido»): the look after app.open at sound, the same in the
            // runs that stopped there and in the one that went on for 15 calls, did not say the window was where it was
            // asked, and the model pressed «Sonido» in the breadcrumb of the page it was on. The place this turn's
            // app.open asked of this application is told against the one in sight, as a fact; when they are the same,
            // the other places (sight_places) are not said: nobody asked to go to them.
            bool arrived = false;
            if (Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.AskedPlace)
                && asked is { } wanted
                && Baxy.Kernel.Operations.ApplicationPlaces.SameApplication(wanted.Application, (string?)place["application"])
                // Revisión w11-rev4: a place asked that declares nothing it shows is never found in sight (a game's page
                // shows the store's address too): it is not told as the one in sight nor as not.
                && Baxy.Kernel.Operations.ApplicationPlaces.DeclaresShown(wanted.Application, wanted.Place))
            {
                arrived = string.Equals(wanted.Place, inSight, StringComparison.Ordinal);
                text.Append(arrived
                    ? ": es el que pidió app_open en este turno"
                    : ", no el que pidió app_open en este turno (" + wanted.Place + ")");
            }

            text.Append('\n');
            // Prueba en vivo de la versión final (renew_v6, «abre la biblioteca de Steam»): Steam opened cold with no
            // place; its places were told by app.open and after a failed look while it was still updating, and once its
            // store was in sight six looks said «Lugar a la vista: store» and nothing else, until the turn's 15 calls
            // ran out. Where the view says which place is in sight, it says beside it the application's other places
            // that app.open opens directly, from the data (ApplicationPlaces), as facts.
            // Revisión de nb-w11-quieto: an application with many places (Configuración, 52) would list them all, a
            // block that invites going to them; beyond MaximumListedPlaces only their number is said.
            string? application = (string?)place["application"];
            int otherCount = Baxy.Kernel.Operations.ApplicationPlaces.PlacesOf(application).Count(other => other.Place != inSight);
            if (!arrived && otherCount > 0
                && Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.SightPlaces))
            {
                if (otherCount + 1 > MaximumListedPlaces)
                {
                    text.Append('(').Append(application).Append(" se abre directo, sin pulsar, en otros ").Append(otherCount)
                        .Append(" lugares: app_open con appId «").Append(application).Append("» y su place)\n");
                }
                else
                {
                    text.Append("(los otros lugares de ").Append(application)
                        .Append(" se abren directo, sin pulsar: app_open con appId «").Append(application)
                        .Append("» y place ").Append(OtherPlaces(application, inSight)).Append(")\n");
                }
            }
        }

        // BAXY Renew al máximo P8.4 (sonda F019: «quedó en la tienda» with the library's tab selected): what the reader
        // marked as chosen (selected, or toggled on) is said first, before the reading order buries it between brackets.
        string[] chosen = controls.OfType<JsonObject>()
            .Where(static control => ((string?)control["state"] ?? string.Empty).Split(' ')
                .Any(static part => part is "selected" or "on"))
            .Select(static control => $"[{(int?)control["i"]}] {(string?)control["kind"]} «{(string?)control["name"]}»")
            .ToArray();
        if (chosen.Length > 0)
        {
            text.Append("Seleccionados o activados: ").Append(string.Join(" | ", chosen)).Append('\n');
        }

        int count = (int?)view["controlCount"] ?? controls.Count;
        bool drawn = controls.Count <= 1 && (string?)view["textAuthority"] == "windows_media_ocr_lines";
        // Renew al máximo (w9-dudas, falsedades F019): «no hay más botones en esa ventana» and «la ventana no muestra sus
        // botones» were told of Steam's library under «Controles:» / «(ninguno)», with the note that the list was not
        // whole only after it. Where the reader says its list is not whole, the heading says it, before any control.
        // Replayed on the notebook's int10 turns (scripts/renew/ayudas/dudas.py, 3 runs × 3 seeds): «no buttons» in the
        // first answer 4/9 → 1/9; in the follow-up, whose history already said it, 5/9 → 5/9.
        bool notWhole = Baxy.Providers.Windows.Infrastructure.ModelAids.On(
                Baxy.Providers.Windows.Infrastructure.ModelAids.ControlsNotComplete)
            && (drawn || count > controls.Count || (bool?)view["partial"] == true || (bool?)view["frameOnly"] == true
                || (string?)view["uiaFailed"] is { Length: > 0 });
        text.Append(notWhole ? "Controles (no es la lista completa de la ventana: puede tener más):\n" : "Controles:\n");
        foreach (JsonNode? node in controls)
        {
            if (node is JsonObject control)
            {
                text.Append(Control(control)).Append('\n');
            }
        }

        if (controls.Count == 0)
        {
            text.Append(notWhole ? "(no se leyó ninguno)\n" : "(ninguno)\n");
        }

        if (count > controls.Count)
        {
            text.Append("(+").Append(count - controls.Count).Append(" más, sin listar por el tope");
            // Uso-108 (B5): 47 cut views in the fleet's runs, 0 followed by a look with wanted: the line had no way out.
            if (Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.CutNamesWanted))
            {
                text.Append(": wanted los busca");
            }

            text.Append(")\n");
            // Uso-108 (B15): a look with wanted that found nothing looked just like one that found it past the cut.
            if (view["wantedMissing"] is JsonArray missing && missing.Count > 0
                && Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.WantedNotFound))
            {
                // Review 16, I3: a row scrolled out of the list is not walked: the fact is about what is in sight.
                text.Append("(ningún control a la vista lleva ")
                    .Append(string.Join(", ", missing.Select(static word => $"«{(string?)word}»"))).Append(" en su nombre)\n");
            }
        }

        // Renew al máximo (w8, falsedades F019): Steam's library read only by OCR, with no control or one, was told «hay
        // 324 juegos» from «FAVORITOS (324)» and «no hay botón de Biblioteca» while «BIBLIOTECA» was in its text (and a
        // click by that label pressed it). Such a window's text is what it shows: each line says only its own words, any
        // line is pressed by its label, and a word missing from «Controles» is not missing from the window.
        if (drawn && Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.DrawnTextNext))
        {
            text.Append("(esta ventana no da sus controles: su «Texto» se leyó de la pantalla tal cual, y cada línea dice "
                + "sólo lo que pone (un número junto a un nombre cuenta sólo lo de ese nombre); una línea de ahí se pulsa "
                + "por su texto, como label, y que algo no salga en «Controles» no significa que no esté)\n");
        }

        if (view["disabled"] is JsonArray disabled && disabled.Count > 0)
        {
            text.Append("Desactivados: ").Append(string.Join(" | ", disabled.OfType<JsonObject>()
                .Select(static control => $"{(string?)control["kind"]} «{(string?)control["name"]}»"))).Append('\n');
        }

        // Ronda final 20 (regla 3): disabled controls the look did not list are not controls that do not exist.
        if ((bool?)view["disabledCut"] == true)
        {
            text.Append("(puede haber controles desactivados sin listar)\n");
        }

        // What the reader said about its own reading.
        if ((bool?)view["partial"] == true)
        {
            text.Append("(la lectura quedó incompleta: puede haber más controles sin listar)\n");
        }

        if ((bool?)view["frameOnly"] == true)
        {
            text.Append("(sólo se leyó el marco de la ventana: sus controles no se pudieron leer)\n");
        }

        if ((string?)view["uiaFailed"] is { Length: > 0 } walkFailed)
        {
            text.Append("(no se pudo leer el árbol accesible de la ventana: ").Append(walkFailed).Append(")\n");
        }

        if ((string?)view["textAuthority"] == "unavailable")
        {
            text.Append("(no se pudo leer el texto en pantalla)\n");
        }

        // Ronda final 19 (regla 3): text not read, or read and cut, is said, never taken for what the window shows.
        if ((string?)view["textAuthority"] == "not_read")
        {
            text.Append("(el texto en pantalla no se leyó en esta mirada: se lee con includeText)\n");
        }

        if ((int?)view["textOmittedLines"] is > 0 and int omittedLines)
        {
            text.Append("(texto cortado: ").Append(omittedLines)
                .Append(" líneas leídas no se listan, por largas o pasado el tope");
            // Encargo LEC2: where what the cap left out lies, how much of it was a list's rows, and the look that reads it.
            if (view["textOmittedZones"] is JsonObject { Count: > 0 } cutZones)
            {
                text.Append("; fuera por el tope: ").Append(string.Join(", ", cutZones
                    .Where(static zone => Zones.ContainsKey(zone.Key) && (int?)zone.Value > 0)
                    .Select(static zone => $"{(int?)zone.Value} {Zones[zone.Key]}")));
                if ((int?)view["textOmittedListRows"] is > 0 and int listRows)
                {
                    text.Append(" (").Append(listRows).Append(" de ellas, filas de una lista de controles)");
                }

                if ((string?)view["textRestWith"] == "lines")
                {
                    text.Append("; se leen todas, cada una en su sitio, con lines");
                }
            }

            text.Append(")\n");
        }

        if (view["text"] is JsonObject zones)
        {
            // BAXY Renew al máximo 7.2 (A11y-Compressor; AgentOccam, table 10): a line that only repeats the name of a
            // control listed above says nothing new; it is left out and how many were is said, so a notice worded as a
            // button is never taken for absent.
            var listedNames = new HashSet<string>(
                controls.Concat(view["disabled"] as JsonArray ?? [])
                    .Select(static control => Folded((string?)control?["name"]))
                    .Where(static name => name.Length > 0),
                StringComparer.OrdinalIgnoreCase);
            int repeatedNames = 0;
            // uso-89 (diag-b5bd, R06, 5 of 6: «El del norte tiene la mejor calificación, 829» for the page's «El faro del
            // norte - calificacion 8,9»): text read by OCR beside the controls an application gives says what it is.
            // Windows.Media.Ocr gives each line's text and box and no confidence (OcrLine, OcrWord: Text, BoundingRect),
            // while a control's name is what the application itself exposes (UI Automation's Name). A line that is a
            // listed control's name misread (its letters and its digits a few edits from that name's: «calificaclon 829»
            // for «calificacion 8,9») is that control's text read worse: left out and counted, as an exact repeat is
            // (held-out h1, the page's ListItems beside the OCR: the 6 answers of 20 made from the look took the OCR's
            // «1.750» for the ListItem's «10.750», with the note and without it).
            // What stays is said once, before it (a window drawn without controls has its own note above).
            bool recognized = !drawn && (string?)view["textAuthority"] == "windows_media_ocr_lines"
                && Baxy.Providers.Windows.Infrastructure.ModelAids.On(
                    Baxy.Providers.Windows.Infrastructure.ModelAids.ScreenTextRecognized);
            (string Letters, string Digits)[] listedShapes = recognized
                ? controls.Concat(view["disabled"] as JsonArray ?? [])
                    .Select(static control => Shape((string?)control?["name"]))
                    .Where(static shape => shape.Letters.Length >= MisreadMinimumLetters)
                    .ToArray()
                : [];
            int misreadNames = 0;
            List<string> Kept(JsonArray read)
            {
                var lines = new List<string>();
                foreach (JsonNode? line in read)
                {
                    if ((string?)line is not { Length: > 0 } value)
                    {
                        continue;
                    }

                    if (listedNames.Contains(Folded(value)))
                    {
                        repeatedNames++;
                    }
                    else if (listedShapes.Length > 0 && Misreads(Shape(value), listedShapes))
                    {
                        misreadNames++;
                    }
                    else
                    {
                        lines.Add(value);
                    }
                }

                return lines;
            }

            // Encargo LEC3: the text as it is read on screen, by columns and blocks (WindowsVisibleOcrLocator.ReadingColumns),
            // so an author line stays with its message and the last block seen is told as such; the bands of the 3×3 grid
            // are for a look without them.
            var bands = new List<(string Label, List<string> Lines)>();
            bool byColumns = false;
            if (view["textColumns"] is JsonArray { Count: > 0 } textColumns)
            {
                // A column, beside others, whose lines are half or more names of listed controls is a list's (Encargo
                // LEC2's ListRows): what is left of it goes on one line, with no «last» of its own.
                bool besideOthers = textColumns.Count > 1;
                var columns = textColumns.OfType<JsonObject>()
                    .Select(column =>
                    {
                        List<JsonArray> read = [.. (column["blocks"] as JsonArray ?? []).OfType<JsonArray>()];
                        int lines = read.Sum(static block => block.Count);
                        List<List<string>> blocks = [.. read.Select(Kept).Where(static block => block.Count > 0)];
                        bool list = besideOthers && lines >= 5 && (lines - blocks.Sum(static block => block.Count)) * 2 >= lines;
                        return (Zone: (string?)column["zone"], ToBottomEdge: (bool?)column["toBottomEdge"] == true, List: list,
                            Blocks: list && blocks.Count > 0 ? [[.. blocks.SelectMany(static block => block)]] : blocks);
                    })
                    .Where(static column => column.Blocks.Count > 0)
                    .ToList();
                for (int c = 0; c < columns.Count; c++)
                {
                    string where = columns[c].Zone switch { "L" => "izq.", "R" => "der.", _ => "centro" };
                    string column = columns.Count == 1 ? string.Empty : $"columna {c + 1} ({where}), ";
                    if (columns[c].List)
                    {
                        bands.Add(($"{column}lo que queda de una lista de controles", columns[c].Blocks[0]));
                        continue;
                    }

                    for (int b = 0; b < columns[c].Blocks.Count; b++)
                    {
                        string label = $"{column}bloque {b + 1}";
                        if (b == columns[c].Blocks.Count - 1 && columns[c].ToBottomEdge)
                        {
                            label += b == 0
                                ? ", cortado por el borde de abajo: sigue más abajo sin verse"
                                : ", el último que se ve, cortado por el borde de abajo: sigue más abajo sin verse";
                        }
                        else if (b == columns[c].Blocks.Count - 1 && b > 0)
                        {
                            label += columns.Count == 1 ? ", el último que se ve" : ", el último que se ve en esa columna";
                        }

                        bands.Add((label, columns[c].Blocks[b]));
                    }
                }

                byColumns = bands.Count > 0;
            }
            else
            {
                foreach ((string label, string[] bandZones) in Bands)
                {
                    var lines = new List<string>();
                    foreach (string zone in bandZones)
                    {
                        if (zones[zone] is JsonArray zoneLines)
                        {
                            lines.AddRange(Kept(zoneLines));
                        }
                    }

                    bands.Add((label, lines));
                }
            }

            foreach ((string label, List<string> lines) in bands)
            {
                if (lines.Count > 0)
                {
                    if (recognized)
                    {
                        text.Append("(el «Texto» se reconoció de la imagen de la ventana (OCR): puede leer mal letras y "
                            + "cifras, como una coma decimal tomada por un dígito; lo que nombran los controles lo da la "
                            + "propia aplicación y manda sobre ese texto)\n");
                        if (view["textLanguages"] is JsonArray { Count: > 0 } languages)
                        {
                            // Encargo 119: nonsense told as a read when the text is in an alphabet the OCR does not have.
                            text.Append("(ese OCR sólo reconoce ").Append(string.Join(", ", languages.Select(static tag => (string?)tag)))
                                .Append(": un texto en otro alfabeto sale como letras sin sentido; entonces di que no se pudo leer)\n");
                        }

                        recognized = false;
                    }

                    if (byColumns)
                    {
                        text.Append("(el «Texto» va como se lee en pantalla: por columnas, de izquierda a derecha, y cada "
                            + "columna de arriba abajo, en bloques; un salto grande o un cambio de sangría separa un bloque del "
                            + "siguiente, y la línea corta de encima de un bloque (un nombre, una hora) va con él; lo de arriba "
                            + "del todo y el último bloque son lo que se ve: si la vista se desplaza, puede haber más)\n");
                        byColumns = false;
                    }

                    text.Append("Texto ").Append(label).Append(": ").Append(string.Join(" | ", lines)).Append('\n');
                }
            }

            if (repeatedNames > 0)
            {
                text.Append('(').Append(repeatedNames)
                    .Append(" líneas de texto no se listan: repiten el nombre de un control listado)\n");
            }

            if (misreadNames > 0)
            {
                text.Append('(').Append(misreadNames)
                    .Append(" líneas del texto reconocido no se listan: repetían el nombre de un control listado con "
                        + "letras o cifras mal leídas)\n");
            }
        }

        if ((string?)view["error"] is { Length: > 0 } error)
        {
            text.Append("Error: ").Append(error).Append('\n');
        }

        // The kernel's facts of the look travel whole (status, error, cause, effectUncertain included); only what it
        // observed is re-presented, as the view, made from the whole receipt: the kernel's mark that its own copy of the
        // observation was cut (observedLimit) does not describe this view.
        var projection = new JsonObject();
        foreach ((string key, JsonNode? fact) in facts)
        {
            if (key is not ("observed" or "observedLimit"))
            {
                projection[key] = fact?.DeepClone();
            }
        }

        projection["view"] = text.ToString().TrimEnd();
        projected = projection.ToJsonString(new JsonSerializerOptions
        {
            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        });
        return true;
    }

    // Ajuste c3 (E017): Windows' common file dialog as the provider read it by its structure (CommonFileDialog), whatever
    // the look listed and whatever the language: the folder its address shows, what its name field holds and the path
    // they make, that a whole path written there saves or opens there, and the button that confirms. In E017 the model
    // pressed «Guardar» with the field holding the text's first words, or typed «lista.txt» with the dialog in its last
    // folder, and said it saved in the folder asked: the address bar was past the look's limit (10 or 15 controls).
    private static string FileDialogLine(JsonObject dialog)
    {
        var line = new StringBuilder("Diálogo de archivos de Windows: carpeta ");
        if ((string?)dialog["folder"] is { Length: > 0 } folder)
        {
            line.Append('«').Append(folder).Append('»');
        }
        else if ((string?)dialog["shown"] is { Length: > 0 } shown)
        {
            line.Append('«').Append(shown).Append("» (no es una carpeta del disco)");
        }
        else
        {
            line.Append("sin leer");
        }

        if (dialog["name"] is JsonNode name)
        {
            line.Append("; su campo de nombre");
            if ((int?)dialog["nameIndex"] is int nameIndex)
            {
                line.Append(" [").Append(nameIndex).Append(']');
            }

            line.Append(" tiene «").Append((string?)name).Append('»');
            if ((string?)dialog["path"] is { Length: > 0 } path)
            {
                line.Append(", que daría ").Append(path);
            }

            line.Append("; una ruta entera escrita en ese campo (C:\\…\\nombre.ext) guarda o abre ahí sin recorrer carpetas");
        }

        line.Append("; «").Append((string?)dialog["accept"]).Append('»');
        if ((int?)dialog["acceptIndex"] is int acceptIndex)
        {
            line.Append(" [").Append(acceptIndex).Append(']');
        }

        return line.Append(" lo confirma").ToString();
    }

    // The places of the application other than the one in sight, sorted, each with what its placeValue takes (as
    // AppOpenHandler.PlacesNext says them); empty for an application with no other place.
    private static string OtherPlaces(string? application, string? inSight) => string.Join(", ",
        Baxy.Kernel.Operations.ApplicationPlaces.PlacesOf(application)
            .Where(place => place.Place != inSight)
            .Select(static place => place.Takes switch
            {
                "query" => $"{place.Place} (placeValue: lo que se busca)",
                "game" or "slug" => $"{place.Place} (placeValue: el nombre del juego)",
                _ => place.Place,
            }));

    // Where the reader (DesktopUiaWorker.ps1, Get-CaretPlace) found the caret of a focused edit or document with text,
    // its TextPattern selection against the whole text; null for anything else, the reader having said nothing.
    private static string? CaretNote(string? caret) => caret switch
    {
        "start" => "(cursor al principio del texto: lo que se escriba va antes de lo que ya tiene)",
        "end" => "(cursor al final del texto: lo que se escriba va después de lo que ya tiene)",
        "middle" => "(cursor en medio del texto: lo que se escriba va ahí, ni al principio ni al final)",
        "selection" => "(hay texto seleccionado: lo que se escriba lo reemplaza)",
        _ => null,
    };

    /// <summary>uso-89: the fewest letters a control's name has for an OCR line to be read as that name misread.</summary>
    internal const int MisreadMinimumLetters = 8;

    // uso-89: a line's letters (folded: lower case, no accents) and its digits, apart: OCR misreads the one and the other
    // in their own ways (rn→m, l↔i; a decimal comma read as a digit or lost).
    private static (string Letters, string Digits) Shape(string? text)
    {
        var letters = new StringBuilder();
        var digits = new StringBuilder();
        foreach (char c in (text ?? string.Empty).Normalize(NormalizationForm.FormD))
        {
            if (char.IsDigit(c))
            {
                digits.Append(c);
            }
            else if (char.IsLetter(c))
            {
                letters.Append(char.ToLowerInvariant(c));
            }
        }

        return (letters.ToString(), digits.ToString());
    }

    // A line is a listed name misread when its letters are within a fifth of that name's (in edits) and its digits within
    // two, and no more edits than the name has digits: «El del norte - calificaclon 829» is «El faro del norte -
    // calificacion 8,9»; «Pedido 5678» is not «Pedido 1234», and «Sólo instalados (3)» beside the check box «Sólo
    // instalados» says a count the name does not, so it stays.
    private static bool Misreads((string Letters, string Digits) line, (string Letters, string Digits)[] names)
    {
        if (line.Letters.Length < MisreadMinimumLetters)
        {
            return false;
        }

        foreach ((string letters, string digits) in names)
        {
            int longest = Math.Max(letters.Length, line.Letters.Length);
            if (Math.Abs(letters.Length - line.Letters.Length) * 5 > longest
                || Math.Abs(digits.Length - line.Digits.Length) > 2)
            {
                continue;
            }

            if (Edits(letters, line.Letters) * 5 <= longest
                && Edits(digits, line.Digits) <= Math.Min(2, digits.Length))
            {
                return true;
            }
        }

        return false;
    }

    private static int Edits(string a, string b)
    {
        var previous = new int[b.Length + 1];
        var current = new int[b.Length + 1];
        for (int j = 0; j <= b.Length; j++)
        {
            previous[j] = j;
        }

        for (int i = 1; i <= a.Length; i++)
        {
            current[0] = i;
            for (int j = 1; j <= b.Length; j++)
            {
                current[j] = Math.Min(Math.Min(current[j - 1], previous[j]) + 1,
                    previous[j - 1] + (a[i - 1] == b[j - 1] ? 0 : 1));
            }

            (previous, current) = (current, previous);
        }

        return previous[b.Length];
    }

    private static string Folded(string? text) => string.Join(' ',
        (text ?? string.Empty).Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));

    private static string Control(JsonObject control)
    {
        var line = new StringBuilder();
        line.Append('[').Append((int?)control["i"]).Append("] ").Append((string?)control["kind"]).Append(" «")
            .Append((string?)control["name"]).Append('»');
        // R6-NB-5: a long name is cut whole at its end, and the view says how much of it is missing.
        if ((int?)control["nameCut"] is > 0 and int cut)
        {
            line.Append(" (nombre cortado: faltan ").Append(cut).Append(" caracteres)");
        }

        // Only when the reader gave one: a control without its rectangle has no zone.
        if ((string?)control["zone"] is { } zone && Zones.TryGetValue(zone, out string? place))
        {
            line.Append(" (").Append(place).Append(')');
        }

        if ((string?)control["value"] is { Length: > 0 } value)
        {
            line.Append(" = ").Append(value);
            // Uso-108 (A7): a long value is cut at 120 by the reader; a prefix that reads whole is a false value.
            if ((int?)control["valueCut"] is > 0 and int valueCut)
            {
                line.Append(" (valor cortado: faltan ").Append(valueCut).Append(" caracteres)");
            }
        }

        if ((string?)control["state"] is { Length: > 0 } state)
        {
            line.Append(" (").Append(state).Append(')');
        }

        // BAXY Renew cu (C11): what the application says the item is (Excel's «1» is «Encabezado de fila»).
        if ((string?)control["itemType"] is { Length: > 0 } itemType)
        {
            line.Append(" (tipo: ").Append(itemType).Append(')');
        }

        // The worker counts the copies after the first (DesktopUiaWorker.ps1, $seen[$key].repeated): found three
        // times it says 2, and the view says the three.
        if ((int?)control["repeated"] is > 0 and int copies)
        {
            line.Append(" ×").Append(copies + 1);
        }

        if ((string?)control["shortcut"] is { Length: > 0 } shortcut)
        {
            line.Append(" [atajo ").Append(shortcut).Append(']');
        }

        return line.ToString();
    }
}
