namespace Baxy.Providers.Windows.External;

/// <summary>
/// INS-1, for the BAXY a store installed: Steam and the itch app remove the folder themselves and no uninstaller of
/// BAXY's runs, so the alarms and reminders it set would go on ringing from Windows' Task Scheduler. This is what the
/// App does when the store lets it run one last time (Baxy.exe --remove-scheduled-rings; Steam's install script,
/// scripts/steam/installscript.vdf): the tasks the data root recorded, and their files, and nothing else
/// (<see cref="ScheduledRingTasks"/>).
/// </summary>
public static class ScheduledRingsRemoval
{
    private static readonly Lock Spent = new();

    /// <summary>
    /// Removes every alarm and reminder <paramref name="dataRoot"/> recorded and returns how many.
    /// </summary>
    /// <exception cref="IOException">The Task Scheduler refused; what it had not removed yet stays recorded.</exception>
    public static int RemoveAll(string dataRoot) => RemoveAll(new WindowsTaskSchedulerHost(), dataRoot);

    internal static int RemoveAll(ITaskSchedulerHost host, string dataRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        try
        {
            return ScheduledRingTasks.RemoveAll(host, AlarmRingHandoff.Folder(dataRoot));
        }
        catch (TaskSchedulerHostException refused)
        {
            throw new IOException($"the Task Scheduler did not remove BAXY's alarms and reminders ({refused.Message})", refused);
        }
    }

    /// <summary>
    /// PRV-2: removes the one-time alarms and reminders of <paramref name="dataRoot"/> that rang and will not ring again
    /// (<see cref="ScheduledRingTasks.RemoveSpent"/>): their task and their script. Returns how many.
    /// </summary>
    /// <exception cref="IOException">The Task Scheduler refused; what it had not removed yet stays recorded.</exception>
    public static int RemoveSpent(string dataRoot) => RemoveSpent(new WindowsTaskSchedulerHost(), dataRoot);

    internal static int RemoveSpent(ITaskSchedulerHost host, string dataRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        try
        {
            // One at a time: the App asks when it starts and when each ring ends, from threads of its own.
            lock (Spent)
            {
                return ScheduledRingTasks.RemoveSpent(host, AlarmRingHandoff.Folder(dataRoot));
            }
        }
        catch (TaskSchedulerHostException refused)
        {
            throw new IOException($"the Task Scheduler did not remove BAXY's spent alarms and reminders ({refused.Message})", refused);
        }
    }
}
