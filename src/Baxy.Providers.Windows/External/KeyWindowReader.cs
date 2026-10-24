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
    /// application still runs and is not in front, that application too (a key with no window goes to it,
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
    private readonly IOpenedApplicationFocus _opened;
    private readonly Func<nint> _front;
    private readonly Func<nint, IEnumerable<string>> _processNames;
    private readonly Func<nint, VisibleControlSurface.OpenedApplication, bool> _windowOf;

    public KeyWindowReader()
        : this(new OpenedApplicationFocus(), VisibleControlSurface.FrontWindow, WindowProcessNames,
            WindowsVisibleControlAdapter.IsWindowOfOpened)
    {
    }

    /// <param name="opened">The opening app.open noted (<see cref="OpenedApplicationFocus"/>).</param>
    /// <param name="front">The window in front now.</param>
    /// <param name="processNames">A window's process names: its own and, for a frame, the hosted app's.</param>
    /// <param name="windowOf">Whether a window is the opened application's
    /// (<see cref="WindowsVisibleControlAdapter.IsWindowOfOpened"/>).</param>
    internal KeyWindowReader(
        IOpenedApplicationFocus opened,
        Func<nint> front,
        Func<nint, IEnumerable<string>> processNames,
        Func<nint, VisibleControlSurface.OpenedApplication, bool> windowOf)
    {
        _opened = opened ?? throw new ArgumentNullException(nameof(opened));
        _front = front ?? throw new ArgumentNullException(nameof(front));
        _processNames = processNames ?? throw new ArgumentNullException(nameof(processNames));
        _windowOf = windowOf ?? throw new ArgumentNullException(nameof(windowOf));
    }

    public KeyWindowKind KindOf(long? window)
    {
        if (window is { } named)
        {
            return named > 0 ? OfWindow((nint)named) : KeyWindowKind.Unknown;
        }

        nint front = _front();
        if (front == 0)
        {
            return KeyWindowKind.Unknown;
        }

        // Holdout v5 V5E021: an opening whose process no longer exists (closed since; its names read empty, unknown) is
        // no window a key reaches (OpenedApplicationKeyboard sends it to the front then): the front decides.
        KeyWindowKind kind = OfWindow(front);
        if (kind != KeyWindowKind.Ordinary
            || _opened.PeekOpened() is not { } opened
            || _windowOf(front, opened)
            || !VisibleControlSurface.OpenedAlive(opened))
        {
            return kind;
        }

        List<string> names = [ProcessName(opened.ProcessId)];
        if (opened.Window != 0)
        {
            names.AddRange(_processNames(opened.Window));
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

    private KeyWindowKind OfWindow(nint window) => Classify(_processNames(window));

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
