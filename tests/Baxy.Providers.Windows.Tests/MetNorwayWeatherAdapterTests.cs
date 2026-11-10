using System.Globalization;
using System.Net;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo W): la lectura del clima
/// devuelve lo que el servicio público dijo del lugar nombrado o de la
/// ubicación de este PC, y nombra sus ausencias sin inventar un pronóstico.
/// WEB1 (2026-11-07): el servicio es MET Norway y los lugares son los de GeoNames
/// que BAXY lleva dentro; el recibo conserva su forma.
/// </summary>
[TestFixture]
public sealed class MetNorwayWeatherAdapterTests
{
    private const string ProjectUserAgent = @"^BAXY/\d+\.\d+\.\d+ \(https://github\.com/REDSOULTM/BAXY\)$";

    // 19:15 in Buenos Aires (UTC-3).
    private static readonly DateTimeOffset Now = new(2026, 9, 20, 22, 15, 0, TimeSpan.Zero);

    // --- Places ------------------------------------------------------------------------------------------------------

    private static string P(
        long id, string feature, double latitude, double longitude, string country, long? region, double population,
        string? zone, string es, string? en = null, long? province = null) =>
        string.Join('\t', "P", id.ToString(CultureInfo.InvariantCulture), feature,
            latitude.ToString("F4", CultureInfo.InvariantCulture), longitude.ToString("F4", CultureInfo.InvariantCulture),
            country, region?.ToString(CultureInfo.InvariantCulture) ?? "", province?.ToString(CultureInfo.InvariantCulture) ?? "",
            population.ToString(CultureInfo.InvariantCulture), zone ?? "", es, en ?? es, "", "");

    private static readonly string[] Countries =
    [
        "C\tAR\t3865483", "C\tCL\t3895114", "C\tUS\t6252001", "C\tES\t2510769", "C\tVE\t3625428", "C\tPH\t1694008",
        "C\tPE\t3932488", "C\tMX\t3996063",
        P(3865483, "PCLI", -34, -64, "AR", null, 45851378, null, "Argentina"),
        P(3895114, "PCLI", -30, -71, "CL", null, 19859921, null, "Chile"),
        P(6252001, "PCLI", 39.76, -98.5, "US", null, 341784857, null, "Estados Unidos", "United States"),
        P(2510769, "PCLI", 40, -4, "ES", null, 49355143, null, "España", "Spain"),
        P(3625428, "PCLI", 8, -66, "VE", null, 28515829, "America/Caracas", "Venezuela"),
        P(1694008, "PCLI", 13, 122, "PH", null, 112508994, "Asia/Manila", "Filipinas", "Philippines"),
        P(3932488, "PCLI", -10, -76, "PE", null, 32510453, "America/Lima", "Perú", "Peru"),
        P(3996063, "PCLI", 23, -102, "MX", null, 131946900, null, "México", "Mexico"),
    ];

    private static readonly string[] World =
    [
        .. Countries,
        P(3433955, "ADM1", -34.6, -58.45, "AR", 3433955, 2776138, "America/Argentina/Buenos_Aires",
            "Ciudad Autónoma de Buenos Aires", "Buenos Aires F.D."),
        P(3435910, "PPLC", -34.6131, -58.3772, "AR", 3433955, 2891082, "America/Argentina/Buenos_Aires", "Buenos Aires"),
        // Uso real tanda 4c «Digame el weather lunes 13 en North Carolina» read «Calvary, Georgia».
        P(4197000, "ADM1", 32.75, -83.5, "US", 4197000, 10711908, "America/New_York", "Georgia"),
        P(4185731, "PPL", 30.72697, -84.35088, "US", 4197000, 161, "America/New_York", "Calvary"),
        P(4482348, "ADM1", 35.50069, -80.00032, "US", 4482348, 11046024, "America/New_York", "Carolina del Norte", "North Carolina"),
        // The region's English name is the city's: a seat of government keeps the name.
        P(3868621, "ADM1", -32.75, -71.3333, "CL", 3868621, 1790219, "America/Santiago", "Región de Valparaíso", "Valparaiso"),
        P(3868626, "PPLA", -33.03932, -71.62725, "CL", 3868621, 282448, "America/Santiago", "Valparaíso"),
        P(3522186, "ADM1", 20.5, -98.9, "MX", 3522186, 3082841, "America/Mexico_City", "Hidalgo"),
        P(1, "PPL", 20.1, -98.9, "MX", 3522186, 993, "America/Mexico_City", "Texas"),
        P(4736286, "ADM1", 31.25044, -99.25061, "US", 4736286, 22875689, "America/Chicago", "Texas"),
        P(2, "PPL", 29.38, -94.9, "US", 4736286, 47618, "America/Chicago", "Texas City"),
        // M58: Foster City, Michigan has no population; Foster City, California was meant.
        P(5001836, "ADM1", 44.25, -85.5, "US", 5001836, 10077331, "America/Detroit", "Michigan"),
        P(5332921, "ADM1", 37.25, -119.75, "US", 5332921, 39512223, "America/Los_Angeles", "California"),
        P(4993198, "PPL", 45.96329, -87.74402, "US", 5001836, 0, "America/Menominee", "Foster City"),
        P(5350159, "PPL", 37.55855, -122.27108, "US", 5332921, 33477, "America/Los_Angeles", "Foster City",
            province: 5392427),
        "N\t5392427\tCondado de San Mateo\tSan Mateo County",
        // Ronda 19: Valencia of Venezuela and of Spain are comparable, of the Philippines much smaller.
        P(3646751, "ADM1", 10.2, -68.1, "VE", 3646751, 2245744, "America/Caracas", "Carabobo"),
        P(3625549, "PPLA", 10.16202, -68.00765, "VE", 3646751, 1385083, "America/Caracas", "Valencia"),
        P(2593113, "ADM1", 39.5, -0.75, "ES", 2593113, 5425182, "Europe/Madrid", "Comunidad Valenciana", "Valencia"),
        P(2509954, "PPLA", 39.46975, -0.37739, "ES", 2593113, 814208, "Europe/Madrid", "Valencia"),
        P(7521309, "ADM1", 9.6, 123.0, "PH", 7521309, 1354995, "Asia/Manila", "Negros Oriental"),
        P(1698120, "PPL", 9.28, 123.24, "PH", 7521309, 31477, "Asia/Manila", "Valencia"),
        // A town of a region's name inside it is the town; a seat abroad does not take a region's name.
        P(5128638, "ADM1", 43.0, -75.5, "US", 5128638, 19274244, "America/New_York", "Nueva York", "New York"),
        P(5128581, "PPL", 40.7143, -74.006, "US", 5128638, 8804190, "America/New_York", "Nueva York", "New York"),
        P(4155751, "ADM1", 28.75, -82.5, "US", 4155751, 17671452, "America/New_York", "Florida"),
        P(3564124, "ADM1", 21.5, -78.0, "CU", 3564124, 780000, "America/Havana", "Provincia de Camagüey", "Camaguey"),
        P(3557758, "PPLA2", 21.5246, -78.2256, "CU", 3564124, 63007, "America/Havana", "Florida"),
        // A county seat of the same name does not take a state's name; a country of several zones is read in its
        // capital's.
        P(6254928, "ADM1", 37.5481, -77.4467, "US", 6254928, 8811195, "America/New_York", "Virginia"),
        P(5048033, "PPLA2", 47.5233, -92.5366, "US", 5037779, 3361, "America/Chicago", "Virginia"),
        P(3871336, "PPLC", -33.4569, -70.6483, "CL", 3873544, 4837295, "America/Santiago", "Santiago de Chile", "Santiago"),
        P(3936452, "ADM1", -12.0, -77.0, "PE", 3936452, 9485405, "America/Lima", "Lima"),
        P(3936456, "PPLC", -12.04318, -77.02824, "PE", 3936452, 7737002, "America/Lima", "Lima"),
        P(3336902, "ADM1", 42.75, -8.0, "ES", 3336902, 2701819, "Europe/Madrid", "Galicia"),
        P(3118999, "PPL", 42.6, -8.1, "ES", 3336902, 120, "Europe/Madrid", "Lima"),
    ];

    private static GeoNamesGazetteer Gazetteer() => new(new StringReader(string.Join('\n', World)));

    // --- The service -------------------------------------------------------------------------------------------------

    private const string Located =
        """{"success":true,"country":"Chile","region":"Region de Valparaiso","city":"Valparaiso","latitude":-33.0363,"longitude":-71.6297,"timezone":{"id":"America/Santiago","utc":"-03:00"}}""";

    // One step of MET Norway's complete forecast (https://api.met.no/weatherapi/locationforecast/2.0/documentation).
    private sealed record Hour(
        string Time,
        double Temperature,
        string Symbol,
        double? Apparent = null,
        double? Humidity = 80,
        double? Wind = 2.5,
        double? Dew = 10.0,
        double? Uv = 0.0,
        double Precipitation = 0.0,
        double? Chance = null,
        double? SixHoursMax = null,
        double? SixHoursMin = null,
        bool SixHourly = false,
        double? SixHoursChance = null);

    private static string Forecast(params Hour[] hours)
    {
        var series = new JsonArray();
        foreach (Hour hour in hours)
        {
            var instant = new JsonObject { ["air_temperature"] = hour.Temperature };
            if (hour.Apparent is { } apparent) instant["apparent_air_temperature"] = apparent;
            if (hour.Humidity is { } humidity) instant["relative_humidity"] = humidity;
            if (hour.Wind is { } wind) instant["wind_speed"] = wind;
            if (hour.Dew is { } dew) instant["dew_point_temperature"] = dew;
            if (hour.Uv is { } uv) instant["ultraviolet_index_clear_sky"] = uv;
            var data = new JsonObject { ["instant"] = new JsonObject { ["details"] = instant } };
            var rain = new JsonObject { ["precipitation_amount"] = hour.Precipitation };
            if (hour.Chance is { } chance) rain["probability_of_precipitation"] = chance;
            if (!hour.SixHourly)
            {
                data["next_1_hours"] = new JsonObject
                {
                    ["summary"] = new JsonObject { ["symbol_code"] = hour.Symbol },
                    ["details"] = rain,
                };
            }
            var six = new JsonObject { ["precipitation_amount"] = hour.Precipitation };
            if (hour.SixHoursMax is { } high) six["air_temperature_max"] = high;
            if (hour.SixHoursMin is { } low) six["air_temperature_min"] = low;
            if (hour.SixHourly && hour.Chance is { } sixChance) six["probability_of_precipitation"] = sixChance;
            if (hour.SixHoursChance is { } ahead) six["probability_of_precipitation"] = ahead;
            data["next_6_hours"] = new JsonObject
            {
                ["summary"] = new JsonObject { ["symbol_code"] = hour.Symbol },
                ["details"] = six,
            };
            series.Add(new JsonObject { ["time"] = hour.Time, ["data"] = data });
        }

        return new JsonObject
        {
            ["type"] = "Feature",
            ["properties"] = new JsonObject
            {
                ["meta"] = new JsonObject { ["updated_at"] = "2026-09-20T18:00:00Z" },
                ["timeseries"] = series,
            },
        }.ToJsonString();
    }

    // Buenos Aires from 19:00 on Sunday 20 (UTC-3): the evening, then Monday with light rain at night.
    private static readonly string BuenosAires = Forecast(
        new Hour("2026-09-20T22:00:00Z", 18.8, "cloudy", Apparent: 20.2, Humidity: 92, Wind: 2.5, Dew: 17.44, Uv: 0.42, Chance: 10),
        new Hour("2026-09-20T23:00:00Z", 18.0, "cloudy"),
        // Its six hours end tomorrow at 05:00: that chance of rain is not today's.
        new Hour("2026-09-21T02:00:00Z", 16.6, "partlycloudy_night", SixHoursChance: 90),
        new Hour("2026-09-21T03:00:00Z", 14.0, "lightrain", Chance: 65, SixHoursMax: 15.0, SixHoursMin: 12.5),
        new Hour("2026-09-21T15:00:00Z", 21.0, "partlycloudy_day", Uv: 3.1, SixHoursMax: 22.1, SixHoursMin: 19.0),
        new Hour("2026-09-21T21:00:00Z", 19.0, "fair_day", SixHoursMax: 21.5, SixHoursMin: 16.0));

    private static string Sun(string date, string offset, string rise, string set) =>
        new JsonObject
        {
            ["type"] = "Feature",
            ["properties"] = new JsonObject
            {
                ["body"] = "Sun",
                ["sunrise"] = new JsonObject { ["time"] = date + "T" + rise + offset },
                ["sunset"] = new JsonObject { ["time"] = date + "T" + set + offset },
            },
        }.ToJsonString();

    private sealed record Answer(HttpStatusCode Status, string Body = "", DateTimeOffset? Expires = null, DateTimeOffset? LastModified = null);

    // Answers each request by the first route its address contains; a request no route answers fails as no network.
    private sealed class Service : HttpMessageHandler
    {
        internal List<HttpRequestMessage> Asked { get; } = [];

        internal List<(string Contains, Func<Answer> Answer)> Routes { get; } = [];

        internal Service Route(string contains, Func<Answer> answer)
        {
            Routes.Add((contains, answer));
            return this;
        }

        internal Service Route(string contains, string body) => Route(contains, () => new Answer(HttpStatusCode.OK, body));

        internal IEnumerable<string> Forecasts =>
            Asked.Select(static request => request.RequestUri!.AbsoluteUri).Where(static url => url.Contains("locationforecast", StringComparison.Ordinal));

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Asked.Add(request);
            string address = Uri.UnescapeDataString(request.RequestUri!.AbsoluteUri);
            foreach ((string contains, Func<Answer> answer) in Routes)
            {
                if (!address.Contains(contains, StringComparison.Ordinal))
                    continue;
                Answer given = answer();
                var response = new HttpResponseMessage(given.Status) { Content = new StringContent(given.Body) };
                response.Content.Headers.Expires = given.Expires;
                response.Content.Headers.LastModified = given.LastModified;
                return Task.FromResult(response);
            }
            throw new HttpRequestException("unreachable " + request.RequestUri.Host);
        }
    }

    private static Service Met(string forecast = "") => new Service()
        .Route("ipwho.is", Located)
        .Route("locationforecast", forecast.Length > 0 ? forecast : BuenosAires)
        .Route("date=2026-09-20", Sun("2026-09-20", "-03:00", "07:05", "19:02"))
        .Route("date=2026-09-21", Sun("2026-09-21", "-03:00", "07:04", "19:03"));

    private static MetNorwayWeatherAdapter Adapter(Service service, Func<DateTimeOffset>? now = null, string? keptFile = null) =>
        new(service, Gazetteer, now ?? (static () => Now), keptFile);

    private static Task<ExternalCapabilityReceipt> Read(MetNorwayWeatherAdapter adapter, object arguments) =>
        adapter.InvokeAsync("weather.current", JsonSerializer.SerializeToElement(arguments), CancellationToken.None).AsTask();

    // --- The weather of a named place --------------------------------------------------------------------------------

    [Test]
    public async Task ANamedPlaceIsFoundHereAndItsForecastIsReadVerbatim()
    {
        Service service = Met();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "buenos aires" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.False);
            // MET Norway: coordinates of 4 decimals at most, and a User-Agent that names the application and a contact.
            Assert.That(service.Forecasts.Single(),
                Is.EqualTo("https://api.met.no/weatherapi/locationforecast/2.0/complete?lat=-34.6131&lon=-58.3772"));
            Assert.That(service.Asked.Select(static request => request.Headers.UserAgent.ToString()),
                Has.All.Match(ProjectUserAgent));
            Assert.That(service.Asked.Select(static request => request.RequestUri!.Host), Has.All.EqualTo("api.met.no"));
        });
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("location").GetString(), Is.EqualTo("Buenos Aires"));
            Assert.That(result.GetProperty("region").GetString(), Is.EqualTo("Ciudad Autónoma de Buenos Aires"));
            Assert.That(result.GetProperty("country").GetString(), Is.EqualTo("Argentina"));
            Assert.That(result.GetProperty("locatedBy").GetString(), Is.EqualTo("named_place_geocoded"));
            Assert.That(result.GetProperty("timezone").GetString(), Is.EqualTo("America/Argentina/Buenos_Aires"));
            Assert.That(result.GetProperty("observedAtLocal").GetString(), Is.EqualTo("2026-09-20T19:00"));
            Assert.That(result.GetProperty("temperatureC").GetDouble(), Is.EqualTo(18.8));
            Assert.That(result.GetProperty("apparentC").GetDouble(), Is.EqualTo(20.2));
            Assert.That(result.GetProperty("condition").GetString(), Is.EqualTo("nublado"));
            Assert.That(result.GetProperty("weatherCode").GetInt32(), Is.EqualTo(3));
            Assert.That(result.GetProperty("windKmh").GetDouble(), Is.EqualTo(9.0), "2.5 m/s");
            Assert.That(result.GetProperty("humidityPercent").GetDouble(), Is.EqualTo(92));
            Assert.That(result.GetProperty("precipitationMm").GetDouble(), Is.EqualTo(0));
            JsonElement today = result.GetProperty("today");
            Assert.That(today.GetProperty("date").GetString(), Is.EqualTo("2026-09-20"));
            Assert.That(today.GetProperty("weekday").GetString(), Is.EqualTo("domingo"));
            Assert.That(today.GetProperty("maxC").GetDouble(), Is.EqualTo(18.8));
            Assert.That(today.GetProperty("minC").GetDouble(), Is.EqualTo(16.6));
            Assert.That(today.GetProperty("rainProbabilityPercent").GetDouble(), Is.EqualTo(10));
            // The service gives no hour already past: today's figures are from the hour in course on.
            Assert.That(today.GetProperty("figuresFrom").GetString(), Is.EqualTo("19:00"));
            JsonElement tomorrow = result.GetProperty("tomorrow");
            Assert.That(tomorrow.GetProperty("date").GetString(), Is.EqualTo("2026-09-21"));
            Assert.That(tomorrow.GetProperty("weekday").GetString(), Is.EqualTo("lunes"));
            Assert.That(tomorrow.GetProperty("rainProbabilityPercent").GetDouble(), Is.EqualTo(65));
            Assert.That(tomorrow.GetProperty("condition").GetString(), Is.EqualTo("lluvia débil"), "the most severe sky");
            // The six-hour extremes that end within the day count; the evening's (to 03:00 next day) does not.
            Assert.That(tomorrow.GetProperty("maxC").GetDouble(), Is.EqualTo(22.1));
            Assert.That(tomorrow.GetProperty("minC").GetDouble(), Is.EqualTo(12.5));
            // Uso real tanda 2: the sun times are the place's clock of each day.
            Assert.That(today.GetProperty("sunrise").GetString(), Is.EqualTo("07:05"));
            Assert.That(today.GetProperty("sunset").GetString(), Is.EqualTo("19:02"));
            Assert.That(tomorrow.GetProperty("sunrise").GetString(), Is.EqualTo("07:04"));
            Assert.That(tomorrow.GetProperty("sunset").GetString(), Is.EqualTo("19:03"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("met_norway_locationforecast_v2"));
        });
    }

    [Test]
    public async Task TheSunIsAskedInThePlacesOffsetAndWithoutItTheWeatherStillAnswers()
    {
        Service service = new Service()
            .Route("locationforecast", BuenosAires)
            .Route("sunrise", () => new Answer(HttpStatusCode.ServiceUnavailable));

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "Buenos Aires" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(service.Asked.Select(static request => request.RequestUri!.Query),
                Has.Some.Contains("date=2026-09-20&offset=-03:00").And.Some.Contains("date=2026-09-21&offset=-03:00"));
            Assert.That(receipt.Result!.Value.GetProperty("today").GetProperty("sunrise").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(receipt.Result!.Value.GetProperty("tomorrow").GetProperty("sunset").ValueKind, Is.EqualTo(JsonValueKind.Null));
        });
    }

    [Test]
    public async Task WithoutAPlaceThisPcIsLocatedByItsPublicAddressAndReadInItsZone()
    {
        Service service = Met(Forecast(new Hour("2026-09-20T22:00:00Z", 12.0, "clearsky_night")));

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("location").GetString(), Is.EqualTo("Valparaiso"));
            Assert.That(result.GetProperty("region").GetString(), Is.EqualTo("Region de Valparaiso"));
            Assert.That(result.GetProperty("locatedBy").GetString(), Is.EqualTo("public_ip_address"));
            Assert.That(result.GetProperty("timezone").GetString(), Is.EqualTo("America/Santiago"));
            Assert.That(result.GetProperty("condition").GetString(), Is.EqualTo("despejado"));
            Assert.That(service.Forecasts.Single(), Does.EndWith("?lat=-33.0363&lon=-71.6297"));
        });
    }

    [Test]
    public async Task APlaceNotNamedSoIsAnHonestAbsenceBeforeAnyRead()
    {
        Service service = Met();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "Bruno Mars" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("weather_place_not_found"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(service.Asked, Is.Empty, "the place is looked up on this PC");
        });
    }

    [Test]
    public async Task AServiceThatDoesNotAnswerIsNamedNotGuessed()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(new Service()), new { location = "Madrid, ES" });
        ExternalCapabilityReceipt named = await Read(Adapter(new Service()), new { location = "Buenos Aires" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("weather_place_not_found"), "Madrid is not among these places");
            Assert.That(named.ErrorCode, Is.EqualTo("weather_service_unavailable"));
        });
    }

    // Renew al máximo (auditoría de flujos, web): «¿cómo está el clima?» without network is the service not answering;
    // it was weather_location_unavailable, and the model asked the person where they were.
    [Test]
    public async Task WithoutNetworkTheWeatherHereIsTheServiceNotAnsweringNotAnUnknownPlace()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(new Service()), new { });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("weather_service_unavailable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    // fable/estab-wx-clima (tanda n6 t1-c05 «va a llover mañana en valpo?» → «el servicio meteorológico no respondió» at
    // 2.1 s; n5 read it): a service that fails once and answers next is read after one pause.
    [Test]
    public async Task AServiceThatFailsOnceIsAskedAgainOnceAfterAPause()
    {
        int forecastCalls = 0;
        Service service = new Service()
            .Route("locationforecast", () => ++forecastCalls == 1
                ? new Answer(HttpStatusCode.BadGateway)
                : new Answer(HttpStatusCode.OK, BuenosAires))
            .Route("sunrise", Sun("2026-09-20", "-03:00", "07:05", "19:02"));
        var clock = System.Diagnostics.Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "Buenos Aires" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("location").GetString(), Is.EqualTo("Buenos Aires"));
            Assert.That(forecastCalls, Is.EqualTo(2));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(TransientHttp.Pause - TimeSpan.FromMilliseconds(50)));
        });
    }

    // Contracase: failing twice keeps the same honest final, with no third ask; a refusal that is not transient (404) is
    // not asked again, nor a throttle (429): MET Norway asks to «limit traffic immediately».
    [TestCase(HttpStatusCode.ServiceUnavailable, 2)]
    [TestCase(HttpStatusCode.NotFound, 1)]
    [TestCase(HttpStatusCode.TooManyRequests, 1)]
    public async Task AServiceThatFailsAgainOrRefusesKeepsTheHonestFinal(HttpStatusCode status, int expectedCalls)
    {
        int forecastCalls = 0;
        Service service = new Service()
            .Route("locationforecast", () =>
            {
                forecastCalls++;
                return new Answer(status);
            })
            .Route("sunrise", Sun("2026-09-20", "-03:00", "07:05", "19:02"));

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "Buenos Aires" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("weather_service_unavailable"));
            Assert.That(forecastCalls, Is.EqualTo(expectedCalls));
        });
    }

    // MET Norway: on a 429 «limit traffic immediately»: nothing more is asked until its Retry-After has passed.
    [Test]
    public async Task AfterAThrottleNothingIsAskedUntilTheServiceSaysSo()
    {
        DateTimeOffset now = Now;
        int forecastCalls = 0;
        Service service = new Service()
            .Route("locationforecast", () => ++forecastCalls == 1
                ? new Answer(HttpStatusCode.TooManyRequests)
                : new Answer(HttpStatusCode.OK, BuenosAires))
            .Route("sunrise", Sun("2026-09-20", "-03:00", "07:05", "19:02"));
        MetNorwayWeatherAdapter adapter = Adapter(service, () => now);

        ExternalCapabilityReceipt throttled = await Read(adapter, new { location = "Buenos Aires" });
        now = Now.AddSeconds(30);
        ExternalCapabilityReceipt waiting = await Read(adapter, new { location = "Buenos Aires" });
        int whileWaiting = forecastCalls;
        now = Now.AddMinutes(2);
        ExternalCapabilityReceipt again = await Read(adapter, new { location = "Buenos Aires" });

        Assert.Multiple(() =>
        {
            Assert.That(throttled.ErrorCode, Is.EqualTo("weather_service_unavailable"));
            Assert.That(waiting.ErrorCode, Is.EqualTo("weather_service_unavailable"));
            Assert.That(whileWaiting, Is.EqualTo(1));
            Assert.That(again.Verified, Is.True, again.ErrorCode);
        });
    }

    // MET Norway's terms: «Never repeat requests until the time indicated in the Expires response header», and «Use the
    // If-Modified-Since request header to avoid repeatedly downloading the same data». WEB3: Locationforecast's own page
    // asks for longer: «Identical requests should not be repeated more often than every 30 mins for the Nordic region, or
    // every 3rd hour for the rest of the world» (https://api.met.no/weatherapi/locationforecast/2.0/documentation, read
    // 2026-11-07); a forecast of Santiago came back that day with an Expires 30 minutes ahead.
    [Test]
    public async Task AnAnswerIsNotAskedAgainBeforeItExpiresAndThenOnlyIfItChanged()
    {
        DateTimeOffset now = Now;
        DateTimeOffset modified = Now.AddMinutes(-20);
        var answers = new Queue<Answer>([
            new Answer(HttpStatusCode.OK, BuenosAires, Now.AddMinutes(30), modified),
            new Answer(HttpStatusCode.NotModified, "", Now.AddMinutes(90), modified),
        ]);
        Service service = new Service()
            .Route("locationforecast", () => answers.Dequeue())
            .Route("sunrise", () => new Answer(HttpStatusCode.OK, Sun("2026-09-20", "-03:00", "07:05", "19:02"), Now.AddDays(1)));
        MetNorwayWeatherAdapter adapter = Adapter(service, () => now);

        await Read(adapter, new { location = "Buenos Aires" });
        now = Now.AddMinutes(10);
        await Read(adapter, new { location = "Buenos Aires" });
        now = Now.AddMinutes(40);
        await Read(adapter, new { location = "Buenos Aires" });
        now = Now.AddMinutes(175);
        await Read(adapter, new { location = "Buenos Aires" });
        int beforeExpiry = service.Forecasts.Count();
        now = Now.AddMinutes(185);
        ExternalCapabilityReceipt unchanged = await Read(adapter, new { location = "Buenos Aires" });

        Assert.Multiple(() =>
        {
            Assert.That(beforeExpiry, Is.EqualTo(1));
            Assert.That(service.Forecasts.Count(), Is.EqualTo(2));
            Assert.That(service.Asked.Last(static request => request.RequestUri!.AbsoluteUri.Contains("locationforecast",
                StringComparison.Ordinal)).Headers.IfModifiedSince, Is.EqualTo(modified));
            Assert.That(unchanged.Verified, Is.True, unchanged.ErrorCode);
            // The kept forecast, read at 22:20: its 20:00 step (UTC 23:00) is the one in course.
            Assert.That(unchanged.Result!.Value.GetProperty("temperatureC").GetDouble(), Is.EqualTo(18.0));
            Assert.That(service.Asked.Count(static request => request.RequestUri!.AbsoluteUri.Contains("date=2026-09-20",
                StringComparison.Ordinal)), Is.EqualTo(1), "the sun of a day is asked once until it expires");
        });
    }

    // WEB3: the terms ask not to repeat «requests for data which never change» (https://api.met.no/doc/TermsOfService):
    // the sunrise and sunset of a day at a place are such data, though Sunrise 3.0 answered that day with an Expires six
    // minutes ahead. The sun of a day is asked once while that day is today or tomorrow.
    [Test]
    public async Task TheSunOfADayIsAskedOnceThoughItsAnswerExpiresInMinutes()
    {
        DateTimeOffset now = Now;
        Service service = new Service()
            .Route("locationforecast", () => new Answer(HttpStatusCode.OK, BuenosAires, now.AddMinutes(30)))
            .Route("date=2026-09-20", () => new Answer(HttpStatusCode.OK, Sun("2026-09-20", "-03:00", "07:05", "19:02"), now.AddMinutes(6)))
            .Route("date=2026-09-21", () => new Answer(HttpStatusCode.OK, Sun("2026-09-21", "-03:00", "07:04", "19:03"), now.AddMinutes(6)));
        MetNorwayWeatherAdapter adapter = Adapter(service, () => now);

        await Read(adapter, new { location = "Buenos Aires" });
        // 22:20 in Buenos Aires: still the same day, and the forecast is asked again.
        now = Now.AddMinutes(185);
        ExternalCapabilityReceipt later = await Read(adapter, new { location = "Buenos Aires" });

        Assert.Multiple(() =>
        {
            Assert.That(service.Forecasts.Count(), Is.EqualTo(2));
            Assert.That(service.Asked.Count(static request => request.RequestUri!.AbsoluteUri.Contains("date=2026-09-20",
                StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(service.Asked.Count(static request => request.RequestUri!.AbsoluteUri.Contains("date=2026-09-21",
                StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(later.Result!.Value.GetProperty("today").GetProperty("sunset").GetString(), Is.EqualTo("19:02"));
        });
    }

    // WEB3: «Cache data locally» and «Never repeat requests until the time indicated in the Expires response header»
    // (https://api.met.no/doc/TermsOfService) hold across a restart of BAXY too: what was kept is in its data folder, and
    // a new reader of the weather asks nothing that the last one may not ask yet.
    [Test]
    public async Task WhatWasKeptOutlivesARestart()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-met-kept-" + Guid.NewGuid().ToString("N"));
        string kept = Path.Combine(folder, "met-norway-answers.v1.json");
        try
        {
            Service first = Met();
            using (MetNorwayWeatherAdapter before = Adapter(first, () => Now, kept))
                await Read(before, new { location = "Buenos Aires" });
            Service second = Met();
            ExternalCapabilityReceipt after;
            using (MetNorwayWeatherAdapter restarted = Adapter(second, () => Now.AddMinutes(20), kept))
                after = await Read(restarted, new { location = "Buenos Aires" });

            Assert.Multiple(() =>
            {
                Assert.That(first.Asked.Count(static request => request.RequestUri!.Host == "api.met.no"), Is.EqualTo(3));
                Assert.That(second.Asked.Where(static request => request.RequestUri!.Host == "api.met.no"), Is.Empty);
                Assert.That(after.Verified, Is.True, after.ErrorCode);
                Assert.That(after.Result!.Value.GetProperty("temperatureC").GetDouble(), Is.EqualTo(18.8));
            });
        }
        finally
        {
            if (Directory.Exists(folder)) Directory.Delete(folder, recursive: true);
        }
    }

    // Contracase: a kept file that cannot be read is no answer: the weather is asked as if nothing had been kept.
    [Test]
    public async Task AnUnreadableKeptFileIsAskedAround()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-met-kept-" + Guid.NewGuid().ToString("N"));
        string kept = Path.Combine(folder, "met-norway-answers.v1.json");
        Directory.CreateDirectory(folder);
        await File.WriteAllTextAsync(kept, "{ not json");
        try
        {
            Service service = Met();
            ExternalCapabilityReceipt receipt;
            using (MetNorwayWeatherAdapter adapter = Adapter(service, () => Now, kept))
                receipt = await Read(adapter, new { location = "Buenos Aires" });

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(service.Forecasts.Count(), Is.EqualTo(1));
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    // --- Which place -------------------------------------------------------------------------------------------------

    // Uso real tanda 4c «Digame el weather lunes 13 en North Carolina» read «Calvary, Georgia»: a region named in either
    // language is the region.
    [TestCase("North Carolina")]
    [TestCase("north carolina")]
    [TestCase("Carolina del Norte")]
    public async Task ARegionNamedInEitherLanguageIsTheRegionNotAHamletThatBorrowsItsName(string asked)
    {
        Service service = Met();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = asked });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("location").GetString(), Is.EqualTo("Carolina del Norte"));
            Assert.That(result.TryGetProperty("region", out _), Is.False);
            Assert.That(result.GetProperty("country").GetString(), Is.EqualTo("Estados Unidos"));
            Assert.That(service.Forecasts.Single(), Does.Contain("lat=35.5007"));
        });
    }

    [Test]
    public async Task ACapitalThatSharesItsRegionsNameStaysTheCity()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = "valparaiso" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("location").GetString(), Is.EqualTo("Valparaíso"));
            Assert.That(receipt.Result!.Value.GetProperty("region").GetString(), Is.EqualTo("Región de Valparaíso"));
        });
    }

    [TestCase("Nueva York", "lat=40.7143")]
    [TestCase("Florida", "lat=28.7500")]
    public async Task ARegionYieldsToATownOfItsNameInsideItButNotToASeatAbroad(string asked, string coordinates)
    {
        Service service = Met();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = asked });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("location").GetString(), Is.EqualTo(asked));
            Assert.That(receipt.Result!.Value.GetProperty("country").GetString(), Is.EqualTo("Estados Unidos"));
            Assert.That(service.Forecasts.Single(), Does.Contain(coordinates));
        });
    }

    [Test]
    public async Task ACountySeatOfAStatesNameDoesNotTakeIt()
    {
        Service service = Met();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "Virginia" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(service.Forecasts.Single(), Does.Contain("lat=37.5481"));
    }

    [Test]
    public async Task ACountryOfSeveralZonesIsReadInItsCapitalsZone()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = "Chile" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.Result!.Value.GetProperty("timezone").GetString(), Is.EqualTo("America/Santiago"));
    }

    [Test]
    public async Task AVillageThatSharesAStatesNameYieldsToTheState()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = "Texas" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.Result!.Value.GetProperty("country").GetString(), Is.EqualTo("Estados Unidos"));
    }

    // M58 (v3d-final F-p07-t1/t2 «I must verify the weather in Foster City later today»): among places of the asked
    // name the most populous is read; «Lugar, Región» (or its province) reads the one in that region.
    [TestCase("Foster City", "California")]
    [TestCase("Foster City, Michigan", "Michigan")]
    [TestCase("Foster City, California", "California")]
    [TestCase("Foster City, San Mateo County", "California")]
    public async Task ThePlaceOfTheAskedNameIsTheMostPopulousOrTheOneInTheRegionSaid(string asked, string region)
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = asked });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("location").GetString(), Is.EqualTo("Foster City"));
            Assert.That(receipt.Result!.Value.GetProperty("region").GetString(), Is.EqualTo(region));
        });
    }

    // Ronda 19 (r17 t2-c13 «¿qué tiempo va a hacer mañana en Valencia? ¿cojo paraguas?» → Valencia, Venezuela): two
    // towns of comparable size share the name; the country the person's speech marks keeps one, the receipt says
    // namesakes exist (the reply names the country), a region said keeps its own, and a much smaller namesake in the
    // marked country is no namesake of the large town. Auditoría final: with nothing that keeps one, nothing is read
    // and the namesakes go back as candidates.
    [TestCase("Valencia", "ES", "España", true)]
    [TestCase("Valencia, Carabobo", "ES", "Venezuela", false)]
    [TestCase("Valencia, ES", null, "España", false)]
    [TestCase("Valencia, Spain", null, "España", false)]
    public async Task NamesakesOfComparableSizeAreToldAndTheSpeechOfThePersonChooses(
        string asked, string? dialect, string country, bool namesakesTold)
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = asked, dialectCountry = dialect });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("location").GetString(), Is.EqualTo("Valencia"));
            Assert.That(result.GetProperty("country").GetString(), Is.EqualTo(country));
            Assert.That(result.TryGetProperty("namesakesElsewhere", out JsonElement told) && told.GetBoolean(),
                Is.EqualTo(namesakesTold));
        });
    }

    [TestCase("Valencia", null, "weather_place_ambiguous", 2)]
    [TestCase("Valencia", "MX", "weather_place_ambiguous", 2)]
    // A comma part that places nothing (a vocative the mind could not tell from a region) places no Valencia.
    [TestCase("Valencia, Juan", "ES", "weather_place_not_found", 3)]
    public async Task NamesakesNothingKeepsOneOfAreCandidatesAndNothingIsRead(
        string asked, string? dialect, string code, int candidates)
    {
        Service service = Met();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = asked, dialectCountry = dialect });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.Result!.Value.GetProperty("candidates").GetArrayLength(), Is.EqualTo(candidates));
            Assert.That(receipt.Result!.Value.GetProperty("candidateCount").GetInt32(), Is.EqualTo(candidates));
            Assert.That(receipt.Result!.Value.GetProperty("candidates")[0].GetProperty("country").GetString(),
                Is.EqualTo("Venezuela"), "the largest first");
            Assert.That(receipt.Result!.Value.GetProperty("candidates")[0].GetProperty("region").GetString(),
                Is.EqualTo("Carabobo"));
            Assert.That(service.Asked, Is.Empty, "no forecast is read");
        });
    }

    [Test]
    public async Task AMuchSmallerNamesakeInTheMarkedCountryIsNotChosen()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = "Lima", dialectCountry = "ES" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("country").GetString(), Is.EqualTo("Perú"));
            Assert.That(receipt.Result!.Value.TryGetProperty("namesakesElsewhere", out _), Is.False);
        });
    }

    // Ronda 19 contracase: a name no place bears is still not found; nothing is invented. The places whose name begins
    // with the words said are what the person may have meant, largest first.
    [Test]
    public async Task ANameNoPlaceBearsStaysNotFoundWithThePlacesWhoseNameBeginsSo()
    {
        ExternalCapabilityReceipt nothing = await Read(Adapter(Met()), new { location = "Xqzvlop" });
        ExternalCapabilityReceipt beginning = await Read(Adapter(Met()), new { location = "Foster" });
        ExternalCapabilityReceipt partOfAWord = await Read(Adapter(Met()), new { location = "Fost" });

        Assert.Multiple(() =>
        {
            Assert.That(nothing.ErrorCode, Is.EqualTo("weather_place_not_found"));
            Assert.That(nothing.Result!.Value.GetProperty("candidateCount").GetInt32(), Is.Zero);
            Assert.That(beginning.ErrorCode, Is.EqualTo("weather_place_not_found"));
            Assert.That(beginning.Result!.Value.GetProperty("candidates")[0].GetProperty("region").GetString(),
                Is.EqualTo("California"));
            Assert.That(beginning.Result!.Value.GetProperty("candidateCount").GetInt32(), Is.EqualTo(2));
            Assert.That(partOfAWord.Result!.Value.GetProperty("candidateCount").GetInt32(), Is.Zero);
        });
    }

    [Test]
    public async Task APlaceKnownOnlyByAnAliasOfAnotherIsNotFound()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = "Carolina del Sur" });

        Assert.That(receipt.ErrorCode, Is.EqualTo("weather_place_not_found"));
    }

    // Uso real tanda 4c «Whats the air quality hoy?» was read from Open-Meteo's air service, non-commercial like its
    // forecast; no free service allows a sold product. WEB3 (2026-11-07): none without a key either (OpenAQ and WAQI ask
    // for one, WAQI an agreement for for-profit use, MET Norway's covers Norway only), so the field is absent and the
    // receipt says why in a typed reason: the model says it has no such data, never a «null» it may read as «clean air».
    [Test]
    public async Task TheAirOfThePlaceHasNoServiceAndIsNamedAbsent()
    {
        Service service = Met();

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "Buenos Aires" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.TryGetProperty("airQuality", out _), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("unavailable").GetProperty("airQuality").GetString(),
                Is.EqualTo("no_keyless_service_allows_commercial_use"));
            Assert.That(service.Asked.Select(static request => request.RequestUri!.AbsolutePath),
                Has.None.Contains("air"));
        });
    }

    // Uso real tanda 6 «Dime el UV index», «¿Cómo está el dew point ahora?» went to web pages that define them: the UV
    // index (now and today's and tomorrow's peak; MET Norway gives it for a clear sky) and the dew point are readings
    // of the same forecast.
    [Test]
    public async Task TheUvIndexAndTheDewPointAreReadWithTheWeather()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = "Buenos Aires" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("uvIndex").GetDouble(), Is.EqualTo(0.4));
            Assert.That(result.GetProperty("dewPointC").GetDouble(), Is.EqualTo(17.4));
            Assert.That(result.GetProperty("today").GetProperty("uvIndexMax").GetDouble(), Is.EqualTo(0.4));
            Assert.That(result.GetProperty("tomorrow").GetProperty("uvIndexMax").GetDouble(), Is.EqualTo(3.1));
        });
    }

    [Test]
    public async Task AServiceAnswerWithoutUvDewPointOrChanceOfRainNamesTheirAbsence()
    {
        Service service = Met(Forecast(
            new Hour("2026-09-20T22:00:00Z", 18.8, "cloudy", Apparent: null, Dew: null, Uv: null, Humidity: null, Wind: null)));

        ExternalCapabilityReceipt receipt = await Read(Adapter(service), new { location = "Buenos Aires" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("temperatureC").GetDouble(), Is.EqualTo(18.8));
            foreach (string absent in (string[])["apparentC", "uvIndex", "dewPointC", "humidityPercent", "windKmh"])
                Assert.That(result.GetProperty(absent).ValueKind, Is.EqualTo(JsonValueKind.Null), absent);
            Assert.That(result.GetProperty("today").GetProperty("uvIndexMax").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(result.GetProperty("today").GetProperty("rainProbabilityPercent").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(result.GetProperty("tomorrow").GetProperty("condition").GetString(), Is.EqualTo("sin dato"));
        });
    }

    // Uso real tanda 6 «cuál es el pronóstico del tiempo para la semana» got today and tomorrow only: the week comes in
    // the same read; the days after tomorrow are laterDays, each with its date, its weekday, its sky and its figures.
    [Test]
    public async Task TheDaysAfterTomorrowAreReadWithTheirWeekday()
    {
        var hours = new List<Hour> { new("2026-09-24T21:00:00Z", 16.4, "cloudy") };
        string[] skies = ["cloudy", "rain", "lightrain", "partlycloudy", "clearsky", "fair", "snow", "snow", "snow"];
        for (int day = 1; day <= 8; day++)
        {
            string date = new DateOnly(2026, 9, 24).AddDays(day).ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            foreach (string hour in (string[])["06", "12", "18"])
            {
                hours.Add(new Hour(date + "T" + hour + ":00:00Z", 10 + day, skies[day] + (hour == "06" ? "_night" : "_day"),
                    Chance: day * 10, SixHoursMax: 12 + day, SixHoursMin: 8 + day, SixHourly: true));
            }
        }
        Service service = Met(Forecast([.. hours]));

        ExternalCapabilityReceipt receipt = await Read(
            Adapter(service, static () => new DateTimeOffset(2026, 9, 24, 21, 45, 0, TimeSpan.Zero)), new { });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        JsonElement result = receipt.Result!.Value;
        JsonElement later = result.GetProperty("laterDays");
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("today").GetProperty("date").GetString(), Is.EqualTo("2026-09-24"));
            Assert.That(result.GetProperty("today").GetProperty("weekday").GetString(), Is.EqualTo("jueves"));
            Assert.That(result.GetProperty("tomorrow").GetProperty("weekday").GetString(), Is.EqualTo("viernes"));
            Assert.That(later.GetArrayLength(), Is.EqualTo(5), "seven days in all, as before");
            Assert.That(later[0].GetProperty("date").GetString(), Is.EqualTo("2026-09-26"));
            Assert.That(later[0].GetProperty("weekday").GetString(), Is.EqualTo("sábado"));
            Assert.That(later[0].GetProperty("condition").GetString(), Is.EqualTo("lluvia débil"));
            Assert.That(later[0].GetProperty("maxC").GetDouble(), Is.EqualTo(14), "the six hours' highest");
            Assert.That(later[0].GetProperty("minC").GetDouble(), Is.EqualTo(10));
            Assert.That(later[0].GetProperty("rainProbabilityPercent").GetDouble(), Is.EqualTo(20));
            Assert.That(later[1].GetProperty("weekday").GetString(), Is.EqualTo("domingo"));
            Assert.That(later[4].GetProperty("date").GetString(), Is.EqualTo("2026-09-30"));
            Assert.That(later[4].GetProperty("weekday").GetString(), Is.EqualTo("miércoles"));
            Assert.That(later[4].GetProperty("condition").GetString(), Is.EqualTo("nieve"));
        });
    }

    [Test]
    public async Task AServiceThatGivesOnlyTwoDaysLeavesNoLaterDays()
    {
        ExternalCapabilityReceipt receipt = await Read(Adapter(Met()), new { location = "Buenos Aires" });

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(receipt.Result!.Value.GetProperty("laterDays").GetArrayLength(), Is.EqualTo(0));
    }

    [TestCase("clearsky_day", 0, "despejado")]
    [TestCase("fair_night", 1, "mayormente despejado")]
    [TestCase("fog", 45, "niebla")]
    [TestCase("lightrainshowers_polartwilight", 80, "chubascos débiles")]
    [TestCase("heavyrain", 65, "lluvia intensa")]
    [TestCase("lightsleet", 68, "aguanieve débil")]
    [TestCase("sleetshowers_day", 84, "chubascos de aguanieve")]
    [TestCase("snowshowers_night", 86, "chubascos de nieve")]
    [TestCase("rainandthunder", 95, "tormenta")]
    // MET Norway's own spelling of two symbols (an extra «s» after «light»).
    [TestCase("lightssleetshowersandthunder_day", 95, "tormenta")]
    [TestCase("heavysnowandthunder", 97, "tormenta fuerte")]
    [TestCase("tornado", -1, "sin dato")]
    [TestCase(null, -1, "sin dato")]
    public void MetNorwaySymbolsAreNamedAsWmoCodesInPlainWords(string? symbol, int code, string words)
    {
        Assert.Multiple(() =>
        {
            Assert.That(MetNorwayWeatherAdapter.WmoCode(symbol), Is.EqualTo(code));
            Assert.That(MetNorwayWeatherAdapter.Condition(code), Is.EqualTo(words));
        });
    }
}
