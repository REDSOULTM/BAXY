using System.Text.Json;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// La zona horaria de un lugar o de una zona nombrada. Uso real tanda 4
/// «convertir nueve de la mañana huso horario a madrid», tanda 2 «what time is
/// it right now in paris»: la hora de otro lugar es el reloj de este PC más el
/// desfase de la zona de ese lugar ahora, no páginas de relojes. La zona sale de
/// los datos de zonas de Windows (identificadores IANA o de Windows); un lugar se
/// traduce a su zona con los lugares de GeoNames que BAXY lleva dentro (WEB1,
/// 2026-11-07: antes, el geocodificador gratuito de Open-Meteo, de uso sólo no
/// comercial), los mismos que lee el clima: el nombre no sale del PC.
/// </summary>
public interface IPlaceTimeZoneResolver
{
    ValueTask<PlaceTimeZoneReading> ResolveAsync(string place, CancellationToken cancellationToken);
}

public sealed record PlaceTimeZone(string Name, string Country, TimeZoneInfo Zone, string Authority);

/// <summary>El lugar resuelto, o la causa por la que no se resolvió y, si los hay, los lugares que se hallaron en su
/// lugar (como el clima los da: requested, candidateCount, candidates).</summary>
public sealed record PlaceTimeZoneReading(PlaceTimeZone? Place, string? ErrorCode, JsonElement? Candidates = null);

public sealed class GeoNamesPlaceTimeZoneResolver : IPlaceTimeZoneResolver
{
    private readonly Func<GeoNamesGazetteer> _places;

    public GeoNamesPlaceTimeZoneResolver()
        : this(static () => GeoNamesGazetteer.Shared)
    {
    }

    // Las pruebas entregan sus propios lugares.
    internal GeoNamesPlaceTimeZoneResolver(Func<GeoNamesGazetteer> places) => _places = places;

    public ValueTask<PlaceTimeZoneReading> ResolveAsync(string place, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string named = place.Trim();
        if (TimeZoneInfo.TryFindSystemTimeZoneById(named, out TimeZoneInfo? zone))
        {
            // «America/New_York», «Eastern Standard Time», «UTC»: a zone the mind
            // named by its identifier needs no lookup.
            return ValueTask.FromResult(
                new PlaceTimeZoneReading(new PlaceTimeZone(named, string.Empty, zone, "time_zone_id"), null));
        }

        // The place is asked as the model wrote it (BAXY Renew audit 2026-10-15: no word list strips «la», «el»), and
        // chosen as the weather chooses it (GeoNamesGazetteer.Choose): «Washington» is the capital, not the state; of
        // «París» of France and of Texas, France, far larger; «Mérida, Venezuela» is Venezuela's. WEB2 (2026-11-07):
        // namesakes of comparable size («Georgia», the state and the country) are not one of them taken as the place,
        // nor is a place whose name only begins so: they go back as candidates, so the person is asked.
        GeoNamesGazetteer places;
        try
        {
            places = _places();
        }
        catch (InvalidOperationException)
        {
            return ValueTask.FromResult(new PlaceTimeZoneReading(null, "time_place_service_unavailable"));
        }

        GazetteerChoice choice = places.Choose(named);
        if (choice.Place is not { } found)
        {
            return ValueTask.FromResult(new PlaceTimeZoneReading(
                null,
                choice.Ambiguous ? "time_place_ambiguous" : "time_place_not_found",
                places.CandidatesJson(named, choice.Candidates)));
        }
        // «Canadá», «Estados Unidos»: a country with several zones has none of
        // its own, and one of them is not the time of the whole country.
        if (string.IsNullOrWhiteSpace(found.TimeZone)
            || !TimeZoneInfo.TryFindSystemTimeZoneById(found.TimeZone, out TimeZoneInfo? placeZone))
        {
            return ValueTask.FromResult(new PlaceTimeZoneReading(null, "time_place_zone_ambiguous"));
        }

        return ValueTask.FromResult(new PlaceTimeZoneReading(
            new PlaceTimeZone(found.NameEs, places.Country(found)?.NameEs ?? string.Empty, placeZone, "named_place_geocoded"),
            null));
    }
}
