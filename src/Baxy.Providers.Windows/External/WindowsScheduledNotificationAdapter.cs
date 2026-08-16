using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsScheduledNotificationAdapter : IExternalOperationAdapter
{
    private static readonly string[] ResultStringProperties =
        ["taskName", "state", "nextRunUtc", "authority"];
    private static readonly string[] DiagnosticBooleanProperties =
        ["schedulerRunning", "toastEnabled", "healthy"];
    private static readonly string[] DiagnosticIntegerProperties =
        ["taskCount", "firedReceiptCount", "issueCount"];
    private readonly string _alarmRoot;
    private readonly IExternalProcessRunner _runner;
    private readonly string _schedulerScript;

    internal WindowsScheduledNotificationAdapter(string dataRoot)
        : this(dataRoot, new ExternalProcessRunner(), Path.Combine(
            AppContext.BaseDirectory, "WindowsScheduledNotification.ps1"))
    {
    }

    internal WindowsScheduledNotificationAdapter(
        string dataRoot,
        IExternalProcessRunner runner,
        string schedulerScript)
    {
        _alarmRoot = Path.Combine(Path.GetFullPath(dataRoot), "scheduled-notifications");
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _schedulerScript = Path.GetFullPath(schedulerScript);
    }

    public bool CanHandle(string operation) => operation is
        "notification.cancel.at" or "notification.cancel.latest"
        or "notification.diagnose" or "notification.schedule";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (operation == "notification.diagnose")
        {
            if (!File.Exists(_schedulerScript))
                return ExternalJson.Failure(operation, "notification_scheduler_script_missing");
            try
            {
                return await DiagnoseAsync(operation, cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is IOException or JsonException
                or UnauthorizedAccessException or TimeoutException)
            {
                return ExternalJson.Failure(operation, "notification_diagnostics_failed");
            }
        }
        string kind;
        try
        {
            kind = ExternalJson.RequiredString(arguments, "kind");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "notification_kind_invalid");
        }
        if (kind is not ("alarm" or "reminder"))
            return ExternalJson.Failure(operation, "notification_kind_invalid");
        if (!File.Exists(_schedulerScript))
            return ExternalJson.Failure(operation, "notification_scheduler_script_missing");
        if (operation == "notification.cancel.at")
        {
            return await CancelAtAsync(
                operation, kind, arguments, cancellationToken).ConfigureAwait(false);
        }
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return operation == "notification.schedule"
                ? await ScheduleAsync(
                    operation, kind, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false)
                : await CancelAsync(
                    operation, kind, effectBoundary, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "notification_scheduler_failed");
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or UnauthorizedAccessException or TimeoutException or InvalidDataException)
        {
            return effectBoundary.Failure(operation, "notification_scheduler_failed");
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> CancelAtAsync(
        string operation,
        string kind,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int hour = ExternalJson.OptionalInt(arguments, "hour", -1);
        int minute = ExternalJson.OptionalInt(arguments, "minute", 0);
        string? period = arguments.TryGetProperty("period", out JsonElement periodElement)
            ? periodElement.GetString()
            : null;
        if (hour is < 0 or > 23
            || minute is < 0 or > 59
            || period is not null and not ("am" or "pm")
            || period is not null && hour is not (>= 1 and <= 12))
        {
            return ExternalJson.FailureBeforeEffect(
                operation, "notification_clock_selector_invalid");
        }

        ExternalProcessResult resolved;
        try
        {
            resolved = await _runner.RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                    _schedulerScript, "-Mode", "resolve-at", "-Kind", kind,
                    "-Hour", hour.ToString(System.Globalization.CultureInfo.InvariantCulture),
                    "-Minute", minute.ToString(System.Globalization.CultureInfo.InvariantCulture),
                    .. (period is null ? [] : new[] { "-Period", period })],
                TimeSpan.FromSeconds(30), cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or UnauthorizedAccessException or TimeoutException or InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(
                operation, "notification_clock_resolution_failed");
        }

        if (!TryParseExactClockSelection(
                resolved, kind, out string? taskName, out string? nextRunUtc,
                out string resolutionError))
        {
            return ExternalJson.FailureBeforeEffect(operation, resolutionError);
        }

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            effectBoundary.Cross(cancellationToken);
            ExternalProcessResult canceled = await _runner.RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                    _schedulerScript, "-Mode", "cancel-exact", "-Kind", kind,
                    "-TaskName", taskName!, "-DueUtc", nextRunUtc!],
                TimeSpan.FromSeconds(30), cancellationToken).ConfigureAwait(false);
            return Parse(operation, canceled, taskName, effectBoundary, writer =>
            {
                writer.WriteString("kind", kind);
                writer.WriteNumber("hour", hour);
                writer.WriteNumber("minute", minute);
                if (period is not null) writer.WriteString("period", period);
                writer.WriteString("expectedNextRunUtc", nextRunUtc);
            });
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "notification_scheduler_failed");
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or UnauthorizedAccessException or TimeoutException or InvalidDataException)
        {
            return effectBoundary.Failure(operation, "notification_scheduler_failed");
        }
    }

    private static bool TryParseExactClockSelection(
        ExternalProcessResult process,
        string kind,
        out string? taskName,
        out string? nextRunUtc,
        out string error)
    {
        taskName = null;
        nextRunUtc = null;
        error = "notification_clock_resolution_failed";
        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .LastOrDefault();
        if (process.ExitCode != 0 || line is null) return false;
        using JsonDocument document = JsonDocument.Parse(line);
        JsonElement source = document.RootElement;
        if (!source.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
        {
            if (source.TryGetProperty("matchCount", out JsonElement count)
                && count.ValueKind == JsonValueKind.Number)
            {
                error = count.GetInt32() == 0
                    ? "notification_clock_not_found"
                    : "notification_clock_ambiguous";
            }
            return false;
        }
        taskName = source.TryGetProperty("taskName", out JsonElement task)
            && task.ValueKind == JsonValueKind.String ? task.GetString() : null;
        nextRunUtc = source.TryGetProperty("nextRunUtc", out JsonElement next)
            && next.ValueKind == JsonValueKind.String ? next.GetString() : null;
        string prefix = kind == "alarm" ? "BAXY-Alarm-" : "BAXY-Reminder-";
        if (taskName is null
            || !taskName.StartsWith(prefix, StringComparison.Ordinal)
            || taskName.Length != prefix.Length + 32
            || !taskName[prefix.Length..].All(Uri.IsHexDigit)
            || !DateTimeOffset.TryParse(
                nextRunUtc,
                System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.RoundtripKind,
                out DateTimeOffset nextRun)
            || nextRun <= DateTimeOffset.UtcNow)
        {
            taskName = null;
            nextRunUtc = null;
            return false;
        }
        return true;
    }

    private async ValueTask<ExternalCapabilityReceipt> DiagnoseAsync(
        string operation,
        CancellationToken cancellationToken)
    {
        ExternalProcessResult process = await _runner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                _schedulerScript, "-Mode", "diagnose", "-Kind", "reminder",
                "-AlarmRoot", _alarmRoot],
            TimeSpan.FromSeconds(30), cancellationToken).ConfigureAwait(false);
        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .LastOrDefault();
        if (process.ExitCode != 0 || line is null)
            return ExternalJson.Failure(operation, "notification_diagnostics_process_failed");
        using JsonDocument document = JsonDocument.Parse(line);
        JsonElement source = document.RootElement;
        if (!source.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            return ExternalJson.Failure(operation, "notification_diagnostics_postread_failed");
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            foreach (string name in DiagnosticBooleanProperties)
                if (source.TryGetProperty(name, out JsonElement value)
                    && value.ValueKind is JsonValueKind.True or JsonValueKind.False)
                    writer.WriteBoolean(name, value.GetBoolean());
            foreach (string name in DiagnosticIntegerProperties)
                if (source.TryGetProperty(name, out JsonElement value)
                    && value.ValueKind == JsonValueKind.Number)
                    writer.WriteNumber(name, value.GetInt32());
            if (source.TryGetProperty("tasks", out JsonElement tasks)
                && tasks.ValueKind == JsonValueKind.Array)
            {
                writer.WritePropertyName("tasks"); tasks.WriteTo(writer);
            }
            writer.WriteString("authority", "windows_task_scheduler_notification_diagnostics_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, false);
    }

    private async ValueTask<ExternalCapabilityReceipt> ScheduleAsync(
        string operation,
        string kind,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string title = ExternalJson.RequiredString(arguments, "title");
        string dueText = ExternalJson.RequiredString(arguments, "dueUtc");
        string? recurrence = arguments.TryGetProperty("recurrence", out JsonElement recurrenceElement)
            ? recurrenceElement.GetString() : null;
        if (recurrence is not null and not ("daily" or "hourly"))
            return ExternalJson.Failure(operation, "notification_recurrence_invalid");
        if (!DateTimeOffset.TryParse(
            dueText, System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.RoundtripKind, out DateTimeOffset due)
            || due <= DateTimeOffset.UtcNow.AddSeconds(5)
            || due > DateTimeOffset.UtcNow.AddYears(1)
            || Encoding.UTF8.GetByteCount(title) > 1_024)
            return ExternalJson.Failure(operation, "notification_schedule_invalid");

        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(_alarmRoot);
        string id = Guid.NewGuid().ToString("N");
        string taskName = "BAXY-" + (kind == "alarm" ? "Alarm-" : "Reminder-") + id;
        string ringScript = Path.Combine(_alarmRoot, taskName + ".ps1");
        string receipt = Path.Combine(_alarmRoot, taskName + ".fired");
        WriteRingScript(ringScript, receipt, title);
        ExternalProcessResult process = await _runner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                _schedulerScript, "-Mode", recurrence is null ? "schedule" : "schedule-recurring",
                "-Kind", kind,
                "-TaskName", taskName, "-DueUtc", due.ToString("O"),
                "-RingScriptPath", ringScript,
                .. (recurrence is null ? [] : new[] { "-Recurrence", recurrence })],
            TimeSpan.FromSeconds(30),
            cancellationToken).ConfigureAwait(false);
        return Parse(operation, process, taskName, effectBoundary, writer =>
        {
            writer.WriteString("kind", kind);
            writer.WriteString("title", title);
            writer.WriteString("dueUtc", due.ToUniversalTime());
            if (recurrence is not null) writer.WriteString("recurrence", recurrence);
        });
    }

    private async ValueTask<ExternalCapabilityReceipt> CancelAsync(
        string operation,
        string kind,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        effectBoundary.Cross(cancellationToken);
        ExternalProcessResult process = await _runner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                _schedulerScript, "-Mode", "cancel", "-Kind", kind],
            TimeSpan.FromSeconds(30),
            cancellationToken).ConfigureAwait(false);
        return Parse(operation, process, expectedTaskName: null, effectBoundary,
            writer => writer.WriteString("kind", kind));
    }

    private static ExternalCapabilityReceipt Parse(
        string operation,
        ExternalProcessResult process,
        string? expectedTaskName,
        ExternalEffectBoundary effectBoundary,
        Action<Utf8JsonWriter> writeKnown)
    {
        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .LastOrDefault();
        if (process.ExitCode != 0 || line is null)
            return effectBoundary.Failure(operation, "notification_scheduler_process_failed");
        using JsonDocument document = JsonDocument.Parse(line);
        JsonElement source = document.RootElement;
        bool effect = source.TryGetProperty("effectObserved", out JsonElement effectValue)
            && effectValue.ValueKind == JsonValueKind.True;
        if (!source.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
        {
            bool crossed = !source.TryGetProperty(
                    "effectBoundaryCrossed", out JsonElement crossedValue)
                || crossedValue.ValueKind != JsonValueKind.False;
            if (!crossed)
                return ExternalJson.FailureBeforeEffect(
                    operation, "notification_scheduler_precondition_changed");
            return effectBoundary.Failure(
                operation, "notification_scheduler_postread_failed", effect);
        }
        if (expectedTaskName is not null
            && (!source.TryGetProperty("taskName", out JsonElement observedTask)
                || observedTask.ValueKind != JsonValueKind.String
                || !string.Equals(
                    observedTask.GetString(), expectedTaskName, StringComparison.Ordinal)))
            return effectBoundary.Failure(
                operation, "notification_scheduler_identity_mismatch", effect);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writeKnown(writer);
            foreach (string name in ResultStringProperties)
            {
                if (source.TryGetProperty(name, out JsonElement value)
                    && value.ValueKind == JsonValueKind.String)
                    writer.WriteString(name, value.GetString());
            }
            if (source.TryGetProperty("canceled", out JsonElement canceled)
                && canceled.ValueKind is JsonValueKind.True or JsonValueKind.False)
                writer.WriteBoolean("canceled", canceled.GetBoolean());
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effect);
    }

    private static void WriteRingScript(string path, string receiptPath, string title)
    {
        string title64 = Convert.ToBase64String(Encoding.UTF8.GetBytes(title));
        string receipt64 = Convert.ToBase64String(Encoding.UTF8.GetBytes(receiptPath));
        string script = "$ErrorActionPreference='SilentlyContinue'\n"
            + "$title=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + title64 + "'))\n"
            + "$receipt=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + receipt64 + "'))\n"
            + "[IO.File]::WriteAllText($receipt,[DateTimeOffset]::UtcNow.ToString('O'))\n"
            + "$sound='C:\\Windows\\Media\\Alarm01.wav'\n"
            + "if([IO.File]::Exists($sound)){for($i=0;$i -lt 3;$i++){(New-Object Media.SoundPlayer $sound).PlaySync()}}"
            + "else{for($i=0;$i -lt 3;$i++){[Console]::Beep(880,700)}}\n"
            + "& msg.exe * ('BAXY: '+$title)\n";
        File.WriteAllText(path, script, new UTF8Encoding(false));
    }
}
