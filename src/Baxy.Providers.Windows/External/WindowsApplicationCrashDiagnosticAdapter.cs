using System.Globalization;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsApplicationCrashDiagnosticAdapter : IExternalOperationAdapter
{
    private const string DiagnosticScript = """
        $ErrorActionPreference='Stop'
        $hours=[int]$args[0]
        $limit=[int]$args[1]
        function Read-BaxyCrashEvents {
          @(
            Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=(Get-Date).AddHours(-$hours);Id=1000,1001,1002,1026} -ErrorAction SilentlyContinue |
              Where-Object {$_.ProviderName -in @('Application Error','Windows Error Reporting','Application Hang','.NET Runtime')} |
              Sort-Object RecordId -Descending |
              Select-Object -First ([Math]::Min(200,$limit*4)) |
              ForEach-Object {
                # Each event's own schema says where the application is (BAXY Renew audit 2026-10-15: the first
                # non-empty property was taken, a bucket id for 1001 and the whole message for 1026): Application
                # Error 1000 and Application Hang 1002 put it first, with the faulting module fourth (1000); Windows
                # Error Reporting 1001 puts its event name third and the application (P1) sixth; the .NET Runtime 1026
                # message starts «Application: <name>». Any other shape gives no name.
                $values=@($_.Properties|ForEach-Object {[string]$_.Value})
                $application=''
                $module=''
                $reported=''
                switch("$($_.ProviderName)/$($_.Id)"){
                  'Application Error/1000' {if($values.Count -gt 0){$application=$values[0]};if($values.Count -gt 3){$module=$values[3]}}
                  'Application Hang/1002' {if($values.Count -gt 0){$application=$values[0]}}
                  'Windows Error Reporting/1001' {if($values.Count -gt 5){$reported=$values[2];$application=$values[5]}}
                  '.NET Runtime/1026' {if($values.Count -gt 0 -and $values[0] -match '^Application: ([^\r\n]+)'){$application=$Matches[1].Trim()}}
                }
                [pscustomobject]@{
                  recordId=[long]$_.RecordId
                  eventId=[int]$_.Id
                  provider=[string]$_.ProviderName
                  timeUtc=$_.TimeCreated.ToUniversalTime().ToString('o')
                  applicationName=$application.Substring(0,[Math]::Min(128,$application.Length))
                  faultingModule=$module.Substring(0,[Math]::Min(128,$module.Length))
                  reportedEvent=$reported.Substring(0,[Math]::Min(64,$reported.Length))
                }
              }
          )
        }
        try {
          $first=@(Read-BaxyCrashEvents)
          Start-Sleep -Milliseconds 120
          $second=@(Read-BaxyCrashEvents)
          $firstIds=@{};foreach($item in $first){$firstIds[[string]$item.recordId]=$true}
          $stable=@($second|Where-Object {$firstIds.ContainsKey([string]$_.recordId)}|Select-Object -First $limit)
          [pscustomobject]@{
            ok=$true
            firstObservationCount=$first.Count
            secondObservationCount=$second.Count
            events=$stable
          }|ConvertTo-Json -Depth 5 -Compress
        } catch {
          [pscustomobject]@{ok=$false;error='application_crash_diagnostic_failed'}|ConvertTo-Json -Compress
          exit 2
        }
        """;

    private readonly IExternalProcessRunner _runner;

    internal WindowsApplicationCrashDiagnosticAdapter()
        : this(new ExternalProcessRunner()) { }

    internal WindowsApplicationCrashDiagnosticAdapter(IExternalProcessRunner runner) =>
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));

    public bool CanHandle(string operation) =>
        operation == "system.application.crash.diagnose";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        try
        {
            int hours = ExternalJson.OptionalInt(arguments, "hours", 24);
            int limit = ExternalJson.OptionalInt(arguments, "limit", 20);
            if (hours is < 1 or > 168 || limit is < 1 or > 50)
                return ExternalJson.Failure(operation, "invalid_arguments");

            ExternalProcessResult process = await _runner.RunAsync(
                "powershell.exe",
                [
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "& {\n" + DiagnosticScript + "\n}",
                    hours.ToString(CultureInfo.InvariantCulture),
                    limit.ToString(CultureInfo.InvariantCulture),
                ],
                TimeSpan.FromSeconds(30),
                cancellationToken).ConfigureAwait(false);
            string line = process.Output.Split(
                ['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).LastOrDefault() ?? "{}";
            using JsonDocument response = JsonDocument.Parse(line);
            if (!response.RootElement.TryGetProperty("ok", out JsonElement ok)
                || ok.ValueKind != JsonValueKind.True
                || !response.RootElement.TryGetProperty("events", out JsonElement events))
                return ExternalJson.Failure(operation, "application_crash_diagnostic_failed");

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteNumber("hours", hours);
                writer.WriteNumber("firstObservationCount",
                    response.RootElement.GetProperty("firstObservationCount").GetInt32());
                writer.WriteNumber("secondObservationCount",
                    response.RootElement.GetProperty("secondObservationCount").GetInt32());
                writer.WritePropertyName("events");
                events.WriteTo(writer);
                writer.WriteString("authority", "windows_application_eventlog_recordid_secondread");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, false);
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or InvalidDataException or TimeoutException)
        {
            return ExternalJson.Failure(operation, "application_crash_diagnostic_failed");
        }
    }
}
