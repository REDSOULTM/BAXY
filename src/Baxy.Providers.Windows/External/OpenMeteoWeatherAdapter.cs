using System.Globalization;
using System.Net.Http;
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
    private const string ForecastAuthority = "https://api.open-meteo.com/v1/forecast";
    // Dos lectores públicos de la ubicación por IP: el segundo contesta cuando el
    // primero no lo hace; ninguno recibe otra cosa que la petición vacía.
    private static readonly string[] LocationByIpAuthorities =
    [
        "https://ipwho.is/",
        "http://ip-api.com/json/?fields=status,country,regionName,city,lat,lon",
    ];

    private readonly HttpClient _http;
    private readonly Func<string, CancellationToken, Task<string>>? _fetch;

    internal OpenMeteoWeatherAdapter()
    {
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(12) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY/1.0 weather-read");
    }

    // Las pruebas entregan las respuestas de cada dirección sin red.
    internal OpenMeteoWeatherAdapter(Func<string, CancellationToken, Task<string>> fetch)
    {
        _http = new HttpClient();
        _fetch = fetch;
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
            Place? place = location is null
                ? await LocateByIpAsync(cancellationToken).ConfigureAwait(false)
                : await GeocodeAsync(location, cancellationToken).ConfigureAwait(false);
            if (place is null)
            {
                return ExternalJson.FailureBeforeEffect(
                    operation,
                    location is null ? "weather_location_unavailable" : "weather_place_not_found");
            }

            string forecastUrl = ForecastAuthority
                + "?latitude=" + place.Value.Latitude.ToString("F4", CultureInfo.InvariantCulture)
                + "&longitude=" + place.Value.Longitude.ToString("F4", CultureInfo.InvariantCulture)
                + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,precipitation"
                + "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunrise,sunset"
                + "&timezone=auto&forecast_days=2";
            string forecastJson = await FetchAsync(forecastUrl, cancellationToken).ConfigureAwait(false);
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
            Place located = place.Value;
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
                writer.WriteNumber("weatherCode", weatherCode);
                writer.WriteString("condition", Condition(weatherCode));
                writer.WriteStartObject("today");
                WriteNumber(writer, "maxC", ReadDoubleAt(daily, "temperature_2m_max", 0));
                WriteNumber(writer, "minC", ReadDoubleAt(daily, "temperature_2m_min", 0));
                WriteNumber(writer, "rainProbabilityPercent", ReadDoubleAt(daily, "precipitation_probability_max", 0));
                WriteClock(writer, "sunrise", ReadStringAt(daily, "sunrise", 0));
                WriteClock(writer, "sunset", ReadStringAt(daily, "sunset", 0));
                writer.WriteEndObject();
                writer.WriteStartObject("tomorrow");
                writer.WriteString("date", ReadStringAt(daily, "time", 1) ?? string.Empty);
                WriteNumber(writer, "maxC", ReadDoubleAt(daily, "temperature_2m_max", 1));
                WriteNumber(writer, "minC", ReadDoubleAt(daily, "temperature_2m_min", 1));
                WriteNumber(writer, "rainProbabilityPercent", ReadDoubleAt(daily, "precipitation_probability_max", 1));
                writer.WriteString("condition", Condition(tomorrowCode ?? -1));
                WriteClock(writer, "sunrise", ReadStringAt(daily, "sunrise", 1));
                WriteClock(writer, "sunset", ReadStringAt(daily, "sunset", 1));
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

    private async Task<Place?> GeocodeAsync(string location, CancellationToken cancellationToken)
    {
        string url = GeocodingAuthority + "?count=1&language=es&name=" + Uri.EscapeDataString(location);
        string json = await FetchAsync(url, cancellationToken).ConfigureAwait(false);
        using JsonDocument document = JsonDocument.Parse(json);
        if (!document.RootElement.TryGetProperty("results", out JsonElement results)
            || results.ValueKind != JsonValueKind.Array
            || results.GetArrayLength() == 0)
        {
            return null;
        }

        JsonElement first = results[0];
        double? latitude = ReadDouble(first, "latitude");
        double? longitude = ReadDouble(first, "longitude");
        if (latitude is null || longitude is null)
            return null;
        return new Place(
            ReadString(first, "name") ?? location,
            ReadString(first, "admin1"),
            ReadString(first, "country") ?? string.Empty,
            latitude.Value,
            longitude.Value,
            "named_place_geocoded");
    }

    private async Task<Place?> LocateByIpAsync(CancellationToken cancellationToken)
    {
        foreach (string authority in LocationByIpAuthorities)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string json;
            try
            {
                json = await FetchAsync(authority, cancellationToken).ConfigureAwait(false);
            }
            catch (HttpRequestException)
            {
                continue;
            }
            catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                continue;
            }

            try
            {
                using JsonDocument document = JsonDocument.Parse(json);
                JsonElement root = document.RootElement;
                if (root.ValueKind != JsonValueKind.Object)
                    continue;
                bool ok = (root.TryGetProperty("success", out JsonElement success) && success.ValueKind == JsonValueKind.True)
                    || (root.TryGetProperty("status", out JsonElement status) && status.ValueKind == JsonValueKind.String
                        && status.GetString() == "success");
                if (!ok)
                    continue;
                double? latitude = ReadDouble(root, "latitude") ?? ReadDouble(root, "lat");
                double? longitude = ReadDouble(root, "longitude") ?? ReadDouble(root, "lon");
                string? city = ReadString(root, "city");
                if (latitude is null || longitude is null || string.IsNullOrWhiteSpace(city))
                    continue;
                return new Place(
                    city,
                    ReadString(root, "region") ?? ReadString(root, "regionName"),
                    ReadString(root, "country") ?? string.Empty,
                    latitude.Value,
                    longitude.Value,
                    "public_ip_address");
            }
            catch (JsonException)
            {
                continue;
            }
        }

        return null;
    }

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

    private readonly record struct Place(
        string Name,
        string? Region,
        string Country,
        double Latitude,
        double Longitude,
        string Source);
}
