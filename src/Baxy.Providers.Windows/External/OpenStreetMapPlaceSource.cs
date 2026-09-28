using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// M51 (D32): «aparcamiento en Plaza del Polvorista», «gas stations in Buford»,
// «taquerías cerca» los contesta OpenStreetMap por su servicio Nominatim, abierto y sin
// clave. Dos peticiones como mucho: el lugar nombrado (o la ciudad de este PC, sólo su
// nombre) para saber su recuadro, y la clase de sitio buscada dentro de él.
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

    // La clase de sitio, como la entiende Nominatim (sus «special phrases» en inglés,
    // o el nombre cuando OpenStreetMap no tiene clase propia: «taqueria»).
    private static readonly Dictionary<string, string> Kinds = new(StringComparer.Ordinal)
    {
        ["aparcamiento"] = "parking", ["aparcamientos"] = "parking",
        ["estacionamiento"] = "parking", ["estacionamientos"] = "parking",
        ["parqueadero"] = "parking", ["parqueaderos"] = "parking", ["parking"] = "parking",
        ["gasolinera"] = "fuel", ["gasolineras"] = "fuel", ["bencinera"] = "fuel",
        ["bencineras"] = "fuel", ["fuel"] = "fuel",
        ["farmacia"] = "pharmacy", ["farmacias"] = "pharmacy", ["pharmacy"] = "pharmacy",
        ["pharmacies"] = "pharmacy", ["drugstore"] = "pharmacy", ["drugstores"] = "pharmacy",
        ["hospital"] = "hospital", ["hospitales"] = "hospital", ["hospitals"] = "hospital",
        ["clinica"] = "clinic", ["clinicas"] = "clinic", ["clinic"] = "clinic", ["clinics"] = "clinic",
        ["cajero"] = "atm", ["cajeros"] = "atm", ["atm"] = "atm", ["atms"] = "atm",
        ["hotel"] = "hotel", ["hoteles"] = "hotel", ["hotels"] = "hotel",
        ["hostal"] = "hostel", ["hostales"] = "hostel", ["hostel"] = "hostel", ["hostels"] = "hostel",
        ["supermercado"] = "supermarket", ["supermercados"] = "supermarket",
        ["supermarket"] = "supermarket", ["supermarkets"] = "supermarket",
        ["restaurante"] = "restaurant", ["restaurantes"] = "restaurant",
        ["restaurant"] = "restaurant", ["restaurants"] = "restaurant",
        ["taqueria"] = "taqueria", ["taquerias"] = "taqueria",
        ["cafeteria"] = "cafe", ["cafeterias"] = "cafe", ["cafe"] = "cafe", ["cafes"] = "cafe",
        ["panaderia"] = "bakery", ["panaderias"] = "bakery", ["bakery"] = "bakery", ["bakeries"] = "bakery",
        ["comisaria"] = "police", ["comisarias"] = "police",
        ["veterinaria"] = "veterinary", ["veterinarias"] = "veterinary", ["veterinario"] = "veterinary",
        ["museo"] = "museum", ["museos"] = "museum", ["museum"] = "museum", ["museums"] = "museum",
        ["biblioteca"] = "library", ["bibliotecas"] = "library", ["library"] = "library", ["libraries"] = "library",
        ["cine"] = "cinema", ["cines"] = "cinema", ["cinema"] = "cinema", ["cinemas"] = "cinema",
        ["dentista"] = "dentist", ["dentistas"] = "dentist", ["dentist"] = "dentist", ["dentists"] = "dentist",
    };

    private static readonly (string First, string Second, string Kind)[] PairedKinds =
    [
        ("gas", "station", "fuel"), ("gas", "stations", "fuel"),
        ("petrol", "station", "fuel"), ("petrol", "stations", "fuel"),
        ("car", "park", "parking"), ("car", "parks", "parking"),
    ];

    // «… en Plaza del Polvorista», «… in Buford», «… cerca de La Puntilla». Con «en» o
    // «in» el lugar tiene que ser un nombre (mayúscula), para no tomar «en el centro».
    private static readonly Regex PlacePhrase = new(
        @"\b(?<link>cerca\s+del?|near|around|alrededor\s+del?|en|in|at)\s+(?<place>[^?!.;]+)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(1));

    private static readonly HashSet<string> SelfPlaces = new(StringComparer.Ordinal)
    {
        "mi", "me", "aqui", "aca", "here", "you", "my", "casa", "home", "ti",
    };

    private static readonly HashSet<string> TrailingTime = new(StringComparer.Ordinal)
    {
        "hoy", "today", "ahora", "now", "tonight",
    };

    // Null cuando la consulta no pide una clase de sitio en un lugar.
    internal static PlaceAsk? Parse(string query, string? near)
    {
        string? kind = KindOf(WikipediaSearchSource.FoldedWords(query));
        if (kind is null) return null;
        string? place = near ?? PlaceOf(query);
        return string.IsNullOrWhiteSpace(place) ? null : new PlaceAsk(kind, place);
    }

    private static string? KindOf(string[] words)
    {
        for (int index = 0; index < words.Length; index++)
        {
            string next = index + 1 < words.Length ? words[index + 1] : string.Empty;
            foreach ((string first, string second, string paired) in PairedKinds)
            {
                if (words[index] == first && next == second) return paired;
            }
            if (Kinds.TryGetValue(words[index], out string? kind)) return kind;
        }
        return null;
    }

    private static string? PlaceOf(string query)
    {
        foreach (Match found in PlacePhrase.Matches(query))
        {
            string link = found.Groups["link"].Value.ToLowerInvariant();
            string place = found.Groups["place"].Value.Trim(' ', ',', ':');
            string[] words = place.Split(' ', StringSplitOptions.RemoveEmptyEntries).ToArray();
            while (words.Length > 0 && TrailingTime.Contains(WikipediaSearchSource.FoldedWords(words[^1]).FirstOrDefault() ?? string.Empty))
            {
                words = words[..^1];
            }
            // «la», «el», «the» delante del nombre no lo hacen minúscula.
            int start = words.Length > 1 && WikipediaSearchSource.FoldedWords(words[0]).FirstOrDefault()
                is "la" or "el" or "los" or "las" or "the" ? 1 : 0;
            if (words.Length <= start) continue;
            string first = words[start];
            if (SelfPlaces.Contains(WikipediaSearchSource.FoldedWords(first).FirstOrDefault() ?? string.Empty)) continue;
            bool named = words.Skip(start).Any(static word => char.IsUpper(word[0]));
            if (link is "en" or "in" or "at" && !named) continue;
            if (KindOf(WikipediaSearchSource.FoldedWords(first)) is not null) continue;
            // «calle Génova en Madrid» → «calle Génova, Madrid».
            return Regex.Replace(string.Join(' ', words), @"\s+(?:en|in)\s+", ", ",
                RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, TimeSpan.FromSeconds(1));
        }
        return null;
    }

    // Null cuando Nominatim no contestó; vacío cuando contestó sin nada.
    internal async Task<List<(string Title, string Url, string Snippet)>?> SearchAsync(
        PlaceAsk ask,
        int limit,
        string language,
        CancellationToken cancellationToken)
    {
        string? area = await ReadAsync(
            Endpoint + "?format=jsonv2&limit=1&q=" + Uri.EscapeDataString(ask.Place), cancellationToken)
            .ConfigureAwait(false);
        try
        {
            if (area is null) return null;
            if (AreaOf(area) is not { } box) return [];
            string? found = await ReadAsync(
                Endpoint + "?format=jsonv2&bounded=1&limit=10"
                + "&accept-language=" + language + "&viewbox=" + box.Viewbox
                + "&q=" + Uri.EscapeDataString(ask.Kind), cancellationToken).ConfigureAwait(false);
            return found is null ? null : Places(found, box.Latitude, box.Longitude).Take(Math.Clamp(limit, 1, 10)).ToList();
        }
        catch (JsonException)
        {
            return null;
        }
    }

    internal readonly record struct Area(string Viewbox, double Latitude, double Longitude);

    // El recuadro del lugar, con al menos ~1 km por lado y como mucho ~30 km, y su centro.
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
            for (int index = 0; index < 4; index++)
            {
                if (box[index].ValueKind != JsonValueKind.String
                    || !double.TryParse(box[index].GetString(), NumberStyles.Float, CultureInfo.InvariantCulture, out edges[index]))
                {
                    return null;
                }
            }
            (double south, double north, double west, double east) = (edges[0], edges[1], edges[2], edges[3]);
            double latitude = (south + north) / 2, longitude = (west + east) / 2;
            double halfHeight = Math.Clamp((north - south) / 2, 0.01, 0.15);
            double halfWidth = Math.Clamp((east - west) / 2, 0.01, 0.15);
            static string Coordinate(double value) => value.ToString("0.#####", CultureInfo.InvariantCulture);
            return new Area(
                Coordinate(longitude - halfWidth) + "," + Coordinate(latitude + halfHeight) + ","
                + Coordinate(longitude + halfWidth) + "," + Coordinate(latitude - halfHeight),
                latitude,
                longitude);
        }
        return null;
    }

    // Cada sitio: su nombre (o su clase), su dirección y su página en OpenStreetMap,
    // del más cercano al centro del lugar al más lejano (Nominatim los ordena por
    // importancia, no por distancia).
    internal static List<(string Title, string Url, string Snippet)> Places(string body, double latitude, double longitude)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        if (document.RootElement.ValueKind != JsonValueKind.Array) throw new JsonException("Not a Nominatim answer.");
        var places = new List<(double Distance, string Title, string Url, string Snippet)>();
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
            double distance = double.TryParse(Text(place, "lat"), NumberStyles.Float, CultureInfo.InvariantCulture, out double lat)
                && double.TryParse(Text(place, "lon"), NumberStyles.Float, CultureInfo.InvariantCulture, out double lon)
                    ? Math.Pow(lat - latitude, 2) + Math.Pow((lon - longitude) * Math.Cos(latitude * Math.PI / 180), 2)
                    : double.MaxValue;
            places.Add((
                distance,
                title,
                "https://www.openstreetmap.org/" + kind + "/" + osmId.ToString(CultureInfo.InvariantCulture),
                address.Length <= 300 ? address : address[..300]));
        }
        return places
            .OrderBy(static place => place.Distance)
            .Select(static place => (place.Title, place.Url, place.Snippet))
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
