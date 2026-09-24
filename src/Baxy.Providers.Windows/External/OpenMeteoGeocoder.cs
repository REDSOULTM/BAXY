using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Los lugares que el geocodificador público sin clave conoce por un nombre:
/// nombre, región, país, coordenadas, zona horaria IANA y población. Lo usan la
/// lectura del clima (el primero, por sus coordenadas) y la hora de otro lugar
/// (el más poblado, por su zona).
/// </summary>
internal static class OpenMeteoGeocoder
{
    private const string Authority = "https://geocoding-api.open-meteo.com/v1/search";

    internal static async Task<IReadOnlyList<GeocodedPlace>> SearchAsync(
        string name,
        int count,
        Func<string, CancellationToken, Task<string>> fetch,
        CancellationToken cancellationToken)
    {
        string url = Authority + "?count=" + count.ToString(System.Globalization.CultureInfo.InvariantCulture)
            + "&language=es&name=" + Uri.EscapeDataString(name);
        string json = await fetch(url, cancellationToken).ConfigureAwait(false);
        using JsonDocument document = JsonDocument.Parse(json);
        var places = new List<GeocodedPlace>();
        if (!document.RootElement.TryGetProperty("results", out JsonElement results)
            || results.ValueKind != JsonValueKind.Array)
        {
            return places;
        }

        foreach (JsonElement result in results.EnumerateArray())
        {
            double? latitude = ReadDouble(result, "latitude");
            double? longitude = ReadDouble(result, "longitude");
            if (latitude is null || longitude is null)
                continue;
            places.Add(new GeocodedPlace(
                ReadString(result, "name") ?? name,
                ReadString(result, "admin1"),
                ReadString(result, "country") ?? string.Empty,
                latitude.Value,
                longitude.Value,
                ReadString(result, "timezone"),
                ReadDouble(result, "population") ?? 0));
        }

        return places;
    }

    private static string? ReadString(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static double? ReadDouble(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            ? value.GetDouble()
            : null;
}

internal readonly record struct GeocodedPlace(
    string Name,
    string? Region,
    string Country,
    double Latitude,
    double Longitude,
    string? TimeZone,
    double Population);
