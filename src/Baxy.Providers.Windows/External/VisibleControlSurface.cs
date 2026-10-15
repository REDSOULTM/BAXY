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
        // No read brings a window up (v3 point 0, «mirar no roba el foco»): an act by coordinates that follows takes
        // the front inside a burst of the foreground lease, after the person's pause.
        nint hwnd = await ForegroundTargetAsync(cancellationToken).ConfigureAwait(false);
        return hwnd == 0
            ? null
            : await CaptureAsync(hwnd, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// The window <see cref="CaptureForegroundAsync"/> would capture, without capturing it: the window the calls are
    /// bound to while it lives (0 otherwise), or the window a person acts on. Merge of round 1 (fable/cu-v3-vista with
    /// fable/cu-v3-clic and fable/cu-v3-pausa): a bound window behind the person's is no longer brought up before the
    /// act, so it is read where it is; <see cref="CaptureAsync"/> takes a covered window's own drawing, never what
    /// covers it, and only a press by coordinates takes the front, inside a burst of the foreground lease.
    /// </summary>
    internal static async ValueTask<nint> ForegroundTargetAsync(CancellationToken cancellationToken)
    {
        if (RequiredWindow.Value is var required and not 0)
            return IsAlive(required) ? required : 0;
        return await ResolveForegroundAsync(cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// The window a person acts on right now: the root of the foreground
    /// window, or the topmost foreign window when the foreground is ours or
    /// has no usable surface. The compact view, the click and the scroll all
    /// resolve the window here, so they always mean the same one. It is read where it is (v3 point 0, «mirar no
    /// roba el foco»: the accessible tree and the window's own image are read behind the person's window); an act by
    /// coordinates takes the front itself, inside a burst of the foreground lease.
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
        // has no usable surface, take that window (an act by coordinates brings
        // it up in its burst, because the click lands on whatever is on top).
        _ = GetWindowThreadProcessId(hwnd, out uint foregroundProcess);
        // The desktop itself (Progman / WorkerW, «Program Manager») and the
        // taskbar are never the surface a person acts on: when nothing owns the
        // foreground the act lands on the topmost application window.
        if (foregroundProcess == unchecked((uint)Environment.ProcessId) || !HasUsableSurface(hwnd)
            || IsShellSurface(hwnd))
        {
            nint candidate = TopmostForeignWindow();
            if (candidate != 0)
                hwnd = candidate;
        }

        return hwnd;
    }

    /// <summary>
    /// The window of one process: the ApplicationFrameHost frame hosting it
    /// when it draws inside one (a packaged app such as the Calculator has no
    /// top-level window of its own, only its pop-ups), else the
    /// one in front when it is the process's and has a usable surface, else
    /// its largest usable top-level window, read where it is (never brought to
    /// the front: the acts that need the front take it themselves); 0 when the
    /// process shows nothing.
    /// </summary>
    internal static async ValueTask<nint> ResolveProcessWindowAsync(
        int processId,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        // The shared frame host is no app's process: any packaged app's frame would do for it.
        if (IsSharedFrameHost(ProcessIdentity(unchecked((uint)processId)).ProcessName))
            return 0;
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
            if (found == 0 || !(HasUsableSurface(found) || MinimizedDocumentWindow(found)))
                found = frame;
        }

        // v3 point 1: content drawn by a process the application started (WebView2, CEF) is its surface.
        return FamilySurface(found);
    }

    /// <summary>
    /// The application's window when its process is unknown (app.open did not
    /// verify, or the application was already there): the topmost visible
    /// window whose executable is the application, else the topmost one whose
    /// executable's own description names it (<see cref="DescriptionNamesApplication"/>: a file manager whose title is
    /// the folder it shows, goal v3 analysis r3a M5) and that no other application started
    /// (<see cref="LaunchedByAnotherApplication"/>: a runtime carried inside an application describes the runtime),
    /// the one its title also names first (<see cref="ChooseNamedWindow"/>), else the topmost one whose
    /// title names it in its last segment (<see cref="TitleNamesApplication"/>), or the topmost window of the same
    /// packaged application above it (<see cref="PackagedApplication"/>: the image a photo viewer opened, titled by
    /// the file, over the viewer's gallery titled by the application's name).
    /// Never a developer's or BAXY's own window the request did not name
    /// (<see cref="ProtectedFrom"/>). Read where it is; 0 when none is.
    /// cu-v3-elevacion (r9 v3-65): a window that runs as administrator whose program opens again with the person's
    /// rights gives way to a readable copy of that same program (<see cref="PreferReadableCopy"/>): BAXY opens a
    /// console again with the person's rights next to a raised copy it cannot close, and the copy it opened is the one
    /// it works on.
    /// </summary>
    internal static ValueTask<nint> ResolveTitledWindowAsync(
        string application,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (FoldTitle(application).Length == 0)
            return ValueTask.FromResult<nint>(0);
        var executables = new Dictionary<int, string>();
        string ExecutableOf(int processId)
        {
            if (!executables.TryGetValue(processId, out string? executable))
            {
                executable = Applications.WindowsInstalledApplicationPlatform.ExecutableImagePath(processId) ?? string.Empty;
                executables[processId] = executable;
            }

            return executable;
        }

        nint chosen = PreferReadableCopy(
            ResolveTitledWindow(application, accept: null),
            window => WindowProcess(window).ProcessId,
            RunsAboveUs,
            Applications.InvokerLaunch.WindowReopensUnraised,
            ExecutableOf,
            accept => ResolveTitledWindow(application, accept));

        // v3 point 1: content drawn by a process the application started (WebView2, CEF) is its surface.
        return ValueTask.FromResult(FamilySurface(chosen));
    }

    /// <summary>
    /// Review of cu-v3-elevacion (finding 1): <paramref name="chosen"/> stays unless it runs as administrator
    /// (<paramref name="runsAboveUs"/>) and its program would open again with the person's rights
    /// (<paramref name="reopensUnraised"/>); only then is it replaced by the window <paramref name="resolveAccepting"/>
    /// finds among the processes that run that same executable and not above BAXY. A raised window of a program that
    /// raises itself (the Task Manager), or one whose readable namesake is another program (a folder called like it),
    /// is never traded: the view keeps saying «elevated», an honest limit, instead of acting on another window.
    /// </summary>
    internal static nint PreferReadableCopy(
        nint chosen,
        Func<nint, int> processOf,
        Func<int, bool> runsAboveUs,
        Func<int, bool> reopensUnraised,
        Func<int, string> executableOf,
        Func<Func<int, bool>, nint> resolveAccepting)
    {
        if (chosen == 0)
            return 0;
        int raised = processOf(chosen);
        if (!runsAboveUs(raised) || !reopensUnraised(raised))
            return chosen;
        string program = executableOf(raised);
        if (program.Length == 0)
            return chosen;
        nint copy = resolveAccepting(owner =>
            !runsAboveUs(owner) && string.Equals(executableOf(owner), program, StringComparison.OrdinalIgnoreCase));
        return copy != 0 ? copy : chosen;
    }

    // minimized: whether a minimized window a person would restore counts (MinimizedDocumentWindow), only when no usable
    // window is found (estabilización D2).
    private static nint ResolveTitledWindow(string application, Func<int, bool>? accept)
    {
        nint found = ResolveTitledWindow(application, accept, minimized: false);
        return found != 0 ? found : ResolveTitledWindow(application, accept, minimized: true);
    }

    private static nint ResolveTitledWindow(string application, Func<int, bool>? accept, bool minimized)
    {
        nint byProcess = 0;
        bool byProcessEnabled = true;
        bool byProcessSecondary = false;
        nint byProcessBelow = 0;
        nint byDescriptionAndTitle = 0;
        nint byDescription = 0;
        nint byTitle = 0;
        uint self = unchecked((uint)Environment.ProcessId);
        var names = new Dictionary<uint, string>();
        var described = new Dictionary<uint, bool>();
        var packages = new Dictionary<uint, string>();
        var topmostOfPackage = new Dictionary<string, nint>(StringComparer.OrdinalIgnoreCase);
        Dictionary<uint, uint>? parents = null;
        HashSet<uint>? windowed = null;
        uint? shell = null;
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || GetAncestor(window, 3) != window)
                return true;
            if ((GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner == 0 || owner == self || !(HasUsableSurface(window) || (minimized && MinimizedDocumentWindow(window))))
                return true;
            if (accept is not null && !accept(unchecked((int)owner)))
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
                // Ronda 24 (pasada r23 v3-05, v3-06): the first window of the application's process in Z order may be a
                // secondary one («86 aviso(s)») above the window the person works in. Revision 1 (B2): an owned modal
                // never enters this enumeration, its disabled owner does; that topmost window disabled, the modal is above
                // it and the enumeration stops there: another enabled window of the same process (a second browser
                // window) is never taken in its place. Revision 4 (B1): what makes the topmost a secondary is the window
                // itself (a dialog box, a window that cannot be maximized: IsSecondaryWindow), never whether its title
                // carries the application's name: an open message or an open photo, titled by its content, stays the
                // topmost and is kept. Only below a secondary does the enumeration go on, to the process's next window
                // that is no secondary, kept when enabled (a disabled one is under a modal the secondary may be).
                bool enabled = IsWindowEnabled(window);
                bool secondary = IsSecondaryWindow(GetWindowLongPtrW(window, -16).ToInt64(), ClassName(window));
                if (byProcess == 0)
                {
                    byProcess = window;
                    byProcessEnabled = enabled;
                    byProcessSecondary = secondary;
                    return byProcessEnabled && byProcessSecondary;
                }

                if (secondary)
                    return true;
                if (enabled)
                    byProcessBelow = window;
                return false;
            }

            if (byProcess != 0)
                return true;

            if (!packages.TryGetValue(owner, out string? package))
            {
                package = PackagedApplication(owner);
                packages[owner] = package;
            }

            if (package.Length > 0)
                topmostOfPackage.TryAdd(package, window);

            if (!described.TryGetValue(owner, out bool descriptionNames))
            {
                descriptionNames = DescriptionNamesApplication(ProcessDescription(owner), application)
                    && !LaunchedByAnotherApplication(
                        owner,
                        parents ??= ParentByProcess(),
                        ExecutableName,
                        StartedNoLaterThan,
                        process => (windowed ??= ProcessesOwningTopLevelWindows()).Contains(process),
                        shell ??= ShellProcess(),
                        self);
                described[owner] = descriptionNames;
            }

            bool titleNames = TitleNamesApplication(WindowTitle(window), application);
            if (descriptionNames && byDescription == 0)
                byDescription = window;
            if (descriptionNames && titleNames && byDescriptionAndTitle == 0)
                byDescriptionAndTitle = window;
            if (byTitle == 0 && titleNames)
                byTitle = window;
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        nint titledPackageTopmost = 0;
        if (byTitle != 0 && GetWindowThreadProcessId(byTitle, out uint titledOwner) != 0
            && packages.TryGetValue(titledOwner, out string? titledPackage) && titledPackage.Length > 0)
        {
            titledPackageTopmost = topmostOfPackage.GetValueOrDefault(titledPackage);
        }

        return ChooseNamedWindow(
            byProcess, byDescriptionAndTitle, byDescription, byTitle, titledPackageTopmost, byProcessBelow, byProcessEnabled,
            byProcessSecondary);
    }

    /// <summary>
    /// The window <see cref="ResolveTitledWindowAsync"/> takes, from the topmost window of each kind: the executable
    /// is the application; else its description names it and its title too (among the windows of a process whose
    /// description names the application, the one its title names, not a secondary list or chat above it); else only
    /// its description names it; else only its title, or, when that window belongs to a packaged application,
    /// <paramref name="titledPackageTopmost"/>: the topmost window of that same package, the one the person used
    /// last (goal v3 r7: a photo opened from its folder shows in a window of the viewer's package titled by the file,
    /// above the viewer's gallery titled by the application's name; «la imagen que tengo abierta» was looked for in
    /// the gallery). 0 when none does. Ronda 24 (pasada r23 v3-05, v3-06), revision 4 (B1): the topmost window of the
    /// application's own process enabled and a secondary itself (<paramref name="byProcessSecondary"/>: a dialog box
    /// such as «86 aviso(s)», a window that cannot be maximized), the process's next enabled window that is no secondary
    /// (<paramref name="byProcessBelow"/>: the one the person used last below it) comes first. Any other topmost of the
    /// process is kept whatever its title says: an open message «RE: Presupuesto - Mensaje (HTML)» above the main window
    /// of its mail application, an open photo «paisaje.jpg» above the gallery «Photos». Revision 1 (B2): the topmost
    /// window of the process disabled (<paramref name="byProcessEnabled"/> false: a modal dialog is open over it, and an
    /// owned dialog never enters the enumeration) is kept: the modal is reached through it, never a second window of the
    /// same application acted in instead.
    /// </summary>
    internal static nint ChooseNamedWindow(
        nint byProcess, nint byDescriptionAndTitle, nint byDescription, nint byTitle, nint titledPackageTopmost = 0,
        nint byProcessBelow = 0, bool byProcessEnabled = true, bool byProcessSecondary = false) =>
        byProcessBelow != 0 && byProcess != 0 && byProcessEnabled && byProcessSecondary ? byProcessBelow
        : byProcess != 0 ? byProcess
        : byDescriptionAndTitle != 0 ? byDescriptionAndTitle
        : byDescription != 0 ? byDescription
        : byTitle != 0 && titledPackageTopmost != 0 ? titledPackageTopmost
        : byTitle;

    /// <summary>
    /// Revision 4 of ronda 24 (B1): a top-level window that is a secondary of its application by itself, never by its
    /// title: a dialog box (the system's dialog class) or a window without a maximize box. A window the person works in
    /// (a main window, an open message, an open photo) can be maximized.
    /// </summary>
    internal static bool IsSecondaryWindow(long style, string className) =>
        string.Equals(className, "#32770", StringComparison.Ordinal) || (style & 0x10000) == 0;

    /// <summary>
    /// The packaged application a process runs as (its AppUserModelID, «Publisher.App_hash!App»); empty for a process
    /// that is not packaged (a classic desktop executable, a browser and the web apps it draws, the shared frame host
    /// of the packaged apps, the shell) or that cannot be read. Two processes of one package are one application.
    /// </summary>
    internal static string PackagedApplication(uint processId)
    {
        if (processId == 0)
            return string.Empty;
        nint process = OpenProcess(0x1000, false, processId);
        if (process == 0)
            return string.Empty;
        try
        {
            char[] buffer = new char[131];
            uint length = (uint)buffer.Length;
            return GetApplicationUserModelId(process, ref length, buffer) == 0 && length > 1
                ? new string(buffer, 0, (int)length - 1)
                : string.Empty;
        }
        finally
        {
            _ = CloseHandle(process);
        }
    }

    [LibraryImport("kernel32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int GetApplicationUserModelId(nint process, ref uint length, [Out] char[] applicationUserModelId);

    /// <summary>
    /// Whether <paramref name="process"/> was started by another application: going up through the ancestors that
    /// run its same executable (a runtime's own helper processes), the first one that runs another executable is
    /// alive, started no later than its child, is neither the shell (<paramref name="shell"/>, what a person starts
    /// from the desktop or the taskbar) nor this product (<paramref name="self"/>), and owns top-level windows (a
    /// service host that starts packaged applications owns none). Such a process is a runtime the application carries
    /// inside (an embedded browser, a web helper): its executable's description names the runtime, never the
    /// application the person asked for (safety review 2026-10-07: an embedded browser described «<Browser> <Runtime>»
    /// drawing a chat application's window was taken for the browser «<Browser>»). Unknown ancestry is not another application.
    /// </summary>
    internal static bool LaunchedByAnotherApplication(
        uint process,
        IReadOnlyDictionary<uint, uint> parents,
        Func<uint, string> executable,
        Func<uint, uint, bool> startedNoLaterThan,
        Func<uint, bool> ownsTopLevelWindows,
        uint shell,
        uint self)
    {
        string own = executable(process);
        if (process == 0 || own.Length == 0)
            return false;
        uint current = process;
        for (int depth = 0; depth < 16; depth++)
        {
            if (!parents.TryGetValue(current, out uint parent) || parent == 0 || parent == current)
                return false;
            // A parent id can outlive its process and be handed to a newer one: that one started nothing here.
            if (!startedNoLaterThan(parent, current))
                return false;
            if (parent == shell || parent == self)
                return false;
            string launcher = executable(parent);
            if (launcher.Length == 0)
                return false;
            if (string.Equals(launcher, own, StringComparison.OrdinalIgnoreCase))
            {
                current = parent;
                continue;
            }

            return ownsTopLevelWindows(parent);
        }

        return false;
    }

    private static string ExecutableName(uint processId) => ProcessIdentity(processId).ProcessName;

    // Whether the first process started no later than the second (a second of tolerance); false when either start is unknown.
    private static bool StartedNoLaterThan(uint first, uint second) =>
        StartTime(first) is { } firstStarted && StartTime(second) is { } secondStarted
        && firstStarted <= secondStarted.AddSeconds(1);

    // The processes that own at least one top-level window, shown or hidden.
    private static HashSet<uint> ProcessesOwningTopLevelWindows()
    {
        var owners = new HashSet<uint>();
        EnumWindowsProc callback = (window, _) =>
        {
            if (GetWindowThreadProcessId(window, out uint owner) != 0 && owner != 0)
                owners.Add(owner);
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return owners;
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
        // frame hosts (its process is not the frame's), nor a window of the
        // application's process family (v3 point 1: the content a WebView2 or
        // CEF child process draws over the application's own window).
        if (coverOwner == owner || coverOwner == unchecked((uint)Environment.ProcessId)
            || root == FamilyPeer(hwnd)
            || (IsVisibleFrame(hwnd) && FrameHosts(hwnd, hosted => hosted == coverOwner))
            || IsFamilyContent(hwnd, owner, root, coverOwner))
            return 0;
        return root;
    }

    // The windows where the person's own work and BAXY live: an editor, an IDE, a terminal, a console, BAXY itself.
    // Safety review 2026-10-07: a file «<App>LocalAdapter.cs» open in Visual Studio Code was the first window titled
    // «<App>», and a mission would have typed and pressed keys in the editor where the developer's agent lives. Such
    // a window is the application only when the request names that very application (the names on the right); BAXY's
    // own never is.
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
        // Estabilización U (revisión H2): BAXY's own window is never acted on, named or not: its view holds its
        // own settings (the bypass switch and its question), which only the person changes.
        ["Baxy"] = [],
        ["baxy-core"] = [],
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
    /// The executable's own description (its FileDescription, «<Name> File Manager») names the application: the whole
    /// name, or the name followed by more words («<Name>» names «<Name> File Manager»), when the name has a word of its
    /// own (not only «Microsoft» or «app»). A description that only shares a word with the name («Panel» of «panel de
    /// miniaturas») never does.
    /// </summary>
    internal static bool DescriptionNamesApplication(string? description, string? application)
    {
        string named = FoldTitle(description);
        string wanted = FoldTitle(application);
        if (named.Length == 0 || wanted.Length == 0 || ApplicationWords(wanted).Length == 0)
            return false;
        return named == wanted
            || (named.StartsWith(wanted, StringComparison.Ordinal) && !char.IsLetterOrDigit(named[wanted.Length]));
    }

    /// <summary>The FileDescription of a process's executable; empty when it cannot be read (an elevated process).</summary>
    internal static string ProcessDescription(uint processId)
    {
        if (processId == 0)
            return string.Empty;
        nint process = OpenProcess(0x1000, false, processId);
        if (process == 0)
            return string.Empty;
        try
        {
            char[] buffer = new char[1024];
            int length = buffer.Length;
            if (!QueryFullProcessImageNameW(process, 0, buffer, ref length) || length <= 0)
                return string.Empty;
            string path = new(buffer, 0, length);
            return System.Diagnostics.FileVersionInfo.GetVersionInfo(path).FileDescription?.Trim() ?? string.Empty;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
            return string.Empty;
        }
        finally
        {
            _ = CloseHandle(process);
        }
    }

    [LibraryImport("kernel32.dll", EntryPoint = "QueryFullProcessImageNameW", StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool QueryFullProcessImageNameW(nint process, uint flags, [Out] char[] path, ref int length);

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
        // «Documento1 - Word (No responde)»: a state the system adds in parentheses after the name is no word of it.
        string segment = TrailingState().Replace(TitleSeparator().Split(FoldTitle(title))[^1], string.Empty).Trim();
        if (segment.Length == 0)
            return false;
        if (NamesAsWords(segment, wanted))
            return true;
        string[] words = ApplicationWords(wanted);
        if (!words.Any(word => NamesAsWords(segment, word)))
            return false;
        // r15b v3-47: a word the segment shares with the name names the application when the segment says nothing
        // else («Word» for «Microsoft Word»), when two words of the name are said together («Reproductor de Windows
        // Media» for «Windows Media Player Legacy»), or when the name writes that word as a proper name («Riot Client»
        // for «Cliente de Riot», «Zoom Meeting» for «Zoom Workplace»). «Sistema y seguridad» only shares the common
        // noun «sistema» with «Información del sistema» and is another window (revisión destino del pedido).
        string[] own = ApplicationWords(new string([.. segment.Select(character => char.IsLetterOrDigit(character) ? character : ' ')]));
        if (own.Length > 0 && own.All(word => words.Contains(word, StringComparer.Ordinal)))
            return true;
        if (Enumerable.Range(0, Math.Max(0, words.Length - 1)).Any(at => NamesAsWords(segment, $"{words[at]} {words[at + 1]}")))
            return true;
        return ProperNameWords(application!).Any(word => NamesAsWords(segment, word));
    }

    /// <summary>
    /// The words a name writes as proper names: a capitalized word after the first («Cliente de Riot», «Microsoft
    /// Word»), and the first too when no word of the name is written in lower case («Zoom Workplace»). «Información del
    /// sistema» has none; the system's own name («Seguridad de Windows») is carried by many and names none.
    /// </summary>
    private static string[] ProperNameWords(string application)
    {
        string[] written = application.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        bool titleCase = written.All(word => !char.IsLetter(word[0]) || char.IsUpper(word[0]));
        string[] own = ApplicationWords(FoldTitle(application));
        return [.. written
            .Select((word, at) => (word, at))
            .Where(item => char.IsUpper(item.word[0]) && (item.at > 0 || titleCase))
            .Select(item => FoldTitle(item.word))
            .Where(word => own.Contains(word, StringComparer.Ordinal) && !PlatformWords.Contains(word))];
    }

    // The system's own name, which the names of many of its applications carry.
    private static readonly HashSet<string> PlatformWords = new(StringComparer.Ordinal) { "windows" };

    [System.Text.RegularExpressions.GeneratedRegex(@"\s*\([^()]*\)\s*$", System.Text.RegularExpressions.RegexOptions.CultureInvariant)]
    private static partial System.Text.RegularExpressions.Regex TrailingState();

    // Words that join a name and name nothing by themselves («Información del sistema», «Bloc de notas»).
    private static readonly HashSet<string> FunctionWords = new(StringComparer.Ordinal)
    {
        "del", "and", "for", "con", "por", "para", "una", "uno", "las", "los", "the",
    };

    private static string[] ApplicationWords(string folded) =>
        [.. folded.Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Where(word => word.Length >= 3 && !GenericApplicationWords.Contains(word) && !FunctionWords.Contains(word))];

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

    /// <summary>
    /// The process a visible ApplicationFrameHost frame hosts; 0 when the window is no such frame or hosts nothing.
    /// Review 2026-10-07: the frame's own process is one ApplicationFrameHost shared by every packaged app on screen
    /// (Settings, the Store, the Calculator); a mission bound to it could take another app's frame on its next look.
    /// </summary>
    internal static uint HostedProcess(nint frame)
    {
        if (!IsVisibleFrame(frame))
            return 0;
        uint found = 0;
        _ = FrameHosts(frame, owner =>
        {
            found = owner;
            return true;
        });
        return found;
    }

    /// <summary>
    /// The process a view names as its window's: the hosted app's for an ApplicationFrameHost frame (the shared host
    /// is never a mission's process), else the window's own.
    /// </summary>
    internal static (int ProcessId, string ProcessName) ViewProcess(nint hwnd)
    {
        uint hosted = HostedProcess(hwnd);
        return hosted == 0 ? WindowProcess(hwnd) : ProcessIdentity(hosted);
    }

    /// <summary>
    /// The processes that draw a window: its own and those of its child windows (a frame's hosted app, an embedded web
    /// view), at most eight. A pop-up such as a tooltip belongs to the process that drew the part under the cursor.
    /// </summary>
    internal static IReadOnlyList<int> DrawingProcesses(nint window)
    {
        var owners = new List<int>();
        if (window == 0)
            return owners;
        _ = GetWindowThreadProcessId(window, out uint own);
        if (own != 0)
            owners.Add((int)own);
        EnumWindowsProc children = (child, unused) =>
        {
            GetWindowThreadProcessId(child, out uint owner);
            if (owner != 0 && !owners.Contains((int)owner))
                owners.Add((int)owner);
            return owners.Count < 8;
        };
        _ = EnumChildWindows(window, children, nint.Zero);
        return owners;
    }

    /// <summary>Whether a process name is the frame host shared by the packaged apps (never one app's process).</summary>
    internal static bool IsSharedFrameHost(string? processName) =>
        string.Equals(processName, "ApplicationFrameHost", StringComparison.OrdinalIgnoreCase);

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
        // The front is taken on purpose: a guard handing back a front an opened application took stops here.
        Applications.ForegroundHandBack.NoteFrontTaken();
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

    /// <summary>The window the calls of this scope are bound to (<see cref="RequireWindow"/>), or 0.</summary>
    internal static nint BoundWindow => RequiredWindow.Value;

    // The window in front is this one (or a window inside it), or its family peer (v3 point 1: the application's
    // window and the content a process it started draws over it hold the front for each other, never another process).
    internal static bool ForegroundIs(nint window)
    {
        nint foreground = GetForegroundWindow();
        if (foreground == 0 || window == 0)
            return false;
        nint root = GetAncestor(foreground, 2);
        nint front = root == 0 ? foreground : root;
        return front == window || (FamilyPeer(window) is var peer and not 0 && front == peer)
            || HeldByItsOwner(window, front, static hwnd => GetWindow(hwnd, 4), AppWindow, TakesActivation, ProcessOf);
    }

    /// <summary>
    /// The window in front is this one, a window inside it, or a window it owns (its own dialog or pop-up). Another
    /// top-level window of the same process is not: a second folder window, the taskbar of the shell, another
    /// browser window are the person's, and keys or a lease meant for this window never count them as it. Ronda 24
    /// (t-menu-4): a pop-up is part of its owner, so the owner in front holds it too (<see cref="HeldByItsOwner"/>).
    /// </summary>
    internal static bool ForegroundIsOrOwnedBy(nint window)
    {
        nint foreground = GetForegroundWindow();
        if (IsOrOwnedByFamily(window, FamilyPeer(window), foreground,
                static hwnd => GetAncestor(hwnd, 2), static hwnd => GetWindow(hwnd, 4)))
            return true;
        nint root = foreground == 0 ? 0 : GetAncestor(foreground, 2);
        return HeldByItsOwner(
            window, root == 0 ? foreground : root, static hwnd => GetWindow(hwnd, 4), AppWindow, TakesActivation, ProcessOf);
    }

    /// <summary>
    /// Ronda 24 (t-menu-4): whether <paramref name="window"/> is a pop-up of the window in front (<paramref name="front"/>,
    /// a root): owned by it (GW_OWNER), of its very process, no window of its own on the taskbar (no
    /// WS_EX_APPWINDOW), and one that never takes the activation itself (<see cref="TakesActivation(long, long)"/>). A
    /// menu or a list a window shows lives in such a window while its owner keeps the activation, and the keys reach it
    /// through its owner. Review 1 of ronda 24 (finding 1): a modeless dialog with a title bar (a find and replace the
    /// mission opened) takes the activation itself, so its owner in front never holds it: the keys meant for it would
    /// land in the person's document. Contracases: such a dialog, a window of another process, a window with a taskbar
    /// button of its own (a second main window the first owns), and an owner that is not the one in front are never held.
    /// </summary>
    internal static bool HeldByItsOwner(
        nint window,
        nint front,
        Func<nint, nint> owner,
        Func<nint, bool> appWindow,
        Func<nint, bool> takesActivation,
        Func<nint, uint> process)
    {
        if (window == 0 || front == 0 || window == front || owner(window) != front || appWindow(window)
            || takesActivation(window))
            return false;
        uint own = process(window);
        return own != 0 && own == process(front);
    }

    private static bool AppWindow(nint window) => (GetWindowLongPtrW(window, -20).ToInt64() & 0x40000) != 0;

    private static bool TakesActivation(nint window) =>
        TakesActivation(GetWindowLongPtrW(window, -16).ToInt64(), GetWindowLongPtrW(window, -20).ToInt64());

    /// <summary>
    /// Review 1 of ronda 24 (finding 1): whether a top-level window with these styles takes the activation itself.
    /// Never one marked WS_EX_NOACTIVATE, nor a pop-up (WS_POPUP) without a title bar (no full WS_CAPTION): a menu, a
    /// list, a suggestions drop-down. Any other does: a dialog with its title bar, an overlapped window.
    /// </summary>
    internal static bool TakesActivation(long style, long exStyle)
    {
        const long popup = 0x80000000L, caption = 0x00C00000L, noActivate = 0x08000000L;
        if ((exStyle & noActivate) != 0)
            return false;
        return (style & popup) == 0 || (style & caption) == caption;
    }

    /// <summary>
    /// Whether the window Windows shows at a point of the screen (physical pixels; the one a press or the wheel there
    /// reaches) is this window, a window inside it, a window it owns, or its family peer. Safety review r10a: the window
    /// holding the front and the point lying in its rectangle do not say it, since a window of another application kept
    /// always on top (a video or call picture-in-picture, a sticky note) may cover that point.
    /// </summary>
    internal static bool PointShows(nint window, int screenX, int screenY)
    {
        nint shown = InPhysicalPixels(() => WindowFromPoint(new Point(screenX, screenY)));
        return IsOrOwnedByFamily(window, FamilyPeer(window), shown,
            static hwnd => GetAncestor(hwnd, 2), static hwnd => GetWindow(hwnd, 4));
    }

    /// <summary>
    /// As <see cref="PointShows"/>, but true when it cannot be told: no window at the point, or the point could not be
    /// read in physical pixels. For the lease's question whether the person's input may have reached a window (review
    /// r2 of interrupcion-fantasma), where a doubt counts as reached; a click's guard keeps <see cref="PointShows"/>.
    /// </summary>
    internal static bool PointMayShow(nint window, int screenX, int screenY)
    {
        nint previous = SetThreadDpiAwarenessContext(PerMonitorAwareV2);
        nint shown;
        try
        {
            shown = WindowFromPoint(new Point(screenX, screenY));
        }
        finally
        {
            if (previous != 0)
                _ = SetThreadDpiAwarenessContext(previous);
        }

        return MayShow(window, FamilyPeer(window), shown, physical: previous != 0,
            static hwnd => GetAncestor(hwnd, 2), static hwnd => GetWindow(hwnd, 4));
    }

    /// <summary>
    /// The judgement of <see cref="PointMayShow"/>: whether <paramref name="shown"/> (the window at the point, 0 for
    /// none) may be the window or its family peer; true when nothing was found or the point was not physical.
    /// </summary>
    internal static bool MayShow(
        nint window, nint peer, nint shown, bool physical, Func<nint, nint> root, Func<nint, nint> owner) =>
        !physical || shown == 0 || IsOrOwnedByFamily(window, peer, shown, root, owner);

    /// <summary>
    /// <see cref="IsOrOwnedBy"/> for the window or its family peer (v3 point 1, <see cref="FamilyPeer"/>: the
    /// application's window and the content a process it started draws over it); 0 for no peer.
    /// </summary>
    internal static bool IsOrOwnedByFamily(
        nint window, nint peer, nint foreground, Func<nint, nint> root, Func<nint, nint> owner) =>
        IsOrOwnedBy(window, foreground, root, owner) || (peer != 0 && IsOrOwnedBy(peer, foreground, root, owner));

    /// <summary>
    /// Whether <paramref name="foreground"/> is <paramref name="window"/>, inside it (same root) or owned by it,
    /// following the owner chain of the foreground's root a few steps.
    /// </summary>
    internal static bool IsOrOwnedBy(nint window, nint foreground, Func<nint, nint> root, Func<nint, nint> owner)
    {
        if (window == 0 || foreground == 0)
            return false;
        nint current = root(foreground);
        if (current == 0)
            current = foreground;
        for (int step = 0; step < 8 && current != 0; step++)
        {
            if (current == window)
                return true;
            current = owner(current);
        }

        return false;
    }

    private sealed class RequiredWindowScope(nint previous) : IDisposable
    {
        public void Dispose() => RequiredWindow.Value = previous;
    }

    // The window as drawn now, held in memory: what the view, a click and a scroll compare and read is never written.
    // A window nothing covers is copied from the screen (the fast way); one behind another window draws itself
    // (WindowsScreenshotProvider.CaptureCoveredWindowImage), so a look behind the person's window reads that window,
    // never what covers it (v3 point 0). The caller says when it already knows a cover is there (one always on top,
    // which the Z-order walk leaves out).
    // An image compared with an earlier one is taken the same way (selfDrawn: the earlier one's SelfDrawn): the
    // screen copy and the window's own drawing of an unchanged window differ (the caption, what covers it), and a
    // click or a scroll that did nothing would read as a changed surface.
    internal static ValueTask<CapturedWindow?> CaptureAsync(
        nint hwnd,
        CancellationToken cancellationToken,
        bool covered = false,
        bool? selfDrawn = null)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (hwnd == 0)
            return ValueTask.FromResult<CapturedWindow?>(null);
        ShowBehind(hwnd);
        if (!TryBounds(hwnd, out int left, out int top, out _, out _))
            return ValueTask.FromResult<CapturedWindow?>(null);
        bool drawsItself = selfDrawn ?? (covered || CoveredFromAbove(hwnd));
        WindowImage image = drawsItself
            ? WindowsScreenshotProvider.CaptureCoveredWindowImage(hwnd)
            : WindowsScreenshotProvider.CaptureWindowImage(hwnd);
        return ValueTask.FromResult<CapturedWindow?>(
            new CapturedWindow(hwnd, image.Bmp, left, top, image.Width, image.Height, image.Sha256)
            {
                SelfDrawn = drawsItself,
            });
    }

    /// <summary>
    /// A minimized window draws nothing (no capture gets it) and its accessible tree shrinks: it is shown at its
    /// place without being activated, right behind the window the person has in front, which keeps the front and
    /// the keyboard (v3 point 0). Nothing happens to a window that is not minimized.
    /// </summary>
    internal static void ShowBehind(nint hwnd)
    {
        if (hwnd == 0 || !IsIconic(hwnd))
            return;
        nint foreground = GetForegroundWindow();
        nint root = foreground == 0 ? 0 : GetAncestor(foreground, 2);
        // SW_SHOWNOACTIVATE (4); then below the person's window: SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE.
        _ = ShowWindow(hwnd, 4);
        if (root != 0 && root != hwnd)
            _ = SetWindowPos(hwnd, root, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010);
    }

    /// <summary>The refusal of a point located on a surface that changed while the person's pause was waited for.</summary>
    internal const string SurfaceChangedWhileWaiting = "visible_surface_changed_while_waiting";

    /// <summary>
    /// The same window, at the same place and size, drawn the same: a point located on one capture still means the
    /// same thing on the other.
    /// </summary>
    internal static bool SameSurface(CapturedWindow located, CapturedWindow again) =>
        located.Hwnd == again.Hwnd
        && located.Left == again.Left
        && located.Top == again.Top
        && located.Width == again.Width
        && located.Height == again.Height
        && string.Equals(located.Sha256, again.Sha256, StringComparison.Ordinal);

    /// <summary>
    /// Review of fable/cu-v3-pausa: a point is located on a capture taken before the wait for the person's pause, and
    /// that wait (up to the lease's ceiling) happens exactly while the person is active. Once the burst is granted the
    /// window is captured again: the new capture is the baseline of the post-read, and <see cref="Moved"/> says that
    /// the window moved or was resized (no located point holds then), while <see cref="Redrawn"/> says only its
    /// drawing changed (a caller that can locate again does so on the new capture; one that cannot refuses).
    /// </summary>
    internal readonly record struct SurfaceAfterWait(CapturedWindow? Again, bool Moved, bool Redrawn)
    {
        internal bool Same => Again is not null && !Moved && !Redrawn;
    }

    internal static async ValueTask<SurfaceAfterWait> SurfaceAfterWaitAsync(
        CapturedWindow located,
        Func<nint, CancellationToken, ValueTask<CapturedWindow?>> capture,
        CancellationToken cancellationToken)
    {
        CapturedWindow? again = await capture(located.Hwnd, cancellationToken).ConfigureAwait(false);
        if (again is not { } seen)
            return new SurfaceAfterWait(null, true, false);
        bool moved = seen.Hwnd != located.Hwnd
            || seen.Left != located.Left
            || seen.Top != located.Top
            || seen.Width != located.Width
            || seen.Height != located.Height;
        return new SurfaceAfterWait(seen, moved, !moved && !SameSurface(located, seen));
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

    // The opened application's largest usable window, and whether it looks drawn; no window while it has none yet
    // (an updater or splash only, or nothing). Measured on a cold client launch: its main window came up with the
    // navigation bar over a black page (one colour on 76–96 % of the window) for about three seconds, and a click on
    // the bar then was undone when the client loaded its start page; once the page is drawn, one colour covers about
    // a third. A pop-up of the same application over the main window (a chat) is not what a person opening the
    // application acts on: with bringToFront the main window is brought back in front. Neither a look nor a click
    // asks for it any more (v3 point 0, fix 1): both reach the window where it is, behind the person's own, and only
    // the pointer, last, takes the front inside a burst of the foreground lease.
    internal static async ValueTask<OpenedSurface> FrontOpenedAsync(
        OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken,
        bool bringToFront = false)
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
        if (bringToFront && ((root == 0 ? foreground : root) != target || CoveredFromAbove(target)))
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

    /// <summary>
    /// A left click on a point of the screen, only inside a burst of the foreground lease that may still act (the
    /// person paused and has not touched anything since); whether it was sent. The caller restores the burst.
    /// </summary>
    internal static bool Click(IInputBurst burst, int screenX, int screenY, nint window = 0)
    {
        if (!PointAt(burst, screenX, screenY))
            return false;
        // Right before the press: the point still shows the window it is meant for (safety review r10a; a window
        // kept always on top may have come over it since the check).
        if (window != 0 && !PointShows(window, screenX, screenY))
            return false;
        mouse_event(0x0002, 0, 0, 0, BaxyInputMark.Value);
        mouse_event(0x0004, 0, 0, 0, BaxyInputMark.Value);
        return true;
    }

    /// <summary>
    /// The cursor placed on a point of the screen in physical pixels, the unit of every point the views hold (the
    /// capture, the window bounds from the compositor, the accessible tree's rectangles). This process is not DPI
    /// aware: a point set without a per-monitor context is scaled by the monitor's factor (measured 2026-10-07 at
    /// 125 %: a word read at y=440 in a folder window's side list was clicked at y=550, three rows lower, and the
    /// window opened another folder). The cursor moves only inside a burst of the foreground lease that may still act.
    /// </summary>
    internal static bool PointAt(IInputBurst burst, int screenX, int screenY) =>
        burst.MayAct && InPhysicalPixels(() => SetCursorPos(screenX, screenY));

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

    /// <summary>r29: <see cref="RunsAboveUs"/> of a process that is still running (a process that already ended
    /// cannot be opened either, and is not «raised»).</summary>
    internal static bool LiveProcessRunsAboveUs(int processId) =>
        processId > 0 && ProcessIdentity(unchecked((uint)processId)).ProcessName.Length > 0 && RunsAboveUs(processId);

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

    /// <summary>
    /// Goal v3 point 2 (modal surface): a window that a modal dialog of its own disabled («Guardar como», «Cambiar
    /// tamaño», «Fuente») is acted on through that dialog, as a person does: the enabled pop-up Windows names for it
    /// (GW_ENABLEDPOPUP), of the same process and visible, followed while that one is disabled by another. An enabled
    /// window, or one without such a pop-up, is itself.
    /// </summary>
    internal static nint ModalSurface(nint window) => ModalSurface(
        window,
        IsWindowEnabled,
        hwnd => GetWindow(hwnd, 6),
        IsAlive,
        hwnd => GetWindowThreadProcessId(hwnd, out uint process) == 0 ? 0 : process);

    internal static nint ModalSurface(
        nint window, Func<nint, bool> enabled, Func<nint, nint> enabledPopup, Func<nint, bool> alive, Func<nint, uint> process)
    {
        nint surface = window;
        for (int depth = 0; depth < 4 && surface != 0 && !enabled(surface); depth++)
        {
            nint popup = enabledPopup(surface);
            if (popup == 0 || popup == surface || !alive(popup) || process(popup) != process(window))
                break;
            surface = popup;
        }

        return surface;
    }

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
        return ProcessIdentity(processId);
    }

    private static (int ProcessId, string ProcessName) ProcessIdentity(uint processId)
    {
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

    /// <summary>
    /// A top-level window as the choice of a process's window reads it; <paramref name="Minimized"/>: a minimized window
    /// a person would restore (<see cref="MinimizedDocumentWindow"/>), which has no usable surface while minimized.
    /// </summary>
    internal readonly record struct TopLevelWindow(nint Window, uint ProcessId, bool Usable, long Area, bool Minimized = false);

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
    /// Estabilización D2 (banco h1, s11 and u1: a chat client and a music player already running and minimized; the
    /// view read the person's editor in their place): a process with no usable window but a minimized one a person would restore has
    /// that one, the topmost; the look shows it behind the person's window without activating it
    /// (<see cref="ShowBehind"/>) and an act brings it up restored.
    /// </summary>
    internal static nint ChooseProcessWindow(IEnumerable<TopLevelWindow> windows, uint processId, nint front, nint frame = 0)
    {
        if (frame != 0)
            return frame;
        nint best = 0;
        long bestArea = 0;
        nint minimized = 0;
        foreach (TopLevelWindow window in windows)
        {
            if (window.ProcessId == processId && window.Minimized && minimized == 0)
                minimized = window.Window;
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
        return best != 0 ? best : minimized;
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
            windows.Add(new TopLevelWindow(window, owner, usable, area, !usable && MinimizedDocumentWindow(window)));
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

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetWindowPos(nint hwnd, nint insertAfter, int x, int y, int width, int height, uint flags);

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
    private static partial nint GetWindow(nint hwnd, uint command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowEnabled(nint hwnd);

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
        string Sha256)
    {
        // Drawn by the window itself (PrintWindow) rather than copied from the screen.
        internal bool SelfDrawn { get; init; }
    }
}
