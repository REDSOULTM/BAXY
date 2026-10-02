using System.Buffers;
using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// M119: WindowsScheduledNotification.ps1 answered in-process through the Task Scheduler COM API.
/// Every mode prints the JSON line the script prints and «exits 1» where the script throws, so the
/// adapter reads both alike. When the scheduler itself fails before anything changed, the call goes
/// to the script (and a diagnostic line is written); once a task was registered or a deletion was
/// attempted, a failure is reported as the script's would be and never retried.
/// </summary>
internal sealed class NativeScheduledNotificationBackend(
    ITaskSchedulerHost host,
    IScheduledNotificationBackend fallback,
    string fallbackDiagnosticsPath) : IScheduledNotificationBackend
{
    private const int AcceptableNeverRan = 267011;
    private static readonly string[] StateNames = ["Unknown", "Disabled", "Queued", "Ready", "Running"];

    public async ValueTask<ExternalProcessResult> RunAsync(
        ScheduledNotificationRequest request,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Outcome outcome = await Task.Run(() => Execute(request), cancellationToken).ConfigureAwait(false);
        if (outcome.Result is not null) return outcome.Result;
        WriteFallbackDiagnostic(request.Mode, outcome.FallbackReason!);
        return await fallback.RunAsync(request, cancellationToken).ConfigureAwait(false);
    }

    private Outcome Execute(ScheduledNotificationRequest request)
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
                "cancel" => CancelLatest(request, effect),
                _ => throw new ScriptFailure("invalid_mode"),
            };
            return new Outcome(new ExternalProcessResult(0, line + Environment.NewLine, string.Empty), null);
        }
        catch (TaskSchedulerHostException exception) when (!effect.Committed)
        {
            return new Outcome(null, Describe(exception));
        }
        catch (Exception exception)
        {
            // The script runs with $ErrorActionPreference = 'Stop': whatever throws ends it with exit 1.
            return new Outcome(new ExternalProcessResult(1, string.Empty, Describe(exception)), null);
        }
    }

    private string Diagnose(ScheduledNotificationRequest request)
    {
        int? toastSetting = host.ToastsEnabledSetting();
        using ITaskSchedulerSession session = host.Open();
        // A connected Task Scheduler is a running Schedule service; when it is not, Open fails
        // and the script answers (Get-Service reads the stopped state).
        const bool schedulerRunning = true;
        IReadOnlyList<ScheduledTaskSnapshot> observed = session.Read("BAXY-");
        int issueCount = observed.Count(task => !Acceptable(task.LastTaskResult));
        bool toastEnabled = toastSetting is null || toastSetting.Value != 0;
        int receipts = FiredReceiptCount(request.AlarmRoot);
        if (!toastEnabled) issueCount++;
        return Json(writer =>
        {
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", true);
            writer.WriteBoolean("schedulerRunning", schedulerRunning);
            writer.WriteBoolean("toastEnabled", toastEnabled);
            writer.WriteBoolean("healthy", issueCount == 0);
            writer.WriteNumber("taskCount", observed.Count);
            writer.WriteNumber("firedReceiptCount", receipts);
            writer.WriteNumber("issueCount", issueCount);
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
            writer.WriteString("authority", "windows_task_scheduler_notification_diagnostics_postread");
        });
    }

    private string ResolveAt(ScheduledNotificationRequest request)
    {
        int hour = request.Hour;
        int minute = request.Minute;
        string? period = string.IsNullOrEmpty(request.Period) ? null : request.Period;
        if (hour is < 0 or > 23 || minute is < 0 or > 59 || period is not null && hour is < 1 or > 12)
            throw new ScriptFailure("invalid_clock_selector");
        int targetHour = hour;
        if (Is(period, "am")) targetHour = hour % 12;
        else if (Is(period, "pm")) targetHour = hour % 12 + 12;
        string prefix = Is(request.Kind, "alarm") ? "BAXY-Alarm-" : "BAXY-Reminder-";
        DateTimeOffset now = DateTimeOffset.Now;
        List<(string TaskName, string NextRunUtc)> matches = [];
        using ITaskSchedulerSession session = host.Open();
        foreach (string name in session.TaskNames().Where(name => Like(name, prefix)))
        {
            if (!IsOwn(request.AlarmRoot, name)) continue;
            ScheduledTaskSnapshot info = session.Find(name) ?? throw new ScriptFailure("task_vanished");
            if (info.NextRunLocal is not DateTime nextLocal) continue;
            DateTimeOffset next = new(nextLocal);
            if (next <= now) continue;
            bool hourMatches = period is not null
                ? next.Hour == targetHour
                : hour <= 12 ? next.Hour % 12 == hour % 12 : next.Hour == hour;
            if (hourMatches && next.Minute == minute)
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
            throw new ScriptFailure("invalid_task_name");
        if (!File.Exists(request.RingScriptPath))
            throw new ScriptFailure("ring_script_missing");
        DateTimeOffset due = DateTimeOffset.Parse(
            request.DueUtc ?? string.Empty, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind);
        DateTime dueLocal = due.LocalDateTime;
        if (due <= DateTimeOffset.UtcNow.AddSeconds(5))
            throw new ScriptFailure("due_time_not_future");
        bool recurring = request.Mode == "schedule-recurring";
        string? trigger = recurring && Is(request.Recurrence, "daily") ? "daily"
            : recurring && Is(request.Recurrence, "hourly") ? "hourly"
            : null;
        string xml = ScheduledNotificationTaskXml.Build(
            request.Kind, request.RingScriptPath!, due, trigger, host.CurrentUserSid());
        using ITaskSchedulerSession session = host.Open();
        // Register-ScheduledTask -Force: create or update this name. A Register that fails changed
        // nothing, so the script may still be asked; after it succeeds the effect is committed.
        session.Register(taskName, xml);
        effect.Committed = true;
        ScheduledTaskSnapshot task = session.Find(taskName) ?? throw new ScriptFailure("task_missing_after_register");
        if (task.NextRunLocal is not DateTime nextLocal)
            throw new ScriptFailure("next_run_missing");
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
            throw new ScriptFailure("invalid_task_name");
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
            throw new ScriptFailure("next_run_missing");
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

    private string CancelLatest(ScheduledNotificationRequest request, EffectState effect)
    {
        string prefix = Is(request.Kind, "alarm") ? "BAXY-Alarm-" : "BAXY-Reminder-";
        DateTimeOffset now = DateTimeOffset.Now;
        using ITaskSchedulerSession session = host.Open();
        // M80 (DEV-D v3m D-w18-t5): the latest is the pending notification of this BAXY whose ring
        // script was written last (it is written just before the task is registered).
        string? selected = session.TaskNames()
            .Where(name => Like(name, prefix) && IsOwn(request.AlarmRoot, name))
            .Where(name =>
            {
                ScheduledTaskSnapshot pending = session.Find(name) ?? throw new ScriptFailure("task_vanished");
                return pending.NextRunLocal is DateTime next && new DateTimeOffset(next) > now;
            })
            .OrderByDescending(name => string.IsNullOrEmpty(request.AlarmRoot)
                ? DateTime.MinValue
                : File.GetLastWriteTimeUtc(Path.Combine(request.AlarmRoot, name + ".ps1")))
            .FirstOrDefault();
        if (selected is null)
        {
            return Json(writer =>
            {
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", true);
                writer.WriteBoolean("effectObserved", false);
                writer.WriteBoolean("canceled", false);
                writer.WriteString("authority", "windows_task_scheduler_absence_postread");
            });
        }
        effect.Committed = true;
        session.Delete(selected);
        bool stillPresent = session.Find(selected) is not null;
        return Json(writer =>
        {
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", !stillPresent);
            writer.WriteBoolean("effectObserved", true);
            writer.WriteBoolean("canceled", !stillPresent);
            writer.WriteString("taskName", selected);
            writer.WriteString("authority", "windows_task_scheduler_absence_postread");
        });
    }

    private void WriteFallbackDiagnostic(string mode, string reason)
    {
        try
        {
            string line = Json(writer =>
            {
                writer.WriteString("schema", "baxy.notification-scheduler-fallback.v1");
                writer.WriteString("utc", DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture));
                writer.WriteString("mode", mode);
                writer.WriteString("reason", reason);
            });
            string? directory = Path.GetDirectoryName(fallbackDiagnosticsPath);
            if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
            File.AppendAllText(fallbackDiagnosticsPath, line + Environment.NewLine, new UTF8Encoding(false));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or ArgumentException or NotSupportedException)
        {
            // A diagnostic that cannot be written does not change the result.
        }
    }

    private const RegexOptions ScriptRegex = RegexOptions.IgnoreCase | RegexOptions.CultureInvariant;
    private static readonly TimeSpan RegexTimeout = TimeSpan.FromMilliseconds(100);

    // PowerShell -like, -eq and -match compare case-insensitively.
    private static bool Like(string name, string prefix) =>
        name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);

    private static bool Is(string? value, string expected) =>
        string.Equals(value, expected, StringComparison.OrdinalIgnoreCase);

    private static bool IsOwn(string? alarmRoot, string name) =>
        string.IsNullOrEmpty(alarmRoot) || File.Exists(Path.Combine(alarmRoot, name + ".ps1"));

    // Get-ChildItem -Filter '*.fired' -File -ErrorAction SilentlyContinue: an unreadable folder counts none.
    private static int FiredReceiptCount(string? alarmRoot)
    {
        if (string.IsNullOrEmpty(alarmRoot) || !Directory.Exists(alarmRoot)) return 0;
        try
        {
            return Directory.EnumerateFiles(alarmRoot, "*.fired").Count();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return 0;
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

    private sealed record Outcome(ExternalProcessResult? Result, string? FallbackReason);

    private sealed class EffectState
    {
        internal bool Committed { get; set; }
    }

    private sealed class ScriptFailure(string message) : Exception(message);
}

/// <summary>
/// The task Register-ScheduledTask stores for WindowsScheduledNotification.ps1 (New-ScheduledTaskAction,
/// New-ScheduledTaskTrigger -Once/-Daily/-RepetitionInterval, New-ScheduledTaskSettingsSet
/// -StartWhenAvailable -ExecutionTimeLimit 10 min, the user's interactive token), element by element
/// as Task Scheduler exports it.
/// </summary>
internal static class ScheduledNotificationTaskXml
{
    private const string Namespace = "http://schemas.microsoft.com/windows/2004/02/mit/task";

    /// <param name="trigger">null (once), "daily" or "hourly".</param>
    internal static string Build(
        string kind, string ringScriptPath, DateTimeOffset due, string? trigger, string userSid)
    {
        // New-ScheduledTaskTrigger -At keeps the local wall time to the second, with its offset.
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
            writer.WriteElementString("DisallowStartIfOnBatteries", Namespace, "true");
            writer.WriteElementString("StopIfGoingOnBatteries", Namespace, "true");
            writer.WriteElementString("ExecutionTimeLimit", Namespace, "PT10M");
            writer.WriteElementString("MultipleInstancesPolicy", Namespace, "IgnoreNew");
            writer.WriteElementString("StartWhenAvailable", Namespace, "true");
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
            writer.WriteElementString("Command", Namespace, "powershell.exe");
            writer.WriteElementString("Arguments", Namespace,
                "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File " + quotedScript);
            writer.WriteEndElement();
            writer.WriteEndElement();
            writer.WriteEndElement();
        }
        return text.ToString();
    }
}
