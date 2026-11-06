using System.Buffers;
using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// M119: BAXY's alarms and reminders, answered in-process through the Task Scheduler COM API. Each mode answers one
/// JSON line (exit 0), or exit 1 with the cause when it throws. When the scheduler fails before anything changed the
/// line says so (task_scheduler_unavailable, nothing crossed); once a task was registered or a deletion was attempted,
/// a failure is an exit 1 and never retried.
/// </summary>
internal sealed class NativeScheduledNotificationBackend(ITaskSchedulerHost host) : IScheduledNotificationBackend
{
    private const int AcceptableNeverRan = 267011;
    private const int ShownFiredReceipts = 10;
    private static readonly string[] StateNames = ["Unknown", "Disabled", "Queued", "Ready", "Running"];

    public async ValueTask<ExternalProcessResult> RunAsync(
        ScheduledNotificationRequest request,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return await Task.Run(() => Execute(request), cancellationToken).ConfigureAwait(false);
    }

    private ExternalProcessResult Execute(ScheduledNotificationRequest request)
    {
        var effect = new EffectState();
        try
        {
            string line = request.Mode switch
            {
                "diagnose" => Diagnose(request),
                "resolve-at" => ResolveAt(request),
                "schedule" or "schedule-recurring" => Schedule(request, effect),
                "cancel-exact" => CancelExact(request, effect),
                _ => throw new ScheduleFailure("invalid_mode"),
            };
            return new ExternalProcessResult(0, line + Environment.NewLine, string.Empty);
        }
        catch (TaskSchedulerHostException exception) when (!effect.Committed)
        {
            string line = Json(writer =>
            {
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", false);
                writer.WriteBoolean("effectObserved", false);
                writer.WriteBoolean("effectBoundaryCrossed", false);
                writer.WriteString("error", "task_scheduler_unavailable");
                writer.WriteString("detail", Describe(exception));
            });
            return new ExternalProcessResult(0, line + Environment.NewLine, string.Empty);
        }
        // Renew al máximo (w8): a schedule or a cancel that failed before its Register or Delete (a ring script missing,
        // a due time that passed meanwhile, a task with no next run or gone while listed) changed nothing, and came back
        // as a bare process failure the adapter reads as «may have changed». It says so, with its cause.
        catch (Exception exception) when (!effect.Committed && request.Mode is "schedule" or "schedule-recurring"
            or "cancel-exact")
        {
            string line = Json(writer =>
            {
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", false);
                writer.WriteBoolean("effectObserved", false);
                writer.WriteBoolean("effectBoundaryCrossed", false);
                writer.WriteString("error", exception is ScheduleFailure ? exception.Message : "failed_before_effect");
                writer.WriteString("detail", Describe(exception));
            });
            return new ExternalProcessResult(0, line + Environment.NewLine, string.Empty);
        }
        catch (Exception exception)
        {
            return new ExternalProcessResult(1, string.Empty, Describe(exception));
        }
    }

    // Why a notification did not ring: whether the scheduler answers, whether Windows shows notifications, each
    // task's last result, and what each ring's own receipt (.fired) wrote: when it rang, whether its notification was
    // read back from Windows' history and which sound played.
    private string Diagnose(ScheduledNotificationRequest request)
    {
        // Auditoría final (regla 3): a setting or a history that was not read is said as not read: it is neither
        // «enabled», nor «not shown», nor counted toward «healthy».
        int? toastSetting = host.ToastsEnabledSetting();
        bool? toastEnabled = toastSetting is null ? null : toastSetting.Value != 0;
        List<FiredReceipt>? read = FiredReceipts(request.AlarmRoot);
        List<FiredReceipt> fired = read ?? [];
        int firedNotShown = fired.Count(receipt => receipt.NotificationShown == false);
        int firedShownUnread = fired.Count(receipt => receipt.NotificationShown is null);
        IReadOnlyList<ScheduledTaskSnapshot>? observed;
        try
        {
            using ITaskSchedulerSession session = host.Open();
            observed = session.Read("BAXY-");
        }
        catch (TaskSchedulerHostException)
        {
            // A Task Scheduler that does not answer is not running BAXY's notifications, whatever its service says,
            // and none of its tasks was read: the line gives no task count and no task list.
            observed = null;
        }
        int issueCount = (observed?.Count(task => !Acceptable(task.LastTaskResult)) ?? 1) + firedNotShown
            + (toastEnabled == false ? 1 : 0);
        bool allRead = toastEnabled is not null && read is not null && firedShownUnread == 0;
        return Json(writer =>
        {
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", true);
            writer.WriteBoolean("schedulerRunning", observed is not null);
            if (toastEnabled is bool enabled) writer.WriteBoolean("toastEnabled", enabled);
            if (issueCount > 0 || allRead) writer.WriteBoolean("healthy", issueCount == 0);
            if (observed is not null) writer.WriteNumber("taskCount", observed.Count);
            if (read is not null)
            {
                writer.WriteNumber("firedReceiptCount", fired.Count);
                writer.WriteNumber("firedNotShownCount", firedNotShown);
            }
            if (firedShownUnread > 0) writer.WriteNumber("firedShownUnreadCount", firedShownUnread);
            if (issueCount > 0 || allRead) writer.WriteNumber("issueCount", issueCount);
            if (read is not null)
            {
                writer.WriteStartArray("firedReceipts");
                foreach (FiredReceipt receipt in fired.Take(ShownFiredReceipts))
                {
                    writer.WriteStartObject();
                    writer.WriteString("taskName", receipt.TaskName);
                    if (receipt.RangUtc is not null) writer.WriteString("rangUtc", receipt.RangUtc);
                    else writer.WriteNull("rangUtc");
                    if (receipt.NotificationShown is bool shown) writer.WriteBoolean("notificationShown", shown);
                    else writer.WriteNull("notificationShown");
                    if (receipt.Sound is not null) writer.WriteString("sound", receipt.Sound);
                    else writer.WriteNull("sound");
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
            }
            if (observed is not null)
            {
                writer.WriteStartArray("tasks");
                foreach (ScheduledTaskSnapshot task in observed)
                {
                    writer.WriteStartObject();
                    writer.WriteString("taskName", task.Name);
                    writer.WriteString("state", StateName(task.State));
                    WriteUtcOrNull(writer, "nextRunUtc", task.NextRunLocal);
                    WriteUtcOrNull(writer, "lastRunUtc", task.LastRunLocal);
                    writer.WriteNumber("lastTaskResult", (long)(uint)task.LastTaskResult);
                    writer.WriteBoolean("resultAcceptable", Acceptable(task.LastTaskResult));
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
            }
            writer.WriteString("authority", "windows_task_scheduler_notification_diagnostics_postread");
        });
    }

    private string ResolveAt(ScheduledNotificationRequest request)
    {
        int hour = request.Hour;
        int minute = request.Minute;
        // The clock is a 24-hour local time (schedule's «at»): it selects that exact hour and minute.
        if (hour is < 0 or > 23 || minute is < 0 or > 59)
            throw new ScheduleFailure("invalid_clock_selector");
        string prefix = Is(request.Kind, "alarm") ? "BAXY-Alarm-" : "BAXY-Reminder-";
        DateTimeOffset now = DateTimeOffset.Now;
        List<(string TaskName, string NextRunUtc)> matches = [];
        using ITaskSchedulerSession session = host.Open();
        foreach (string name in session.TaskNames().Where(name => Like(name, prefix)))
        {
            if (!IsOwn(request.AlarmRoot, name)) continue;
            ScheduledTaskSnapshot info = session.Find(name) ?? throw new ScheduleFailure("task_vanished");
            if (info.NextRunLocal is not DateTime nextLocal) continue;
            DateTimeOffset next = new(nextLocal);
            if (next <= now) continue;
            if (next.Hour == hour && next.Minute == minute)
                matches.Add((info.Name, Utc(next)));
        }
        return Json(writer =>
        {
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", matches.Count == 1);
            writer.WriteBoolean("effectObserved", false);
            writer.WriteBoolean("effectBoundaryCrossed", false);
            writer.WriteNumber("matchCount", matches.Count);
            if (matches.Count == 1)
            {
                writer.WriteString("taskName", matches[0].TaskName);
                writer.WriteString("nextRunUtc", matches[0].NextRunUtc);
            }
            writer.WriteString("authority", "windows_task_scheduler_clock_resolution_snapshot");
        });
    }

    private string Schedule(ScheduledNotificationRequest request, EffectState effect)
    {
        string taskName = request.TaskName ?? string.Empty;
        if (!Regex.IsMatch(taskName, "^BAXY-(Alarm|Reminder)-[0-9a-f]{32}$", ScriptRegex, RegexTimeout))
            throw new ScheduleFailure("invalid_task_name");
        if (!File.Exists(request.RingScriptPath))
            throw new ScheduleFailure("ring_script_missing");
        DateTimeOffset due = DateTimeOffset.Parse(
            request.DueUtc ?? string.Empty, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind);
        DateTime dueLocal = due.LocalDateTime;
        if (due <= DateTimeOffset.UtcNow.AddSeconds(5))
            throw new ScheduleFailure("due_time_not_future");
        bool recurring = request.Mode == "schedule-recurring";
        string? trigger = recurring && Is(request.Recurrence, "daily") ? "daily"
            : recurring && Is(request.Recurrence, "hourly") ? "hourly"
            : null;
        string xml = ScheduledNotificationTaskXml.Build(
            request.Kind, request.RingScriptPath!, due, trigger, host.CurrentUserSid());
        using ITaskSchedulerSession session = host.Open();
        // Create or update this name. A Register that fails changed nothing; after it succeeds the effect is
        // committed.
        session.Register(taskName, xml);
        effect.Committed = true;
        ScheduledTaskSnapshot task = session.Find(taskName) ?? throw new ScheduleFailure("task_missing_after_register");
        if (task.NextRunLocal is not DateTime nextLocal)
            throw new ScheduleFailure("next_run_missing");
        double deltaSeconds = Math.Abs((nextLocal - dueLocal).TotalSeconds);
        return Json(writer =>
        {
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok",
                string.Equals(task.Name, taskName, StringComparison.OrdinalIgnoreCase) && deltaSeconds <= 2);
            writer.WriteBoolean("effectObserved", true);
            writer.WriteString("taskName", task.Name);
            writer.WriteString("state", StateName(task.State));
            writer.WriteString("nextRunUtc", Utc(new DateTimeOffset(nextLocal)));
            writer.WriteString("recurrence", recurring ? request.Recurrence ?? string.Empty : "none");
            writer.WriteString("authority", "windows_task_scheduler_postread");
        });
    }

    private string CancelExact(ScheduledNotificationRequest request, EffectState effect)
    {
        string expected = Is(request.Kind, "alarm")
            ? "^BAXY-Alarm-[0-9a-f]{32}$"
            : "^BAXY-Reminder-[0-9a-f]{32}$";
        string taskName = request.TaskName ?? string.Empty;
        if (!Regex.IsMatch(taskName, expected, ScriptRegex, RegexTimeout))
            throw new ScheduleFailure("invalid_task_name");
        DateTimeOffset expectedDue = DateTimeOffset.Parse(
            request.DueUtc ?? string.Empty, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind);
        using ITaskSchedulerSession session = host.Open();
        ScheduledTaskSnapshot? candidate = session.Find(taskName);
        if (candidate is null)
        {
            return Json(writer =>
            {
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", false);
                writer.WriteBoolean("effectObserved", false);
                writer.WriteBoolean("effectBoundaryCrossed", false);
                writer.WriteString("error", "task_missing_before_effect");
            });
        }
        if (candidate.NextRunLocal is not DateTime nextLocal)
            throw new ScheduleFailure("next_run_missing");
        DateTimeOffset observedDue = new DateTimeOffset(nextLocal).ToUniversalTime();
        if (Math.Abs((observedDue - expectedDue.ToUniversalTime()).TotalSeconds) > 2)
        {
            return Json(writer =>
            {
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", false);
                writer.WriteBoolean("effectObserved", false);
                writer.WriteBoolean("effectBoundaryCrossed", false);
                writer.WriteString("error", "task_changed_before_effect");
            });
        }
        effect.Committed = true;
        session.Delete(taskName);
        bool stillPresent = session.Find(taskName) is not null;
        return Json(writer =>
        {
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", !stillPresent);
            writer.WriteBoolean("effectObserved", true);
            writer.WriteBoolean("effectBoundaryCrossed", true);
            writer.WriteBoolean("canceled", !stillPresent);
            writer.WriteString("taskName", taskName);
            writer.WriteString("nextRunUtc", Utc(observedDue));
            writer.WriteString("authority", "windows_task_scheduler_exact_identity_absence_postread");
        });
    }

    private const RegexOptions ScriptRegex = RegexOptions.IgnoreCase | RegexOptions.CultureInvariant;
    private static readonly TimeSpan RegexTimeout = TimeSpan.FromMilliseconds(100);

    private static bool Like(string name, string prefix) =>
        name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);

    private static bool Is(string? value, string expected) =>
        string.Equals(value, expected, StringComparison.OrdinalIgnoreCase);

    private static bool IsOwn(string? alarmRoot, string name) =>
        string.IsNullOrEmpty(alarmRoot) || File.Exists(Path.Combine(alarmRoot, name + ".ps1"));

    // What a ring wrote in its receipt (WindowsScheduledNotificationAdapter.WriteRingScript): null where the receipt
    // could not be read or does not say it.
    private sealed record FiredReceipt(string TaskName, string? RangUtc, bool? NotificationShown, string? Sound);

    // The rings of this data root, the latest first; an unreadable folder has none.
    // The receipts of the rings, newest first: none when the folder was never made (nothing scheduled yet), null when
    // the folder could not be listed (auditoría final, regla 3: not «no rings»).
    private static List<FiredReceipt>? FiredReceipts(string? alarmRoot)
    {
        if (string.IsNullOrEmpty(alarmRoot) || !Directory.Exists(alarmRoot)) return [];
        try
        {
            return Directory.EnumerateFiles(alarmRoot, "*.fired")
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .Select(ReadFiredReceipt)
                .ToList();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    private static FiredReceipt ReadFiredReceipt(string path)
    {
        string taskName = Path.GetFileNameWithoutExtension(path);
        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object) return new FiredReceipt(taskName, null, null, null);
            return new FiredReceipt(
                taskName,
                root.TryGetProperty("rangUtc", out JsonElement rang) && rang.ValueKind == JsonValueKind.String
                    ? rang.GetString() : null,
                root.TryGetProperty("notificationShown", out JsonElement shown)
                    && shown.ValueKind is JsonValueKind.True or JsonValueKind.False ? shown.GetBoolean() : null,
                root.TryGetProperty("sound", out JsonElement sound) && sound.ValueKind == JsonValueKind.String
                    ? sound.GetString() : null);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return new FiredReceipt(taskName, null, null, null);
        }
    }

    private static bool Acceptable(int lastTaskResult) =>
        lastTaskResult is 0 or AcceptableNeverRan;

    private static string StateName(int state) =>
        state >= 0 && state < StateNames.Length ? StateNames[state] : state.ToString(CultureInfo.InvariantCulture);

    private static string Utc(DateTimeOffset value) =>
        value.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);

    private static void WriteUtcOrNull(Utf8JsonWriter writer, string name, DateTime? local)
    {
        if (local is DateTime value) writer.WriteString(name, Utc(new DateTimeOffset(value)));
        else writer.WriteNull(name);
    }

    private static string Describe(Exception exception) =>
        exception.InnerException is null
            ? exception.GetType().Name + ":" + exception.Message
            : exception.GetType().Name + ":" + exception.Message + "<-"
                + exception.InnerException.GetType().Name + ":" + exception.InnerException.Message;

    private static string Json(Action<Utf8JsonWriter> writeProperties)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(
            buffer, new JsonWriterOptions { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping }))
        {
            writer.WriteStartObject();
            writeProperties(writer);
            writer.WriteEndObject();
        }
        return Encoding.UTF8.GetString(buffer.WrittenSpan);
    }

    private sealed class EffectState
    {
        internal bool Committed { get; set; }
    }

    private sealed class ScheduleFailure(string message) : Exception(message);
}

/// <summary>
/// The task of one notification, element by element as Task Scheduler exports it: the ring script run by
/// powershell.exe at the due time (once, daily or hourly), at most 10 minutes, with the user's interactive token. It
/// asks to start on battery and not to stop when the PC goes on battery, to start as soon as it can after a start it
/// missed (StartWhenAvailable), and to wake the PC to run (WakeToRun). Windows honors WakeToRun only when the power
/// plan allows wake timers, so a task set says nothing about whether a sleeping PC rings.
/// </summary>
internal static class ScheduledNotificationTaskXml
{
    private const string Namespace = "http://schemas.microsoft.com/windows/2004/02/mit/task";

    /// <param name="trigger">null (once), "daily" or "hourly".</param>
    internal static string Build(
        string kind, string ringScriptPath, DateTimeOffset due, string? trigger, string userSid)
    {
        // The trigger keeps the local wall time to the second, with its offset.
        DateTimeOffset local = due.ToLocalTime();
        string startBoundary = local.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture)
            + local.ToString("zzz", CultureInfo.InvariantCulture);
        string quotedScript = "\"" + ringScriptPath.Replace("\"", "\"\"", StringComparison.Ordinal) + "\"";
        var text = new StringBuilder();
        using (XmlWriter writer = XmlWriter.Create(text, new XmlWriterSettings
        {
            OmitXmlDeclaration = true,
            Indent = true,
            IndentChars = "  ",
        }))
        {
            writer.WriteStartElement("Task", Namespace);
            writer.WriteAttributeString("version", "1.3");
            writer.WriteStartElement("RegistrationInfo", Namespace);
            writer.WriteElementString("Description", Namespace, "BAXY verified " + kind);
            writer.WriteEndElement();
            writer.WriteStartElement("Principals", Namespace);
            writer.WriteStartElement("Principal", Namespace);
            writer.WriteAttributeString("id", "Author");
            writer.WriteElementString("UserId", Namespace, userSid);
            writer.WriteElementString("LogonType", Namespace, "InteractiveToken");
            writer.WriteEndElement();
            writer.WriteEndElement();
            writer.WriteStartElement("Settings", Namespace);
            writer.WriteElementString("DisallowStartIfOnBatteries", Namespace, "false");
            writer.WriteElementString("StopIfGoingOnBatteries", Namespace, "false");
            writer.WriteElementString("ExecutionTimeLimit", Namespace, "PT10M");
            writer.WriteElementString("MultipleInstancesPolicy", Namespace, "IgnoreNew");
            writer.WriteElementString("StartWhenAvailable", Namespace, "true");
            writer.WriteElementString("WakeToRun", Namespace, "true");
            writer.WriteStartElement("IdleSettings", Namespace);
            writer.WriteElementString("Duration", Namespace, "PT10M");
            writer.WriteElementString("WaitTimeout", Namespace, "PT1H");
            writer.WriteElementString("StopOnIdleEnd", Namespace, "true");
            writer.WriteElementString("RestartOnIdle", Namespace, "false");
            writer.WriteEndElement();
            writer.WriteElementString("UseUnifiedSchedulingEngine", Namespace, "true");
            writer.WriteEndElement();
            writer.WriteStartElement("Triggers", Namespace);
            writer.WriteStartElement(trigger == "daily" ? "CalendarTrigger" : "TimeTrigger", Namespace);
            writer.WriteElementString("StartBoundary", Namespace, startBoundary);
            if (trigger == "hourly")
            {
                writer.WriteStartElement("Repetition", Namespace);
                writer.WriteElementString("Interval", Namespace, "PT1H");
                writer.WriteElementString("Duration", Namespace, "P3650D");
                writer.WriteElementString("StopAtDurationEnd", Namespace, "true");
                writer.WriteEndElement();
            }
            if (trigger == "daily")
            {
                writer.WriteStartElement("ScheduleByDay", Namespace);
                writer.WriteElementString("DaysInterval", Namespace, "1");
                writer.WriteEndElement();
            }
            writer.WriteEndElement();
            writer.WriteEndElement();
            writer.WriteStartElement("Actions", Namespace);
            writer.WriteAttributeString("Context", "Author");
            writer.WriteStartElement("Exec", Namespace);
            writer.WriteElementString("Command", Namespace, SystemExecutable.PowerShellInTask);
            writer.WriteElementString("Arguments", Namespace,
                "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File " + quotedScript);
            writer.WriteEndElement();
            writer.WriteEndElement();
            writer.WriteEndElement();
        }
        return text.ToString();
    }
}
