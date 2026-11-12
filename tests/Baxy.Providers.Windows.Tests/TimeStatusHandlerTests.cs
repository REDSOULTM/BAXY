using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// V5E016 («si alguien en Tokio mira el reloj ahora mismo, ¿qué hora ve?»): system.time with the place was right, but the
/// model added the offset to the PC's local clock and missed the change of day. With the aid place_clock, the place
/// carries its own date, clock time and weekday at the observed instant; without it, the place reads as before.
/// </summary>
[TestFixture]
public sealed class TimeStatusHandlerTests
{
    private static readonly DateTimeOffset Observed = new(2026, 10, 24, 18, 28, 41, TimeSpan.Zero);

    [Test]
    public async Task ThePlaceSaysItsOwnDateClockAndWeekday()
    {
        using IDisposable setting = ModelAids.Use(ModelAids.PlaceClock);

        JsonElement place = (await Read()).GetProperty("place");

        Assert.Multiple(() =>
        {
            Assert.That(place.GetProperty("timeZone").GetString(), Is.EqualTo("Asia/Tokyo"));
            Assert.That(place.GetProperty("utcOffsetMinutes").GetInt32(), Is.EqualTo(540));
            Assert.That(place.GetProperty("date").GetString(), Is.EqualTo("2026-10-25"));
            Assert.That(place.GetProperty("localTime").GetString(), Is.EqualTo("03:28"));
            Assert.That(place.GetProperty("weekday").GetString(), Is.EqualTo("Sunday"));
        });
    }

    [TestCase("none")]
    [TestCase(ModelAids.CalculatorNext)]
    public async Task WithTheAidOffThePlaceReadsAsBefore(string aids)
    {
        using IDisposable setting = ModelAids.Use(aids);

        JsonElement result = await Read();

        Assert.Multiple(() =>
        {
            Assert.That(result.EnumerateObject().Select(property => property.Name),
                Is.EqualTo(new[] { "version", "utc", "localUtcOffsetMinutes", "localTime", "place" }));
            Assert.That(result.GetProperty("place").EnumerateObject().Select(property => property.Name),
                Is.EqualTo(new[] { "name", "country", "timeZone", "utcOffsetMinutes", "authority" }));
        });
    }

    // PUE5: with only utc and the offset the model read the utc field's hour as the PC's («son las 5:54 de la tarde» at
    // 05:54). The PC's clock time alone, without a date: a local date beside it brought «las 0:37 de este viernes» on a
    // Thursday (PUE4), so the date stays where it was.
    [Test]
    public async Task TheReadingAlsoSaysThePcsClockTimeWithoutADate()
    {
        JsonElement result = await Read();

        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("localTime").GetString(), Is.EqualTo("15:28"));
            Assert.That(result.TryGetProperty("local", out _), Is.False);
        });
    }

    // WEB2: a place not resolved fails with the places found instead, as the weather's does, so the person is asked.
    [Test]
    public async Task APlaceNotResolvedFailsWithThePlacesFoundInstead()
    {
        var handler = new TimeStatusHandler(new FixedClock(), new Namesakes());

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation",
                JsonDocument.Parse("""{"place":"Georgia"}""").RootElement.Clone()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("time_place_ambiguous"));
            Assert.That(outcome.Result?.GetProperty("candidateCount").GetInt32(), Is.EqualTo(2));
            Assert.That(OperationVisibleFacts.FromOutcome("system.time", outcome), Does.Contain("\"candidates\""));
        });
    }

    // VER1 (PR-03, «en siete días es el viernes 12»): asked for a date that is not today the model counted days and
    // weekdays itself and was wrong in most answers. The date is worked out here, on the PC's own date, with its weekday
    // and how far it is from today.
    [TestCase(15, "2026-11-08", "Sunday")]
    [TestCase(2, "2026-10-26", "Monday")]
    [TestCase(100, "2027-02-01", "Monday")]
    [TestCase(-45, "2026-09-09", "Wednesday")]
    public async Task ADateSomeDaysFromTodayIsWorkedOutHere(int days, string date, string weekday)
    {
        JsonElement calendar = (await Ask($$"""{"daysFromToday":{{days}}}""", Observed)).GetProperty("calendar");

        Assert.Multiple(() =>
        {
            Assert.That(calendar.GetProperty("today").GetRawText(), Is.EqualTo("""{"date":"2026-10-24","weekday":"Saturday"}"""));
            Assert.That(calendar.GetProperty("inDays").GetProperty("date").GetString(), Is.EqualTo(date));
            Assert.That(calendar.GetProperty("inDays").GetProperty("weekday").GetString(), Is.EqualTo(weekday));
            Assert.That(calendar.GetProperty("inDays").GetProperty("daysFromToday").GetInt32(), Is.EqualTo(days));
        });
    }

    // With its year, that one date. Today is Saturday 2026-10-24.
    [TestCase(2026, 12, 25, "2026-12-25", "Friday", 62)]
    [TestCase(2026, 9, 18, "2026-09-18", "Friday", -36)]
    [TestCase(2001, 9, 11, "2001-09-11", "Tuesday", -9174)]
    [TestCase(2028, 2, 29, "2028-02-29", "Tuesday", 493)]
    public async Task ADateWithItsYearSaysItsWeekdayAndHowFarItIsFromToday(
        int year, int month, int day, string date, string weekday, int days)
    {
        JsonElement asked = (await Ask($$"""{"year":{{year}},"month":{{month}},"day":{{day}}}""", Observed))
            .GetProperty("calendar").GetProperty("onDate");

        Assert.That(asked.GetRawText(),
            Is.EqualTo($$"""{"date":"{{date}}","weekday":"{{weekday}}","daysFromToday":{{days}}}"""));
    }

    // With no year the model chooses none (it gave this year's 1 January for the one coming, 312 days ago): the coming
    // one, today's included, and the last one before today.
    [TestCase(12, 25, "2026-12-25", "Friday", 62, "2025-12-25", "Thursday", -303)]
    [TestCase(1, 1, "2027-01-01", "Friday", 69, "2026-01-01", "Thursday", -296)]
    [TestCase(9, 18, "2027-09-18", "Saturday", 329, "2026-09-18", "Friday", -36)]
    [TestCase(10, 25, "2026-10-25", "Sunday", 1, "2025-10-25", "Saturday", -364)]
    [TestCase(2, 29, "2028-02-29", "Tuesday", 493, "2024-02-29", "Thursday", -968)]
    public async Task ADayAndMonthWithNoYearSayTheComingOneAndTheLastOne(
        int month, int day, string coming, string comingWeekday, int comingDays, string last, string lastWeekday, int lastDays)
    {
        JsonElement asked = (await Ask($$"""{"month":{{month}},"day":{{day}}}""", Observed))
            .GetProperty("calendar").GetProperty("onDate");

        Assert.Multiple(() =>
        {
            Assert.That(asked.GetProperty("coming").GetRawText(),
                Is.EqualTo($$"""{"date":"{{coming}}","weekday":"{{comingWeekday}}","daysFromToday":{{comingDays}}}"""));
            Assert.That(asked.GetProperty("last").GetRawText(),
                Is.EqualTo($$"""{"date":"{{last}}","weekday":"{{lastWeekday}}","daysFromToday":{{lastDays}}}"""));
        });
    }

    // Today's own day and month: it is the coming one, with no distance to tell.
    [Test]
    public async Task TodaysOwnDateIsTheComingOne()
    {
        JsonElement asked = (await Ask("""{"month":10,"day":24}""", Observed)).GetProperty("calendar").GetProperty("onDate");

        Assert.Multiple(() =>
        {
            Assert.That(asked.GetProperty("coming").GetRawText(), Is.EqualTo("""{"date":"2026-10-24","weekday":"Saturday"}"""));
            Assert.That(asked.GetProperty("last").GetProperty("date").GetString(), Is.EqualTo("2025-10-24"));
        });
    }

    // On a Monday (2026-11-09) and on a Saturday (2026-10-24): the last one before today, the coming one after it and
    // the one in next week, weeks from Monday.
    [TestCase("2026-11-09T22:10:00-03:00", "tuesday", false, "2026-11-03", "2026-11-10", "2026-11-17")]
    [TestCase("2026-11-09T22:10:00-03:00", "Friday", false, "2026-11-06", "2026-11-13", "2026-11-20")]
    [TestCase("2026-11-09T22:10:00-03:00", "sunday", false, "2026-11-08", "2026-11-15", "2026-11-22")]
    [TestCase("2026-11-09T22:10:00-03:00", "monday", true, "2026-11-02", "2026-11-16", "2026-11-16")]
    [TestCase("2026-10-24T15:28:41-03:00", "friday", false, "2026-10-23", "2026-10-30", "2026-10-30")]
    [TestCase("2026-10-24T15:28:41-03:00", "saturday", true, "2026-10-17", "2026-10-31", "2026-10-31")]
    [TestCase("2026-10-24T15:28:41-03:00", "sunday", false, "2026-10-18", "2026-10-25", "2026-11-01")]
    public async Task AWeekdaySaysTheDatesItFallsOn(
        string now, string weekday, bool isToday, string last, string coming, string inNextWeek)
    {
        DateTimeOffset clock = DateTimeOffset.Parse(now, System.Globalization.CultureInfo.InvariantCulture);
        JsonElement asked = (await Ask($$"""{"weekday":"{{weekday}}"}""", clock)).GetProperty("calendar").GetProperty("weekday");
        DateOnly today = DateOnly.FromDateTime(clock.DateTime);
        int Away(string key) => DateOnly.Parse(asked.GetProperty(key).GetProperty("date").GetString()!,
            System.Globalization.CultureInfo.InvariantCulture).DayNumber - today.DayNumber;

        Assert.Multiple(() =>
        {
            Assert.That(asked.GetProperty("name").GetString(), Is.EqualTo(weekday).IgnoreCase);
            Assert.That(asked.GetProperty("isToday").GetBoolean(), Is.EqualTo(isToday));
            Assert.That(asked.GetProperty("last").GetProperty("date").GetString(), Is.EqualTo(last));
            Assert.That(asked.GetProperty("coming").GetProperty("date").GetString(), Is.EqualTo(coming));
            Assert.That(asked.GetProperty("inNextWeek").GetProperty("date").GetString(), Is.EqualTo(inNextWeek));
            foreach (string key in new[] { "last", "coming", "inNextWeek" })
            {
                Assert.That(asked.GetProperty(key).GetProperty("daysFromToday").GetInt32(), Is.EqualTo(Away(key)), key);
            }
        });
    }

    // The PC's own date, not the UTC one: at 22:30 in UTC-3 it is already tomorrow in UTC.
    [Test]
    public async Task TheCalendarCountsFromThePcsOwnDate()
    {
        JsonElement calendar = (await Ask("""{"daysFromToday":1}""", new DateTimeOffset(2026, 11, 10, 1, 30, 0, TimeSpan.Zero)))
            .GetProperty("calendar");

        Assert.Multiple(() =>
        {
            Assert.That(calendar.GetProperty("today").GetProperty("date").GetString(), Is.EqualTo("2026-11-09"));
            Assert.That(calendar.GetProperty("inDays").GetRawText(),
                Is.EqualTo("""{"date":"2026-11-10","weekday":"Tuesday","daysFromToday":1}"""));
        });
    }

    [TestCase("""{"month":2,"day":30}""")]
    [TestCase("""{"month":2,"day":29,"year":2027}""")]
    [TestCase("""{"month":13,"day":1}""")]
    [TestCase("""{"day":27}""")]
    [TestCase("""{"month":11}""")]
    [TestCase("""{"year":2027}""")]
    [TestCase("""{"month":"11","day":27}""")]
    [TestCase("""{"weekday":"viernes"}""")]
    [TestCase("""{"weekday":"3"}""")]
    [TestCase("""{"daysFromToday":1.5}""")]
    [TestCase("""{"daysFromToday":"7"}""")]
    public async Task ADateThatCannotBeReadIsNotGuessed(string arguments)
    {
        var handler = new TimeStatusHandler(new FixedClock(), new Tokyo());

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", JsonDocument.Parse(arguments).RootElement.Clone()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("time_date_invalid"));
            Assert.That(OperationVisibleFacts.FromOutcome("system.time", outcome), Does.Contain("\"month\":\"1 to 12, with day\""));
        });
    }

    // A reading that asks for no date says none, as before; null arguments ask for none.
    [TestCase("{}")]
    [TestCase("""{"day":null,"daysFromToday":null,"month":null,"place":null,"weekday":null,"year":null}""")]
    public async Task AReadingThatAsksForNoDateCarriesNoCalendar(string arguments)
    {
        JsonElement result = await Ask(arguments, Observed);

        Assert.That(result.EnumerateObject().Select(property => property.Name),
            Is.EqualTo(new[] { "version", "utc", "localUtcOffsetMinutes", "localTime" }));
    }

    // What the model reads of it (OperationVisibleFacts): the calendar whole, with its dates and weekdays.
    [Test]
    public async Task TheModelReadsTheCalendar()
    {
        var handler = new TimeStatusHandler(new FixedClock(), new Tokyo());
        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation",
                JsonDocument.Parse("""{"daysFromToday":7,"weekday":"friday"}""").RootElement.Clone()),
            CancellationToken.None);

        string seen = OperationVisibleFacts.FromOutcome("system.time", outcome);

        Assert.Multiple(() =>
        {
            Assert.That(seen, Does.Contain("""
                "inDays":{"date":"2026-10-31","weekday":"Saturday","daysFromToday":7}
                """.Trim()));
            Assert.That(seen, Does.Contain("""
                "weekday":{"name":"Friday","isToday":false,"last":{"date":"2026-10-23","daysFromToday":-1},"coming":{"date":"2026-10-30","daysFromToday":6},"inNextWeek":{"date":"2026-10-30","daysFromToday":6}}
                """.Trim()));
        });
    }

    // The catalog takes the three arguments as it types them, and nothing else.
    [TestCase("""{"daysFromToday":15}""", true)]
    [TestCase("""{"month":11,"day":27}""", true)]
    [TestCase("""{"month":11,"day":27,"year":2027}""", true)]
    [TestCase("""{"weekday":"friday"}""", true)]
    [TestCase("""{"weekday":"viernes"}""", false)]
    [TestCase("""{"daysFromToday":"15"}""", false)]
    [TestCase("""{"daysFromToday":40000}""", false)]
    [TestCase("""{"month":0,"day":27}""", false)]
    [TestCase("""{"date":"2026-11-27"}""", false)]
    public void TheCatalogTypesTheDateAsked(string arguments, bool valid)
    {
        Assert.That(ProductCatalog.TryGet("system.time", out ProductOperationDescriptor? descriptor), Is.True);

        Assert.That(OperationArgumentValidator.IsValid(JsonDocument.Parse(arguments).RootElement, descriptor!.ArgumentsSchema),
            Is.EqualTo(valid));
    }

    private static async Task<JsonElement> Ask(string arguments, DateTimeOffset now)
    {
        var handler = new TimeStatusHandler(new ClockAt(now), new Tokyo());
        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", JsonDocument.Parse(arguments).RootElement.Clone()),
            CancellationToken.None);
        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        return outcome.Result!.Value;
    }

    private sealed class ClockAt(DateTimeOffset now) : ITimeStatusProvider
    {
        public ValueTask<TimeStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken) =>
            ValueTask.FromResult<TimeStatusSnapshot?>(new TimeStatusSnapshot(now.ToUniversalTime(), -180));
    }

    private static async Task<JsonElement> Read()
    {
        var handler = new TimeStatusHandler(new FixedClock(), new Tokyo());
        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation",
                JsonDocument.Parse("""{"place":"Tokio"}""").RootElement.Clone()),
            CancellationToken.None);
        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        return outcome.Result!.Value;
    }

    private sealed class FixedClock : ITimeStatusProvider
    {
        public ValueTask<TimeStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken) =>
            ValueTask.FromResult<TimeStatusSnapshot?>(new TimeStatusSnapshot(Observed, -180));
    }

    private sealed class Tokyo : IPlaceTimeZoneResolver
    {
        public ValueTask<PlaceTimeZoneReading> ResolveAsync(string place, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new PlaceTimeZoneReading(
                new PlaceTimeZone("Tokio", "Japón", TimeZoneInfo.FindSystemTimeZoneById("Asia/Tokyo"), "test"),
                null));
    }

    private sealed class Namesakes : IPlaceTimeZoneResolver
    {
        public ValueTask<PlaceTimeZoneReading> ResolveAsync(string place, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new PlaceTimeZoneReading(null, "time_place_ambiguous", JsonDocument.Parse(
                """{"version":1,"requested":"Georgia","candidateCount":2,"candidates":[{"name":"Georgia","region":"Georgia","country":"Estados Unidos"},{"name":"Georgia","country":"Georgia"}]}""")
                .RootElement.Clone()));
    }
}
