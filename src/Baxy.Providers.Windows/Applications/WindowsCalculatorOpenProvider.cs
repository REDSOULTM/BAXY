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
        if (!reused)
        {
            if (!_platform.Launch()) return Failure(request, ApplicationOpenErrorCodes.LaunchFailed, false);
            for (int attempt = 0; attempt < 30 && selected is null; attempt++)
            {
                if (attempt > 0) await _platform.DelayAsync(Delay, cancellationToken).ConfigureAwait(false);
                selected = _platform.Inventory().FirstOrDefault(candidate => candidate.Visible
                    && !before.Any(old => old.ProcessId == candidate.ProcessId
                        && old.CreationTimeUtcTicks == candidate.CreationTimeUtcTicks));
            }
        }
        if (selected is null) return Failure(request, ApplicationOpenErrorCodes.VerificationFailed, !reused);
        _platform.RequestForeground(selected.WindowHandle);
        CalculatorSnapshot? Observe(bool requireForeground) =>
            _platform.Inventory().FirstOrDefault(candidate =>
                candidate.ProcessId == selected.ProcessId
                && candidate.CreationTimeUtcTicks == selected.CreationTimeUtcTicks
                && candidate.WindowHandle == selected.WindowHandle
                && candidate.Visible
                && (!requireForeground || candidate.Foreground));
        CalculatorSnapshot? verified = Observe(requireForeground: true);
        if (verified is null)
        {
            await _platform.DelayAsync(Delay, cancellationToken).ConfigureAwait(false);
            verified = Observe(requireForeground: true) ?? Observe(requireForeground: false);
        }
        if (verified is null) return Failure(request, ApplicationOpenErrorCodes.VerificationFailed, !reused);
        string executable = Path.Combine(Environment.SystemDirectory, "calc.exe");
        var receipt = new ApplicationLaunchReceipt(
            request.InvocationId, request.ApplicationId, !reused, reused,
            verified.ProcessId, verified.CreationTimeUtcTicks, executable,
            null, null, verified.WindowHandle, null);
        return new ApplicationOpenResult(true, true, "Calculadora", reused,
            verified.ProcessId, verified.WindowHandle, null, receipt);
    }

    private static ApplicationOpenResult Failure(
        ApplicationOpenRequest request, string error, bool effect) => new(
        effect, false, "Calculadora", false, null, null, error,
        new ApplicationLaunchReceipt(request.InvocationId, request.ApplicationId,
            effect, false, null, null, null, null, null, null, error));

    internal static bool IsCalculatorWindowTitle(string title)
    {
        string normalized = InstalledApplicationResolver.Normalize(title);
        return normalized is "calculadora" or "calculator"
            || normalized.StartsWith("calculadora ", StringComparison.Ordinal)
            || normalized.StartsWith("calculator ", StringComparison.Ordinal);
    }
}

internal sealed record CalculatorSnapshot(
    int ProcessId, long CreationTimeUtcTicks, long WindowHandle, bool Visible, bool Foreground);

internal interface ICalculatorPlatform
{
    IReadOnlyList<CalculatorSnapshot> Inventory();
    bool Launch();
    void RequestForeground(long windowHandle);
    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}

internal sealed partial class WindowsCalculatorPlatform : ICalculatorPlatform
{
    public IReadOnlyList<CalculatorSnapshot> Inventory()
    {
        // CalculatorApp.MainWindowHandle is 0; the visible UWP chrome lives on
        // ApplicationFrameHost with title Calculadora/Calculator.
        var found = new List<CalculatorSnapshot>();
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window))
            {
                return true;
            }

            int length = GetWindowTextLength(window);
            if (length <= 0)
            {
                return true;
            }

            string title = ReadWindowTitle(window, length);
            if (!WindowsCalculatorOpenProvider.IsCalculatorWindowTitle(title))
            {
                return true;
            }

            GetWindowThreadProcessId(window, out uint processId);
            try
            {
                using var process = Process.GetProcessById(unchecked((int)processId));
                found.Add(new CalculatorSnapshot(
                    process.Id,
                    process.StartTime.ToUniversalTime().Ticks,
                    window.ToInt64(),
                    Visible: true,
                    Foreground: GetForegroundWindow() == window));
            }
            catch (Exception exception) when (exception is ArgumentException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
            }

            return true;
        };
        _ = EnumWindows(callback, 0);
        return found;
    }

    private static unsafe string ReadWindowTitle(nint window, int length)
    {
        char[] title = new char[length + 1];
        fixed (char* buffer = title)
        {
            int written = GetWindowText(window, buffer, title.Length);
            return written > 0 ? new string(buffer, 0, written) : string.Empty;
        }
    }

    public bool Launch()
    {
        string executable = Path.Combine(Environment.SystemDirectory, "calc.exe");
        if (!File.Exists(executable)) return false;
        using Process? process = Process.Start(new ProcessStartInfo(executable)
        {
            UseShellExecute = true,
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

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextLengthW")]
    private static partial int GetWindowTextLength(nint window);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(
        nint window,
        char* text,
        int maxCount);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

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
