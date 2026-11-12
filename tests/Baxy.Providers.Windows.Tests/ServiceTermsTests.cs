using System.Net;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// WEB1 (2026-11-07, LIC1 R3): BAXY se distribuye y se vende, así que no pregunta a un servicio cuyo uso gratuito es
/// sólo no comercial. Open-Meteo: «You may only use the free API services for non-commercial purposes», y un «commercial
/// product» cuenta como comercial (https://open-meteo.com/en/terms, leído 2026-11-07); eso alcanza a su geocodificador.
/// Estas pruebas usan los lugares de GeoNames que este build lleva dentro.
/// </summary>
[TestFixture]
public sealed class ServiceTermsTests
{
    // api.met.no: datos NLOD 2.0 y CC BY 4.0, con crédito a MET Norway (https://api.met.no/doc/License); ipwho.is:
    // «Commercial use allowed» (LIC1).
    private static readonly string[] CommercialUseAllowed = ["api.met.no", "ipwho.is"];

    private sealed class Recorder : HttpMessageHandler
    {
        internal List<Uri> Asked { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Asked.Add(request.RequestUri!);
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.ServiceUnavailable));
        }
    }

    [Test]
    public async Task TheWeatherAsksOnlyServicesWhoseTermsAllowASoldProduct()
    {
        var recorder = new Recorder();
        using var adapter = new MetNorwayWeatherAdapter(recorder, static () => GeoNamesGazetteer.Shared, static () => DateTimeOffset.UtcNow);

        await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "Valparaíso" }), CancellationToken.None);
        await adapter.InvokeAsync("weather.current", JsonSerializer.SerializeToElement(new { }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(recorder.Asked.Select(static uri => uri.Host).Distinct(), Is.SubsetOf(CommercialUseAllowed));
            // Valparaíso of Chile, found on this PC: its coordinates go to the forecast, its name nowhere.
            Assert.That(recorder.Asked.Select(static uri => uri.AbsoluteUri), Has.Some.Contains("lat=-33.0360&lon=-71.6296"));
            Assert.That(recorder.Asked.Select(static uri => Uri.UnescapeDataString(uri.AbsoluteUri)),
                Has.None.Contains("Valpara"));
        });
    }

    [Test]
    public async Task ThePlaceOfAnotherTimeIsFoundWithoutAskingAnyService()
    {
        var resolver = new GeoNamesPlaceTimeZoneResolver();

        PlaceTimeZoneReading reading = await resolver.ResolveAsync("Valparaíso", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reading.Place?.Zone.Id, Is.EqualTo("America/Santiago"));
            Assert.That(reading.Place?.Country, Is.EqualTo("Chile"));
        });
    }

    // The names the person says, in Spanish or in English, are the places of BAXY's copy of GeoNames.
    [TestCase("Nueva York", "Nueva York", "America/New_York")]
    [TestCase("New York", "Nueva York", "America/New_York")]
    [TestCase("Londres", "Londres", "Europe/London")]
    [TestCase("tokio", "Tokio", "Asia/Tokyo")]
    [TestCase("Santiago", "Santiago de Chile", "America/Santiago")]
    [TestCase("Carolina del Norte", "Carolina del Norte", "America/New_York")]
    public void TheCopyOfGeoNamesNamesPlacesInSpanishAndEnglish(string asked, string spanish, string zone)
    {
        GeoNamesGazetteer places = GeoNamesGazetteer.Shared;

        GazetteerPlace found = places.Named(asked).MaxBy(static place => place.Population)!;

        Assert.Multiple(() =>
        {
            Assert.That(found.NameEs, Is.EqualTo(spanish));
            Assert.That(found.TimeZone, Is.EqualTo(zone));
        });
    }

    // WEB2 (held-out w2-14, w2-15, w2-56): a comuna, which GeoNames gives as a division without population and
    // cities1000 leaves out, was weather_place_not_found and time_place_not_found.
    [TestCase("Las Condes", "America/Santiago")]
    [TestCase("Lo Barnechea", "America/Santiago")]
    [TestCase("Isla de Pascua", "Pacific/Easter")]
    public async Task AComunaIsAPlaceOfTheCopy(string asked, string zone)
    {
        GazetteerChoice choice = GeoNamesGazetteer.Shared.Choose(asked);
        PlaceTimeZoneReading reading = await new GeoNamesPlaceTimeZoneResolver().ResolveAsync(asked, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(choice.Place?.NameEs, Is.EqualTo(asked));
            Assert.That(choice.Place is { } place ? GeoNamesGazetteer.Shared.Country(place)?.NameEs : null, Is.EqualTo("Chile"));
            Assert.That(reading.Place?.Zone.Id, Is.EqualTo(zone));
        });
    }
}
