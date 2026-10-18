using System.Diagnostics;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed record WindowsProcessIdentity(int ProcessId, long StartTimeUtcTicks);

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
}

internal sealed class WindowsProcessTerminationPlatform : IWindowsProcessTerminationPlatform
{
    public IReadOnlyList<WindowsProcessIdentity> Snapshot(string processName)
    {
        Process[] processes = Process.GetProcessesByName(processName);
        try
        {
            return processes
                .Select(process => new WindowsProcessIdentity(
                    process.Id, process.StartTime.ToUniversalTime().Ticks))
                .OrderBy(identity => identity.ProcessId)
                .ToArray();
        }
        finally
        {
            foreach (Process process in processes) process.Dispose();
        }
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

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        bool effectMayHaveOccurred = false;
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            string processName = NormalizeName(ExternalJson.RequiredString(arguments, "name"));
            IReadOnlyList<WindowsProcessIdentity> before = _platform.Snapshot(processName);
            if (before.Count == 0)
            {
                return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(operation, "process_not_running"));
            }

            int terminated = 0, alreadyExited = 0, denied = 0;
            foreach (WindowsProcessIdentity identity in before)
            {
                cancellationToken.ThrowIfCancellationRequested();
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
                    return ValueTask.FromResult(ExternalJson.Failure(
                        operation, "process_termination_postread_failed", effectMayHaveOccurred));
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
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("processName", processName);
                writer.WriteNumber("beforeCount", before.Count);
                writer.WriteNumber("terminatedCount", terminated);
                writer.WriteNumber("alreadyExitedCount", alreadyExited);
                writer.WriteNumber("afterCount", after.Count);
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
            return ValueTask.FromResult(ExternalJson.Failure(
                operation, "process_termination_failed", effectMayHaveOccurred));
        }
    }

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
