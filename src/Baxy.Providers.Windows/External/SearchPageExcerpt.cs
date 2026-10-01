using System.Text;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M98 (DEV-D v3x D-w01-t2 «cuánta sal le echo al agua» → «No encontré una cifra exacta»): the general engine's
// snippet stops at about 250 characters, and El Tiempo's said «la regla del 1, 100 y 10» without the rule; its page
// says «un tercio de cucharada por cada litro de agua» two paragraphs below. The sentences of a result's page that
// carry the most of what was asked (and a figure, when a figure was asked) are read with the snippet. Only the
// page's prose counts: scripts, styles, menus, headers, footers and forms are dropped before reading.
internal static class SearchPageExcerpt
{
    private const int MaximumSentences = 3;
    private const int MaximumCharacters = 600;

    private static readonly TimeSpan RegexBudget = TimeSpan.FromSeconds(2);

    private static readonly Regex Unread = new(
        @"<!--.*?-->|<(head|script|style|noscript|svg|nav|header|footer|aside|form|template|iframe|button|select)\b.*?</\1\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Block = new(
        @"</?(?:p|li|h[1-6]|br|div|tr|td|th|dd|dt|blockquote|section|article|main|ul|ol|table|figcaption)\b[^>]*>",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Tag = new("<[^>]*>", RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex SentenceEnd = new(
        @"(?<=[.!?])\s+(?=[\p{Lu}¿¡\d""«“])", RegexOptions.CultureInvariant, RegexBudget);

    // Words that ask for a figure: an amount, a distance, a price, a date, an age, a size.
    private static readonly HashSet<string> FigureWords = new(StringComparer.Ordinal)
    {
        "cuanto", "cuanta", "cuantos", "cuantas", "distancia", "distance", "precio", "precios", "price", "prices",
        "cuesta", "cuestan", "cost", "costs", "cuando", "when", "fecha", "fechas", "date", "dates", "ano", "anos",
        "year", "years", "edad", "age", "altura", "height", "mide", "miden", "pesa", "pesan", "weigh", "weight",
        "cifra", "cifras", "numero", "number", "porcentaje", "percent", "percentage", "temperatura", "temperature",
        "habitantes", "population", "poblacion", "duracion", "dura", "long", "far", "tall", "old", "many", "much",
    };

    internal static bool AsksFigure(string query) =>
        WikipediaSearchSource.FoldedWords(query).Any(FigureWords.Contains);

    // The page's sentences that carry the most of the query's content words, in the page's order; "" when none
    // carries enough of them. A sentence already read (in the result's title or snippet) is not read again.
    internal static string Read(string page, string query, string alreadyRead)
    {
        string[] terms = SearchPertinence.ContentTerms(query);
        if (terms.Length == 0 || page.Length == 0) return string.Empty;
        bool figure = AsksFigure(query);
        string read = string.Join(' ', WikipediaSearchSource.FoldedWords(alreadyRead));
        try
        {
            var chosen = new List<(double Score, int Index, string Sentence)>();
            int index = 0;
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (string sentence in Sentences(page))
            {
                index++;
                string folded = string.Join(' ', WikipediaSearchSource.FoldedWords(sentence));
                // A snippet stops mid-sentence: what it read is the sentence's beginning.
                string opening = folded.Length > 60 ? folded[..60] : folded;
                if (folded.Length == 0 || !seen.Add(folded) || read.Contains(opening, StringComparison.Ordinal)) continue;
                var observed = new HashSet<string>(WebBrowserAdapter.SearchTokens(sentence), StringComparer.Ordinal);
                int matched = terms.Count(term => WebBrowserAdapter.MatchesSearchTerm(term, observed));
                bool figured = figure && sentence.Any(char.IsDigit);
                if (matched < (figured ? 1 : Math.Min(2, terms.Length))) continue;
                chosen.Add((matched + (figured ? 1 : 0), index, sentence));
            }
            var excerpt = new StringBuilder();
            foreach ((_, _, string sentence) in chosen
                .OrderByDescending(static item => item.Score)
                .ThenBy(static item => item.Index)
                .Take(MaximumSentences)
                .OrderBy(static item => item.Index))
            {
                if (excerpt.Length + sentence.Length + 1 > MaximumCharacters) break;
                if (excerpt.Length > 0) excerpt.Append(' ');
                excerpt.Append(sentence);
            }
            return excerpt.ToString();
        }
        catch (RegexMatchTimeoutException)
        {
            return string.Empty;
        }
    }

    // The page's prose as sentences of a readable length (a menu item or a caption is not one).
    private static IEnumerable<string> Sentences(string page)
    {
        string prose = Block.Replace(Unread.Replace(page, " "), "\n");
        prose = System.Net.WebUtility.HtmlDecode(Tag.Replace(prose, " "));
        foreach (string line in prose.Split('\n'))
        {
            string text = string.Join(' ', line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
            if (text.Length == 0) continue;
            foreach (string sentence in SentenceEnd.Split(text))
            {
                if (sentence.Length is >= 30 and <= 600) yield return sentence;
            }
        }
    }
}
