using System.Globalization;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// One call of WindowsScheduledNotification.ps1, by its parameters. The native backend answers
/// it in-process with the same JSON line the script prints; the script backend runs the script.
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
    public string? Period { get; init; }
}

internal interface IScheduledNotificationBackend
{
    ValueTask<ExternalProcessResult> RunAsync(
        ScheduledNotificationRequest request,
        CancellationToken cancellationToken);
}

internal sealed class ScriptScheduledNotificationBackend(
    IExternalProcessRunner runner,
    string schedulerScript) : IScheduledNotificationBackend
{
    private readonly IExternalProcessRunner _runner =
        runner ?? throw new ArgumentNullException(nameof(runner));

    public ValueTask<ExternalProcessResult> RunAsync(
        ScheduledNotificationRequest request,
        CancellationToken cancellationToken)
    {
        List<string> arguments =
        [
            "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
            schedulerScript, "-Mode", request.Mode, "-Kind", request.Kind,
        ];
        Add(arguments, "-TaskName", request.TaskName);
        Add(arguments, "-DueUtc", request.DueUtc);
        Add(arguments, "-RingScriptPath", request.RingScriptPath);
        if (request.Mode == "resolve-at")
        {
            Add(arguments, "-Hour", request.Hour.ToString(CultureInfo.InvariantCulture));
            Add(arguments, "-Minute", request.Minute.ToString(CultureInfo.InvariantCulture));
        }
        Add(arguments, "-AlarmRoot", request.AlarmRoot);
        Add(arguments, "-Recurrence", request.Recurrence);
        Add(arguments, "-Period", request.Period);
        return _runner.RunAsync(
            "powershell.exe", arguments, TimeSpan.FromSeconds(30), cancellationToken);
    }

    private static void Add(List<string> arguments, string name, string? value)
    {
        if (value is null) return;
        arguments.Add(name);
        arguments.Add(value);
    }
}
