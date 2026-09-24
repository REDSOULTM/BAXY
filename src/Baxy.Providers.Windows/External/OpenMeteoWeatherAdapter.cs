using System.Globalization;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

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

    internal OpenMeteoWeatherAdapter()
    {
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(12) };
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

        try
        {
            PublicPlace? place = location is null
                ? await _locator.LocateAsync(cancellationToken).ConfigureAwait(false)
                : await GeocodeAsync(location, cancellationToken).ConfigureAwait(false);
            if (place is null)
            {
                return ExternalJson.FailureBeforeEffect(
                    operation,
                    location is null ? "weather_location_unavailable" : "weather_place_not_found");
            }

            string coordinates = "?latitude=" + place.Value.Latitude.ToString("F4", CultureInfo.InvariantCulture)
                + "&longitude=" + place.Value.Longitude.ToString("F4", CultureInfo.InvariantCulture);
            // Uso real tanda 6 «Dime el UV index», «¿Cómo está el dew point ahora?»
            // buscaron definiciones y mapas en la web: el índice UV y el punto de
            // rocío son del mismo servicio y vienen en la misma lectura.
            string forecastUrl = ForecastAuthority + coordinates
                + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,precipitation,"
                + "uv_index,dew_point_2m"
                + "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunrise,sunset,uv_index_max"
                + "&timezone=auto&forecast_days=2";
            // Uso real tanda 4c «Whats the air quality hoy?» buscó páginas de
            // otro país: la calidad del aire del mismo lugar es otra lectura del
            // mismo servicio, pedida a la vez; si no contesta, el clima sigue.
            Task<string> forecastRead = FetchAsync(forecastUrl, cancellationToken);
            Task<AirQuality?> airRead = ReadAirQualityAsync(AirQualityAuthority + coordinates
                + "&current=us_aqi,pm2_5,pm10&timezone=auto", cancellationToken);
            string forecastJson = await forecastRead.ConfigureAwait(false);
            AirQuality? air = await airRead.ConfigureAwait(false);
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
                WriteNumber(writer, "maxC", ReadDoubleAt(daily, "temperature_2m_max", 0));
                WriteNumber(writer, "minC", ReadDoubleAt(daily, "temperature_2m_min", 0));
                WriteNumber(writer, "rainProbabilityPercent", ReadDoubleAt(daily, "precipitation_probability_max", 0));
                WriteNumber(writer, "uvIndexMax", ReadDoubleAt(daily, "uv_index_max", 0));
                WriteClock(writer, "sunrise", ReadStringAt(daily, "sunrise", 0));
                WriteClock(writer, "sunset", ReadStringAt(daily, "sunset", 0));
                writer.WriteEndObject();
                writer.WriteStartObject("tomorrow");
                writer.WriteString("date", ReadStringAt(daily, "time", 1) ?? string.Empty);
                WriteNumber(writer, "maxC", ReadDoubleAt(daily, "temperature_2m_max", 1));
                WriteNumber(writer, "minC", ReadDoubleAt(daily, "temperature_2m_min", 1));
                WriteNumber(writer, "rainProbabilityPercent", ReadDoubleAt(daily, "precipitation_probability_max", 1));
                WriteNumber(writer, "uvIndexMax", ReadDoubleAt(daily, "uv_index_max", 1));
                writer.WriteString("condition", Condition(tomorrowCode ?? -1));
                WriteClock(writer, "sunrise", ReadStringAt(daily, "sunrise", 1));
                WriteClock(writer, "sunset", ReadStringAt(daily, "sunset", 1));
                writer.WriteEndObject();
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

    // Uso real tanda 4c «Digame el weather lunes 13 en North Carolina» leyó el
    // clima de «Calvary, Georgia»: el geocodificador lista primero un pueblo que
    // lleva ese nombre como alias, y no indexa los estados ni las regiones por su
    // nombre. De su lista (en español y en inglés, porque la persona nombra el
    // lugar en cualquiera de los dos) se elige: el primer lugar que se llama
    // así; la región de ese nombre cuando la lista la nombra como región de sus
    // lugares y lo que se llama así es un pueblo menor (no una capital, o una
    // cien veces menos poblada que la región); y, sin nada de eso, el primer
    // lugar poblado o región que comparte una palabra con lo pedido. Un alias
    // ajeno o un parque que lleva el nombre no bastan.
    private async Task<PublicPlace?> GeocodeAsync(string location, CancellationToken cancellationToken)
    {
        string asked = RegionKey(location);
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

        JsonElement? namedPlace = candidates
            .Where(item => Spellings(item, "name").Any(name => name is not null && Fold(name) == Fold(location)))
            .Select(item => (JsonElement?)item)
            .FirstOrDefault();
        long? regionId = candidates
            .Where(item => Spellings(item, "admin1").Any(region => region is not null && RegionKey(region) == asked))
            .Select(item => ReadLong(item, "admin1_id"))
            .OfType<long>()
            .GroupBy(id => id)
            .OrderByDescending(group => group.Count())
            .Select(group => (long?)group.Key)
            .FirstOrDefault();

        string? namedCode = namedPlace is { } placeItem ? ReadString(placeItem, "feature_code") : null;
        if (regionId is long region
            && (namedPlace is null || (namedCode is not null && namedCode.StartsWith("PPL", StringComparison.Ordinal)))
            && await ReadGeocodedAsync(region, cancellationToken).ConfigureAwait(false) is { } regionItem)
        {
            double regionPopulation = ReadDouble(regionItem, "population") ?? 0;
            double namedPopulation = namedPlace is { } minor ? ReadDouble(minor, "population") ?? 0 : 0;
            bool regionIsMeant = namedPlace is null
                || namedCode is not ("PPLC" or "PPLA" or "PPLA2")
                || regionPopulation >= 100 * Math.Max(namedPopulation, 1);
            if (regionIsMeant && PlaceOf(regionItem, location) is { } regionPlace)
                return regionPlace;
        }

        if (namedPlace is { } exact)
            return PlaceOf(exact, location);
        string[] askedWords = Fold(location).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        foreach (JsonElement item in Results(spanish))
        {
            if (ReadString(item, "name") is { } name
                && ReadString(item, "feature_code") is { } code
                && (code.StartsWith("PPL", StringComparison.Ordinal) || code.StartsWith("ADM", StringComparison.Ordinal)
                    || code.StartsWith("PCL", StringComparison.Ordinal))
                && Fold(name).Split(' ', StringSplitOptions.RemoveEmptyEntries).Intersect(askedWords).Any())
            {
                return PlaceOf(item, location);
            }
        }

        return null;
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

    // «North Carolina», «Carolina del Norte», «Estado de Jalisco» y «Comunidad
    // Autónoma de Cataluña» se comparan por su nombre propio, sin tildes ni la
    // palabra que dice qué clase de región es.
    private static readonly Regex RegionKind = new(
        @"^(?:comunidad autonoma|comunidad foral|comunidad|estado libre y soberano|estado|provincia|region|"
        + @"departamento|state|province|region|department|prefectura|prefecture|canton|oblast)\s+(?:de\s+la\s+|del\s+|de\s+|of\s+)?"
        + @"|\s+(?:department|province|state|region|prefecture|oblast)$",
        RegexOptions.CultureInvariant);

    private static string RegionKey(string name) => RegionKind.Replace(Fold(name), string.Empty).Trim();

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
        _fetch is not null
            ? _fetch(url, cancellationToken)
            : _http.GetStringAsync(url, cancellationToken);

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

    public void Dispose() => _http.Dispose();

    private readonly record struct AirQuality(int UsAqi, double? Pm25, double? Pm10);
}
