using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Uso real tanda 4 «convertir nueve de la mañana huso horario a madrid»: la hora
/// de otro lugar es este reloj leído junto al desfase de la zona de ese lugar en
/// el mismo instante; sin lugar, la lectura es la de siempre.
/// </summary>
[TestFixture]
public sealed class TimeStatusHandlerTests
{
    private static readonly DateTimeOffset Instant = new(2026, 9, 24, 11, 18, 52, TimeSpan.Zero);

    [Test]
    public void ThePlaceIsAnOptionalReadOnlyArgument()
    {
        var handler = new TimeStatusHandler(new FixedClock(), new Places());

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.ReadOnly));
            Assert.That(handler.Definition.ProductDescriptor!.ArgumentsSchema.CanonicalJson, Does.Contain("\"place\""));
            Assert.That(handler.Definition.ProductDescriptor!.ArgumentsSchema.Required, Is.Empty);
        });
    }

    [Test]
    public async Task WithoutAPlaceTheClockIsReadAlone()
    {
        var places = new Places();
        OperationOutcome outcome = await new TimeStatusHandler(new FixedClock(), places)
            .ExecuteAsync(Invocation("{}"), CancellationToken.None);

        JsonElement result = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Verified, Is.True);
            Assert.That(places.Asked, Is.Empty);
            Assert.That(result.GetProperty("localUtcOffsetMinutes").GetInt32(), Is.EqualTo(-180));
            Assert.That(result.TryGetProperty("place", out _), Is.False);
        });
    }

    [Test]
    public async Task ANamedPlaceCarriesItsZoneOffsetAtTheSameInstant()
    {
        var places = new Places();
        OperationOutcome outcome = await new TimeStatusHandler(new FixedClock(), places)
            .ExecuteAsync(Invocation("""{"place":"madrid"}"""), CancellationToken.None);

        JsonElement place = outcome.Result!.Value.GetProperty("place");
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Verified, Is.True);
            Assert.That(places.Asked, Is.EqualTo(new[] { "madrid" }));
            Assert.That(outcome.Result!.Value.GetProperty("utc").GetString(), Does.StartWith("2026-09-24T11:18:52"));
            Assert.That(place.GetProperty("name").GetString(), Is.EqualTo("Madrid"));
            Assert.That(place.GetProperty("country").GetString(), Is.EqualTo("España"));
            Assert.That(place.GetProperty("timeZone").GetString(), Is.EqualTo("Europe/Madrid"));
            // Central European Summer Time on that day.
            Assert.That(place.GetProperty("utcOffsetMinutes").GetInt32(), Is.EqualTo(120));
            Assert.That(place.GetProperty("authority").GetString(), Is.EqualTo("named_place_geocoded"));
        });
    }

    [Test]
    public async Task APlaceWithoutAZoneFailsWithItsCauseAndReadsNoClock()
    {
        var clock = new FixedClock();
        OperationOutcome outcome = await new TimeStatusHandler(clock, new Places())
            .ExecuteAsync(Invocation("""{"place":"canada"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("time_place_zone_ambiguous"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(clock.Reads, Is.Zero);
        });
    }

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(json).RootElement.Clone());

    private sealed class FixedClock : ITimeStatusProvider
    {
        public int Reads { get; private set; }

        public ValueTask<TimeStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken)
        {
            Reads++;
            return ValueTask.FromResult<TimeStatusSnapshot?>(new TimeStatusSnapshot(Instant, -180));
        }
    }

    private sealed class Places : IPlaceTimeZoneResolver
    {
        public List<string> Asked { get; } = [];

        public ValueTask<PlaceTimeZoneReading> ResolveAsync(string place, CancellationToken cancellationToken)
        {
            Asked.Add(place);
            return ValueTask.FromResult(place == "madrid"
                ? new PlaceTimeZoneReading(
                    new PlaceTimeZone("Madrid", "España", TimeZoneInfo.FindSystemTimeZoneById("Europe/Madrid"), "named_place_geocoded"),
                    null)
                : new PlaceTimeZoneReading(null, "time_place_zone_ambiguous"));
        }
    }
}
