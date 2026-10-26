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

    /// <summary>Records one exception nothing caught; <paramref name="directory"/>: where (tests), else the profile's.</summary>
    internal static void Record(string source, Exception? exception, string? directory = null)
    {
        Exception? inner = exception is AggregateException { InnerExceptions.Count: 1 } aggregate
            ? aggregate.InnerExceptions[0]
            : exception;
        string type = inner?.GetType().FullName ?? "unknown";
        string site = inner?.TargetSite?.Name ?? "unknown";
        ShellTraceSink.Record(ShellTraceScopes.Startup, "process", Stage,
            $"{source}.{inner?.GetType().Name ?? "unknown"}.{site}".ToLowerInvariant());
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
