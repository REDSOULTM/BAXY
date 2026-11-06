using System.Globalization;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>A row a page shows on screen: where it is, top to bottom, and the text of its cells in order.</summary>
internal sealed record UserBrowserPageRow(double Top, double Bottom, IReadOnlyList<string> Cells);

/// <summary>What a page's rows say of their order: how many there are and, of the rows with a date or a time of their
/// own, which one has the latest (null when fewer than two rows have one, or two tie).</summary>
internal sealed record PageRowFacts(int Count, int? LatestRow, string? LatestWhen, string? LatestText, int WithoutDate);

/// <summary>
/// Encargo 82 (vivo del 81, «léeme el último correo» 0/2): a list read as flat text gives its rows with no sign of how
/// they lie on screen, and the model took the last row as the latest (the mail of «ayer», not the one of 10:31). The
/// rows as the page shows them, by their place on screen, and the row with the latest date or time by the form of a
/// cell that holds nothing else (a time inside a subject is the subject's). Webmail lists put the newest on top by
/// default, not always: the facts are what is on screen, and the model decides what the person meant.
/// </summary>
internal static partial class PageRows
{
    private const int MaximumText = 160;

    [GeneratedRegex(@"^\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?\s?m\.?)?$", RegexOptions.CultureInvariant | RegexOptions.IgnoreCase)]
    private static partial Regex TimeForm();

    [GeneratedRegex(@"^\d{1,4}/\d{1,2}(?:/\d{1,4})?$|^\d{1,4}-\d{1,2}-\d{1,4}$", RegexOptions.CultureInvariant)]
    private static partial Regex NumericDateForm();

    /// <summary>The facts of the rows, or null when they are no list of dated rows and no grid: most pages' lists are
    /// menus, whose order says nothing. Rows inside another row are that row's.</summary>
    internal static PageRowFacts? Read(IReadOnlyList<UserBrowserPageRow>? rows, DateTime now, CultureInfo culture)
    {
        if (rows is null || rows.Count < 2)
            return null;
        var shown = new List<UserBrowserPageRow>();
        foreach (UserBrowserPageRow row in rows.OrderBy(static row => row.Top).ThenByDescending(static row => row.Bottom))
        {
            if (row.Cells.Count > 0 && (shown.Count == 0 || row.Top >= shown[^1].Bottom - 1))
                shown.Add(row);
        }

        var dated = new List<(int Row, DateTime When, string Said)>();
        for (int index = 0; index < shown.Count; index++)
        {
            // Of the cells that are a date or a time, the last: the column of dates comes after what it dates.
            foreach (string cell in shown[index].Cells.Reverse())
            {
                if (When(cell, now, culture) is DateTime when)
                {
                    dated.Add((index + 1, when, cell.Trim()));
                    break;
                }
            }

            // A row with only its whole name (a list's option): its last words, the fewest that read as a date («lunes
            // 10:31» of a subject that ends in «del lunes» and a time is the time).
            if (shown[index].Cells is [string name] && !dated.Any(row => row.Row == index + 1))
            {
                string[] words = name.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                for (int count = 1; count <= Math.Min(3, words.Length - 1); count++)
                {
                    string end = string.Join(' ', words[^count..]);
                    if (When(end, now, culture) is DateTime when)
                    {
                        dated.Add((index + 1, when, end));
                        break;
                    }
                }
            }
        }

        if (dated.Count < 2)
            return null;
        DateTime latest = dated.Max(static row => row.When);
        (int Row, DateTime When, string Said)[] first = [.. dated.Where(row => row.When == latest)];
        if (first.Length != 1)
            return new(shown.Count, null, null, null, shown.Count - dated.Count);
        string text = string.Join(" · ", shown[first[0].Row - 1].Cells.Select(static cell => cell.Trim()));
        return new(shown.Count, first[0].Row, first[0].Said,
            text.Length > MaximumText ? text[..MaximumText] + "…" : text, shown.Count - dated.Count);
    }

    /// <summary>When a cell that holds only a date or a time says: a time alone is today's, as a mail list shows
    /// today's mail; a date without a year is the last one that has passed. Null for anything else.</summary>
    internal static DateTime? When(string cell, DateTime now, CultureInfo culture)
    {
        string said = cell.Trim();
        if (said.Length is < 3 or > 32 || !said.Any(char.IsDigit) || said.Split(' ').Length > 5)
            return null;
        // Letters beside digits are read as a month's name by the culture; digits alone only in a time's or a date's whole
        // form («3-1» is a score, «10.31» a price).
        if (!TimeForm().IsMatch(said) && !NumericDateForm().IsMatch(said) && !said.Any(char.IsLetter))
            return null;
        foreach (CultureInfo reader in (CultureInfo[])[culture, CultureInfo.GetCultureInfo("en-US")])
        {
            if (!DateTime.TryParse(said, reader,DateTimeStyles.NoCurrentDateDefault | DateTimeStyles.AllowWhiteSpaces, out DateTime read))
                continue;
            if (read.Date == DateTime.MinValue.Date)
                return now.Date + read.TimeOfDay;
            return read > now.AddDays(1) && !said.Contains(read.Year.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
                ? read.AddYears(-1)
                : read;
        }

        return null;
    }
}
