using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

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
    private readonly IScheduledNotificationBackend _backend;
    private readonly string _schedulerScript;

    // M119: the Task Scheduler COM API answers in-process (~2 s of powershell.exe per turn less);
    // the script stays as the fallback when the scheduler cannot be reached that way.
    internal WindowsScheduledNotificationAdapter(string dataRoot)
        : this(dataRoot, new WindowsTaskSchedulerHost(), new ExternalProcessRunner(), Path.Combine(
            AppContext.BaseDirectory, "WindowsScheduledNotification.ps1"))
    {
    }

    internal WindowsScheduledNotificationAdapter(
        string dataRoot,
        ITaskSchedulerHost scheduler,
        IExternalProcessRunner runner,
        string schedulerScript)
        : this(dataRoot, runner, schedulerScript,
            scheduler ?? throw new ArgumentNullException(nameof(scheduler)))
    {
    }

    /// <summary>The script alone, as before M119.</summary>
    internal WindowsScheduledNotificationAdapter(
        string dataRoot,
        IExternalProcessRunner runner,
        string schedulerScript)
        : this(dataRoot, runner, schedulerScript, scheduler: null)
    {
    }

    private WindowsScheduledNotificationAdapter(
        string dataRoot,
        IExternalProcessRunner runner,
        string schedulerScript,
        ITaskSchedulerHost? scheduler)
    {
        string root = Path.GetFullPath(dataRoot);
        _alarmRoot = Path.Combine(root, "scheduled-notifications");
        _schedulerScript = Path.GetFullPath(schedulerScript);
        var script = new ScriptScheduledNotificationBackend(
            runner ?? throw new ArgumentNullException(nameof(runner)), _schedulerScript);
        _backend = scheduler is null
            ? script
            : new NativeScheduledNotificationBackend(
                scheduler, script, Path.Combine(root, "notification-scheduler-fallback.jsonl"));
    }

    public bool CanHandle(string operation) => operation is "schedule.alarms";

    // BAXY Renew (2026-10-15): one operation for what BAXY rings later, alarms and reminders (OpenClaw's cron; Anthropic,
    // «consolidate overlapping tools»): create, list, cancel and diagnose. The time is the person's: minutes from now
    // or a local clock time, never UTC written by the model (e2e E004: it wrote dueUtc wrong and retried the failing
    // call 15 times). The trigger is set in local time and the result says it in local time too.
    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string action = OptionalString(arguments, "action") ?? string.Empty;
        string kind = OptionalString(arguments, "kind") ?? "reminder";
        if (action is not ("create" or "list" or "cancel" or "diagnose"))
            return ExternalJson.FailureBeforeEffect(operation, "schedule_action_invalid");
        if (kind is not ("alarm" or "reminder"))
            return ExternalJson.FailureBeforeEffect(operation, "notification_kind_invalid");
        if (!File.Exists(_schedulerScript))
            return ExternalJson.Failure(operation, "notification_scheduler_script_missing");
        if (action is "diagnose" or "list")
        {
            try
            {
                return action == "diagnose"
                    ? await DiagnoseAsync(operation, cancellationToken).ConfigureAwait(false)
                    : await ListAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is IOException or JsonException
                or UnauthorizedAccessException or TimeoutException)
            {
                return ExternalJson.Failure(
                    operation, action == "diagnose" ? "notification_diagnostics_failed" : "notification_list_failed");
            }
        }

        string? at = OptionalString(arguments, "at");
        if (action == "cancel" && at is not null)
        {
            return TryLocalClock(at, out int hour, out int minute)
                ? await CancelAtAsync(operation, kind, hour, minute, cancellationToken).ConfigureAwait(false)
                : ExternalJson.FailureBeforeEffect(operation, "notification_clock_selector_invalid");
        }

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            if (action == "cancel")
                return await CancelAsync(operation, kind, effectBoundary, cancellationToken).ConfigureAwait(false);
            return TryDue(arguments, at, DateTimeOffset.Now, out DateTimeOffset due)
                ? await ScheduleAsync(operation, kind, arguments, due, effectBoundary, cancellationToken)
                    .ConfigureAwait(false)
                : ExternalJson.FailureBeforeEffect(operation, "schedule_time_invalid");
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

    private static string? OptionalString(JsonElement arguments, string name) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.String
        && !string.IsNullOrWhiteSpace(value.GetString())
            ? value.GetString()!.Trim()
            : null;

    /// <summary>
    /// When a new alarm or reminder rings: inMinutes or inSeconds (a timer) from now, or «at» as a local clock time
    /// («18:30», the next time that clock comes) or a local date and time («2026-10-16T08:00»).
    /// </summary>
    internal static bool TryDue(JsonElement arguments, string? at, DateTimeOffset now, out DateTimeOffset due)
    {
        due = default;
        if (arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("inMinutes", out JsonElement minutes)
            && minutes.ValueKind == JsonValueKind.Number)
        {
            if (!minutes.TryGetInt32(out int count) || count is < 1 or > 525_600) return false;
            due = now.AddMinutes(count);
            return true;
        }
        if (arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("inSeconds", out JsonElement seconds)
            && seconds.ValueKind == JsonValueKind.Number)
        {
            if (!seconds.TryGetInt32(out int count) || count is < 10 or > 86_400) return false;
            due = now.AddSeconds(count);
            return true;
        }
        if (at is null) return false;
        DateTime local;
        if (TryLocalClock(at, out int hour, out int minute))
        {
            DateTime today = now.LocalDateTime.Date.AddHours(hour).AddMinutes(minute);
            local = today > now.LocalDateTime.AddSeconds(5) ? today : today.AddDays(1);
        }
        else if (!DateTime.TryParseExact(
                at, ["yyyy-MM-ddTHH:mm", "yyyy-MM-dd HH:mm", "yyyy-MM-ddTHH:mm:ss"],
                System.Globalization.CultureInfo.InvariantCulture, System.Globalization.DateTimeStyles.None,
                out local))
        {
            return false;
        }
        due = new DateTimeOffset(local, TimeZoneInfo.Local.GetUtcOffset(local));
        return true;
    }

    // A 24-hour local clock time, «7:05» or «19:30».
    private static bool TryLocalClock(string at, out int hour, out int minute)
    {
        bool parsed = DateTime.TryParseExact(
            at, ["H:mm", "HH:mm"], System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.None, out DateTime clock);
        hour = parsed ? clock.Hour : -1;
        minute = parsed ? clock.Minute : -1;
        return parsed;
    }

    private async ValueTask<ExternalCapabilityReceipt> CancelAtAsync(
        string operation,
        string kind,
        int hour,
        int minute,
        CancellationToken cancellationToken)
    {
        ExternalProcessResult resolved;
        try
        {
            resolved = await _backend.RunAsync(
                new ScheduledNotificationRequest("resolve-at", kind)
                {
                    Hour = hour,
                    Minute = minute,
                    // M80: only the notifications this data root set are candidates.
                    AlarmRoot = _alarmRoot,
                },
                cancellationToken).ConfigureAwait(false);
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
            ExternalProcessResult canceled = await _backend.RunAsync(
                new ScheduledNotificationRequest("cancel-exact", kind)
                {
                    TaskName = taskName!,
                    DueUtc = nextRunUtc!,
                },
                cancellationToken).ConfigureAwait(false);
            return Parse(operation, canceled, taskName, effectBoundary, writer =>
            {
                writer.WriteString("kind", kind);
                writer.WriteNumber("hour", hour);
                writer.WriteNumber("minute", minute);
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
        ExternalProcessResult process = await _backend.RunAsync(
            new ScheduledNotificationRequest("diagnose", "reminder") { AlarmRoot = _alarmRoot },
            cancellationToken).ConfigureAwait(false);
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

    private async ValueTask<ExternalCapabilityReceipt> ListAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        // AGENDA1435 «listá los timers»: the scheduled BAXY tasks (alarms and
        // reminders) with the title kept in each ring script and the next run.
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 50);
        ExternalProcessResult process = await _backend.RunAsync(
            new ScheduledNotificationRequest("diagnose", "reminder") { AlarmRoot = _alarmRoot },
            cancellationToken).ConfigureAwait(false);
        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .LastOrDefault();
        if (process.ExitCode != 0 || line is null)
            return ExternalJson.Failure(operation, "notification_list_process_failed");
        using JsonDocument document = JsonDocument.Parse(line);
        JsonElement source = document.RootElement;
        if (!source.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            return ExternalJson.Failure(operation, "notification_list_postread_failed");
        List<(string Kind, string? Title, string? NextRunUtc, string State)> items = [];
        int staleTasks = 0;
        DateTimeOffset now = DateTimeOffset.UtcNow;
        if (source.TryGetProperty("tasks", out JsonElement tasks) && tasks.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement task in tasks.EnumerateArray())
            {
                string taskName = task.TryGetProperty("taskName", out JsonElement nameElement)
                    && nameElement.ValueKind == JsonValueKind.String ? nameElement.GetString() ?? "" : "";
                Match identity = Regex.Match(taskName, "^BAXY-(Alarm|Reminder)-[0-9a-f]{32}$",
                    RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(100));
                if (!identity.Success) continue;
                // M80 (DEV-D v3m D-w16-t2): the scheduler is shared by every BAXY data root of this user; the
                // notifications listed are the ones this data root set (its ring script is here).
                if (!File.Exists(Path.Combine(_alarmRoot, taskName + ".ps1"))) continue;
                string? nextRun = task.TryGetProperty("nextRunUtc", out JsonElement nextElement)
                    && nextElement.ValueKind == JsonValueKind.String ? nextElement.GetString() : null;
                string state = task.TryGetProperty("state", out JsonElement stateElement)
                    && stateElement.ValueKind == JsonValueKind.String ? stateElement.GetString() ?? "" : "";
                // A one-shot task that already fired keeps its registration without a
                // next run: it is not scheduled any more and is not listed.
                if (nextRun is null
                    || !DateTimeOffset.TryParse(nextRun, System.Globalization.CultureInfo.InvariantCulture,
                        System.Globalization.DateTimeStyles.RoundtripKind, out DateTimeOffset nextRunAt)
                    || nextRunAt <= now)
                {
                    staleTasks++;
                    continue;
                }
                items.Add((
                    identity.Groups[1].Value == "Alarm" ? "alarm" : "reminder",
                    ReadRingTitle(Path.Combine(_alarmRoot, taskName + ".ps1")),
                    nextRun,
                    state));
            }
        }
        var shown = items.OrderBy(item => item.NextRunUtc ?? "~", StringComparer.Ordinal).Take(limit).ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteNumber("count", items.Count);
            writer.WriteStartArray("notifications");
            foreach (var item in shown)
            {
                writer.WriteStartObject();
                writer.WriteString("kind", item.Kind);
                if (item.Title is not null) writer.WriteString("title", item.Title);
                if (item.NextRunUtc is not null)
                {
                    writer.WriteString("nextRunUtc", item.NextRunUtc);
                    if (DateTimeOffset.TryParse(item.NextRunUtc, System.Globalization.CultureInfo.InvariantCulture,
                            System.Globalization.DateTimeStyles.RoundtripKind, out DateTimeOffset next))
                        writer.WriteString("nextRunLocal", next.ToLocalTime().ToString(
                            "yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture));
                }
                writer.WriteString("state", item.State);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteNumber("staleTaskCount", staleTasks);
            writer.WriteNumber("resultLimit", limit);
            writer.WriteBoolean("resultsMayBeTruncated", items.Count > shown.Length);
            writer.WriteString("authority", "windows_task_scheduler_notification_list_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static string? ReadRingTitle(string path)
    {
        if (!File.Exists(path)) return null;
        Match encoded = Regex.Match(File.ReadAllText(path), @"FromBase64String\('([A-Za-z0-9+/=]+)'\)",
            RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(100));
        if (!encoded.Success) return null;
        try
        {
            return Encoding.UTF8.GetString(Convert.FromBase64String(encoded.Groups[1].Value));
        }
        catch (FormatException)
        {
            return null;
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> ScheduleAsync(
        string operation,
        string kind,
        JsonElement arguments,
        DateTimeOffset due,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string title = ExternalJson.RequiredString(arguments, "title");
        string? recurrence = arguments.TryGetProperty("recurrence", out JsonElement recurrenceElement)
            ? recurrenceElement.GetString() : null;
        if (recurrence is not null and not ("daily" or "hourly"))
            return ExternalJson.Failure(operation, "notification_recurrence_invalid");
        if (due <= DateTimeOffset.UtcNow.AddSeconds(5)
            || due > DateTimeOffset.UtcNow.AddYears(1)
            || Encoding.UTF8.GetByteCount(title) > 1_024)
            return ExternalJson.Failure(operation, "notification_schedule_invalid");

        await PruneSpentNotificationsAsync(cancellationToken).ConfigureAwait(false);
        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(_alarmRoot);
        string id = Guid.NewGuid().ToString("N");
        string taskName = "BAXY-" + (kind == "alarm" ? "Alarm-" : "Reminder-") + id;
        string ringScript = Path.Combine(_alarmRoot, taskName + ".ps1");
        string receipt = Path.Combine(_alarmRoot, taskName + ".fired");
        WriteRingScript(ringScript, receipt, title);
        ExternalProcessResult process = await _backend.RunAsync(
            new ScheduledNotificationRequest(
                recurrence is null ? "schedule" : "schedule-recurring", kind)
            {
                TaskName = taskName,
                DueUtc = due.ToString("O"),
                RingScriptPath = ringScript,
                Recurrence = recurrence,
            },
            cancellationToken).ConfigureAwait(false);
        return Parse(operation, process, taskName, effectBoundary, writer =>
        {
            writer.WriteString("kind", kind);
            writer.WriteString("title", title);
            writer.WriteString("dueUtc", due.ToUniversalTime());
            writer.WriteString("dueLocal", due.ToLocalTime().ToString(
                "yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture));
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
        ExternalProcessResult process = await _backend.RunAsync(
            // M80 (DEV-D v3m D-w18-t5): the latest is the last one this data root set that is still pending.
            new ScheduledNotificationRequest("cancel", kind) { AlarmRoot = _alarmRoot },
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

    /// <summary>
    /// How long a ring script stays after its last ring. A recurring notification rewrites its receipt each time
    /// it rings, so only a one-shot that rang long ago, or a recurring one that stopped ringing, gets this old.
    /// </summary>
    internal static readonly TimeSpan SpentRingScriptAge = TimeSpan.FromDays(30);

    /// <summary>
    /// Removes the ring script and receipt of every notification of this data root whose last ring is older than
    /// <see cref="SpentRingScriptAge"/> and whose task the scheduler no longer holds (auditoría de estabilidad r19,
    /// hallazgo 4: scripts and receipts piled up with no live task behind them). A task that is still registered
    /// keeps its script whatever the age of its receipt: a daily one whose machine stayed off for a month still
    /// rings when it comes back. A script that never rang has no receipt and stays: it may still be pending.
    /// </summary>
    internal static void PruneSpentRingScripts(
        string alarmRoot, DateTimeOffset now, IReadOnlySet<string> liveTaskNames)
    {
        ArgumentNullException.ThrowIfNull(liveTaskNames);
        foreach (string receipt in SpentReceipts(alarmRoot, now))
        {
            if (liveTaskNames.Contains(Path.GetFileNameWithoutExtension(receipt))) continue;
            try
            {
                File.Delete(Path.ChangeExtension(receipt, ".ps1"));
                File.Delete(receipt);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // A file in use stays for the next notification set.
            }
        }
    }

    private static string[] SpentReceipts(string alarmRoot, DateTimeOffset now)
    {
        try
        {
            return Directory.GetFiles(alarmRoot, "BAXY-*.fired")
                .Where(receipt => now - File.GetLastWriteTimeUtc(receipt) > SpentRingScriptAge)
                .ToArray();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    // Only when a receipt is old enough does the scheduler get read, and only a read that answered with its
    // task list lets anything go: without that proof every script stays.
    private async ValueTask PruneSpentNotificationsAsync(CancellationToken cancellationToken)
    {
        DateTimeOffset now = DateTimeOffset.UtcNow;
        if (SpentReceipts(_alarmRoot, now).Length == 0) return;
        IReadOnlySet<string>? live;
        try
        {
            ExternalProcessResult process = await _backend.RunAsync(
                new ScheduledNotificationRequest("diagnose", "reminder") { AlarmRoot = _alarmRoot },
                cancellationToken).ConfigureAwait(false);
            live = ReadTaskNames(process);
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or UnauthorizedAccessException or TimeoutException or InvalidDataException)
        {
            return;
        }
        if (live is not null) PruneSpentRingScripts(_alarmRoot, now, live);
    }

    private static HashSet<string>? ReadTaskNames(ExternalProcessResult process)
    {
        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .LastOrDefault();
        if (process.ExitCode != 0 || line is null) return null;
        using JsonDocument document = JsonDocument.Parse(line);
        JsonElement source = document.RootElement;
        if (!source.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
            || !source.TryGetProperty("tasks", out JsonElement tasks) || tasks.ValueKind != JsonValueKind.Array)
            return null;
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (JsonElement task in tasks.EnumerateArray())
        {
            if (task.ValueKind != JsonValueKind.Object
                || !task.TryGetProperty("taskName", out JsonElement name)
                || name.ValueKind != JsonValueKind.String)
                return null;
            names.Add(name.GetString()!);
        }
        return names;
    }

    // What rings: a Windows notification with the title (PowerShell's own AppUserModelID, which Windows registers;
    // msg.exe, used before, does not exist on Windows 11 Home, so the title was never shown there), then the sound.
    // The receipt is written after ringing and says what was delivered: the notification only when it is read back
    // from the notification history, and which sound played.
    private static void WriteRingScript(string path, string receiptPath, string title)
    {
        string title64 = Convert.ToBase64String(Encoding.UTF8.GetBytes(title));
        string receipt64 = Convert.ToBase64String(Encoding.UTF8.GetBytes(receiptPath));
        string tag = Path.GetFileNameWithoutExtension(path)[^16..];
        string script = "$ErrorActionPreference='Stop'\n"
            + "$title=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + title64 + "'))\n"
            + "$receipt=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + receipt64 + "'))\n"
            + "$toast=$false\n"
            + "try{[void][Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]\n"
            + "$app='{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe'\n"
            + "$xml=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)\n"
            + "$text=$xml.GetElementsByTagName('text');[void]$text.Item(0).AppendChild($xml.CreateTextNode('BAXY'));[void]$text.Item(1).AppendChild($xml.CreateTextNode($title))\n"
            + "$note=[Windows.UI.Notifications.ToastNotification]::new($xml);$note.Tag='" + tag + "'\n"
            + "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($note);Start-Sleep -Milliseconds 300\n"
            + "$toast=@([Windows.UI.Notifications.ToastNotificationManager]::History.GetHistory($app)|Where-Object{$_.Tag -eq '" + tag + "'}).Count -gt 0}catch{}\n"
            + "$sound='none'\n"
            + "try{$wav='C:\\Windows\\Media\\Alarm01.wav'\n"
            + "if([IO.File]::Exists($wav)){for($i=0;$i -lt 3;$i++){(New-Object Media.SoundPlayer $wav).PlaySync()};$sound='wav'}"
            + "else{for($i=0;$i -lt 3;$i++){[Console]::Beep(880,700)};$sound='beep'}}catch{}\n"
            + "[IO.File]::WriteAllText($receipt,(@{rangUtc=[DateTimeOffset]::UtcNow.ToString('O');notificationShown=$toast;sound=$sound}|ConvertTo-Json -Compress))\n";
        File.WriteAllText(path, script, new UTF8Encoding(false));
    }
}
