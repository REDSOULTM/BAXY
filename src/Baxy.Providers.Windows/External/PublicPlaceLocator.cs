using System.Net.Http;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Un lugar leído de un servicio público: su nombre, su región, su país, sus
/// coordenadas y cómo se supo (nombrado y geocodificado, o por la dirección
/// pública de este PC).
/// </summary>
internal readonly record struct PublicPlace(
    string Name,
    string? Region,
    string Country,
    double Latitude,
    double Longitude,
    string Source,
    string? CountryCode = null);

/// <summary>
/// Uso real tanda 4c (2026-09-24): el clima ya sabía dónde está este PC y la
/// búsqueda «cerca de mí» no. Este lector es el único que lo averigua: pregunta
/// a dos servicios públicos por la dirección pública de este PC (el segundo
/// contesta cuando el primero no) con la petición vacía; ninguno recibe nada de
/// la persona, y lo que sale de aquí hacia otros servicios es sólo la ciudad o
/// las coordenadas que el propio servicio dedujo de esa dirección.
/// </summary>
internal sealed class PublicPlaceLocator
{
    // Over https only (BAXY Renew audit 2026-10-15: the fallback ip-api.com answered in plain http, so where the PC
    // is travelled unencrypted).
    private static readonly string[] LocationByIpAuthorities =
    [
        "https://ipwho.is/",
    ];

    private readonly Func<string, CancellationToken, Task<string>> _fetch;

    internal PublicPlaceLocator(Func<string, CancellationToken, Task<string>> fetch) =>
        _fetch = fetch ?? throw new ArgumentNullException(nameof(fetch));

    internal async Task<PublicPlace?> LocateAsync(CancellationToken cancellationToken)
    {
        foreach (string authority in LocationByIpAuthorities)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string json;
            try
            {
                json = await _fetch(authority, cancellationToken).ConfigureAwait(false);
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
                if (!root.TryGetProperty("success", out JsonElement success) || success.ValueKind != JsonValueKind.True)
                    continue;
                double? latitude = ReadDouble(root, "latitude");
                double? longitude = ReadDouble(root, "longitude");
                string? city = ReadString(root, "city");
                if (latitude is null || longitude is null || string.IsNullOrWhiteSpace(city))
                    continue;
                return new PublicPlace(
                    city,
                    ReadString(root, "region"),
                    ReadString(root, "country") ?? string.Empty,
                    latitude.Value,
                    longitude.Value,
                    "public_ip_address",
                    // M54: the country the service deduced, so a search near this PC stays in its country
                    // (v3b-final F-p01-t2: «Curico» alone geocoded to Curico, Indiana).
                    ReadString(root, "country_code"));
            }
            catch (JsonException)
            {
                continue;
            }
        }

        return null;
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
