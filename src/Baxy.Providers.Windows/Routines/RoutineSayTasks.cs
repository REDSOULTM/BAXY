using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Routines;

/// <summary>What the Task Scheduler answered about a routine's task: whether it is set (or gone, for a removal), the
/// next time it runs as the scheduler itself reads it back, and the cause when it is not.</summary>
public sealed record RoutineSayTask(bool Ok, DateTimeOffset? NextRun, string? Error);

/// <summary>
/// RUT4 (owner, 2026-11-10: «todos los días a las 10 dime buen día… una vez y listo»; documentacion/RUTINAS.md §4): the
/// Task Scheduler task of a routine that says a text at a time. It is the machinery of BAXY's alarms and reminders
/// (<see cref="ScheduledRingScript"/>, <see cref="ScheduledNotificationTaskXml"/>, <see cref="ScheduledRingTasks"/>)
/// with a third kind, <c>BAXY-Say-…</c>: at its time the script hands the text to the open App, which says it once with
/// BAXY's voice and rings nothing (AlarmRinger); with BAXY closed, Windows shows it once as an ordinary notification.
/// The task's name comes from the data root and the routine's id, so setting it again replaces it and two data roots
/// never share one. Once, every day (Task Scheduler schema, ScheduleByDay) or on days of the week (ScheduleByWeek);
/// it never wakes a sleeping PC: it runs when the PC is next on (StartWhenAvailable).
/// </summary>
public sealed class RoutineSayTasks
{
    private readonly string _alarmRoot;
    private readonly ITaskSchedulerHost _host;

    public RoutineSayTasks(string dataRoot)
        : this(dataRoot, new WindowsTaskSchedulerHost())
    {
    }

    internal RoutineSayTasks(string dataRoot, ITaskSchedulerHost host)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        _alarmRoot = Path.Combine(Path.GetFullPath(dataRoot), ScheduledRingTasks.FolderName);
        _host = host ?? throw new ArgumentNullException(nameof(host));
    }

    /// <summary>The task of this data root's routine with that id.</summary>
    public string TaskName(string routineId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(routineId);
        byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(
            _alarmRoot.TrimEnd(Path.DirectorySeparatorChar).ToUpperInvariant() + "|" + routineId));
        return ScheduledRingTasks.SayPrefix + Convert.ToHexStringLower(hash)[..32];
    }

    /// <summary>
    /// Sets the routine's task (a new one, or over the one it had): says <paramref name="text"/> at
    /// <paramref name="first"/> and then, with <paramref name="days"/> empty and <paramref name="daily"/> false, never
    /// again; daily, each day at that clock; with days, each week on them. Read back from the scheduler: without a next
    /// run nothing is left set.
    /// </summary>
    public RoutineSayTask Set(
        string routineId, string text, DateTimeOffset first, bool daily, IReadOnlyCollection<DayOfWeek> days)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(text);
        ArgumentNullException.ThrowIfNull(days);
        string taskName = TaskName(routineId);
        string script = Path.Combine(_alarmRoot, taskName + ".ps1");
        bool registered = false;
        try
        {
            // The scheduler is opened before anything is written: one that does not answer leaves the task this
            // replaces, and its script, as they were.
            using ITaskSchedulerSession session = _host.Open();
            string xml = ScheduledNotificationTaskXml.Build(
                AlarmRingHandoff.SayKind, script, first, days.Count > 0 ? "weekly" : daily ? "daily" : null,
                _host.CurrentUserSid(), days, wake: false);
            Directory.CreateDirectory(_alarmRoot);
            // A receipt of the task it replaces (it said its text once already) would make the new one look spent.
            File.Delete(Path.Combine(_alarmRoot, taskName + ScheduledRingTasks.ReceiptExtension));
            // The clock the person asked for, as the routine keeps it (the hand-over carries it to the conversation's line).
            ScheduledRingScript.Write(script, text, first.ToString("HH:mm", CultureInfo.InvariantCulture));
            session.Register(taskName, xml);
            registered = true;
            if (session.Find(taskName)?.NextRunLocal is DateTime next)
            {
                return new RoutineSayTask(true, new DateTimeOffset(next), null);
            }

            // Registered and with no next run, it would never say anything: it does not stay.
            ScheduledRingTasks.Remove(session, _alarmRoot, taskName);
            return new RoutineSayTask(false, null, "routine_task_not_verified");
        }
        catch (Exception exception) when (exception is TaskSchedulerHostException or IOException
            or UnauthorizedAccessException)
        {
            // REV11 B-1: registered and not read back, the routine is not saved; its task does not stay to speak every
            // day with nothing in the list. Taken off by name, not by reading it first (reading it is what failed).
            return registered
                ? new RoutineSayTask(false, null, Withdrawn(taskName) ? "routine_task_not_verified" : "routine_task_not_removed")
                : new RoutineSayTask(false, null, "routine_scheduler_unavailable");
        }
    }

    // A task just registered, deleted by name on a fresh session (Microsoft Learn, ITaskFolder::DeleteTask), and then
    // what it left in the folder; false when the scheduler refused: its script stays, the record of a task to remove
    // («Olvidar todo» removes every BAXY-Say task its folder records, REV11 B-2).
    private bool Withdrawn(string taskName)
    {
        try
        {
            using (ITaskSchedulerSession session = _host.Open())
            {
                session.Delete(taskName);
            }

            foreach (string left in Directory.GetFiles(_alarmRoot, taskName + ".*"))
            {
                File.Delete(left);
            }

            return true;
        }
        catch (Exception exception) when (exception is TaskSchedulerHostException or IOException
            or UnauthorizedAccessException)
        {
            return false;
        }
    }

    /// <summary>Removes the routine's task and what it left in the folder; Ok when none is left (also when it had none).</summary>
    public RoutineSayTask Remove(string routineId)
    {
        string taskName = TaskName(routineId);
        try
        {
            using ITaskSchedulerSession session = _host.Open();
            ScheduledRingTasks.Remove(session, _alarmRoot, taskName);
            return session.Find(taskName) is null
                ? new RoutineSayTask(true, null, null)
                : new RoutineSayTask(false, null, "routine_task_not_removed");
        }
        catch (Exception exception) when (exception is TaskSchedulerHostException or IOException
            or UnauthorizedAccessException)
        {
            return new RoutineSayTask(false, null, "routine_scheduler_unavailable");
        }
    }

    /// <summary>RUT9 (REV9 H10): whether the routine's task already said its text (its script wrote its receipt).</summary>
    public bool Said(string routineId) =>
        File.Exists(Path.Combine(_alarmRoot, TaskName(routineId) + ScheduledRingTasks.ReceiptExtension));

    /// <summary>
    /// RUT9 (REV9 H5): removes every routine task this data root recorded (one per script in its folder), for when the
    /// routines file cannot be read and no id is known; the number removed, or null when one of them stayed.
    /// </summary>
    public int? RemoveEvery()
    {
        try
        {
            string[] recorded = [.. ScheduledRingTasks.Recorded(_alarmRoot)
                .Where(static name => name.StartsWith(ScheduledRingTasks.SayPrefix, StringComparison.Ordinal))];
            if (recorded.Length == 0)
            {
                return 0;
            }

            using ITaskSchedulerSession session = _host.Open();
            foreach (string taskName in recorded)
            {
                ScheduledRingTasks.Remove(session, _alarmRoot, taskName);
            }

            return recorded.All(taskName => session.Find(taskName) is null) ? recorded.Length : null;
        }
        catch (Exception exception) when (exception is TaskSchedulerHostException or IOException
            or UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>«Olvidar todo»: removes the tasks of these routines; false when one of them stayed.</summary>
    public bool RemoveAll(IEnumerable<string> routineIds)
    {
        ArgumentNullException.ThrowIfNull(routineIds);
        bool all = true;
        foreach (string routineId in routineIds)
        {
            all &= Remove(routineId).Ok;
        }

        return all;
    }
}
