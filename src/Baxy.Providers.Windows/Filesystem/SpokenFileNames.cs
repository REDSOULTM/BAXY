using System.Globalization;
using System.Text;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// A file's name as a person says it. A voice dictates no separator between a name's words (holdout v5 V5E052
/// «factura marzo.pdf» for factura-marzo.pdf; holdout v6 V6F010 «lista invitados» for lista_invitados.txt), so the
/// words between space, -, _ and . are the name, whatever separates them. Every tool that matches a name the person
/// gave against the names of files and folders compares them here; a name spelled exactly (case aside) is still the
/// one meant before any that only has its words.
/// </summary>
public static class SpokenFileNames
{
    /// <summary>The words of a name in lower case, joined by one space where space, -, _ or . separated them:
    /// «Lista_Invitados.txt» and «lista invitados.txt» are «lista invitados txt».</summary>
    public static string Words(string name) => Join(name, withoutAccents: false);

    /// <summary><see cref="Words"/> also without accents («Canción.txt» is «cancion txt»): the names alike a tool
    /// offers, never one it acts on.</summary>
    public static string Folded(string name) => Join(name, withoutAccents: true);

    /// <summary>Whether a file's name is the name said, its words otherwise separated (case aside).</summary>
    public static bool Same(string fileName, string said) =>
        Words(said) is { Length: > 0 } words && Words(fileName) == words;

    /// <summary>Whether a file's name holds the part said, its words otherwise separated (case aside).</summary>
    public static bool Contains(string fileName, string part) =>
        Words(part) is { Length: > 0 } words && Words(fileName).Contains(words, StringComparison.Ordinal);

    /// <summary>Whether a file's name holds the part said, its words otherwise separated, case and accents aside
    /// (cosecha 03-11 F14: «Título» said, TITULO in the name).</summary>
    public static bool ContainsFolded(string fileName, string part) =>
        Folded(part) is { Length: > 0 } words && Folded(fileName).Contains(words, StringComparison.Ordinal);

    /// <summary>Whether a name holds every word said, in any order and with others between («presentación hito 2» in
    /// «Presentacion Curso Hito 2»; cosecha 04-11 F33): the words of a name, as a search engine's match with operator
    /// «and» takes them and a phrase query does not (elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-query.html).
    /// Two words or more: one is already a part of the name. A short word without a digit (under four letters: «de»,
    /// «del») need not be there when at least two others are: a person says it and a file's name leaves it out.</summary>
    public static bool HoldsWords(string name, string said)
    {
        string[] asked = Folded(said).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (asked.Length < 2) return false;
        var words = Folded(name).Split(' ', StringSplitOptions.RemoveEmptyEntries).ToHashSet(StringComparer.Ordinal);
        string[] held = [.. asked.Where(words.Contains)];
        return held.Length == asked.Length
            || (held.Length >= 2 && asked.Except(held).All(word => word.Length < 4 && !word.Any(char.IsDigit)));
    }

    /// <summary>
    /// How many letters the name said is off from a file's name when it is alike, null when it is not: each word said
    /// against a word of the name, in order and side by side (<see cref="Folded"/>), within the edits a word of its
    /// length may have. Cosecha 03-11 F14: a product's name misheard by one letter (i for y) and said without its
    /// accent, and no name held it. The edits are Elasticsearch's fuzziness AUTO:4,8 (none for a word under 4 letters, 1 under 8,
    /// else 2; elastic.co/guide/en/elasticsearch/reference/current/common-options.html#fuzziness) counted as Lucene
    /// counts them, a swap of two letters side by side being one (optimal string alignment); a word with a digit is
    /// never off («2024» is not «2025»). Measured on 69,640 real names of a PC (Desktop, Documents, Downloads): 259
    /// absent queries of two common words found any name alike in 8 (0.08 names each), against 20 (4.2) with AUTO:3,6;
    /// a misheard word of a real name found its file in 270 of 400.
    /// </summary>
    public static int? Alike(string fileName, string said)
    {
        string[] asked = Folded(said).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        string[] words = Folded(fileName).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        int? best = null;
        for (int start = 0; asked.Length > 0 && start + asked.Length <= words.Length; start++)
        {
            int cost = 0;
            for (int index = 0; index < asked.Length && cost >= 0; index++)
                cost = WordEdits(asked[index], words[start + index]) is int edits ? cost + edits : -1;
            if (cost >= 0 && (best is null || cost < best)) best = cost;
        }
        return best;
    }

    private static int? WordEdits(string said, string word)
    {
        if (string.Equals(said, word, StringComparison.Ordinal)) return 0;
        int allowed = said.Length < 4 ? 0 : said.Length < 8 ? 1 : 2;
        if (allowed == 0 || Math.Abs(said.Length - word.Length) > allowed
            || said.Any(char.IsDigit) || word.Any(char.IsDigit))
            return null;
        // Optimal string alignment distance over two rows back.
        int[] before = new int[word.Length + 1], previous = new int[word.Length + 1], current = new int[word.Length + 1];
        for (int column = 0; column <= word.Length; column++) previous[column] = column;
        for (int row = 1; row <= said.Length; row++)
        {
            current[0] = row;
            for (int column = 1; column <= word.Length; column++)
            {
                int cost = said[row - 1] == word[column - 1] ? 0 : 1;
                current[column] = Math.Min(Math.Min(previous[column] + 1, current[column - 1] + 1),
                    previous[column - 1] + cost);
                if (row > 1 && column > 1 && said[row - 1] == word[column - 2] && said[row - 2] == word[column - 1])
                    current[column] = Math.Min(current[column], before[column - 2] + 1);
            }
            (before, previous, current) = (previous, current, before);
        }
        return previous[word.Length] <= allowed ? previous[word.Length] : null;
    }

    private static string Join(string name, bool withoutAccents)
    {
        string text = name;
        try
        {
            text = name.Normalize(withoutAccents ? NormalizationForm.FormD : NormalizationForm.FormC);
        }
        catch (ArgumentException)
        {
            // a name Windows allows with a lone surrogate has no normal form
        }

        var joined = new StringBuilder(text.Length);
        bool gap = false;
        foreach (char character in text)
        {
            if (withoutAccents && CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
                continue;
            if (character is ' ' or '-' or '_' or '.')
            {
                gap = joined.Length > 0;
                continue;
            }

            if (gap) joined.Append(' ');
            gap = false;
            joined.Append(char.ToLowerInvariant(character));
        }

        return joined.ToString();
    }
}
