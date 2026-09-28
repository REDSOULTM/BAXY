using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M53 (paso 6 del goal v3, D35, estudio R8): una receta con nombre o el argumento de una
// obra concreta no se recitan de memoria: el 4B mezclaba plantillas (pan de banana sin
// plátano, pastel de choclo como bizcocho, El hobbit con el Anillo Único). La mente los
// manda a web.search con una consulta que lleva su palabra de clase («receta …»,
// «resumen …»); esta fuente lee la fuente abierta que los trae:
//   - receta → Wikilibros: es.wikibooks «Artes culinarias/Recetas/…» (plantilla «Datos de
//     receta») y en.wikibooks «Cookbook:…» (espacio 102). TextExtracts se come las
//     plantillas y las tablas, así que se lee el wikitexto de la página;
//   - argumento → la sección «Argumento»/«Plot» del artículo de Wikipedia de la obra
//     (texto plano con las cabeceras marcadas), recortada a ≤ 1 500 caracteres.
// Todo sale por la API de MediaWiki, sin clave, con el User-Agent de D32; sale sólo la
// consulta. CC BY-SA: la página va en «url» y la App la muestra como enlace «fuente»
// bajo el mensaje (D35), nunca en la prosa.
internal sealed class WikimediaReferenceSource(HttpClient http)
{
    internal const int EvidenceCharacters = 1_500;
    private static readonly TimeSpan RequestTimeout = TimeSpan.FromSeconds(2.5);
    private const string SpanishRecipePrefix = "Artes culinarias/Recetas/";
    private const string EnglishRecipePrefix = "Cookbook:";

    private readonly HttpClient _http = http ?? throw new ArgumentNullException(nameof(http));

    internal enum ReferenceKind
    {
        Recipe,
        Plot,
        Ranking,
    }

    // Subject: las palabras que nombran el plato o la obra, en el orden dicho; Named: las
    // que el título tiene que llevar (el sujeto sin los sustantivos de clase de obra).
    internal readonly record struct ReferenceAsk(ReferenceKind Kind, string[] Subject, string[] Named);

    internal readonly record struct ReferenceReading(
        string Title,
        string Url,
        string Evidence,
        string Authority,
        int? Servings);

    internal static string Authority(string project, string language) => project + "_" + language + "_api";

    internal static string KindName(ReferenceKind kind) => kind switch
    {
        ReferenceKind.Recipe => "recipe",
        ReferenceKind.Plot => "plot",
        _ => "ranking",
    };

    private static readonly HashSet<string> RecipeCues = new(StringComparer.Ordinal)
    {
        "receta", "recetas", "recipe", "recipes", "ingredientes", "ingrediente", "ingredients", "ingredient",
    };

    private static readonly HashSet<string> PlotCues = new(StringComparer.Ordinal)
    {
        "argumento", "trama", "sinopsis", "plot", "synopsis",
    };

    // «el libro del Hobbit»: la clase de la obra ayuda a buscar, pero el título no la lleva.
    private static readonly HashSet<string> WorkNouns = new(StringComparer.Ordinal)
    {
        "libro", "libros", "novela", "novelas", "pelicula", "peliculas", "peli", "pelis", "serie", "series", "obra",
        "saga", "cuento", "book", "books", "novel", "novels", "movie", "movies", "film", "films", "show", "play",
    };

    // La consulta la escribe la mente (semantic.knowledge.reference_lookup): una palabra de
    // clase y el referente. Sin referente no hay nada que consultar.
    internal static ReferenceAsk? Parse(string query)
    {
        string[] words = WebBrowserAdapter.SearchTokens(query);
        if (words.Length > 0 && words[0] == "ranking")
        {
            // «ranking objetos brillantes del cielo nocturno»: what is ranked and by what come
            // first (the list's title carries them); the rest only helps the search.
            string[] ranked = words[1..];
            return ranked.Length >= 2 ? new ReferenceAsk(ReferenceKind.Ranking, ranked, ranked[..2]) : null;
        }
        bool recipe = words.Any(RecipeCues.Contains);
        bool plot = !recipe && words.Any(static word =>
            PlotCues.Contains(word) || word.StartsWith("resum", StringComparison.Ordinal)
            || word.StartsWith("summar", StringComparison.Ordinal));
        if (!recipe && !plot) return null;
        string[] subject = words
            .Where(static word => !RecipeCues.Contains(word) && !PlotCues.Contains(word)
                && !word.StartsWith("resum", StringComparison.Ordinal)
                && !word.StartsWith("summar", StringComparison.Ordinal))
            .ToArray();
        string[] named = recipe ? subject : subject.Where(static word => !WorkNouns.Contains(word)).ToArray();
        if (named.Length == 0) return null;
        return new ReferenceAsk(recipe ? ReferenceKind.Recipe : ReferenceKind.Plot, subject, named);
    }

    // La palabra de clase que escribió la mente está en el idioma de la persona («receta»,
    // «resumen» / «recipe», «summary»): ese proyecto se pregunta primero.
    private static readonly HashSet<string> EnglishCues = new(StringComparer.Ordinal)
    {
        "recipe", "recipes", "ingredients", "ingredient", "plot", "synopsis",
    };

    internal static string[] CueLanguages(string query, string[] languages)
    {
        string[] words = WebBrowserAdapter.SearchTokens(query);
        bool english = words.Any(static word =>
            EnglishCues.Contains(word) || word.StartsWith("summar", StringComparison.Ordinal));
        bool spanish = words.Any(static word =>
            (RecipeCues.Contains(word) && !EnglishCues.Contains(word))
            || word is "argumento" or "trama" or "sinopsis"
            || word.StartsWith("resum", StringComparison.Ordinal));
        return english == spanish ? languages : english ? ["en", "es"] : ["es", "en"];
    }

    internal Task<ReferenceReading?> ReadAsync(ReferenceAsk ask, string[] languages, CancellationToken cancellationToken) =>
        ask.Kind switch
        {
            ReferenceKind.Recipe => ReadRecipeAsync(ask, languages, cancellationToken),
            ReferenceKind.Plot => ReadPlotAsync(ask, languages, cancellationToken),
            _ => ReadRankingAsync(ask, languages, cancellationToken),
        };

    // ------------------------------------------------------------------ recetas

    internal static Uri RecipeSearchUri(string language, string terms)
    {
        string search = language == "es" ? terms + " prefix:" + SpanishRecipePrefix : terms;
        string space = language == "es" ? "0" : "102";
        return new Uri("https://" + language + ".wikibooks.org/w/api.php"
            + "?action=query&format=json&formatversion=2"
            + "&generator=search&gsrnamespace=" + space + "&gsrlimit=5"
            + "&gsrsearch=" + Uri.EscapeDataString(search)
            + "&prop=revisions%7Cinfo&rvprop=content&rvslots=main&inprop=url");
    }

    // El nombre del plato en inglés, leído del enlace entre idiomas del artículo español
    // que lo describe («Pan de banana» → «Banana bread»): el Cookbook sólo está en inglés.
    internal static Uri EnglishNameUri(string terms) =>
        new("https://es.wikipedia.org/w/api.php?action=query&format=json&formatversion=2"
            + "&generator=search&gsrnamespace=0&gsrlimit=1&gsrsearch=" + Uri.EscapeDataString(terms)
            + "&prop=langlinks&lllang=en");

    private async Task<ReferenceReading?> ReadRecipeAsync(
        ReferenceAsk ask, string[] languages, CancellationToken cancellationToken)
    {
        string terms = string.Join(' ', ask.Subject);
        using var siblings = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        // Mientras se pregunta el recetario español se lee, en paralelo, el nombre inglés
        // del plato: si el español no lo tiene, el inglés se pregunta sin esperar otra vuelta.
        Task<string?>? englishName = languages[0] == "es"
            ? ReadEnglishNameAsync(terms, ask.Named, siblings.Token)
            : null;
        try
        {
            string? englishAsked = null;
            foreach (string language in languages)
            {
                // The English book was already asked with these very words (the dish's English name).
                if (language == "en" && string.Equals(englishAsked, terms, StringComparison.Ordinal)) continue;
                ReferenceReading? found = await ReadRecipePageAsync(language, terms, ask.Named, cancellationToken)
                    .ConfigureAwait(false);
                if (found is not null) return found;
                if (language == "es" && englishName is not null)
                {
                    string? name = await englishName.ConfigureAwait(false);
                    englishName = null;
                    if (name is not null)
                    {
                        string[] words = WebBrowserAdapter.SearchTokens(name);
                        englishAsked = string.Join(' ', words);
                        ReferenceReading? translated = await ReadRecipePageAsync("en", name, words, cancellationToken)
                            .ConfigureAwait(false);
                        if (translated is not null) return translated;
                    }
                }
            }
            return null;
        }
        finally
        {
            await siblings.CancelAsync().ConfigureAwait(false);
        }
    }

    private async Task<ReferenceReading?> ReadRecipePageAsync(
        string language, string terms, string[] named, CancellationToken cancellationToken)
    {
        string? body = await GetAsync(RecipeSearchUri(language, terms), cancellationToken).ConfigureAwait(false);
        if (body is null) return null;
        try
        {
            return ParseRecipeResponse(body, language, named);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private async Task<string?> ReadEnglishNameAsync(string terms, string[] named, CancellationToken cancellationToken)
    {
        string? body = await GetAsync(EnglishNameUri(terms), cancellationToken).ConfigureAwait(false);
        if (body is null) return null;
        try
        {
            return ParseEnglishName(body, named);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    internal static string? ParseEnglishName(string body, string[] named)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        foreach (JsonElement page in Pages(document.RootElement))
        {
            // El artículo tiene que ser del plato («Pan de banana»), no de algo que lo nombra.
            if (!TitleCarries(StringOf(page, "title"), named)) continue;
            if (page.TryGetProperty("langlinks", out JsonElement links) && links.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement link in links.EnumerateArray())
                {
                    string title = StringOf(link, "title");
                    if (StringOf(link, "lang") == "en" && title.Length is > 0 and <= 256) return title;
                }
            }
        }
        return null;
    }

    // De las páginas de la búsqueda, la receta cuyo nombre es el plato pedido: todas sus
    // palabras en el título; primero la que no añade nada («Sopaipilla» antes que
    // «Sopaipillas pasadas»), después el puesto en la búsqueda. Una página sin
    // ingredientes o sin pasos (un índice de variantes) no es la receta.
    internal static ReferenceReading? ParseRecipeResponse(string body, string language, string[] named)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        string prefix = language == "es" ? SpanishRecipePrefix : EnglishRecipePrefix;
        string host = language + ".wikibooks.org";
        var candidates = new List<(int Extra, int Index, string Title, string Url, string Wikitext)>();
        foreach (JsonElement page in Pages(document.RootElement))
        {
            string title = StringOf(page, "title");
            if (!title.StartsWith(prefix, StringComparison.Ordinal)) continue;
            string name = title[prefix.Length..];
            if (!TitleCarries(name, named)) continue;
            string url = StringOf(page, "fullurl");
            if (!Uri.TryCreate(url, UriKind.Absolute, out Uri? parsed)
                || parsed.Scheme != Uri.UriSchemeHttps
                || !string.Equals(parsed.Host, host, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            string wikitext = page.TryGetProperty("revisions", out JsonElement revisions)
                && revisions.ValueKind == JsonValueKind.Array && revisions.GetArrayLength() > 0
                && revisions[0].TryGetProperty("slots", out JsonElement slots)
                && slots.TryGetProperty("main", out JsonElement main)
                ? StringOf(main, "content")
                : string.Empty;
            int extra = NameWords(name).Count(word => !named.Any(asked =>
                WebBrowserAdapter.MatchesSearchTerm(word, [asked]) || WebBrowserAdapter.MatchesSearchTerm(asked, [word])));
            int index = page.TryGetProperty("index", out JsonElement position) && position.TryGetInt32(out int value)
                ? value : int.MaxValue;
            candidates.Add((extra, index, name, parsed.AbsoluteUri, wikitext));
        }
        foreach ((_, _, string name, string url, string wikitext) in candidates
            .OrderBy(static item => item.Extra).ThenBy(static item => item.Index))
        {
            Recipe? recipe = language == "es" ? SpanishRecipe(wikitext) : EnglishRecipe(wikitext);
            if (recipe is null) continue;
            return new ReferenceReading(
                name, url, RecipeEvidence(name, recipe.Value, language), Authority("wikibooks", language), recipe.Value.Servings);
        }
        return null;
    }

    internal readonly record struct Recipe(string[] Ingredients, string[] Steps, int? Servings, string Description);

    // es.wikibooks: {{Artes culinarias/Datos de receta |comensales= |ingredientes= * … |procedimiento= # …}}
    internal static Recipe? SpanishRecipe(string wikitext)
    {
        // «Sopaipilla» keeps the template's blank example inside a comment, above the real one.
        wikitext = WithoutComments(wikitext);
        string? template = TemplateBody(wikitext, "Artes culinarias/Datos de receta");
        if (template is null) return null;
        Dictionary<string, string> parameters = TemplateParameters(template);
        string[] ingredients = ListItems(parameters.GetValueOrDefault("ingredientes") ?? string.Empty, '*');
        string[] steps = ListItems(parameters.GetValueOrDefault("procedimiento") ?? string.Empty, '#');
        if (ingredients.Length < 2 || steps.Length == 0) return null;
        int? servings = ServingsOf(parameters.GetValueOrDefault("comensales"));
        string? info = TemplateBody(wikitext, "Artes culinarias/Información receta");
        string prose = info is not null ? info.TrimStart('|') : ProseAfterTemplates(wikitext);
        // «Pastel de choclo»: the photo above the template says which variant it writes
        // («Pastel dulce de choclo (Perú). Variante dulce, sin relleno y con pasas.»).
        string caption = LeadCaption(wikitext[..Math.Max(0, wikitext.IndexOf(template, StringComparison.Ordinal))]);
        return new Recipe(ingredients, steps, servings, Sentences(
            string.Join(' ', new[] { caption, PlainWikiText(prose) }.Where(static part => part.Length > 0)), 400));
    }

    // en.wikibooks: {{recipesummary | Servings = …}} y las secciones «Ingredients» (lista o
    // tabla) y «Procedure»/«Directions»/«Method».
    internal static Recipe? EnglishRecipe(string wikitext)
    {
        wikitext = WithoutComments(wikitext);
        Dictionary<string, string> sections = Sections(wikitext);
        string? ingredientsText = FirstSection(sections, "ingredients");
        string? stepsText = FirstSection(sections, "procedure", "directions", "method", "preparation", "instructions", "steps");
        if (ingredientsText is null || stepsText is null) return null;
        string[] ingredients = ingredientsText.Contains("{|", StringComparison.Ordinal)
            ? TableIngredients(ingredientsText)
            : ListItems(ingredientsText, '*');
        string[] steps = ListItems(stepsText, '#');
        if (ingredients.Length < 2 || steps.Length == 0) return null;
        string? summary = TemplateBody(wikitext, "recipesummary") ?? TemplateBody(wikitext, "Recipe summary");
        int? servings = summary is null ? null : ServingsOf(TemplateParameters(summary).GetValueOrDefault("servings"));
        return new Recipe(ingredients, steps, servings, Sentences(PlainWikiText(ProseAfterTemplates(
            sections.GetValueOrDefault(string.Empty) ?? string.Empty)), 300));
    }

    // La evidencia que lee el redactor: qué es, los ingredientes (con sus porciones si la
    // página las dice) y los pasos numerados, en ≤ 1 500 caracteres; los pasos que no
    // caben se cortan enteros y se dice que siguen.
    internal static string RecipeEvidence(string name, Recipe recipe, string language)
    {
        bool spanish = language == "es";
        var text = new StringBuilder();
        if (recipe.Description.Length > 0) text.Append(recipe.Description).Append('\n');
        text.Append(spanish ? "Ingredientes" : "Ingredients");
        if (recipe.Servings is int servings)
            text.Append(spanish ? " (para " + servings + " personas)" : " (serves " + servings + ")");
        text.Append(":\n");
        foreach (string ingredient in recipe.Ingredients) text.Append("- ").Append(ingredient).Append('\n');
        text.Append(spanish ? "Preparación:\n" : "Procedure:\n");
        for (int index = 0; index < recipe.Steps.Length; index++)
        {
            string line = (index + 1).ToString(CultureInfo.InvariantCulture) + ". " + recipe.Steps[index] + "\n";
            if (text.Length + line.Length > EvidenceCharacters)
            {
                text.Append(spanish ? "(la página sigue con más pasos)" : "(the page continues with more steps)");
                break;
            }
            text.Append(line);
        }
        return text.ToString().TrimEnd();
    }

    private static string[] TableIngredients(string section)
    {
        var rows = new List<string>();
        int start = section.IndexOf("{|", StringComparison.Ordinal);
        int end = section.IndexOf("|}", start, StringComparison.Ordinal);
        string table = end > start ? section[(start + 2)..end] : section[(start + 2)..];
        foreach (string row in table.Split("|-"))
        {
            var cells = new List<string>();
            foreach (string rawLine in row.Split('\n'))
            {
                string line = rawLine.Trim();
                if (!line.StartsWith('|') || line.StartsWith("|+", StringComparison.Ordinal)) continue;
                foreach (string cell in line[1..].Split("||"))
                {
                    string value = PlainWikiText(CellValue(cell));
                    cells.Add(value);
                }
            }
            string[] filled = cells.Where(static cell => cell.Length > 0).ToArray();
            if (filled.Length < 2 || filled[0].StartsWith("total", StringComparison.OrdinalIgnoreCase)) continue;
            // Ingrediente, y su primera medida (unidades, volumen o peso); los porcentajes de
            // panadero no son cantidades para cocinar.
            string measure = filled.Skip(1).FirstOrDefault(static cell => !cell.EndsWith('%')) ?? string.Empty;
            if (measure.Length > 0) rows.Add(measure + " " + filled[0]);
        }
        return rows.ToArray();
    }

    // «style="…" | contenido»: el contenido es lo que sigue al último separador de atributos.
    private static string CellValue(string cell)
    {
        int bar = cell.IndexOf('|', StringComparison.Ordinal);
        if (bar > 0 && cell[..bar].Contains('=', StringComparison.Ordinal) && !cell[..bar].Contains("[[", StringComparison.Ordinal))
        {
            return cell[(bar + 1)..];
        }
        return cell;
    }

    // ------------------------------------------------------------------ argumento de una obra

    internal static Uri PlotUri(string language, string terms) =>
        new("https://" + language + ".wikipedia.org/w/api.php?action=query&format=json&formatversion=2"
            + "&generator=search&gsrnamespace=0&gsrlimit=1&gsrsearch=" + Uri.EscapeDataString(terms)
            + "&prop=extracts%7Cinfo%7Cpageprops&explaintext=1&exsectionformat=wiki&inprop=url&ppprop=disambiguation");

    private async Task<ReferenceReading?> ReadPlotAsync(
        ReferenceAsk ask, string[] languages, CancellationToken cancellationToken)
    {
        string terms = string.Join(' ', ask.Subject);
        foreach (string language in languages)
        {
            string? body = await GetAsync(PlotUri(language, terms), cancellationToken).ConfigureAwait(false);
            if (body is null) continue;
            try
            {
                if (ParsePlotResponse(body, language, ask.Named) is { } found) return found;
            }
            catch (JsonException)
            {
            }
        }
        return null;
    }

    private static readonly string[] PlotHeadings =
    [
        "argumento", "sinopsis", "trama", "resumen", "plot", "synopsis", "plot summary", "summary", "story", "premise",
    ];

    // El primer resultado tiene que ser la obra (todas las palabras de su nombre en el
    // título); se lee su sección de argumento o, si no la tiene, su introducción.
    internal static ReferenceReading? ParsePlotResponse(string body, string language, string[] named)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        string host = language + ".wikipedia.org";
        foreach (JsonElement page in Pages(document.RootElement))
        {
            if (page.TryGetProperty("pageprops", out JsonElement props) && props.ValueKind == JsonValueKind.Object
                && props.TryGetProperty("disambiguation", out _))
            {
                continue;
            }
            string title = StringOf(page, "title");
            string url = StringOf(page, "fullurl");
            if (!TitleCarries(title, named)
                || !Uri.TryCreate(url, UriKind.Absolute, out Uri? parsed)
                || parsed.Scheme != Uri.UriSchemeHttps
                || !string.Equals(parsed.Host, host, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            string evidence = PlotEvidence(StringOf(page, "extract"));
            if (evidence.Length == 0) continue;
            return new ReferenceReading(title, parsed.AbsoluteUri, evidence, WikipediaSearchSource.Authority(language), null);
        }
        return null;
    }

    internal static string PlotEvidence(string extract)
    {
        string text = extract.Replace("​", string.Empty, StringComparison.Ordinal);
        var headings = Regex.Matches(text, @"^(=+)\s*(.+?)\s*=+\s*$", RegexOptions.Multiline);
        string chosen = headings.Count > 0 ? text[..headings[0].Index] : text;
        for (int index = 0; index < headings.Count; index++)
        {
            Match heading = headings[index];
            if (heading.Groups[1].Value.Length != 2) continue;
            string name = string.Join(' ', WikipediaSearchSource.FoldedWords(heading.Groups[2].Value));
            if (!PlotHeadings.Contains(name)) continue;
            int end = text.Length;
            for (int next = index + 1; next < headings.Count; next++)
            {
                if (headings[next].Groups[1].Value.Length <= 2)
                {
                    end = headings[next].Index;
                    break;
                }
            }
            chosen = Regex.Replace(text[(heading.Index + heading.Length)..end], @"^=+.*=+\s*$", string.Empty, RegexOptions.Multiline);
            break;
        }
        return Sentences(string.Join(' ', chosen.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)), EvidenceCharacters);
    }

    // ------------------------------------------------------------------ listas con cifras

    // es.wikipedia guarda sus listas en el espacio «Anexo» (104); en.wikipedia, como «List of …».
    internal static Uri RankingSearchUri(string language, string terms) =>
        new("https://" + language + ".wikipedia.org/w/api.php?action=query&format=json&formatversion=2"
            + "&generator=search&gsrlimit=3&gsrnamespace=" + (language == "es" ? "104" : "0")
            + "&gsrsearch=" + Uri.EscapeDataString(language == "es" ? terms : "intitle:list " + terms)
            + "&prop=revisions%7Cinfo&rvprop=content&rvslots=main&inprop=url");

    private async Task<ReferenceReading?> ReadRankingAsync(
        ReferenceAsk ask, string[] languages, CancellationToken cancellationToken)
    {
        string terms = string.Join(' ', ask.Subject);
        foreach (string language in languages)
        {
            string? body = await GetAsync(RankingSearchUri(language, terms), cancellationToken).ConfigureAwait(false);
            if (body is null) continue;
            try
            {
                if (ParseRankingResponse(body, language, ask.Named) is { } found) return found;
            }
            catch (JsonException)
            {
            }
        }
        return null;
    }

    // La lista cuyo título lleva lo que se ordena y por qué («Anexo:Estrellas más
    // brillantes», «List of brightest stars»); se lee su primera tabla, fila a fila, en su
    // orden. Una tabla ilegible no es una respuesta: nada se inventa.
    internal static ReferenceReading? ParseRankingResponse(string body, string language, string[] named)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        string host = language + ".wikipedia.org";
        // The list that adds least to what was asked first («tallest buildings» before
        // «tallest residential buildings»), then the search's order.
        foreach (JsonElement page in Pages(document.RootElement)
            .OrderBy(page => NameWords(StringOf(page, "title")).Count(word => !named.Any(asked =>
                WebBrowserAdapter.MatchesSearchTerm(word, [asked]) || WebBrowserAdapter.MatchesSearchTerm(asked, [word])))))
        {
            string title = StringOf(page, "title");
            string name = Regex.Replace(title, @"^(?:Anexo:|List of |Lists of )", string.Empty, RegexOptions.IgnoreCase);
            string url = StringOf(page, "fullurl");
            // A list, not an article that mentions one («History of the world's tallest buildings»).
            if (name.Length == title.Length
                || !TitleCarries(name, named)
                || !Uri.TryCreate(url, UriKind.Absolute, out Uri? parsed)
                || parsed.Scheme != Uri.UriSchemeHttps
                || !string.Equals(parsed.Host, host, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            string wikitext = page.TryGetProperty("revisions", out JsonElement revisions)
                && revisions.ValueKind == JsonValueKind.Array && revisions.GetArrayLength() > 0
                && revisions[0].TryGetProperty("slots", out JsonElement slots)
                && slots.TryGetProperty("main", out JsonElement main)
                ? StringOf(main, "content")
                : string.Empty;
            string? table = TableEvidence(name, WithoutComments(wikitext));
            if (table is not null)
            {
                return new ReferenceReading(name, parsed.AbsoluteUri, table, WikipediaSearchSource.Authority(language), null);
            }
        }
        return null;
    }

    // La primera tabla «wikitable»: su cabecera y sus filas en orden, cada una con sus
    // primeras celdas no vacías, hasta 1 500 caracteres. Null con menos de tres filas.
    internal static string? TableEvidence(string name, string wikitext)
    {
        Match open = Regex.Match(wikitext, @"^\{\|[^\n]*wikitable[^\n]*$", RegexOptions.Multiline);
        if (!open.Success) return null;
        int end = wikitext.IndexOf("\n|}", open.Index, StringComparison.Ordinal);
        string table = wikitext[(open.Index + open.Length)..(end > open.Index ? end : wikitext.Length)];
        var header = new List<string>();
        var rows = new List<string>();
        foreach (string row in Regex.Split(table, @"^\|-[^\n]*$", RegexOptions.Multiline))
        {
            var cells = new List<string>();
            bool headed = false;
            bool data = false;
            foreach (string rawLine in row.Split('\n'))
            {
                string line = rawLine.Trim();
                if (line.Length == 0 || line.StartsWith("|+", StringComparison.Ordinal)) continue;
                char marker = line[0];
                if (marker is not ('|' or '!')) continue;
                headed |= marker == '!';
                data |= marker == '|';
                foreach (string cell in line[1..].Split(marker == '!' ? "!!" : "||"))
                {
                    string value = PlainWikiText(CellValue(cell));
                    // «_row_count» and the like are the table's machinery, not a value.
                    if (value.Length is > 0 and <= 200 && !value.StartsWith('_')) cells.Add(value);
                }
            }
            if (cells.Count == 0) continue;
            if (headed && !data && rows.Count == 0)
            {
                header.AddRange(cells);
                continue;
            }
            rows.Add(string.Join(" — ", cells.Take(5)));
        }
        if (rows.Count < 3) return null;
        var text = new StringBuilder(name).Append('\n');
        if (header.Count > 0) text.Append(string.Join(" — ", header.Take(6))).Append('\n');
        foreach (string row in rows)
        {
            if (text.Length + row.Length + 1 > EvidenceCharacters) break;
            text.Append(row).Append('\n');
        }
        return text.ToString().TrimEnd();
    }

    // ------------------------------------------------------------------ comunes

    private async Task<string?> GetAsync(Uri uri, CancellationToken cancellationToken)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(RequestTimeout);
        using var request = new HttpRequestMessage(HttpMethod.Get, uri);
        request.Headers.TryAddWithoutValidation("User-Agent", WikipediaSearchSource.UserAgent);
        try
        {
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, timeout.Token)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode) return null;
            return await WebBrowserAdapter.ReadBoundedTextAsync(response, 2_000_000, timeout.Token).ConfigureAwait(false);
        }
        catch (HttpRequestException)
        {
            return null;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
    }

    private static JsonElement[] Pages(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object) throw new JsonException("Not a MediaWiki answer.");
        if (root.TryGetProperty("error", out _)) throw new JsonException("MediaWiki answered an error.");
        if (!root.TryGetProperty("query", out JsonElement query)
            || !query.TryGetProperty("pages", out JsonElement pages)
            || pages.ValueKind != JsonValueKind.Array)
        {
            return [];
        }
        return pages.EnumerateArray()
            .Where(static page => page.ValueKind == JsonValueKind.Object)
            .OrderBy(static page => page.TryGetProperty("index", out JsonElement index) && index.TryGetInt32(out int value)
                ? value : int.MaxValue)
            .ToArray();
    }

    private static string StringOf(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    // Las palabras del nombre de una página, sin el numeral romano de sus variantes
    // («Banana Bread I», «Banana Bread III»).
    private static string[] NameWords(string name) =>
        WebBrowserAdapter.SearchTokens(Regex.Replace(name, @"\s+[IVX]{1,4}$", string.Empty));

    private static bool TitleCarries(string title, string[] named)
    {
        var words = new HashSet<string>(NameWords(title), StringComparer.Ordinal);
        return named.Length > 0 && named.All(word => WebBrowserAdapter.MatchesSearchTerm(word, words));
    }

    // El cuerpo de la primera plantilla con ese nombre, llaves anidadas incluidas.
    internal static string? TemplateBody(string wikitext, string name)
    {
        Match open = Regex.Match(wikitext, @"\{\{\s*" + Regex.Escape(name).Replace(@"\ ", @"[ _]") + @"\s*(?=[|}\n])",
            RegexOptions.IgnoreCase);
        if (!open.Success) return null;
        int depth = 1;
        int position = open.Index + open.Length;
        while (position < wikitext.Length - 1)
        {
            if (wikitext[position] == '{' && wikitext[position + 1] == '{')
            {
                depth++;
                position += 2;
            }
            else if (wikitext[position] == '}' && wikitext[position + 1] == '}')
            {
                depth--;
                if (depth == 0) return wikitext[(open.Index + open.Length)..position];
                position += 2;
            }
            else
            {
                position++;
            }
        }
        return null;
    }

    // Parámetros con nombre de una plantilla, partidos sólo en las barras de primer nivel.
    internal static Dictionary<string, string> TemplateParameters(string body)
    {
        var parameters = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var current = new StringBuilder();
        int braces = 0;
        int brackets = 0;
        void Flush()
        {
            string part = current.ToString();
            current.Clear();
            int equals = part.IndexOf('=', StringComparison.Ordinal);
            if (equals <= 0) return;
            string key = part[..equals].Trim();
            if (key.Length is > 0 and <= 64) parameters[key] = part[(equals + 1)..];
        }
        for (int index = 0; index < body.Length; index++)
        {
            char character = body[index];
            char next = index + 1 < body.Length ? body[index + 1] : '\0';
            if (character == '{' && next == '{') { braces++; current.Append("{{"); index++; continue; }
            if (character == '}' && next == '}') { braces--; current.Append("}}"); index++; continue; }
            if (character == '[' && next == '[') { brackets++; current.Append("[["); index++; continue; }
            if (character == ']' && next == ']') { brackets--; current.Append("]]"); index++; continue; }
            if (character == '|' && braces == 0 && brackets == 0)
            {
                Flush();
                continue;
            }
            current.Append(character);
        }
        Flush();
        return parameters;
    }

    // Los elementos de una lista de wikitexto («* …» o «# …»), en texto plano.
    private static string[] ListItems(string text, char marker) =>
        text.Split('\n')
            .Select(static line => line.Trim())
            .Where(line => line.Length > 1 && line[0] == marker && line[1] != ':')
            .Select(line => PlainWikiText(line.TrimStart(marker, '*', '#', ' ')))
            .Where(static item => item.Length > 0)
            .ToArray();

    // Las secciones de nivel 2 por su título plegado; la clave vacía es lo que va antes.
    private static Dictionary<string, string> Sections(string wikitext)
    {
        var sections = new Dictionary<string, string>(StringComparer.Ordinal);
        MatchCollection headings = Regex.Matches(wikitext, @"^==\s*([^=\n]+?)\s*==\s*$", RegexOptions.Multiline);
        sections[string.Empty] = headings.Count > 0 ? wikitext[..headings[0].Index] : wikitext;
        for (int index = 0; index < headings.Count; index++)
        {
            int start = headings[index].Index + headings[index].Length;
            int end = index + 1 < headings.Count ? headings[index + 1].Index : wikitext.Length;
            string name = string.Join(' ', WikipediaSearchSource.FoldedWords(headings[index].Groups[1].Value));
            sections.TryAdd(name, wikitext[start..end]);
        }
        return sections;
    }

    private static string? FirstSection(Dictionary<string, string> sections, params string[] names) =>
        names.Select(name => sections.GetValueOrDefault(name)).FirstOrDefault(static text => text is not null);

    private static int? ServingsOf(string? value)
    {
        if (value is null) return null;
        Match number = Regex.Match(value, @"^\s*(\d{1,3})\b");
        return number.Success && int.TryParse(number.Groups[1].Value, NumberStyles.None, CultureInfo.InvariantCulture, out int servings)
            && servings > 0
            ? servings
            : null;
    }

    // La prosa de la página fuera de sus plantillas y tablas (su descripción).
    private static string ProseAfterTemplates(string wikitext)
    {
        string text = wikitext;
        for (int guard = 0; guard < 20; guard++)
        {
            string reduced = Regex.Replace(text, @"\{\{[^{}]*\}\}|\{\|[\s\S]*?\|\}", string.Empty);
            if (reduced == text) break;
            text = reduced;
        }
        return string.Join(' ', text.Split('\n')
            .Select(static line => line.Trim())
            .Where(static line => line.Length > 0 && !line.StartsWith("==", StringComparison.Ordinal)
                && !line.StartsWith("__", StringComparison.Ordinal) && !line.StartsWith('*')
                && !line.StartsWith('#') && !line.StartsWith('|') && !line.StartsWith("[[Cat", StringComparison.OrdinalIgnoreCase)));
    }

    private static readonly Regex ImageOption = new(
        @"^(?:thumb|thumbnail|miniatura|miniaturadeimagen|mini|derecha|izquierda|centro|right|left|center|none|"
        + @"frame|marco|frameless|sinmarco|upright(?:=.*)?|border|borde|\d+(?:x\d+)?px|alt=.*|link=.*|vínculo=.*)$",
        RegexOptions.IgnoreCase);

    // El pie de la primera imagen de ese tramo de wikitexto, en texto plano; vacío si no hay.
    internal static string LeadCaption(string wikitext)
    {
        Match image = Regex.Match(wikitext, @"\[\[(?:Archivo|File|Imagen|Image):([^\[\]]*(?:\[\[[^\[\]]*\]\][^\[\]]*)*)\]\]",
            RegexOptions.IgnoreCase);
        if (!image.Success) return string.Empty;
        string[] parts = TemplateParts(image.Groups[1].Value);
        string caption = parts.Skip(1).LastOrDefault(part => !ImageOption.IsMatch(part.Trim())) ?? string.Empty;
        return PlainWikiText(caption);
    }

    // Partes separadas por barras de primer nivel (fuera de [[…]] y {{…}}).
    private static string[] TemplateParts(string body)
    {
        var parts = new List<string>();
        var current = new StringBuilder();
        int depth = 0;
        for (int index = 0; index < body.Length; index++)
        {
            char character = body[index];
            char next = index + 1 < body.Length ? body[index + 1] : '\0';
            if ((character == '[' && next == '[') || (character == '{' && next == '{')) depth++;
            if ((character == ']' && next == ']') || (character == '}' && next == '}')) depth--;
            if (character == '|' && depth == 0)
            {
                parts.Add(current.ToString());
                current.Clear();
                continue;
            }
            current.Append(character);
        }
        parts.Add(current.ToString());
        return parts.ToArray();
    }

    private static string WithoutComments(string wikitext) =>
        Regex.Replace(wikitext, @"<!--[\s\S]*?(?:-->|$)", string.Empty);

    // Wikitexto a texto: {{ing|X}} y {{coc|X}} (ingrediente y técnica de cocina) → X,
    // [[a|b]] → b, sin ficheros, categorías, citas, etiquetas ni negritas.
    internal static string PlainWikiText(string wikitext)
    {
        string text = Regex.Replace(WithoutComments(wikitext), @"<ref[^>/]*/>|<ref[^>]*>[\s\S]*?</ref>", string.Empty,
            RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"\[\[(?:Archivo|File|Imagen|Image|Categor[ií]a|Category):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]",
            string.Empty, RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"<math[^>]*>[\s\S]*?</math>", string.Empty, RegexOptions.IgnoreCase);
        // The value templates of list tables keep their value («{{val|-1.46}}», «{{sort|k|Sirio}}»).
        text = Regex.Replace(text, @"\{\{\s*(?:val|nts|nowrap|small|formatnum)\s*\|([^{}|]*)(?:\|[^{}]*)?\}\}", "$1",
            RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"\{\{\s*sort\s*\|[^{}|]*\|([^{}|]*)\}\}", "$1", RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"\{\{\s*formatnum\s*:\s*([^{}|]*)\}\}", "$1", RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"\{\{\s*convert\s*\|([^{}|]*)\|([^{}|]*)(?:\|[^{}]*)?\}\}", "$1 $2",
            RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"\{\{\s*(?:ing|coc)\s*\|([^{}|]*)(?:\|([^{}]*))?\}\}",
            static match => match.Groups[2].Success && match.Groups[2].Value.Trim().Length > 0
                ? match.Groups[2].Value
                : match.Groups[1].Value, RegexOptions.IgnoreCase);
        for (int guard = 0; guard < 10; guard++)
        {
            string reduced = Regex.Replace(text, @"\{\{[^{}]*\}\}", string.Empty);
            if (reduced == text) break;
            text = reduced;
        }
        text = Regex.Replace(text, @"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]", "$1");
        text = Regex.Replace(text, @"\[https?://\S+\s+([^\]]*)\]", "$1");
        text = Regex.Replace(text, @"<[^>]+>", string.Empty);
        text = text.Replace("'''", string.Empty, StringComparison.Ordinal)
            .Replace("''", string.Empty, StringComparison.Ordinal)
            .Replace("&nbsp;", " ", StringComparison.Ordinal)
            .Replace("​", string.Empty, StringComparison.Ordinal);
        return string.Join(' ', text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)).Trim();
    }

    // Hasta «limit» caracteres cortando en el final de una frase (o de una palabra).
    internal static string Sentences(string text, int limit)
    {
        string trimmed = text.Trim();
        if (trimmed.Length <= limit) return trimmed;
        string head = trimmed[..limit];
        int end = Math.Max(head.LastIndexOf(". ", StringComparison.Ordinal), head.LastIndexOf(".\n", StringComparison.Ordinal));
        if (end >= limit / 3) return head[..(end + 1)];
        int space = head.LastIndexOf(' ');
        return (space > 0 ? head[..space] : head) + "…";
    }
}
