using System.Text;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Uso real v3, tanda 4 (c10): «los horarios del Cercanías» was confirmed by another Google search the person had open
/// in the same window, because only the host was compared. A navigation now arrives when the address read is the one
/// asked for —path and query, with the spellings a browser shows normalized— or, for a redirect, an address of the
/// same site that was not on show before the link was opened and does not answer the same path with another query.
/// </summary>
internal sealed partial class UserBrowserSurface
{
    /// <summary>
    /// The address read is the destination asked for: the same site, the same path (escaping, a final slash and the
    /// fragment aside) and every query parameter asked for with the same value («+» and «%20» alike, case aside). A
    /// page may add parameters of its own (a search engine's session or source markers): those are not compared.
    /// </summary>
    internal static bool ReachedTarget(Uri requested, Uri observed)
    {
        if (!SameSite(requested, observed)
            || !string.Equals(PathOf(requested), PathOf(observed), StringComparison.Ordinal))
            return false;
        List<KeyValuePair<string, string>> seen = QueryOf(observed);
        return QueryOf(requested).All(asked => seen.Any(pair => SameParameter(asked, pair)));
    }

    /// <summary>
    /// The address answers the path asked for with another value of a parameter asked for: another search on the
    /// same results page is a different page, never a redirect of this one.
    /// </summary>
    internal static bool ContradictsTarget(Uri requested, Uri observed)
    {
        if (!string.Equals(PathOf(requested), PathOf(observed), StringComparison.Ordinal))
            return false;
        List<KeyValuePair<string, string>> seen = QueryOf(observed);
        return QueryOf(requested).Any(asked =>
            seen.Any(pair => string.Equals(pair.Key, asked.Key, StringComparison.Ordinal))
            && !seen.Any(pair => SameParameter(asked, pair)));
    }

    /// <summary>Both addresses name the same page (each reaches the other).</summary>
    internal static bool SameAddress(Uri left, Uri right) => ReachedTarget(left, right) && ReachedTarget(right, left);

    private static bool SameParameter(KeyValuePair<string, string> asked, KeyValuePair<string, string> seen) =>
        string.Equals(asked.Key, seen.Key, StringComparison.Ordinal)
        && string.Equals(asked.Value, seen.Value, StringComparison.OrdinalIgnoreCase);

    private static string PathOf(Uri address)
    {
        string path = Unescape(address.AbsolutePath);
        return path.TrimEnd('/');
    }

    private static List<KeyValuePair<string, string>> QueryOf(Uri address)
    {
        string query = address.Query.TrimStart('?');
        if (query.Length == 0)
            return [];
        var pairs = new List<KeyValuePair<string, string>>();
        foreach (string part in query.Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            int equals = part.IndexOf('=', StringComparison.Ordinal);
            string name = equals < 0 ? part : part[..equals];
            string value = equals < 0 ? string.Empty : part[(equals + 1)..];
            pairs.Add(new(Unescape(name.Replace('+', ' ')), Unescape(value.Replace('+', ' '))));
        }
        return pairs;
    }

    private static string Unescape(string text)
    {
        string value;
        try
        {
            value = Uri.UnescapeDataString(text);
        }
        catch (UriFormatException)
        {
            value = text;
        }
        return value.Normalize(NormalizationForm.FormC);
    }
}
