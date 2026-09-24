using System.Net.Http;
using System.Text.Json;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// La zona horaria de un lugar o de una zona nombrada. Uso real tanda 4
/// «convertir nueve de la mañana huso horario a madrid», tanda 2 «what time is
/// it right now in paris»: la hora de otro lugar es el reloj de este PC más el
/// desfase de la zona de ese lugar ahora, no páginas de relojes. La zona sale de
/// los datos de zonas de Windows (identificadores IANA o de Windows); un lugar se
/// traduce a su zona con el mismo geocodificador público que usa el clima.
/// </summary>
public interface IPlaceTimeZoneResolver
{
    ValueTask<PlaceTimeZoneReading> ResolveAsync(string place, CancellationToken cancellationToken);
}

public sealed record PlaceTimeZone(string Name, string Country, TimeZoneInfo Zone, string Authority);

/// <summary>El lugar resuelto, o la causa por la que no se resolvió.</summary>
public sealed record PlaceTimeZoneReading(PlaceTimeZone? Place, string? ErrorCode);

public sealed class OpenMeteoPlaceTimeZoneResolver : IPlaceTimeZoneResolver, IDisposable
{
    private readonly HttpClient _http;
    private readonly Func<string, CancellationToken, Task<string>>? _fetch;

    public OpenMeteoPlaceTimeZoneResolver()
    {
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(6) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY/1.0 time-zone-read");
    }

    // Las pruebas entregan la respuesta del geocodificador sin red.
    internal OpenMeteoPlaceTimeZoneResolver(Func<string, CancellationToken, Task<string>> fetch)
    {
        _http = new HttpClient();
        _fetch = fetch;
    }

    public async ValueTask<PlaceTimeZoneReading> ResolveAsync(string place, CancellationToken cancellationToken)
    {
        string named = place.Trim();
        if (TimeZoneInfo.TryFindSystemTimeZoneById(named, out TimeZoneInfo? zone))
        {
            // «America/New_York», «Eastern Standard Time», «UTC»: a zone the mind
            // named by its identifier needs no lookup.
            return new PlaceTimeZoneReading(new PlaceTimeZone(named, string.Empty, zone, "time_zone_id"), null);
        }

        // «La Paz», «la India»: a Spanish article may belong to the name or not, and
        // a name is shared by many places («La Paz» of Bolivia and of Mexico). Both
        // spellings are asked and the most populated place is the one meant.
        string[] names = ArticleLess(named) is { } bare ? [named, bare] : [named];
        var candidates = new List<GeocodedPlace>();
        try
        {
            IReadOnlyList<GeocodedPlace>[] found = await Task.WhenAll(names.Select(
                name => OpenMeteoGeocoder.SearchAsync(name, 10, FetchAsync, cancellationToken))).ConfigureAwait(false);
            foreach (IReadOnlyList<GeocodedPlace> places in found)
                candidates.AddRange(places);
        }
        catch (Exception exception) when (
            exception is HttpRequestException or JsonException or InvalidOperationException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return new PlaceTimeZoneReading(null, "time_place_service_unavailable");
        }

        if (candidates.Count == 0)
            return new PlaceTimeZoneReading(null, "time_place_not_found");
        GeocodedPlace geocoded = candidates.MaxBy(place => place.Population);
        // «Canadá», «Estados Unidos»: a country with several zones has none of
        // its own, and one of them is not the time of the whole country.
        if (string.IsNullOrWhiteSpace(geocoded.TimeZone)
            || !TimeZoneInfo.TryFindSystemTimeZoneById(geocoded.TimeZone, out TimeZoneInfo? placeZone))
        {
            return new PlaceTimeZoneReading(null, "time_place_zone_ambiguous");
        }

        return new PlaceTimeZoneReading(
            new PlaceTimeZone(geocoded.Name, geocoded.Country, placeZone, "named_place_geocoded"),
            null);
    }

    private static string? ArticleLess(string name)
    {
        foreach (string article in new[] { "la ", "el ", "los ", "las " })
        {
            if (name.StartsWith(article, StringComparison.OrdinalIgnoreCase) && name.Length > article.Length + 1)
                return name[article.Length..].Trim();
        }
        return null;
    }

    private Task<string> FetchAsync(string url, CancellationToken cancellationToken) =>
        _fetch is not null
            ? _fetch(url, cancellationToken)
            : _http.GetStringAsync(url, cancellationToken);

    public void Dispose() => _http.Dispose();
}
