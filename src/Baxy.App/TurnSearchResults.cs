using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.App;

/// <summary>
/// Uso real 2026-11-02 («el mejor calificado de esos»): a web.fetch of one search result came back web_fetch_status_403
/// and the model gave up, with the other results of the same turn's search unread. The addresses this turn's web.search
/// results gave, in the order they came, once each, less those a web.fetch of the turn asked for; a failed web.fetch's
/// result lists them as <c>unreadResults</c> (aid fetch_other_results). A new turn or a heartbeat starts with none.
/// </summary>
internal sealed class TurnSearchResults
{
    /// <summary>The most addresses a failed web.fetch's result lists.</summary>
    internal const int MaximumListed = 8;

    private readonly List<(string Url, string Address)> _given = [];
    private readonly HashSet<string> _read = new(StringComparer.Ordinal);

    /// <summary>A turn the person opened (not an answer to the waiting call) or a heartbeat.</summary>
    internal void NewTurn()
    {
        _given.Clear();
        _read.Clear();
    }

    /// <summary>
    /// A call ran with <paramref name="arguments"/> and ended with <paramref name="observation"/>, as the model reads it;
    /// returned as it came, or, for a failed web.fetch with results of the turn still unread, with them beside it.
    /// </summary>
    internal string Observed(string operation, JsonObject arguments, string observation)
    {
        if (operation is not ("web.search" or "web.fetch"))
        {
            return observation;
        }

        JsonNode? facts;
        try
        {
            facts = JsonNode.Parse(observation);
        }
        catch (JsonException)
        {
            return observation;
        }

        if (operation == "web.search")
        {
            foreach (JsonNode? result in facts?["observed"]?["results"] as JsonArray ?? [])
            {
                if (Text(result?["url"]) is { } url && Address(url) is { } address
                    && !_given.Exists(given => given.Address == address))
                {
                    _given.Add((url, address));
                }
            }

            return observation;
        }

        if (Text(arguments["url"]) is { } asked && Address(asked) is { } fetched)
        {
            _read.Add(fetched);
        }

        string[] unread = [.. _given.Where(given => !_read.Contains(given.Address)).Select(static given => given.Url)
            .Take(MaximumListed)];
        if (facts is not JsonObject told || (string?)told["status"] != "failed" || unread.Length == 0
            || !ModelAids.On(ModelAids.FetchOtherResults))
        {
            return observation;
        }

        told["unreadResults"] = new JsonArray([.. unread.Select(static url => (JsonNode)url)]);
        return told.ToJsonString(SaidFolders.AsWritten);
    }

    // An address as web.fetch reads it: one written without its scheme is read over https (WebBrowserAdapter.FetchAsync).
    private static string? Address(string url)
    {
        string written = url.Contains("://", StringComparison.Ordinal) ? url : "https://" + url;
        return Uri.TryCreate(written, UriKind.Absolute, out Uri? address) ? address.AbsoluteUri : null;
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text.Trim() : null;
}
