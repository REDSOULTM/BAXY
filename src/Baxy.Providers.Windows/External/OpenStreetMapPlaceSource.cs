using System.Globalization;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// M51 (D32): web.search con source=places lo contesta OpenStreetMap, abierto y sin clave, por el servicio Photon.
// La clase de sitio (kind, en inglés: «pharmacy», «parking») y el lugar (place) los escribe el modelo. Tres peticiones
// como mucho: el lugar, para saber su centro y su recuadro (el primero que Photon da); los sitios cuyo valor de
// OpenStreetMap es esa clase, los más cercanos al centro; y, si no hay ninguno (una clase que no es un valor de OSM,
// «gas station»), los sitios cuyo nombre la lleva dentro del recuadro.
// LIC2 (2026-11-08): BAXY se vende. La política de Nominatim (operations.osmfoundation.org/policies/nominatim, leída
// 2026-11-08) pone «an absolute maximum of 1 request per second» a «the sum of traffic by all your users», avisa a
// las «Commercial applications ... serving paying customers» de que el acceso se puede retirar, y exige poder cambiar
// de servicio «without requiring a software update». Photon (photon.komoot.io, Apache-2.0, los mismos datos de
// OpenStreetMap) sólo pide «please be fair - extensive usage will be throttled»; su /reverse con osm_tag da los sitios
// de una clase más cercanos a un punto (github.com/komoot/photon, docs/api-v1.md). Sin «lang»: la instancia pública no
// admite «es» (400) y el nombre local ya está en su idioma. Medido el 2026-11-08 con 12 pedidos (tmp\LIC2\lugares): 10
// de 12 con sitios en los dos servicios; «gas station» sólo por nombre; Photon no guarda los sitios sin nombre.
// Se mantiene lo que pedía Nominatim, que es lo justo con cualquier servicio gratis: el User-Agent del proyecto, una
// petición por segundo como mucho en todo el proceso, y lo leído se guarda un día. Los datos son ODbL: el recibo dice
// OpenStreetMap (answeredBy) y THIRD_PARTY_NOTICES lo acredita.
internal sealed class OpenStreetMapPlaceSource(HttpClient http)
{
    internal const string Authority = "openstreetmap_photon";
    private const string Endpoint = "https://photon.komoot.io/";
    private static readonly TimeSpan Spacing = TimeSpan.FromMilliseconds(1_100);
    private static readonly TimeSpan CacheLifetime = TimeSpan.FromHours(24);
    private static readonly SemaphoreSlim Turn = new(1, 1);
    private static DateTimeOffset _lastRequest = DateTimeOffset.MinValue;

    private readonly HttpClient _http = http ?? throw new ArgumentNullException(nameof(http));
    private readonly Dictionary<string, (DateTimeOffset At, string Body)> _cache = new(StringComparer.Ordinal);

    internal readonly record struct PlaceAsk(string Kind, string Place);

    // Each site as OpenStreetMap has it: its name (or, without one, its OSM value), its whole address, its page on
    // OpenStreetMap and its distance in metres from the centre of the place (null when the source gave no coordinates).
    // ARR2: and its category, the OpenStreetMap tag Photon gives it (osm_key and osm_value, docs/api-v1.md), written
    // key=value as the OSM wiki writes a tag («A tag consists of two parts, a key and a value, separated by an equals
    // sign», wiki.openstreetmap.org/wiki/Tags, read 2026-11-08): what the site is, whatever kind was asked.
    internal readonly record struct Place(string Name, string Address, string Url, int? DistanceMeters, string Category = "");

    // «Resolved»: the address of the place found for the place asked; null when none was found (and then no site is
    // asked).
    // SourceLimitReached (ronda final 11): the source gave its 10, the nearest ones; others may be as near.
    // ARR2: CategoryAsked is the OSM value the kind was asked as; ByName, that no site had it and the sites are those
    // whose name holds the kind.
    internal readonly record struct PlaceReading(
        string? Resolved,
        List<Place> Places,
        bool SourceLimitReached = false,
        string? CategoryAsked = null,
        bool ByName = false);

    // Null when the source did not answer.
    internal async Task<PlaceReading?> SearchNearAsync(
        PlaceAsk ask,
        int limit,
        CancellationToken cancellationToken)
    {
        try
        {
            string? area = await ReadAsync(
                Endpoint + "api/?limit=1&q=" + Uri.EscapeDataString(ask.Place), cancellationToken).ConfigureAwait(false);
            if (area is null) return null;
            if (AreaOf(area) is not { } box) return new PlaceReading(null, []);
            string value = string.Join('_', ask.Kind.ToLowerInvariant()
                .Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
            string? found = await ReadAsync(
                Endpoint + "reverse?lat=" + Coordinate(box.Latitude) + "&lon=" + Coordinate(box.Longitude)
                + "&radius=" + box.RadiusKilometers.ToString("0.#", CultureInfo.InvariantCulture)
                + "&limit=10&osm_tag=:" + Uri.EscapeDataString(value), cancellationToken).ConfigureAwait(false);
            if (found is null) return null;
            bool byName = Given(found) == 0;
            if (byName)
            {
                found = await ReadAsync(
                    Endpoint + "api/?limit=10&bbox=" + box.Bbox + "&q=" + Uri.EscapeDataString(ask.Kind),
                    cancellationToken).ConfigureAwait(false);
                if (found is null) return null;
            }
            List<Place> all = Places(found, box.Latitude, box.Longitude);
            // Ronda final 12 (regla 3): the source's cap is on what it gave, before the entries without a name or an
            // address are left out.
            return new PlaceReading(box.Name, all.Take(Math.Clamp(limit, 1, 10)).ToList(), Given(found) >= 10, value, byName);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // The place's address, its box («minLon,minLat,maxLon,maxLat», at least ~1 km and at most ~30 km a side), its
    // centre, and the radius in kilometres that reaches the box's corners from it.
    internal readonly record struct Area(string Name, string Bbox, double Latitude, double Longitude, double RadiusKilometers);

    private const double MetersPerDegree = 111_320;

    private static string Coordinate(double value) => value.ToString("0.#####", CultureInfo.InvariantCulture);

    // Metres between two points a few kilometres apart (equirectangular: good to well under 1 %
    // at that scale).
    private static double Meters(double latitude, double longitude, double otherLatitude, double otherLongitude) =>
        Math.Sqrt(Math.Pow((otherLatitude - latitude) * MetersPerDegree, 2)
            + Math.Pow((otherLongitude - longitude) * MetersPerDegree * Math.Cos(latitude * Math.PI / 180), 2));

    // The features of a Photon answer (a GeoJSON FeatureCollection).
    private static JsonElement.ArrayEnumerator Features(JsonDocument document) =>
        document.RootElement.ValueKind == JsonValueKind.Object
        && document.RootElement.TryGetProperty("features", out JsonElement features)
        && features.ValueKind == JsonValueKind.Array
            ? features.EnumerateArray()
            : throw new JsonException("Not a Photon answer.");

    private static int Given(string body)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        return Features(document).Count();
    }

    // The first place Photon lists: its address, its box (its extent, or its point when it has none) and its centre.
    // Null when it lists none.
    internal static Area? AreaOf(string body)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        foreach (JsonElement place in Features(document))
        {
            if (!place.TryGetProperty("properties", out JsonElement properties)) continue;
            double west, north, east, south;
            if (properties.TryGetProperty("extent", out JsonElement extent)
                && extent.ValueKind == JsonValueKind.Array && extent.GetArrayLength() == 4
                && extent.EnumerateArray().All(static edge => edge.ValueKind == JsonValueKind.Number))
            {
                // Photon's extent is [west, north, east, south].
                (west, north, east, south) = (extent[0].GetDouble(), extent[1].GetDouble(), extent[2].GetDouble(), extent[3].GetDouble());
            }
            else if (PointOf(place) is (double pointLatitude, double pointLongitude))
            {
                (west, north, east, south) = (pointLongitude, pointLatitude, pointLongitude, pointLatitude);
            }
            else
            {
                continue;
            }
            double latitude = (south + north) / 2, longitude = (west + east) / 2;
            double halfHeight = Math.Clamp(Math.Abs(north - south) / 2, 0.01, 0.15);
            double halfWidth = Math.Clamp(Math.Abs(east - west) / 2, 0.01, 0.15);
            double radius = Math.Max(1, Math.Sqrt(Math.Pow(halfHeight * MetersPerDegree, 2)
                + Math.Pow(halfWidth * MetersPerDegree * Math.Cos(latitude * Math.PI / 180), 2)) / 1000);
            return new Area(
                Address(properties),
                Coordinate(longitude - halfWidth) + "," + Coordinate(latitude - halfHeight) + ","
                + Coordinate(longitude + halfWidth) + "," + Coordinate(latitude + halfHeight),
                latitude,
                longitude,
                radius);
        }
        return null;
    }

    // The sites Photon found, from the nearest to the farthest from the place's centre, each once: Photon makes one
    // document per house number of an OSM object that has several (komoot/photon#884), all with its osm_id.
    internal static List<Place> Places(string body, double latitude, double longitude)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        var places = new List<(double Distance, Place Place)>();
        foreach (JsonElement place in Features(document))
        {
            if (!place.TryGetProperty("properties", out JsonElement properties)) continue;
            string kind = Text(properties, "osm_type") switch { "N" => "node", "W" => "way", "R" => "relation", _ => "" };
            if (kind.Length == 0
                || !properties.TryGetProperty("osm_id", out JsonElement id) || !id.TryGetInt64(out long osmId))
            {
                continue;
            }
            string address = Address(properties);
            string name = Text(properties, "name");
            string value = Text(properties, "osm_value");
            string title = name.Length > 0 ? name : value.Replace('_', ' ');
            if (title.Length == 0 || address.Length == 0) continue;
            double? distance = PointOf(place) is (double lat, double lon) ? Meters(latitude, longitude, lat, lon) : null;
            string key = Text(properties, "osm_key");
            places.Add((distance ?? double.MaxValue, new Place(
                title,
                address.Length <= 300 ? address : address[..300],
                "https://www.openstreetmap.org/" + kind + "/" + osmId.ToString(CultureInfo.InvariantCulture),
                // Said to the nearest ten metres: the centre of a square is not more exact than that.
                distance is { } metres ? (int)(Math.Round(metres / 10) * 10) : null,
                key.Length > 0 && value.Length > 0 ? key + "=" + value : value)));
        }
        return places
            .OrderBy(static place => place.Distance)
            .Select(static place => place.Place)
            .DistinctBy(static place => place.Url)
            .ToList();
    }

    // A feature's point: GeoJSON keeps [longitude, latitude].
    private static (double Latitude, double Longitude)? PointOf(JsonElement feature) =>
        feature.TryGetProperty("geometry", out JsonElement geometry)
        && geometry.ValueKind == JsonValueKind.Object
        && geometry.TryGetProperty("coordinates", out JsonElement point)
        && point.ValueKind == JsonValueKind.Array && point.GetArrayLength() >= 2
        && point[0].ValueKind == JsonValueKind.Number && point[1].ValueKind == JsonValueKind.Number
            ? (point[1].GetDouble(), point[0].GetDouble())
            : null;

    // A whole address from Photon's parts, from the site to the country, as Nominatim's display_name read: its name,
    // its street with its number, and the places that hold it, each said once.
    private static string Address(JsonElement properties)
    {
        string street = Text(properties, "street");
        string number = Text(properties, "housenumber");
        var parts = new List<string>();
        foreach (string part in new[]
        {
            Text(properties, "name"), street.Length > 0 && number.Length > 0 ? street + " " + number : street,
            Text(properties, "locality"), Text(properties, "district"), Text(properties, "city"), Text(properties, "state"),
            Text(properties, "country"),
        })
        {
            if (part.Length > 0 && !parts.Contains(part, StringComparer.OrdinalIgnoreCase)) parts.Add(part);
        }
        return string.Join(", ", parts);
    }

    private static string Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? string.Empty
            : string.Empty;

    private async Task<string?> ReadAsync(string url, CancellationToken cancellationToken)
    {
        lock (_cache)
        {
            if (_cache.TryGetValue(url, out (DateTimeOffset At, string Body) kept)
                && DateTimeOffset.UtcNow - kept.At < CacheLifetime)
            {
                return kept.Body;
            }
        }
        await Turn.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            TimeSpan wait = _lastRequest + Spacing - DateTimeOffset.UtcNow;
            if (wait > TimeSpan.Zero) await Task.Delay(wait, cancellationToken).ConfigureAwait(false);
            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.TryAddWithoutValidation("User-Agent", ProductIdentity.UserAgent);
            try
            {
                using HttpResponseMessage response = await _http
                    .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                    .ConfigureAwait(false);
                if (!response.IsSuccessStatusCode) return null;
                string body = await WebBrowserAdapter.ReadBoundedTextAsync(response, 1_000_000, cancellationToken)
                    .ConfigureAwait(false);
                using (JsonDocument.Parse(body))
                {
                    // Sólo se guarda lo que es JSON; una página de error no.
                }
                lock (_cache)
                {
                    if (_cache.Count >= 256) _cache.Clear();
                    _cache[url] = (DateTimeOffset.UtcNow, body);
                }
                return body;
            }
            catch (HttpRequestException)
            {
                return null;
            }
            catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                return null;
            }
            catch (JsonException)
            {
                return null;
            }
            finally
            {
                _lastRequest = DateTimeOffset.UtcNow;
            }
        }
        finally
        {
            Turn.Release();
        }
    }
}
