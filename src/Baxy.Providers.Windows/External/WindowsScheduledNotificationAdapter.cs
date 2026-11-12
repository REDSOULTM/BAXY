using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsScheduledNotificationAdapter : IExternalOperationAdapter
{
    private static readonly string[] ResultStringProperties =
        ["taskName", "state", "nextRunUtc", "authority"];
    private static readonly string[] DiagnosticBooleanProperties =
        ["schedulerRunning", "toastEnabled", "healthy"];
    private static readonly string[] DiagnosticIntegerProperties =
        ["taskCount", "firedReceiptCount", "firedNotShownCount", "firedShownUnreadCount", "issueCount"];
    private static readonly string[] DiagnosticArrayProperties = ["tasks", "firedReceipts"];
    private readonly string _alarmRoot;
    private readonly IScheduledNotificationBackend _backend;

    // M119: the Task Scheduler COM API answers in-process.
    internal WindowsScheduledNotificationAdapter(string dataRoot)
        : this(dataRoot, new NativeScheduledNotificationBackend(new WindowsTaskSchedulerHost()))
    {
    }

    internal WindowsScheduledNotificationAdapter(string dataRoot, IScheduledNotificationBackend backend)
    {
        _alarmRoot = Path.Combine(Path.GetFullPath(dataRoot), ScheduledRingTasks.FolderName);
        _backend = backend ?? throw new ArgumentNullException(nameof(backend));
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
        string? namedKind = OptionalString(arguments, "kind");
        string kind = namedKind ?? "reminder";
        if (action is not ("create" or "list" or "cancel" or "diagnose" or "stop" or "snooze"))
            return ExternalJson.FailureBeforeEffect(operation, "schedule_action_invalid");
        if (kind is not ("alarm" or "reminder"))
            return ExternalJson.FailureBeforeEffect(operation, "notification_kind_invalid");
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

        if (action is "stop" or "snooze")
            return await AnswerRingAsync(operation, action, arguments, namedKind, cancellationToken).ConfigureAwait(false);

        string? at = OptionalString(arguments, "at");
        if (action == "cancel" && at is not null)
        {
            return TryLocalClock(at, out int hour, out int minute)
                ? await CancelAtAsync(operation, namedKind is null ? ["alarm", "reminder"] : [kind], hour, minute,
                    cancellationToken).ConfigureAwait(false)
                : ExternalJson.FailureBeforeEffect(operation, "notification_clock_selector_invalid");
        }

        // ALR5 (B4): with no time, cancel takes «the only one pending»; while one of that kind rings, which one is meant
        // is not said (the one ringing, if it rang once, is not even pending), and the one deleted was another.
        if (action == "cancel" && RingingNow() is { Count: > 0 } ringing
            && ringing.Any(ring => namedKind is null || ring.Kind == namedKind))
        {
            return CancelWhileItRings(operation, ringing, "nothing was canceled: cancel deletes one that is set and "
                + "is not ringing, and with no at it does not say which. What rings now (ringingNow) is answered with "
                + "stop, which silences it, or snooze, which rings it again later (inMinutes or at); at with its time "
                + "names one that is set to cancel");
        }

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            if (action == "cancel")
                return await CancelPendingAsync(operation, namedKind, effectBoundary, cancellationToken)
                    .ConfigureAwait(false);
            return TryDue(arguments, at, DateTimeOffset.Now, out DateTimeOffset due, out bool movedToNextDay)
                ? await ScheduleAsync(operation, kind, arguments, due, movedToNextDay, effectBoundary,
                    cancellationToken).ConfigureAwait(false)
                : ExternalJson.FailureBeforeEffect(operation, "schedule_time_invalid");
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "notification_scheduler_failed");
        }
        // V5E060: the arguments are read before this boundary with their own codes; what lands here is the scheduler's.
        catch (Exception exception) when (exception is IOException or JsonException
            or UnauthorizedAccessException or TimeoutException)
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

    // An argument written with a value (null is the same as leaving it out).
    private static bool Present(JsonElement arguments, string name) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty(name, out JsonElement value)
        && value.ValueKind != JsonValueKind.Null;

    /// <summary>
    /// When a new alarm or reminder rings: inMinutes or inSeconds (a timer) from now, or «at» as a local clock time
    /// («18:30», the next time that clock comes) or a local date and time («2026-10-16T08:00»).
    /// </summary>
    internal static bool TryDue(JsonElement arguments, string? at, DateTimeOffset now, out DateTimeOffset due) =>
        TryDue(arguments, at, now, out due, out _);

    // movedToNextDay: a clock time that had already passed today, set for tomorrow.
    private static bool TryDue(
        JsonElement arguments, string? at, DateTimeOffset now, out DateTimeOffset due, out bool movedToNextDay)
    {
        due = default;
        movedToNextDay = false;
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
            movedToNextDay = today <= now.LocalDateTime.AddSeconds(5);
            local = movedToNextDay ? today.AddDays(1) : today;
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

    // FT/proveedores goal (review of receipts): a cancel at a clock time with no kind looked only among reminders (the
    // default kind), so the alarm at that time was «not found» (or a reminder at that time went instead); most cancels
    // the model writes name the time and no kind. With no kind both are resolved (reads, no effect) and only one
    // notification at that time in all is canceled; one of each kind is ambiguous.
    private async ValueTask<ExternalCapabilityReceipt> CancelAtAsync(
        string operation,
        string[] kinds,
        int hour,
        int minute,
        CancellationToken cancellationToken)
    {
        string kind = kinds[0];
        string? taskName = null, nextRunUtc = null;
        string resolutionError = "notification_clock_not_found";
        int found = 0;
        foreach (string candidate in kinds)
        {
            ExternalProcessResult resolved;
            try
            {
                resolved = await _backend.RunAsync(
                    new ScheduledNotificationRequest("resolve-at", candidate)
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

            if (TryParseExactClockSelection(
                    resolved, candidate, out string? candidateTask, out string? candidateNextRun,
                    out string candidateError))
            {
                found++;
                (kind, taskName, nextRunUtc) = (candidate, candidateTask, candidateNextRun);
            }
            else if (candidateError != "notification_clock_not_found")
            {
                resolutionError = candidateError;
                if (kinds.Length == 1 || candidateError != "notification_clock_ambiguous")
                    return ExternalJson.FailureBeforeEffect(operation, candidateError);
                found += 2;
            }
        }

        IReadOnlyList<AlarmRingHandoff.Ring> ringing = RingingNow();
        if (found != 1)
        {
            string error = found == 0 ? resolutionError : "notification_clock_ambiguous";
            // ALR5 (B4): while something rings, a cancel that found none at that time says that nothing was deleted
            // nor set and that it rings on (the words after it were «te lo recordaré a las once», with nothing set).
            return error != "notification_clock_not_found" || ringing.Count == 0
                ? ExternalJson.FailureBeforeEffect(operation, error)
                : CancelWhileItRings(operation, ringing, FormattableString.Invariant(
                    $"nothing was canceled and nothing was set: none is set for {hour:00}:{minute:00}. What rings now ")
                    + "(ringingNow) still rings: stop silences it, snooze rings it again later (inMinutes or at)", error);
        }

        if (ringing.Any(ring => string.Equals(ring.TaskName, taskName, StringComparison.Ordinal)))
        {
            return CancelWhileItRings(operation, ringing, "nothing was canceled: that one rings now. stop silences it "
                + "(one that repeats still rings next time) and snooze rings it again later (inMinutes or at); cancel "
                + "deletes it once it no longer rings");
        }

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return await CancelExactAsync(operation, kind, taskName!, nextRunUtc!, effectBoundary, writer =>
            {
                writer.WriteString("kind", kind);
                writer.WriteNumber("hour", hour);
                writer.WriteNumber("minute", minute);
                writer.WriteString("expectedNextRunUtc", nextRunUtc);
            }, cancellationToken).ConfigureAwait(false);
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

    // ALR5 (B4, held-out bench on the base: asked to be reminded later of the one ringing, the model wrote a cancel in
    // 4 of 45 samples and said «te lo recordaré»; a cancel deletes, and with another reminder pending it deleted that
    // one): what is deleted does not come back, so cancel never takes the one that rings now nor picks among the rest
    // while one rings. What rings is answered with stop or snooze, as Google's assistant keeps «Cancel an existing
    // alarm» apart from «Stop a ringing alarm» (Google Nest Help, «Set and manage alarms») and Android's clock Stop
    // apart from Delete (Clock Help, «Set, cancel, or snooze alarms»). Nothing is deleted, and the result says what
    // rings and what answers it (Anthropic, «Writing tools for agents»: an error says what to change).
    private static ExternalCapabilityReceipt CancelWhileItRings(
        string operation, IReadOnlyList<AlarmRingHandoff.Ring> ringing, string next,
        string error = "notification_cancel_rings_now") =>
        ExternalJson.FailureBeforeEffect(operation, error) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteBoolean("canceled", false);
                WriteRinging(writer, ringing);
                writer.WriteString("next", next);
                writer.WriteEndObject();
            }),
        };

    // The one task named (its identity and the next run read before), deleted only while it still rings then.
    private async ValueTask<ExternalCapabilityReceipt> CancelExactAsync(
        string operation,
        string kind,
        string taskName,
        string nextRunUtc,
        ExternalEffectBoundary effectBoundary,
        Action<Utf8JsonWriter> writeKnown,
        CancellationToken cancellationToken)
    {
        effectBoundary.Cross(cancellationToken);
        ExternalProcessResult canceled = await _backend.RunAsync(
            new ScheduledNotificationRequest("cancel-exact", kind)
            {
                TaskName = taskName,
                DueUtc = nextRunUtc,
            },
            cancellationToken).ConfigureAwait(false);
        return Parse(operation, canceled, taskName, effectBoundary, writeKnown);
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
            foreach (string name in DiagnosticArrayProperties)
                if (source.TryGetProperty(name, out JsonElement items) && items.ValueKind == JsonValueKind.Array)
                {
                    writer.WritePropertyName(name); items.WriteTo(writer);
                }
            writer.WriteString("authority", "windows_task_scheduler_notification_diagnostics_postread");
            writer.WriteEndObject();
        });
        // BAXY Renew (notebook): a read of this operation, which also writes, changes nothing: what it asked for is
        // the scheduler read back, reached once the read answered (before, the handler turned it into
        // external_effect_unobserved and the model never saw the diagnosis).
        return ExternalJson.Switched(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> ListAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        // AGENDA1435 «listá los timers»: the scheduled BAXY tasks (alarms and
        // reminders) with the title kept in each ring script and the next run.
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 50);
        (List<PendingNotification>? items, int staleTasks, string? error) =
            await ReadPendingAsync(cancellationToken).ConfigureAwait(false);
        if (items is null)
        {
            return ExternalJson.Failure(operation, error == "scheduler_unavailable"
                ? "notification_scheduler_unavailable"
                : "notification_list_" + error);
        }
        var shown = items.OrderBy(item => item.NextRunUtc ?? "~", StringComparer.Ordinal).Take(limit).ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteNumber("count", items.Count);
            writer.WriteStartArray("notifications");
            foreach (var item in shown) WritePending(writer, item);
            writer.WriteEndArray();
            WriteRinging(writer, RingingNow());
            writer.WriteNumber("staleTaskCount", staleTasks);
            writer.WriteNumber("resultLimit", limit);
            writer.WriteBoolean("resultsMayBeTruncated", items.Count > shown.Length);
            writer.WriteString("authority", "windows_task_scheduler_notification_list_postread");
            writer.WriteEndObject();
        });
        // A read reached by reading, as the diagnosis above.
        return ExternalJson.Switched(operation, result, effectObserved: false);
    }

    private sealed record PendingNotification(
        string TaskName, string Kind, string? Title, string? NextRunUtc, string State);

    private static void WritePending(Utf8JsonWriter writer, PendingNotification item)
    {
        writer.WriteStartObject();
        writer.WriteString("kind", item.Kind);
        if (item.Title is not null) writer.WriteString("title", item.Title);
        if (item.NextRunUtc is not null)
        {
            writer.WriteString("nextRunUtc", item.NextRunUtc);
            WriteLocal(writer, item.NextRunUtc);
            WriteDay(writer, item.NextRunUtc, DateTimeOffset.Now);
        }
        writer.WriteString("state", item.State);
        writer.WriteEndObject();
    }

    // GUA1 (VIVO13, 11-11-2026): «¿Qué alarmas tengo puestas?» → «programada para hoy a las 09:15» with nextRunLocal
    // 2026-11-12 09:15 (tomorrow). The model had to subtract the clock line's date from this one, and the 4B carries a
    // number of one date into the other (VER1). The day relative to today is the scheduler's own reading, counted here.
    internal static void WriteDay(Utf8JsonWriter writer, string nextRunUtc, DateTimeOffset now)
    {
        if (!DateTimeOffset.TryParse(nextRunUtc, System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.RoundtripKind, out DateTimeOffset next))
            return;
        // In local days, as nextRunLocal is written.
        int days = (next.ToLocalTime().Date - now.ToLocalTime().Date).Days;
        writer.WriteString("nextRunDay", days switch
        {
            0 => "today",
            1 => "tomorrow",
            _ => string.Create(System.Globalization.CultureInfo.InvariantCulture, $"in {days} days"),
        });
    }

    private static void WriteLocal(Utf8JsonWriter writer, string nextRunUtc)
    {
        if (DateTimeOffset.TryParse(nextRunUtc, System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.RoundtripKind, out DateTimeOffset next))
            writer.WriteString("nextRunLocal", next.ToLocalTime().ToString(
                "yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture));
    }

    // The alarms and reminders of this data root still to ring, as the scheduler reads them back; null with the cause
    // («process_failed», «postread_failed», «scheduler_unavailable») when it was not read.
    private async ValueTask<(List<PendingNotification>? Items, int Stale, string? Error)> ReadPendingAsync(
        CancellationToken cancellationToken)
    {
        ExternalProcessResult process = await _backend.RunAsync(
            new ScheduledNotificationRequest("diagnose", "reminder") { AlarmRoot = _alarmRoot },
            cancellationToken).ConfigureAwait(false);
        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .LastOrDefault();
        if (process.ExitCode != 0 || line is null)
            return (null, 0, "process_failed");
        using JsonDocument document = JsonDocument.Parse(line);
        JsonElement source = document.RootElement;
        if (!source.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            return (null, 0, "postread_failed");
        // A scheduler that did not answer was not read: there is no list, not an empty one.
        if (!SchedulerAnswered(source))
            return (null, 0, "scheduler_unavailable");
        List<PendingNotification> items = [];
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
                items.Add(new PendingNotification(
                    taskName,
                    identity.Groups[1].Value == "Alarm" ? "alarm" : "reminder",
                    ScheduledRingScript.ReadTitle(Path.Combine(_alarmRoot, taskName + ".ps1")),
                    nextRun,
                    state));
            }
        }
        return (items, staleTasks, null);
    }

    private async ValueTask<ExternalCapabilityReceipt> ScheduleAsync(
        string operation,
        string kind,
        JsonElement arguments,
        DateTimeOffset due,
        bool movedToNextDay,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        // V5E060: the title is optional, as the catalog has it (a create without one was refused as a scheduler
        // failure the scheduler never saw); one that is there and is not words fails here with its own code.
        string? title = OptionalString(arguments, "title");
        if (title is null && Present(arguments, "title"))
            return ExternalJson.FailureBeforeEffect(operation, "notification_title_invalid");
        string? recurrence = OptionalString(arguments, "recurrence");
        if ((recurrence is null && Present(arguments, "recurrence")) || recurrence is not (null or "daily" or "hourly"))
            return ExternalJson.FailureBeforeEffect(operation, "notification_recurrence_invalid");
        if (due <= DateTimeOffset.UtcNow.AddSeconds(5))
            return DuePassed(operation, kind, title, recurrence, due);
        if (due > DateTimeOffset.UtcNow.AddYears(1)
            || (title is not null && Encoding.UTF8.GetByteCount(title) > 1_024))
            return ExternalJson.Failure(operation, "notification_schedule_invalid");

        await PruneSpentNotificationsAsync(cancellationToken).ConfigureAwait(false);
        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(_alarmRoot);
        string id = Guid.NewGuid().ToString("N");
        string taskName = "BAXY-" + (kind == "alarm" ? "Alarm-" : "Reminder-") + id;
        string ringScript = Path.Combine(_alarmRoot, taskName + ".ps1");
        // ALR1: the time it is set for is said when it rings («Alarma de las 7:00»); an hourly one rings at a new hour each
        // time, and says the time it rings.
        ScheduledRingScript.Write(ringScript, title, recurrence == "hourly"
            ? null
            : due.ToLocalTime().ToString("HH:mm", System.Globalization.CultureInfo.InvariantCulture));
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
        ExternalCapabilityReceipt scheduled = Parse(operation, process, taskName, effectBoundary, writer =>
        {
            writer.WriteString("kind", kind);
            if (title is not null) writer.WriteString("title", title);
            writer.WriteString("dueUtc", due.ToUniversalTime());
            writer.WriteString("dueLocal", due.ToLocalTime().ToString(
                "yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture));
            DateTimeOffset now = DateTimeOffset.Now;
            writer.WriteString("scheduledFor", DayFromToday(due, now));
            if (movedToNextDay)
            {
                writer.WriteBoolean("movedToNextDay", true);
                writer.WriteString("nowLocal", now.ToString(
                    "yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture));
            }
            if (recurrence is not null) writer.WriteString("recurrence", recurrence);
        });
        // Ronda final (limite 6): a scheduler that took nothing leaves nothing behind, so «before any effect» holds.
        if (!scheduled.Verified && !scheduled.EffectObserved && !scheduled.EffectMayHaveOccurred)
        {
            try { File.Delete(ringScript); } catch (Exception exception) when (exception is IOException or UnauthorizedAccessException) { }
        }

        return scheduled;
    }

    // Encargo 59 (sonda del 57, 6 of 6): «hoy a las 9» after 9 went as at "09:00", set for tomorrow, and the model said
    // «quedó para hoy» from a dueLocal it had to compare with today's date itself (Test of Time, arXiv 2406.09170: date
    // arithmetic is where models slip). As Anthropic's guide asks of a result (meaningful words, not raw values) and
    // as Android's clock confirms an alarm relative to now, the day it rings is said relative to today (scheduledFor),
    // and a clock time that had passed today says it moved, with the time here. Measured with the real model (5
    // phrases of a past time today, 5 seeds): tomorrow's alarm told as today's 20 of 25 before (none said tomorrow), 0
    // with the three fields; without nowLocal it gave a made-up cause («ya pasó la medianoche») 3 of 25, with it 1.
    private static string DayFromToday(DateTimeOffset due, DateTimeOffset now) =>
        (due.LocalDateTime.Date - now.LocalDateTime.Date).Days switch
        {
            0 => "today",
            1 => "tomorrow",
            _ => due.LocalDateTime.ToString("dddd yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture),
        };

    private static string LocalMinute(DateTimeOffset value) => value.ToLocalTime().ToString(
        "yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture);

    // Encargo 57 (banco de uso U35, three cycles of five): «despiértame mañana a las 7» went as at "<today>T07:00", a date
    // and time that had passed that afternoon, and the bare notification_schedule_invalid left the model saying the time
    // «is not valid». As Anthropic's guide to writing tools for agents asks of an error (what to change, in the form the
    // tool takes), the refusal says it set nothing (scheduled false), the time asked and the time here, both local, and
    // ends with the same call at that clock time alone, which TryDue sets for the next time that clock comes. Measured
    // with the real model (15 held-out failures): with the call leading, 4 set it and the rest said «la dejé para
    // mañana» with nothing set; «nothing is set yet» first and the call last, 15 of 15. Only a date and time can be past:
    // a clock time alone is always the next one.
    private static ExternalCapabilityReceipt DuePassed(
        string operation, string kind, string? title, string? recurrence, DateTimeOffset due)
    {
        DateTimeOffset now = DateTimeOffset.Now;
        string clock = due.ToLocalTime().ToString("HH:mm", System.Globalization.CultureInfo.InvariantCulture);
        _ = TryDue(default, clock, now, out DateTimeOffset next);
        var call = new System.Text.Json.Nodes.JsonObject { ["action"] = "create", ["kind"] = kind, ["at"] = clock };
        if (title is not null) call["title"] = title;
        if (recurrence is not null) call["recurrence"] = recurrence;
        string dueLocal = Local(due), nowLocal = Local(now);
        return ExternalJson.FailureBeforeEffect(operation, "notification_schedule_invalid") with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("kind", kind);
                writer.WriteBoolean("scheduled", false);
                writer.WriteString("dueLocal", dueLocal);
                writer.WriteString("nowLocal", nowLocal);
                writer.WriteString("next", $"nothing is set yet: {dueLocal} had already passed (it is {nowLocal} here); "
                    + $"to set it for {Local(next)}, call {Baxy.Kernel.Operations.WireNames.Call(operation, call)}");
                writer.WriteEndObject();
            }),
        };

        static string Local(DateTimeOffset value) => value.ToLocalTime().ToString(
            "yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture);
    }

    // Renew al máximo (w5): a cancel with no kind and no time looked only among reminders (the default kind), so
    // «cancela la alarma» written without kind found «nothing pending» while the alarm still rang (or canceled a
    // reminder instead). The pending ones of both kinds are read first (no effect): one kind pending is canceled as
    // that kind; none is said as none of either; both is ambiguous, with what is pending, and nothing is canceled.
    // Renew al máximo (w9): a cancel by kind canceled the newest of that kind without saying which. The one pending is
    // canceled by its identity (cancel-exact) and the result names it (title, local time); several of the kind cancel
    // none and list them (notification_cancel_ambiguous), and at names the one.
    private async ValueTask<ExternalCapabilityReceipt> CancelPendingAsync(
        string operation,
        string? namedKind,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        (List<PendingNotification>? items, _, string? error) =
            await ReadPendingAsync(cancellationToken).ConfigureAwait(false);
        if (items is null)
        {
            return ExternalJson.FailureBeforeEffect(operation, error == "scheduler_unavailable"
                ? "notification_scheduler_unavailable"
                : "notification_pending_read_failed");
        }

        PendingNotification[] candidates = [.. items
            .Where(item => namedKind is null || item.Kind == namedKind)
            .OrderBy(item => item.NextRunUtc ?? "~", StringComparer.Ordinal)];
        bool aid = ModelAids.On(ModelAids.CancelScope);
        if (candidates.Length == 0)
        {
            return ExternalJson.Switched(operation, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                if (namedKind is not null) writer.WriteString("kind", namedKind);
                writer.WriteBoolean("canceled", false);
                writer.WriteBoolean("pendingFound", false);
                if (aid)
                {
                    writer.WriteString("next",
                        $"nothing was canceled: no {namedKind ?? "alarm or reminder"} set by BAXY is pending");
                }
                writer.WriteString("authority", "windows_task_scheduler_notification_list_postread");
                writer.WriteEndObject();
            }), effectObserved: false);
        }

        if (candidates.Length > 1)
        {
            bool bothKinds = candidates.Select(item => item.Kind).Distinct(StringComparer.Ordinal).Count() > 1;
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteNumber("pendingCount", candidates.Length);
                writer.WriteStartArray("pending");
                foreach (PendingNotification item in candidates.Take(10))
                    WritePending(writer, item);
                writer.WriteEndArray();
                if (aid)
                {
                    writer.WriteString("next", bothKinds
                        ? "nothing was canceled: alarms and reminders set by BAXY are pending; "
                            + "kind, or at with its time, names the one to cancel"
                        : $"nothing was canceled: {candidates.Length} {candidates[0].Kind}s set by BAXY are pending; "
                            + "at with its time names the one to cancel");
                }
                writer.WriteEndObject();
            }), bothKinds ? "notification_kind_ambiguous" : "notification_cancel_ambiguous");
        }

        PendingNotification only = candidates[0];
        return await CancelExactAsync(operation, only.Kind, only.TaskName, only.NextRunUtc!, effectBoundary, writer =>
        {
            writer.WriteString("kind", only.Kind);
            if (only.Title is not null) writer.WriteString("title", only.Title);
            WriteLocal(writer, only.NextRunUtc!);
            writer.WriteString("expectedNextRunUtc", only.NextRunUtc);
        }, cancellationToken).ConfigureAwait(false);
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
            {
                // Renew al máximo (w8): a due time that passed while it was being scheduled is the same refusal as
                // one that had passed before (notification_schedule_invalid), and nothing was scheduled.
                string? cause = source.TryGetProperty("error", out JsonElement causeValue)
                    && causeValue.ValueKind == JsonValueKind.String ? causeValue.GetString() : null;
                return ExternalJson.FailureBeforeEffect(
                    operation,
                    cause switch
                    {
                        "task_scheduler_unavailable" => "notification_scheduler_unavailable",
                        "due_time_not_future" => "notification_schedule_invalid",
                        _ => "notification_scheduler_precondition_changed",
                    });
            }
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
        bool? canceled = source.TryGetProperty("canceled", out JsonElement canceledValue)
            && canceledValue.ValueKind is JsonValueKind.True or JsonValueKind.False
                ? canceledValue.GetBoolean()
                : null;
        // BAXY Renew (notebook): a cancel whose verified read found nothing of that kind pending from this BAXY
        // deleted nothing (canceled:false, no effect): nothing is left to cancel, the state asked for, and the
        // result says that nothing was pending (before, the handler reported it as a verification that failed).
        bool nothingPending = canceled == false && !effect;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writeKnown(writer);
            foreach (string name in ResultStringProperties)
            {
                if (source.TryGetProperty(name, out JsonElement value)
                    && value.ValueKind == JsonValueKind.String)
                    writer.WriteString(name, value.GetString());
            }
            if (canceled is bool wasCanceled)
                writer.WriteBoolean("canceled", wasCanceled);
            if (nothingPending)
                writer.WriteBoolean("pendingFound", false);
            writer.WriteEndObject();
        });
        return nothingPending
            ? ExternalJson.Switched(operation, result, effectObserved: false)
            : ExternalJson.Success(operation, result, effect);
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
            || !SchedulerAnswered(source)
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

    // Whether the diagnosis read the scheduler's tasks (schedulerRunning:true); without it, its task list is no read.
    private static bool SchedulerAnswered(JsonElement diagnosis) =>
        diagnosis.TryGetProperty("schedulerRunning", out JsonElement running)
        && running.ValueKind == JsonValueKind.True;

    /// <summary>How long a stop or a snooze waits for the App to end the ring it answers.</summary>
    internal static TimeSpan AnswerWait { get; set; } = TimeSpan.FromSeconds(5);

    /// <summary>Snooze's default, as Android's clock (AOSP DeskClock, SettingsDAO: snooze length, default "10").</summary>
    private const int SnoozeMinutes = 10;

    // What rings now in the open App (AlarmRingHandoff); with no App holding this folder, nothing rings, and a ring an
    // App left behind when it ended is cleared.
    private IReadOnlyList<AlarmRingHandoff.Ring> RingingNow()
    {
        IReadOnlyList<AlarmRingHandoff.Ring> ringing = AlarmRingHandoff.Ringing(_alarmRoot);
        if (ringing.Count == 0 || AlarmRingHandoff.AppHolds(_alarmRoot)) return ringing;
        foreach (AlarmRingHandoff.Ring left in ringing) AlarmRingHandoff.End(_alarmRoot, left.TaskName);
        return [];
    }

    private static void WriteRinging(Utf8JsonWriter writer, IReadOnlyList<AlarmRingHandoff.Ring> ringing)
    {
        writer.WriteStartArray("ringingNow");
        foreach (AlarmRingHandoff.Ring ring in ringing) WriteRing(writer, ring);
        writer.WriteEndArray();
    }

    private static void WriteRing(Utf8JsonWriter writer, AlarmRingHandoff.Ring ring)
    {
        writer.WriteStartObject();
        writer.WriteString("id", ring.Id);
        writer.WriteString("kind", ring.Kind);
        if (ring.Title is not null) writer.WriteString("title", ring.Title);
        writer.WriteString("clock", ring.Clock);
        writer.WriteEndObject();
    }

    // ALR1 (owner, 2026-11-08: «a las 3 me dice, tienes tanto, yo le digo, Baxi, perfecto… lo mismo en la alarma»; and
    // «Baxi, gracias… Baxi para la alarma, tipos como funcionan de Alexa»): the alarm or reminder ringing now in the open
    // App is answered with the same operation that set it, as Google's assistant stops or snoozes a ringing alarm by
    // voice («Stop», «Snooze for 10 minutes»: Google Nest Help, «Set and manage alarms») and Alexa a reminder («Snooze
    // reminder for 10 minutes», «Dismiss reminder»: Amazon, «Get Reminder Notifications From Alexa»). The model names it
    // by the id its turn note shows (with no id, every one ringing: ALR3 below); the card's buttons call it the same way.
    // stop ends this ring (a daily or hourly one rings again next time); snooze sets a one-time one of the same kind and
    // title inMinutes from now (10 by default) and then ends this ring. The receipt is the App's ring read back gone.
    // ALR3 (F9 of VIVO1: with a reminder and an alarm ringing, «Baxy, gracias» left both ringing): with no id, stop or
    // snooze answers every one ringing now (of kind, and at that local clock, HH:mm as cancel's, when they are given),
    // as a smart speaker's «stop» ends what rings; the receipt says each one.
    // ALR5 (B4: asked to be reminded of the one ringing at a time of day, 9 held-out phrases, the model did it in none
    // of 27 samples: 15 snoozed it ten or fifteen minutes, 7 set another and left this one ringing, 4 wrote a cancel
    // with that time and 1 stopped it): snooze takes when it rings again, inMinutes or at, a local clock time (the next
    // time the clock shows it), so the model does no arithmetic with the time; a reminder of Outlook is snoozed for «a
    // few minutes, hours, or even days» (Microsoft Support, «Turn off or postpone a reminder») and one of Apple's
    // Reminders is put off to a later time («Manage notifications from Reminders on Mac»). No source, own measurement:
    // a date and time is taken only when it is that next time, since of 6 the model wrote for «mañana…» 3 were today's
    // date, already past, and 2 the day after tomorrow's, told «mañana». With stop, at still names which one (ALR3).
    private async ValueTask<ExternalCapabilityReceipt> AnswerRingAsync(
        string operation,
        string action,
        JsonElement arguments,
        string? namedKind,
        CancellationToken cancellationToken)
    {
        string? id = OptionalString(arguments, "id");
        if (id is null && Present(arguments, "id"))
            return ExternalJson.FailureBeforeEffect(operation, "notification_ring_id_invalid");
        string? at = OptionalString(arguments, "at");
        int hour = -1, minute = -1;
        if (action == "stop" && at is not null && !TryLocalClock(at, out hour, out minute))
            return ExternalJson.FailureBeforeEffect(operation, "notification_clock_selector_invalid");
        int minutes = SnoozeMinutes;
        if (action == "snooze" && Present(arguments, "inMinutes")
            && (arguments.GetProperty("inMinutes").ValueKind != JsonValueKind.Number
                || !arguments.GetProperty("inMinutes").TryGetInt32(out minutes) || minutes is < 1 or > 1_440))
            return ExternalJson.FailureBeforeEffect(operation, "notification_snooze_invalid");
        IReadOnlyList<AlarmRingHandoff.Ring> ringing = RingingNow();
        // An at that is the clock of one ringing (the one of id, or with no id one of the kind) still names that one, as
        // before ALR5 («la de las 7» is not «mañana a las 7»: taken as when, a wake-up alarm would be silent until the next
        // day). ALR5's blind review: «pospón la alarma de las 7» written with its id and at 07:00 moved it to tomorrow.
        bool OfClock(AlarmRingHandoff.Ring ring) =>
            TryLocalClock(ring.Clock, out int h, out int m) && h == hour && m == minute;
        bool names = action == "stop" ? at is not null
            : at is not null && TryLocalClock(at, out hour, out minute)
                && ringing.Any(ring => (id is null
                    ? namedKind is null || ring.Kind == namedKind
                    : string.Equals(ring.Id, id, StringComparison.OrdinalIgnoreCase)) && OfClock(ring));
        // The minutes win over the clock time, as in create (TryDue).
        DateTimeOffset? again = null;
        bool againNextDay = false;
        if (action == "snooze" && at is not null && !names && !Present(arguments, "inMinutes"))
        {
            DateTimeOffset now = DateTimeOffset.Now;
            // Nothing is set, it rings on, and the refusal says what rings and how to say when.
            ExternalCapabilityReceipt NotSnoozed(string next) =>
                ExternalJson.FailureBeforeEffect(operation, "notification_snooze_invalid") with
                {
                    Result = ExternalJson.Create(writer =>
                    {
                        writer.WriteStartObject(); writer.WriteNumber("version", 1);
                        WriteRinging(writer, ringing);
                        writer.WriteString("next", "nothing was snoozed: " + next);
                        writer.WriteEndObject();
                    }),
                };
            if (!TryDue(default, at, now, out DateTimeOffset due))
            {
                return ringing.Count == 0
                    ? ExternalJson.FailureBeforeEffect(operation, "notification_snooze_invalid")
                    : NotSnoozed("at is not a local clock time (HH:mm, the next time the clock shows it); say when "
                        + "with at or with inMinutes");
            }

            string clock = due.ToLocalTime().ToString("HH:mm", System.Globalization.CultureInfo.InvariantCulture);
            _ = TryDue(default, clock, now, out DateTimeOffset next, out bool nextDay);
            if (ringing.Count > 0 && LocalMinute(due) != LocalMinute(next))
            {
                // A date and time that is not the next time the clock shows that time: the refusal ends with the same
                // call at the clock time alone, as create's does (DuePassed).
                var call = new System.Text.Json.Nodes.JsonObject { ["action"] = "snooze" };
                if (id is not null) call["id"] = id;
                else if (namedKind is not null) call["kind"] = namedKind;
                call["at"] = clock;
                return NotSnoozed($"a snooze reaches the next 24 hours and {LocalMinute(due)} is not in them (it is "
                    + $"{LocalMinute(now)} here); to ring it again at {LocalMinute(next)}, call "
                    + Baxy.Kernel.Operations.WireNames.Call(operation, call));
            }

            (again, againNextDay) = (next, nextDay);
        }

        AlarmRingHandoff.Ring[] candidates = [.. ringing.Where(ring => id is null
            ? (namedKind is null || ring.Kind == namedKind) && (!names || OfClock(ring))
            : string.Equals(ring.Id, id, StringComparison.OrdinalIgnoreCase))];
        if (ringing.Count == 0 && action == "stop")
        {
            // Nothing rings: the silence asked for is already there, and nothing was stopped.
            return ExternalJson.Switched(operation, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteBoolean("stopped", false);
                writer.WriteBoolean("ringingFound", false);
                writer.WriteString("next", "nothing was stopped: no alarm or reminder rings in the BAXY App now (one that "
                    + "rings as a Windows notification is answered on that notification)");
                writer.WriteString("authority", "baxy_app_ring_postread");
                writer.WriteEndObject();
            }), effectObserved: false);
        }

        if (candidates.Length == 0)
        {
            string error = ringing.Count == 0 ? "notification_not_ringing" : "notification_ring_not_found";
            string verb = action == "stop" ? "stopped" : "snoozed";
            return ExternalJson.FailureBeforeEffect(operation, error) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    WriteRinging(writer, ringing);
                    writer.WriteString("next", ringing.Count == 0
                        ? $"nothing was {verb}: no alarm or reminder rings in the BAXY App now (one that rings as a "
                            + "Windows notification is answered on that notification)"
                        : $"nothing was {verb}: id names the one of ringingNow to answer");
                    writer.WriteEndObject();
                }),
            };
        }

        var effectBoundary = new ExternalEffectBoundary();
        var answered = new List<(AlarmRingHandoff.Ring Ring, JsonElement? Snoozed)>();
        ExternalCapabilityReceipt? notSet = null;
        try
        {
            foreach (AlarmRingHandoff.Ring ring in candidates)
            {
                JsonElement? snoozed = null;
                if (action == "snooze")
                {
                    JsonElement same = ExternalJson.Create(writer =>
                    {
                        writer.WriteStartObject();
                        if (ring.Title is not null) writer.WriteString("title", ring.Title);
                        writer.WriteEndObject();
                    });
                    ExternalCapabilityReceipt set = await ScheduleAsync(operation, ring.Kind, same,
                        again ?? DateTimeOffset.Now.AddMinutes(minutes), againNextDay, effectBoundary,
                        cancellationToken).ConfigureAwait(false);
                    // A snooze that set nothing leaves the ring ringing: the person still hears it and can answer again.
                    if (!set.Verified)
                    {
                        notSet = set;
                        break;
                    }

                    snoozed = set.Result;
                }

                effectBoundary.Cross(cancellationToken);
                AlarmRingHandoff.Answer(_alarmRoot, ring.TaskName, action);
                answered.Add((ring, snoozed));
            }

            DateTimeOffset until = DateTimeOffset.UtcNow + AnswerWait;
            while (answered.Any(a => AlarmRingHandoff.IsRinging(_alarmRoot, a.Ring.TaskName))
                   && DateTimeOffset.UtcNow < until)
                await Task.Delay(100, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "notification_ring_answer_unconfirmed");
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return effectBoundary.Failure(operation, "notification_ring_answer_failed");
        }

        if (answered.Count == 0) return notSet!;
        var ended = new Dictionary<string, bool>(StringComparer.Ordinal);
        foreach ((AlarmRingHandoff.Ring ring, _) in answered)
        {
            ended[ring.TaskName] = !AlarmRingHandoff.IsRinging(_alarmRoot, ring.TaskName);
            // Ended by this answer or by its own time meanwhile: no answer is left behind for the task's next ring.
            if (ended[ring.TaskName]) AlarmRingHandoff.End(_alarmRoot, ring.TaskName);
        }

        void WriteAnswer(Utf8JsonWriter writer, AlarmRingHandoff.Ring ring, JsonElement? snoozed, bool done)
        {
            writer.WriteString("id", ring.Id);
            writer.WriteString("kind", ring.Kind);
            if (ring.Title is not null) writer.WriteString("title", ring.Title);
            writer.WriteString("clock", ring.Clock);
            // ALR5: «snoozed» is the new ring set, which is read back before this one is answered; whether this ring
            // was seen to end is «ringing». A snooze the App did not end in time said snoozed:false beside the
            // inMinutes and dueLocal of the ring it had just set.
            writer.WriteBoolean(action == "stop" ? "stopped" : "snoozed",
                action == "stop" ? done : snoozed is { ValueKind: JsonValueKind.Object });
            writer.WriteBoolean("ringing", !done);
            if (snoozed is { ValueKind: JsonValueKind.Object } next)
            {
                // By the minutes, the minutes; by a clock time, the time it was set for (and that it is tomorrow's).
                if (again is null) writer.WriteNumber("inMinutes", minutes);
                foreach (string name in (string[])["dueLocal", "scheduledFor", "nextRunUtc"])
                {
                    if (next.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String)
                        writer.WriteString(name, value.GetString());
                }
                if (next.TryGetProperty("movedToNextDay", out JsonElement moved) && moved.ValueKind == JsonValueKind.True)
                {
                    writer.WriteBoolean("movedToNextDay", true);
                    if (next.TryGetProperty("nowLocal", out JsonElement here) && here.ValueKind == JsonValueKind.String)
                        writer.WriteString("nowLocal", here.GetString());
                }
            }
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            if (candidates.Length == 1)
            {
                WriteAnswer(writer, answered[0].Ring, answered[0].Snoozed, ended[answered[0].Ring.TaskName]);
            }
            else
            {
                // Each one answered, and any a snooze that set nothing left ringing.
                writer.WriteStartArray("rings");
                foreach (AlarmRingHandoff.Ring ring in candidates)
                {
                    writer.WriteStartObject();
                    int index = answered.FindIndex(a => a.Ring.TaskName == ring.TaskName);
                    WriteAnswer(writer, ring, index < 0 ? null : answered[index].Snoozed,
                        index >= 0 && ended[ring.TaskName]);
                    writer.WriteEndObject();
                }

                writer.WriteEndArray();
            }

            writer.WriteString("authority", "baxy_app_ring_postread");
            writer.WriteEndObject();
        });
        // A ring the App did not end in time was answered (the answer waits for it) but is not seen silent; with several,
        // one that did end is an effect seen.
        bool seen = answered.Any(a => a.Snoozed is not null)
            || (candidates.Length > 1 && ended.Values.Any(static done => done));
        return notSet is null && ended.Values.All(static done => done)
            ? ExternalJson.Success(operation, result)
            : ExternalJson.FailureAfterEffect(operation, notSet?.ErrorCode ?? "notification_ring_answer_unconfirmed", seen)
                with { Result = result };
    }
}
