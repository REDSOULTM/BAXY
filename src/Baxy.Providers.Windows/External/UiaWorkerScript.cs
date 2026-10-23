using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Renew al máximo (rendimiento): a helper script run by the persistent UI Automation worker's «script» command
/// (DesktopUiaWorker.ps1, Do-Script: its own STA runspace, <c>$args</c> as with -Command) instead of a PowerShell started
/// cold for it. Measured on the notebook: the start and its UI Automation load were most of a Calculator evaluation.
/// The answer reads as the per-call PowerShell's did: the script's last JSON line as its output, nothing when it wrote
/// none (it failed before its receipt), and a worker that could not answer inside the budget as a run that failed.
/// </summary>
internal static class UiaWorkerScript
{
    internal static async ValueTask<ExternalProcessResult> RunAsync(
        IUiaWorker worker,
        string script,
        IReadOnlyList<string> scriptArguments,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(worker);
        var arguments = new JsonArray();
        foreach (string argument in scriptArguments)
            arguments.Add((JsonNode?)argument);
        string command = new JsonObject
        {
            ["cmd"] = "script",
            ["script"] = script,
            ["args"] = arguments,
        }.ToJsonString();
        // A worker that stopped answering (it is replaced) is what a per-call PowerShell over its budget was.
        using JsonDocument answer = await worker.SendAsync(command, timeout, cancellationToken).ConfigureAwait(false)
            ?? throw new TimeoutException("The UI Automation worker did not answer the script.");
        JsonElement root = answer.RootElement;
        string output = root.ValueKind == JsonValueKind.Object
            && root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
            && root.TryGetProperty("line", out JsonElement line) && line.ValueKind == JsonValueKind.String
                ? line.GetString() ?? string.Empty
                : string.Empty;
        return new ExternalProcessResult(output.Length > 0 ? 0 : 1, output, string.Empty);
    }
}
