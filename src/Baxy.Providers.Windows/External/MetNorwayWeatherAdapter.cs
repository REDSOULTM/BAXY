using System.Diagnostics;
using System.Globalization;
using System.Net;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo W): la encuesta pide el
/// clima, no páginas sobre el clima. Esta lectura pregunta a un servicio público
/// sin clave: el lugar nombrado se busca en los lugares de GeoNames que BAXY lleva
/// dentro; sin lugar, la ubicación de este PC se toma de su dirección pública. El
/// recibo trae sólo lo que el servicio devolvió, con las unidades que declaró;
/// nada se inventa ni se redondea de más.
/// <para>
/// WEB1 (2026-11-07, LIC1 R3): BAXY se vende, y el plan gratuito de Open-Meteo es «only ... for non-commercial
/// purposes» (https://open-meteo.com/en/terms). El pronóstico y el sol son ahora de MET Norway (api.met.no), cuyos datos
/// son NLOD 2.0 y CC BY 4.0, con crédito a MET Norway (https://api.met.no/doc/License); sus términos
/// (https://api.met.no/doc/TermsOfService, revisión 2026-11-05) piden un User-Agent que identifique la aplicación con un
/// contacto, coordenadas de 4 decimales como mucho, no repetir una petición antes de su «Expires» y usar
/// If-Modified-Since, y limitar el tráfico en cuanto contestan 429: aquí se hace todo eso. La calidad del aire no tiene
/// servicio gratuito de uso comercial: no va, y «unavailable» dice por qué (WEB3).
/// </para>
/// <para>
/// WEB3 (2026-11-07): el tope de 20 peticiones/s es «per application (total, not per client)», la suma de todas las
/// instalaciones, no por IP; cada instalación pide poco y, por eso, cumple sin proxy mientras la suma quede lejos. Para
/// eso: el pronóstico de un lugar no se repite antes de 3 horas (lo que pide Locationforecast fuera de la zona nórdica),
/// el sol de un día se pide una vez (no cambia), y lo guardado vive en la carpeta de datos de BAXY, de modo que un
/// reinicio no vuelve a preguntar. Quién se identifica y con qué contacto: <see cref="ProductIdentity"/>.
/// </para>
/// </summary>
internal sealed class MetNorwayWeatherAdapter : IExternalOperationAdapter, IDisposable
{
    private const string ForecastAuthority = "https://api.met.no/weatherapi/locationforecast/2.0/complete";
    private const string SunAuthority = "https://api.met.no/weatherapi/sunrise/3.0/sun";
    // Uso real tanda 6 «El pronóstico del tiempo para la semana»: hoy y los seis días que siguen.
    private const int ForecastDays = 7;
    private const int KeptAnswers = 64;
    // WEB3: Locationforecast «Identical requests should not be repeated more often than every 30 mins for the Nordic
    // region, or every 3rd hour for the rest of the world» (https://api.met.no/weatherapi/locationforecast/2.0/documentation,
    // read 2026-11-07), and its Expires may be sooner (Santiago, that day: 30 minutes). The longer wait is kept
    // everywhere: outside the Nordic area the forecast changes every 6 hours, so nothing newer is lost.
    private static readonly TimeSpan ForecastRepeat = TimeSpan.FromHours(3);

    private readonly HttpClient _http;
    private readonly Func<GeoNamesGazetteer> _places;
    private readonly Func<DateTimeOffset> _now;
    private readonly PublicPlaceLocator _locator;
    private readonly Dictionary<string, KeptAnswer> _kept = new(StringComparer.Ordinal);
    private readonly Lock _keptLock = new();
    // WEB3: what was kept, in BAXY's data folder, so a restart does not ask again what may not be asked yet; null keeps
    // it in memory only.
    private readonly string? _keptFile;
    private bool _keptLoaded;
    // After a 429, nothing is asked until the service's Retry-After (a minute when it says none) has passed.
    private DateTimeOffset _quietUntil = DateTimeOffset.MinValue;
    private static readonly TimeSpan QuietWithoutRetryAfter = TimeSpan.FromMinutes(1);

    internal MetNorwayWeatherAdapter(string dataRoot)
        : this(SearchPageReader.StrangerHandler(), static () => GeoNamesGazetteer.Shared, static () => DateTimeOffset.UtcNow,
            Path.Combine(dataRoot, "met-norway-answers.v1.json"))
    {
    }

    // Las pruebas contestan desde su propio manejador, con sus lugares y su reloj.
    internal MetNorwayWeatherAdapter(
        HttpMessageHandler handler, Func<GeoNamesGazetteer> places, Func<DateTimeOffset> now, string? keptFile = null)
    {
        _keptFile = keptFile;
        _http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(12) };
        // MET Norway: «application/domain name, optionally version number», and a link where it finds a contact.
        _http.DefaultRequestHeaders.UserAgent.ParseAdd(ProductIdentity.UserAgent);
        _places = places;
        _now = now;
        _locator = new PublicPlaceLocator((url, cancellationToken) =>
            TransientHttp.GetStringAsync(_http.GetStringAsync, url, cancellationToken));
    }

    public bool CanHandle(string operation) => operation is "weather.current";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string? location = null;
        if (arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("location", out JsonElement named)
            && named.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(named.GetString()))
        {
            location = named.GetString()!.Trim();
        }
        string? dialectCountry = arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("dialectCountry", out JsonElement marked)
            && marked.ValueKind == JsonValueKind.String
            ? marked.GetString()
            : null;

        try
        {
            var namesakes = new Namesakes(dialectCountry);
            // Ronda 22: where the time of a weather read goes (the place, the forecast) travels in elapsedMs.
            var clock = Stopwatch.StartNew();
            PublicPlace located;
            if (location is null)
            {
                PublicPlaceLocator.Lookup here = await _locator.LocateAsync(cancellationToken).ConfigureAwait(false);
                if (here.Unreachable) return ExternalJson.FailureBeforeEffect(operation, "weather_service_unavailable");
                if (here.Place is not { } found)
                    return ExternalJson.FailureBeforeEffect(operation, "weather_location_unavailable");
                located = found;
            }
            else
            {
                PlaceChoice choice = Geocode(location, namesakes);
                if (choice.Place is not { } found)
                    return PlaceCandidates(operation, location, choice);
                located = found;
            }
            long placeMs = clock.ElapsedMilliseconds;

            // Here is this PC, whose own clock keeps its zone when the place service names none; a named place without
            // one (a country of several zones) is read in UTC, and the receipt says so.
            TimeZoneInfo zone = Zone(located.TimeZone) ?? (location is null ? TimeZoneInfo.Local : TimeZoneInfo.Utc);
            // MET Norway: «truncate all coordinates to max 4 decimals».
            string coordinates = "lat=" + located.Latitude.ToString("F4", CultureInfo.InvariantCulture)
                + "&lon=" + located.Longitude.ToString("F4", CultureInfo.InvariantCulture);
            DateTimeOffset now = _now();
            DateOnly today = DateOnly.FromDateTime(TimeZoneInfo.ConvertTime(now, zone).DateTime);
            Task<string> forecastRead = ReadAsync(
                ForecastAuthority + "?" + coordinates, now + ForecastRepeat, cancellationToken);
            Task<SunTimes> todaySun = ReadSunAsync(coordinates, today, zone, cancellationToken);
            Task<SunTimes> tomorrowSun = ReadSunAsync(coordinates, today.AddDays(1), zone, cancellationToken);
            string forecastJson = await forecastRead.ConfigureAwait(false);
            long forecastMs = clock.ElapsedMilliseconds - placeMs;
            SunTimes sunToday = await todaySun.ConfigureAwait(false);
            SunTimes sunTomorrow = await tomorrowSun.ConfigureAwait(false);
            long totalMs = clock.ElapsedMilliseconds;

            using JsonDocument forecast = JsonDocument.Parse(forecastJson);
            List<Step> steps = Steps(forecast.RootElement, zone);
            if (steps.Count == 0)
                return ExternalJson.FailureBeforeEffect(operation, "weather_service_unavailable");
            // The step in course: the last one already begun (the service's first step is the hour in course).
            Step current = steps.LastOrDefault(step => step.At <= now) ?? steps[0];
            int weatherCode = WmoCode(current.Symbol);
            List<Day> days = [.. Enumerable.Range(0, ForecastDays).Select(offset => DayOf(steps, today.AddDays(offset)))];

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("location", located.Name);
                if (located.Region is { Length: > 0 } region)
                    writer.WriteString("region", region);
                writer.WriteString("country", located.Country);
                // Ronda 19: other towns of this name and comparable size exist in other countries; the reply names
                // the country read, so the person can tell it was not the one meant.
                if (namesakes.Elsewhere)
                    writer.WriteBoolean("namesakesElsewhere", true);
                writer.WriteString("locatedBy", located.Source);
                writer.WriteString("observedAtLocal", current.Local.ToString("yyyy-MM-dd'T'HH:mm", CultureInfo.InvariantCulture));
                writer.WriteString("timezone", ZoneName(zone));
                WriteNumber(writer, "temperatureC", current.Temperature);
                WriteNumber(writer, "apparentC", current.Apparent);
                WriteNumber(writer, "humidityPercent", current.Humidity);
                // The service gives the wind in m/s; the receipt keeps km/h.
                WriteNumber(writer, "windKmh", current.WindSpeed * 3.6);
                WriteNumber(writer, "precipitationMm", current.HourPrecipitation);
                WriteNumber(writer, "uvIndex", current.UvIndex);
                WriteNumber(writer, "dewPointC", current.DewPoint);
                writer.WriteNumber("weatherCode", weatherCode);
                writer.WriteString("condition", Condition(weatherCode));
                writer.WriteStartObject("today");
                WriteDay(writer, days[0]);
                // WEB1: the service gives no hour already past; maxC, minC, the chance of rain and the UV peak of today
                // are of the hours from this one on.
                if (days[0].From is { } from)
                    writer.WriteString("figuresFrom", from.ToString("HH:mm", CultureInfo.InvariantCulture));
                WriteNumber(writer, "maxC", days[0].Max);
                WriteNumber(writer, "minC", days[0].Min);
                WriteNumber(writer, "rainProbabilityPercent", days[0].RainProbability);
                WriteNumber(writer, "uvIndexMax", days[0].UvIndexMax);
                WriteClock(writer, "sunrise", sunToday.Rise);
                WriteClock(writer, "sunset", sunToday.Set);
                writer.WriteEndObject();
                writer.WriteStartObject("tomorrow");
                WriteDay(writer, days[1]);
                WriteNumber(writer, "maxC", days[1].Max);
                WriteNumber(writer, "minC", days[1].Min);
                WriteNumber(writer, "rainProbabilityPercent", days[1].RainProbability);
                WriteNumber(writer, "uvIndexMax", days[1].UvIndexMax);
                writer.WriteString("condition", Condition(days[1].Code));
                WriteClock(writer, "sunrise", sunTomorrow.Rise);
                WriteClock(writer, "sunset", sunTomorrow.Set);
                writer.WriteEndObject();
                // Uso real tanda 6: the days after tomorrow, while the service forecasts them.
                writer.WriteStartArray("laterDays");
                foreach (Day day in days.Skip(2).TakeWhile(static day => day.Steps > 0))
                {
                    writer.WriteStartObject();
                    WriteDay(writer, day);
                    writer.WriteString("condition", Condition(day.Code));
                    WriteNumber(writer, "maxC", day.Max);
                    WriteNumber(writer, "minC", day.Min);
                    WriteNumber(writer, "rainProbabilityPercent", day.RainProbability);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                // WEB3: no service gives the air without a key and allows a sold product (Open-Meteo's is
                // non-commercial; OpenAQ and WAQI ask for a key, WAQI an agreement for for-profit use; MET Norway's covers
                // Norway only): the field is absent and the reason is said, so it is never read as clean air.
                writer.WriteStartObject("unavailable");
                writer.WriteString("airQuality", "no_keyless_service_allows_commercial_use");
                writer.WriteEndObject();
                writer.WriteStartObject("elapsedMs");
                writer.WriteNumber("place", placeMs);
                writer.WriteNumber("forecast", forecastMs);
                writer.WriteNumber("total", totalMs);
                writer.WriteEndObject();
                writer.WriteString("authority", "met_norway_locationforecast_v2");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, effectObserved: false);
        }
        catch (Exception exception) when (
            exception is HttpRequestException or JsonException or InvalidOperationException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return ExternalJson.FailureBeforeEffect(operation, "weather_service_unavailable");
        }
    }

    // --- The place ---------------------------------------------------------------------------------------------------

    // The place read is the one the gazetteer chooses for the name asked (GeoNamesGazetteer.Choose, shared with
    // another place's time since WEB2). The receipt says when namesakes exist elsewhere.
    private sealed class Namesakes(string? dialectCountry)
    {
        internal string? DialectCountry { get; } = dialectCountry;

        internal bool Elsewhere { get; set; }
    }

    // The place read, or none and what was found instead: the namesakes of comparable size (Ambiguous), the places of
    // the name outside the region said, or the places whose name begins so when none is named so.
    private sealed record PlaceChoice(PublicPlace? Place, IReadOnlyList<GazetteerPlace> Candidates, bool Ambiguous);

    private ExternalCapabilityReceipt PlaceCandidates(string operation, string location, PlaceChoice choice) =>
        new(operation, false, false, _places().CandidatesJson(location, choice.Candidates),
            choice.Ambiguous ? "weather_place_ambiguous" : "weather_place_not_found");

    private PlaceChoice Geocode(string location, Namesakes namesakes)
    {
        GeoNamesGazetteer places = _places();
        GazetteerChoice choice = places.Choose(location, namesakes.DialectCountry);
        namesakes.Elsewhere = choice.NamesakesElsewhere;
        return choice.Place is { } place
            ? new(PlaceOf(places, place), [], false)
            : new(null, choice.Candidates, choice.Ambiguous);
    }

    private static PublicPlace PlaceOf(GeoNamesGazetteer places, GazetteerPlace place)
    {
        string? region = places.Region(place)?.NameEs;
        return new PublicPlace(
            place.NameEs,
            region is not null && GeoNamesGazetteer.Fold(region) == GeoNamesGazetteer.Fold(place.NameEs) ? null : region,
            places.Country(place)?.NameEs ?? string.Empty,
            place.Latitude,
            place.Longitude,
            "named_place_geocoded",
            // A country of several zones has none of its own: it is read in its capital's.
            place.TimeZone ?? places.CapitalZone(place));
    }

    private static TimeZoneInfo? Zone(string? id) =>
        id is { Length: > 0 } && TimeZoneInfo.TryFindSystemTimeZoneById(id, out TimeZoneInfo? zone) ? zone : null;

    // The zone by its IANA name, as the service of places names it; this PC's own zone is named so too.
    private static string ZoneName(TimeZoneInfo zone) =>
        !zone.HasIanaId && TimeZoneInfo.TryConvertWindowsIdToIanaId(zone.Id, out string? iana) ? iana : zone.Id;

    // --- The forecast ------------------------------------------------------------------------------------------------

    // One step of the forecast: its start, in UTC and in the place's clock, the instant readings, the sky and the rain
    // of the hour (or of the six hours) that follow, the six hours' extremes, and the chance of rain the service gives
    // for the hour and for the six hours that follow (outside the Nordic countries it gives none).
    private sealed record Step(
        DateTimeOffset At,
        DateTime Local,
        double? Temperature,
        double? Apparent,
        double? Humidity,
        double? WindSpeed,
        double? DewPoint,
        double? UvIndex,
        string? Symbol,
        double? HourPrecipitation,
        double? SixHoursMax,
        double? SixHoursMin,
        double? HourRainChance,
        double? SixHoursRainChance);

    private static List<Step> Steps(JsonElement root, TimeZoneInfo zone)
    {
        var steps = new List<Step>();
        if (!root.TryGetProperty("properties", out JsonElement properties)
            || !properties.TryGetProperty("timeseries", out JsonElement series)
            || series.ValueKind != JsonValueKind.Array)
        {
            return steps;
        }

        foreach (JsonElement item in series.EnumerateArray())
        {
            if (ReadString(item, "time") is not { } time
                || !DateTimeOffset.TryParse(time, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out DateTimeOffset at)
                || !item.TryGetProperty("data", out JsonElement data))
            {
                continue;
            }
            JsonElement? instant = Details(data, "instant");
            JsonElement? hour = Details(data, "next_1_hours");
            JsonElement? sixHours = Details(data, "next_6_hours");
            steps.Add(new Step(
                at,
                TimeZoneInfo.ConvertTime(at, zone).DateTime,
                ReadAt(instant, "air_temperature"),
                ReadAt(instant, "apparent_air_temperature"),
                ReadAt(instant, "relative_humidity"),
                ReadAt(instant, "wind_speed"),
                ReadAt(instant, "dew_point_temperature"),
                ReadAt(instant, "ultraviolet_index_clear_sky"),
                Symbol(data, "next_1_hours") ?? Symbol(data, "next_6_hours"),
                ReadAt(hour, "precipitation_amount"),
                ReadAt(sixHours, "air_temperature_max"),
                ReadAt(sixHours, "air_temperature_min"),
                ReadAt(hour, "probability_of_precipitation"),
                ReadAt(sixHours, "probability_of_precipitation")));
        }

        steps.Sort(static (left, right) => left.At.CompareTo(right.At));
        return steps;
    }

    // A day of the place's clock, as its steps give it: its extremes and its highest chance of rain (of the instants,
    // the hours and the six hours that end within the day: another day's rain is not this day's), the highest UV index
    // and the most severe sky, as Open-Meteo's daily weather code was («the most severe weather condition on a given
    // day»). The service forecasts no hour already past: today's figures are from its first step on («figuresFrom»).
    private sealed record Day(
        DateOnly Date, int Steps, DateTime? From, double? Max, double? Min, double? RainProbability, double? UvIndexMax, int Code);

    private static Day DayOf(List<Step> steps, DateOnly date)
    {
        DateTime start = date.ToDateTime(TimeOnly.MinValue);
        DateTime end = start.AddDays(1);
        List<Step> within = [.. steps.Where(step => step.Local >= start && step.Local < end)];
        List<Step> wholeSixHours = [.. within.Where(step => step.Local.AddHours(6) <= end)];
        double?[] highs = [.. within.Select(static step => step.Temperature), .. wholeSixHours.Select(static step => step.SixHoursMax)];
        double?[] lows = [.. within.Select(static step => step.Temperature), .. wholeSixHours.Select(static step => step.SixHoursMin)];
        return new Day(
            date,
            within.Count,
            within.Count == 0 ? null : within[0].Local,
            highs.Max(),
            lows.Min(),
            within.Max(step => step.HourRainChance ?? (step.Local.AddHours(6) <= end ? step.SixHoursRainChance : null)),
            within.Max(static step => step.UvIndex),
            within.Count == 0 ? -1 : within.Max(static step => WmoCode(step.Symbol)));
    }

    // --- The sun -----------------------------------------------------------------------------------------------------

    private readonly record struct SunTimes(DateTimeOffset? Rise, DateTimeOffset? Set);

    // Uso real tanda 2 (2026-09-23) «necesito el horario de la caída del sol para mañana»: MET Norway's Sunrise 3.0
    // gives the day's sunrise and sunset in the offset asked (https://api.met.no/weatherapi/sunrise/3.0/documentation);
    // when it does not answer, the weather still does and the times are null.
    private async Task<SunTimes> ReadSunAsync(
        string coordinates, DateOnly day, TimeZoneInfo zone, CancellationToken cancellationToken)
    {
        TimeSpan offset = zone.GetUtcOffset(day.ToDateTime(new TimeOnly(12, 0)));
        string url = SunAuthority + "?" + coordinates
            + "&date=" + day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture)
            // «+» escaped: in a query it may be read as a space.
            + "&offset=" + (offset < TimeSpan.Zero ? "-" : "%2B") + offset.ToString(@"hh\:mm", CultureInfo.InvariantCulture);
        // The sun of a day never changes: it is kept until that day is past everywhere.
        var dayPast = new DateTimeOffset(day.AddDays(2).ToDateTime(TimeOnly.MinValue), TimeSpan.Zero);
        try
        {
            using JsonDocument document = JsonDocument.Parse(
                await ReadAsync(url, dayPast, cancellationToken).ConfigureAwait(false));
            return document.RootElement.TryGetProperty("properties", out JsonElement properties)
                ? new SunTimes(SunTime(properties, "sunrise"), SunTime(properties, "sunset"))
                : default;
        }
        catch (Exception exception) when (
            exception is HttpRequestException or JsonException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return default;
        }
    }

    private static DateTimeOffset? SunTime(JsonElement properties, string name) =>
        properties.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Object
        && ReadString(value, "time") is { } time
        && DateTimeOffset.TryParse(time, CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTimeOffset at)
            ? at
            : null;

    // --- The service -------------------------------------------------------------------------------------------------

    // KeptUntil: no earlier than the answer's Expires, nor than the wait its product asks (ForecastRepeat, a day past).
    private sealed record KeptAnswer(string Url, string Body, DateTimeOffset KeptUntil, DateTimeOffset? LastModified);

    // MET Norway: «Never repeat requests until the time indicated in the Expires response header», «Use the
    // If-Modified-Since request header», and on a 429 «limit traffic immediately»: nothing more is asked until its
    // Retry-After (or a minute) has passed. A failure that is quick and not a
    // refusal (no answer, a timeout status, a server error) is asked once more after a pause, as TransientHttp does.
    private async Task<string> ReadAsync(string url, DateTimeOffset unchangedUntil, CancellationToken cancellationToken)
    {
        KeptAnswer? kept;
        lock (_keptLock)
        {
            LoadKept();
            _kept.TryGetValue(url, out kept);
        }
        if (kept is not null && _now() < kept.KeptUntil)
            return kept.Body;
        lock (_keptLock)
        {
            if (_now() < _quietUntil)
                throw new HttpRequestException("MET Norway asked to wait", null, HttpStatusCode.TooManyRequests);
        }

        var clock = Stopwatch.StartNew();
        try
        {
            return await AskAsync(url, kept, unchangedUntil, cancellationToken).ConfigureAwait(false);
        }
        catch (HttpRequestException exception) when (
            exception.StatusCode is null or HttpStatusCode.RequestTimeout or >= HttpStatusCode.InternalServerError
            && clock.Elapsed <= TransientHttp.QuickFailure)
        {
            await Task.Delay(TransientHttp.Pause, cancellationToken).ConfigureAwait(false);
        }

        return await AskAsync(url, kept, unchangedUntil, cancellationToken).ConfigureAwait(false);
    }

    private async Task<string> AskAsync(
        string url, KeptAnswer? kept, DateTimeOffset unchangedUntil, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        if (kept?.LastModified is { } since)
            request.Headers.IfModifiedSince = since;
        using HttpResponseMessage response = await _http.SendAsync(request, cancellationToken).ConfigureAwait(false);
        if (response.StatusCode == HttpStatusCode.TooManyRequests)
        {
            TimeSpan wait = response.Headers.RetryAfter?.Delta
                ?? (response.Headers.RetryAfter?.Date is { } date ? date - _now() : QuietWithoutRetryAfter);
            lock (_keptLock)
                _quietUntil = _now() + wait;
        }
        string body;
        if (response.StatusCode == HttpStatusCode.NotModified && kept is not null)
        {
            body = kept.Body;
        }
        else
        {
            response.EnsureSuccessStatusCode();
            body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
        }

        DateTimeOffset expires = response.Content.Headers.Expires ?? _now();
        var answer = new KeptAnswer(
            url,
            body,
            expires > unchangedUntil ? expires : unchangedUntil,
            response.Content.Headers.LastModified ?? kept?.LastModified);
        lock (_keptLock)
        {
            if (!_kept.ContainsKey(url) && _kept.Count >= KeptAnswers)
                _kept.Remove(_kept.Values.MinBy(static old => old.KeptUntil)!.Url);
            _kept[url] = answer;
            SaveKept();
        }
        return body;
    }

    // Called under _keptLock. A kept file that cannot be read is as if nothing had been kept: the weather is asked.
    private void LoadKept()
    {
        if (_keptLoaded || _keptFile is null)
            return;
        _keptLoaded = true;
        try
        {
            if (!File.Exists(_keptFile))
                return;
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(_keptFile));
            foreach (JsonElement entry in document.RootElement.GetProperty("answers").EnumerateArray())
            {
                if (_kept.Count >= KeptAnswers)
                    break;
                var answer = new KeptAnswer(
                    entry.GetProperty("url").GetString()!,
                    entry.GetProperty("body").GetString()!,
                    entry.GetProperty("keptUntil").GetDateTimeOffset(),
                    entry.TryGetProperty("lastModified", out JsonElement modified) ? modified.GetDateTimeOffset() : null);
                _kept[answer.Url] = answer;
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException
            or InvalidOperationException or KeyNotFoundException or FormatException)
        {
            _kept.Clear();
        }
    }

    // Called under _keptLock. Not being able to write only means asking again after a restart, once that is allowed.
    private void SaveKept()
    {
        if (_keptFile is null)
            return;
        string temporary = _keptFile + "." + Environment.ProcessId.ToString(CultureInfo.InvariantCulture) + ".tmp";
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_keptFile)!);
            using (FileStream stream = File.Create(temporary))
            using (var writer = new Utf8JsonWriter(stream))
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteStartArray("answers");
                foreach (KeptAnswer answer in _kept.Values)
                {
                    writer.WriteStartObject();
                    writer.WriteString("url", answer.Url);
                    writer.WriteString("keptUntil", answer.KeptUntil);
                    if (answer.LastModified is { } modified)
                        writer.WriteString("lastModified", modified);
                    writer.WriteString("body", answer.Body);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteEndObject();
            }
            File.Move(temporary, _keptFile, overwrite: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            try
            {
                File.Delete(temporary);
            }
            catch (Exception leftover) when (leftover is IOException or UnauthorizedAccessException)
            {
                // A temporary file left behind is overwritten by the next save.
            }
        }
    }

    // --- The sky -----------------------------------------------------------------------------------------------------

    // MET Norway's symbols (https://github.com/metno/weathericons, weather/legend.csv; «_day», «_night» and
    // «_polartwilight» are variants of one sky) as the WMO present-weather codes of table 4677 (WMO-No. 306), the codes
    // the receipt names: showers 80-86, rain 61-65, rain and snow 68-69, snow 71-75, thunderstorm 95 (heavy 97), fog 45.
    internal static int WmoCode(string? symbol)
    {
        string sky = symbol is null ? string.Empty : symbol.Split('_', 2)[0].Trim();
        if (sky.EndsWith("andthunder", StringComparison.Ordinal))
            return sky.StartsWith("heavy", StringComparison.Ordinal) ? 97 : 95;
        return sky switch
        {
            "clearsky" => 0,
            "fair" => 1,
            "partlycloudy" => 2,
            "cloudy" => 3,
            "fog" => 45,
            "lightrain" => 61,
            "rain" => 63,
            "heavyrain" => 65,
            "lightsleet" => 68,
            "sleet" or "heavysleet" => 69,
            "lightsnow" => 71,
            "snow" => 73,
            "heavysnow" => 75,
            "lightrainshowers" => 80,
            "rainshowers" => 81,
            "heavyrainshowers" => 82,
            "lightsleetshowers" => 83,
            "sleetshowers" or "heavysleetshowers" => 84,
            "lightsnowshowers" => 85,
            "snowshowers" or "heavysnowshowers" => 86,
            _ => -1,
        };
    }

    // Códigos WMO, en las palabras que una persona usa para el cielo.
    internal static string Condition(int code) => code switch
    {
        0 => "despejado",
        1 => "mayormente despejado",
        2 => "parcialmente nublado",
        3 => "nublado",
        45 or 48 => "niebla",
        51 or 53 or 55 => "llovizna",
        56 or 57 => "llovizna helada",
        61 => "lluvia débil",
        63 => "lluvia",
        65 => "lluvia intensa",
        66 or 67 => "lluvia helada",
        68 => "aguanieve débil",
        69 => "aguanieve",
        71 => "nieve débil",
        73 => "nieve",
        75 => "nieve intensa",
        77 => "granizo fino",
        80 => "chubascos débiles",
        81 => "chubascos",
        82 => "chubascos intensos",
        83 => "chubascos de aguanieve débiles",
        84 => "chubascos de aguanieve",
        85 or 86 => "chubascos de nieve",
        95 => "tormenta",
        96 or 99 => "tormenta con granizo",
        97 => "tormenta fuerte",
        _ => "sin dato",
    };

    // --- Reading and writing -----------------------------------------------------------------------------------------

    private static JsonElement? Details(JsonElement data, string period) =>
        data.TryGetProperty(period, out JsonElement value) && value.ValueKind == JsonValueKind.Object
        && value.TryGetProperty("details", out JsonElement details) && details.ValueKind == JsonValueKind.Object
            ? details
            : null;

    private static string? Symbol(JsonElement data, string period) =>
        data.TryGetProperty(period, out JsonElement value) && value.ValueKind == JsonValueKind.Object
        && value.TryGetProperty("summary", out JsonElement summary) && summary.ValueKind == JsonValueKind.Object
            ? ReadString(summary, "symbol_code")
            : null;

    private static double? ReadAt(JsonElement? element, string name) =>
        element is { } found && found.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            ? value.GetDouble()
            : null;

    private static string? ReadString(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static void WriteNumber(Utf8JsonWriter writer, string name, double? value)
    {
        if (value is null)
            writer.WriteNull(name);
        else
            writer.WriteNumber(name, Math.Round(value.Value, 1));
    }

    // The receipt carries only the clock of the place («19:32»).
    private static void WriteClock(Utf8JsonWriter writer, string name, DateTimeOffset? at)
    {
        if (at is { } time)
            writer.WriteString(name, time.ToString("HH:mm", CultureInfo.InvariantCulture));
        else
            writer.WriteNull(name);
    }

    // Uso real tanda 6: a day of the forecast is named by the person by its weekday
    // («el sábado»), so each day carries its date and the weekday of that date, in the
    // same plain Spanish words as the sky.
    private static void WriteDay(Utf8JsonWriter writer, Day day)
    {
        writer.WriteString("date", day.Date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
        writer.WriteString("weekday", Weekday(day.Date.DayOfWeek));
    }

    private static string Weekday(DayOfWeek day) => day switch
    {
        DayOfWeek.Monday => "lunes",
        DayOfWeek.Tuesday => "martes",
        DayOfWeek.Wednesday => "miércoles",
        DayOfWeek.Thursday => "jueves",
        DayOfWeek.Friday => "viernes",
        DayOfWeek.Saturday => "sábado",
        _ => "domingo",
    };

    public void Dispose() => _http.Dispose();
}
