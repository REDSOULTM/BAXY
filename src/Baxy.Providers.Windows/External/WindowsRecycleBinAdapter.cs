using System.Text.Json;

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

    internal WindowsRecycleBinAdapter() : this(new ExternalProcessRunner())
    {
    }

    internal WindowsRecycleBinAdapter(IExternalProcessRunner runner) =>
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));

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
            ExternalProcessResult process = await _runner.RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-Command", EmptyScript],
                TimeSpan.FromSeconds(30), cancellationToken).ConfigureAwait(false);
            string? line = process.Output.Split(
                ['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
            if (process.ExitCode != 0 || line is null)
                return effectBoundary.Failure(operation, "recycle_bin_empty_process_failed");
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
                return effectBoundary.Failure(
                    operation, "recycle_bin_empty_postread_failed", ambiguous);
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
            return ExternalJson.Success(
                operation, result, effectObserved: beforeCount > 0);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "recycle_bin_empty_failed");
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or JsonException or TimeoutException)
        {
            return effectBoundary.Failure(operation, "recycle_bin_empty_failed");
        }
    }
}
