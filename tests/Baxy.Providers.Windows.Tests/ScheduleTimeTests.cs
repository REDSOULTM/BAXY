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

    // Encargo 57 (banco de uso U35): «despiértame mañana a las 7» went as a date and time that had already passed that
    // day. Nothing is scheduled; the refusal says so, the time asked and the time here, and its next ends with the same
    // call at that clock time alone, which sets the next time that clock comes.
    [Test]
    public async Task A_date_and_time_already_past_says_nothing_is_set_and_gives_the_call_at_the_clock_time_alone()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-schedule-past-" + Guid.NewGuid().ToString("N"));
        using var cleanup = new Cleanup(root);
        ScriptedNotificationBackend backend = ScriptedNotificationBackend.Registering();
        var adapter = new WindowsScheduledNotificationAdapter(root, backend);
        DateTime asked = DateTime.Now.AddHours(-2);
        string at = asked.ToString("yyyy-MM-ddTHH:mm", System.Globalization.CultureInfo.InvariantCulture);
        string clock = asked.ToString("HH:mm", System.Globalization.CultureInfo.InvariantCulture);
        using JsonDocument request = JsonDocument.Parse(
            $$"""{"action":"create","at":"{{at}}","kind":"alarm","title":"Prueba"}""");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", request.RootElement.Clone(), CancellationToken.None);

        string next = receipt.Result?.GetProperty("next").GetString() ?? "";
        string call = Baxy.Kernel.Operations.WireNames.Call("schedule.alarms", new()
        {
            ["action"] = "create", ["kind"] = "alarm", ["at"] = clock, ["title"] = "Prueba",
        });
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_schedule_invalid"));
            Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(backend.Requests, Is.Empty);
            Assert.That(receipt.Result?.GetProperty("dueLocal").GetString(), Is.EqualTo(at.Replace('T', ' ')));
            Assert.That(receipt.Result?.GetProperty("nowLocal").GetString(), Does.StartWith(
                DateTime.Now.ToString("yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(receipt.Result?.GetProperty("scheduled").GetBoolean(), Is.False);
            Assert.That(next, Does.StartWith("nothing is set yet: " + at.Replace('T', ' ') + " had already passed"));
            Assert.That(next, Does.EndWith(", call " + call));
            Assert.That(next, Does.Contain("to set it for " + asked.AddDays(1).ToString("yyyy-MM-dd",
                System.Globalization.CultureInfo.InvariantCulture) + " " + clock));
        });
    }

    // Encargo 59: «ponme una alarma hoy a las 9» after 9 went as at "09:00", which sets the next 9:00, tomorrow, and the
    // model answered «quedó para hoy a las 9» from a dueLocal it had to compare with today's date itself. The receipt
    // says the day in calendar words relative to today, and that a clock time already past today moved to tomorrow,
    // with the time here.
    [Test]
    public async Task A_set_alarm_says_its_day_relative_to_today_and_that_a_clock_time_past_today_moved_to_tomorrow()
    {
        Assume.That(DateTime.Now.TimeOfDay, Is.InRange(TimeSpan.FromMinutes(1), new TimeSpan(23, 50, 0)));
        string root = Path.Combine(Path.GetTempPath(), "baxy-schedule-day-" + Guid.NewGuid().ToString("N"));
        using var cleanup = new Cleanup(root);
        var adapter = new WindowsScheduledNotificationAdapter(root, ScriptedNotificationBackend.Registering());
        async Task<JsonElement> Set(string json)
        {
            using JsonDocument document = JsonDocument.Parse(json);
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "schedule.alarms", document.RootElement.Clone(), CancellationToken.None);
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            return receipt.Result!.Value;
        }

        DateTime later = DateTime.Today.AddDays(3).AddHours(8);
        JsonElement passed = await Set("""{"action":"create","kind":"alarm","at":"00:00"}""");
        JsonElement tonight = await Set("""{"action":"create","kind":"alarm","at":"23:59"}""");
        JsonElement timer = await Set("""{"action":"create","kind":"reminder","inMinutes":5}""");
        JsonElement dated = await Set($$"""{"action":"create","kind":"alarm","at":"{{later:yyyy-MM-ddTHH:mm}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(passed.GetProperty("scheduledFor").GetString(), Is.EqualTo("tomorrow"));
            Assert.That(passed.GetProperty("movedToNextDay").GetBoolean(), Is.True);
            Assert.That(passed.GetProperty("nowLocal").GetString(), Does.StartWith(
                DateTime.Today.ToString("yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(tonight.GetProperty("scheduledFor").GetString(), Is.EqualTo("today"));
            Assert.That(tonight.TryGetProperty("movedToNextDay", out _), Is.False);
            Assert.That(tonight.TryGetProperty("nowLocal", out _), Is.False);
            Assert.That(timer.GetProperty("scheduledFor").GetString(), Is.EqualTo("today"));
            Assert.That(timer.TryGetProperty("movedToNextDay", out _), Is.False);
            Assert.That(dated.GetProperty("scheduledFor").GetString(), Is.EqualTo(
                later.ToString("dddd yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(dated.TryGetProperty("movedToNextDay", out _), Is.False);
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
