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
    private const string AppId = "BAXY.Product.App";
    private readonly Action<bool> _answer;
    private ToastNotification? _shown;

    internal ProposalToast(Action<bool> answer)
    {
        _answer = answer ?? throw new ArgumentNullException(nameof(answer));
    }

    /// <summary>Shows the proposal with its buttons; false when Windows did not take it (the caller notifies plainly).</summary>
    internal bool Show(string title, string? context)
    {
        try
        {
            Register();
            var xml = new XmlDocument();
            xml.LoadXml("<toast scenario=\"reminder\"><visual><binding template=\"ToastGeneric\"><text/><text/></binding></visual>"
                + "<actions><action content=\"Sí\" arguments=\"yes\" activationType=\"foreground\"/>"
                + "<action content=\"No\" arguments=\"no\" activationType=\"foreground\"/></actions></toast>");
            IXmlNode[] texts = [.. xml.GetElementsByTagName("text")];
            texts[0].InnerText = title;
            texts[1].InnerText = context ?? string.Empty;
            var toast = new ToastNotification(xml) { ExpirationTime = DateTimeOffset.Now.AddMinutes(10) };
            toast.Activated += (_, args) =>
            {
                if (args is ToastActivatedEventArgs activated && activated.Arguments is "yes" or "no")
                {
                    _answer(activated.Arguments == "yes");
                }
            };
            Hide();
            ToastNotificationManager.CreateToastNotifier(AppId).Show(toast);
            _shown = toast;
            return true;
        }
        catch (Exception exception) when (exception is InvalidOperationException or ArgumentException
            or UnauthorizedAccessException or SecurityException or System.Runtime.InteropServices.COMException)
        {
            return false;
        }
    }

    /// <summary>The proposal was answered elsewhere or ended: its toast goes.</summary>
    internal void Hide()
    {
        if (_shown is not { } toast)
        {
            return;
        }

        _shown = null;
        try
        {
            ToastNotificationManager.CreateToastNotifier(AppId).Hide(toast);
        }
        catch (Exception exception) when (exception is ArgumentException or System.Runtime.InteropServices.COMException)
        {
            // Already gone from the action center.
        }
    }

    private static void Register()
    {
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\Classes\AppUserModelId\" + AppId);
        if (key.GetValue("DisplayName") as string != "BAXY")
        {
            key.SetValue("DisplayName", "BAXY");
        }
    }
}
