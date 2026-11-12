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
/// dangerous. Two cases. An address (a page's, or the host a ping names) to a host that came neither from this
/// session's results (their address fields: a search result, a page fetched or read, a tab) nor from the person's
/// words (the site's name, «youtube» for www.youtube.com), <c>host_not_from_session</c>: the way out for what a page
/// told the model to send. And a game the person did not name, <c>game_title_not_said</c>. A search followed by the
/// fetch of one of its results never waits. An IP in the person's own network (loopback, private, link-local) goes; one
/// at any other IP waits unless the person wrote it or a result gave it (auditoría de la App, 2026-10-23: a fetch of
/// «http://203.0.113.9/?d=…» left the PC unasked). Owner's decision, 2026-10-25: only what is destructive or really
/// dangerous asks, BAXY must not bother the person all the time; so searching or looking something up on the web never
/// waits, whatever of the person's text or data it carries, and a site said by its name opens. Revisión de privacidad
/// 2026-11-09 (PRIV-01): a bare site nobody gave went too («it carries nothing past its host») and a ping was not
/// weighed; the host's own name carries (63 octets a label, 255 a name, RFC 1035 §2.3.4), so a host nobody gave waits
/// whatever its address carries, and every label of it is one somebody gave. Which calls go out is the catalog's typed
/// fact (al máximo 5.1: the network effect, with the call's exact arguments), and the address is the call's
/// <c>url</c>, or a ping's <c>host</c>. A heartbeat holds every such call already (NativeTurnLoop.BeatProposes).
/// Before any of that, a search or a message with an argument that is the person's to say and that they did not goes
/// back to the model (<see cref="Unsaid"/>).
/// </summary>
internal sealed class NetworkEgress
{
    /// <summary>The most result hosts a held call's result lists (<see cref="ResultHosts"/>).</summary>
    internal const int MaximumResultHosts = 8;

    // A result's text longer than this (a snippet, a page) gives no words to a search: a title, a name or a value does.
    private const int MaximumGivenLength = 120;

    // The game catalog whose store game.store.page opens (GameStoreHandler), and the shortest title weighed against a link.
    private const string StoreCatalog = "steam";
    private const int MinimumLinkTitle = 4;

    private readonly HashSet<string> _hosts = new(StringComparer.Ordinal);
    private readonly HashSet<string> _words = new(StringComparer.Ordinal);

    // The words of each thing the person said in this session, in the order they said them (SaidRunTogether).
    private readonly List<string[]> _said = [];
    private readonly List<string> _resultHosts = [];
    private readonly HashSet<string> _queriesRefused = new(StringComparer.Ordinal);

    // The tabs browser.tabs.list read (title, active) and the person's turn it read them in; a close refused for a tab not
    // named goes once in that turn (said_tab).
    private (string Title, bool Active)[] _tabs = [];
    private int _tabsTurn = -1;
    private int _tabRefusedTurn = -1;

    // The person's turn one of BAXY's own calls went back in, for an open window their words name (own_named_window, once).
    private int _exitRefusedTurn = -1;

    // The person's turn in which a call other than a change of BAXY's own settings came back (OwnBrakes: a brake relaxed
    // after it is the model's means to something else, never what the person asked first).
    private int _calledTurn = -1;

    // The fewest letters of a part of a tab's title weighed with its words run together («chat gpt» names «ChatGPT»).
    private const int MinimumTabWord = 4;

    // A call refused for an application not said, by turn, operation and application (application_not_said goes once).
    private readonly HashSet<string> _applicationsRefused = new(StringComparer.Ordinal);

    // The links of the last page read (browser.page.read), the browser it was read in and the person's turn it was read in.
    private string[] _pageLinks = [];
    private string _pageBrowser = string.Empty;
    private int _pageTurn;

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
    private string _latestWritten = string.Empty;
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

        // COR1 (VIVO3 A3, 2 de 2: refused for «Búsqueda web» off, the model switched it back on with baxy.settings.set and
        // played the video): one of BAXY's own brakes is the person's to relax. The change goes unasked only when a
        // clause of this turn's words ends in that setting's name as Ajustes shows it and no other call came back first
        // in the turn; any other waits for their «sí», as a game they did not name. A form compared: «on» and «off»
        // have no name to weigh, so the order of the turn stands for the value (what the model does after another call
        // is its own idea), and the name at the end of the clause for what is asked («enciende la búsqueda web»; in
        // «haz una búsqueda web de panaderías» the name is how they ask for something else, which follows it).
        // TPV1: Bypass's «on» waits for the «sí» even when named, and a tool profile is asked for by its own name.
        if (OwnBrakes.Relaxed(operation, arguments) is { } brake
            && (OwnBrakes.AlwaysAsks(brake) || !AskedNow(OwnBrakes.Names(brake, arguments))))
        {
            return OwnBrakes.Cause;
        }

        if (!NativeTurnLoop.Has(operation, arguments, OperationEffects.Network))
        {
            return null;
        }

        // Revisión de privacidad 2026-11-09 (PRIV-01): a host nobody gave went when its address carried nothing past it,
        // and a ping (its address is «host») was never weighed. The name itself carries: every label of it reaches the
        // server that answers for the name above it, whether or not a page is there (RFC 1035 §2.3.4: 63 octets a
        // label, 255 a name; the DNS channel of MITRE ATT&CK T1048 and T1071.004), and a ping resolves it first.
        // An address whose host cannot be read is nobody's either.
        return (Text(arguments["url"]) ?? Text(arguments["host"])) is { } given
            && (HostOf(given) is not { Length: > 0 } host || !Grounded(host))
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
    /// and the next. Encargo 58 (S03): a message.send.test is a message too (it asks before it goes, like message.send).
    /// Aid «said_channel».</item>
    /// <item>A creator's name searched as another one that sounds alike, a question's subject searched as another word: a
    /// call that goes out with a query (web.search only by the sources that search its text) whose words share none of
    /// theirs in this session nor of what its results and memory gave, <c>query_not_said</c>, once for those words; the
    /// same words again go, as written, for a search they asked in other words. Aid «said_query».</item>
    /// <item>Banco de uso 2026-11-03 (S01, S05, S06): «en la página de streaming de prueba ponme …» played it in a streaming
    /// service and «en el chat de prueba …» went to a chat client, with the window they named open: a call whose closed
    /// argument (other than a message's channel, the item above) holds an application the alias data know and their words
    /// now or just before do not name, while their words name open windows (<paramref name="named"/>) none of which is
    /// that application's, <c>application_not_said</c>, once in the turn for that call and application; the same call
    /// again goes, as written. Aid «named_window_app».</item>
    /// </list>
    /// Banco uso-cf8d (U40, R13): with the open windows the person named (<paramref name="named"/>, asked only for a
    /// channel not said) the next says the calls that reach them, their process filled in, in place of the question.
    /// </summary>
    internal (string Code, string Next)? Unsaid(string operation, JsonObject arguments, Func<JsonArray>? named = null)
    {
        if (operation is "message.draft" or "message.send" or "message.send.test" && ModelAids.On(ModelAids.SaidChannel)
            && Text(arguments["channel"]) is { } channel
            && !Joined(_previous + " " + _latest).Contains(Joined(channel), StringComparison.Ordinal)
            // Encargo 12: a channel is said by its name or by one of its non-ambiguous abbreviations as a whole word
            // («… por wsp» names WhatsApp): the owner's one accepted help, a name-equivalence list (ApplicationAliases).
            && !ApplicationAliases.Names(_previous + " " + _latest, channel))
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
            string reaching = Reaching(named?.Invoke() ?? [], Text(arguments["text"]));
            return ("channel_not_said", "nothing ran: "
                + (reaching.Length > 0 ? reaching : $"the person did not name {channel} now nor just before; if they spoke "
                    + "to someone there, answer them in words; if they want a message sent, ask them by which channel")
                + (confirmed ? "; if they named this channel in other words, call it again exactly as before: they are "
                    + "asked before it goes" : string.Empty));
        }

        // actualizar-ordenes-app (control e64-H-C03): without tab a close acts on the active tab, and a switch_tab goes nowhere.
        // When this turn's tab list has another tab their words name, and the active one is not named, it goes back once with
        // that title, as game_title_not_said and channel_not_said do with what the person did not say. A form compared: the
        // model may mean the active tab, and the same call again runs. EFE1 (mapa G-05; base c8340433b, modelo de serie, 3
        // semillas): the words are this turn's alone. A tab the turn before asked about sent «cierra esta pestaña» back
        // with its title, and the model closed that tab 18 of 18.
        if (operation == "browser.control" && ModelAids.On(ModelAids.SaidTab) && Text(arguments["action"]) is "close" or "switch_tab"
            && Text(arguments["tab"]) is null && _tabsTurn == _turns && _tabRefusedTurn != _turns && ListedTabNamed() is { } tab)
        {
            _tabRefusedTurn = _turns;
            string active = _tabs.FirstOrDefault(static t => t.Active).Title is { Length: > 0 } shown ? $", «{shown}»," : string.Empty;
            string without = Text(arguments["action"]) == "close"
                ? $"without tab this closes the active tab{active} which the person did not name"
                : "without tab this goes to no tab";
            return ("tab_not_said", $"nothing ran: {without}; they named the tab «{tab}»: call it again with tab \"{tab}\", or "
                + "exactly as before if they meant the active one");
        }

        // actualizar-ordenes-app (pestanas_ho T14, T24): one of BAXY's own calls (closing itself, a setting of its own, its update)
        // while the person's words name an open window or one of its tabs (NamedWindows reads both) goes back once with what
        // they named, as said_tab does: a form compared, never what they meant; if they asked BAXY itself, it runs again.
        // EFE1 (mapa G-05, D-07, RED-1; base c8340433b, modelo de serie, 3 semillas): held by what the turn before named
        // («Abre YouTube», then «BAXY, ciérrate»), BAXY closed 0 of 30 and 21 of the 30 answers offered closing that
        // window; its voice went off 3 of 9. This guard reads this turn's words alone (SaidNow): an order to BAXY itself
        // says nothing of the window of another turn, and the name they call BAXY by names no window either.
        if (operation is "baxy.exit" or "baxy.settings.set" or "baxy.update" && ModelAids.On(ModelAids.OwnNamedWindow)
            && named is not null && _exitRefusedTurn != _turns && SaidNow(named()) is { Count: > 0 } openNamed)
        {
            _exitRefusedTurn = _turns;
            bool exit = operation == "baxy.exit";
            return ("own_names_window", (exit ? "nothing ran and BAXY stays open" : "nothing ran and BAXY did not change")
                + ": the person's words name "
                + string.Join(", ", openNamed.OfType<JsonObject>().Select(static window => "«" + (string?)window["title"] + "»"
                    + (window["tabs"] is JsonArray tabs && tabs.Count > 0
                        ? " (its tab " + string.Join(", ", tabs.Select(static tab => "«" + (string?)tab?["title"] + "»")) + ")"
                        : string.Empty)))
                + (exit
                    ? "; close that with its own call (browser_control close with tab, or app_close), or call baxy_exit again "
                        + "exactly as before if they asked BAXY itself to close"
                    : "; act on that with its own calls (browser_control with tab, app_close, the window tools), or call "
                        + WireNames.Of(operation) + " again exactly as before if they asked it of BAXY itself"));
        }

        if (named is not null && ModelAids.On(ModelAids.NamedWindowApp) && ApplicationUnsaid(operation, arguments) is { } app
            && named() is { Count: > 0 } windows && !windows.OfType<JsonObject>().Any(window => Holds(window, app))
            && _applicationsRefused.Add(string.Join('\n', _turns, operation, Joined(app))))
        {
            return ("application_not_said", ReachingFirst(windows)
                + $"; this call ran nothing: the person did not name {app} now nor just before");
        }

        // Encargo 115 (H2, T1, T3, «en el libro frutas…» with that workbook open): the model made a new file named after the
        // window, libro_frutas.txt with the table well formed, or a workbook titled Frutas. A form compared: a new file whose
        // name holds the name of a window the person's words name, and no extension of theirs. The model may mean it: the same
        // call again runs.
        if (named is not null && ModelAids.On(ModelAids.NamedWindowApp) && NewFileName(operation, arguments) is { } made
            && named() is { Count: > 0 } open && open.OfType<JsonObject>().Any(window => NamedAfter(made, window))
            && _applicationsRefused.Add(string.Join('\n', _turns, operation, Joined(made))))
        {
            return ("new_file_named_after_window", ReachingFirst(open) + "; this call ran nothing: it would make a new file, "
                + $"«{made}», and leave them as they are. If the person asked for a new file, call it again exactly as before");
        }

        // web.search's currency and places sources search their typed fields, not the query's text.
        if (!ModelAids.On(ModelAids.SaidQuery) || !NativeTurnLoop.Has(operation, arguments, OperationEffects.Network)
            // Encargo 119 (F12): media.play.exact's title goes out to Spotify's search as a query does, and a name the model
            // altered as it copied it («quiero <artista>» sent as another word) ran 25 s to say nothing was found.
            || (Text(arguments["query"]) ?? (operation == "media.play.exact" ? Text(arguments["title"]) : null)) is not { } query
            || Text(arguments["source"]) is not (null or "web" or "encyclopedia"))
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

        // Encargo 119 (F12): told only to use their words, the model gave the name back and asked which song (name kept 35/40,
        // searched 5/40; base 4/40, the altered name searched in the rest); with what they said written in the call, 20/35.
        if (operation == "media.play.exact" && SaidAlike(query) is { } alike)
        {
            return ("query_not_said", $"{WireNames.Call("media.play.query", new() { ["provider"] = Text(arguments["provider"]), ["query"] = alike })} "
                + "searches Spotify for what the person said (an artist, a style or a song) and plays its first result; this "
                + $"call ran nothing: they did not say «{query}»");
        }

        return ("query_not_said", "nothing ran: this search has none of the person's words nor of what this session's "
            + "results and memory gave; call it again with their words, names exactly as they said them, even ones you do "
            + "not know; if they asked it in these words, call it again exactly as before");
    }

    /// <summary>
    /// Banco de uso 2026-11-03 (S07): «¿qué estado tengo puesto en el chat de prueba?» read the clipboard, failed, and the
    /// model told the person nothing was copied. What a failed call with no next of its own says (NativeTurnLoop asks
    /// for the turn's first call) when the person's words name open windows (<paramref name="named"/>, read only then)
    /// and none of the call's texts is in their titles or processes: the call that reaches them first (a form compared;
    /// the model decides). Null: nothing. Aid «named_window_app».
    /// </summary>
    internal static string? Unreached(JsonObject arguments, Func<JsonArray> named)
    {
        if (!ModelAids.On(ModelAids.NamedWindowApp) || named() is not { Count: > 0 } windows)
        {
            return null;
        }

        string[] given = [.. arguments.Select(static argument => Text(argument.Value)).OfType<string>().Select(Joined)
            .Where(static text => text.Length >= 3)];
        if (windows.OfType<JsonObject>().Any(window => given.Any(text =>
                Joined((string?)window["title"] + " " + (string?)window["process"]).Contains(text, StringComparison.Ordinal))))
        {
            return null;
        }

        return ReachingFirst(windows) + "; this call is not on them";
    }

    /// <summary>
    /// Banco de uso 05-11 (U06): «abre YouTube y búscame…» failed in BAXY's own browser, a tab of the person's browser had
    /// YouTube in its title, and a next leading with the call took the model there (a next that starts with the call is made:
    /// encargo 28), where it pressed two links with their accounts on. What the next says instead when every window their
    /// words name is a browser named only by what its tabs show, and they said no browser (the last word of the title's last
    /// part, its name, nor its process): what is there, and the call last, after their yes. Null: nothing to say. A form
    /// compared; whether to go there is theirs.
    /// </summary>
    internal string? BrowserUnsaid(JsonArray named)
    {
        JsonObject[] windows = [.. named.OfType<JsonObject>()];
        string said = SaidSpaced();
        if (windows.Length == 0 || !windows.All(static window => window["tabs"] is JsonArray { Count: > 0 })
            || windows.Any(window => BrowserSaid(said, window)))
        {
            return null;
        }

        string shown = string.Join("; ", windows.Select(static window => string.Join(", ",
            (window["tabs"] as JsonArray ?? []).OfType<JsonObject>().Select(static tab => "«" + (string?)tab["title"] + "»"
                + ((bool?)tab["shown"] == true ? " (shown)" : " (not the one shown)"))) + " in «" + (string?)window["title"] + "»"));
        string call = string.Join(" or ", windows.Select(static window => WireNames.Of("input.visible.controls") + " "
            + new JsonObject { ["application"] = (string?)window["process"] ?? (string?)window["title"] }
                .ToJsonString(SaidFolders.AsWritten)));
        return $"this call failed. The person's own browser is open with what their words name: {shown}; it holds their accounts "
            + $"and they did not ask for it: tell them this failed and ask whether to do it there; only after their yes, {call} reads it";
    }

    private static bool BrowserSaid(string said, JsonObject window)
    {
        string browser = Regex.Split((string?)window["title"] ?? string.Empty, @"\s+[-|–—·]\s+")[^1];
        string name = Spaced(browser).Split(' ')[^1];
        string process = Spaced((string?)window["process"] ?? string.Empty);
        return (name.Length > 0 && said.Contains(" " + name + " ", StringComparison.Ordinal))
            || (process.Length > 0 && said.Contains(" " + process + " ", StringComparison.Ordinal));
    }

    /// <summary>
    /// Encargo 65 (cosecha F2, uso real 03-11): a request for the newest mail of one sender in a webmail named by the
    /// person, with that site open in a tab of their browser, ran email.latest.read (Outlook's newest mail, another
    /// sender), and the model said there was no mail from that sender. What the turn's first call, completed, says when its result names the application whose data
    /// it read (<paramref name="source"/>: Outlook) and the person's words name open windows or tabs
    /// (<paramref name="named"/>, read only then) none of which shows that application: the call that reaches them first,
    /// and that this result is of that application alone (UFO2 and Navi: the agent acts on what is open; Anthropic,
    /// «Writing effective tools for agents»: a result says what it covers). A form compared; the model decides. Null:
    /// nothing. Aid «named_tab_source».
    /// </summary>
    internal static string? Elsewhere(string source, Func<JsonArray> named)
    {
        string joined = Joined(source);
        if (!ModelAids.On(ModelAids.NamedTabSource) || joined.Length == 0 || named() is not { Count: > 0 } windows
            || windows.OfType<JsonObject>().Any(window => Joined(Shown(window)).Contains(joined, StringComparison.Ordinal)))
        {
            return null;
        }

        return ReachingFirst(windows) + $"; this result is of {source} alone, not of them";
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
            _latestWritten = words;
            _turns++;
        }

        Collect(words, _words);
        _said.Add([.. Regex.Split(Folded(words), @"[^\p{L}\p{Nd}]+").Where(static word => word.Length > 0)]);

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
        if (operation != OwnBrakes.Operation)
        {
            _calledTurn = _turns;
        }

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
        if (operation == "browser.tabs.list" && facts?["observed"]?["tabs"] is JsonArray tabs)
        {
            _tabs = [.. tabs.OfType<JsonObject>()
                .Select(static tab => (Title: Text(tab["title"]) ?? string.Empty, Active: tab["active"] is JsonValue on
                    && on.TryGetValue(out bool active) && active))
                .Where(static tab => tab.Title.Length > 0)];
            _tabsTurn = _turns;
        }

        if (operation == "browser.page.read" && facts?["observed"] is JsonObject page
            && Text(page["browser"]) is { } browser && page["links"] is JsonArray links)
        {
            _pageLinks = [.. links.Select(Text).OfType<string>()];
            _pageBrowser = browser;
            _pageTurn = _turns;
        }
    }

    /// <summary>
    /// Encargo 113 (banco de uso R06): a page was read and «ábreme la ficha de ese» went to the store's page by the title of
    /// one of its links; not in the store, the model gave up or made up a store address. The failure of a game.store.page
    /// whose title is a link of the page read now or just before, with the store not said in their words, says so with the
    /// look at that page. It runs first, and what they asked of the store still goes to the store when it has it. A form
    /// compared; the model decides. Aid «link_of_open_page».
    /// </summary>
    internal string WithLinkOfPage(string operation, JsonObject arguments, string observation)
    {
        if (operation != "game.store.page" || !ModelAids.On(ModelAids.LinkOfOpenPage)
            || LinkOfPage(Text(arguments["title"])) is not { } link
            || ApplicationPlaces.ApplicationOfCatalog(StoreCatalog) is not { } store
            || Joined(_previous + " " + _latest).Contains(Joined(store), StringComparison.Ordinal)
            || ApplicationAliases.Names(_previous + " " + _latest, store)
            || JsonNode.Parse(observation) is not JsonObject facts
            || Text(facts["error"]) != "game_title_not_found" || facts["observed"] is not JsonObject observed)
        {
            return observation;
        }

        observed["next"] = WireNames.Call("input.visible.controls", new JsonObject { ["application"] = _pageBrowser })
            + $" reads the page open in {_pageBrowser}, where \"{link}\" is a link, and {WireNames.Of("input.visible.click")} "
            + $"opens it; {store}'s store has no game called that, and nothing was opened: if the person asked for the store, "
            + "tell them that instead";
        return facts.ToJsonString(SaidFolders.AsWritten);
    }

    /// <summary>A new session: nothing seen or heard in the last one counts.</summary>
    internal void Reset()
    {
        _hosts.Clear();
        _words.Clear();
        _said.Clear();
        _resultHosts.Clear();
        _queriesRefused.Clear();
        _channelsRefused.Clear();
        _given.Clear();
        _pageLinks = [];
        _tabs = [];
        _tabsTurn = _tabRefusedTurn = _exitRefusedTurn = -1;
        _latest = _previous = _latestWritten = string.Empty;
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

        // A host a result or the person gave is that host as written, and the hosts above it, which carry less. PRIV-01:
        // every host under it counted too, so a page read sent «ana-gomez.recetas.example» to its own server unasked,
        // and on a site that gives each of its people a host, to another's.
        if (_hosts.Any(seen => host == seen || seen.EndsWith("." + host, StringComparison.Ordinal)))
        {
            return true;
        }

        // The site's own name, the label before its ending («youtube» in m.youtube.com, «bbc» in bbc.co.uk), is the
        // person's to say; and so is each label before it (PRIV-01: «lofi» in lofi.youtube.com went with the site's name
        // said, as any host under a site they named did).
        // An ending of two labels is a country's («co.uk», «com.ar», «gob.cl»: RFC 1591, the two-letter codes and the
        // categories registries keep under them); under any other ending the short label is somebody's own site
        // («ana.abc.example» is abc's, not a site called «ana»).
        string[] labels = host.Split('.');
        int named = labels.Length switch
        {
            1 or 2 => 0,
            _ => labels[^1].Length == 2 && labels[^2].Length <= 3 ? labels.Length - 3 : labels.Length - 2,
        };
        return labels[named].Length >= 3 && labels[..(named + 1)].All(SaidLabel);
    }

    // A label of a host is the person's when they said every part of it («rfc editor» for rfc-editor.org). Uso real
    // 02-11: «abre fackebook marketplace» held www.facebook.com/marketplace as a site nobody gave. A part of 5 letters or
    // more the person said with one letter changed, added or missing (as typed or as the ear wrote it) is theirs too; a
    // shorter one must be said as it is. PRIV-01, now that a bare site nobody gave waits: a site's name is written run
    // together and said with its words apart («la tercera» for latercera.com), so a part made of words they said, whole
    // and one after another in one thing they said, is theirs as well.
    private bool SaidLabel(string label)
    {
        string[] parts = label.Split('-', StringSplitOptions.RemoveEmptyEntries);
        return parts.Length > 0 && parts.All(part => _words.Contains(part)
            || (part.Length >= 5 && _words.Any(word => OneEditApart(word, part)))
            || SaidRunTogether(part));
    }

    // Whether the text is two or more words the person said one after another, in that order and in one thing they said,
    // written together. Revisión a ciegas de PRV1: any words of the session in any order counted, so «feria» of one turn
    // and «libre» of another made ferialibre a site they named.
    private bool SaidRunTogether(string text)
    {
        foreach (string[] said in _said)
        {
            for (int first = 0; first < said.Length - 1; first++)
            {
                int at = 0;
                for (int word = first; word < said.Length
                    && text.AsSpan(at).StartsWith(said[word], StringComparison.Ordinal); word++)
                {
                    at += said[word].Length;
                    if (at == text.Length)
                    {
                        if (word > first)
                        {
                            return true;
                        }

                        break;
                    }
                }
            }
        }

        return false;
    }

    // Whether two words differ by one letter changed, added or missing (Levenshtein distance 1).
    private static bool OneEditApart(string a, string b)
    {
        if (Math.Abs(a.Length - b.Length) > 1)
        {
            return false;
        }

        int start = 0;
        while (start < a.Length && start < b.Length && a[start] == b[start])
        {
            start++;
        }

        int endA = a.Length;
        int endB = b.Length;
        while (endA > start && endB > start && a[endA - 1] == b[endB - 1])
        {
            endA--;
            endB--;
        }

        return endA - start <= 1 && endB - start <= 1 && (endA - start) + (endB - start) >= 1;
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

    /// <summary>
    /// Banco de uso 2026-11-03 (U40, R13): the open windows the person's words now or just before name, for a message by
    /// a channel they did not say (a chat open in another application). A window is named when a part of its title
    /// (between « - », « | », « – », « — », « · ») of 4 letters or more is words they said, whole and in that order: a
    /// form compared, the model decides what to write where.
    /// </summary>
    /// <remarks>
    /// Banco de uso 2026-11-03 (R11, R12): «manda al Grupo de prueba …» named no window, since the chat was a row of the
    /// list inside one («Chat de prueba»). A window is named too when a visible row of its lists (<paramref name="rows"/>,
    /// the reader keeps only rows <see cref="NamesRow"/> accepts, and they are compared again here) is; the window carries
    /// those rows, and nothing else of the window is read.
    /// </remarks>
    /// <remarks>
    /// Encargo 65 (cosecha F2): a window is named too when a tab of its tab strip is (<see cref="NamesTab"/>); the window
    /// carries those tabs, each with whether it is the one shown.
    /// </remarks>
    internal JsonArray Named(
        IEnumerable<(string Title, string? Process)> windows,
        IEnumerable<VisibleRow>? rows = null)
    {
        var named = new JsonArray();
        var byWindow = new Dictionary<(string, string?), JsonObject>();
        string said = SaidSpaced();
        foreach ((string title, string? process) in windows)
        {
            if (Regex.Split(title, @"\s+[-|–—·]\s+").Any(part => SaidWhole(said, part)))
            {
                JsonObject window = new() { ["title"] = title, ["process"] = process };
                byWindow.TryAdd((title, process), window);
                named.Add(window);
            }
        }

        foreach ((string title, string? process, string row, bool tab, bool shown) in rows ?? [])
        {
            if (!(tab ? TabNamed(said, row) : SaidWhole(said, row)))
            {
                continue;
            }

            if (!byWindow.TryGetValue((title, process), out JsonObject? window))
            {
                window = new JsonObject { ["title"] = title, ["process"] = process };
                byWindow[(title, process)] = window;
                named.Add(window);
            }

            string key = tab ? "tabs" : "rows";
            JsonArray listed = window[key] as JsonArray ?? [];
            window[key] = listed;
            if (tab && !listed.Any(seen => (string?)seen?["title"] == row))
            {
                listed.Add(new JsonObject { ["title"] = row, ["shown"] = shown });
            }
            else if (!tab && !listed.Any(seen => (string?)seen == row))
            {
                listed.Add(row);
            }
        }

        return named;
    }

    /// <summary>
    /// Banco de uso 2026-11-03 (R11, R12): whether the person's words now or just before name a row of a list by its whole
    /// name, as a part of a window's title is named: its words of 4 letters or more, whole and in that order («Equipo Lunes
    /// 🌙» by «a Equipo Lunes», never «Equipo Lunes y Martes»). A form compared; the reader of the rows keeps no other.
    /// </summary>
    internal Func<string, bool> NamesRow()
    {
        string said = SaidSpaced();
        return row => SaidWhole(said, row);
    }

    /// <summary>
    /// Encargo 65 (cosecha F2): whether the person's words now or just before name a tab of a browser by its page's title:
    /// a part of it is named as a part of a window's title is, or a word of 4 letters or more of its first or last part,
    /// when that part has 2 words or fewer, is a word they said («en Gmail» names «Recibidos - ana@x.cl - Gmail», «en el
    /// Drive» names «Mi unidad - Google Drive»). A page's title names its site in its first or last part (W3C, WCAG 2
    /// technique G88 «Providing descriptive titles for Web pages»: the page and the site, as «Page - Site»; Google's own
    /// put the site first); a long part is the page's own words, which never name it alone. A form compared; the reader
    /// of the tabs keeps no other.
    /// </summary>
    internal Func<string, bool> NamesTab()
    {
        string said = SaidSpaced();
        return tab => TabNamed(said, tab);
    }

    /// <summary>
    /// Encargo 119 (F12): the run of the person's latest words, as they wrote it, closest in form to a name that has none of
    /// them: a name altered as it was copied («Zarzalito» for what they said, «Zorzalero»), at most half its letters apart
    /// (Levenshtein over the folded letters); null when none is that close, as a song's title they described and did not
    /// say. A form compared; the model decides.
    /// </summary>
    internal string? SaidAlike(string name)
    {
        string wanted = Joined(name);
        string[] said = Regex.Matches(_latestWritten, @"[\p{L}\p{M}\p{Nd}]+").Select(static word => word.Value).ToArray();
        int words = Regex.Count(name, @"[\p{L}\p{M}\p{Nd}]+");
        string? closest = null;
        double least = 0.5;
        for (int size = Math.Max(1, words - 1); size <= words + 1; size++)
        {
            for (int start = 0; start + size <= said.Length; start++)
            {
                string run = string.Join(' ', said, start, size);
                string joined = Joined(run);
                if (joined.Length < 4)
                    continue;
                double apart = LettersApart(wanted, joined) / (double)Math.Max(wanted.Length, joined.Length);
                if (apart <= least)
                {
                    (least, closest) = (apart, run);
                }
            }
        }

        return closest;
    }

    private static int LettersApart(string left, string right)
    {
        int[] previous = [.. Enumerable.Range(0, right.Length + 1)];
        for (int i = 1; i <= left.Length; i++)
        {
            int[] current = new int[right.Length + 1];
            current[0] = i;
            for (int j = 1; j <= right.Length; j++)
            {
                current[j] = Math.Min(Math.Min(previous[j] + 1, current[j - 1] + 1), previous[j - 1] + (left[i - 1] == right[j - 1] ? 0 : 1));
            }

            previous = current;
        }

        return previous[right.Length];
    }

    private string SaidSpaced() => " " + Spaced(_previous) + " " + Spaced(_latest) + " ";

    // The name the person calls BAXY by, as its own windows are titled (MainWindow, OverlayWindow), folded.
    private const string OwnName = "baxy";

    // Of the windows named now or just before (Named), the ones this turn's words name, each with the tabs and rows they
    // name now: what holds a call of BAXY's own. A part of a title, a tab's site or a row that is BAXY's own name and no
    // more names nothing: in «BAXY, ciérrate» it is the one they speak to (a folder or a page of that name stays out).
    private JsonArray SaidNow(JsonArray? windows)
    {
        var now = new JsonArray();
        string said = " " + Spaced(_latest) + " ";
        foreach (JsonObject window in (windows ?? []).OfType<JsonObject>())
        {
            string title = (string?)window["title"] ?? string.Empty;
            JsonNode[] tabs = [.. (window["tabs"] as JsonArray ?? []).OfType<JsonNode>()
                .Where(tab => TabNamed(said, (string?)tab["title"] ?? string.Empty, OwnName))];
            JsonNode[] rows = [.. (window["rows"] as JsonArray ?? []).OfType<JsonNode>()
                .Where(row => (string?)row is { } name && Spaced(name) != OwnName && SaidWhole(said, name))];
            if (tabs.Length == 0 && rows.Length == 0
                && !Regex.Split(title, @"\s+[-|–—·]\s+").Any(part => Spaced(part) != OwnName && SaidWhole(said, part)))
            {
                continue;
            }

            JsonObject kept = new() { ["title"] = title, ["process"] = (string?)window["process"] };
            if (tabs.Length > 0)
            {
                kept["tabs"] = new JsonArray([.. tabs.Select(static tab => tab.DeepClone())]);
            }

            if (rows.Length > 0)
            {
                kept["rows"] = new JsonArray([.. rows.Select(static row => row.DeepClone())]);
            }

            now.Add(kept);
        }

        return now;
    }

    // actualizar-ordenes-app (pestanas_ho T14): a comma parts a site from its motto too («Wikipedia, la enciclopedia libre»).
    // «own»: a part that is that name and no more, or that word of a site, is not counted (SaidNow).
    private static bool TabNamed(string said, string title, string? own = null)
    {
        string[] parts = Regex.Split(title.Trim(), @"\s+[-|–—·]\s+|,\s+");
        return parts.Any(part => Spaced(part) != own && SaidWhole(said, part))
            || SiteWordSaid(said, parts[0], own) || SiteWordSaid(said, parts[^1], own);
    }

    private static bool SiteWordSaid(string said, string part, string? own = null)
    {
        string[] words = Spaced(part).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return words.Length is > 0 and <= 2 && words.Any(word => word != own && word.Count(char.IsLetter) >= 4
            && said.Contains(" " + word + " ", StringComparison.Ordinal));
    }

    private static bool SaidWhole(string said, string text)
    {
        string part = Spaced(text);
        return part.Count(char.IsLetter) >= 4 && said.Contains(" " + part + " ", StringComparison.Ordinal);
    }

    // Banco uso-cf8d (U40, R13): the model read the windows named after «ask them by which channel» and asked it. The way
    // to them is the next, as the call itself with its argument filled in (Anthropic, «Writing effective tools for
    // agents»: actionable errors with a correctly formatted input; UFO2: the route that reaches the target first). Measured
    // with the model (encargo 20, U40 and R13, 5 seeds each): with the clause asking the channel after this one it asked
    // it 10 of 10; with «answer them in words» kept, 4 of 10 answers; with this alone, 9 of 10 looked at the window.
    // Banco de uso 2026-11-03 (R11, R12): a window named by a row of its lists says that row after its call («(its row
    // «Grupo de prueba»)»), the place in it the person's words name.
    // Banco uso-93f1 (U40): told only to write with input_text_type, the model typed with no index and the text went to
    // the focused menu bar (2 of 2); with the field by its index here, the index from its look (UFO AppUIExecutor:
    // set_edit_text takes the control id from the window's control list), 5 of 5 typed into the box, twice.
    // Banco ab-93-ce (R11, 0 of 2): after that, with «the person did not name whatsapp» leading, the model asked «¿Por
    // WhatsApp o por Discord?». Measured with the model (encargo 45, the whole turn): leading with what their words name
    // (the row and its window, and no channel), then the click on that row and the text to write, R11 reached the box and
    // «Enviar» 9 of 10 (the other asked before any call, in every arm) against 4-8 of 10, the p of a call after the
    // refusal 0.91 → 0.98; held-out messages 22 → 27 of 30, the controls as they were. Without «in what it shows», a
    // draft's refusal (S03 with message.send.test hidden) got the row clicked unread, at index 0, 4 of 10; with it, 10 of
    // 10, and R11, R12 and two held-out 20 of 20.
    private static string Reaching(JsonArray named, string? text)
    {
        JsonObject[] windows = [.. named.OfType<JsonObject>()];
        if (windows.Length == 0)
            return string.Empty;
        string[] rows = [.. windows.SelectMany(static window => window["rows"] as JsonArray ?? [])
            .Select(static row => (string?)row).OfType<string>()];
        string calls = string.Join(" or ", windows.Select(static window => new JsonObject
        {
            ["application"] = (string?)window["process"] ?? (string?)window["title"],
        }.ToJsonString(SaidFolders.AsWritten)));
        string click = WireNames.Of("input.visible.click") + rows.Length switch
        {
            0 => string.Empty,
            1 => $" on its row «{rows[0]}» in what it shows",
            _ => " on the row their words name in what it shows",
        };
        string write = text is null
            ? "write in it"
            : $"write {JsonSerializer.Serialize(text, SaidFolders.AsWritten)} in it";
        return $"the person's words name {string.Join(" and ", windows.Select(NamedBy))}, and no channel: "
            + $"{WireNames.Of("input.visible.controls")} {calls} reads {(windows.Length == 1 ? "it" : "each")}, then "
            + $"{click} and {WireNames.Of("input.text.type")} with the index of its field {write}";
    }

    // What of an open window the person's words name: the rows of its lists they name, or its title.
    private static string NamedBy(JsonObject window)
    {
        string[] rows = [.. (window["rows"] as JsonArray ?? []).Select(static row => "«" + (string?)row + "»")];
        string title = $"the open window «{(string?)window["title"]}»";
        return rows.Length switch
        {
            0 => title,
            1 => $"{rows[0]}, a row of {title}",
            _ => $"{string.Join(", ", rows)}, rows of {title}",
        };
    }

    // Banco de uso 2026-11-03 (S05): with the way to the window after the refusal, as Reaching says it, the model told
    // the person «the window open is that one, not the client» (2 of 2); the filled call first, then what this one did
    // (encargo 28: the call leading the next is made, a route after the failure is told).
    private static string ReachingFirst(JsonArray named)
    {
        JsonObject[] windows = [.. named.OfType<JsonObject>()];
        string calls = string.Join(" or ", windows.Select(static window => WireNames.Of("input.visible.controls") + " "
            + new JsonObject { ["application"] = (string?)window["process"] ?? (string?)window["title"] }
                .ToJsonString(SaidFolders.AsWritten) + RowsOf(window) + TabsOf(window)));
        string titles = string.Join(", ", windows.Select(static window => "«" + (string?)window["title"] + "»"));
        return $"{calls} reads the open {(windows.Length == 1 ? "window" : "windows")} their words name ({titles}), and "
            + $"{WireNames.Of("input.visible.click")} acts on what it shows";
    }

    // The link of the page read now or just before that bears this title, as the page shows it («… (edición larga)»).
    private string? LinkOfPage(string? title)
    {
        string joined = Joined(title ?? string.Empty);
        return _turns - _pageTurn > 1 || joined.Length < MinimumLinkTitle
            ? null
            : _pageLinks.FirstOrDefault(link => Joined(link).Contains(joined, StringComparison.Ordinal));
    }

    // The name of the new file a call would make; null when it adds to or replaces a file, or the person said its extension.
    private string? NewFileName(string operation, JsonObject arguments)
    {
        if (operation == "office.document.create")
            return Text(arguments["title"]);
        if (operation != "file.write" || arguments["append"] is JsonValue append && append.TryGetValue(out bool adds) && adds
            || Text(arguments["expectedSha256"]) is not null || Text(arguments["path"]) is not { } path)
            return null;
        string extension = System.IO.Path.GetExtension(path).TrimStart('.');
        return extension.Length > 0 && SaidSpaced().Contains(" " + Spaced(extension) + " ", StringComparison.Ordinal)
            ? null
            : System.IO.Path.GetFileNameWithoutExtension(path);
    }

    // Whether a file's name holds the name a window shows for what it has open: its title's first part, without an extension.
    private static bool NamedAfter(string file, JsonObject window)
    {
        string first = Regex.Split(((string?)window["title"] ?? string.Empty).Trim(), @"\s+[-|–—·]\s+|:\s+")[0];
        string name = Spaced(System.IO.Path.GetFileNameWithoutExtension(first));
        return name.Length >= 3 && (" " + Spaced(file) + " ").Contains(" " + name + " ", StringComparison.Ordinal);
    }

    // The value of a closed argument of the call (one of its schema's values) that is an application the alias data know,
    // when the person's words now or just before hold none of its forms; a message's channel is the channel rule's.
    private string? ApplicationUnsaid(string operation, JsonObject arguments)
    {
        if (!ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor) || descriptor is null)
        {
            return null;
        }

        string said = SaidSpaced();
        foreach (OperationArgumentProperty property in descriptor.ArgumentsSchema.Properties)
        {
            if (property.Name != "channel" && property.AllowedValues.Count > 0 && Text(arguments[property.Name]) is { } value
                && ApplicationAliases.FormsOf(value) is { Count: > 0 } forms
                && !forms.Any(form => said.Contains(" " + form + " ", StringComparison.Ordinal))
                && !Joined(said).Contains(Joined(value), StringComparison.Ordinal))
            {
                return value;
            }
        }

        return null;
    }

    // A window is the application's when its title or process holds one of its forms as whole words, or its name run
    // together («whatsapp» in «WhatsApp Beta»).
    private static bool Holds(JsonObject window, string application)
    {
        string shown = (string?)window["title"] + " " + (string?)window["process"];
        string spaced = " " + Spaced(shown) + " ";
        return ApplicationAliases.FormsOf(application).Any(form => spaced.Contains(" " + form + " ", StringComparison.Ordinal))
            || Joined(shown).Contains(Joined(application), StringComparison.Ordinal);
    }

    // Encargo 65: the tabs of a window the person's words name, each with whether it is the one shown; one that is not is
    // clicked in what the look shows first.
    private static string TabsOf(JsonObject window)
    {
        JsonObject[] tabs = [.. (window["tabs"] as JsonArray ?? []).OfType<JsonObject>()];
        if (tabs.Length == 0)
            return string.Empty;
        string click = WireNames.Of("input.visible.click");
        string Of(JsonObject tab) => "«" + (string?)tab["title"] + "»" + ((bool?)tab["shown"] == true
            ? ", shown"
            : $", not the one shown: {click} on it in what it shows");
        return $" (its {(tabs.Length == 1 ? "tab" : "tabs")} {string.Join("; ", tabs.Select(Of))})";
    }

    // What a window shows of itself to a comparison: its title, process, rows and tabs named.
    private static string Shown(JsonObject window) =>
        string.Join(' ', new[] { (string?)window["title"], (string?)window["process"] }
            .Concat((window["rows"] as JsonArray ?? []).Select(static row => (string?)row))
            .Concat((window["tabs"] as JsonArray ?? []).Select(static tab => (string?)tab?["title"]))
            .OfType<string>());

    private static string RowsOf(JsonObject window) =>
        window["rows"] is JsonArray { Count: > 0 } rows
            ? $" (its {(rows.Count == 1 ? "row" : "rows")} {string.Join(", ", rows.Select(static row => "«" + (string?)row + "»"))})"
            : string.Empty;

    // Folded words one space apart: «Sala  Turquesa,» is «sala turquesa».
    private static string Spaced(string text) =>
        string.Join(' ', Regex.Split(Folded(text), @"[^\p{L}\p{Nd}]+").Where(static word => word.Length > 0));

    // Letters and digits alone: «Whats App» is «whatsapp».
    private static string Joined(string text) => Regex.Replace(Folded(text), @"[^\p{L}\p{Nd}]+", string.Empty);

    // The one tab of the list, other than the active one, that the person's words of this turn name: as a browser's
    // tab strip is read (TabNamed), or by a part of its title with its words run together («chat gpt» names «ChatGPT»).
    // Null when the active tab is named too, or none or several are.
    private string? ListedTabNamed()
    {
        string said = " " + Spaced(_latest) + " ";
        string joined = Joined(_latest);
        bool Named(string title) => TabNamed(said, title) || Regex.Split(title.Trim(), @"\s+[-|–—·]\s+")
            .Any(part => Joined(part) is { Length: >= MinimumTabWord } whole && joined.Contains(whole, StringComparison.Ordinal));
        if (_tabs.Any(tab => tab.Active && Named(tab.Title)))
        {
            return null;
        }

        string[] named = [.. _tabs.Where(tab => !tab.Active && Named(tab.Title)).Select(static tab => tab.Title)];
        return named.Length == 1 ? named[0] : null;
    }

    // The punctuation that ends a clause (as SaidVerbs reads it).
    private static readonly Regex ClauseEnds = new(@"[,;:.?!¿¡\r\n]+", RegexOptions.CultureInvariant);

    // A clause of this turn's words ends in one of the brake's names, its words together and in order («enciende la
    // búsqueda web», «activa otra vez la búsqueda web, por favor»), and nothing else was called before in the turn.
    private bool AskedNow(string[] names)
    {
        if (_calledTurn == _turns)
        {
            return false;
        }

        string[][] clauses = [.. ClauseEnds.Split(_latest).Select(Words).Where(static clause => clause.Length > 0)];
        return names.Select(static name => Words(Folded(name))).Any(name =>
            name.Length > 0 && clauses.Any(clause => clause.Length >= name.Length && clause.AsSpan(clause.Length - name.Length).SequenceEqual(name)));
    }

    private static string[] Words(string text) =>
        [.. Regex.Split(text, @"[^\p{L}\p{Nd}]+").Where(static word => word.Length > 0)];

    // Every word of the name is one the person said in this session («doom eternal» in «pon Doom Eternal»).
    private bool Said(string name)
    {
        string[] words = [.. Regex.Split(Folded(name), @"[^\p{L}\p{Nd}]+").Where(word => word.Length > 0)];
        return words.Length > 0 && words.All(_words.Contains);
    }

    // An address's host; a ping names its host bare, and one written as an IPv6 («2001:db8::7») reads as no address.
    private static string HostOf(string address) =>
        address.Contains(':', StringComparison.Ordinal) && IPAddress.TryParse(address.Trim().Trim('[', ']'), out IPAddress? ip)
            ? ip.ToString()
            : UriOf(address) is { } uri ? Normalized(uri.Host) : string.Empty;

    private static Uri? UriOf(string address)
    {
        string given = address.Trim();
        return Uri.TryCreate(given, UriKind.Absolute, out Uri? uri) && uri.Host.Length > 0 ? uri
            : Uri.TryCreate("http://" + given, UriKind.Absolute, out uri) ? uri
            : null;
    }

    private static string Normalized(string host)
    {
        string name = host.Trim().TrimEnd('.').ToLowerInvariant();
        return name.StartsWith("www.", StringComparison.Ordinal) ? name[4..] : name;
    }

    // Lower case without accents: «Viña» is «vina» (also how a conversation is found by its title, FieldProductChannel).
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
