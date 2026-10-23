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
    string Source);

/// <summary>
/// Uso real tanda 4c (2026-09-24): el clima ya sabía dónde está este PC y la
/// búsqueda «cerca de mí» no. Este lector es el único que lo averigua: pregunta
/// a un servicio público (ipwho.is, por https) por la dirección pública de este
/// PC con la petición vacía; no recibe nada de la persona, y lo que sale de aquí
/// hacia otros servicios es sólo la ciudad o las coordenadas que el propio
/// servicio dedujo de esa dirección.
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

    // Where this PC is, or null; Unreachable when no service answered at all (no network), which is not a place unknown.
    // Renew al máximo (auditoría de flujos): without network the weather here asked the person where they were.
    internal readonly record struct Lookup(PublicPlace? Place, bool Unreachable);

    internal async Task<Lookup> LocateAsync(CancellationToken cancellationToken)
    {
        bool answered = false;
        foreach (string authority in LocationByIpAuthorities)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string json;
            try
            {
                json = await _fetch(authority, cancellationToken).ConfigureAwait(false);
                answered = true;
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
                return new Lookup(new PublicPlace(
                    city,
                    ReadString(root, "region"),
                    ReadString(root, "country") ?? string.Empty,
                    latitude.Value,
                    longitude.Value,
                    "public_ip_address"), false);
            }
            catch (JsonException)
            {
                continue;
            }
        }

        return new Lookup(null, !answered);
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
