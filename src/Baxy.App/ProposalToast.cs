using System.Security;
using Microsoft.Win32;
using Windows.Data.Xml.Dom;
using Windows.UI.Notifications;

namespace Baxy.App;

/// <summary>
/// A heartbeat's proposal while the person plays, is in a call or watches something (design v4: «llega como
/// notificación de Windows» with Sí / No). The answer goes to the same confirmation as the card's buttons
/// (<see cref="MainWindowViewModel.AnswerConfirmationAsync"/>); the toast never brings BAXY's window forward. An
/// unpackaged app shows toasts under an AppUserModelID registered for the current user
/// (HKCU\Software\Classes\AppUserModelId), as Windows documents for desktop apps.
/// </summary>
internal sealed class ProposalToast
{
    internal const string AppId = "BAXY.Product.App";

    // What Windows takes to bring a toast up once it has it, which nothing tells an app: 284 to 532 ms measured from
    // Show's return to its first pixel (OVL1, 80 toasts on one notebook), 322 to 627 ms for one that takes the place of
    // another (12), and it tells of a press 39 to 119 ms after it.
    private const int UpAllowance = 500;
    private readonly object _gate = new();
    private Action? _hide;
    private int _showing;

    /// <summary>
    /// OVL1: how long a toast must have been with Windows before its Sí answers. A toast comes up over whatever the
    /// person is clicking on, and Windows takes a press on its button from some 60 ms after it shows (measured). Windows
    /// draws the toast: it cannot be shown off, and all an app knows of a press is when Windows told of it. So the wait
    /// is the overlay's Sí's (<see cref="ApprovalGuard"/>) and what the toast takes to come up, counted from handing it
    /// to Windows: by those measures, some 750 ms on the screen at the least. A Sí that comes sooner does not answer;
    /// Windows took the toast away with the press, and a second one would come up later still, with nothing to say
    /// when (0.7 to 1.6 s measured), so the person is told plainly that the proposal still waits and answers it on its
    /// card. The No always answers.
    /// </summary>
    internal int ArmMilliseconds { get; init; } = OverlayWindow.ArmMilliseconds + UpAllowance;

    /// <summary>Milliseconds of a steady clock (tests set it).</summary>
    internal Func<long> Ticks { get; init; } = static () => Environment.TickCount64;

    /// <summary>
    /// Puts a toast up with that title and context, whose buttons go to the given answer; gives how to take it away, or
    /// null when Windows did not take it (tests set it).
    /// </summary>
    internal Func<string, string?, Action<bool>, Action?> Post { get; init; } = Windows;

    /// <summary>Tells the person something plainly, with no buttons (whoever shows the toasts sets it).</summary>
    internal Action<string>? Plain { get; init; }

    /// <summary>Shows the proposal with its buttons, whose press goes to <paramref name="answer"/> (that proposal's own);
    /// false when Windows did not take it (the caller notifies plainly).</summary>
    internal bool Show(string title, string? context, Action<bool> answer)
    {
        ArgumentNullException.ThrowIfNull(answer);
        lock (_gate)
        {
            Hide();
            int showing = _showing;
            long? since = null;
            bool spent = false;
            Action? hide = Post(title, context, approve =>
            {
                // Windows tells of a press on a thread of its own: the time is read before anything can hold it up.
                long now = Ticks();
                if (approve)
                {
                    bool early, mine;
                    lock (_gate)
                    {
                        if (spent)
                        {
                            return;
                        }

                        spent = early = !(since is { } shown && now - shown >= ArmMilliseconds);
                        mine = _showing == showing;
                        if (early && mine)
                        {
                            _hide = null;
                        }
                    }

                    if (early)
                    {
                        if (mine)
                        {
                            Plain?.Invoke(UiLanguage.Say("Ese Sí no contó: llegó nada más salir el aviso. Sigue pendiente: ", "That Yes did not count: it came as the notice came up. Still pending: ") + title);
                        }

                        return;
                    }
                }

                answer(approve);
            });
            if (hide is null)
            {
                return false;
            }

            since = Ticks();
            _hide = hide;
            return true;
        }
    }

    /// <summary>The proposal was answered elsewhere or ended: its toast goes.</summary>
    internal void Hide()
    {
        lock (_gate)
        {
            _showing++;
            Action? hide = _hide;
            _hide = null;
            hide?.Invoke();
        }
    }

    private static Action? Windows(string title, string? context, Action<bool> answer)
    {
        try
        {
            Register();
            var xml = new XmlDocument();
            xml.LoadXml("<toast scenario=\"reminder\"><visual><binding template=\"ToastGeneric\"><text/><text/></binding></visual>"
                + "<actions><action content=\"" + UiLanguage.Say("Sí", "Yes") + "\" arguments=\"yes\" activationType=\"foreground\"/>"
                + "<action content=\"No\" arguments=\"no\" activationType=\"foreground\"/></actions></toast>");
            IXmlNode[] texts = [.. xml.GetElementsByTagName("text")];
            texts[0].InnerText = title;
            texts[1].InnerText = context ?? string.Empty;
            var toast = new ToastNotification(xml) { ExpirationTime = DateTimeOffset.Now.AddMinutes(10) };
            toast.Activated += (_, args) =>
            {
                if (args is ToastActivatedEventArgs activated && activated.Arguments is "yes" or "no")
                {
                    answer(activated.Arguments == "yes");
                }
            };
            ToastNotificationManager.CreateToastNotifier(AppId).Show(toast);
            return () =>
            {
                try
                {
                    ToastNotificationManager.CreateToastNotifier(AppId).Hide(toast);
                }
                catch (Exception exception) when (exception is ArgumentException or System.Runtime.InteropServices.COMException)
                {
                    // Already gone from the action center.
                }
            };
        }
        catch (Exception exception) when (exception is InvalidOperationException or ArgumentException
            or UnauthorizedAccessException or SecurityException or System.Runtime.InteropServices.COMException)
        {
            return null;
        }
    }

    internal static void Register()
    {
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\Classes\AppUserModelId\" + AppId);
        if (key.GetValue("DisplayName") as string != "BAXY")
        {
            key.SetValue("DisplayName", "BAXY");
        }
    }
}
