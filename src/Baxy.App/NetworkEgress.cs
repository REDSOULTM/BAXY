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
/// search followed by the fetch of one of its results never waits. An address literal (an IP) carries no words: a ping
/// to one goes, and so does a page in the person's own network (loopback, private, link-local), but a page at any
/// other IP waits unless the person wrote it or a result gave it (auditoría de la App, 2026-10-23: a fetch of
/// «http://203.0.113.9/?d=…» left the PC unasked, the plainest way out for what a page told the model to send). Which calls go out is the catalog's typed fact (al máximo 5.1: the network
/// effect, with the call's exact arguments), and the address is the call's <c>url</c> or <c>host</c>. A heartbeat holds
/// every such call already (NativeTurnLoop.BeatProposes).
/// </summary>
internal sealed class NetworkEgress
{
    /// <summary>The shortest remembered value looked for: a shorter one («sí», a year) is found in any address.</summary>
    internal const int MinimumRememberedCharacters = 8;

    /// <summary>The most result hosts a held call's result lists (<see cref="ResultHosts"/>).</summary>
    internal const int MaximumResultHosts = 8;

    private readonly HashSet<string> _hosts = new(StringComparer.Ordinal);
    private readonly HashSet<string> _words = new(StringComparer.Ordinal);
    private readonly List<string> _remembered = [];
    private readonly List<string> _resultHosts = [];

    /// <summary>
    /// The hosts of the addresses this session's results gave (a search result, a page fetched or read, a tab), in the
    /// order they came, once each, the last <see cref="MaximumResultHosts"/>: never one only the person's words gave,
    /// nor one memory read.
    /// </summary>
    internal IReadOnlyList<string> ResultHosts => _resultHosts;

    /// <summary>What the call carries out that waits for the person's «sí», as a code for the model; null: it goes.</summary>
    internal string? Holds(string operation, JsonObject arguments)
    {
        // Renew al máximo (F001, int6 s0): «pon Doom Eternal» gave game.launch an id that is Rocket League's; refused
        // with game_title_mismatch, the model called it again with title «Rocket League» and that game started. The
        // title is the person's to say: one they did not say waits for their «sí» like a host nobody gave.
        if (operation == "game.launch" && Text(arguments["title"]) is { } title && !Said(title))
        {
            return "game_title_not_said";
        }

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

        string? url = Text(arguments["url"]);
        string? address = url ?? Text(arguments["host"]);
        return address is not null && HostOf(address) is { Length: > 0 } host
            && !Grounded(host, carriesPage: url is not null)
                ? "host_not_from_session"
                : null;
    }

    /// <summary>The person's words in this session, and the addresses they wrote or dictated in them.</summary>
    internal void Heard(string words)
    {
        foreach (string word in Regex.Split(Folded(words), @"[^\p{L}\p{Nd}]+"))
        {
            if (word.Length > 0)
            {
                _words.Add(word);
            }
        }

        // «https://www.rfc-editor.org/rfc/rfc2324» or «rfc-editor.org» is the person's own host, as a result's address
        // is (e2e E022, 2026-10-22: its name split at the hyphen never matched their words).
        foreach (Match address in Regex.Matches(words, @"(?:https?://)?[\p{L}\p{Nd}-]+(?:\.[\p{L}\p{Nd}-]+)*\.\p{L}{2,}\b"))
        {
            if (HostOf(address.Value) is { Length: > 0 } host)
            {
                _hosts.Add(host);
            }
        }

        // An address the person wrote as its IP («http://192.0.2.7/estado») is theirs too.
        foreach (Match address in Regex.Matches(words, @"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![.]?\d)"))
        {
            if (IPAddress.TryParse(address.Value, out IPAddress? ip))
            {
                _hosts.Add(ip.ToString());
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
        _resultHosts.Clear();
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
                            string host = Normalized(address.Host);
                            _hosts.Add(host);
                            if (!memoryRead && !_resultHosts.Contains(host))
                            {
                                _resultHosts.Add(host);
                                if (_resultHosts.Count > MaximumResultHosts)
                                {
                                    _resultHosts.RemoveAt(0);
                                }
                            }
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

    private bool Grounded(string host, bool carriesPage)
    {
        if (IPAddress.TryParse(host.Trim('[', ']'), out IPAddress? ip))
        {
            return !carriesPage || InPersonsNetwork(ip) || _hosts.Contains(host) || _hosts.Contains(ip.ToString());
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
        // A name with hyphens is the person's when they said every part of it («rfc editor» for rfc-editor.org).
        string[] parts = name.Split('-', StringSplitOptions.RemoveEmptyEntries);
        return name.Length >= 3 && parts.Length > 0 && parts.All(_words.Contains);
    }

    // The PC itself, the person's own network, or a device linked to it: a page there is not on the internet.
    private static bool InPersonsNetwork(IPAddress ip)
    {
        if (ip.IsIPv4MappedToIPv6)
        {
            ip = ip.MapToIPv4();
        }

        if (IPAddress.IsLoopback(ip))
        {
            return true;
        }

        if (ip.AddressFamily == System.Net.Sockets.AddressFamily.InterNetworkV6)
        {
            return ip.IsIPv6LinkLocal || ip.IsIPv6SiteLocal || ip.IsIPv6UniqueLocal;
        }

        byte[] bytes = ip.GetAddressBytes();
        return bytes[0] == 10
            || (bytes[0] == 172 && bytes[1] is >= 16 and <= 31)
            || (bytes[0] == 192 && bytes[1] == 168)
            || (bytes[0] == 169 && bytes[1] == 254);
    }

    // Every word of the name is one the person said in this session («doom eternal» in «pon Doom Eternal»).
    private bool Said(string name)
    {
        string[] words = [.. Regex.Split(Folded(name), @"[^\p{L}\p{Nd}]+").Where(word => word.Length > 0)];
        return words.Length > 0 && words.All(_words.Contains);
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
