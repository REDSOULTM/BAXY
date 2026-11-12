using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Threading;

namespace Baxy.App;

/// <summary>
/// Auditoría de la App (2026-10-23): an exception nothing caught ended BAXY without a word (a view handler is async
/// void, and the shell had no handler of its own), its core, its mind and what they started with it. Each one is
/// recorded in the profile (<c>&lt;datos&gt;/diagnostics/unhandled.v1.jsonl</c>, bounded as the conversation log): where
/// it came from, its type, the method that threw and its stack, never its message (it may quote what the person said or
/// a path of theirs); with <c>BAXY_APP_TRACE</c> it is a trace line too. One on the interface's thread is handled there
/// and BAXY goes on (a turn releases what it holds in its own finally); a task nobody awaited is observed; one on
/// another thread still ends the process, recorded first.
/// </summary>
internal static class UnhandledFailures
{
    internal const string Stage = "process.unhandled";
    private const int MaximumStackCharacters = 4_096;
    private static readonly object Gate = new();

    internal static void Attach(Application application)
    {
        ArgumentNullException.ThrowIfNull(application);
        application.DispatcherUnhandledException += OnDispatcherUnhandled;
        TaskScheduler.UnobservedTaskException += (_, eventArgs) =>
        {
            Record("task", eventArgs.Exception);
            eventArgs.SetObserved();
        };
        AppDomain.CurrentDomain.UnhandledException += (_, eventArgs) =>
            Record("domain", eventArgs.ExceptionObject as Exception);
    }

    private static void OnDispatcherUnhandled(object sender, DispatcherUnhandledExceptionEventArgs eventArgs)
    {
        Record("dispatcher", eventArgs.Exception);
        eventArgs.Handled = true;
    }

    // A label the trace keeps. 2026-11-05: a long exception type or a compiler's method name («<Main>b__0») passed the
    // trace's limits, and the line said only «invalid».
    internal static string TraceDetail(string source, string? type, string site)
    {
        string label = string.Concat($"{source}.{type ?? "unknown"}.{site}".ToLowerInvariant()
            .Select(static character => character is (>= 'a' and <= 'z') or (>= '0' and <= '9') or '.' or '_' or '-'
                ? character
                : '_'));
        return label.Length <= ShellTrace.MaximumLabelLength ? label : label[..ShellTrace.MaximumLabelLength];
    }

    /// <summary>
    /// A task started and left: its failure is recorded when it fails, under <paramref name="source"/>. Unwatched, it is
    /// recorded only when the collector finds the task, which may be never before BAXY closes («the exception is
    /// escalated … when the task is garbage-collected»,
    /// learn.microsoft.com/dotnet/standard/parallel-programming/exception-handling-task-parallel-library, read 2026-11-09).
    /// </summary>
    internal static void Watch(Task task, string source, string? directory = null) =>
        _ = task.ContinueWith(
            failed => Record(source, failed.Exception, directory),
            CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously,
            TaskScheduler.Default);

    /// <summary>Records one exception nothing caught; <paramref name="directory"/>: where (tests), else the profile's.</summary>
    internal static void Record(string source, Exception? exception, string? directory = null)
    {
        Exception? inner = exception is AggregateException { InnerExceptions.Count: 1 } aggregate
            ? aggregate.InnerExceptions[0]
            : exception;
        string type = inner?.GetType().FullName ?? "unknown";
        string site = inner?.TargetSite?.Name ?? "unknown";
        ShellTraceSink.Record(ShellTraceScopes.Startup, "process", Stage, TraceDetail(source, inner?.GetType().Name, site));
        try
        {
            string folder = directory ?? Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "diagnostics");
            string stack = inner?.StackTrace ?? string.Empty;
            var line = new Dictionary<string, object?>
            {
                ["utc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                ["source"] = source,
                ["type"] = type,
                ["site"] = site,
                ["hresult"] = inner?.HResult,
                ["stack"] = stack.Length <= MaximumStackCharacters ? stack : stack[..MaximumStackCharacters],
            };
            lock (Gate)
            {
                Directory.CreateDirectory(folder);
                new BoundedJsonlFile(Path.Combine(folder, "unhandled.v1.jsonl")).AppendLine(JsonSerializer.Serialize(line));
            }
        }
        catch (Exception recordFailure) when (recordFailure is IOException or UnauthorizedAccessException
            or InvalidOperationException or ArgumentException)
        {
            // Recording it never adds a failure of its own.
        }
    }
}
