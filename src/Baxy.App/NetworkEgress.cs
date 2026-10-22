using System.Globalization;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;

namespace Baxy.App;

/// <summary>
/// BAXY Renew al máximo 11.5 (identity: «puede entrar información, no puede salir contenido del usuario»; lethal
/// trifecta, OWASP LLM01, CaMeL): in a turn the person opened, a call that sends an address or a query out of the PC
/// waits for their «sí» when it carries what only BAXY could put there. Two cases, as the cross check bounded it
/// (VERIFICACION-pc-de-nb.md, 11.5): a value the model read from memory in this turn (memory.recall or memory.list, at
/// least <see cref="MinimumRememberedCharacters"/> letters or digits, compared folded: case, accents, spacing and
/// URL escapes aside), or a host that came neither from this session's results (their address fields: a search result,
/// a page fetched or read, a tab) nor from the person's words (the site's name, «youtube» for www.youtube.com). A
/// search followed by the fetch of one of its results never waits; an address literal carries no words and is
/// checked only for remembered values. Which calls go out is the catalog's typed fact (al máximo 5.1: the network
/// effect, with the call's exact arguments), and the address is the call's <c>url</c> or <c>host</c>. A heartbeat holds
/// every such call already (NativeTurnLoop.BeatProposes).
/// </summary>
internal sealed class NetworkEgress
{
    /// <summary>The shortest remembered value looked for: a shorter one («sí», a year) is found in any address.</summary>
    internal const int MinimumRememberedCharacters = 8;

    private readonly HashSet<string> _hosts = new(StringComparer.Ordinal);
    private readonly HashSet<string> _words = new(StringComparer.Ordinal);
    private readonly List<string> _remembered = [];

    /// <summary>What the call carries out that waits for the person's «sí», as a code for the model; null: it goes.</summary>
    internal string? Holds(string operation, JsonObject arguments)
    {
        if (!NativeTurnLoop.Has(operation, arguments, OperationEffects.Network))
        {
            return null;
        }

        foreach ((string _, JsonNode? value) in arguments)
        {
            if (value is JsonValue text && text.TryGetValue(out string? sent)
                && Compact(Uri.UnescapeDataString(sent.Replace('+', ' '))) is var carried
                && _remembered.Exists(remembered => carried.Contains(remembered, StringComparison.Ordinal)))
            {
                return "sends_remembered_value";
            }
        }

        string? address = Text(arguments["url"]) ?? Text(arguments["host"]);
        return address is not null && HostOf(address) is { Length: > 0 } host && !Grounded(host)
            ? "host_not_from_session"
            : null;
    }

    /// <summary>The person's words in this session.</summary>
    internal void Heard(string words)
    {
        foreach (string word in Regex.Split(Folded(words), @"[^\p{L}\p{Nd}]+"))
        {
            if (word.Length > 0)
            {
                _words.Add(word);
            }
        }
    }

    /// <summary>A call's result as the model reads it: its addresses, and what memory read in this turn.</summary>
    internal void Observed(string operation, string observation)
    {
        JsonNode? facts;
        try
        {
            facts = JsonNode.Parse(observation);
        }
        catch (JsonException)
        {
            return;
        }

        Walk(facts, operation is "memory.recall" or "memory.list");
    }

    /// <summary>A new turn: what memory read in the last one is not this turn's.</summary>
    internal void NewTurn() => _remembered.Clear();

    /// <summary>A new session: nothing seen or heard in the last one counts.</summary>
    internal void Reset()
    {
        NewTurn();
        _hosts.Clear();
        _words.Clear();
    }

    private void Walk(JsonNode? node, bool memoryRead)
    {
        switch (node)
        {
            case JsonObject facts:
                foreach ((string key, JsonNode? value) in facts)
                {
                    if (value is JsonValue text && text.TryGetValue(out string? field))
                    {
                        if ((key == "url" || key.EndsWith("Url", StringComparison.Ordinal))
                            && Uri.TryCreate(field, UriKind.Absolute, out Uri? address) && address.Host.Length > 0)
                        {
                            _hosts.Add(Normalized(address.Host));
                        }

                        // A record the projection shows (MemoryOperationResponseProjection: label and value; a
                        // sensitive one redacted, so the model never read it).
                        if (memoryRead && key == "value" && field != "[REDACTED]"
                            && Compact(field) is { Length: >= MinimumRememberedCharacters } remembered)
                        {
                            _remembered.Add(remembered);
                        }
                    }
                    else
                    {
                        Walk(value, memoryRead);
                    }
                }

                break;
            case JsonArray items:
                foreach (JsonNode? item in items)
                {
                    Walk(item, memoryRead);
                }

                break;
        }
    }

    private bool Grounded(string host)
    {
        if (IPAddress.TryParse(host, out _))
        {
            return true;
        }

        if (_hosts.Any(seen => host == seen || host.EndsWith("." + seen, StringComparison.Ordinal)
                || seen.EndsWith("." + host, StringComparison.Ordinal)))
        {
            return true;
        }

        // The site's own name, the label before its ending («youtube» in m.youtube.com, «bbc» in bbc.co.uk), never a
        // subdomain anyone may choose («lofi» in lofi.exfil.example).
        string[] labels = host.Split('.');
        string name = labels.Length switch
        {
            1 => labels[0],
            2 => labels[0],
            _ => labels[^2].Length <= 3 ? labels[^3] : labels[^2],
        };
        return name.Length >= 3 && _words.Contains(name);
    }

    private static string HostOf(string address)
    {
        string given = address.Trim();
        return Uri.TryCreate(given, UriKind.Absolute, out Uri? uri) && uri.Host.Length > 0 ? Normalized(uri.Host)
            : Uri.TryCreate("http://" + given, UriKind.Absolute, out uri) ? Normalized(uri.Host)
            : string.Empty;
    }

    private static string Normalized(string host)
    {
        string name = host.Trim().TrimEnd('.').ToLowerInvariant();
        return name.StartsWith("www.", StringComparison.Ordinal) ? name[4..] : name;
    }

    // Lower case without accents: «Ñuñoa» is «nunoa».
    private static string Folded(string text)
    {
        var folded = new StringBuilder(text.Length);
        foreach (char c in text.Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(c) != UnicodeCategory.NonSpacingMark)
            {
                folded.Append(char.ToLowerInvariant(c));
            }
        }

        return folded.ToString();
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text : null;

    // Folded, letters and digits only: «Ñuñoa» and «nunoa-del-mar» are the same value.
    private static string Compact(string text) => string.Concat(Folded(text).Where(char.IsLetterOrDigit));
}
