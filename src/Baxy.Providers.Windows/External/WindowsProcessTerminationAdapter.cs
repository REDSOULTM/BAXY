using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Providers.Windows.External;

// Renew al máximo (B-SYS-6): AccessDenied marks an instance whose start time Windows would not let BAXY read (a service
// running as SYSTEM): its identity cannot be pinned, so it is never ended, only counted.
internal sealed record WindowsProcessIdentity(int ProcessId, long StartTimeUtcTicks, bool AccessDenied = false);

// What ending one observed process came to: this kill ended it, it had already exited on its own, or it is still
// there (or its id now belongs to another process).
internal enum WindowsProcessTermination
{
    Terminated,
    AlreadyExited,
    NotTerminated,
    // Ronda final: the kill was sent and the wait ran out; if the post-read finds it gone, this call ended it.
    KillSent,
    // FT/proveedores goal (review of receipts): Windows refused this one (it runs elevated or as another user).
    Denied,
}

internal interface IWindowsProcessTerminationPlatform
{
    IReadOnlyList<WindowsProcessIdentity> Snapshot(string processName);

    WindowsProcessTermination Terminate(string processName, WindowsProcessIdentity identity);

    // uso-129: read before the kill, what else of the application these instances belong to is running: its main process
    // when these are not it, and its other processes.
    WindowsProcessFamily Family(string processName, IReadOnlyList<WindowsProcessIdentity> instances) => WindowsProcessFamily.None;

    // Read after the kill: those of the family still running.
    WindowsProcessFamily StillRunning(WindowsProcessFamily family) => WindowsProcessFamily.None;
}

/// <summary>uso-129: the rest of an application around the instances of one executable.</summary>
internal sealed record WindowsProcessFamily(ApplicationProcess? Main, IReadOnlyList<ApplicationProcess> Others)
{
    internal static WindowsProcessFamily None { get; } = new(null, []);
}

internal sealed class WindowsProcessTerminationPlatform : IWindowsProcessTerminationPlatform
{
    public WindowsProcessFamily Family(string processName, IReadOnlyList<WindowsProcessIdentity> instances)
    {
        IReadOnlyDictionary<int, ApplicationProcess> running = ApplicationFamily.Read();
        ApplicationProcess[] mains = [.. instances
            .Select(instance => ApplicationFamily.MainOf(running, instance.ProcessId))
            .OfType<ApplicationProcess>()
            .DistinctBy(static process => process.Id)];
        bool Named(ApplicationProcess process) =>
            string.Equals(process.Name, processName, StringComparison.OrdinalIgnoreCase);
        ApplicationProcess? other = mains.FirstOrDefault(process => !Named(process));
        return new(other,
            [.. mains.SelectMany(main => ApplicationFamily.Members(running, main))
                .Where(process => !Named(process) && process.Id != other?.Id)
                .DistinctBy(static process => process.Id)]);
    }

    public WindowsProcessFamily StillRunning(WindowsProcessFamily family)
    {
        IReadOnlyDictionary<int, ApplicationProcess> running = ApplicationFamily.Read();
        bool Alive(ApplicationProcess process) =>
            running.TryGetValue(process.Id, out ApplicationProcess? now) && now.StartTicks == process.StartTicks;
        return new(family.Main is { } main && Alive(main) ? main : null, [.. family.Others.Where(Alive)]);
    }

    public IReadOnlyList<WindowsProcessIdentity> Snapshot(string processName)
    {
        Process[] processes = Process.GetProcessesByName(processName);
        try
        {
            return Identities(processes.Select(process => (process.Id, (Func<DateTime>)(() => process.StartTime))));
        }
        finally
        {
            foreach (Process process in processes) process.Dispose();
        }
    }

    // Renew al máximo (B-SYS-6): each instance is read on its own. One Windows will not let BAXY read (Win32Exception,
    // a SYSTEM service) is kept as denied; one that exited while being read (InvalidOperationException) is gone and
    // left out. Before, either ended the whole call before any of the person's own instances were tried.
    internal static IReadOnlyList<WindowsProcessIdentity> Identities(
        IEnumerable<(int ProcessId, Func<DateTime> StartTime)> processes)
    {
        var identities = new List<WindowsProcessIdentity>();
        foreach ((int processId, Func<DateTime> startTime) in processes)
        {
            try
            {
                identities.Add(new WindowsProcessIdentity(processId, startTime().ToUniversalTime().Ticks));
            }
            catch (System.ComponentModel.Win32Exception)
            {
                identities.Add(new WindowsProcessIdentity(processId, 0, AccessDenied: true));
            }
            catch (InvalidOperationException)
            {
            }
        }
        return identities.OrderBy(identity => identity.ProcessId).ToArray();
    }

    // Only the named process is ended: the confirmation names one executable, so the processes it started (an
    // explorer's windows, a launcher's games) are not part of the request.
    public WindowsProcessTermination Terminate(string processName, WindowsProcessIdentity identity)
    {
        try
        {
            using Process process = Process.GetProcessById(identity.ProcessId);
            if (!string.Equals(process.ProcessName, processName, StringComparison.OrdinalIgnoreCase)
                || process.StartTime.ToUniversalTime().Ticks != identity.StartTimeUtcTicks)
            {
                return WindowsProcessTermination.NotTerminated;
            }

            process.Kill(entireProcessTree: false);
            return process.WaitForExit(5000) && process.HasExited
                ? WindowsProcessTermination.Terminated
                : WindowsProcessTermination.KillSent;
        }
        catch (ArgumentException)
        {
            return WindowsProcessTermination.AlreadyExited;
        }
        catch (InvalidOperationException)
        {
            // FT/proveedores goal (review of receipts): it exited between being found and being read (a browser's
            // child): gone, as asked, not a failure of the whole call.
            return WindowsProcessTermination.AlreadyExited;
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return WindowsProcessTermination.Denied;
        }
    }
}

internal sealed class WindowsProcessTerminationAdapter : IExternalOperationAdapter
{
    private readonly IWindowsProcessTerminationPlatform _platform;

    internal WindowsProcessTerminationAdapter()
        : this(new WindowsProcessTerminationPlatform())
    {
    }

    internal WindowsProcessTerminationAdapter(IWindowsProcessTerminationPlatform platform) =>
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));

    public bool CanHandle(string operation) =>
        operation == "system.process.terminate.named";

    // Banco ciego c3 C3-130 s0: a process of Windows' shell or session is refused before the person is asked
    // (VisibleControlSurface.WindowsSessionProcess); the run refuses it again.
    public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult(PartOfWindows(operation, arguments));

    private static ExternalCapabilityReceipt? PartOfWindows(string operation, JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("name", out JsonElement name) && name.ValueKind == JsonValueKind.String
        && VisibleControlSurface.WindowsSessionProcess(name.GetString())
            ? ExternalJson.FailureBeforeEffect(operation, "process_part_of_windows")
            : null;

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (PartOfWindows(operation, arguments) is { } refused)
            return ValueTask.FromResult(refused);
        bool effectMayHaveOccurred = false;
        string? processName = null;
        IReadOnlyList<WindowsProcessIdentity> before = [];
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            processName = NormalizeName(ExternalJson.RequiredString(arguments, "name"));
            before = _platform.Snapshot(processName);
            if (before.Count == 0)
            {
                return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(operation, "process_not_running"));
            }

            WindowsProcessFamily family = _platform.Family(processName, before);
            int terminated = 0, alreadyExited = 0, denied = 0;
            foreach (WindowsProcessIdentity identity in before)
            {
                cancellationToken.ThrowIfCancellationRequested();
                // Renew al máximo (B-SYS-6): an instance whose identity could not be read is not ended: the kill could
                // not be bound to it, and Windows refuses BAXY there anyway.
                if (identity.AccessDenied)
                {
                    denied++;
                    continue;
                }
                effectMayHaveOccurred = true;
                switch (_platform.Terminate(processName, identity))
                {
                    case WindowsProcessTermination.Terminated:
                    case WindowsProcessTermination.KillSent:
                        terminated++;
                        break;
                    case WindowsProcessTermination.AlreadyExited:
                        alreadyExited++;
                        break;
                    case WindowsProcessTermination.Denied:
                        denied++;
                        break;
                }
            }

            IReadOnlyList<WindowsProcessIdentity> after = _platform.Snapshot(processName);
            var original = before.ToHashSet();
            WindowsProcessIdentity[] lingering = after.Where(original.Contains).ToArray();
            if (lingering.Length != 0)
            {
                if (denied == 0)
                {
                    // Renew al máximo (8.3): what the post-read found is the state after, never dropped.
                    return ValueTask.FromResult(ExternalJson.WithStateAfter(
                        ExternalJson.Failure(operation, "process_termination_postread_failed", effectMayHaveOccurred),
                        StillRunning(lingering.Length)));
                }

                // FT/proveedores goal (review of receipts): the instances Windows would not let BAXY end (elevated, or
                // another user's) are named as that, with what was ended; before, one of them ended the call as a
                // bare failure, the others untried and unreported, and «may have happened» when nothing had.
                JsonElement partial = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("processName", processName);
                    writer.WriteNumber("beforeCount", before.Count);
                    writer.WriteNumber("terminatedCount", terminated);
                    writer.WriteNumber("alreadyExitedCount", alreadyExited);
                    writer.WriteNumber("deniedCount", denied);
                    writer.WriteNumber("stillRunningCount", lingering.Length);
                    writer.WriteEndObject();
                });
                return ValueTask.FromResult(new ExternalCapabilityReceipt(
                    operation, terminated > 0, false, partial, "process_termination_access_denied")
                {
                    EffectMayHaveOccurred = terminated > 0,
                });
            }

            WindowsProcessIdentity[] replacements = after
                .Where(identity => !original.Contains(identity))
                .OrderBy(identity => identity.ProcessId)
                .ToArray();
            WindowsProcessFamily left = _platform.StillRunning(family);
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("processName", processName);
                writer.WriteNumber("beforeCount", before.Count);
                writer.WriteNumber("terminatedCount", terminated);
                writer.WriteNumber("alreadyExitedCount", alreadyExited);
                writer.WriteNumber("afterCount", after.Count);
                WriteFamily(writer, processName, left);
                writer.WriteBoolean("originalIdentitiesAbsent", true);
                writer.WriteNumber("replacementCount", replacements.Length);
                writer.WriteStartArray("identities");
                foreach (WindowsProcessIdentity identity in before)
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("processId", identity.ProcessId);
                    writer.WriteNumber("startTimeUtcTicks", identity.StartTimeUtcTicks);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteStartArray("replacementIdentities");
                foreach (WindowsProcessIdentity identity in replacements)
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("processId", identity.ProcessId);
                    writer.WriteNumber("startTimeUtcTicks", identity.StartTimeUtcTicks);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteString("authority", "windows_process_original_identity_absence_postread");
                writer.WriteEndObject();
            });
            // Processes that had all exited on their own before the kill leave the state asked for, reached by nothing
            // this call did.
            return ValueTask.FromResult(ExternalJson.Switched(
                operation, result, effectObserved: terminated > 0));
        }
        catch (InvalidDataException)
        {
            return ValueTask.FromResult(ExternalJson.Failure(operation, "invalid_arguments"));
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception or NotSupportedException)
        {
            ExternalCapabilityReceipt failure = ExternalJson.Failure(
                operation, "process_termination_failed", effectMayHaveOccurred);
            return ValueTask.FromResult(failure.EffectMayHaveOccurred && processName is not null
                ? ExternalJson.WithStateAfter(failure, Reread(processName, before))
                : failure);
        }
    }

    // uso-129 («cierra los procesos en segundo plano»: a helper was forced, its application stayed and it was said closed):
    // the kill reached the named executable; what of its application still runs is said, and the main process, which
    // starts its helpers again, with the call that reaches it.
    private static void WriteFamily(Utf8JsonWriter writer, string processName, WindowsProcessFamily left)
    {
        if (left.Others.Count > 0)
        {
            writer.WriteStartArray("sameApplicationStillRunning");
            foreach (string name in left.Others.Select(static process => process.Name)
                .Distinct(StringComparer.OrdinalIgnoreCase).Order(StringComparer.OrdinalIgnoreCase))
                writer.WriteStringValue(name);
            writer.WriteEndArray();
        }

        if (left.Main is { } main)
        {
            writer.WriteBoolean("mainStillRunning", true);
            writer.WriteString("mainProcessName", main.Name);
            writer.WriteString("next", Baxy.Kernel.Operations.WireNames.Call("system.process.terminate.named",
                new() { ["name"] = main.Name })
                + $" ends the application itself; only {processName} ended here, and while {main.Name} runs it can start it again.");
        }
    }

    // Renew al máximo (8.3): one more read of the name after a kill whose post-read threw: how many of the instances
    // asked to end are still there; nothing when that read fails too.
    private JsonElement? Reread(string processName, IReadOnlyList<WindowsProcessIdentity> before)
    {
        try
        {
            var original = before.ToHashSet();
            return StillRunning(_platform.Snapshot(processName).Count(original.Contains));
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception or NotSupportedException)
        {
            return null;
        }
    }

    private static JsonElement StillRunning(int count) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteNumber("stillRunningCount", count);
        writer.WriteBoolean("requestedStateReached", count == 0);
        writer.WriteString("authority", "windows_process_original_identity_postread");
        writer.WriteEndObject();
    });

    private static string NormalizeName(string value)
    {
        string name = value.Trim();
        if (name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            name = name[..^4];
        if (name.Length is < 1 or > 128
            || name.Any(character => !(char.IsLetterOrDigit(character)
                || character is ' ' or '_' or '-' or '.')))
        {
            throw new InvalidDataException("Process name is invalid.");
        }
        return name;
    }
}
