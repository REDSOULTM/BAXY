using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew (2026-10-15): schedule takes the person's time — minutes or seconds from now, or a local clock time —
/// and never asks the model for UTC (e2e E004: dueUtc written wrong, the failing call retried 15 times).
/// </summary>
[TestFixture]
public sealed class ScheduleTimeTests
{
    private static readonly DateTimeOffset Now =
        new(new DateTime(2026, 10, 15, 16, 40, 0, DateTimeKind.Local));

    private static bool Due(string json, out DateTimeOffset due)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        JsonElement arguments = document.RootElement;
        string? at = arguments.TryGetProperty("at", out JsonElement value) ? value.GetString() : null;
        return WindowsScheduledNotificationAdapter.TryDue(arguments, at, Now, out due);
    }

    [Test]
    public void Minutes_and_seconds_count_from_now()
    {
        Assert.Multiple(() =>
        {
            Assert.That(Due("""{"inMinutes":20}""", out DateTimeOffset minutes), Is.True);
            Assert.That(minutes, Is.EqualTo(Now.AddMinutes(20)));
            Assert.That(Due("""{"inSeconds":90}""", out DateTimeOffset seconds), Is.True);
            Assert.That(seconds, Is.EqualTo(Now.AddSeconds(90)));
        });
    }

    [Test]
    public void A_clock_time_is_the_next_time_that_clock_comes()
    {
        Assert.Multiple(() =>
        {
            Assert.That(Due("""{"at":"18:30"}""", out DateTimeOffset later), Is.True);
            Assert.That(later.LocalDateTime, Is.EqualTo(new DateTime(2026, 10, 15, 18, 30, 0)));
            Assert.That(Due("""{"at":"7:00"}""", out DateTimeOffset tomorrow), Is.True);
            Assert.That(tomorrow.LocalDateTime, Is.EqualTo(new DateTime(2026, 10, 16, 7, 0, 0)));
            Assert.That(Due("""{"at":"2026-10-20T08:15"}""", out DateTimeOffset dated), Is.True);
            Assert.That(dated.LocalDateTime, Is.EqualTo(new DateTime(2026, 10, 20, 8, 15, 0)));
        });
    }

    // On the real Task Scheduler of this PC: a reminder 30 minutes from now is set, listed with its local time and
    // cancelled, and its task is gone. Nothing rings: it is cancelled long before.
    [Test]
    [Explicit("Registers one real BAXY reminder task in the user's Task Scheduler and cancels it.")]
    public async Task A_reminder_is_set_listed_and_cancelled_on_the_real_scheduler()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-schedule-live-" + Guid.NewGuid().ToString("N"));
        using var cleanup = new Cleanup(root);
        var adapter = new WindowsScheduledNotificationAdapter(root);
        async Task<ExternalCapabilityReceipt> Run(string json)
        {
            using JsonDocument document = JsonDocument.Parse(json);
            return await adapter.InvokeAsync("schedule.alarms", document.RootElement.Clone(), CancellationToken.None);
        }

        ExternalCapabilityReceipt created = await Run(
            """{"action":"create","kind":"reminder","title":"Prueba de BAXY","inMinutes":30}""");
        ExternalCapabilityReceipt listed = await Run("""{"action":"list"}""");
        ExternalCapabilityReceipt cancelled = await Run("""{"action":"cancel","kind":"reminder"}""");
        ExternalCapabilityReceipt after = await Run("""{"action":"list"}""");

        Assert.Multiple(() =>
        {
            Assert.That(created.Verified, Is.True, created.ErrorCode);
            Assert.That(created.Result?.GetProperty("dueLocal").GetString(),
                Is.EqualTo(DateTime.Now.AddMinutes(30).ToString("yyyy-MM-dd HH:mm",
                    System.Globalization.CultureInfo.InvariantCulture)).Or.EqualTo(DateTime.Now.AddMinutes(31)
                    .ToString("yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(listed.Verified, Is.True, listed.ErrorCode);
            Assert.That(listed.Result?.ToString(), Does.Contain("Prueba de BAXY"));
            Assert.That(cancelled.Verified, Is.True, cancelled.ErrorCode);
            Assert.That(after.Result?.ToString(), Does.Not.Contain("Prueba de BAXY"));
        });
    }

    // On the real scheduler: a reminder 15 seconds from now rings, and its receipt — written after ringing — says the
    // Windows notification was read back from the notification history and which sound played.
    [Test]
    [Explicit("Rings one real BAXY reminder on this PC (a notification and a sound).")]
    public async Task A_reminder_rings_with_a_notification_read_back_from_the_history()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-schedule-ring-" + Guid.NewGuid().ToString("N"));
        using var cleanup = new Cleanup(root);
        var adapter = new WindowsScheduledNotificationAdapter(root);
        using JsonDocument request = JsonDocument.Parse(
            """{"action":"create","kind":"reminder","title":"Prueba de BAXY: este aviso se puede cerrar","inSeconds":15}""");
        ExternalCapabilityReceipt created = await adapter.InvokeAsync(
            "schedule.alarms", request.RootElement.Clone(), CancellationToken.None);
        Assert.That(created.Verified, Is.True, created.ErrorCode);
        string receipt = Path.Combine(root, "scheduled-notifications",
            created.Result!.Value.GetProperty("taskName").GetString() + ".fired");
        DateTime deadline = DateTime.UtcNow.AddSeconds(90);
        while (!File.Exists(receipt) && DateTime.UtcNow < deadline)
            await Task.Delay(500);
        await Task.Delay(500);
        using JsonDocument rang = JsonDocument.Parse(File.ReadAllText(receipt));
        Assert.Multiple(() =>
        {
            Assert.That(rang.RootElement.GetProperty("notificationShown").GetBoolean(), Is.True, rang.RootElement.ToString());
            Assert.That(rang.RootElement.GetProperty("sound").GetString(), Is.AnyOf("wav", "beep"));
        });
    }

    private sealed class Cleanup(string path) : IDisposable
    {
        public void Dispose()
        {
            if (Directory.Exists(path)) Directory.Delete(path, recursive: true);
        }
    }

    [TestCase("""{}""")]
    [TestCase("""{"inMinutes":0}""")]
    [TestCase("""{"inSeconds":3}""")]
    [TestCase("""{"at":"25:00"}""")]
    [TestCase("""{"at":"a las siete"}""")]
    public void Anything_else_is_not_a_time(string json) =>
        Assert.That(Due(json, out _), Is.False);
}
