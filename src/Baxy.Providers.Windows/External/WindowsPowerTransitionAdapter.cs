using System.Runtime.InteropServices;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed record WindowsPowerTransitionResult(bool Accepted, string Authority);

internal interface IWindowsPowerTransitionPlatform
{
    WindowsPowerTransitionResult Request(string action);
}

internal sealed partial class WindowsPowerTransitionPlatform : IWindowsPowerTransitionPlatform
{
    private const uint ExitWindowsLogoff = 0x00000000;
    private const uint ExitWindowsForceIfHung = 0x00000010;
    private const uint ShutdownReasonMajorApplication = 0x00040000;
    private const uint ShutdownReasonPlanned = 0x80000000;

    public WindowsPowerTransitionResult Request(string action) => action switch
    {
        "lock" => new(LockWorkStation(), "win32_lockworkstation_acceptance"),
        "signout" => new(
            ExitWindowsEx(
                ExitWindowsLogoff | ExitWindowsForceIfHung,
                ShutdownReasonMajorApplication | ShutdownReasonPlanned),
            "win32_exitwindowsex_logoff_acceptance"),
        "sleep" => new(
            SetSuspendState(hibernate: false, forceCritical: true, disableWakeEvent: false),
            "win32_setsuspendstate_acceptance"),
        "restart" => new(
            InitiateSystemShutdownEx(
                null,
                "BAXY confirmó el reinicio solicitado.",
                timeout: 0,
                forceAppsClosed: true,
                rebootAfterShutdown: true,
                ShutdownReasonMajorApplication | ShutdownReasonPlanned),
            "win32_initiatesystemshutdownex_restart_acceptance"),
        "shutdown" => new(
            InitiateSystemShutdownEx(
                null,
                "BAXY confirmó el apagado solicitado.",
                timeout: 0,
                forceAppsClosed: true,
                rebootAfterShutdown: false,
                ShutdownReasonMajorApplication | ShutdownReasonPlanned),
            "win32_initiatesystemshutdownex_shutdown_acceptance"),
        _ => new(false, "unsupported_power_transition"),
    };

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool LockWorkStation();

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ExitWindowsEx(uint flags, uint reason);

    [LibraryImport("powrprof.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetSuspendState(
        [MarshalAs(UnmanagedType.Bool)] bool hibernate,
        [MarshalAs(UnmanagedType.Bool)] bool forceCritical,
        [MarshalAs(UnmanagedType.Bool)] bool disableWakeEvent);

    [LibraryImport("advapi32.dll", EntryPoint = "InitiateSystemShutdownExW",
        StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool InitiateSystemShutdownEx(
        string? machineName,
        string? message,
        uint timeout,
        [MarshalAs(UnmanagedType.Bool)] bool forceAppsClosed,
        [MarshalAs(UnmanagedType.Bool)] bool rebootAfterShutdown,
        uint reason);
}

internal sealed class DeniedHostPowerTransitionPlatform : IWindowsPowerTransitionPlatform
{
    public WindowsPowerTransitionResult Request(string action) =>
        new(false, "power_transition_physical_gate_required");
}

internal sealed class WindowsPowerTransitionAdapter : IExternalOperationAdapter
{
    internal const string DenyHostPowerTransitionVariable = "BAXY_DENY_HOST_POWER_TRANSITION";
    internal const string ObservedCorpusVariable = "BAXY_GOAL10_OBSERVED_CORPUS";

    private readonly IWindowsPowerTransitionPlatform _platform;

    internal WindowsPowerTransitionAdapter()
        : this(CreateDefaultPlatform())
    {
    }

    internal WindowsPowerTransitionAdapter(IWindowsPowerTransitionPlatform platform) =>
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));

    internal static bool HostPowerTransitionDeniedForThisProcess() =>
        !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable(ObservedCorpusVariable))
        || string.Equals(
            Environment.GetEnvironmentVariable(DenyHostPowerTransitionVariable),
            "1",
            StringComparison.Ordinal);

    internal static IWindowsPowerTransitionPlatform CreateDefaultPlatform() =>
        HostPowerTransitionDeniedForThisProcess()
            ? new DeniedHostPowerTransitionPlatform()
            : new WindowsPowerTransitionPlatform();

    public bool CanHandle(string operation) => operation == "system.power";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            string action = ExternalJson.RequiredString(arguments, "action");
            if (action is not ("lock" or "restart" or "shutdown" or "signout" or "sleep"))
                return ValueTask.FromResult(ExternalJson.Failure(operation, "invalid_arguments"));

            if (_platform is DeniedHostPowerTransitionPlatform)
            {
                return ValueTask.FromResult(ExternalJson.Failure(
                    operation, "power_transition_physical_gate_required"));
            }

            effectBoundary.Cross(cancellationToken);
            WindowsPowerTransitionResult transition = _platform.Request(action);
            if (!transition.Accepted)
            {
                return ValueTask.FromResult(effectBoundary.Failure(
                    operation, "power_transition_not_accepted"));
            }

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("action", action);
                writer.WriteBoolean("accepted", true);
                writer.WriteString("requestedUtc", DateTimeOffset.UtcNow);
                writer.WriteString("authority", transition.Authority);
                writer.WriteEndObject();
            });
            return ValueTask.FromResult(ExternalJson.Success(operation, result));
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "power_transition_failed"));
        }
        catch (InvalidDataException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, "invalid_arguments"));
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or NotSupportedException or System.ComponentModel.Win32Exception)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "power_transition_failed"));
        }
    }
}
