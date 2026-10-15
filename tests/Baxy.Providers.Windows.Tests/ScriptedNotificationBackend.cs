using System.Text.Json;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The Task Scheduler as the notification adapter asks it, answering scripted JSON lines; every request is kept.
/// </summary>
internal sealed class ScriptedNotificationBackend(Func<ScheduledNotificationRequest, ExternalProcessResult> answer)
    : IScheduledNotificationBackend
{
    internal List<ScheduledNotificationRequest> Requests { get; } = [];

    public ValueTask<ExternalProcessResult> RunAsync(
        ScheduledNotificationRequest request,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Requests.Add(request);
        return ValueTask.FromResult(answer(request));
    }

    /// <summary>Each call answers the next line; the last one repeats.</summary>
    internal static ScriptedNotificationBackend Lines(params string[] lines)
    {
        int calls = 0;
        return new(_ => new ExternalProcessResult(0, lines[Math.Min(calls++, lines.Length - 1)], string.Empty));
    }

    /// <summary>A schedule answers the task it was asked to register, ready, due in an hour.</summary>
    internal static ScriptedNotificationBackend Registering() => new(Registered);

    internal static ExternalProcessResult Registered(ScheduledNotificationRequest request) => new(
        0,
        JsonSerializer.Serialize(new
        {
            version = 1,
            ok = true,
            effectObserved = true,
            taskName = request.TaskName,
            state = "Ready",
            nextRunUtc = DateTimeOffset.UtcNow.AddHours(1).ToString("O"),
            recurrence = request.Recurrence ?? "none",
            authority = "windows_task_scheduler_postread",
        }),
        string.Empty);
}
