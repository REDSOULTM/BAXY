using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Capture;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    internal static async ValueTask<CapturedWindow?> CaptureForegroundAsync(
        CancellationToken cancellationToken)
    {
        // M132, measured live: the opened client's updater closed while its
        // label was looked for, the front fell to the person's editor, and
        // the word was read and pressed there. A click bound to the opened
        // application reads only that application's window.
        if (RequiredWindow.Value is var required and not 0)
            return ForegroundIs(required) ? await CaptureAsync(required, cancellationToken).ConfigureAwait(false) : null;
        nint hwnd = await ResolveForegroundAsync(cancellationToken).ConfigureAwait(false);
        return hwnd == 0
            ? null
            : await CaptureAsync(hwnd, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// The window a person acts on right now: the root of the foreground
    /// window, or the topmost foreign window when the foreground is ours or
    /// has no usable surface. The compact view, the click and the scroll all
    /// resolve the window here, so they always mean the same one.
    /// </summary>
    internal static async ValueTask<nint> ResolveForegroundAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        nint hwnd = GetForegroundWindow();
        // While a window is changing hands (an application was just brought to
        // the front) the foreground is briefly nobody's: wait a little, then
        // take the topmost foreign window rather than answering «no window».
        for (int attempt = 0; hwnd == 0 && attempt < 6; attempt++)
        {
            await Task.Delay(200, cancellationToken).ConfigureAwait(false);
            hwnd = GetForegroundWindow();
        }
        if (hwnd == 0)
            hwnd = TopmostForeignWindow();
        if (hwnd == 0)
            return 0;
        // UI1395: a freshly launched UWP app is fronted by its CoreWindow
        // (calculatorapp.exe, no top-level window of its own) and, once a
        // control is invoked, by its ApplicationFrameHost frame. The frame is
        // the root ancestor of both moments, so that one window is compared;
        // a classic top-level window keeps the largest-window rule.
        nint root = GetAncestor(hwnd, 2);
        if (root != 0 && root != hwnd)
        {
            hwnd = root;
        }
        else
        {
            // The window in front stays the one, when it has a surface; only
            // a front window without one gives way to the process's largest
            // usable window (File Explorer with several folder windows open).
            _ = GetWindowThreadProcessId(hwnd, out uint processId);
            nint chosen = ProcessWindow(unchecked((int)processId), hwnd);
            if (chosen != 0)
                hwnd = chosen;
        }
        // UI1735: two Chromium-based launchers replace their start-up
        // window with their main window a few seconds after app.open verified
        // the focus, and the foreground fell back to this product's own window
        // (or to a window with no surface); the label was then searched on the
        // wrong surface for the whole budget. The surface a person acts on is
        // the topmost window that is not BAXY: when the foreground is ours or
        // has no usable surface, take that window and bring it to the front,
        // because the click lands on whatever is on top.
        _ = GetWindowThreadProcessId(hwnd, out uint foregroundProcess);
        // The desktop itself (Progman / WorkerW, «Program Manager») and the
        // taskbar are never the surface a person acts on: when nothing owns the
        // foreground the act lands on the topmost application window.
        if (foregroundProcess == unchecked((uint)Environment.ProcessId) || !HasUsableSurface(hwnd)
            || IsShellSurface(hwnd))
        {
            nint candidate = TopmostForeignWindow();
            if (candidate != 0)
            {
                BringToFront(candidate);
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
                hwnd = candidate;
            }
        }

        return hwnd;
    }

    /// <summary>
    /// The window of one process: the ApplicationFrameHost frame hosting it
    /// when it draws inside one (a packaged app such as the Calculator has no
    /// top-level window of its own, only its pop-ups), else the
    /// one in front when it is the process's and has a usable surface, else
    /// its largest usable top-level window. Brought to the front so keys and
    /// clicks land on it; 0 when the process shows nothing.
    /// </summary>
    internal static async ValueTask<nint> ResolveProcessWindowAsync(
        int processId,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        nint found = 0;
        for (int attempt = 0; found == 0 && attempt < 8; attempt++)
        {
            if (attempt > 0)
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            nint front = GetForegroundWindow();
            uint process = unchecked((uint)processId);
            nint frame = FrameHosting(process);
            found = ChooseProcessWindow(
                TopLevelWindowsOf(process), process, front == 0 ? 0 : GetAncestor(front, 2), frame);
            if (found == 0 || !HasUsableSurface(found))
                found = frame;
        }

        if (found == 0)
            return 0;
        if (GetForegroundWindow() != found)
        {
            BringToFront(found);
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        }

        return found;
    }

    /// <summary>
    /// The application's window when its process is unknown (app.open did not
    /// verify, or the application was already there): the topmost visible
    /// window whose executable is the application, else the topmost one whose
    /// title names it in its last segment (<see cref="TitleNamesApplication"/>).
    /// Never a developer's or BAXY's own window the request did not name
    /// (<see cref="ProtectedFrom"/>). Brought to the front; 0 when none is.
    /// </summary>
    internal static async ValueTask<nint> ResolveTitledWindowAsync(
        string application,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (FoldTitle(application).Length == 0)
            return 0;
        nint byProcess = 0;
        nint byTitle = 0;
        uint self = unchecked((uint)Environment.ProcessId);
        var names = new Dictionary<uint, string>();
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || GetAncestor(window, 3) != window)
                return true;
            if ((GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner == 0 || owner == self || !HasUsableSurface(window))
                return true;
            if (!names.TryGetValue(owner, out string? processName))
            {
                processName = WindowProcess(window).ProcessName;
                names[owner] = processName;
            }

            if (ProtectedFrom(processName, application))
                return true;
            if (ProcessIsApplication(processName, application))
            {
                byProcess = window;
                return false;
            }

            if (byTitle == 0 && TitleNamesApplication(WindowTitle(window), application))
                byTitle = window;
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        nint found = byProcess != 0 ? byProcess : byTitle;
        if (found == 0)
            return 0;
        if (GetForegroundWindow() != found)
        {
            BringToFront(found);
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        }

        return found;
    }

    /// <summary>
    /// The root window of another process drawn over the centre of this one,
    /// or 0 when the window is what a person sees there. Measured: a fullscreen
    /// video player on top of a settings page and of a game launcher; the view read the player
    /// and a click would have landed on it.
    /// </summary>
    internal static nint CoveringWindow(nint hwnd)
    {
        if (!TryBounds(hwnd, out int left, out int top, out int right, out int bottom))
            return 0;
        var centre = new Point((left + right) / 2, (top + bottom) / 2);
        nint hit = InPhysicalPixels(() => WindowFromPoint(centre));
        if (hit == 0)
            return 0;
        nint root = GetAncestor(hit, 2);
        if (root == 0)
            root = hit;
        if (root == hwnd)
            return 0;
        _ = GetWindowThreadProcessId(root, out uint coverOwner);
        _ = GetWindowThreadProcessId(hwnd, out uint owner);
        // A window of the same process (a dialog, a menu, a popup) and this
        // product's own window are not covers; nor is a pop-up of the app a
        // frame hosts (its process is not the frame's).
        if (coverOwner == owner || coverOwner == unchecked((uint)Environment.ProcessId)
            || (IsVisibleFrame(hwnd) && FrameHosts(hwnd, hosted => hosted == coverOwner)))
            return 0;
        return root;
    }

    // The windows where the person's own work and BAXY live: an editor, an IDE, a terminal, a console, BAXY itself.
    // Safety review 2026-10-07: a file «<App>LocalAdapter.cs» open in Visual Studio Code was the first window titled
    // «<App>», and a mission would have typed and pressed keys in the editor where the developer's agent lives. Such
    // a window is the application only when the request names that very application (the names on the right).
    private static readonly Dictionary<string, string[]> ProtectedProcesses = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Code"] = ["code", "vs code", "vscode", "visual studio code"],
        ["Code - Insiders"] = ["code insiders", "visual studio code insiders"],
        ["devenv"] = ["visual studio", "devenv"],
        ["WindowsTerminal"] = ["terminal", "windows terminal"],
        ["OpenConsole"] = ["terminal", "windows terminal"],
        ["powershell"] = ["powershell", "windows powershell"],
        ["pwsh"] = ["powershell", "pwsh"],
        ["cmd"] = ["cmd", "simbolo del sistema", "command prompt"],
        ["conhost"] = ["cmd", "simbolo del sistema", "command prompt", "consola"],
        ["Baxy"] = ["baxy"],
        ["baxy-core"] = ["baxy"],
    };

    // Words of an application's name that name no application by themselves.
    private static readonly HashSet<string> GenericApplicationWords = new(StringComparer.Ordinal)
    {
        "the", "los", "las", "navegador", "browser", "google", "microsoft", "mozilla", "app", "aplicacion",
    };

    /// <summary>A developer's or BAXY's own process that the request did not name.</summary>
    internal static bool ProtectedFrom(string? processName, string? application)
    {
        string process = (processName ?? string.Empty).Trim();
        if (process.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            process = process[..^4];
        return ProtectedProcesses.TryGetValue(process, out string[]? names)
            && !names.Contains(FoldTitle(application), StringComparer.Ordinal);
    }

    /// <summary>
    /// The executable is the application: its name is the application's name without spaces
    /// («EpicGamesLauncher»), or one of its distinctive words (the browser's short name for its full name).
    /// </summary>
    internal static bool ProcessIsApplication(string? processName, string? application)
    {
        string process = FoldTitle(processName);
        if (process.EndsWith(".exe", StringComparison.Ordinal))
            process = process[..^4];
        string wanted = FoldTitle(application);
        if (process.Length == 0 || wanted.Length == 0)
            return false;
        return process == wanted.Replace(" ", string.Empty, StringComparison.Ordinal)
            || ApplicationWords(wanted).Contains(process, StringComparer.Ordinal);
    }

    /// <summary>
    /// The title names the application where windows put their own name: as whole words in its last « - »
    /// segment («Ron92 - <chat app>», «Nueva pestaña - <browser>»), or the whole title when it has no separator
    /// («Calculadora»). «<App>LocalAdapter.cs - BAXY - Visual Studio Code» names Visual Studio Code.
    /// </summary>
    internal static bool TitleNamesApplication(string? title, string? application)
    {
        string wanted = FoldTitle(application);
        if (wanted.Length == 0)
            return false;
        string segment = TitleSeparator().Split(FoldTitle(title))[^1].Trim();
        if (segment.Length == 0)
            return false;
        return NamesAsWords(segment, wanted) || ApplicationWords(wanted).Any(word => NamesAsWords(segment, word));
    }

    private static string[] ApplicationWords(string folded) =>
        [.. folded.Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Where(word => word.Length >= 3 && !GenericApplicationWords.Contains(word))];

    private static bool NamesAsWords(string text, string words)
    {
        for (int at = text.IndexOf(words, StringComparison.Ordinal); at >= 0;
             at = text.IndexOf(words, at + 1, StringComparison.Ordinal))
        {
            int end = at + words.Length;
            if ((at == 0 || !char.IsLetterOrDigit(text[at - 1])) && (end == text.Length || !char.IsLetterOrDigit(text[end])))
                return true;
        }

        return false;
    }

    [System.Text.RegularExpressions.GeneratedRegex(@"\s+[-\u2013\u2014|]\s+", System.Text.RegularExpressions.RegexOptions.CultureInvariant)]
    private static partial System.Text.RegularExpressions.Regex TitleSeparator();

    internal static string FoldTitle(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return string.Empty;
        string decomposed = value.Normalize(System.Text.NormalizationForm.FormD);
        var builder = new System.Text.StringBuilder(decomposed.Length);
        bool pendingSpace = false;
        foreach (char character in decomposed)
        {
            // A format character (Edge writes «Microsoft\u200b Edge» in its titles) is no letter of the name.
            if (System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                is System.Globalization.UnicodeCategory.NonSpacingMark or System.Globalization.UnicodeCategory.Format)
            {
                continue;
            }

            if (char.IsWhiteSpace(character))
            {
                pendingSpace = builder.Length > 0;
                continue;
            }

            if (pendingSpace)
            {
                builder.Append(' ');
                pendingSpace = false;
            }

            builder.Append(char.ToLowerInvariant(character));
        }

        return builder.ToString();
    }

    /// <summary>
    /// The visible ApplicationFrameHost frame that hosts this process (a packaged app such as the Calculator, the
    /// Clock or Settings draws inside a frame of another process and has no top-level window of its own); 0 when
    /// none shows it. A cloaked frame (a suspended app) is not on screen.
    /// </summary>
    internal static nint FrameHosting(uint processId)
    {
        nint frame = 0;
        EnumWindowsProc callback = (window, outerParameter) =>
        {
            if (!IsVisibleFrame(window) || !FrameHosts(window, owner => owner == processId))
                return true;
            frame = window;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        return frame;
    }

    /// <summary>Every visible frame by the process it hosts, read in one pass over the desktop.</summary>
    internal static Dictionary<uint, nint> HostedFrames()
    {
        var frames = new Dictionary<uint, nint>();
        EnumWindowsProc callback = (window, outerParameter) =>
        {
            if (!IsVisibleFrame(window))
                return true;
            _ = FrameHosts(window, owner =>
            {
                frames.TryAdd(owner, window);
                return false;
            });
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return frames;
    }

    private static bool IsVisibleFrame(nint window) =>
        IsWindowVisible(window) && ClassName(window) == "ApplicationFrameWindow"
        && !(DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0);

    private static bool FrameHosts(nint frame, Func<uint, bool> hosted)
    {
        _ = GetWindowThreadProcessId(frame, out uint host);
        bool hosts = false;
        EnumWindowsProc children = (child, innerParameter) =>
        {
            GetWindowThreadProcessId(child, out uint owner);
            if (owner != host && hosted(owner))
            {
                hosts = true;
                return false;
            }

            return true;
        };
        _ = EnumChildWindows(frame, children, nint.Zero);
        return hosts;
    }

    private static bool IsShellSurface(nint window)
    {
        string className = ClassName(window);
        return className is "Progman" or "WorkerW" or "Shell_TrayWnd" or "Shell_SecondaryTrayWnd";
    }

    internal static string ClassName(nint window)
    {
        var buffer = new char[128];
        int copied = GetClassNameW(window, buffer, buffer.Length);
        return copied <= 0 ? string.Empty : new string(buffer, 0, copied);
    }

    /// <summary>
    /// Brings a window to the front the way the messaging adapter does: attached
    /// to the input of the thread that owns the foreground, so Windows accepts
    /// the request from this background process (a plain SetForegroundWindow is
    /// refused and the typed keys would go elsewhere).
    /// </summary>
    internal static bool BringToFront(nint window)
    {
        nint foreground = GetForegroundWindow();
        uint foregroundThread = GetWindowThreadProcessId(foreground, out _);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != 0
            && currentThread != foregroundThread
            && AttachThreadInput(currentThread, foregroundThread, true);
        try
        {
            if (IsIconic(window))
                _ = ShowWindow(window, 9);
            _ = BringWindowToTop(window);
            _ = SetForegroundWindow(window);
            return GetForegroundWindow() == window;
        }
        finally
        {
            if (attached)
                _ = AttachThreadInput(currentThread, foregroundThread, false);
        }
    }

    private static readonly AsyncLocal<nint> RequiredWindow = new();

    // Binds the reads and presses of the calls made inside the scope to one window: while it is not the one in
    // front, nothing is captured, so nothing is read or pressed elsewhere.
    internal static IDisposable RequireWindow(nint window)
    {
        nint previous = RequiredWindow.Value;
        RequiredWindow.Value = window;
        return new RequiredWindowScope(previous);
    }

    // The window in front is this one (or a window inside it).
    internal static bool ForegroundIs(nint window)
    {
        nint foreground = GetForegroundWindow();
        if (foreground == 0 || window == 0)
            return false;
        nint root = GetAncestor(foreground, 2);
        return (root == 0 ? foreground : root) == window;
    }

    private sealed class RequiredWindowScope(nint previous) : IDisposable
    {
        public void Dispose() => RequiredWindow.Value = previous;
    }

    // The window as drawn now, held in memory: what the view, a click and a scroll compare and read is never written.
    internal static ValueTask<CapturedWindow?> CaptureAsync(
        nint hwnd,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (hwnd == 0 || !TryBounds(hwnd, out int left, out int top, out _, out _))
            return ValueTask.FromResult<CapturedWindow?>(null);
        WindowImage image = WindowsScreenshotProvider.CaptureWindowImage(hwnd);
        return ValueTask.FromResult<CapturedWindow?>(
            new CapturedWindow(hwnd, image.Bmp, left, top, image.Width, image.Height, image.Sha256));
    }

    // M132 (owner script t36 «abre … y ve a la biblioteca», launched cold): the opening was verified on the
    // client's updater window (400×129, its own process) and the click looked at the front window for its whole
    // budget, but the main window came seconds later from a helper process the client started, and the front had
    // gone back to whatever was there before. What a click right after an opening acts on is the application that
    // was opened: its process or one it started, the largest usable window of them, brought to the front.
    private static readonly object OpenedGate = new();
    private static OpenedApplication? _opened;

    internal static void NoteOpened(int processId, bool launched, long window = 0)
    {
        if (processId <= 0)
            return;
        DateTime started;
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(processId);
            started = process.StartTime.ToUniversalTime();
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            return;
        }

        DateTime noted = DateTime.UtcNow;
        lock (OpenedGate)
            _opened = new OpenedApplication(processId, started, noted, LaunchedNow(started, noted, launched), (nint)window);
    }

    // A process this opening started, against a new window of one already running: File Explorer opens its folder
    // window inside the shell's explorer.exe (v2-s04, measured: the click then took the largest window of every
    // program the shell ever started, the desktop among them, waited 41 s for its label and covered the folder
    // window with the person's editor). A window of a running process is drawn as it shows.
    private static readonly TimeSpan LaunchWindow = TimeSpan.FromMinutes(1);

    internal static bool LaunchedNow(DateTime processStartedUtc, DateTime notedUtc, bool launched) =>
        launched && notedUtc - processStartedUtc < LaunchWindow;

    internal static OpenedApplication? TakeOpened(TimeSpan freshness)
    {
        lock (OpenedGate)
        {
            OpenedApplication? opened = _opened;
            _opened = null;
            return opened is { } value && DateTime.UtcNow - value.NotedUtc <= freshness ? value : null;
        }
    }

    internal static OpenedApplication? PeekOpened(TimeSpan freshness)
    {
        lock (OpenedGate)
        {
            return _opened is { } value && DateTime.UtcNow - value.NotedUtc <= freshness ? value : null;
        }
    }

    // The opened application's largest usable window, brought to the front, and whether it looks drawn; no window
    // while it has none yet (an updater or splash only, or nothing). Measured on a cold client launch: its main
    // window came up with the navigation bar over a black page (one colour on 76–96 % of the window) for about
    // three seconds, and a click on the bar then was undone when the client loaded its start page; once the page
    // is drawn, one colour covers about a third. A pop-up of the same application over the main window (a chat)
    // is not what a person opening the application acts on: the main window is brought back in front.
    internal static async ValueTask<OpenedSurface> FrontOpenedAsync(
        OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        // An application that was running already is the window the opening verified while it is still on screen;
        // only one launched now is followed through the processes it starts (its main window replaces a splash).
        nint target = 0;
        if (!opened.Launched && opened.Window != 0 && IsAlive(opened.Window)
            && HasUsableSurface(opened.Window) && !IsShellSurface(opened.Window))
        {
            target = opened.Window;
        }
        else
        {
            HashSet<uint> family = ProcessFamily(opened);
            if (family.Count == 0)
                return default;
            target = LargestUsableWindow(family);
        }

        if (target == 0)
            return default;
        nint foreground = GetForegroundWindow();
        nint root = foreground == 0 ? 0 : GetAncestor(foreground, 2);
        // Measured: the chat pop-up came up over the main window without taking the focus, so the main window was
        // the foreground and still covered where its navigation is.
        if ((root == 0 ? foreground : root) != target || CoveredFromAbove(target))
        {
            BringToFront(target);
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        }

        if (!judgeDrawn)
            return new OpenedSurface(target, Drawn: true);
        double? share = await DominantColourShareAsync(target, cancellationToken).ConfigureAwait(false);
        return new OpenedSurface(target, Drawn: share is not { } measured || measured < BlankShare);
    }

    // One colour over this share of a window is a page still to be drawn (black, white or a spinner on a plain
    // background); a drawn page measured about a third.
    private const double BlankShare = 0.7;

    private static async ValueTask<double?> DominantColourShareAsync(
        nint window,
        CancellationToken cancellationToken)
    {
        try
        {
            return await CaptureAsync(window, cancellationToken).ConfigureAwait(false) is { } capture
                ? DominantColourShare(capture.Bmp)
                : null;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or UnauthorizedAccessException or ArgumentException)
        {
            return null;
        }
    }

    // 32-bit BGRA bitmap (the capture's own encoding): the share of sampled pixels in the commonest colour, each
    // channel quantised to sixteen levels.
    internal static double? DominantColourShare(byte[] bmp)
    {
        const int header = 54;
        if (bmp.Length <= header || bmp[0] != (byte)'B' || bmp[1] != (byte)'M'
            || BitConverter.ToInt16(bmp, 28) != 32)
        {
            return null;
        }
        int pixels = (bmp.Length - header) / 4;
        if (pixels == 0)
            return null;
        int step = Math.Max(1, pixels / 40_000);
        var counts = new int[4096];
        int sampled = 0;
        int best = 0;
        for (int index = 0; index < pixels; index += step)
        {
            int offset = header + index * 4;
            int bin = ((bmp[offset + 2] >> 4) << 8) | ((bmp[offset + 1] >> 4) << 4) | (bmp[offset] >> 4);
            best = Math.Max(best, ++counts[bin]);
            sampled++;
        }
        return (double)best / sampled;
    }

    private static HashSet<uint> ProcessFamily(OpenedApplication opened)
    {
        var family = new HashSet<uint>();
        Dictionary<uint, List<uint>> children = ChildrenByParent();
        var pending = new Queue<uint>();
        pending.Enqueue(unchecked((uint)opened.ProcessId));
        while (pending.Count > 0)
        {
            uint current = pending.Dequeue();
            if (!family.Add(current) || !children.TryGetValue(current, out List<uint>? started))
                continue;
            foreach (uint child in started)
            {
                // A parent id can outlive its process and be handed to another one; a child that is older than
                // the opened process was not started by it.
                if (StartedAfter(child, opened.StartedUtc))
                    pending.Enqueue(child);
            }
        }

        if (!ProcessAlive(opened))
            family.Remove(unchecked((uint)opened.ProcessId));
        return family;
    }

    private static bool StartedAfter(uint processId, DateTime startedUtc)
    {
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(unchecked((int)processId));
            return process.StartTime.ToUniversalTime() >= startedUtc.AddSeconds(-1);
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            return false;
        }
    }

    private static bool ProcessAlive(OpenedApplication opened)
    {
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(opened.ProcessId);
            return !process.HasExited
                && Math.Abs((process.StartTime.ToUniversalTime() - opened.StartedUtc).TotalSeconds) < 1;
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            return false;
        }
    }

    private static unsafe Dictionary<uint, List<uint>> ChildrenByParent()
    {
        var children = new Dictionary<uint, List<uint>>();
        nint snapshot = CreateToolhelp32Snapshot(0x00000002, 0);
        if (snapshot == -1 || snapshot == 0)
            return children;
        try
        {
            var entry = new ProcessEntry32 { Size = (uint)sizeof(ProcessEntry32) };
            if (!Process32FirstW(snapshot, ref entry))
                return children;
            do
            {
                if (entry.ProcessId != 0 && entry.ParentProcessId != entry.ProcessId)
                {
                    if (!children.TryGetValue(entry.ParentProcessId, out List<uint>? list))
                        children[entry.ParentProcessId] = list = [];
                    list.Add(entry.ProcessId);
                }
                entry.Size = (uint)sizeof(ProcessEntry32);
            }
            while (Process32NextW(snapshot, ref entry));
        }
        finally
        {
            _ = CloseHandle(snapshot);
        }

        return children;
    }

    private static nint LargestUsableWindow(HashSet<uint> family)
    {
        nint best = 0;
        long bestArea = 0;
        EnumWindowsProc callback = (window, unused) =>
        {
            if (GetAncestor(window, 3) != window || (GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            _ = GetWindowThreadProcessId(window, out uint owner);
            // A packaged app opened is drawn inside the frame that hosts it (its own process has no top-level window).
            bool owned = family.Contains(owner) || (IsVisibleFrame(window) && FrameHosts(window, family.Contains));
            if (!owned || !HasUsableSurface(window) || IsShellSurface(window))
                return true;
            if (!TryBounds(window, out int left, out int top, out int right, out int bottom))
                return true;
            // An updater or splash (measured 500×161) is not the application's surface yet.
            if (right - left < 300 || bottom - top < 200)
                return true;
            long area = (long)(right - left) * (bottom - top);
            if (area > bestArea)
            {
                bestArea = area;
                best = window;
            }
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return best;
    }

    // A visible, uncloaked window that is not always-on-top and sits above the target in the Z order over part
    // of it (always-on-top windows stay above whatever is brought forward, so they are not counted).
    private static bool CoveredFromAbove(nint target)
    {
        if (!TryBounds(target, out int left, out int top, out int right, out int bottom))
            return false;
        bool covered = false;
        EnumWindowsProc callback = (window, unused) =>
        {
            if (window == target)
                return false;
            if (!IsWindowVisible(window) || (GetWindowLongPtrW(window, -20).ToInt64() & 0x8) != 0)
                return true;
            if (DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
                return true;
            if (!TryBounds(window, out int otherLeft, out int otherTop, out int otherRight, out int otherBottom))
                return true;
            if (otherLeft < right && otherRight > left && otherTop < bottom && otherBottom > top)
            {
                covered = true;
                return false;
            }
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return covered;
    }

    // A click bound to the opened application lands only while its window is still the one in front.
    internal static bool MayPress() =>
        RequiredWindow.Value == 0 || ForegroundIs(RequiredWindow.Value);

    internal static void Click(int screenX, int screenY)
    {
        _ = PointAt(screenX, screenY);
        mouse_event(0x0002, 0, 0, 0, 0);
        mouse_event(0x0004, 0, 0, 0, 0);
    }

    /// <summary>
    /// The cursor placed on a point of the screen in physical pixels, the unit of every point the views hold (the
    /// capture, the window bounds from the compositor, the accessible tree's rectangles). This process is not DPI
    /// aware: a point set without a per-monitor context is scaled by the monitor's factor (measured 2026-10-07 at
    /// 125 %: a word read at y=440 in a folder window's side list was clicked at y=550, three rows lower, and the
    /// window opened another folder).
    /// </summary>
    internal static bool PointAt(int screenX, int screenY) => InPhysicalPixels(() => SetCursorPos(screenX, screenY));

    internal static T InPhysicalPixels<T>(Func<T> act)
    {
        nint previous = SetThreadDpiAwarenessContext(PerMonitorAwareV2);
        try
        {
            return act();
        }
        finally
        {
            if (previous != 0)
                _ = SetThreadDpiAwarenessContext(previous);
        }
    }

    private static readonly nint PerMonitorAwareV2 = -4;

    /// <summary>
    /// Whether a window's process runs with more rights than this one (an elevated app such as Task Manager):
    /// Windows refuses UI Automation patterns and input from a lower process (UIPI), so nothing can be done there.
    /// Measured: Task Manager showed four controls and every click failed.
    /// </summary>
    internal static bool RunsAboveUs(int processId)
    {
        if (processId <= 0 || Elevated(Environment.ProcessId) == true)
            return false;
        return Elevated(processId) != false;
    }

    internal static bool? Elevated(int processId)
    {
        nint process = OpenProcess(0x1000, false, unchecked((uint)processId));
        if (process == 0)
            return null;
        try
        {
            if (!OpenProcessToken(process, 0x0008, out nint token))
                return null;
            try
            {
                return GetTokenInformation(token, 20, out int elevation, sizeof(int), out _) ? elevation != 0 : null;
            }
            finally
            {
                _ = CloseHandle(token);
            }
        }
        finally
        {
            _ = CloseHandle(process);
        }
    }

    [LibraryImport("kernel32.dll")]
    private static partial nint OpenProcess(uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, uint processId);

    [LibraryImport("advapi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool OpenProcessToken(nint process, uint access, out nint token);

    [LibraryImport("advapi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetTokenInformation(nint token, int informationClass, out int information, int length, out int returned);

    internal static bool IsAlive(nint hwnd) => hwnd != 0 && IsWindow(hwnd) && IsWindowVisible(hwnd);

    internal static string WindowTitle(nint hwnd)
    {
        int length = GetWindowTextLengthW(hwnd);
        if (length <= 0)
            return string.Empty;
        var buffer = new char[Math.Min(length, 512) + 1];
        int copied = GetWindowTextW(hwnd, buffer, buffer.Length);
        return copied <= 0 ? string.Empty : new string(buffer, 0, copied);
    }

    internal static (int ProcessId, string ProcessName) WindowProcess(nint hwnd)
    {
        _ = GetWindowThreadProcessId(hwnd, out uint processId);
        if (processId == 0)
            return (0, string.Empty);
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(unchecked((int)processId));
            return (unchecked((int)processId), process.ProcessName);
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return (unchecked((int)processId), string.Empty);
        }
    }

    internal static bool TryBounds(nint hwnd, out int left, out int top, out int right, out int bottom)
    {
        left = top = right = bottom = 0;
        if (DwmGetWindowAttribute(hwnd, 9, out Rect rect, Marshal.SizeOf<Rect>()) != 0
            && !GetWindowRect(hwnd, out rect))
        {
            return false;
        }
        left = rect.Left;
        top = rect.Top;
        right = rect.Right;
        bottom = rect.Bottom;
        return right > left && bottom > top;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    /// <summary>A top-level window as the choice of a process's window reads it.</summary>
    internal readonly record struct TopLevelWindow(nint Window, uint ProcessId, bool Usable, long Area);

    /// <summary>
    /// The window of <paramref name="processId"/> a person acts on: the one in
    /// front (<paramref name="front"/>, a root window) when it is the
    /// process's and usable, else the process's largest usable window; 0 when
    /// it has none. Usable is visible, titled, uncloaked, of a real size and
    /// not a shell surface. Measured live: explorer.exe holds the desktop, the
    /// taskbar and a cloaked untitled frame larger than its folder windows
    /// (taking it made every look bound to the process wait out its eight
    /// retries, ≈1.8 s), and with two folder windows open the largest is not
    /// necessarily the one the person is looking at. A process drawn inside an
    /// ApplicationFrameHost <paramref name="frame"/> has that frame as its
    /// window: its own top-level windows are its pop-ups. Measured live on a
    /// packaged app: a click on its search field opened the history flyout
    /// («Host de ventanas emergentes»), the process's only titled window; it
    /// was taken and brought over the frame, the view lost the search field,
    /// and a history entry was clicked as if it were the search.
    /// </summary>
    internal static nint ChooseProcessWindow(IEnumerable<TopLevelWindow> windows, uint processId, nint front, nint frame = 0)
    {
        if (frame != 0)
            return frame;
        nint best = 0;
        long bestArea = 0;
        foreach (TopLevelWindow window in windows)
        {
            if (window.ProcessId != processId || !window.Usable)
                continue;
            if (front != 0 && window.Window == front)
                return window.Window;
            if (window.Area > bestArea)
            {
                bestArea = window.Area;
                best = window.Window;
            }
        }
        return best;
    }

    internal static nint LargestTopLevelWindow(int processId) => ProcessWindow(processId, 0);

    internal static nint ProcessWindow(int processId, nint front) =>
        ChooseProcessWindow(TopLevelWindowsOf(unchecked((uint)processId)), unchecked((uint)processId), front);

    private static List<TopLevelWindow> TopLevelWindowsOf(uint processId)
    {
        var windows = new List<TopLevelWindow>();
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window))
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner != processId)
                return true;
            Rect rect = default;
            bool usable = !IsShellSurface(window) && HasUsableSurface(window) && GetWindowRect(window, out rect);
            long area = usable
                ? (long)Math.Max(0, rect.Right - rect.Left) * Math.Max(0, rect.Bottom - rect.Top)
                : 0;
            windows.Add(new TopLevelWindow(window, owner, usable, area));
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return windows;
    }

    internal static bool HasUsableSurface(nint window)
    {
        if (!IsWindowVisible(window) || GetWindowTextLengthW(window) == 0)
            return false;
        if (DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
            return false;
        if (!TryBounds(window, out int left, out int top, out int right, out int bottom))
            return false;
        return right - left >= 200 && bottom - top >= 150;
    }

    // EnumWindows walks top-level windows from the top of the Z order down:
    // the first visible, titled, uncloaked, non-tool window of another
    // process with a real surface is what the person sees in front.
    private static nint TopmostForeignWindow()
    {
        nint found = 0;
        uint self = unchecked((uint)Environment.ProcessId);
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || GetAncestor(window, 3) != window)
                return true;
            if ((GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner == 0 || owner == self)
                return true;
            if (!HasUsableSurface(window))
                return true;
            found = window;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        return found;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint hwnd);

    [LibraryImport("user32.dll")]
    private static partial int GetWindowTextLengthW(nint hwnd);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int GetClassNameW(nint hwnd, [Out] char[] text, int count);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachThreadInput(uint idAttach, uint idAttachTo, [MarshalAs(UnmanagedType.Bool)] bool attach);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BringWindowToTop(nint hwnd);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindow(nint hwnd, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint hwnd);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int GetWindowTextW(nint hwnd, [Out] char[] text, int count);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindowLongPtrW(nint hwnd, int index);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(
        nint hwnd, int attribute, out int value, int size);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumChildWindows(nint parent, EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint window);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial nint WindowFromPoint(Point point);

    [StructLayout(LayoutKind.Sequential)]
    private struct Point(int x, int y)
    {
        public int X = x;
        public int Y = y;
    }

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint hwnd, uint flags);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint hwnd, out Rect rect);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetCursorPos(int x, int y);

    [LibraryImport("user32.dll")]
    private static partial nint SetThreadDpiAwarenessContext(nint context);

    [LibraryImport("user32.dll")]
    private static partial void mouse_event(
        uint flags, uint dx, uint dy, uint data, nuint extra);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(
        nint hwnd, int attribute, out Rect rect, int size);

    [StructLayout(LayoutKind.Sequential)]
    private unsafe struct ProcessEntry32
    {
        public uint Size;
        public uint Usage;
        public uint ProcessId;
        public nint DefaultHeapId;
        public uint ModuleId;
        public uint Threads;
        public uint ParentProcessId;
        public int PriorityClassBase;
        public uint Flags;
        public fixed ushort ExeFile[260];
    }

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial nint CreateToolhelp32Snapshot(uint flags, uint processId);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool Process32FirstW(nint snapshot, ref ProcessEntry32 entry);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool Process32NextW(nint snapshot, ref ProcessEntry32 entry);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CloseHandle(nint handle);

    internal readonly record struct OpenedSurface(nint Window, bool Drawn);

    internal readonly record struct OpenedApplication(
        int ProcessId,
        DateTime StartedUtc,
        DateTime NotedUtc,
        bool Launched,
        nint Window = 0);

    internal readonly record struct CapturedWindow(
        nint Hwnd,
        byte[] Bmp,
        int Left,
        int Top,
        int Width,
        int Height,
        string Sha256);
}
