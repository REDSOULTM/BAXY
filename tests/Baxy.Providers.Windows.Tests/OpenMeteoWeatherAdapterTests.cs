using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo W): la lectura del clima
/// devuelve lo que el servicio público dijo del lugar nombrado o de la
/// ubicación de este PC, y nombra sus ausencias sin inventar un pronóstico.
/// </summary>
[TestFixture]
public sealed class OpenMeteoWeatherAdapterTests
{
    private const string Geocoded =
        """{"results":[{"name":"Buenos Aires","latitude":-34.61315,"longitude":-58.37723,"country":"Argentina","admin1":"Ciudad Autónoma de Buenos Aires"}]}""";

    private const string Located =
        """{"success":true,"country":"Chile","region":"Region de Curico","city":"Curico","latitude":-34.9828,"longitude":-71.2394}""";

    private const string Forecast =
        """
        {"timezone":"America/Argentina/Buenos_Aires",
         "current":{"time":"2026-09-20T19:15","temperature_2m":18.8,"apparent_temperature":20.2,"relative_humidity_2m":92,"weather_code":3,"wind_speed_10m":8.0,"precipitation":0.0},
         "daily":{"time":["2026-09-20","2026-09-21"],"temperature_2m_max":[22.1,21.0],"temperature_2m_min":[14.0,12.5],"precipitation_probability_max":[10,65],"weather_code":[3,61],
                  "sunrise":["2026-09-20T07:05","2026-09-21T07:04"],"sunset":["2026-09-20T19:02","2026-09-21T19:03"]}}
        """;

    [Test]
    public async Task ANamedPlaceIsGeocodedAndItsForecastIsReadVerbatim()
    {
        var asked = new List<string>();
        var adapter = new OpenMeteoWeatherAdapter((url, _) =>
        {
            asked.Add(url);
            return Task.FromResult(url.Contains("geocoding", StringComparison.Ordinal) ? Geocoded : Forecast);
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current",
            JsonSerializer.SerializeToElement(new { location = "buenos aires" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(asked[0], Does.Contain("name=buenos%20aires"));
            Assert.That(asked[1], Does.Contain("latitude=-34.6131").And.Contain("forecast_days=2")
                .And.Contain("sunrise,sunset"));
        });
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("location").GetString(), Is.EqualTo("Buenos Aires"));
            Assert.That(result.GetProperty("country").GetString(), Is.EqualTo("Argentina"));
            Assert.That(result.GetProperty("locatedBy").GetString(), Is.EqualTo("named_place_geocoded"));
            Assert.That(result.GetProperty("temperatureC").GetDouble(), Is.EqualTo(18.8));
            Assert.That(result.GetProperty("apparentC").GetDouble(), Is.EqualTo(20.2));
            Assert.That(result.GetProperty("condition").GetString(), Is.EqualTo("nublado"));
            Assert.That(result.GetProperty("windKmh").GetDouble(), Is.EqualTo(8.0));
            Assert.That(result.GetProperty("humidityPercent").GetDouble(), Is.EqualTo(92));
            Assert.That(result.GetProperty("today").GetProperty("rainProbabilityPercent").GetDouble(), Is.EqualTo(10));
            Assert.That(result.GetProperty("tomorrow").GetProperty("date").GetString(), Is.EqualTo("2026-09-21"));
            Assert.That(result.GetProperty("tomorrow").GetProperty("rainProbabilityPercent").GetDouble(), Is.EqualTo(65));
            Assert.That(result.GetProperty("tomorrow").GetProperty("condition").GetString(), Is.EqualTo("lluvia débil"));
            // Uso real tanda 2: the sun times are the service's local clock of each day.
            Assert.That(result.GetProperty("today").GetProperty("sunrise").GetString(), Is.EqualTo("07:05"));
            Assert.That(result.GetProperty("today").GetProperty("sunset").GetString(), Is.EqualTo("19:02"));
            Assert.That(result.GetProperty("tomorrow").GetProperty("sunrise").GetString(), Is.EqualTo("07:04"));
            Assert.That(result.GetProperty("tomorrow").GetProperty("sunset").GetString(), Is.EqualTo("19:03"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("open_meteo_forecast_v1"));
        });
    }

    [Test]
    public async Task WithoutAPlaceThisPcIsLocatedByItsPublicAddress()
    {
        var adapter = new OpenMeteoWeatherAdapter((url, _) => Task.FromResult(
            url.Contains("ipwho", StringComparison.Ordinal) ? Located : Forecast));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current",
            JsonSerializer.SerializeToElement(new { }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("location").GetString(), Is.EqualTo("Curico"));
            Assert.That(result.GetProperty("region").GetString(), Is.EqualTo("Region de Curico"));
            Assert.That(result.GetProperty("locatedBy").GetString(), Is.EqualTo("public_ip_address"));
        });
    }

    [Test]
    public async Task APlaceTheServiceDoesNotKnowIsAnHonestAbsenceBeforeAnyRead()
    {
        var adapter = new OpenMeteoWeatherAdapter((_, _) => Task.FromResult("""{"generationtime_ms":0.4}"""));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current",
            JsonSerializer.SerializeToElement(new { location = "Bruno Mars" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("weather_place_not_found"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task AServiceThatDoesNotAnswerIsNamedNotGuessed()
    {
        var adapter = new OpenMeteoWeatherAdapter((_, _) =>
            throw new System.Net.Http.HttpRequestException("offline"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current",
            JsonSerializer.SerializeToElement(new { location = "Madrid" }),
            CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("weather_service_unavailable"));
    }

    [TestCase(0, "despejado")]
    [TestCase(45, "niebla")]
    [TestCase(63, "lluvia")]
    [TestCase(95, "tormenta")]
    [TestCase(123, "sin dato")]
    public void WmoCodesAreNamedInPlainWords(int code, string expected) =>
        Assert.That(OpenMeteoWeatherAdapter.Condition(code), Is.EqualTo(expected));
}
