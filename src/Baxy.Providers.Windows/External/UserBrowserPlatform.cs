using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Windows.Media.Control;

namespace Baxy.Providers.Windows.External;

internal sealed record UserBrowserWindow(nint Handle, string Title);

internal sealed record UserMediaSession(
    string SourceAppUserModelId,
    string Title,
    string Artist,
    string PlaybackStatus);

/// <summary>What the page step did inside the person's browser: the last step reached and the name it acted on.</summary>
internal sealed record UserBrowserPageStep(bool PlayInvoked, string Step, string Chosen);

internal sealed record UserBrowserTab(string Title, bool Selected);

internal sealed record UserBrowserPageText(string Title, string Text, bool Truncated);

/// <summary>
/// Everything the user-browser surface touches on the PC. The production
/// implementation opens links the way the shell does, reads top-level window
/// titles, the system media sessions (SMTC) and the address field through UI
/// Automation; tests replace it whole.
/// </summary>
internal interface IUserBrowserPlatform
{
    UserBrowserIdentity? ResolveDefault();

    /// <summary>Opens the address with the person's default browser. Throws when nothing was launched.</summary>
    void Open(Uri address);

    IReadOnlyList<UserBrowserWindow> ListWindows(string processName);

    ValueTask<IReadOnlyList<UserMediaSession>> ReadMediaSessionsAsync(CancellationToken cancellationToken);

    ValueTask<bool> PlayMediaSessionAsync(UserMediaSession session, CancellationToken cancellationToken);

    /// <summary>The text of the window's address field, or null when UI Automation cannot read it.</summary>
    ValueTask<string?> ReadAddressAsync(nint window, CancellationToken cancellationToken);

    /// <summary>Picks the named title on a streaming page shown in the window and presses its play control.</summary>
    ValueTask<UserBrowserPageStep> StartTitleInPageAsync(
        nint window, string title, bool typeSearch, CancellationToken cancellationToken);

    /// <summary>The window's tabs (title, selected), or null when UI Automation cannot read its tab strip.</summary>
    ValueTask<IReadOnlyList<UserBrowserTab>?> ReadTabsAsync(nint window, CancellationToken cancellationToken);

    /// <summary>The title and visible text of the page the window shows, or null when it cannot be read.</summary>
    ValueTask<UserBrowserPageText?> ReadPageTextAsync(
        nint window, int maximumCharacters, CancellationToken cancellationToken);

    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}

internal sealed partial class WindowsUserBrowserPlatform : IUserBrowserPlatform
{
    private readonly IExternalProcessRunner _runner;

    internal WindowsUserBrowserPlatform()
        : this(new ExternalProcessRunner())
    {
    }

    internal WindowsUserBrowserPlatform(IExternalProcessRunner runner) =>
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));

    public UserBrowserIdentity? ResolveDefault() => UserBrowserIdentityResolver.ResolveFromRegistry();

    public void Open(Uri address)
    {
        ArgumentNullException.ThrowIfNull(address);
        if (address.Scheme is not ("http" or "https"))
            throw new ArgumentException("Only web addresses are opened.", nameof(address));
        // The shell resolves the link exactly as a click would: the person's
        // browser, their profile and session, a new tab in the window they use.
        using Process? _ = Process.Start(new ProcessStartInfo(address.AbsoluteUri)
        {
            UseShellExecute = true,
        });
    }

    public IReadOnlyList<UserBrowserWindow> ListWindows(string processName)
    {
        var owners = new HashSet<uint>();
        Process[] processes = Process.GetProcessesByName(processName);
        try
        {
            foreach (Process process in processes)
                owners.Add(checked((uint)process.Id));
        }
        finally
        {
            foreach (Process process in processes)
                process.Dispose();
        }
        var windows = new List<UserBrowserWindow>();
        if (owners.Count == 0)
            return windows;
        EnumWindowsProc callback = (window, unused) =>
        {
            if (!IsWindowVisible(window))
                return true;
            _ = GetWindowThreadProcessId(window, out uint owner);
            if (!owners.Contains(owner))
                return true;
            string title = ReadWindowTitle(window);
            if (title.Length > 0)
                windows.Add(new UserBrowserWindow(window, title));
            return true;
        };
        // A failed enumeration is no observation: the caller sees no window
        // change and the navigation stays unconfirmed, never an exception.
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return windows;
    }

    public async ValueTask<IReadOnlyList<UserMediaSession>> ReadMediaSessionsAsync(
        CancellationToken cancellationToken)
    {
        var sessions = new List<UserMediaSession>();
        try
        {
            GlobalSystemMediaTransportControlsSessionManager manager =
                await GlobalSystemMediaTransportControlsSessionManager.RequestAsync();
            foreach (GlobalSystemMediaTransportControlsSession session in manager.GetSessions())
            {
                cancellationToken.ThrowIfCancellationRequested();
                string title = string.Empty;
                string artist = string.Empty;
                try
                {
                    GlobalSystemMediaTransportControlsSessionMediaProperties properties =
                        await session.TryGetMediaPropertiesAsync();
                    title = properties?.Title ?? string.Empty;
                    artist = properties?.Artist ?? string.Empty;
                }
                catch (Exception exception) when (exception is COMException
                    or InvalidOperationException)
                {
                    // A session without readable metadata still has a state.
                }
                sessions.Add(new UserMediaSession(
                    session.SourceAppUserModelId ?? string.Empty,
                    title,
                    artist,
                    StatusName(session.GetPlaybackInfo()?.PlaybackStatus)));
            }
        }
        catch (Exception exception) when (exception is COMException
            or InvalidOperationException or UnauthorizedAccessException)
        {
            // No media session service: nothing can be observed through it.
        }
        return sessions;
    }

    public async ValueTask<bool> PlayMediaSessionAsync(
        UserMediaSession target, CancellationToken cancellationToken)
    {
        try
        {
            GlobalSystemMediaTransportControlsSessionManager manager =
                await GlobalSystemMediaTransportControlsSessionManager.RequestAsync();
            foreach (GlobalSystemMediaTransportControlsSession session in manager.GetSessions())
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!string.Equals(session.SourceAppUserModelId, target.SourceAppUserModelId,
                        StringComparison.Ordinal))
                    continue;
                GlobalSystemMediaTransportControlsSessionMediaProperties properties =
                    await session.TryGetMediaPropertiesAsync();
                if (!string.Equals(properties?.Title ?? string.Empty, target.Title, StringComparison.Ordinal))
                    continue;
                return await session.TryPlayAsync();
            }
        }
        catch (Exception exception) when (exception is COMException
            or InvalidOperationException or UnauthorizedAccessException)
        {
        }
        return false;
    }

    public async ValueTask<string?> ReadAddressAsync(nint window, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.Address,
            [window.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            TimeSpan.FromSeconds(8),
            cancellationToken).ConfigureAwait(false);
        return result is { } value
            && value.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
            && value.TryGetProperty("value", out JsonElement address)
            && address.ValueKind == JsonValueKind.String
                ? address.GetString()
                : null;
    }

    public async ValueTask<UserBrowserPageStep> StartTitleInPageAsync(
        nint window, string title, bool typeSearch, CancellationToken cancellationToken)
    {
        string[] arguments =
        [
            window.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(title)),
            "30",
            typeSearch ? "1" : "0",
        ];
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.PagePlay, arguments, TimeSpan.FromSeconds(45), cancellationToken)
            .ConfigureAwait(false);
        if (result is not { } value)
            return new UserBrowserPageStep(false, "script_failed", string.Empty);
        bool played = value.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True;
        string step = value.TryGetProperty("step", out JsonElement stepValue)
            && stepValue.ValueKind == JsonValueKind.String ? stepValue.GetString() ?? string.Empty : string.Empty;
        string chosen = value.TryGetProperty("chosen", out JsonElement chosenValue)
            && chosenValue.ValueKind == JsonValueKind.String ? chosenValue.GetString() ?? string.Empty : string.Empty;
        return new UserBrowserPageStep(played, step, chosen);
    }

    public async ValueTask<IReadOnlyList<UserBrowserTab>?> ReadTabsAsync(
        nint window, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.Tabs,
            [window.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            TimeSpan.FromSeconds(10),
            cancellationToken).ConfigureAwait(false);
        if (result is not { } value
            || !value.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
            || !value.TryGetProperty("tabs", out JsonElement tabs) || tabs.ValueKind != JsonValueKind.Array)
            return null;
        var read = new List<UserBrowserTab>();
        foreach (JsonElement tab in tabs.EnumerateArray())
        {
            string title = tab.TryGetProperty("title", out JsonElement name) && name.ValueKind == JsonValueKind.String
                ? name.GetString() ?? string.Empty
                : string.Empty;
            bool selected = tab.TryGetProperty("selected", out JsonElement flag) && flag.ValueKind == JsonValueKind.True;
            read.Add(new UserBrowserTab(title, selected));
        }
        return read;
    }

    public async ValueTask<UserBrowserPageText?> ReadPageTextAsync(
        nint window, int maximumCharacters, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.PageText,
            [
                window.ToString(System.Globalization.CultureInfo.InvariantCulture),
                maximumCharacters.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ],
            TimeSpan.FromSeconds(20),
            cancellationToken).ConfigureAwait(false);
        if (result is not { } value
            || !value.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            return null;
        string Read(string property) => value.TryGetProperty(property, out JsonElement field)
            && field.ValueKind == JsonValueKind.String ? field.GetString() ?? string.Empty : string.Empty;
        bool truncated = value.TryGetProperty("truncated", out JsonElement cut) && cut.ValueKind == JsonValueKind.True;
        return new UserBrowserPageText(Read("title"), Read("text"), truncated);
    }

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    private async ValueTask<JsonElement?> RunScriptAsync(
        string script,
        IReadOnlyList<string> scriptArguments,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        var arguments = new List<string>
        {
            "-NoProfile", "-NonInteractive", "-Command", "& {\n" + script + "\n}",
        };
        arguments.AddRange(scriptArguments);
        string powershell = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.System),
            "WindowsPowerShell", "v1.0", "powershell.exe");
        try
        {
            ExternalProcessResult run = await _runner.RunAsync(
                powershell, arguments, timeout, cancellationToken).ConfigureAwait(false);
            string line = run.Output.Split('\n', StringSplitOptions.RemoveEmptyEntries
                | StringSplitOptions.TrimEntries).LastOrDefault() ?? string.Empty;
            if (run.ExitCode != 0 || !line.StartsWith('{'))
                return null;
            using JsonDocument document = JsonDocument.Parse(line);
            return document.RootElement.Clone();
        }
        catch (Exception exception) when (exception is IOException or TimeoutException
            or JsonException or Win32Exception)
        {
            return null;
        }
    }

    private static string StatusName(GlobalSystemMediaTransportControlsSessionPlaybackStatus? status) =>
        status switch
        {
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing => "playing",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused => "paused",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Stopped => "stopped",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Closed => "closed",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Opened => "opened",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Changing => "changing",
            _ => string.Empty,
        };

    private static unsafe string ReadWindowTitle(nint handle)
    {
        const int capacity = 1024;
        char* buffer = stackalloc char[capacity];
        int length = GetWindowText(handle, buffer, capacity);
        return length > 0 ? new string(buffer, 0, length) : string.Empty;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(nint window, char* text, int capacity);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);
}
