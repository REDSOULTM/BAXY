using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real tanda 4 «convertir nueve de la mañana huso horario a madrid»: la zona
/// de un lugar sale de los datos de zonas de Windows o del geocodificador público;
/// un nombre compartido es el lugar más poblado y un país con varias zonas no
/// tiene una hora propia.
/// </summary>
[TestFixture]
public sealed class PlaceTimeZoneResolverTests
{
    [Test]
    public async Task AZoneIdentifierIsReadFromTheZoneDataWithoutAnyLookup()
    {
        var asked = new List<string>();
        var resolver = new OpenMeteoPlaceTimeZoneResolver((url, _) =>
        {
            asked.Add(url);
            return Task.FromResult("{}");
        });

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("America/New_York", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.Empty);
            Assert.That(reading.ErrorCode, Is.Null);
            Assert.That(reading.Place!.Zone.Id, Is.EqualTo("America/New_York"));
            Assert.That(reading.Place.Authority, Is.EqualTo("time_zone_id"));
        });
    }

    [Test]
    public async Task ASharedNameIsTheMostPopulatedPlaceWithOrWithoutItsArticle()
    {
        var asked = new List<string>();
        var resolver = new OpenMeteoPlaceTimeZoneResolver((url, _) =>
        {
            asked.Add(url);
            return Task.FromResult(url.Contains("name=la%20paz", StringComparison.Ordinal)
                ? """
                  {"results":[
                    {"name":"La Paz","latitude":24.14,"longitude":-110.31,"country":"México","timezone":"America/Mazatlan","population":250141},
                    {"name":"La Paz","latitude":-16.5,"longitude":-68.15,"country":"Bolivia","timezone":"America/La_Paz","population":812799}]}
                  """
                : """{"results":[{"name":"Paz","latitude":10.0,"longitude":-70.0,"country":"Venezuela","timezone":"America/Caracas","population":900}]}""");
        });

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("la paz", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Has.Count.EqualTo(2));
            Assert.That(asked, Has.Some.Contains("name=paz"));
            Assert.That(asked, Has.All.Contains("count=10"));
            Assert.That(reading.Place!.Name, Is.EqualTo("La Paz"));
            Assert.That(reading.Place.Country, Is.EqualTo("Bolivia"));
            Assert.That(reading.Place.Zone.Id, Is.EqualTo("America/La_Paz"));
            Assert.That(reading.Place.Authority, Is.EqualTo("named_place_geocoded"));
        });
    }

    [Test]
    public async Task ACountryWithSeveralZonesHasNoTimeOfItsOwn()
    {
        var resolver = new OpenMeteoPlaceTimeZoneResolver((_, _) => Task.FromResult(
            """{"results":[{"name":"Canadá","latitude":60.1,"longitude":-113.6,"country":"Canadá","population":37058856}]}"""));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("canada", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reading.Place, Is.Null);
            Assert.That(reading.ErrorCode, Is.EqualTo("time_place_zone_ambiguous"));
        });
    }

    [Test]
    public async Task AnUnknownPlaceAndASilentServiceAreNamedApart()
    {
        var unknown = new OpenMeteoPlaceTimeZoneResolver((_, _) => Task.FromResult("""{"generationtime_ms":0.4}"""));
        var offline = new OpenMeteoPlaceTimeZoneResolver((_, _) =>
            throw new System.Net.Http.HttpRequestException("offline"));

        PlaceTimeZoneReading notFound = await unknown.ResolveAsync("Bruno Mars", CancellationToken.None);
        PlaceTimeZoneReading unavailable = await offline.ResolveAsync("Madrid", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(notFound.ErrorCode, Is.EqualTo("time_place_not_found"));
            Assert.That(unavailable.ErrorCode, Is.EqualTo("time_place_service_unavailable"));
        });
    }
}
