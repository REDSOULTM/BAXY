using System.Globalization;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// GUA1 (VIVO13, 11-11-2026): «¿Qué alarmas tengo puestas?» → «programada para hoy a las 09:15» with nextRunLocal
// 2026-11-12 09:15. The list tells each one's day relative to today, counted by the tool in local days.
public sealed class AlarmListDayTests
{
    private static string DayOf(DateTimeOffset next, DateTimeOffset now)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            WindowsScheduledNotificationAdapter.WriteDay(
                writer, next.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture), now);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(Encoding.UTF8.GetString(stream.ToArray()));
        return document.RootElement.GetProperty("nextRunDay").GetString()!;
    }

    [TestCase(0, 9, 15, "today")]
    [TestCase(1, 9, 15, "tomorrow")]
    [TestCase(1, 0, 5, "tomorrow")]
    [TestCase(3, 7, 0, "in 3 days")]
    public void TheDayIsCountedInLocalDays(int days, int hour, int minute, string expected)
    {
        DateTime today = DateTime.Today;
        var now = new DateTimeOffset(today.AddHours(22));
        var next = new DateTimeOffset(today.AddDays(days).AddHours(hour).AddMinutes(minute));

        Assert.That(DayOf(next, now), Is.EqualTo(expected));
    }

    [Test]
    public void LateAtNightAnAlarmAfterMidnightIsTomorrow()
    {
        DateTime today = DateTime.Today;
        var now = new DateTimeOffset(today.AddHours(23).AddMinutes(50));
        var next = new DateTimeOffset(today.AddDays(1).AddMinutes(10));

        Assert.That(DayOf(next, now), Is.EqualTo("tomorrow"));
    }
}
