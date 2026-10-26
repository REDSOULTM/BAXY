using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo W): la encuesta pide el
/// clima, no páginas sobre el clima. Esta lectura pregunta a un servicio público
/// sin clave: el lugar nombrado se geocodifica; sin lugar, la ubicación de este
/// PC se toma de su dirección pública. El recibo trae sólo lo que el servicio
/// devolvió, con las unidades que declaró; nada se inventa ni se redondea de más.
/// </summary>
internal sealed class OpenMeteoWeatherAdapter : IExternalOperationAdapter, IDisposable
{
    private const string GeocodingAuthority = "https://geocoding-api.open-meteo.com/v1/search";
    private const string GeocodedPlaceAuthority = "https://geocoding-api.open-meteo.com/v1/get";
    private const string ForecastAuthority = "https://api.open-meteo.com/v1/forecast";
    private const string AirQualityAuthority = "https://air-quality-api.open-meteo.com/v1/air-quality";

    private readonly HttpClient _http;
    private readonly Func<string, CancellationToken, Task<string>>? _fetch;
    private readonly PublicPlaceLocator _locator;

    // Ronda 22 (r18 t4-c05: the weather took 5.3 s): a named place this session already resolved is not geocoded
    // again; the forecast is always read anew. Only a place found is kept, with whether it has namesakes elsewhere.
    private readonly ConcurrentDictionary<(string Location, string? DialectCountry), (PublicPlace Place, bool Elsewhere)>
        _resolvedPlaces = new();

    internal OpenMeteoWeatherAdapter()
    {
        _http = new HttpClient(SearchPageReader.StrangerHandler()) { Timeout = TimeSpan.FromSeconds(12) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY/1.0 weather-read");
        _locator = new PublicPlaceLocator(FetchAsync);
    }

    // Las pruebas entregan las respuestas de cada dirección sin red.
    internal OpenMeteoWeatherAdapter(Func<string, CancellationToken, Task<string>> fetch)
    {
        _http = new HttpClient();
        _fetch = fetch;
        _locator = new PublicPlaceLocator(FetchAsync);
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
            PlaceChoice choice;
            if (location is null)
            {
                PublicPlaceLocator.Lookup here = await _locator.LocateAsync(cancellationToken).ConfigureAwait(false);
                if (here.Unreachable) return ExternalJson.FailureBeforeEffect(operation, "weather_service_unavailable");
                choice = new(here.Place, [], false);
            }
            else
            {
                choice = await ResolvePlaceAsync(location, namesakes, cancellationToken).ConfigureAwait(false);
            }
            PublicPlace? place = choice.Place;
            long placeMs = clock.ElapsedMilliseconds;
            if (place is null)
            {
                return location is null
                    ? ExternalJson.FailureBeforeEffect(operation, "weather_location_unavailable")
                    : PlaceCandidates(operation, location, choice);
            }

            string coordinates = "?latitude=" + place.Value.Latitude.ToString("F4", CultureInfo.InvariantCulture)
                + "&longitude=" + place.Value.Longitude.ToString("F4", CultureInfo.InvariantCulture);
            // Uso real tanda 6 «Dime el UV index», «¿Cómo está el dew point ahora?»
            // buscaron definiciones y mapas en la web: el índice UV y el punto de
            // rocío son del mismo servicio y vienen en la misma lectura. «El
            // pronóstico del tiempo para la semana» sólo tuvo hoy y mañana: los
            // siete días llegan en la misma petición; los que siguen a mañana van
            // en laterDays.
            string forecastUrl = ForecastAuthority + coordinates
                + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,precipitation,"
                + "uv_index,dew_point_2m"
                + "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunrise,sunset,uv_index_max"
                + "&timezone=auto&forecast_days=7";
            // Uso real tanda 4c «Whats the air quality hoy?» buscó páginas de
            // otro país: la calidad del aire del mismo lugar es otra lectura del
            // mismo servicio, pedida a la vez; si no contesta, el clima sigue.
            Task<string> forecastRead = FetchAsync(forecastUrl, cancellationToken);
            Task<AirQuality?> airRead = ReadAirQualityAsync(AirQualityAuthority + coordinates
                + "&current=us_aqi,pm2_5,pm10&timezone=auto", cancellationToken);
            string forecastJson = await forecastRead.ConfigureAwait(false);
            long forecastMs = clock.ElapsedMilliseconds - placeMs;
            AirQuality? air = await airRead.ConfigureAwait(false);
            long totalMs = clock.ElapsedMilliseconds;
            using JsonDocument forecast = JsonDocument.Parse(forecastJson);
            JsonElement root = forecast.RootElement;
            if (!root.TryGetProperty("current", out JsonElement current)
                || current.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("daily", out JsonElement daily)
                || daily.ValueKind != JsonValueKind.Object)
            {
                return ExternalJson.FailureBeforeEffect(operation, "weather_service_unavailable");
            }

            int weatherCode = ReadInt(current, "weather_code") ?? -1;
            int? tomorrowCode = ReadIntAt(daily, "weather_code", 1);
            PublicPlace located = place.Value;
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
                writer.WriteString("observedAtLocal", ReadString(current, "time") ?? string.Empty);
                writer.WriteString("timezone", ReadString(root, "timezone") ?? string.Empty);
                WriteNumber(writer, "temperatureC", ReadDouble(current, "temperature_2m"));
                WriteNumber(writer, "apparentC", ReadDouble(current, "apparent_temperature"));
                WriteNumber(writer, "humidityPercent", ReadDouble(current, "relative_humidity_2m"));
                WriteNumber(writer, "windKmh", ReadDouble(current, "wind_speed_10m"));
                WriteNumber(writer, "precipitationMm", ReadDouble(current, "precipitation"));
                WriteNumber(writer, "uvIndex", ReadDouble(current, "uv_index"));
                WriteNumber(writer, "dewPointC", ReadDouble(current, "dew_point_2m"));
                writer.WriteNumber("weatherCode", weatherCode);
                writer.WriteString("condition", Condition(weatherCode));
                writer.WriteStartObject("today");
                WriteDay(writer, ReadStringAt(daily, "time", 0));
                WriteNumber(writer, "maxC", ReadDoubleAt(daily, "temperature_2m_max", 0));
                WriteNumber(writer, "minC", ReadDoubleAt(daily, "temperature_2m_min", 0));
                WriteNumber(writer, "rainProbabilityPercent", ReadDoubleAt(daily, "precipitation_probability_max", 0));
                WriteNumber(writer, "uvIndexMax", ReadDoubleAt(daily, "uv_index_max", 0));
                WriteClock(writer, "sunrise", ReadStringAt(daily, "sunrise", 0));
                WriteClock(writer, "sunset", ReadStringAt(daily, "sunset", 0));
                writer.WriteEndObject();
                writer.WriteStartObject("tomorrow");
                WriteDay(writer, ReadStringAt(daily, "time", 1));
                WriteNumber(writer, "maxC", ReadDoubleAt(daily, "temperature_2m_max", 1));
                WriteNumber(writer, "minC", ReadDoubleAt(daily, "temperature_2m_min", 1));
                WriteNumber(writer, "rainProbabilityPercent", ReadDoubleAt(daily, "precipitation_probability_max", 1));
                WriteNumber(writer, "uvIndexMax", ReadDoubleAt(daily, "uv_index_max", 1));
                writer.WriteString("condition", Condition(tomorrowCode ?? -1));
                WriteClock(writer, "sunrise", ReadStringAt(daily, "sunrise", 1));
                WriteClock(writer, "sunset", ReadStringAt(daily, "sunset", 1));
                writer.WriteEndObject();
                writer.WriteStartArray("laterDays");
                for (int index = 2; ReadStringAt(daily, "time", index) is { } date; index++)
                {
                    writer.WriteStartObject();
                    WriteDay(writer, date);
                    writer.WriteString("condition", Condition(ReadIntAt(daily, "weather_code", index) ?? -1));
                    WriteNumber(writer, "maxC", ReadDoubleAt(daily, "temperature_2m_max", index));
                    WriteNumber(writer, "minC", ReadDoubleAt(daily, "temperature_2m_min", index));
                    WriteNumber(writer, "rainProbabilityPercent", ReadDoubleAt(daily, "precipitation_probability_max", index));
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                if (air is { } quality)
                {
                    writer.WriteStartObject("airQuality");
                    writer.WriteNumber("usAqi", quality.UsAqi);
                    writer.WriteString("category", AirCategory(quality.UsAqi));
                    WriteNumber(writer, "pm25", quality.Pm25);
                    WriteNumber(writer, "pm10", quality.Pm10);
                    writer.WriteEndObject();
                }
                else
                {
                    writer.WriteNull("airQuality");
                }
                writer.WriteStartObject("elapsedMs");
                writer.WriteNumber("place", placeMs);
                writer.WriteNumber("forecast", forecastMs);
                writer.WriteNumber("total", totalMs);
                writer.WriteEndObject();
                writer.WriteString("authority", "open_meteo_forecast_v1");
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

    // The place read is the one whose name is the name asked (case, accents and punctuation folded), in Spanish or in
    // English, because the person names it in either. Uso real tanda 4c «Digame el weather lunes 13 en North Carolina»
    // read «Calvary, Georgia», a hamlet that carries the state's name as an alias: an alias, a park that carries the
    // name or a place that only shares a word with it is not the place. The geocoder indexes no region by its name,
    // so a region is found as the region (admin1) its places name exactly so, and read by its own identifier.
    // «Lugar, Región» keeps the places of that name whose region, province or country is the one said.
    private static readonly string[] RegionFields = ["admin1", "admin2", "country", "country_code"];

    // Ronda 19 (r17 t2-c13 «¿qué tiempo va a hacer mañana en Valencia? ¿cojo paraguas?» → Valencia, Venezuela, the
    // most populous, with no country said): places of the asked name whose size is comparable (a quarter of the
    // largest or more) are namesakes, and among several nothing is chosen: they go back as candidates, largest first.
    // The country the person's speech marks (dialectCountry) keeps the namesakes of that country; a much smaller
    // place of the name is no namesake of a large one. The receipt says when namesakes exist elsewhere.
    private sealed class Namesakes(string? dialectCountry)
    {
        internal string? DialectCountry { get; } = dialectCountry;

        internal bool Elsewhere { get; set; }
    }

    private const double ComparableNamesake = 0.25;

    // The place read, or none and what the service showed instead: the namesakes of comparable size (Ambiguous), or
    // the results of the search when nothing was named so.
    private sealed record PlaceChoice(PublicPlace? Place, IReadOnlyList<JsonElement> Candidates, bool Ambiguous);

    private static ExternalCapabilityReceipt PlaceCandidates(string operation, string location, PlaceChoice choice) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requested", location);
            // Ronda final 10 (regla 3): how many places the geocoder gave, the first eight listed.
            writer.WriteNumber("candidateCount", choice.Candidates.Count);
            if (choice.Candidates.Count > 8) writer.WriteBoolean("truncated", true);
            writer.WriteStartArray("candidates");
            foreach (JsonElement item in choice.Candidates.Take(8))
            {
                writer.WriteStartObject();
                writer.WriteString("name", ReadString(item, "name") ?? string.Empty);
                if (ReadString(item, "admin1") is { Length: > 0 } region)
                    writer.WriteString("region", region);
                writer.WriteString("country", ReadString(item, "country") ?? string.Empty);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
        }), choice.Ambiguous ? "weather_place_ambiguous" : "weather_place_not_found");

    private async Task<PlaceChoice> ResolvePlaceAsync(
        string location, Namesakes namesakes, CancellationToken cancellationToken)
    {
        var key = (location.ToUpperInvariant(), namesakes.DialectCountry?.ToUpperInvariant());
        if (_resolvedPlaces.TryGetValue(key, out var known))
        {
            namesakes.Elsewhere = known.Elsewhere;
            return new(known.Place, [], false);
        }

        PlaceChoice choice = await GeocodeAsync(location, namesakes, cancellationToken).ConfigureAwait(false);
        if (choice.Place is { } found)
            _resolvedPlaces[key] = (found, namesakes.Elsewhere);
        return choice;
    }

    private async Task<PlaceChoice> GeocodeAsync(string location, Namesakes namesakes, CancellationToken cancellationToken)
    {
        // M58 (v3d-final F-p07-t1/t2 «the weather in Foster City»): «Lugar, Región» sends only the name to the
        // geocoder and keeps, of the places of that name, those in the region said.
        string[] parts = location.Split(',', 2, StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        string? within = parts.Length == 2 ? parts[1] : null;
        if (within is not null)
            location = parts[0];
        string asked = Fold(location);
        Task<string> spanishRead = FetchAsync(GeocodingUrl(location, "es"), cancellationToken);
        Task<string> englishRead = FetchAsync(GeocodingUrl(location, "en"), cancellationToken);
        using JsonDocument spanish = JsonDocument.Parse(await spanishRead.ConfigureAwait(false));
        using JsonDocument english = JsonDocument.Parse(await englishRead.ConfigureAwait(false));
        var englishById = new Dictionary<long, JsonElement>();
        foreach (JsonElement item in Results(english))
        {
            if (ReadLong(item, "id") is long id)
                englishById.TryAdd(id, item);
        }
        List<JsonElement> candidates = Results(spanish);
        var spanishIds = candidates.Select(item => ReadLong(item, "id")).OfType<long>().ToHashSet();
        candidates.AddRange(Results(english).Where(item => ReadLong(item, "id") is not long id || !spanishIds.Contains(id)));

        string?[] Spellings(JsonElement item, string field)
        {
            JsonElement? other = ReadLong(item, "id") is long id && englishById.TryGetValue(id, out JsonElement found)
                ? found
                : null;
            return [ReadString(item, field), other is { } englishItem ? ReadString(englishItem, field) : null];
        }

        bool Named(JsonElement item, string field, string folded) =>
            Spellings(item, field).Any(name => name is not null && Fold(name) == folded);

        // A result the service gives without an identifier is told from another by where it is.
        List<JsonElement> exact = [.. candidates
            .Where(item => Named(item, "name", asked))
            .DistinctBy(item => ReadLong(item, "id")?.ToString(CultureInfo.InvariantCulture)
                ?? ReadDouble(item, "latitude") + "/" + ReadDouble(item, "longitude"))];
        long? regionId = candidates
            .Where(item => Named(item, "admin1", asked))
            .Select(item => ReadLong(item, "admin1_id"))
            .OfType<long>()
            .GroupBy(id => id)
            .OrderByDescending(group => group.Count())
            .Select(group => (long?)group.Key)
            .FirstOrDefault();
        if (regionId is long region
            && !exact.Any(item => ReadLong(item, "id") == region)
            && await ReadGeocodedAsync(region, cancellationToken).ConfigureAwait(false) is { } regionItem)
        {
            exact.Add(regionItem);
        }

        if (within is not null)
        {
            string saidRegion = Fold(within);
            exact = [.. exact.Where(item => RegionFields.Any(field => Named(item, field, saidRegion)))];
        }

        if (exact.Count == 0)
            return new(null, [.. candidates.Select(item => item.Clone())], false);
        double top = exact.Max(item => ReadDouble(item, "population") ?? 0);
        List<JsonElement> comparable = [.. exact
            .Where(item => top <= 0 || (ReadDouble(item, "population") ?? 0) >= ComparableNamesake * top)
            .OrderByDescending(item => ReadDouble(item, "population") ?? 0)];
        if (comparable.Count > 1 && namesakes.DialectCountry is { Length: > 0 } marked)
        {
            List<JsonElement> spoken = [.. comparable.Where(item =>
                string.Equals(ReadString(item, "country_code"), marked, StringComparison.OrdinalIgnoreCase))];
            if (spoken.Count == 1)
            {
                namesakes.Elsewhere = true;
                comparable = spoken;
            }
        }

        if (comparable.Count > 1)
            return new(null, [.. comparable.Select(item => item.Clone())], true);
        PublicPlace? place = PlaceOf(comparable[0], location);
        return place is null ? new(null, [comparable[0].Clone()], false) : new(place, [], false);
    }

    // La región se lee por su identificador; si el servicio no la da, cuenta lo
    // que la búsqueda ya dio.
    private async Task<JsonElement?> ReadGeocodedAsync(long id, CancellationToken cancellationToken)
    {
        try
        {
            string json = await FetchAsync(
                GeocodedPlaceAuthority + "?language=es&id=" + id.ToString(CultureInfo.InvariantCulture),
                cancellationToken).ConfigureAwait(false);
            using JsonDocument document = JsonDocument.Parse(json);
            return document.RootElement.ValueKind == JsonValueKind.Object ? document.RootElement.Clone() : null;
        }
        catch (Exception exception) when (
            exception is HttpRequestException or JsonException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return null;
        }
    }

    private static string GeocodingUrl(string location, string language) =>
        GeocodingAuthority + "?count=100&language=" + language + "&name=" + Uri.EscapeDataString(location);

    private static List<JsonElement> Results(JsonDocument document) =>
        document.RootElement.ValueKind == JsonValueKind.Object
            && document.RootElement.TryGetProperty("results", out JsonElement results)
            && results.ValueKind == JsonValueKind.Array
            ? [.. results.EnumerateArray()]
            : [];

    private static PublicPlace? PlaceOf(JsonElement item, string asked)
    {
        double? latitude = ReadDouble(item, "latitude");
        double? longitude = ReadDouble(item, "longitude");
        if (latitude is null || longitude is null)
            return null;
        string name = ReadString(item, "name") ?? asked;
        string? region = ReadString(item, "admin1");
        return new PublicPlace(
            name,
            region is not null && Fold(region) == Fold(name) ? null : region,
            ReadString(item, "country") ?? string.Empty,
            latitude.Value,
            longitude.Value,
            "named_place_geocoded");
    }

    private static string Fold(string text)
    {
        var folded = new StringBuilder(text.Length);
        foreach (char character in text.Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
                continue;
            folded.Append(char.IsLetterOrDigit(character) ? char.ToLowerInvariant(character) : ' ');
        }
        return string.Join(' ', folded.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private async Task<AirQuality?> ReadAirQualityAsync(string url, CancellationToken cancellationToken)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(await FetchAsync(url, cancellationToken).ConfigureAwait(false));
            if (!document.RootElement.TryGetProperty("current", out JsonElement current)
                || current.ValueKind != JsonValueKind.Object
                || ReadInt(current, "us_aqi") is not int usAqi)
            {
                return null;
            }
            return new AirQuality(usAqi, ReadDouble(current, "pm2_5"), ReadDouble(current, "pm10"));
        }
        catch (Exception exception) when (
            exception is HttpRequestException or JsonException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return null;
        }
    }

    // La escala pública del índice (US AQI), en las palabras de cada tramo.
    internal static string AirCategory(int usAqi) => usAqi switch
    {
        <= 50 => "buena",
        <= 100 => "moderada",
        <= 150 => "dañina para grupos sensibles",
        <= 200 => "dañina",
        <= 300 => "muy dañina",
        _ => "peligrosa",
    };

    private Task<string> FetchAsync(string url, CancellationToken cancellationToken) =>
        TransientHttp.GetStringAsync(_fetch ?? _http.GetStringAsync, url, cancellationToken);

    // Códigos WMO del servicio, en las palabras que una persona usa para el cielo.
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
        71 => "nieve débil",
        73 => "nieve",
        75 => "nieve intensa",
        77 => "granizo fino",
        80 => "chubascos débiles",
        81 => "chubascos",
        82 => "chubascos intensos",
        85 or 86 => "chubascos de nieve",
        95 => "tormenta",
        96 or 99 => "tormenta con granizo",
        _ => "sin dato",
    };

    private static string? ReadString(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static double? ReadDouble(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            ? value.GetDouble()
            : null;

    private static long? ReadLong(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            && value.TryGetInt64(out long number)
            ? number
            : null;

    private static int? ReadInt(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            && value.TryGetInt32(out int number)
            ? number
            : null;

    private static JsonElement? ItemAt(JsonElement element, string name, int index) =>
        element.TryGetProperty(name, out JsonElement array) && array.ValueKind == JsonValueKind.Array
            && array.GetArrayLength() > index
            ? array[index]
            : null;

    private static double? ReadDoubleAt(JsonElement element, string name, int index) =>
        ItemAt(element, name, index) is { ValueKind: JsonValueKind.Number } value ? value.GetDouble() : null;

    private static int? ReadIntAt(JsonElement element, string name, int index) =>
        ItemAt(element, name, index) is { ValueKind: JsonValueKind.Number } value && value.TryGetInt32(out int number)
            ? number
            : null;

    private static string? ReadStringAt(JsonElement element, string name, int index) =>
        ItemAt(element, name, index) is { ValueKind: JsonValueKind.String } value ? value.GetString() : null;

    private static void WriteNumber(Utf8JsonWriter writer, string name, double? value)
    {
        if (value is null)
            writer.WriteNull(name);
        else
            writer.WriteNumber(name, Math.Round(value.Value, 1));
    }

    // Uso real tanda 2 (2026-09-23) «necesito el horario de la caída del sol para
    // mañana»: el servicio da la salida y la puesta del sol de cada día en hora
    // local del lugar («2026-09-24T19:32»); el recibo lleva sólo la hora dicha.
    private static void WriteClock(Utf8JsonWriter writer, string name, string? localIso)
    {
        int separator = localIso?.IndexOf('T', StringComparison.Ordinal) ?? -1;
        string clock = separator >= 0 ? localIso![(separator + 1)..] : string.Empty;
        if (clock.Length == 5 && clock[2] == ':' && char.IsAsciiDigit(clock[0]) && char.IsAsciiDigit(clock[1])
            && char.IsAsciiDigit(clock[3]) && char.IsAsciiDigit(clock[4]))
            writer.WriteString(name, clock);
        else
            writer.WriteNull(name);
    }

    // Uso real tanda 6: a day of the forecast is named by the person by its weekday
    // («el sábado»), so each day carries its date and the weekday of that date, in the
    // same plain Spanish words as the sky.
    private static void WriteDay(Utf8JsonWriter writer, string? isoDate)
    {
        writer.WriteString("date", isoDate ?? string.Empty);
        if (DateOnly.TryParseExact(isoDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out DateOnly day))
            writer.WriteString("weekday", Weekday(day.DayOfWeek));
        else
            writer.WriteNull("weekday");
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

    private readonly record struct AirQuality(int UsAqi, double? Pm25, double? Pm10);
}
