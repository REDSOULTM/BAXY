namespace Baxy.Providers.Windows.External;

/// <summary>
/// One call to the Task Scheduler for BAXY's notifications: what to do (Mode) and on what. The native backend answers
/// it with one JSON line.
/// </summary>
internal sealed record ScheduledNotificationRequest(string Mode, string Kind)
{
    public string? TaskName { get; init; }
    public string? DueUtc { get; init; }
    public string? RingScriptPath { get; init; }
    public string? AlarmRoot { get; init; }
    public string? Recurrence { get; init; }
    public int Hour { get; init; } = -1;
    public int Minute { get; init; }
}

// The scheduler as the adapter asks it (the native backend; tests give scripted answers).
internal interface IScheduledNotificationBackend
{
    ValueTask<ExternalProcessResult> RunAsync(
        ScheduledNotificationRequest request,
        CancellationToken cancellationToken);
}
