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
                Is.EqualTo(new[] { "version", "utc", "localUtcOffsetMinutes", "place" }));
            Assert.That(result.GetProperty("place").EnumerateObject().Select(property => property.Name),
                Is.EqualTo(new[] { "name", "country", "timeZone", "utcOffsetMinutes", "authority" }));
        });
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
}
