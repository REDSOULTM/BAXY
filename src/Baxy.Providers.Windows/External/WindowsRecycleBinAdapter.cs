using System.Text.Json;
using Baxy.Providers.Windows.Filesystem;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsRecycleBinAdapter : IExternalOperationAdapter
{
    private const string EmptyScript = """
        $ErrorActionPreference='Stop'
        $shell=New-Object -ComObject Shell.Application
        function Get-BaxyRecycleCount { @($shell.Namespace(10).Items()).Count }
        $before=Get-BaxyRecycleCount
        if($before -gt 0){Clear-RecycleBin -Force -ErrorAction Stop}
        $after=Get-BaxyRecycleCount
        [pscustomobject]@{version=1;ok=($after -eq 0);beforeCount=$before;afterCount=$after;effectObserved=($before -gt 0);authority='windows_recycle_bin_empty_postread'}|ConvertTo-Json -Compress
        """;

    private readonly IExternalProcessRunner _runner;
    private readonly Func<long>? _itemsInBin;

    internal WindowsRecycleBinAdapter() : this(new ExternalProcessRunner(), WindowsRecycleBin.AllItems)
    {
    }

    // Renew al máximo (8.3): itemsInBin is the cheap read of every drive's bin (-1 when it cannot be read), done once
    // after an emptying whose own receipt was lost; null reads nothing.
    internal WindowsRecycleBinAdapter(IExternalProcessRunner runner, Func<long>? itemsInBin = null)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _itemsInBin = itemsInBin;
    }

    public bool CanHandle(string operation) => operation == "system.recyclebin.empty";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            effectBoundary.Cross(cancellationToken);
            ExternalProcessResult process = await _runner.RunPowerShellAsync(
                EmptyScript, [], TimeSpan.FromSeconds(30), cancellationToken).ConfigureAwait(false);
            string? line = process.Output.Split(
                ['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
            if (process.ExitCode != 0 || line is null)
                return ExternalJson.WithStateAfter(
                    effectBoundary.Failure(operation, "recycle_bin_empty_process_failed"), ReadBin());
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement source = document.RootElement;
            if (!source.TryGetProperty("ok", out JsonElement ok)
                || ok.ValueKind != JsonValueKind.True
                || !source.TryGetProperty("afterCount", out JsonElement after)
                || after.GetInt32() != 0)
            {
                bool ambiguous = source.TryGetProperty(
                    "effectObserved", out JsonElement observed)
                    && observed.ValueKind == JsonValueKind.True;
                // Renew al máximo (8.3): the script's own post-read is the state after when it counted the bin.
                return ExternalJson.WithStateAfter(
                    effectBoundary.Failure(operation, "recycle_bin_empty_postread_failed", ambiguous),
                    source.TryGetProperty("afterCount", out JsonElement counted)
                        && counted.ValueKind == JsonValueKind.Number && counted.TryGetInt64(out long left) && left >= 0
                        ? BinState(left, "windows_recycle_bin_empty_postread")
                        : ReadBin());
            }
            int beforeCount = source.GetProperty("beforeCount").GetInt32();
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteNumber("beforeCount", beforeCount);
                writer.WriteNumber("afterCount", 0);
                writer.WriteBoolean("empty", true);
                writer.WriteString("authority", "windows_recycle_bin_empty_postread");
                writer.WriteEndObject();
            });
            // Ronda final: a bin already empty is the state reached (changed:false), not a failure nor an emptying.
            return beforeCount > 0
                ? ExternalJson.Success(operation, result, effectObserved: true)
                : ExternalJson.Switched(operation, result, effectObserved: false);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ExternalJson.WithStateAfter(
                effectBoundary.Failure(operation, "recycle_bin_empty_failed"), ReadBin());
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or JsonException or TimeoutException)
        {
            return ExternalJson.WithStateAfter(
                effectBoundary.Failure(operation, "recycle_bin_empty_failed"), ReadBin());
        }
    }

    // Renew al máximo (8.3): one read of the bins after an emptying left ambiguous; nothing when it cannot be read.
    private JsonElement? ReadBin()
    {
        long items = _itemsInBin?.Invoke() ?? -1;
        return items >= 0 ? BinState(items, "windows_recycle_bin_query_postread") : null;
    }

    private static JsonElement BinState(long items, string authority) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteNumber("itemCount", items);
        writer.WriteBoolean("requestedStateReached", items == 0);
        writer.WriteString("authority", authority);
        writer.WriteEndObject();
    });
}
