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
    // REOPEN1993 H0401/H0714: InitiateSystemShutdownEx needs SeShutdownPrivilege
    // enabled on this process token; without it Windows answered
    // ERROR_PRIVILEGE_NOT_HELD and the product told the person that Windows
    // had not accepted the request. The transition is asked with a short
    // delay so Windows announces it and `shutdown /a` can still abort it.
    internal const uint TransitionDelaySeconds = 30;
    private const string ShutdownPrivilegeName = "SeShutdownPrivilege";
    private const uint TokenAdjustPrivileges = 0x0020;
    private const uint TokenQuery = 0x0008;
    private const uint PrivilegeEnabled = 0x00000002;

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
            EnableShutdownPrivilege() && InitiateSystemShutdownEx(
                null,
                "BAXY confirmó el reinicio solicitado; reinicia en 30 segundos.",
                timeout: TransitionDelaySeconds,
                forceAppsClosed: false,
                rebootAfterShutdown: true,
                ShutdownReasonMajorApplication | ShutdownReasonPlanned),
            "win32_initiatesystemshutdownex_restart_acceptance"),
        "shutdown" => new(
            EnableShutdownPrivilege() && InitiateSystemShutdownEx(
                null,
                "BAXY confirmó el apagado solicitado; apaga en 30 segundos.",
                timeout: TransitionDelaySeconds,
                forceAppsClosed: false,
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

    private static bool EnableShutdownPrivilege()
    {
        if (!OpenProcessToken(GetCurrentProcess(), TokenAdjustPrivileges | TokenQuery, out nint token))
            return false;
        try
        {
            if (!LookupPrivilegeValue(null, ShutdownPrivilegeName, out long luid))
                return false;
            var privileges = new TokenPrivileges { PrivilegeCount = 1, Luid = luid, Attributes = PrivilegeEnabled };
            if (!AdjustTokenPrivileges(token, false, ref privileges, 0, nint.Zero, nint.Zero))
                return false;
            // AdjustTokenPrivileges returns true even when the privilege was not
            // assigned to the token; ERROR_NOT_ALL_ASSIGNED (1300) says so.
            return Marshal.GetLastPInvokeError() != 1300;
        }
        finally
        {
            _ = CloseHandle(token);
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct TokenPrivileges
    {
        public uint PrivilegeCount;
        public long Luid;
        public uint Attributes;
    }

    [LibraryImport("kernel32.dll")]
    private static partial nint GetCurrentProcess();

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CloseHandle(nint handle);

    [LibraryImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool OpenProcessToken(nint process, uint desiredAccess, out nint token);

    [LibraryImport("advapi32.dll", EntryPoint = "LookupPrivilegeValueW", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool LookupPrivilegeValue(string? systemName, string name, out long luid);

    [LibraryImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AdjustTokenPrivileges(nint token, [MarshalAs(UnmanagedType.Bool)] bool disableAll, ref TokenPrivileges newState, uint bufferLength, nint previousState, nint returnLength);

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

internal sealed class WindowsPowerTransitionAdapter : IExternalOperationAdapter
{
    private readonly IWindowsPowerTransitionPlatform _platform;

    internal WindowsPowerTransitionAdapter()
        : this(new WindowsPowerTransitionPlatform())
    {
    }

    internal WindowsPowerTransitionAdapter(IWindowsPowerTransitionPlatform platform) =>
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));

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

            effectBoundary.Cross(cancellationToken);
            WindowsPowerTransitionResult transition = _platform.Request(action);
            if (!transition.Accepted)
            {
                // H0714 «apagá la computadora», H0401 «reiniciá la PC»: que la
                // transición no fuera aceptada no es una duda, es un hecho.
                // Windows devolvió que no la inicia, de modo que no se apagó ni
                // se reinició nada. Contarlo como efecto posible —sólo porque la
                // frontera se cruza antes de preguntar— hacía que el turno
                // publicara «no pude confirmar si la acción se realizó» en vez
                // de lo único que sí se sabe.
                return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(
                    operation, "power_transition_not_accepted"));
            }

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("action", action);
                writer.WriteBoolean("accepted", true);
                if (action is "restart" or "shutdown")
                    writer.WriteNumber("delaySeconds", WindowsPowerTransitionPlatform.TransitionDelaySeconds);
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
