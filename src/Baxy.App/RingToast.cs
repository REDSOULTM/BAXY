using System.Security;
using Baxy.Providers.Windows.External;
using Windows.Data.Xml.Dom;
using Windows.UI.Notifications;

namespace Baxy.App;

/// <summary>
/// The Windows notifications of what the App rings, both under the toast's AppUserModelID (<see cref="ProposalToast.AppId"/>).
/// <para>ALR5 (A3, VIVO1 N6): with BAXY's window minimized or behind, an alarm or reminder the App rang (<see cref="AlarmRinger"/>)
/// showed nothing on screen: its card is in the window. Each one ringing then shows a Windows notification with the card's
/// two buttons, answered through the same schedule.alarms stop or snooze; it goes when the ring ends, however it ended.
/// An alarm's uses Windows' «alarm» scenario (it stays on screen, with its buttons, until it is answered or dismissed) and a
/// reminder's the «reminder» one, as Microsoft Learn's «App notification content» says of both; silent, since the App
/// plays the ring's own tone (the toast's audio element, silent). The App rings, the toast only shows and answers.</para>
/// <para>APP1 (ALR-1 and ALR-2, review of the App 2026-11-09): <see cref="RingInWindows"/> is Windows' own notification of a
/// ring the App took and cannot sound (its tone did not play, or the loop that rings keeps failing). It is the notification
/// the ring script shows with BAXY closed (<see cref="ScheduledRingScript.ToastXml"/>): BAXY, the ring's words and its time,
/// as an alarm (Windows' looping alarm sound) or a reminder, with Windows' own Snooze and Dismiss. Windows' toast schema,
/// scenario «alarm»: «An alarm notification. […] Audio will loop by default and will use alarm audio»
/// (https://learn.microsoft.com/uwp/schemas/tiles/toastschema/element-toast, read 2026-11-09). An alarm's is removed at
/// <see cref="ScheduledRingScript.AlarmCap"/>, as the script removes its own. That ring's status is then «windows», not
/// «ringing», so the silent one above goes (PresenceHost) and only Windows' rings it.</para>
/// </summary>
internal sealed class RingToast
{
    private readonly Dictionary<string, ToastNotification> _shown = new(StringComparer.Ordinal);

    /// <summary>The notification for <paramref name="ring"/>: its kind and clock, the person's words, and the card's buttons
    /// (their arguments «snooze:id» and «stop:id»; a click on the rest, «open:id»).</summary>
    internal static string Xml(RingNow ring, bool english)
    {
        ArgumentNullException.ThrowIfNull(ring);
        bool alarm = ring.Kind == "alarm";
        string head = (alarm ? UiLanguage.Say(english, "Alarma", "Alarm") : UiLanguage.Say(english, "Recordatorio", "Reminder"))
            + " · " + ring.Clock;
        string snooze = alarm ? UiLanguage.Say(english, "Posponer 10 min", "Snooze 10 min")
            : UiLanguage.Say(english, "Recordar en 10 min", "Remind in 10 min");
        string stop = alarm ? UiLanguage.Say(english, "Parar", "Stop") : UiLanguage.Say(english, "Listo", "Done");
        return "<toast scenario=\"" + (alarm ? "alarm" : "reminder") + "\" launch=\"open:" + Escape(ring.Id) + "\">"
            + "<visual><binding template=\"ToastGeneric\"><text>" + Escape(head) + "</text><text>"
            + Escape(ring.Title ?? ring.Words) + "</text></binding></visual><audio silent=\"true\"/><actions>"
            + "<action content=\"" + Escape(snooze) + "\" arguments=\"snooze:" + Escape(ring.Id) + "\" activationType=\"foreground\"/>"
            + "<action content=\"" + Escape(stop) + "\" arguments=\"stop:" + Escape(ring.Id) + "\" activationType=\"foreground\"/>"
            + "</actions></toast>";
    }

    /// <summary>What a press on the notification asks: (stop|snooze|open, id), or null for anything else.</summary>
    internal static (string Action, string Id)? Pressed(string? arguments) =>
        arguments?.Split(':', 2) is [("stop" or "snooze" or "open") and var action, { Length: > 0 } id] ? (action, id) : null;

    /// <summary>Shows <paramref name="ring"/>'s notification once; a press goes to <paramref name="press"/> (any thread), and
    /// so does its closing by the person, as («dismissed», id). False when Windows did not take it.</summary>
    internal bool Show(RingNow ring, bool english, Action<string, string> press)
    {
        ArgumentNullException.ThrowIfNull(ring);
        ArgumentNullException.ThrowIfNull(press);
        if (_shown.ContainsKey(ring.Id))
        {
            return true;
        }

        try
        {
            ProposalToast.Register();
            var xml = new XmlDocument();
            xml.LoadXml(Xml(ring, english));
            var toast = new ToastNotification(xml) { Tag = ring.Id, ExpirationTime = DateTimeOffset.Now.AddHours(1) };
            toast.Activated += (_, args) =>
            {
                if (args is ToastActivatedEventArgs activated && Pressed(activated.Arguments) is var (action, id))
                {
                    press(action, id);
                }
            };
            toast.Dismissed += (_, args) =>
            {
                if (args.Reason == ToastDismissalReason.UserCanceled)
                {
                    press("dismissed", ring.Id);
                }
            };
            ToastNotificationManager.CreateToastNotifier(ProposalToast.AppId).Show(toast);
            _shown[ring.Id] = toast;
            return true;
        }
        catch (Exception exception) when (exception is InvalidOperationException or ArgumentException
            or UnauthorizedAccessException or SecurityException or System.Runtime.InteropServices.COMException)
        {
            return false;
        }
    }

    /// <summary>Windows took the notification of <paramref name="id"/> off the screen (pressed or closed): while it still
    /// rings, <see cref="Show"/> shows it again (ALR5's blind review: closed once, it never came back).</summary>
    internal void Forget(string id) => _shown.Remove(id);

    /// <summary>The ring <paramref name="id"/> no longer rings (answered here, by voice, on the card, or it ran its time):
    /// its notification goes.</summary>
    internal void Hide(string id)
    {
        if (!_shown.Remove(id, out ToastNotification? toast))
        {
            return;
        }

        try
        {
            ToastNotificationManager.CreateToastNotifier(ProposalToast.AppId).Hide(toast);
        }
        catch (Exception exception) when (exception is ArgumentException or System.Runtime.InteropServices.COMException)
        {
            // Already gone from the action center.
        }
    }

    /// <summary>APP1: Windows' own notification of a ring the App cannot sound; false when Windows did not take it.</summary>
    internal static bool RingInWindows(RingNow ring)
    {
        ArgumentNullException.ThrowIfNull(ring);
        try
        {
            ProposalToast.Register();
            var xml = new XmlDocument();
            xml.LoadXml(ScheduledRingScript.ToastXml(ring.Kind, ring.Title, ring.Clock));
            string tag = "ring-" + ring.Id;
            ToastNotificationManager.CreateToastNotifier(ProposalToast.AppId).Show(new ToastNotification(xml) { Tag = tag });
            if (ring.Kind == "alarm")
            {
                _ = RemoveAtTheCapAsync(tag);
            }

            return true;
        }
        catch (Exception exception) when (exception is InvalidOperationException or ArgumentException
            or UnauthorizedAccessException or SecurityException or System.Runtime.InteropServices.COMException)
        {
            return false;
        }
    }

    // An alarm's notification nobody answered stops looping at the cap, as the ring script's does.
    private static async Task RemoveAtTheCapAsync(string tag)
    {
        await Task.Delay(ScheduledRingScript.AlarmCap).ConfigureAwait(false);
        try
        {
            ToastNotificationManager.History.Remove(tag, string.Empty, ProposalToast.AppId);
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.Runtime.InteropServices.COMException)
        {
            // Already answered: it is no longer in the action center.
        }
    }

    private static string Escape(string text) => SecurityElement.Escape(text) ?? string.Empty;
}
