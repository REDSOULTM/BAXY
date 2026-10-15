using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>A search engine's results page: its host (exact, or any subdomain with <see cref="HostSuffix"/>), the paths
/// of its results and the parameter that carries what was searched.</summary>
internal sealed record SearchAddress(string Host, bool HostSuffix, IReadOnlyList<string> Paths, string Param);

/// <summary>
/// Ronda 23 (t4-c10, t3-c06: a search results page whose arrival was missed): the search engines whose results page the browser surface recognizes, read from data
/// (src/baxy_mind/data/search_addresses.v1.json, embedded; the same table baxy_mind.semantic.search_address reads), so
/// the provider names no engine.
/// </summary>
internal static class SearchAddresses
{
    private static readonly Lazy<IReadOnlyList<SearchAddress>> Data = new(Load);

    internal static IReadOnlyList<SearchAddress> All => Data.Value;

    internal static IReadOnlyList<SearchAddress> Parse(Stream stream)
    {
        using JsonDocument document = JsonDocument.Parse(stream);
        var engines = new List<SearchAddress>();
        if (!document.RootElement.TryGetProperty("engines", out JsonElement array)
            || array.ValueKind != JsonValueKind.Array)
            return engines;
        foreach (JsonElement item in array.EnumerateArray())
        {
            string? host = Text(item, "host");
            string? param = Text(item, "param");
            if (host is null || param is null)
                continue;
            bool suffix = item.TryGetProperty("hostSuffix", out JsonElement flag) && flag.ValueKind == JsonValueKind.True;
            var paths = new List<string>();
            if (item.TryGetProperty("paths", out JsonElement list) && list.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement path in list.EnumerateArray())
                {
                    if (path.ValueKind == JsonValueKind.String)
                        paths.Add((path.GetString() ?? string.Empty).Trim().TrimEnd('/'));
                }
            }
            engines.Add(new SearchAddress(host.ToLowerInvariant(), suffix, paths, param));
        }
        return engines;
    }

    /// <summary>
    /// What <paramref name="address"/> searches when it is the results page of a known engine (its host, one of its
    /// paths, its parameter with a value); null for any other address.
    /// </summary>
    internal static string? SearchedText(Uri address, IReadOnlyList<SearchAddress>? engines = null)
    {
        string host = address.Host.Trim().TrimEnd('.').ToLowerInvariant();
        string path = Uri.UnescapeDataString(address.AbsolutePath).TrimEnd('/');
        foreach (SearchAddress engine in engines ?? All)
        {
            bool hostMatches = host == engine.Host || (engine.HostSuffix && host.EndsWith("." + engine.Host, StringComparison.Ordinal));
            if (!hostMatches || !engine.Paths.Contains(path, StringComparer.OrdinalIgnoreCase))
                continue;
            foreach (string part in address.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
            {
                int equals = part.IndexOf('=', StringComparison.Ordinal);
                if (equals <= 0 || !string.Equals(Unescape(part[..equals]), engine.Param, StringComparison.Ordinal))
                    continue;
                string value = Unescape(part[(equals + 1)..]).Trim();
                return value.Length == 0 ? null : value;
            }
        }
        return null;
    }

    private static string Unescape(string text)
    {
        try
        {
            return Uri.UnescapeDataString(text.Replace('+', ' '));
        }
        catch (UriFormatException)
        {
            return text.Replace('+', ' ');
        }
    }

    private static string? Text(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(value.GetString())
            ? value.GetString()!.Trim()
            : null;

    private static IReadOnlyList<SearchAddress> Load()
    {
        using Stream stream = typeof(SearchAddresses).Assembly.GetManifestResourceStream(
                "Baxy.Providers.Windows.SearchAddresses.json")
            ?? throw new InvalidOperationException("search_addresses_missing");
        return Parse(stream);
    }
}
