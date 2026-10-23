namespace Baxy.Providers.Windows.External;

/// <summary>
/// Al máximo, K-2 refinada (2026-10-22): what kind of window an Enter or a space would land on, for the key press's
/// preflight. Enter in a messaging client may send what message.draft left written; in a console it runs what was
/// typed. Everywhere else (a search box, an address bar, a text field) it sends nothing.
/// </summary>
public enum KeyWindowKind
{
    /// <summary>No window, or one whose process could not be read.</summary>
    Unknown,

    /// <summary>Neither a messaging client nor a console.</summary>
    Ordinary,

    /// <summary>A client message.draft and message.send write into.</summary>
    Messaging,

    /// <summary>A terminal, a console, or an editor that hosts one.</summary>
    Console,
}

/// <summary>Reads, with no effect, the window a key press would reach.</summary>
public interface IKeyWindowReader
{
    /// <summary>
    /// The window <paramref name="window"/> names; with none, the window in front and, when a fresh app.open's
    /// application is not in front, that application too (a key with no window goes to it,
    /// <see cref="OpenedApplicationKeyboard"/>). The first that is not ordinary decides.
    /// </summary>
    KeyWindowKind KindOf(long? window);
}

/// <summary>
/// The product's reader. The windows are told by their exact process names, the providers' own data: the messaging
/// clients' (<see cref="WindowsDesktopMessagingAutomation.ClientProcessNames"/>) and the protected consoles and editors'
/// (<see cref="VisibleControlSurface.RunsWhatIsTyped"/>); never an application named here.
/// </summary>
public sealed class KeyWindowReader : IKeyWindowReader
{
    private readonly OpenedApplicationFocus _opened = new();

    public KeyWindowKind KindOf(long? window)
    {
        if (window is { } named)
        {
            return named > 0 ? OfWindow((nint)named) : KeyWindowKind.Unknown;
        }

        nint front = VisibleControlSurface.FrontWindow();
        if (front == 0)
        {
            return KeyWindowKind.Unknown;
        }

        KeyWindowKind kind = OfWindow(front);
        if (kind != KeyWindowKind.Ordinary
            || _opened.PeekOpened() is not { } opened
            || WindowsVisibleControlAdapter.IsWindowOfOpened(front, opened))
        {
            return kind;
        }

        List<string> names = [ProcessName(opened.ProcessId)];
        if (opened.Window != 0)
        {
            names.AddRange(WindowProcessNames(opened.Window));
        }

        return Classify(names);
    }

    /// <summary>
    /// The kind told by the process names of one window (its own and, for a frame, the hosted app's): none readable is
    /// unknown; a messaging client's or a console's name is that; any other, ordinary.
    /// </summary>
    internal static KeyWindowKind Classify(IEnumerable<string?> processNames)
    {
        string[] names = [.. processNames.Select(Bare).Where(static name => name.Length > 0)];
        if (names.Length == 0)
        {
            return KeyWindowKind.Unknown;
        }

        if (names.Any(name => WindowsDesktopMessagingAutomation.ClientProcessNames
                .Contains(name, StringComparer.OrdinalIgnoreCase)))
        {
            return KeyWindowKind.Messaging;
        }

        return names.Any(VisibleControlSurface.RunsWhatIsTyped) ? KeyWindowKind.Console : KeyWindowKind.Ordinary;
    }

    private static KeyWindowKind OfWindow(nint window) => Classify(WindowProcessNames(window));

    private static IEnumerable<string> WindowProcessNames(nint window)
    {
        yield return VisibleControlSurface.WindowProcess(window).ProcessName;
        yield return VisibleControlSurface.ViewProcess(window).ProcessName;
    }

    private static string ProcessName(int processId)
    {
        if (processId <= 0)
        {
            return string.Empty;
        }

        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(processId);
            return process.ProcessName;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return string.Empty;
        }
    }

    private static string Bare(string? processName)
    {
        string name = (processName ?? string.Empty).Trim();
        return name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? name[..^4] : name;
    }
}
