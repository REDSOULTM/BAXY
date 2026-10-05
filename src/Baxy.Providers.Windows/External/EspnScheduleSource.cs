using System.Globalization;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

// M168 (D77, dueño 2026-10-05; DEV-G v4y G-w42-t1 «when do the Lakers play next?», DEV-H H-w44-t1 «what time does the
// arsenal match kick off tonight», DEV-I I-w12-t3 «y cuando jeuga de nuevo», I-w26-t1 «a que hora juega chile el
// martes» → «no encontré»/«no pude buscarlo»): Wikipedia no sabe cuándo juega un equipo, y sin esa hora fallaba también
// el aviso «una hora antes» que la sigue. Contesta la API pública de ESPN (site.api.espn.com), sin clave ni cuenta: no es
// una API oficial documentada, se usa para uso personal no comercial (D32) y, si no responde o no cubre al equipo, la
// búsqueda sigue como antes (noticias, enciclopedia, motor general) y BAXY dice que no lo encontró.
//
// Dos peticiones por pregunta y nada más: la búsqueda de ESPN resuelve el nombre que dijo la persona al equipo (una
// petición en vez de recorrer las listas de equipos de cada liga) y su calendario da el partido. Sale sólo el nombre del
// equipo; el User-Agent es el de BAXY con la URL del repositorio; cada respuesta se guarda poco tiempo (el equipo medio
// día, el calendario diez minutos) y cada petición espera como mucho unos segundos.
internal sealed class EspnScheduleSource
{
    internal const string Authority = "espn_public_schedule";
    private const string SearchEndpoint = "https://site.api.espn.com/apis/search/v2";
    private const string SiteEndpoint = "https://site.api.espn.com/apis/site/v2/sports/";
    private static readonly TimeSpan RequestTimeout = TimeSpan.FromSeconds(6);
    private static readonly TimeSpan TeamCacheLife = TimeSpan.FromHours(12);
    private static readonly TimeSpan ScheduleCacheLife = TimeSpan.FromMinutes(10);
    private const int CacheEntries = 64;
    private const int MaximumBytes = 2_000_000;

    private readonly HttpClient _http;
    private readonly Func<DateTimeOffset> _now;
    private readonly TimeZoneInfo _zone;
    private readonly Dictionary<string, (DateTimeOffset At, string Body)> _cache = new(StringComparer.Ordinal);
    private readonly Lock _cacheLock = new();

    internal EspnScheduleSource(HttpClient http, Func<DateTimeOffset>? now = null, TimeZoneInfo? zone = null)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
        _now = now ?? (static () => DateTimeOffset.UtcNow);
        _zone = zone ?? TimeZoneInfo.Local;
    }

    internal enum Wanted
    {
        Next,
        Last,
    }

    internal enum SportHint
    {
        Any,
        Soccer,
        Basketball,
    }

    // «Team»: the name as the person said it (folded words, an alias already turned into the name ESPN knows); «Rival»:
    // the one named after «contra», «vs», «against» (to pick that match among the next ones), or null.
    internal sealed record MatchAsk(string Team, string? Rival, Wanted Wants, SportHint Sport);

    internal readonly record struct TeamHit(string Id, string Name, string Sport, string League);

    // --- What the person asked -------------------------------------------------------------------------------------

    // The verb or noun of a match.
    private static readonly HashSet<string> PlayWords = new(StringComparer.Ordinal)
    {
        "juega", "juegan", "jugara", "jugaran", "juegue", "jueguen", "jugamos", "play", "plays", "playing",
        "partido", "partidos", "match", "game", "kick", "kickoff", "tip", "tipoff",
    };

    // What asks for the next match: when, at what time, against whom, tonight.
    private static readonly HashSet<string> NextWords = new(StringComparer.Ordinal)
    {
        "cuando", "hora", "when", "time", "next", "proximo", "proxima", "siguiente", "tonight", "hoy", "manana",
        "tomorrow", "contra", "against", "who", "quien", "kick", "kickoff", "tip", "tipoff", "ahora", "now",
        "empieza", "comienza", "start", "starts", "upcoming", "weekend", "finde",
    };

    // What asks for the result of the last one.
    private static readonly HashSet<string> ResultWords = new(StringComparer.Ordinal)
    {
        "gano", "ganaron", "gane", "perdio", "perdieron", "empato", "empataron", "salio", "quedo", "quedaron",
        "resultado", "marcador", "won", "win", "beat", "lost", "score", "result",
    };

    // The words that place it in the past.
    private static readonly HashSet<string> PastWords = new(StringComparer.Ordinal)
    {
        "anoche", "ayer", "yesterday", "last", "night", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado",
        "domingo", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "finde", "weekend",
    };

    // The words that ask only for the next one, even beside a result word («who won and when do they play next»).
    private static readonly HashSet<string> OnlyNextWords = new(StringComparer.Ordinal)
    {
        "cuando", "when", "next", "proximo", "proxima", "siguiente", "hora", "time",
    };

    private static readonly HashSet<string> RivalMarkers = new(StringComparer.Ordinal)
    {
        "contra", "vs", "versus", "against", "ante", "frente",
    };

    // A connector inside a name («Universidad de Chile»), kept only between two words of it.
    private static readonly HashSet<string> NameConnectors = new(StringComparer.Ordinal) { "de", "del" };

    // Everything of the question that is not the team's name.
    private static readonly HashSet<string> FrameWords = new(StringComparer.Ordinal)
    {
        // Spanish
        "a", "al", "el", "la", "los", "las", "lo", "de", "del", "d", "en", "y", "e", "o", "u", "que", "q", "aq", "k",
        "con", "por", "para", "pa", "un", "una", "uno", "se", "le", "les", "me", "mi", "mis", "su", "sus", "tu", "te",
        "nos", "este", "esta", "ese", "esa", "eso", "esto", "ahora", "hoy", "manana", "anoche", "ayer", "noche",
        "tarde", "semana", "finde", "fin", "proximo", "proxima", "siguiente", "nuevo", "nueva", "otra", "otro", "vez",
        "cuando", "hora", "horas", "juega", "juegan", "jugara", "jugaran", "juegue", "jueguen", "jugamos", "jugo",
        "jugaron", "partido", "partidos", "contra", "vs", "versus", "ante", "frente", "como", "salio", "salieron",
        "quedo", "quedaron", "gano", "ganaron", "gane", "perdio", "perdieron", "empato", "empataron", "resultado",
        "marcador", "quien", "quienes", "cual", "sabes", "sabe", "sabias", "che", "oye", "oe", "oiga", "hey", "baxy",
        "wey", "guey", "po", "pues", "mira", "dime", "decime", "digame", "porfa", "favor", "sera", "es", "son", "fue",
        "va", "van", "hay", "viene", "empieza", "comienza", "equipo", "mi", "parce", "parcero", "compa", "pana",
        "clasico", "superclasico", "derbi", "local", "visitante", "casa", "lunes", "martes", "miercoles", "jueves",
        "viernes", "sabado", "domingo", "futbol", "liga", "copa", "nba", "basquet", "baloncesto", "donde", "canal",
        // English
        "when", "what", "whats", "time", "does", "do", "did", "is", "are", "was", "were", "the", "an", "at", "on",
        "in", "of", "for", "to", "next", "game", "games", "match", "matches", "play", "plays", "playing", "played",
        "kick", "kickoff", "off", "tip", "tipoff", "tonight", "today", "tomorrow", "yesterday", "last", "night",
        "this", "weekend", "week", "who", "whos", "won", "win", "wins", "beat", "lost", "score", "scores", "result",
        "results", "against", "they", "them", "their", "it", "my", "i", "you", "know", "ok", "okay", "so", "and",
        "up", "start", "starts", "will", "gonna", "going", "how", "go", "went", "again", "upcoming", "s", "team",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "soccer", "basketball",
        "dude", "bro", "mate", "man", "please", "now", "about", "there", "any", "get", "pull",
    };

    // Words that tell the sport.
    private static readonly HashSet<string> SoccerWords = new(StringComparer.Ordinal)
    {
        "match", "kick", "kickoff", "futbol", "soccer", "gol", "goles", "goal", "goals", "liga", "copa", "champions",
        "libertadores", "premier",
    };

    private static readonly HashSet<string> BasketballWords = new(StringComparer.Ordinal)
    {
        "tip", "tipoff", "nba", "basquet", "baloncesto", "basketball",
    };

    // How people call a team or a national side and ESPN does not (folded words → the name ESPN knows). A national side
    // said in Spanish is searched by its English name. «spurs» said of football is Tottenham, not San Antonio.
    private static readonly (string[] Said, string Name, SportHint Sport)[] Aliases =
    [
        (["barca"], "barcelona", SportHint.Any),
        (["barsa"], "barcelona", SportHint.Any),
        (["la", "u"], "universidad de chile", SportHint.Any),
        (["la", "roja"], "chile", SportHint.Any),
        (["la", "albiceleste"], "argentina", SportHint.Any),
        (["la", "celeste"], "uruguay", SportHint.Any),
        (["el", "tri"], "mexico", SportHint.Any),
        (["la", "vinotinto"], "venezuela", SportHint.Any),
        (["la", "seleccion", "chilena"], "chile", SportHint.Any),
        (["la", "seleccion", "argentina"], "argentina", SportHint.Any),
        (["la", "seleccion", "mexicana"], "mexico", SportHint.Any),
        (["la", "seleccion", "colombiana"], "colombia", SportHint.Any),
        (["la", "seleccion", "peruana"], "peru", SportHint.Any),
        (["la", "seleccion", "uruguaya"], "uruguay", SportHint.Any),
        (["la", "seleccion", "espanola"], "spain", SportHint.Any),
        (["el", "cacique"], "colo colo", SportHint.Any),
        (["el", "xeneize"], "boca juniors", SportHint.Any),
        (["el", "millonario"], "river plate", SportHint.Any),
        (["el", "atleti"], "atletico madrid", SportHint.Any),
        (["atleti"], "atletico madrid", SportHint.Any),
        (["juve"], "juventus", SportHint.Any),
        (["man", "u"], "manchester united", SportHint.Any),
        (["man", "utd"], "manchester united", SportHint.Any),
        (["man", "united"], "manchester united", SportHint.Any),
        (["man", "city"], "manchester city", SportHint.Any),
        (["the", "gunners"], "arsenal", SportHint.Any),
        (["spurs"], "tottenham hotspur", SportHint.Soccer),
        (["the", "sixers"], "76ers", SportHint.Any),
        (["sixers"], "76ers", SportHint.Any),
        (["cavs"], "cavaliers", SportHint.Any),
        (["mavs"], "mavericks", SportHint.Any),
        (["the", "dubs"], "warriors", SportHint.Any),
        (["blazers"], "trail blazers", SportHint.Any),
        (["brasil"], "brazil", SportHint.Any),
        (["espana"], "spain", SportHint.Any),
        (["alemania"], "germany", SportHint.Any),
        (["inglaterra"], "england", SportHint.Any),
        (["francia"], "france", SportHint.Any),
        (["italia"], "italy", SportHint.Any),
        (["holanda"], "netherlands", SportHint.Any),
        (["paises", "bajos"], "netherlands", SportHint.Any),
        (["estados", "unidos"], "united states", SportHint.Any),
        (["belgica"], "belgium", SportHint.Any),
        (["marruecos"], "morocco", SportHint.Any),
        (["japon"], "japan", SportHint.Any),
    ];

    // Null when the query does not ask when a named team plays, nor how its last match went.
    internal static MatchAsk? Parse(string query)
    {
        string[] words = WikipediaSearchSource.FoldedWords(query);
        if (words.Length == 0) return null;
        bool play = words.Any(PlayWords.Contains);
        bool next = words.Any(NextWords.Contains);
        bool result = words.Any(ResultWords.Contains);
        bool past = words.Any(PastWords.Contains);
        SportHint sport = words.Any(BasketballWords.Contains) ? SportHint.Basketball
            : words.Any(SoccerWords.Contains) ? SportHint.Soccer
            : SportHint.Any;
        Wanted wants;
        if (result && (play || past) && !words.Any(OnlyNextWords.Contains)) wants = Wanted.Last;
        else if (play && next) wants = Wanted.Next;
        else return null;

        List<string> tokens = Aliased(words, sport);
        var runs = new List<(List<string> Words, bool AfterRival)>();
        List<string>? current = null;
        bool rivalPending = false;
        for (int index = 0; index < tokens.Count; index++)
        {
            string token = tokens[index];
            bool connector = NameConnectors.Contains(token) && current is { Count: > 0 }
                && index + 1 < tokens.Count && IsNameWord(tokens[index + 1]);
            if (IsNameWord(token) || connector)
            {
                if (current is null)
                {
                    current = [];
                    runs.Add((current, rivalPending));
                    rivalPending = false;
                }
                current.Add(token);
                continue;
            }
            current = null;
            if (RivalMarkers.Contains(token)) rivalPending = true;
        }
        if (runs.Count == 0) return null;
        string team = string.Join(' ', runs[0].Words);
        string? rival = runs.Skip(1).Where(static run => run.AfterRival).Select(static run => string.Join(' ', run.Words))
            .FirstOrDefault();
        // «América contra Chivas» names the team first; «contra Chivas, el América» is rare enough to read as said.
        return new MatchAsk(team, rival, wants, sport);
    }

    // A year («this year» reaches the search as 2026, SearchQueryYear) or any number is no name.
    private static bool IsNameWord(string token) =>
        token.Contains(' ', StringComparison.Ordinal)
        || !FrameWords.Contains(token) && token.Length > 1 && !token.All(char.IsAsciiDigit);

    // The words with each alias turned into one token carrying the name ESPN knows (kept whole, so its «de» is no
    // frame word).
    private static List<string> Aliased(string[] words, SportHint sport)
    {
        var tokens = new List<string>(words.Length);
        for (int index = 0; index < words.Length;)
        {
            (string[] Said, string Name, SportHint Sport)? alias = Aliases
                .Where(candidate => (candidate.Sport == SportHint.Any || candidate.Sport == sport)
                    && index + candidate.Said.Length <= words.Length
                    && candidate.Said.AsSpan().SequenceEqual(words.AsSpan(index, candidate.Said.Length)))
                .Cast<(string[] Said, string Name, SportHint Sport)?>()
                .FirstOrDefault();
            if (alias is { } found)
            {
                tokens.Add(found.Name);
                index += found.Said.Length;
                continue;
            }
            tokens.Add(words[index]);
            index++;
        }
        return tokens;
    }

    // --- Which team that is ----------------------------------------------------------------------------------------

    // The football leagues read (and the national sides); a team whose home league is another is not answered here.
    private static readonly HashSet<string> SoccerLeagues = new(StringComparer.Ordinal)
    {
        "eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "arg.1", "chi.1", "mex.1", "usa.1", "bra.1", "col.1", "uru.1",
        "per.1", "por.1", "ned.1", "uefa.champions", "uefa.europa", "conmebol.libertadores", "conmebol.sudamericana",
    };

    private static readonly string[] YouthOrWomen = ["women", "u17", "u19", "u20", "u21", "u23"];

    internal static Uri SearchUri(string team) =>
        new(SearchEndpoint + "?query=" + Uri.EscapeDataString(team) + "&limit=8&type=team");

    // The first team ESPN ranks for the name, of a league read here, whose name carries every word said (a word of
    // five letters or more may be the start of one: «nugget»); null when none.
    internal static TeamHit? PickTeam(string body, MatchAsk ask)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        if (!document.RootElement.TryGetProperty("results", out JsonElement results)
            || results.ValueKind != JsonValueKind.Array)
        {
            return null;
        }
        string[] said = WikipediaSearchSource.FoldedWords(ask.Team);
        foreach (JsonElement group in results.EnumerateArray())
        {
            if (Text(group, "type") != "team" || !group.TryGetProperty("contents", out JsonElement contents)
                || contents.ValueKind != JsonValueKind.Array)
            {
                continue;
            }
            foreach (JsonElement content in contents.EnumerateArray())
            {
                string name = Text(content, "displayName");
                string sport = Text(content, "sport");
                string league = Text(content, "defaultLeagueSlug");
                string uid = Text(content, "uid");
                int teamAt = uid.LastIndexOf("t:", StringComparison.Ordinal);
                string id = teamAt >= 0 ? uid[(teamAt + 2)..] : string.Empty;
                if (name.Length == 0 || id.Length == 0 || !id.All(char.IsAsciiDigit)) continue;
                bool read = sport switch
                {
                    "basketball" => league == "nba" && ask.Sport != SportHint.Soccer,
                    "soccer" => ask.Sport != SportHint.Basketball && IsReadSoccer(league, name, Text(content, "subtitle")),
                    _ => false,
                };
                if (!read || !NameCarries(name, said)) continue;
                return new TeamHit(id, name, sport, league);
            }
        }
        return null;
    }

    private static bool IsReadSoccer(string league, string name, string subtitle)
    {
        string described = (name + " " + subtitle).ToLowerInvariant();
        if (YouthOrWomen.Any(described.Contains) || league.Contains(".w.", StringComparison.Ordinal)
            || league.EndsWith(".w", StringComparison.Ordinal))
        {
            return false;
        }
        return SoccerLeagues.Contains(league)
            || league.StartsWith("fifa.", StringComparison.Ordinal)
            || league is "uefa.nations" or "uefa.euro" or "conmebol.america"
            || league.StartsWith("concacaf.nations", StringComparison.Ordinal);
    }

    internal static bool NameCarries(string name, string[] said)
    {
        string[] words = WikipediaSearchSource.FoldedWords(name);
        return said.Length > 0 && said.All(asked => words.Any(word =>
            word == asked || asked.Length >= 5 && word.Length > asked.Length && word.StartsWith(asked, StringComparison.Ordinal)
            || word.Length >= 5 && asked.Length > word.Length && asked.StartsWith(word, StringComparison.Ordinal)));
    }

    // The team's calendar: football across every competition it plays (its fixtures, or its results), basketball the
    // NBA season in course (and the regular season, when the one in course has nothing left).
    internal static Uri[] ScheduleUris(TeamHit team, Wanted wants) => team.Sport == "basketball"
        ? [new(SiteEndpoint + "basketball/nba/teams/" + team.Id + "/schedule"),
           new(SiteEndpoint + "basketball/nba/teams/" + team.Id + "/schedule?seasontype=2")]
        : wants == Wanted.Next
            ? [new(SiteEndpoint + "soccer/all/teams/" + team.Id + "/schedule?fixture=true")]
            : [new(SiteEndpoint + "soccer/all/teams/" + team.Id + "/schedule")];

    // --- The match -------------------------------------------------------------------------------------------------

    internal async Task<List<(string Title, string Url, string Snippet)>?> ReadAsync(
        MatchAsk ask,
        CancellationToken cancellationToken)
    {
        string? found = await GetAsync(SearchUri(ask.Team), TeamCacheLife, cancellationToken).ConfigureAwait(false);
        if (found is null) return null;
        TeamHit? team;
        try
        {
            team = PickTeam(found, ask);
        }
        catch (JsonException)
        {
            return null;
        }
        if (team is not { } hit) return null;
        foreach (Uri uri in ScheduleUris(hit, ask.Wants))
        {
            string? body = await GetAsync(uri, ScheduleCacheLife, cancellationToken).ConfigureAwait(false);
            if (body is null) return null;
            try
            {
                if (Answer(body, hit, ask, _now(), _zone, uri) is { } answer) return answer;
            }
            catch (JsonException)
            {
                return null;
            }
        }
        return null;
    }

    private async Task<string?> GetAsync(Uri uri, TimeSpan life, CancellationToken cancellationToken)
    {
        string key = uri.AbsoluteUri;
        DateTimeOffset now = DateTimeOffset.UtcNow;
        lock (_cacheLock)
        {
            if (_cache.TryGetValue(key, out (DateTimeOffset At, string Body) kept) && now - kept.At < life)
                return kept.Body;
        }
        using var request = new HttpRequestMessage(HttpMethod.Get, uri);
        request.Headers.TryAddWithoutValidation("User-Agent", WikipediaSearchSource.UserAgent);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(RequestTimeout);
        try
        {
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, timeout.Token)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode) return null;
            string body = await WebBrowserAdapter.ReadBoundedTextAsync(response, MaximumBytes, timeout.Token)
                .ConfigureAwait(false);
            lock (_cacheLock)
            {
                if (_cache.Count >= CacheEntries) _cache.Clear();
                _cache[key] = (now, body);
            }
            return body;
        }
        catch (HttpRequestException)
        {
            return null;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
    }

    private readonly record struct Fixture(
        DateTimeOffset Start,
        bool TimeKnown,
        string State,
        bool Completed,
        string Detail,
        string Opponent,
        bool Home,
        string OwnScore,
        string OpponentScore,
        string Competition,
        string Venue,
        string Link);

    // The receipt's one result: the next match (or the one being played), or the last one played, with its moment in
    // this PC's time zone. Null when the calendar has none of what was asked: nothing is invented.
    internal static List<(string Title, string Url, string Snippet)>? Answer(
        string body,
        TeamHit team,
        MatchAsk ask,
        DateTimeOffset now,
        TimeZoneInfo zone,
        Uri uri)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        if (!document.RootElement.TryGetProperty("events", out JsonElement events)
            || events.ValueKind != JsonValueKind.Array)
        {
            return null;
        }
        var fixtures = new List<Fixture>();
        foreach (JsonElement item in events.EnumerateArray())
        {
            if (Read(item, team) is { } fixture) fixtures.Add(fixture);
        }
        fixtures.Sort(static (left, right) => left.Start.CompareTo(right.Start));
        string[] rival = ask.Rival is null ? [] : WikipediaSearchSource.FoldedWords(ask.Rival);
        bool AgainstRival(Fixture fixture) => rival.Length > 0 && NameCarries(fixture.Opponent, rival);
        Fixture? chosen;
        if (ask.Wants == Wanted.Next)
        {
            List<Fixture> coming = fixtures
                .Where(fixture => fixture.State == "in" || fixture.State == "pre" && fixture.Start >= now.AddHours(-3))
                .ToList();
            chosen = coming.Where(AgainstRival).Cast<Fixture?>().FirstOrDefault()
                ?? coming.Cast<Fixture?>().FirstOrDefault();
        }
        else
        {
            List<Fixture> played = fixtures.Where(fixture => fixture.Completed && fixture.Start <= now).ToList();
            chosen = played.Where(AgainstRival).Cast<Fixture?>().LastOrDefault()
                ?? played.Cast<Fixture?>().LastOrDefault();
        }
        if (chosen is not { } match) return null;
        string noun = team.Sport == "basketball" ? "game" : "match";
        string title = team.Name + " vs " + match.Opponent;
        string where = match.Home ? "at home against " : "away against ";
        string moment = Moment(match, zone);
        string tail = (match.Competition.Length > 0 ? ", " + match.Competition : string.Empty)
            + (match.Venue.Length > 0 ? ", at " + match.Venue : string.Empty) + ".";
        string snippet;
        if (match.State == "in")
        {
            snippet = "Playing now: " + team.Name + " " + match.OwnScore + ", " + match.Opponent + " "
                + match.OpponentScore + (match.Detail.Length > 0 ? " (" + match.Detail + ")" : string.Empty)
                + ", started " + moment + tail;
        }
        else if (ask.Wants == Wanted.Next)
        {
            snippet = "Next " + noun + ": " + team.Name + " play " + where + match.Opponent + " " + moment + tail;
        }
        else
        {
            string verdict = Verdict(match.OwnScore, match.OpponentScore);
            string opponent = verdict switch
            {
                "beat" => " " + match.Opponent,
                "lost to" => " " + match.Opponent,
                _ => " with " + match.Opponent,
            };
            snippet = "Last " + noun + ": " + team.Name + " " + verdict + opponent + " " + match.OwnScore + "-"
                + match.OpponentScore + (match.Home ? " at home" : " away") + ", " + moment + tail;
        }
        return [(title, match.Link.Length > 0 ? match.Link : uri.AbsoluteUri, snippet)];
    }

    // «on Friday 2026-10-09 at 19:30 local time (UTC-03:00)»; without a confirmed time, only the day, said so (in words
    // that a report repeats without reading as a failure: «aún no se ha anunciado», not «no está confirmada»).
    private static string Moment(Fixture match, TimeZoneInfo zone)
    {
        DateTimeOffset local = TimeZoneInfo.ConvertTime(match.Start, zone);
        string day = "on " + local.ToString("dddd yyyy-MM-dd", CultureInfo.InvariantCulture);
        if (!match.TimeKnown)
            return day + " (the start time is still to be announced, TBD)";
        TimeSpan offset = local.Offset;
        string sign = offset < TimeSpan.Zero ? "-" : "+";
        return day + " at " + local.ToString("HH:mm", CultureInfo.InvariantCulture) + " local time (UTC" + sign
            + offset.Duration().ToString(@"hh\:mm", CultureInfo.InvariantCulture) + ")";
    }

    private static string Verdict(string own, string opponent)
    {
        if (!decimal.TryParse(own, NumberStyles.Number, CultureInfo.InvariantCulture, out decimal mine)
            || !decimal.TryParse(opponent, NumberStyles.Number, CultureInfo.InvariantCulture, out decimal theirs))
        {
            return "played";
        }
        return mine > theirs ? "beat" : mine < theirs ? "lost to" : "drew";
    }

    private static Fixture? Read(JsonElement item, TeamHit team)
    {
        if (item.ValueKind != JsonValueKind.Object
            || !item.TryGetProperty("competitions", out JsonElement competitions)
            || competitions.ValueKind != JsonValueKind.Array || competitions.GetArrayLength() == 0)
        {
            return null;
        }
        JsonElement competition = competitions[0];
        string date = Text(competition, "date") is { Length: > 0 } own ? own : Text(item, "date");
        if (!DateTimeOffset.TryParseExact(date, ["yyyy-MM-dd'T'HH:mm'Z'", "yyyy-MM-dd'T'HH:mm:ss'Z'"],
                CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out DateTimeOffset start))
        {
            return null;
        }
        bool timeKnown = !(competition.TryGetProperty("timeValid", out JsonElement valid) && valid.ValueKind == JsonValueKind.False)
            && !(item.TryGetProperty("timeValid", out JsonElement eventValid) && eventValid.ValueKind == JsonValueKind.False);
        string state = string.Empty;
        bool completed = false;
        string detail = string.Empty;
        if (competition.TryGetProperty("status", out JsonElement status)
            && status.TryGetProperty("type", out JsonElement type) && type.ValueKind == JsonValueKind.Object)
        {
            state = Text(type, "state");
            completed = type.TryGetProperty("completed", out JsonElement done) && done.ValueKind == JsonValueKind.True;
            detail = Text(type, "shortDetail");
        }
        if (!competition.TryGetProperty("competitors", out JsonElement competitors)
            || competitors.ValueKind != JsonValueKind.Array)
        {
            return null;
        }
        string opponent = string.Empty, ownScore = string.Empty, opponentScore = string.Empty;
        bool home = false, found = false;
        foreach (JsonElement competitor in competitors.EnumerateArray())
        {
            string id = competitor.TryGetProperty("team", out JsonElement side) ? Text(side, "id") : string.Empty;
            string name = Text(side, "displayName");
            string score = Score(competitor);
            if (id == team.Id)
            {
                found = true;
                home = Text(competitor, "homeAway") == "home";
                ownScore = score;
            }
            else
            {
                opponent = name;
                opponentScore = score;
            }
        }
        if (!found || opponent.Length == 0) return null;
        string league = item.TryGetProperty("league", out JsonElement leagueElement) ? Text(leagueElement, "name") : string.Empty;
        string season = item.TryGetProperty("seasonType", out JsonElement seasonType) ? Text(seasonType, "name") : string.Empty;
        string competitionName = team.Sport == "basketball"
            ? "NBA" + (season.Length > 0 && season != "Regular Season" ? " " + season : string.Empty)
            : league;
        string venue = competition.TryGetProperty("venue", out JsonElement venueElement) ? Text(venueElement, "fullName") : string.Empty;
        string link = string.Empty;
        if (item.TryGetProperty("links", out JsonElement links) && links.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement candidate in links.EnumerateArray())
            {
                string href = Text(candidate, "href");
                if (href.StartsWith("https://www.espn.com/", StringComparison.Ordinal))
                {
                    link = href;
                    break;
                }
            }
        }
        return new Fixture(start, timeKnown, state, completed, detail, opponent, home, ownScore, opponentScore,
            competitionName, venue, link);
    }

    // The schedule writes a score as an object («displayValue») and the scoreboard as a string.
    private static string Score(JsonElement competitor)
    {
        if (!competitor.TryGetProperty("score", out JsonElement score)) return string.Empty;
        return score.ValueKind switch
        {
            JsonValueKind.String => score.GetString() ?? string.Empty,
            JsonValueKind.Object => Text(score, "displayValue"),
            _ => string.Empty,
        };
    }

    private static string Text(JsonElement element, string name) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(name, out JsonElement value)
            && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;
}
