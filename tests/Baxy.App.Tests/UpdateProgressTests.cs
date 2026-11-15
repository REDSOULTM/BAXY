using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// AUT2: the download done with BAXY open is said and shown with what the installer wrote, each line when it is true, and
/// minutes only when the pace was measured.
/// </summary>
[TestFixture]
internal sealed class UpdateProgressTests
{
    private const long Total = 94_000_000;

    [Test]
    public void ItSaysTheSizeThenHalfWithTheMeasuredMinutesThenThatItClosesForTheSwitch()
    {
        Clock clock = new(new DateTimeOffset(2026, 11, 14, 1, 0, 0, TimeSpan.Zero));
        UpdateProgress teller = new(english: false, clock);

        string? size = teller.Next(Reading("downloading", 1_000_000));
        clock.Advance(TimeSpan.FromSeconds(10));
        string? quiet = teller.Next(Reading("downloading", 2_000_000));
        clock.Advance(TimeSpan.FromSeconds(450));
        string? half = teller.Next(Reading("downloading", 47_000_000));
        string? again = teller.Next(Reading("downloading", 60_000_000));
        string? end = teller.Next(Reading("fetched", Total));

        Assert.Multiple(() =>
        {
            Assert.That(size, Is.EqualTo("Bajo lo que cambió de la 1.5.4: 94 MB."));
            Assert.That(quiet, Is.Null);
            // 46 MB in 460 s: 0.1 MB/s, 47 MB left → 470 s → 8 minutes.
            Assert.That(half, Is.EqualTo("Voy en la mitad: 47 de 94 MB. Faltan unos 8 minutos."));
            Assert.That(again, Is.Null);
            Assert.That(end, Does.StartWith("Ya bajé todo."));
            Assert.That(teller.Next(Reading("fetched", Total)), Is.Null, "each line once");
        });
    }

    [Test]
    public void MinutesAreNotSaidBeforeThePaceWasMeasuredNorWhenLessThanOneIsLeft()
    {
        Clock clock = new(new DateTimeOffset(2026, 11, 14, 1, 0, 0, TimeSpan.Zero));
        UpdateProgress early = new(english: true, clock);
        _ = early.Next(Reading("downloading", 0));
        clock.Advance(TimeSpan.FromSeconds(2));
        Assert.That(early.Next(Reading("downloading", 50_000_000)), Is.EqualTo("I’m halfway: 50 of 94 MB."));

        UpdateProgress fast = new(english: false, clock);
        _ = fast.Next(Reading("downloading", 0));
        clock.Advance(TimeSpan.FromSeconds(10));
        Assert.That(fast.Next(Reading("downloading", 50_000_000)), Is.EqualTo("Voy en la mitad: 50 de 94 MB."));
    }

    [Test]
    public void AShortDownloadOrAFailureOrNothingWrittenSaysNothing()
    {
        UpdateProgress teller = new(english: false);
        Assert.That(teller.Next(null), Is.Null);
        Assert.That(teller.Next(Reading("downloading", 1_000, total: 5_000_000)), Is.Null);
        Assert.That(teller.Next(Reading("fetched", 5_000_000, total: 5_000_000)), Is.Null, "nothing was said of it before");
        Assert.That(new UpdateProgress(english: false).Next(Reading("failed", 0)), Is.Null);
    }

    private static JsonObject Reading(string phase, long done, long total = Total) => new()
    {
        ["version"] = "1.5.4",
        ["phase"] = phase,
        ["done"] = done,
        ["total"] = total,
    };

    private sealed class Clock(DateTimeOffset now) : TimeProvider
    {
        private DateTimeOffset now = now;

        public override DateTimeOffset GetUtcNow() => now;

        internal void Advance(TimeSpan by) => now += by;
    }
}
