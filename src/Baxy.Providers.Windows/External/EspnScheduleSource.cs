using System.Globalization;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

// M168 (D77, dueño 2026-10-05): Wikipedia no sabe cuándo juega un equipo. web.search con source=sports pregunta a la
// API pública de ESPN (site.api.espn.com), sin clave ni cuenta: no es una API oficial documentada, se usa para uso
// personal no comercial (D32). El equipo y si se pide el próximo partido o el último los escribe el modelo (team,
// wants); si ESPN no responde, el recibo dice que no se pudo buscar, y si no conoce al equipo, que no hubo resultados.
//
// Dos peticiones por pregunta y nada más: la búsqueda de ESPN resuelve el nombre al equipo (una petición en vez de
// recorrer las listas de equipos de cada liga) y su calendario da el partido. Sale sólo el nombre del equipo; el
// User-Agent es el de BAXY con la URL del repositorio; cada respuesta se guarda poco tiempo (el equipo medio día, el
// calendario diez minutos) y cada petición espera como mucho unos segundos.
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

    // What the model asked (web.search source=sports): the team as it wrote it, and whether the next match or the last
    // one played.
    internal sealed record MatchAsk(string Team, Wanted Wants);

    internal readonly record struct TeamHit(string Id, string Name, string Sport, string League);

    // --- Which team that is ----------------------------------------------------------------------------------------

    // The football leagues read (and the national sides); a team whose home league is another is not answered here.
    private static readonly HashSet<string> SoccerLeagues = new(StringComparer.Ordinal)
    {
        "eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "arg.1", "chi.1", "mex.1", "usa.1", "bra.1", "col.1", "uru.1",
        "per.1", "por.1", "ned.1", "uefa.champions", "uefa.europa", "conmebol.libertadores", "conmebol.sudamericana",
    };

    internal static Uri SearchUri(string team) =>
        new(SearchEndpoint + "?query=" + Uri.EscapeDataString(team) + "&limit=8&type=team");

    // The first team ESPN ranks for the name whose calendar this source reads (an NBA team, or a football team of a
    // league above, or a national side), as ESPN names it; null when ESPN lists none of those. The receipt says which
    // team it was, so a team ESPN ranked first that is not the one meant is seen as such.
    internal static TeamHit? PickTeam(string body)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        if (!document.RootElement.TryGetProperty("results", out JsonElement results)
            || results.ValueKind != JsonValueKind.Array)
        {
            return null;
        }
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
                    "basketball" => league == "nba",
                    "soccer" => IsReadSoccer(league),
                    _ => false,
                };
                if (read) return new TeamHit(id, name, sport, league);
            }
        }
        return null;
    }

    // ESPN's league codes: a women's league is coded «.w.» or «.w».
    private static bool IsReadSoccer(string league) =>
        !league.Contains(".w.", StringComparison.Ordinal)
        && !league.EndsWith(".w", StringComparison.Ordinal)
        && (SoccerLeagues.Contains(league)
            || league.StartsWith("fifa.", StringComparison.Ordinal)
            || league is "uefa.nations" or "uefa.euro" or "conmebol.america"
            || league.StartsWith("concacaf.nations", StringComparison.Ordinal));

    // The team's calendar: football across every competition it plays (its fixtures, or its results), basketball the
    // NBA season in course (and the regular season, when the one in course has nothing left).
    internal static Uri[] ScheduleUris(TeamHit team, Wanted wants) => team.Sport == "basketball"
        ? [new(SiteEndpoint + "basketball/nba/teams/" + team.Id + "/schedule"),
           new(SiteEndpoint + "basketball/nba/teams/" + team.Id + "/schedule?seasontype=2")]
        : wants == Wanted.Next
            ? [new(SiteEndpoint + "soccer/all/teams/" + team.Id + "/schedule?fixture=true")]
            : [new(SiteEndpoint + "soccer/all/teams/" + team.Id + "/schedule")];

    // --- The match -------------------------------------------------------------------------------------------------

    // One match as ESPN's calendar gives it, its start in this PC's time zone.
    internal readonly record struct Match(
        string Team,
        string Opponent,
        bool Home,
        DateTimeOffset Start,
        bool StartTimeAnnounced,
        string State,
        bool Completed,
        string StatusDetail,
        string TeamScore,
        string OpponentScore,
        string Competition,
        string Venue,
        string Url);

    // Null when ESPN did not answer (network, status, a body that is not its JSON); empty when it answered and has no
    // team of the name whose calendar is read here, or no match of what was asked.
    internal async Task<List<Match>?> ReadAsync(
        MatchAsk ask,
        CancellationToken cancellationToken)
    {
        string? found = await GetAsync(SearchUri(ask.Team), TeamCacheLife, cancellationToken).ConfigureAwait(false);
        if (found is null) return null;
        TeamHit? team;
        try
        {
            team = PickTeam(found);
        }
        catch (JsonException)
        {
            return null;
        }
        if (team is not { } hit) return [];
        foreach (Uri uri in ScheduleUris(hit, ask.Wants))
        {
            string? body = await GetAsync(uri, ScheduleCacheLife, cancellationToken).ConfigureAwait(false);
            if (body is null) return null;
            try
            {
                if (Answer(body, hit, ask.Wants, _now(), _zone, uri) is { } answer) return [answer];
            }
            catch (JsonException)
            {
                return null;
            }
        }
        return [];
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

    // The next match (or the one being played), or the last one played, as the calendar gives it, its start in this
    // PC's time zone. Null when the calendar has none of what was asked: nothing is invented.
    internal static Match? Answer(
        string body,
        TeamHit team,
        Wanted wants,
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
        Fixture? chosen = wants == Wanted.Next
            ? fixtures
                .Where(fixture => fixture.State == "in" || fixture.State == "pre" && fixture.Start >= now.AddHours(-3))
                .Cast<Fixture?>()
                .FirstOrDefault()
            : fixtures
                .Where(fixture => fixture.Completed && fixture.Start <= now)
                .Cast<Fixture?>()
                .LastOrDefault();
        if (chosen is not { } match) return null;
        return new Match(
            team.Name,
            match.Opponent,
            match.Home,
            TimeZoneInfo.ConvertTime(match.Start, zone),
            match.TimeKnown,
            match.State,
            match.Completed,
            match.Detail,
            match.OwnScore,
            match.OpponentScore,
            match.Competition,
            match.Venue,
            match.Link.Length > 0 ? match.Link : uri.AbsoluteUri);
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
