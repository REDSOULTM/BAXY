using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Applications;

public sealed class WindowsCalculatorOpenProvider : IApplicationOpenProvider
{
    private static readonly TimeSpan Delay = TimeSpan.FromMilliseconds(100);
    private readonly ICalculatorPlatform _platform;

    public WindowsCalculatorOpenProvider()
        : this(new WindowsCalculatorPlatform())
    {
    }

    internal WindowsCalculatorOpenProvider(ICalculatorPlatform platform)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
    }

    public async ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken)
    {
        if (!string.Equals(request.ApplicationId, ApplicationIds.Calculator, StringComparison.Ordinal))
            return Failure(request, ApplicationOpenErrorCodes.InvalidApplication, false);
        cancellationToken.ThrowIfCancellationRequested();
        IReadOnlyList<CalculatorSnapshot> before = _platform.Inventory();
        CalculatorSnapshot? selected = before.FirstOrDefault(static item => item.Visible);
        bool reused = selected is not null;
        // v3 point 0 (arreglo 4): without «foreground» the front stays the person's; the packaged Calculator is
        // activated by Windows when it starts, so the front is handed back at once and the receipt says so. Asked in
        // front, it is also read: a person working in it when the opening ends gets it back (OpeningFront).
        long previousFront = _platform.ForegroundWindow();
        if (!reused)
        {
            if (!_platform.Launch()) return Failure(request, ApplicationOpenErrorCodes.LaunchFailed, false);
            // No Calculator was visible before, so the one visible now is the one this opening showed. Windows keeps a
            // prelaunched CalculatorApp process suspended and shows that same process: requiring a new process left
            // every cold opening unverified after the window was on screen, and each retry opened another one
            // (2026-10-15, four windows from one request).
            for (int attempt = 0; attempt < 30 && selected is null; attempt++)
            {
                if (attempt > 0) await _platform.DelayAsync(Delay, cancellationToken).ConfigureAwait(false);
                selected = _platform.Inventory().FirstOrDefault(static candidate => candidate.Visible);
            }
        }
        if (selected is null) return Failure(request, ApplicationOpenErrorCodes.VerificationFailed, !reused);
        // r20b palanca 4 review: the rule of every path of app.open (OpeningFront), read now that the window is seen,
        // right before the front would be asked for: a person working in another window keeps their keyboard and the
        // Calculator is shown above it without the activation; a request from BAXY's own window takes the front.
        long opened = selected.WindowHandle;
        long person = OpeningFront.PersonWindow(_platform, request.Foreground, window => window == opened,
            reused ? 0 : previousFront);
        bool takeFront = request.Foreground && person == 0;
        long handBackTo = request.Foreground ? person : previousFront;
        if (takeFront)
            _platform.RequestForeground(selected.WindowHandle);
        CalculatorSnapshot? Observe(bool requireForeground) =>
            _platform.Inventory().FirstOrDefault(candidate =>
                candidate.ProcessId == selected.ProcessId
                && candidate.CreationTimeUtcTicks == selected.CreationTimeUtcTicks
                && candidate.WindowHandle == selected.WindowHandle
                && candidate.Visible
                && (!requireForeground || candidate.Foreground));
        CalculatorSnapshot? verified = Observe(requireForeground: takeFront);
        if (verified is null)
        {
            await _platform.DelayAsync(Delay, cancellationToken).ConfigureAwait(false);
            // Focus is requested, not required: a system flyout that owns the
            // foreground made every open unverifiable in REPAIR1031 while the app
            // was on screen. A visible window of the bound process is the proof.
            verified = Observe(requireForeground: true) ?? Observe(requireForeground: false);
        }
        if (verified is null) return Failure(request, ApplicationOpenErrorCodes.VerificationFailed, !reused);
        bool windowsActivation = !takeFront && handBackTo != 0 && verified.Foreground
            && verified.WindowHandle != handBackTo;
        bool frontRestored = windowsActivation && _platform.ReturnForeground(handBackTo, verified.WindowHandle);
        bool shown = person != 0 && await OpeningFront.ShowWithoutActivationAsync(
            _platform, verified.WindowHandle, person, window => window == opened, cancellationToken).ConfigureAwait(false);
        string executable = Path.Combine(Environment.SystemDirectory, "calc.exe");
        var receipt = new ApplicationLaunchReceipt(
            request.InvocationId, request.ApplicationId, !reused, reused,
            verified.ProcessId, verified.CreationTimeUtcTicks, executable,
            null, null, verified.WindowHandle, null);
        // Auditoría D9: the name the verified window has, as Windows wrote it; without one, the id asked for (never a
        // name nobody read).
        string title = _platform.WindowTitle(verified.WindowHandle).Trim();
        return new ApplicationOpenResult(true, true, title.Length > 0 ? title : request.ApplicationId, reused,
            verified.ProcessId, verified.WindowHandle, null, receipt, windowsActivation, frontRestored,
            ShownWithoutFocus: shown);
    }

    private static ApplicationOpenResult Failure(
        ApplicationOpenRequest request, string error, bool effect) => new(
        effect, false, request.ApplicationId, false, null, null, error,
        new ApplicationLaunchReceipt(request.InvocationId, request.ApplicationId,
            effect, false, null, null, null, null, null, null, error));
}

internal sealed record CalculatorSnapshot(
    int ProcessId, long CreationTimeUtcTicks, long WindowHandle, bool Visible, bool Foreground);

internal interface ICalculatorPlatform : IOpeningFront
{
    IReadOnlyList<CalculatorSnapshot> Inventory();
    bool Launch();
    void RequestForeground(long windowHandle);
    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);

    // Whether the front is back at «previous».
    bool ReturnForeground(long previous, long opened) => false;

    // The window's title as Windows has it (empty when it has none or is gone).
    string WindowTitle(long windowHandle) => string.Empty;
}

internal sealed partial class WindowsCalculatorPlatform : ICalculatorPlatform
{
    public IReadOnlyList<CalculatorSnapshot> Inventory()
    {
        Process[] processes = Process.GetProcessesByName("CalculatorApp");
        try
        {
            return processes.Select(process =>
            {
                process.Refresh(); nint window = process.MainWindowHandle;
                // The packaged Calculator draws inside the ApplicationFrameHost frame that hosts it.
                if (window == 0 || !IsWindowVisible(window))
                    window = External.VisibleControlSurface.FrameHosting(unchecked((uint)process.Id));
                return new CalculatorSnapshot(process.Id, process.StartTime.ToUniversalTime().Ticks,
                    window.ToInt64(), window != 0 && IsWindowVisible(window),
                    window != 0 && GetForegroundWindow() == window);
            }).ToArray();
        }
        finally { foreach (Process process in processes) process.Dispose(); }
    }

    public bool Launch()
    {
        string executable = Path.Combine(Environment.SystemDirectory, "calc.exe");
        if (!File.Exists(executable)) return false;
        using Process? process = Process.Start(new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        });
        return process is not null;
    }

    public void RequestForeground(long windowHandle)
    {
        nint handle = checked((nint)windowHandle);
        _ = ShowWindowAsync(handle, 9); _ = SetForegroundWindow(handle);
    }

    public async ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        await Task.Delay(delay, cancellationToken).ConfigureAwait(false);

    public long ForegroundWindow() => ForegroundHandBack.Foreground();

    public bool ReturnForeground(long previous, long opened) => ForegroundHandBack.Return(previous, opened);

    public string WindowTitle(long windowHandle) => External.VisibleControlSurface.WindowTitle(checked((nint)windowHandle));

    public long PersonWorkingIn(long window) => ForegroundHandBack.PersonWorkingIn(window);

    public bool ShowAboveWithoutActivation(long window, long personWindow) =>
        ForegroundHandBack.ShowAboveWithoutActivation(window, personWindow);

    [LibraryImport("user32.dll")] private static partial nint GetForegroundWindow();
    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);
    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindowAsync(nint window, int command);
    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint window);
}
