using System.Diagnostics;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed record WindowsProcessIdentity(int ProcessId, long StartTimeUtcTicks);

internal interface IWindowsProcessTerminationPlatform
{
    IReadOnlyList<WindowsProcessIdentity> Snapshot(string processName);

    bool Terminate(string processName, WindowsProcessIdentity identity);
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

    public bool Terminate(string processName, WindowsProcessIdentity identity)
    {
        try
        {
            using Process process = Process.GetProcessById(identity.ProcessId);
            if (!string.Equals(process.ProcessName, processName, StringComparison.OrdinalIgnoreCase)
                || process.StartTime.ToUniversalTime().Ticks != identity.StartTimeUtcTicks)
            {
                return false;
            }

            process.Kill(entireProcessTree: true);
            return process.WaitForExit(5000) && process.HasExited;
        }
        catch (ArgumentException)
        {
            return true;
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
            int terminated = 0;
            foreach (WindowsProcessIdentity identity in before)
            {
                cancellationToken.ThrowIfCancellationRequested();
                effectMayHaveOccurred = true;
                if (_platform.Terminate(processName, identity)) terminated++;
            }

            IReadOnlyList<WindowsProcessIdentity> after = _platform.Snapshot(processName);
            var original = before.ToHashSet();
            WindowsProcessIdentity[] lingering = after.Where(original.Contains).ToArray();
            if (lingering.Length != 0)
            {
                return ValueTask.FromResult(ExternalJson.Failure(
                    operation, "process_termination_postread_failed", effectMayHaveOccurred));
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
            return ValueTask.FromResult(ExternalJson.Success(
                operation, result, effectObserved: before.Count > 0));
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
