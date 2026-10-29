using System.Globalization;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.App;

/// <summary>
/// BAXY Renew al máximo 11.5 (identity: «puede entrar información, no puede salir contenido del usuario»; lethal
/// trifecta, OWASP LLM01, CaMeL): in a turn the person opened, a call waits for their «sí» only for what is really
/// dangerous. Two cases. A page address to a host that came neither from this session's results (their address fields:
/// a search result, a page fetched or read, a tab) nor from the person's words (the site's name, «youtube» for
/// www.youtube.com), <c>host_not_from_session</c>, when the address carries something (a path past «/», a query, a
/// fragment, a name before «@»), is an IP literal or names a port other than its scheme's: the way out for what a page
/// told the model to send. And a game the person did not name, <c>game_title_not_said</c>. A search followed by the
/// fetch of one of its results never waits. An IP in the person's own network (loopback, private, link-local) goes; one
/// at any other IP waits unless the person wrote it or a result gave it (auditoría de la App, 2026-10-23: a fetch of
/// «http://203.0.113.9/?d=…» left the PC unasked). Owner's decision, 2026-10-25: only what is destructive or really
/// dangerous asks, BAXY must not bother the person all the time; so searching or looking something up on the web never
/// waits, whatever of the person's text or data it carries, a bare site by its name («https://ejemplo.com»,
/// «ejemplo.com/») goes since it carries nothing past its host, and a ping sends no page. Which calls go out is the
/// catalog's typed fact (al máximo 5.1: the network effect, with the call's exact arguments), and the address is the
/// call's <c>url</c>. A heartbeat holds every such call already (NativeTurnLoop.BeatProposes). Before any of that, a
/// search or a message with an argument that is the person's to say and that they did not goes back to the model
/// (<see cref="Unsaid"/>).
/// </summary>
internal sealed class NetworkEgress
{
    /// <summary>The most result hosts a held call's result lists (<see cref="ResultHosts"/>).</summary>
    internal const int MaximumResultHosts = 8;

    // A result's text longer than this (a snippet, a page) gives no words to a search: a title, a name or a value does.
    private const int MaximumGivenLength = 120;

    private readonly HashSet<string> _hosts = new(StringComparer.Ordinal);
    private readonly HashSet<string> _words = new(StringComparer.Ordinal);
    private readonly List<string> _resultHosts = [];
    private readonly HashSet<string> _queriesRefused = new(StringComparer.Ordinal);

    // A channel a message was refused by, with the last turn it was refused in (_turns counts the person's turns) and
    // whether that call asked the person's «sí» before it went, and the last turn that ended with the model's question.
    private readonly Dictionary<string, (int Turn, bool Confirmed)> _channelsRefused = new(StringComparer.Ordinal);
    private int _turns;
    private int _asked = -1;

    // The words this session's results and memory reads gave in their short texts (a title, a name, a value; never a
    // page's text nor BAXY's own fields beside «observed»): a search may take its words from them («pon un video de él»
    // after a result named him).
    private readonly HashSet<string> _given = new(StringComparer.Ordinal);

    // The person's words now and just before, folded: what a message's channel is weighed against.
    private string _latest = string.Empty;
    private string _previous = string.Empty;

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

        return Text(arguments["url"]) is { } url && UriOf(url) is { } address
            && Normalized(address.Host) is { Length: > 0 } host && !Grounded(host)
            && (Carries(address) || address.HostNameType is UriHostNameType.IPv4 or UriHostNameType.IPv6
                || !address.IsDefaultPort)
                ? "host_not_from_session"
                : null;
    }

    /// <summary>
    /// Why a call goes back to the model before it runs, and what it does next; null: it goes. Feria 2026-10-27, an
    /// argument that is the person's to say and that they did not (a form compared, never what they meant):
    /// <list type="bullet">
    /// <item>A greeting asked for someone in the room opened a messaging client with a draft: a message.draft or
    /// message.send by a channel their words now or just before did not name (the answer to the model's question keeps
    /// what it asked), <c>channel_not_said</c>; a message.send by that channel again in that turn goes, as written, for a
    /// channel they named in other words (one the ear wrote otherwise), since the person is asked before it goes, while a
    /// draft by it waits the rest of the turn. When that turn ended with the model's question, in the turn right after it
    /// a message by that channel goes (their «sí» to «¿le escribo por …?»), and that channel counts as said in that turn
    /// and the next. Aid «said_channel».</item>
    /// <item>A creator's name searched as another one that sounds alike, a question's subject searched as another word: a
    /// call that goes out with a query (web.search only by the sources that search its text) whose words share none of
    /// theirs in this session nor of what its results and memory gave, <c>query_not_said</c>, once for those words; the
    /// same words again go, as written, for a search they asked in other words. Aid «said_query».</item>
    /// </list>
    /// </summary>
    internal (string Code, string Next)? Unsaid(string operation, JsonObject arguments)
    {
        if (operation is "message.draft" or "message.send" && ModelAids.On(ModelAids.SaidChannel)
            && Text(arguments["channel"]) is { } channel
            && !Joined(_previous + " " + _latest).Contains(Joined(channel), StringComparison.Ordinal))
        {
            // A message that reaches a person (the catalog's external_communication: message.send, which RiskPolicy asks
            // about even in Bypass) waits for their «sí» before it goes; a draft is written in their client unasked.
            bool confirmed = ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor)
                && descriptor?.Risk == OperationRisks.ExternalCommunication;

            // By the channel alone: the model may word the recipient otherwise when it calls again.
            string refused = Joined(channel);
            if (_channelsRefused.TryGetValue(refused, out (int Turn, bool Confirmed) last))
            {
                int refusedIn = last.Turn;
                if (refusedIn == _turns && confirmed && last.Confirmed)
                {
                    // Called again in the turn it was refused in, for a channel the person named in other words (one
                    // the ear wrote otherwise): their «sí» to the message is the check.
                    return null;
                }

                if (refusedIn == _turns - 1 && _asked == refusedIn)
                {
                    // Their answer to the model's question: the channel counts as said in this turn and the next.
                    _latest += " " + Folded(channel);
                    return null;
                }
            }

            _channelsRefused[refused] = (_turns, confirmed);
            return ("channel_not_said", $"nothing ran: the person did not name {channel} now nor just before; if they "
                + "spoke to someone there, answer them in words; if they want a message sent, ask them by which channel"
                + (confirmed ? "; if they named this channel in other words, call it again exactly as before: they are "
                    + "asked before it goes" : string.Empty));
        }

        // web.search's currency, sports and places sources search their typed fields, not the query's text.
        if (!ModelAids.On(ModelAids.SaidQuery) || !NativeTurnLoop.Has(operation, arguments, OperationEffects.Network)
            || Text(arguments["query"]) is not { } query
            || Text(arguments["source"]) is not (null or "web" or "news" or "encyclopedia"))
        {
            return null;
        }

        string[] words = [.. Regex.Split(Folded(query), @"[^\p{L}\p{Nd}]+").Where(static word => word.Length >= 4)];
        // Ajuste c3, e2e E008 («busca en internet en qué año se fundó la ONU», query «año fundación ONU»: refused in 12 of
        // 12 runs, and 3 of them told the person nothing was searched): a word under 4 letters is weighed only when the
        // query writes it as an acronym, 2 or 3 capitals («ONU», «BBC»), the way a name too short for the rule above is
        // written; it is the person's when they said it or a result gave it, exactly. A short word in lower case or with
        // one capital («de», «Los») is still not weighed.
        string[] acronyms = [.. Regex.Split(query, @"[^\p{L}\p{M}\p{Nd}]+")
            .Where(static word => word.Length is 2 or 3 && word.All(char.IsUpper))
            .Select(Folded)];
        if (words.Length == 0 || words.Any(word => _words.Concat(_given).Any(said => SameWord(
                SaidFolders.Sounded(word).Trim(), SaidFolders.Sounded(said).Trim())))
            || acronyms.Any(acronym => _words.Contains(acronym) || _given.Contains(acronym))
            || !_queriesRefused.Add(operation + "\n" + string.Join(' ', words)))
        {
            return null;
        }

        return ("query_not_said", "nothing ran: this search has none of the person's words nor of what this session's "
            + "results and memory gave; call it again with their words, names exactly as they said them, even ones you do "
            + "not know; if they asked it in these words, call it again exactly as before");
    }

    /// <summary>
    /// The person's words in this session, and the addresses they wrote or dictated in them. <paramref name="answering"/>:
    /// they answer the call that waits for their «sí», and the words they said before it are still the ones just before.
    /// </summary>
    internal void Heard(string words, bool answering = false)
    {
        if (answering)
        {
            _latest += " " + Folded(words);
        }
        else
        {
            _previous = _latest;
            _latest = Folded(words);
            _turns++;
        }

        Collect(words, _words);

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

    /// <summary>The model asked the person something, and the turn ends waiting for their answer.</summary>
    internal void Asked() => _asked = _turns;

    /// <summary>A call's result as the model reads it: its addresses, and the words a search may take.</summary>
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
        Gather(facts?["observed"]);
    }

    /// <summary>A new session: nothing seen or heard in the last one counts.</summary>
    internal void Reset()
    {
        _hosts.Clear();
        _words.Clear();
        _resultHosts.Clear();
        _queriesRefused.Clear();
        _channelsRefused.Clear();
        _given.Clear();
        _latest = _previous = string.Empty;
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

    private void Gather(JsonNode? node)
    {
        switch (node)
        {
            case JsonObject facts:
                foreach ((_, JsonNode? value) in facts)
                {
                    Gather(value);
                }

                break;
            case JsonArray items:
                foreach (JsonNode? item in items)
                {
                    Gather(item);
                }

                break;
            case JsonValue value when value.TryGetValue(out string? text) && text.Length <= MaximumGivenLength:
                Collect(text, _given);
                break;
        }
    }

    private static void Collect(string text, HashSet<string> words)
    {
        foreach (string word in Regex.Split(Folded(text), @"[^\p{L}\p{Nd}]+"))
        {
            if (word.Length > 0)
            {
                words.Add(word);
            }
        }
    }

    private bool Grounded(string host)
    {
        if (IPAddress.TryParse(host.Trim('[', ']'), out IPAddress? ip))
        {
            return InPersonsNetwork(ip) || _hosts.Contains(host) || _hosts.Contains(ip.ToString());
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

    // One word with another ending, run together with the next or spelled otherwise by the ear (as they sound,
    // SaidFolders.Sounded: «vianca» is «bianca»): «recetas» for «receta», «zentrovox» for «zentro vox», «alcaldesa» for
    // «alcaldeza» (a start of 5 letters in common, or a word of 4 or more that starts the other), never two that only
    // start alike («aurora» and «auronplay»).
    private static bool SameWord(string word, string said)
    {
        int common = 0;
        while (common < word.Length && common < said.Length && word[common] == said[common])
        {
            common++;
        }

        return common >= 5 || (common >= 4 && common == Math.Min(word.Length, said.Length));
    }

    // Letters and digits alone: «Whats App» is «whatsapp».
    private static string Joined(string text) => Regex.Replace(Folded(text), @"[^\p{L}\p{Nd}]+", string.Empty);

    // Every word of the name is one the person said in this session («doom eternal» in «pon Doom Eternal»).
    private bool Said(string name)
    {
        string[] words = [.. Regex.Split(Folded(name), @"[^\p{L}\p{Nd}]+").Where(word => word.Length > 0)];
        return words.Length > 0 && words.All(_words.Contains);
    }

    private static string HostOf(string address) => UriOf(address) is { } uri ? Normalized(uri.Host) : string.Empty;

    private static Uri? UriOf(string address)
    {
        string given = address.Trim();
        return Uri.TryCreate(given, UriKind.Absolute, out Uri? uri) && uri.Host.Length > 0 ? uri
            : Uri.TryCreate("http://" + given, UriKind.Absolute, out uri) ? uri
            : null;
    }

    // What an address takes to its host besides the host itself: a path past «/», a query, a fragment or a name before
    // «@». A bare site («https://ejemplo.com», «ejemplo.com/») carries nothing.
    private static bool Carries(Uri address) =>
        address.AbsolutePath is not ("/" or "") || address.Query.Length > 0 || address.Fragment.Length > 0
        || address.UserInfo.Length > 0;

    private static string Normalized(string host)
    {
        string name = host.Trim().TrimEnd('.').ToLowerInvariant();
        return name.StartsWith("www.", StringComparison.Ordinal) ? name[4..] : name;
    }

    // Lower case without accents: «Ñuñoa» is «nunoa» (also how a conversation is found by its title, FieldProductChannel).
    internal static string Folded(string text)
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
}
