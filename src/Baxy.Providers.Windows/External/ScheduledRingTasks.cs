using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The Task Scheduler tasks of BAXY's alarms and reminders, and of the routines that say a text at a time (RUT4,
/// <c>BAXY-Say-…</c>, RoutineSayTasks), told by what BAXY itself recorded. Every ring it sets
/// writes its script in the data root's notifications folder under the task's own name
/// (WindowsScheduledNotificationAdapter.WriteRingScript), and that file is what makes a task this BAXY's (M80,
/// NativeScheduledNotificationBackend.IsOwn). The scheduler is never searched by a name pattern: a task of that shape
/// with no script here was set from another data root or by another program, and stays.
/// <para>INS-1: nothing removed them when BAXY was uninstalled, so they kept ringing (and starting PowerShell) on a
/// PC with no BAXY. The installer compiles this file and <see cref="WindowsTaskSchedulerHost"/> as they are
/// (Baxy.Installer.csproj), so this class uses nothing else of the providers.</para>
/// </summary>
internal static class ScheduledRingTasks
{
    /// <summary>The folder of a data root where its rings keep their scripts and receipts.</summary>
    internal const string FolderName = "scheduled-notifications";

    /// <summary>What a ring's script writes when it rings (ScheduledRingScript): when it rang, and how.</summary>
    internal const string ReceiptExtension = ".fired";

    /// <summary>The script's «it is the time», for the open App to take (AlarmRingHandoff).</summary>
    internal const string DueExtension = ".due";

    /// <summary>The App took the ring: it rings now (AlarmRingHandoff).</summary>
    internal const string RingingExtension = ".ringing";

    // Microsoft Learn, TASK_STATE: «TASK_STATE_READY, value 3: The task is ready to be executed, but no instances are
    // queued or running» (1 is disabled, 2 queued, 4 running).
    private const int TaskStateReady = 3;

    private static readonly Regex Name = new(
        "^BAXY-(Alarm|Reminder|Say)-[0-9a-f]{32}$", RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(100));

    /// <summary>Whether a name is one BAXY gives a ring's task: nothing else is a ring of BAXY's.</summary>
    internal static bool IsRingTask(string name) => Name.IsMatch(name);

    /// <summary>The prefix of a routine's task: at its time BAXY says a text once, and nothing rings (RUT4).</summary>
    internal const string SayPrefix = "BAXY-Say-";

    /// <summary>What a ring's task is, by its name: alarm, reminder or say.</summary>
    internal static string Kind(string taskName) =>
        taskName.StartsWith("BAXY-Alarm-", StringComparison.Ordinal) ? "alarm"
        : taskName.StartsWith(SayPrefix, StringComparison.Ordinal) ? "say"
        : "reminder";

    /// <summary>The tasks this notifications folder recorded: one per ring script in it, by the script's name.</summary>
    internal static IReadOnlyList<string> Recorded(string alarmRoot)
    {
        ArgumentNullException.ThrowIfNull(alarmRoot);
        if (!Directory.Exists(alarmRoot))
        {
            return [];
        }

        return [.. Directory.EnumerateFiles(alarmRoot, "BAXY-*.ps1")
            .Select(static script => Path.GetFileNameWithoutExtension(script))
            .Where(IsRingTask)
            .Order(StringComparer.Ordinal)];
    }

    /// <summary>
    /// Removes one ring: its task, when the scheduler still has it (Microsoft Learn, ITaskFolder::DeleteTask: «Deletes a
    /// task from the folder», by «the name of the task that is specified when the task was registered»), and then every
    /// file it left under its name (its script, its receipt, a hand-over in course). The task goes first: if the
    /// scheduler refuses, the script stays and with it the record of a task still to remove.
    /// </summary>
    internal static void Remove(ITaskSchedulerSession session, string alarmRoot, string taskName)
    {
        ArgumentNullException.ThrowIfNull(session);
        ArgumentNullException.ThrowIfNull(alarmRoot);
        if (!IsRingTask(taskName))
        {
            throw new ArgumentException("not a ring task of BAXY's", nameof(taskName));
        }

        if (session.Find(taskName) is not null)
        {
            session.Delete(taskName);
        }

        if (!Directory.Exists(alarmRoot))
        {
            return;
        }

        foreach (string left in Directory.GetFiles(alarmRoot, taskName + ".*"))
        {
            File.Delete(left);
        }
    }

    /// <summary>
    /// Removes every ring this notifications folder recorded and returns how many. A folder with none never opens the
    /// scheduler.
    /// </summary>
    internal static int RemoveAll(ITaskSchedulerHost host, string alarmRoot)
    {
        ArgumentNullException.ThrowIfNull(host);
        IReadOnlyList<string> recorded = Recorded(alarmRoot);
        if (recorded.Count == 0)
        {
            return 0;
        }

        using ITaskSchedulerSession session = host.Open();
        foreach (string taskName in recorded)
        {
            Remove(session, alarmRoot, taskName);
        }

        return recorded.Count;
    }

    /// <summary>
    /// PRV-2: removes the rings of this notifications folder that rang and will not ring again, and returns how many.
    /// A one-time alarm or reminder kept its task registered for good after it rang (the task XML asks for no deletion,
    /// and Microsoft Learn, ITaskSettings::DeleteExpiredTaskAfter: «If no value is specified for this property, then
    /// the Task Scheduler service will not delete the task»); the script went only once no task was behind it, so
    /// neither ever did. Measured on the owner's PC (2026-11-09, read only): 112 tasks of BAXY's rings, every one a
    /// time trigger with no repetition, Ready and with no next run.
    /// <para>A ring is spent when all of this holds: its script wrote its receipt (it rang at least once); the App no
    /// longer rings it and no hand-over is in course; and its task is ready, so its script ended and the person did not
    /// disable it, with no next run (Microsoft Learn, IRegisteredTask::get_NextRunTime: «the time when the registered
    /// task is next scheduled to run»; Task Scheduler reports «none» as DATE 0). A daily or hourly one always has a
    /// next run and stays; so does a one-time one that has not rung, whose time may have passed with the PC off
    /// (StartWhenAvailable starts it «after a delay», and until then it has no next run either: its receipt is what
    /// tells them apart). Windows' own expiry (EndBoundary and DeleteExpiredTaskAfter) is not used: it would take that
    /// late one away without ringing, and leave the script.</para>
    /// <para>The task goes first and then its script; the receipt stays for the diagnosis that reads it («why did my
    /// alarm not ring») and goes with the others at its age (WindowsScheduledNotificationAdapter.PruneSpentRingScripts).
    /// A folder where nothing rang never opens the scheduler.</para>
    /// </summary>
    internal static int RemoveSpent(ITaskSchedulerHost host, string alarmRoot)
    {
        ArgumentNullException.ThrowIfNull(host);
        string[] rang = [.. Recorded(alarmRoot).Where(taskName =>
            File.Exists(Path.Combine(alarmRoot, taskName + ReceiptExtension))
            && !File.Exists(Path.Combine(alarmRoot, taskName + RingingExtension))
            && !File.Exists(Path.Combine(alarmRoot, taskName + DueExtension)))];
        if (rang.Length == 0)
        {
            return 0;
        }

        int removed = 0;
        using ITaskSchedulerSession session = host.Open();
        foreach (string taskName in rang)
        {
            if (session.Find(taskName) is { } task)
            {
                if (task.State != TaskStateReady || task.NextRunLocal is not null)
                {
                    continue;
                }

                session.Delete(taskName);
            }

            File.Delete(Path.Combine(alarmRoot, taskName + ".ps1"));
            removed++;
        }

        return removed;
    }
}
