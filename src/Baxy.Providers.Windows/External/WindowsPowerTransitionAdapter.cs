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
    // SHUTDOWN_GRACE_OVERRIDE | SHUTDOWN_RESTART | SHUTDOWN_POWEROFF (winnt.h).
    private const uint ShutdownGraceOverride = 0x00000020;
    private const uint ShutdownRestart = 0x00000004;
    private const uint ShutdownPowerOff = 0x00000008;
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
        "restart" => Transition(reboot: true),
        "shutdown" => Transition(reboot: false),
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

    // POWER2079 H0401/H0714: on this Windows 11 Home the process holds
    // SeShutdownPrivilege and InitiateSystemShutdownEx is still refused, while
    // `shutdown.exe` schedules the same transition. shutdown.exe asks through
    // InitiateShutdownW, so that is the second door: the older call stays first
    // (it is what REDPC accepted), and only when Windows refuses it does the
    // adapter ask the newer one. Both leave the thirty-second delay Windows
    // announces, so `shutdown /a` can still abort it.
    private static WindowsPowerTransitionResult Transition(bool reboot)
    {
        if (!EnableShutdownPrivilege())
        {
            return new(false, reboot
                ? "win32_initiatesystemshutdownex_restart_acceptance"
                : "win32_initiatesystemshutdownex_shutdown_acceptance");
        }

        string message = reboot
            ? "BAXY confirmó el reinicio solicitado; reinicia en 30 segundos."
            : "BAXY confirmó el apagado solicitado; apaga en 30 segundos.";
        if (InitiateSystemShutdownEx(
                null,
                message,
                timeout: TransitionDelaySeconds,
                forceAppsClosed: false,
                rebootAfterShutdown: reboot,
                ShutdownReasonMajorApplication | ShutdownReasonPlanned))
        {
            return new(true, reboot
                ? "win32_initiatesystemshutdownex_restart_acceptance"
                : "win32_initiatesystemshutdownex_shutdown_acceptance");
        }

        uint flags = ShutdownGraceOverride | (reboot ? ShutdownRestart : ShutdownPowerOff);
        bool accepted = InitiateShutdown(
            null,
            message,
            TransitionDelaySeconds,
            flags,
            ShutdownReasonMajorApplication | ShutdownReasonPlanned) == 0;
        return new(accepted, reboot
            ? "win32_initiateshutdown_restart_acceptance"
            : "win32_initiateshutdown_shutdown_acceptance");
    }

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

    // Returns ERROR_SUCCESS (0) when Windows takes the request; shutdown.exe
    // uses this call, and this machine accepts it where the older one is refused.
    [LibraryImport("advapi32.dll", EntryPoint = "InitiateShutdownW", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    private static partial uint InitiateShutdown(
        string? machineName,
        string? message,
        uint gracePeriod,
        uint shutdownFlags,
        uint reason);

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
