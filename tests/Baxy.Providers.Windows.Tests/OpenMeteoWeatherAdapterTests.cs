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
         "current":{"time":"2026-09-20T19:15","temperature_2m":18.8,"apparent_temperature":20.2,"relative_humidity_2m":92,"weather_code":3,"wind_speed_10m":8.0,"precipitation":0.0,"uv_index":0.42,"dew_point_2m":17.44},
         "daily":{"time":["2026-09-20","2026-09-21"],"temperature_2m_max":[22.1,21.0],"temperature_2m_min":[14.0,12.5],"precipitation_probability_max":[10,65],"weather_code":[3,61],
                  "sunrise":["2026-09-20T07:05","2026-09-21T07:04"],"sunset":["2026-09-20T19:02","2026-09-21T19:03"],"uv_index_max":[5.86,3.1]}}
        """;

    // A service answer from before the UV index and the dew point were asked: the other readings still stand.
    private const string ForecastWithoutUv =
        """
        {"timezone":"America/Santiago",
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
            Assert.That(asked.Single(url => url.StartsWith("https://api.open-meteo.com/", StringComparison.Ordinal)),
                Does.Contain("latitude=-34.6131").And.Contain("forecast_days=7").And.Contain("sunrise,sunset"));
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

    // Uso real tanda 4c «Digame el weather lunes 13 en North Carolina» read «Calvary,
    // Georgia»: the geocoder lists first a hamlet that carries the state's name as an
    // alias, and it indexes no state by name. A region named in either language is the
    // region its places belong to, read by its own identifier.
    private const string CarolinaEs =
        """{"results":[{"id":4185731,"name":"Calvary","latitude":30.72697,"longitude":-84.35088,"feature_code":"PPL","admin1_id":4197000,"population":161,"country":"Estados Unidos","admin1":"Georgia"},{"id":4482347,"name":"North Carolina Zoological Park","latitude":35.63347,"longitude":-79.75948,"feature_code":"PRK","admin1_id":4482348,"country":"Estados Unidos","admin1":"Carolina del Norte"}]}""";

    private const string CarolinaEn =
        """{"results":[{"id":4185731,"name":"Calvary","latitude":30.72697,"longitude":-84.35088,"feature_code":"PPL","admin1_id":4197000,"population":161,"country":"United States","admin1":"Georgia"},{"id":4482347,"name":"North Carolina Zoological Park","latitude":35.63347,"longitude":-79.75948,"feature_code":"PRK","admin1_id":4482348,"country":"United States","admin1":"North Carolina"}]}""";

    private const string CarolinaRegion =
        """{"id":4482348,"name":"Carolina del Norte","latitude":35.50069,"longitude":-80.00032,"feature_code":"ADM1","population":11046024,"country":"Estados Unidos","admin1":"Carolina del Norte"}""";

    private const string Air =
        """{"current":{"time":"2026-09-24T08:00","interval":3600,"us_aqi":75,"pm2_5":32.4,"pm10":33.1}}""";

    private static Func<string, CancellationToken, Task<string>> Service(
        string spanish, string english, string? region = null, string? air = null, List<string>? asked = null) =>
        (url, _) =>
        {
            asked?.Add(url);
            if (url.Contains("/v1/get?", StringComparison.Ordinal))
                return Task.FromResult(region ?? throw new System.Net.Http.HttpRequestException("no region"));
            if (url.Contains("geocoding", StringComparison.Ordinal))
                return Task.FromResult(url.Contains("language=en", StringComparison.Ordinal) ? english : spanish);
            if (url.Contains("air-quality", StringComparison.Ordinal))
                return Task.FromResult(air ?? throw new System.Net.Http.HttpRequestException("no air"));
            return Task.FromResult(Forecast);
        };

    [TestCase("North Carolina")]
    [TestCase("north carolina")]
    [TestCase("Carolina del Norte")]
    public async Task ARegionNamedInEitherLanguageIsTheRegionNotAHamletThatBorrowsItsName(string asked)
    {
        var urls = new List<string>();
        var adapter = new OpenMeteoWeatherAdapter(Service(CarolinaEs, CarolinaEn, CarolinaRegion, asked: urls));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = asked }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("location").GetString(), Is.EqualTo("Carolina del Norte"));
            Assert.That(result.TryGetProperty("region", out _), Is.False);
            Assert.That(result.GetProperty("country").GetString(), Is.EqualTo("Estados Unidos"));
            Assert.That(urls, Has.Some.Contains("/v1/get?language=es&id=4482348"));
            Assert.That(urls.Single(url => url.StartsWith("https://api.open-meteo.com/", StringComparison.Ordinal)),
                Does.Contain("latitude=35.5007"));
        });
    }

    [Test]
    public async Task ACapitalThatSharesItsRegionsNameStaysTheCity()
    {
        const string spanish =
            """{"results":[{"id":3868626,"name":"Curicó","latitude":-34.98279,"longitude":-71.23943,"feature_code":"PPLA","admin1_id":3868621,"population":282448,"country":"Chile","admin1":"Región de Curicó"}]}""";
        const string english =
            """{"results":[{"id":3868626,"name":"Curico","latitude":-34.98279,"longitude":-71.23943,"feature_code":"PPLA","admin1_id":3868621,"population":282448,"country":"Chile","admin1":"Curico Region"}]}""";
        const string region =
            """{"id":3868621,"name":"Región de Curicó","latitude":-32.9,"longitude":-71.2,"feature_code":"ADM1","population":1790219,"country":"Chile"}""";
        var adapter = new OpenMeteoWeatherAdapter(Service(spanish, english, region));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "curico" }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("location").GetString(), Is.EqualTo("Curicó"));
            Assert.That(receipt.Result!.Value.GetProperty("region").GetString(), Is.EqualTo("Región de Curicó"));
        });
    }

    [Test]
    public async Task AVillageThatSharesAStatesNameYieldsToTheState()
    {
        const string spanish =
            """{"results":[{"id":1,"name":"Texas","latitude":20.1,"longitude":-98.9,"feature_code":"PPL","admin1_id":10,"population":993,"country":"México","admin1":"Estado de Hidalgo"},{"id":2,"name":"Texas City","latitude":29.38,"longitude":-94.9,"feature_code":"PPL","admin1_id":4736286,"population":47618,"country":"Estados Unidos","admin1":"Texas"}]}""";
        const string region =
            """{"id":4736286,"name":"Texas","latitude":31.25044,"longitude":-99.25061,"feature_code":"ADM1","population":22875689,"country":"Estados Unidos","admin1":"Texas"}""";
        var adapter = new OpenMeteoWeatherAdapter(Service(spanish, spanish, region));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "Texas" }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.Result!.Value.GetProperty("country").GetString(), Is.EqualTo("Estados Unidos"));
    }

    [Test]
    public async Task APlaceKnownOnlyByAnAliasOfAnotherIsNotFound()
    {
        var adapter = new OpenMeteoWeatherAdapter(Service(CarolinaEs, CarolinaEn));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "Carolina del Sur" }), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("weather_place_not_found"));
    }

    // Uso real tanda 4c «Whats the air quality hoy?»: the air of the same place is read
    // with its weather; when that service does not answer, the weather still does.
    [Test]
    public async Task TheAirOfThePlaceIsReadWithItsWeather()
    {
        var adapter = new OpenMeteoWeatherAdapter((url, _) => Task.FromResult(
            url.Contains("ipwho", StringComparison.Ordinal) ? Located
            : url.Contains("air-quality", StringComparison.Ordinal) ? Air
            : Forecast));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement air = receipt.Result!.Value.GetProperty("airQuality");
        Assert.Multiple(() =>
        {
            Assert.That(air.GetProperty("usAqi").GetInt32(), Is.EqualTo(75));
            Assert.That(air.GetProperty("category").GetString(), Is.EqualTo("moderada"));
            Assert.That(air.GetProperty("pm25").GetDouble(), Is.EqualTo(32.4));
            Assert.That(air.GetProperty("pm10").GetDouble(), Is.EqualTo(33.1));
        });
    }

    [Test]
    public async Task AnAirServiceThatDoesNotAnswerLeavesTheWeatherAndNamesTheAbsence()
    {
        var adapter = new OpenMeteoWeatherAdapter(Service(Geocoded, Geocoded));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "Buenos Aires" }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.Result!.Value.GetProperty("airQuality").ValueKind, Is.EqualTo(JsonValueKind.Null));
    }

    // Uso real tanda 6 «Dime el UV index», «¿Cómo está el dew point ahora?» went to web pages
    // that define them: the UV index (now and today's and tomorrow's peak) and the dew point
    // are readings of the same service, asked in the same forecast read.
    [Test]
    public async Task TheUvIndexAndTheDewPointAreReadWithTheWeather()
    {
        var urls = new List<string>();
        var adapter = new OpenMeteoWeatherAdapter(Service(Geocoded, Geocoded, asked: urls));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "Buenos Aires" }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(urls.Single(url => url.StartsWith("https://api.open-meteo.com/", StringComparison.Ordinal)),
                Does.Contain("uv_index,dew_point_2m").And.Contain("uv_index_max"));
            Assert.That(result.GetProperty("uvIndex").GetDouble(), Is.EqualTo(0.4));
            Assert.That(result.GetProperty("dewPointC").GetDouble(), Is.EqualTo(17.4));
            Assert.That(result.GetProperty("today").GetProperty("uvIndexMax").GetDouble(), Is.EqualTo(5.9));
            Assert.That(result.GetProperty("tomorrow").GetProperty("uvIndexMax").GetDouble(), Is.EqualTo(3.1));
        });
    }

    [Test]
    public async Task AServiceAnswerWithoutUvOrDewPointNamesTheirAbsence()
    {
        var adapter = new OpenMeteoWeatherAdapter((url, _) => Task.FromResult(
            url.Contains("geocoding", StringComparison.Ordinal) ? Geocoded : ForecastWithoutUv));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "Buenos Aires" }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("temperatureC").GetDouble(), Is.EqualTo(18.8));
            Assert.That(result.GetProperty("uvIndex").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(result.GetProperty("dewPointC").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(result.GetProperty("today").GetProperty("uvIndexMax").ValueKind, Is.EqualTo(JsonValueKind.Null));
        });
    }

    // Uso real tanda 6 «cuál es el pronóstico del tiempo para la semana» got today and
    // tomorrow only: the seven days come in the same read; the days after tomorrow are
    // laterDays, each with its date, its weekday, its sky and its figures as read.
    private const string WeekForecast =
        """
        {"timezone":"America/Santiago",
         "current":{"time":"2026-09-24T18:45","temperature_2m":16.4,"apparent_temperature":16.7,"relative_humidity_2m":74,"weather_code":3,"wind_speed_10m":2.3,"precipitation":0.0,"uv_index":0.0,"dew_point_2m":11.8},
         "daily":{"time":["2026-09-24","2026-09-25","2026-09-26","2026-09-27","2026-09-28","2026-09-29","2026-09-30"],
                  "temperature_2m_max":[18.9,20.5,17.2,16.0,19.4,21.1,22.3],"temperature_2m_min":[12.6,12.4,11.0,10.2,11.5,12.0,13.1],
                  "precipitation_probability_max":[2,10,70,45,5,0,3],"weather_code":[3,3,63,61,2,0,1],
                  "sunrise":["2026-09-24T07:33","2026-09-25T07:31","2026-09-26T07:30","2026-09-27T07:29","2026-09-28T07:27","2026-09-29T07:26","2026-09-30T07:25"],
                  "sunset":["2026-09-24T19:44","2026-09-25T19:45","2026-09-26T19:45","2026-09-27T19:46","2026-09-28T19:47","2026-09-29T19:47","2026-09-30T19:48"],
                  "uv_index_max":[5.9,6.3,3.0,4.1,6.8,7.2,7.5]}}
        """;

    [Test]
    public async Task TheDaysAfterTomorrowAreReadWithTheirWeekday()
    {
        var adapter = new OpenMeteoWeatherAdapter((url, _) => Task.FromResult(
            url.Contains("ipwho", StringComparison.Ordinal) ? Located : WeekForecast));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        JsonElement later = result.GetProperty("laterDays");
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("today").GetProperty("date").GetString(), Is.EqualTo("2026-09-24"));
            Assert.That(result.GetProperty("today").GetProperty("weekday").GetString(), Is.EqualTo("jueves"));
            Assert.That(result.GetProperty("tomorrow").GetProperty("weekday").GetString(), Is.EqualTo("viernes"));
            Assert.That(later.GetArrayLength(), Is.EqualTo(5));
            Assert.That(later[0].GetProperty("date").GetString(), Is.EqualTo("2026-09-26"));
            Assert.That(later[0].GetProperty("weekday").GetString(), Is.EqualTo("sábado"));
            Assert.That(later[0].GetProperty("condition").GetString(), Is.EqualTo("lluvia"));
            Assert.That(later[0].GetProperty("maxC").GetDouble(), Is.EqualTo(17.2));
            Assert.That(later[0].GetProperty("minC").GetDouble(), Is.EqualTo(11.0));
            Assert.That(later[0].GetProperty("rainProbabilityPercent").GetDouble(), Is.EqualTo(70));
            Assert.That(later[1].GetProperty("weekday").GetString(), Is.EqualTo("domingo"));
            Assert.That(later[4].GetProperty("date").GetString(), Is.EqualTo("2026-09-30"));
            Assert.That(later[4].GetProperty("weekday").GetString(), Is.EqualTo("miércoles"));
            Assert.That(later[4].GetProperty("condition").GetString(), Is.EqualTo("mayormente despejado"));
        });
    }

    [Test]
    public async Task AServiceThatGivesOnlyTwoDaysLeavesNoLaterDays()
    {
        var adapter = new OpenMeteoWeatherAdapter(Service(Geocoded, Geocoded));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "weather.current", JsonSerializer.SerializeToElement(new { location = "Buenos Aires" }), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.Result!.Value.GetProperty("laterDays").GetArrayLength(), Is.EqualTo(0));
    }

    [TestCase(12, "buena")]
    [TestCase(75, "moderada")]
    [TestCase(130, "dañina para grupos sensibles")]
    [TestCase(180, "dañina")]
    [TestCase(250, "muy dañina")]
    [TestCase(420, "peligrosa")]
    public void TheAirIndexIsNamedByItsPublicScale(int usAqi, string expected) =>
        Assert.That(OpenMeteoWeatherAdapter.AirCategory(usAqi), Is.EqualTo(expected));

    [TestCase(0, "despejado")]
    [TestCase(45, "niebla")]
    [TestCase(63, "lluvia")]
    [TestCase(95, "tormenta")]
    [TestCase(123, "sin dato")]
    public void WmoCodesAreNamedInPlainWords(int code, string expected) =>
        Assert.That(OpenMeteoWeatherAdapter.Condition(code), Is.EqualTo(expected));
}
