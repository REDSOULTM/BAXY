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

    // Uso real v3 tanda 1 («quien gano el mundial del 2014» → «Brasil ganó…»): the mind gives the word beginnings
    // with which a page states what was asked (web.search answerWords: «gan», «campeon», «derrot»…); this provider
    // reads no language of its own. A sentence states it when one of its words begins so and is none of the whole
    // words the mind says begin so but name something else (web.search answerWordsNot: «campeonato», «championship»).
    internal static bool States(
        string sentence, IReadOnlyCollection<string> answerWords, IReadOnlyCollection<string>? notStated = null) =>
        answerWords.Count > 0
        && WikipediaSearchSource.FoldedWords(sentence)
            .Any(word => answerWords.Any(stated => word.StartsWith(stated, StringComparison.Ordinal))
                && notStated?.Contains(word, StringComparer.Ordinal) != true);

    // A fragment (a result's title and snippet) already answers when one of its sentences states what was asked and
    // carries every content word of the query: «Titanic … dirigida por James Cameron» for «quién dirigió Titanic».
    // «Se realizó en Brasil … tras el campeonato de 1950» does not answer who won the 2014 World Cup: it lacks the
    // «mundial» of the query. With no answer words there is nothing to judge and the fragment stands.
    internal static bool FragmentAnswers(
        string fragment, string query, IReadOnlyCollection<string> answerWords,
        IReadOnlyCollection<string>? notStated = null)
    {
        if (answerWords.Count == 0) return true;
        string[] terms = SearchPertinence.ContentTerms(query);
        try
        {
            foreach (string sentence in SentenceEnd.Split(fragment.Replace(" … ", ". ", StringComparison.Ordinal)))
            {
                if (!States(sentence, answerWords, notStated)) continue;
                var observed = new HashSet<string>(WebBrowserAdapter.SearchTokens(sentence), StringComparer.Ordinal);
                if (terms.All(term => WebBrowserAdapter.MatchesSearchTerm(term, observed))) return true;
            }
            return false;
        }
        catch (RegexMatchTimeoutException)
        {
            return true;
        }
    }

    // The page's sentences that carry the most of the query's content words, in the page's order; "" when none
    // carries enough of them. A sentence already read (in the result's title or snippet) is not read again. A
    // sentence that states what was asked (answerWords) needs only one content word and comes first.
    internal static string Read(
        string page, string query, string alreadyRead, IReadOnlyCollection<string>? answerWords = null,
        IReadOnlyCollection<string>? notStated = null)
    {
        answerWords ??= [];
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
                bool answers = States(sentence, answerWords, notStated);
                if (matched < (figured || answers ? 1 : Math.Min(2, terms.Length))) continue;
                chosen.Add((matched + (figured ? 1 : 0) + (answers ? 2 : 0), index, sentence));
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

    // Ronda 24 (r23 t1-c03 «cuales son las peliculas mas taquilleras de la historia? dame el top 5» → «No lo
    // encontré.»): the encyclopedia's annex was the first result, and its ranking is a table; Sentences() cuts at
    // every cell and drops each as too short, so no row ever reached the reply. When the mind says a listing is asked
    // (web.search listing, limit = how many), the first ranking of the page is read as rows: the first <table> or
    // <ol> whose caption (or, without one, the nearest heading above it) carries a content word of the query and that
    // is ordered by position (an <ol>, or a table whose rows open with their position 1, 2, 3…). Each row's cells are
    // joined with « · » after its position («1. Avatar · 2 923 706 026 · 2009»). Only the first such ranking counts:
    // a later one (the same list adjusted for inflation, by year, by opening weekend) answers another question.
    private const int MaximumRows = 20;
    private const int MaximumRowCharacters = 200;

    private static readonly Regex Hidden = new(
        @"<(sup|span|div)\b[^>]*(?:display\s*:\s*none|class=""[^""]*\breference\b)[^>]*>.*?</\1\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex RankingBlock = new(
        @"<(h[1-6])\b[^>]*>(?<heading>.*?)</\1\s*>|<(?<kind>table|ol)\b[^>]*>(?<body>.*?)</\k<kind>\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Caption = new(
        @"<caption\b[^>]*>(.*?)</caption\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex TableRow = new(
        @"<tr\b[^>]*>(.*?)</tr\s*>", RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        RegexBudget);

    private static readonly Regex Cell = new(
        @"<(td|th)\b[^>]*>(.*?)(?=<t[dh]\b|$)", RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        RegexBudget);

    private static readonly Regex ListItem = new(
        @"<li\b[^>]*>(.*?)(?=<li\b|$)", RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        RegexBudget);

    private static readonly Regex Position = new(@"^(\d{1,3})\s*[.ºª°)]?$", RegexOptions.CultureInvariant, RegexBudget);

    internal static string Rows(string page, string query, int count)
    {
        string[] terms = SearchPertinence.ContentTerms(query);
        if (terms.Length == 0 || page.Length == 0 || count <= 0) return string.Empty;
        count = Math.Min(count, MaximumRows);
        try
        {
            string html = Hidden.Replace(Unread.Replace(page, " "), " ");
            string heading = string.Empty;
            foreach (Match block in RankingBlock.Matches(html))
            {
                if (block.Groups["heading"].Success)
                {
                    heading = Text(block.Groups["heading"].Value);
                    continue;
                }
                string body = block.Groups["body"].Value;
                Match caption = Caption.Match(body);
                string named = caption.Success ? Text(caption.Groups[1].Value) : heading;
                var observed = new HashSet<string>(WebBrowserAdapter.SearchTokens(named), StringComparer.Ordinal);
                if (!terms.Any(term => WebBrowserAdapter.MatchesSearchTerm(term, observed))) continue;
                List<string> rows = block.Groups["kind"].Value.Equals("ol", StringComparison.OrdinalIgnoreCase)
                    ? ListRows(body, count)
                    : TableRows(body, count);
                if (rows.Count >= Math.Min(2, count)) return string.Join(" | ", rows);
            }
            return string.Empty;
        }
        catch (RegexMatchTimeoutException)
        {
            return string.Empty;
        }
    }

    // A table is a ranking when its rows (those with data cells) open with their position: 1, then each the same or
    // the next. Any other table (an alphabetical list, a year per row) is not read as one.
    private static List<string> TableRows(string body, int count)
    {
        var rows = new List<string>();
        int last = 0;
        foreach (Match row in TableRow.Matches(body))
        {
            if (!row.Groups[1].Value.Contains("<td", StringComparison.OrdinalIgnoreCase)) continue;
            string[] cells = Cell.Matches(row.Groups[1].Value)
                .Select(static cell => Text(cell.Groups[2].Value))
                .ToArray();
            if (cells.Length < 2) continue;
            Match position = Position.Match(cells[0]);
            // A header written with data cells comes before the first position; after it, a row without one (a
            // note, a total) ends the ranking.
            if (!position.Success)
            {
                if (rows.Count == 0) continue;
                break;
            }
            int rank = int.Parse(position.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
            if (rows.Count == 0 ? rank != 1 : rank != last && rank != last + 1) return [];
            last = rank;
            // Revisión 2 (en.wikipedia «List of highest-grossing films»: Rank · Peak · Title…, read «1. 1 · Avengers:
            // Endgame»): a cell that is only a position before the row's name (its peak, its previous place) names
            // nothing and would read as another place; the cells are read from the first one that is not.
            rows.Add(Row(rank, cells.Skip(1).SkipWhile(static cell => cell.Length == 0 || Position.IsMatch(cell))));
            if (rows.Count >= count) break;
        }
        return rows;
    }

    // Revisión 1 (a WordPress comment list under «2 comentarios en «Las 10 películas más taquilleras…»», the steps
    // under «Cómo ver las películas más taquilleras gratis»): an <ol> is a ranking only when its items are short
    // entries, as a table's rows must open with 1, 2, 3: no item holds a block of its own (<p>, <article>, a nested
    // list…), none is a sentence (ends with its mark) and none runs past ShortEntryWords words. Any other list is
    // not read as one.
    private const int ShortEntryWords = 16;

    private static readonly Regex EntryBlock = new(
        @"<(?:p|article|blockquote|section|header|footer|ol|ul|dl|table|figure|form)\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex EntryIsSentence = new(@"[.!?…]\s*$", RegexOptions.CultureInvariant, RegexBudget);

    private static List<string> ListRows(string body, int count)
    {
        var rows = new List<string>();
        foreach (Match item in ListItem.Matches(body))
        {
            string html = item.Groups[1].Value;
            string text = Text(html);
            if (text.Length == 0) continue;
            if (EntryBlock.IsMatch(html)
                || EntryIsSentence.IsMatch(text)
                || text.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length > ShortEntryWords)
            {
                return [];
            }
            rows.Add(Row(rows.Count + 1, [text]));
            if (rows.Count >= count) break;
        }
        return rows;
    }

    private static string Row(int rank, IEnumerable<string> cells)
    {
        string row = rank.ToString(System.Globalization.CultureInfo.InvariantCulture) + ". "
            + string.Join(" · ", cells.Where(static cell => cell.Length > 0));
        return row.Length > MaximumRowCharacters ? row[..MaximumRowCharacters].TrimEnd() + "…" : row;
    }

    private static string Text(string html) =>
        string.Join(' ', System.Net.WebUtility.HtmlDecode(Tag.Replace(html, " "))
            .Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));

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
