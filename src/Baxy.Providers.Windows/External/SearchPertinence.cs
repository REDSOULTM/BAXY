namespace Baxy.Providers.Windows.External;

// M51 (revisión de la corrida v3a-final, 2026-09-28): Wikipedia y el RSS de noticias
// devuelven lo que comparte UNA palabra con la consulta, y la respuesta se escribía con
// eso: «any new status updates» contestó con «HTTP 301», «gas stations in Buford» con
// un pueblo fantasma de Wyoming, «números ganadores del loto» con el artículo de Baloto.
// Un resultado de estas fuentes sólo vuelve si trata de lo preguntado:
//   - los nombres propios de la consulta (palabras con mayúscula que no abren la frase)
//     están todos en el título o el extracto; sin nombre propio, alguna palabra de
//     contenido está en el título, porque un artículo o un titular trata de su título;
//   - y el título más el extracto repiten las palabras de contenido: todas si son una
//     o dos, la mayoría estricta si son más;
//   - M98: y, cuando hay nombres, lo que se pregunta de ellos (las otras palabras de
//     contenido) también está, o el resultado sólo nombra de quién se pregunta.
// Si ningún resultado pasa, esa fuente no respondió.
internal static class SearchPertinence
{
    // Lo que pide, pregunta o dice dónde mirar, no qué: verbos de pedir, relleno,
    // verbos de relación («quién escribió», «who wrote»), «internet», «wikipedia» y
    // las palabras de actualidad y de precio.
    private static readonly HashSet<string> FrameWords = new(StringComparer.Ordinal)
    {
        "show", "tell", "give", "get", "got", "find", "look", "lookup", "list", "me", "us",
        "something", "anything", "any", "some", "there", "new", "info", "information", "want",
        "need", "know", "like", "let", "only", "just", "also", "much", "many", "have",
        "has", "had", "wrote", "written", "write", "writes", "invented", "discovered",
        "founded", "directed", "painted", "composed", "won", "played", "starred", "starring",
        "muestra", "muestrame", "mostrar", "ensename", "dime", "decime", "dame", "pasame",
        "pasa", "encuentra", "encuentrame", "encontrar", "buscame", "buscarme", "informacion",
        "algo", "alguna", "alguno", "algun", "quiero", "quisiera", "necesito", "saber",
        "puedes", "podrias", "puede", "solo", "solamente", "tambien", "cuanto", "cuanta",
        "cuantos", "cuantas", "tiene", "tienen", "tener", "sale", "vale", "valen", "cuesta",
        "cuestan", "escribio", "escribe", "escrito", "invento", "descubrio", "fundo",
        "dirigio", "pinto", "compuso", "gano", "ganaron",
        // M98: el auxiliar de «quién ha ganado» y la preposición de «distancia entre Lima y
        // Cusco» no son de qué trata la página («el clásico entre equipos de Lima y Cusco»).
        "ha", "han", "he", "hemos", "entre", "between", "desde", "hasta", "hacia",
        "internet", "web", "google", "bing", "duckduckgo", "wikipedia", "online", "net",
        // Lo que dice que es de hoy o que es un precio: un titular lo cuenta con otras
        // palabras («cotiza», «a cuánto está»), y el tema es lo demás.
        "latest", "news", "recent", "noticia", "noticias", "ultima", "ultimas", "ultimo",
        "ultimos", "actualidad", "precio", "precios", "price", "prices", "cost", "costs",
        "cotizacion",
    };

    // Las palabras de contenido que identifican la consulta, plegadas y sin repetir.
    internal static string[] ContentTerms(string query) =>
        WebBrowserAdapter.SearchTokens(query)
            .Where(static token => !FrameWords.Contains(token))
            .ToArray();

    // Los nombres propios: palabras escritas con mayúscula que no abren la frase
    // («who wrote Dracula», «capital de Australia»). «I» no es un nombre.
    internal static string[] EntityTerms(string query)
    {
        var entities = new List<string>();
        bool opening = true;
        foreach (string raw in query.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries))
        {
            string word = raw.TrimStart('¿', '¡', '"', '\'', '«', '(', '“');
            if (word.Length > 0 && !opening && char.IsUpper(word[0]))
            {
                foreach (string token in WikipediaSearchSource.FoldedWords(word))
                {
                    if (token.Length >= 2 && !FrameWords.Contains(token)
                        && ContentTerms(token).Length > 0 && !entities.Contains(token))
                    {
                        entities.Add(token);
                    }
                }
            }
            if (word.Length > 0) opening = word[^1] is '.' or '?' or '!' or ':';
        }
        return entities.ToArray();
    }

    internal static bool IsPertinent(string query, string title, string snippet) =>
        Judge(query, title, snippet) == Pertinence.About;

    internal enum Pertinence
    {
        None,
        // The names the query gives are there, and what it asks of them is not.
        NamesOnly,
        About,
    }

    // M98 (DEV-D v3x D-s111 «¿Cuál es la distancia de Barcelona a París?» → the article on a Barcelona–PSG match,
    // D-p24-t1 «a nice fantasy movie like Elijah Wood» → three films of his, none of fantasy): the query's names
    // made the majority of its words, and a page that only names them passed. What the query asks of those names
    // (its other content words: «distancia», «fantasy») is in the result too, the majority of them, or the result
    // only names what was asked about. A year the query names (D-w14-t1 «… la Vuelta 2026», SearchQueryYear) is
    // in the result as a name is: a headline of last year's race is not about this year's.
    internal static Pertinence Judge(string query, string title, string snippet)
    {
        Pertinence judged = JudgeWords(query, title, snippet);
        return judged == Pertinence.About && OneWorkOfTheCounted(query, title) ? Pertinence.NamesOnly : judged;
    }

    // Ronda 19 (r17 t2-c01 T4 «cuantos discos de estudio tienen los bunkers?» → the article «Los Bunkers (álbum)»,
    // judged About, answered with one record's page): a title «Entity (kind of work …)» is the page of ONE work. A
    // question that counts works of that kind («cuántos discos») is about the entity, not about one of them: such a
    // page only names what is asked about, unless the question names that kind of work for itself («cuántas canciones
    // tiene el álbum …»). A question that is not a count («¿de qué álbum es Ven aquí?» → «Ven aquí (canción de Los
    // Bunkers)») keeps the work's own page, and so does a count of anything but works of that kind, which asks what
    // the work itself has («cuántos premios ganó Titanic» → «Titanic (película de 1997)», «cuántas temporadas tiene
    // Dark» → «Dark (serie de televisión)», «cuántas canciones tiene Thriller» → «Thriller (álbum)»).
    private static readonly string[][] WorkKinds =
    [
        ["album", "disco", "lp", "ep"],
        ["cancion", "tema", "sencillo", "single", "song"],
        ["pelicula", "filme", "film", "movie"],
        ["serie", "series", "show"],
        ["novela", "libro", "novel", "book"],
        ["videojuego", "juego", "game"],
        ["gira", "tour"],
    ];

    private static readonly string[] CountHeads = ["cuantos", "cuantas", "how many", "number of", "numero de", "cantidad de"];

    // The entity a work-qualified title is the work of («Los Bunkers (álbum)» → «Los Bunkers»), or null.
    internal static string? WorkQualifiedEntity(string title)
    {
        int open = title.LastIndexOf('(');
        if (open <= 0 || !title.TrimEnd().EndsWith(')')) return null;
        string[] qualifier = WikipediaSearchSource.FoldedWords(title[(open + 1)..]);
        return qualifier.Length > 0 && KindOf(qualifier[0]) is not null ? title[..open].Trim() : null;
    }

    // Revisión r19: the entity's own page is the one whose title is the entity's name AND that describes what the
    // work's page says its maker is («Los Bunkers (álbum)»: «… de la banda de rock chilena …» → «Los Bunkers»: «…
    // banda de rock chilena …»): two content words besides the name are shared. A namesake that is something else (a
    // town, a ship, another work of the name) shares the name only and is judged as any other result; a
    // disambiguation page never reaches here (WikipediaSearchSource.ParseSearchResponse drops it).
    private const int SharedDescriptionWords = 2;

    internal static bool OwnPageOfTheWork(string workTitle, string workSnippet, string title, string snippet)
    {
        if (WorkQualifiedEntity(workTitle) is not { } entity
            || string.Join(' ', WikipediaSearchSource.FoldedWords(title)) != string.Join(' ', WikipediaSearchSource.FoldedWords(entity)))
        {
            return false;
        }
        var named = new HashSet<string>(WikipediaSearchSource.FoldedWords(entity), StringComparer.Ordinal);
        var described = new HashSet<string>(WikipediaSearchSource.FoldedWords(snippet), StringComparer.Ordinal);
        return ContentTerms(workSnippet)
            .Where(word => !named.Contains(word) && !word.All(char.IsAsciiDigit))
            .Count(word => WebBrowserAdapter.MatchesSearchTerm(word, described)) >= SharedDescriptionWords;
    }

    private static string[]? KindOf(string word) =>
        WorkKinds.FirstOrDefault(kind => kind.Any(name => word == name || word == name + "s" || word == name + "es"));

    internal static bool AsksACount(string query)
    {
        string folded = " " + string.Join(' ', WikipediaSearchSource.FoldedWords(query)) + " ";
        return CountHeads.Any(head => folded.Contains(" " + head + " ", StringComparison.Ordinal));
    }

    private static bool OneWorkOfTheCounted(string query, string title)
    {
        if (WorkQualifiedEntity(title) is null || !AsksACount(query)) return false;
        string[] qualifier = WikipediaSearchSource.FoldedWords(title[(title.LastIndexOf('(') + 1)..]);
        string[] kind = KindOf(qualifier[0])!;
        string[] words = WikipediaSearchSource.FoldedWords(query);
        // The word counted is the one right after the count head; naming the kind there is counting the works.
        var counted = new HashSet<int>();
        for (int index = 0; index < words.Length; index++)
        {
            bool head = words[index] is "cuantos" or "cuantas"
                || (index > 0 && (words[index - 1], words[index]) is ("how", "many") or ("number", "of") or ("numero", "de")
                    or ("cantidad", "de"));
            if (head && index + 1 < words.Length) counted.Add(index + 1);
        }
        // What is counted must be works of the title's kind; a count of anything else is asked of the work itself.
        if (!counted.Any(index => KindOf(words[index]) == kind)) return false;
        return !words.Where((word, index) => !counted.Contains(index)).Any(word => KindOf(word) == kind);
    }

    private static Pertinence JudgeWords(string query, string title, string snippet)
    {
        string[] terms = ContentTerms(query);
        if (terms.Length == 0) return Pertinence.None;
        var titled = new HashSet<string>(WikipediaSearchSource.FoldedWords(title), StringComparer.Ordinal);
        var observed = new HashSet<string>(
            WikipediaSearchSource.FoldedWords(title + " " + snippet), StringComparer.Ordinal);
        string[] years = terms.Where(IsYear).ToArray();
        if (!years.All(observed.Contains)) return Pertinence.None;
        terms = terms.Where(term => !IsYear(term)).ToArray();
        if (terms.Length == 0) return Pertinence.About;
        string[] entities = EntityTerms(query);
        if (entities.Length > 0)
        {
            if (!entities.All(entity => WebBrowserAdapter.MatchesSearchTerm(entity, observed))) return Pertinence.None;
        }
        else if (!terms.Any(term => WebBrowserAdapter.MatchesSearchTerm(term, titled)))
        {
            return Pertinence.None;
        }
        int matched = terms.Count(term => WebBrowserAdapter.MatchesSearchTerm(term, observed));
        int needed = terms.Length <= 2 ? terms.Length : terms.Length / 2 + 1;
        if (matched < needed) return Pertinence.None;
        string[] asked = terms.Where(term => !entities.Contains(term)).ToArray();
        if (entities.Length == 0 || asked.Length == 0) return Pertinence.About;
        int found = asked.Count(term => WebBrowserAdapter.MatchesSearchTerm(term, observed));
        return found >= (asked.Length <= 2 ? asked.Length : asked.Length / 2 + 1) ? Pertinence.About : Pertinence.NamesOnly;
    }

    // The general engine's results are judged by the words they share; one that names years and not the one the
    // query names is about another year («Vingegaard gana La Vuelta 2025» for «… la Vuelta 2026»). One that names
    // no year may still be about it.
    internal static bool OfAnotherYear(string[] queryTokens, HashSet<string> observed)
    {
        string[] years = queryTokens.Where(IsYear).ToArray();
        return years.Length > 0 && observed.Any(IsYear) && !years.All(observed.Contains);
    }

    private static bool IsYear(string term) =>
        term.Length == 4 && term.All(char.IsAsciiDigit)
        && (term.StartsWith("19", StringComparison.Ordinal) || term.StartsWith("20", StringComparison.Ordinal));
}
