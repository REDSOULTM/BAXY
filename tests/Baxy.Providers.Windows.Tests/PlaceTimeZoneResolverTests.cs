using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real tanda 2 «what time is it right now in paris»: la zona de un lugar
/// nombrado sale de un identificador de zona o de los lugares de GeoNames que
/// BAXY lleva dentro (WEB1: antes, el geocodificador de Open-Meteo); su ausencia
/// se nombra.
/// </summary>
[TestFixture]
public sealed class PlaceTimeZoneResolverTests
{
    private static Func<GeoNamesGazetteer> Places(params string[] rows) =>
        () => new GeoNamesGazetteer(new StringReader(string.Join('\n', rows)));

    private static readonly string[] World =
    [
        "C\tMX\t3996063", "C\tBO\t3923057", "C\tVE\t3625428", "C\tCA\t6251999",
        "P\t3996063\tPCLI\t23.0000\t-102.0000\tMX\t\t\t131946900\t\tMéxico\tMexico\t\t",
        "P\t3923057\tPCLI\t-17.0000\t-65.0000\tBO\t\t\t11673029\t\tBolivia\tBolivia\t\t",
        "P\t3625428\tPCLI\t8.0000\t-66.0000\tVE\t\t\t28515829\tAmerica/Caracas\tVenezuela\tVenezuela\t\t",
        "P\t6251999\tPCLI\t60.1087\t-113.6426\tCA\t\t\t41651653\t\tCanadá\tCanada\t\t",
        "P\t4000900\tPPLA\t24.1422\t-110.3108\tMX\t\t\t250141\tAmerica/Mazatlan\tLa Paz\tLa Paz\t\t",
        "P\t3911925\tPPLG\t-16.5000\t-68.1500\tBO\t\t\t812799\tAmerica/La_Paz\tLa Paz\tLa Paz\t\t",
        "P\t3630000\tPPL\t10.0000\t-70.0000\tVE\t\t\t900\tAmerica/Caracas\tPaz\tPaz\t\t",
        "C\tUS\t6252001",
        "P\t6252001\tPCLI\t39.7600\t-98.5000\tUS\t\t\t327167434\t\tEstados Unidos\tUnited States\t\t",
        "P\t5815135\tADM1\t47.5001\t-120.5015\tUS\t5815135\t\t7958180\tAmerica/Los_Angeles\tWashington\tWashington\t\t",
        "P\t4140963\tPPLC\t38.8951\t-77.0364\tUS\t4138106\t\t689545\tAmerica/New_York\tWashington\tWashington D.C.\t\t",
        "C\tGE\t614540",
        "P\t614540\tPCLI\t42.0000\t43.5000\tGE\t\t\t3731000\tAsia/Tbilisi\tGeorgia\tGeorgia\t\t",
        "P\t4197000\tADM1\t32.7504\t-83.5002\tUS\t4197000\t\t10711908\tAmerica/New_York\tGeorgia\tGeorgia\t\t",
        "C\tCL\t3895114",
        "P\t3895114\tPCLI\t-30.0000\t-71.0000\tCL\t\t\t19116209\t\tChile\tChile\t\t",
        "P\t8261466\tADM3\t-27.1288\t-109.3600\tCL\t3868621\t4030752\t7750\tPacific/Easter\tIsla de Pascua\tIsla de Pascua\t\t",
        "C\tSV\t3585968",
        "P\t3585968\tPCLI\t13.8333\t-88.9167\tSV\t\t\t6420744\tAmerica/El_Salvador\tEl Salvador\tEl Salvador\t\t",
        "P\t8261410\tADM3\t-33.4486\t-70.5358\tCL\t3873544\t3871332\t0\tAmerica/Santiago\tLa Reina\tLa Reina\t\t",
        "P\t12031333\tADM3\t14.1925\t-89.1645\tSV\t3587090\t12916950\t7583\tAmerica/El_Salvador\tLa Reina\tLa Reina\t\t",
    ];

    [Test]
    public async Task AZoneIdentifierIsReadFromTheZoneDataWithoutAnyLookup()
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver(
            static () => throw new AssertionException("the places are not read for a zone's identifier"));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("America/New_York", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reading.ErrorCode, Is.Null);
            Assert.That(reading.Place!.Zone.Id, Is.EqualTo("America/New_York"));
            Assert.That(reading.Place.Authority, Is.EqualTo("time_zone_id"));
        });
    }

    [Test]
    // The place is asked as the model wrote it (no word list strips «la»), and the region or country said keeps its
    // place of the name. WEB2 (held-out w2-61 «¿qué hora es en Mérida, Venezuela?»): read as a name, it was not found.
    public async Task APlaceIsAskedAsWrittenAndThePlaceOfTheCountrySaidIsRead()
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver(Places(World));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("la paz, Bolivia", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reading.Place!.Name, Is.EqualTo("La Paz"));
            Assert.That(reading.Place.Country, Is.EqualTo("Bolivia"));
            Assert.That(reading.Place.Zone.Id, Is.EqualTo("America/La_Paz"));
            Assert.That(reading.Place.Authority, Is.EqualTo("named_place_geocoded"));
        });
    }

    // WEB2 (2026-11-07, held-out «¿qué hora es en Georgia?»): namesakes of comparable size, the state and the country,
    // were the most populated said as the place; as the weather, they go back as candidates, so the person is asked.
    [TestCase("Georgia", "Estados Unidos", "Georgia")]
    [TestCase("la paz", "Bolivia", "México")]
    // A division GeoNames gives no population is of a size unknown, a namesake of any.
    [TestCase("La Reina", "El Salvador", "Chile")]
    public async Task NamesakesOfComparableSizeAreCandidatesNotThePlace(string asked, string first, string second)
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver(Places(World));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync(asked, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reading.Place, Is.Null);
            Assert.That(reading.ErrorCode, Is.EqualTo("time_place_ambiguous"));
            Assert.That(reading.Candidates?.GetProperty("requested").GetString(), Is.EqualTo(asked));
            Assert.That(
                reading.Candidates?.GetProperty("candidates").EnumerateArray().Select(static c => c.GetProperty("country").GetString()),
                Is.EqualTo(new[] { first, second }));
        });
    }

    // WEB2 (held-out w2-56 «¿qué hora es en Isla de Pascua?»): a comuna has the time of its own zone.
    [Test]
    public async Task ADivisionNamedAsATownHasTheTimeOfItsZone()
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver(Places(World));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("Isla de Pascua", CancellationToken.None);

        Assert.That(reading.Place?.Zone.Id, Is.EqualTo("Pacific/Easter"));
    }

    // The places a name means are the weather's: «Washington» is the capital, not the larger state of that name.
    [Test]
    public async Task ACapitalKeepsTheNameOfAStateOfItsCountry()
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver(Places(World));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("Washington", CancellationToken.None);

        Assert.That(reading.Place?.Zone.Id, Is.EqualTo("America/New_York"));
    }

    // WEB2: a place whose name only begins so was given as the place, with its time; it is a candidate, not the place.
    [Test]
    public async Task WithNoPlaceNamedSoThePlacesWhoseNameBeginsSoAreCandidates()
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver(Places(World));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("La", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reading.Place, Is.Null);
            Assert.That(reading.ErrorCode, Is.EqualTo("time_place_not_found"));
            Assert.That(reading.Candidates?.GetProperty("candidateCount").GetInt32(), Is.EqualTo(4), "La Paz and La Reina, twice");
        });
    }

    [Test]
    public async Task ACountryWithSeveralZonesHasNoTimeOfItsOwn()
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver(Places(World));

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("canada", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reading.Place, Is.Null);
            Assert.That(reading.ErrorCode, Is.EqualTo("time_place_zone_ambiguous"));
        });
    }

    [Test]
    public async Task AnUnknownPlaceAndPlacesThatCannotBeReadAreNamedApart()
    {
        var known = new GeoNamesPlaceTimeZoneResolver(Places(World));
        var unreadable = new GeoNamesPlaceTimeZoneResolver(
            static () => throw new InvalidOperationException("The place names are not in this build."));

        PlaceTimeZoneReading notFound = await known.ResolveAsync("Bruno Mars", CancellationToken.None);
        PlaceTimeZoneReading unavailable = await unreadable.ResolveAsync("Madrid", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(notFound.ErrorCode, Is.EqualTo("time_place_not_found"));
            Assert.That(unavailable.ErrorCode, Is.EqualTo("time_place_service_unavailable"));
        });
    }
}
