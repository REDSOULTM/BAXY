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
//     o dos, la mayoría estricta si son más.
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

    internal static bool IsPertinent(string query, string title, string snippet)
    {
        string[] terms = ContentTerms(query);
        if (terms.Length == 0) return false;
        var titled = new HashSet<string>(WikipediaSearchSource.FoldedWords(title), StringComparer.Ordinal);
        var observed = new HashSet<string>(
            WikipediaSearchSource.FoldedWords(title + " " + snippet), StringComparer.Ordinal);
        string[] entities = EntityTerms(query);
        if (entities.Length > 0)
        {
            if (!entities.All(entity => WebBrowserAdapter.MatchesSearchTerm(entity, observed))) return false;
        }
        else if (!terms.Any(term => WebBrowserAdapter.MatchesSearchTerm(term, titled)))
        {
            return false;
        }
        int matched = terms.Count(term => WebBrowserAdapter.MatchesSearchTerm(term, observed));
        int needed = terms.Length <= 2 ? terms.Length : terms.Length / 2 + 1;
        return matched >= needed;
    }
}
