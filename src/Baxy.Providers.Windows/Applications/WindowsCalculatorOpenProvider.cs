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
        CalculatorSnapshot? ObserveForeground() =>
            _platform.Inventory().FirstOrDefault(candidate =>
                candidate.ProcessId == selected.ProcessId
                && candidate.CreationTimeUtcTicks == selected.CreationTimeUtcTicks
                && candidate.WindowHandle == selected.WindowHandle
                && candidate.Visible
                && candidate.Foreground);
        CalculatorSnapshot? verified = ObserveForeground();
        if (verified is null)
        {
            await _platform.DelayAsync(Delay, cancellationToken).ConfigureAwait(false);
            verified = ObserveForeground();
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
        Process[] processes = Process.GetProcessesByName("CalculatorApp");
        try
        {
            return processes.Select(process =>
            {
                process.Refresh(); nint window = process.MainWindowHandle;
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
