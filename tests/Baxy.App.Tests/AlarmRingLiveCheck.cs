using System.IO;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.UI.Notifications;

namespace Baxy.App.Tests;

/// <summary>
/// APP1 (ALR-1), on the real desktop, opt-in only (Explicit and BAXY_RING_LIVE_CHECK=1): the loop that rings is forced to
/// fail (its tone throws on every tick) with an alarm handed over in a folder of the test's own. After
/// <see cref="AlarmRinger.FailedTicks"/> ticks the alarm must ring as Windows' own notification (it shows on screen and
/// sounds Windows' alarm for the few seconds this check leaves it), its card must say «windows», and the folder must be
/// released. The notification is removed by its tag at the end.
/// </summary>
[TestFixture]
[Explicit("Shows a Windows alarm notification, with its sound, on the person's desktop.")]
public sealed class AlarmRingLiveCheck
{
    private const string Alarm = "BAXY-Alarm-0123456789abcdef0123456789abcdef";

    [Test]
    public async Task ALoopForcedToFailRingsTheAlarmAsWindowsOwnNotification()
    {
        if (Environment.GetEnvironmentVariable("BAXY_RING_LIVE_CHECK") != "1")
        {
            Assert.Ignore("BAXY_RING_LIVE_CHECK=1 is needed to show a notification on the desktop.");
        }

        string root = Path.Combine(Path.GetTempPath(), "baxy-ring-live-" + Guid.NewGuid().ToString("N"));
        string folder = Path.Combine(root, "scheduled-notifications");
        var statuses = new List<string>();
        var kept = new List<string>();
        const string Tag = "ring-89abcdef";
        try
        {
            using var ringer = new AlarmRinger(
                folder,
                new RingOutput(
                    static (_, _) => throw new NotSupportedException("the loop is forced to fail"),
                    static () => { },
                    static _ => { },
                    static () => false,
                    RingToast.RingInWindows),
                static () => false,
                static () => false,
                failed: failure => kept.Add(failure.GetType().Name));
            ringer.Start();
            ringer.Changed += ring => statuses.Add(ring.Status);
            File.WriteAllText(Path.Combine(folder, Alarm + AlarmRingHandoff.DueExtension),
                new JsonObject { ["rangUtc"] = DateTimeOffset.UtcNow.ToString("O"), ["clock"] = "07:00", ["title"] = "prueba de APP1" }.ToJsonString());

            using var closing = new CancellationTokenSource();
            Task loop = ringer.RunAsync(TimeSpan.FromMilliseconds(500), static () => DateTimeOffset.UtcNow, closing.Token);
            await Task.Delay(TimeSpan.FromSeconds(6));
            bool alive = !loop.IsCompleted;
            bool shown = ToastNotificationManager.History.GetHistory(ProposalToast.AppId).Any(static toast => toast.Tag == Tag);
            await closing.CancelAsync();
            await loop;

            Assert.Multiple(() =>
            {
                Assert.That(alive, Is.True, "the loop outlives its failed ticks");
                Assert.That(kept, Has.Count.EqualTo(AlarmRinger.FailedTicks));
                Assert.That(statuses, Is.EqualTo(new[] { "ringing", "windows" }));
                Assert.That(shown, Is.True, "Windows keeps the alarm's notification");
                Assert.That(AlarmRingHandoff.AppHolds(folder), Is.False);
            });
        }
        finally
        {
            ToastNotificationManager.History.Remove(Tag, string.Empty, ProposalToast.AppId);
            Directory.Delete(root, recursive: true);
        }
    }
}
