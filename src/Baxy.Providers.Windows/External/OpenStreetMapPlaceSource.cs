using System.Globalization;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// M51 (D32): web.search con source=places lo contesta OpenStreetMap por su servicio Nominatim, abierto y sin clave.
// La clase de sitio (kind, en inglés: «pharmacy», «parking») y el lugar (place) los escribe el modelo. Dos peticiones
// como mucho: el lugar, para saber su recuadro (el primero que Nominatim ordena, por su importancia), y la clase de
// sitio buscada dentro de él.
// Política de uso de Nominatim (operations.osmfoundation.org/policies/nominatim):
// «an absolute maximum of 1 request per second», «Provide a valid HTTP Referer or
// User-Agent identifying the application», «Results must be cached on your side», sin
// consultas sistemáticas ni autocompletado. Por eso: el User-Agent del proyecto, una
// petición por segundo como mucho en todo el proceso, y lo leído se guarda un día.
internal sealed class OpenStreetMapPlaceSource(HttpClient http)
{
    internal const string Authority = "openstreetmap_nominatim";
    private const string Endpoint = "https://nominatim.openstreetmap.org/search";
    private static readonly TimeSpan Spacing = TimeSpan.FromMilliseconds(1_100);
    private static readonly TimeSpan CacheLifetime = TimeSpan.FromHours(24);
    private static readonly SemaphoreSlim Turn = new(1, 1);
    private static DateTimeOffset _lastRequest = DateTimeOffset.MinValue;

    private readonly HttpClient _http = http ?? throw new ArgumentNullException(nameof(http));
    private readonly Dictionary<string, (DateTimeOffset At, string Body)> _cache = new(StringComparer.Ordinal);

    internal readonly record struct PlaceAsk(string Kind, string Place);

    // Each site as Nominatim gives it: its name (or, without one, its OSM type), its whole address, its page on
    // OpenStreetMap and its distance in metres from the centre of the place (null when Nominatim gave no coordinates).
    internal readonly record struct Place(string Name, string Address, string Url, int? DistanceMeters);

    // «Resolved»: the address of the place Nominatim found for the place asked; null when it found none (and then no
    // site is asked).
    internal readonly record struct PlaceReading(string? Resolved, List<Place> Places);

    // Null when Nominatim did not answer.
    internal async Task<PlaceReading?> SearchNearAsync(
        PlaceAsk ask,
        int limit,
        string language,
        CancellationToken cancellationToken)
    {
        try
        {
            string? area = await ReadAsync(
                Endpoint + "?format=jsonv2&limit=1&accept-language=" + language + "&q=" + Uri.EscapeDataString(ask.Place),
                cancellationToken).ConfigureAwait(false);
            if (area is null) return null;
            if (AreaOf(area) is not { } box) return new PlaceReading(null, []);
            string? found = await ReadAsync(
                Endpoint + "?format=jsonv2&bounded=1&limit=10"
                + "&accept-language=" + language + "&viewbox=" + box.Viewbox
                + "&q=" + Uri.EscapeDataString(ask.Kind), cancellationToken).ConfigureAwait(false);
            if (found is null) return null;
            return new PlaceReading(
                box.Name,
                Places(found, box.Latitude, box.Longitude).Take(Math.Clamp(limit, 1, 10)).ToList());
        }
        catch (JsonException)
        {
            return null;
        }
    }

    internal readonly record struct Area(string Name, string Viewbox, double Latitude, double Longitude);

    private const double MetersPerDegree = 111_320;

    // Metres between two points a few kilometres apart (equirectangular: good to well under 1 %
    // at that scale).
    private static double Meters(double latitude, double longitude, double otherLatitude, double otherLongitude) =>
        Math.Sqrt(Math.Pow((otherLatitude - latitude) * MetersPerDegree, 2)
            + Math.Pow((otherLongitude - longitude) * MetersPerDegree * Math.Cos(latitude * Math.PI / 180), 2));

    // The first place Nominatim lists with a bounding box: its address, its box (at least ~1 km and at most ~30 km a
    // side) and its centre. Null when it lists none.
    internal static Area? AreaOf(string body)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        if (document.RootElement.ValueKind != JsonValueKind.Array) throw new JsonException("Not a Nominatim answer.");
        foreach (JsonElement place in document.RootElement.EnumerateArray())
        {
            if (!place.TryGetProperty("boundingbox", out JsonElement box)
                || box.ValueKind != JsonValueKind.Array || box.GetArrayLength() != 4)
            {
                continue;
            }
            double[] edges = new double[4];
            bool read = true;
            for (int index = 0; index < 4 && read; index++)
            {
                read = box[index].ValueKind == JsonValueKind.String
                    && double.TryParse(box[index].GetString(), NumberStyles.Float, CultureInfo.InvariantCulture, out edges[index]);
            }
            if (!read) continue;
            (double south, double north, double west, double east) = (edges[0], edges[1], edges[2], edges[3]);
            double latitude = (south + north) / 2, longitude = (west + east) / 2;
            double halfHeight = Math.Clamp((north - south) / 2, 0.01, 0.15);
            double halfWidth = Math.Clamp((east - west) / 2, 0.01, 0.15);
            static string Coordinate(double value) => value.ToString("0.#####", CultureInfo.InvariantCulture);
            return new Area(
                Text(place, "display_name"),
                Coordinate(longitude - halfWidth) + "," + Coordinate(latitude + halfHeight) + ","
                + Coordinate(longitude + halfWidth) + "," + Coordinate(latitude - halfHeight),
                latitude,
                longitude);
        }
        return null;
    }

    // The sites Nominatim found inside the box, from the nearest to the farthest from the place's centre (Nominatim
    // orders them by importance, not by distance).
    internal static List<Place> Places(string body, double latitude, double longitude)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        if (document.RootElement.ValueKind != JsonValueKind.Array) throw new JsonException("Not a Nominatim answer.");
        var places = new List<(double Distance, Place Place)>();
        foreach (JsonElement place in document.RootElement.EnumerateArray())
        {
            string kind = Text(place, "osm_type");
            if (kind is not ("node" or "way" or "relation")
                || !place.TryGetProperty("osm_id", out JsonElement id) || !id.TryGetInt64(out long osmId))
            {
                continue;
            }
            string address = Text(place, "display_name");
            string name = Text(place, "name");
            string title = name.Length > 0 ? name : Text(place, "type").Replace('_', ' ');
            if (title.Length == 0 || address.Length == 0) continue;
            double? distance = double.TryParse(Text(place, "lat"), NumberStyles.Float, CultureInfo.InvariantCulture, out double lat)
                && double.TryParse(Text(place, "lon"), NumberStyles.Float, CultureInfo.InvariantCulture, out double lon)
                    ? Meters(latitude, longitude, lat, lon)
                    : null;
            places.Add((distance ?? double.MaxValue, new Place(
                title,
                address.Length <= 300 ? address : address[..300],
                "https://www.openstreetmap.org/" + kind + "/" + osmId.ToString(CultureInfo.InvariantCulture),
                // Said to the nearest ten metres: the centre of a square is not more exact than that.
                distance is { } metres ? (int)(Math.Round(metres / 10) * 10) : null)));
        }
        return places
            .OrderBy(static place => place.Distance)
            .Select(static place => place.Place)
            .ToList();
    }

    private static string Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
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
            request.Headers.TryAddWithoutValidation("User-Agent", WikipediaSearchSource.UserAgent);
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
