using System.Globalization;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M98 (DEV-D v3x D-w14-t1 «¿quién ha ganado la Vuelta este año?», 2026): the engine got «este año» as typed and
// answered with pages of 2025 and one of 2026 that never said the year; the reply could not tell which was this year's.
// Asked «… la Vuelta 2026?», the same engine answers with the 2026 winner in every snippet. A year the person names
// by its relation to today («este año», «el año pasado», «this year», «next year») reaches the sources as its number,
// read from this PC's clock; nothing else of the query changes.
internal static partial class SearchQueryYear
{
    [GeneratedRegex(
        @"(?<de>\bde\s+)?(?<rel>\b(?:este\s+a[ñn]o|(?:el\s+)?a[ñn]o\s+(?:actual|en\s+curso)|this\s+year(?:'s|’s)?|(?:the\s+)?current\s+year(?:'s|’s)?))(?=\W|$)|"
        + @"\ben\s+lo\s+que\s+va\s+del\s+a[ñn]o\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, matchTimeoutMilliseconds: 2000)]
    private static partial Regex ThisYear();

    [GeneratedRegex(
        @"\b(?<lead>d?el)\s+(?:a[ñn]o\s+pasado|pasado\s+a[ñn]o)\b|\blast\s+year(?:'s|’s)?(?=\W|$)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, matchTimeoutMilliseconds: 2000)]
    private static partial Regex LastYear();

    [GeneratedRegex(
        @"\b(?<lead>d?el)\s+(?:a[ñn]o\s+que\s+viene|(?:pr[óo]ximo|siguiente)\s+a[ñn]o)\b|\bnext\s+year(?:'s|’s)?(?=\W|$)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, matchTimeoutMilliseconds: 2000)]
    private static partial Regex NextYear();

    // The query with each year said by its relation to today written as that year («en lo que va del año» → «en
    // 2026», «del año pasado» → «de 2025»).
    internal static string Anchor(string query, int currentYear)
    {
        try
        {
            string anchored = ThisYear().Replace(query, match => match.Value.StartsWith("en", StringComparison.OrdinalIgnoreCase)
                && !match.Groups["rel"].Success
                    ? "en " + Number(currentYear)
                    : (match.Groups["de"].Success ? match.Groups["de"].Value : string.Empty) + Number(currentYear));
            anchored = LastYear().Replace(anchored, match => Lead(match) + Number(currentYear - 1));
            anchored = NextYear().Replace(anchored, match => Lead(match) + Number(currentYear + 1));
            return string.Join(' ', anchored.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        }
        catch (RegexMatchTimeoutException)
        {
            return query;
        }
    }

    private static string Lead(Match match) =>
        match.Groups["lead"].Value.Equals("del", StringComparison.OrdinalIgnoreCase) ? "de " : string.Empty;

    private static string Number(int year) => year.ToString(CultureInfo.InvariantCulture);
}
