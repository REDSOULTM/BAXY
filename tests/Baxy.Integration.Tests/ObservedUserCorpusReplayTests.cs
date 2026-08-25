using System.Diagnostics;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class ObservedUserCorpusReplayTests
{
    private const string CorpusVariable = "BAXY_GOAL10_OBSERVED_CORPUS";
    private const string MappingVariable = "BAXY_GOAL10_OBSERVED_MAPPING";
    private const string OutputVariable = "BAXY_GOAL10_OBSERVED_OUTPUT";
    private const string MaxCasesVariable = "BAXY_GOAL10_OBSERVED_MAX_CASES";
    private const string SourceVariable = "BAXY_GOAL10_OBSERVED_SOURCE";
    private const string MemoryBaselineVariable = "BAXY_GOAL10_MEMORY_BASELINE";

    private static readonly string[] OwnedEnvironmentVariables =
    [
        "BAXY_DATA_DIR",
        "BAXY_VOICE_WAKE_ON_START",
    ];

    [Test]
    [Explicit("Goal 10 private observed-user replay through the real shell, mind and Core.")]
    [Category("Goal10ObservedProductReplay")]
    public async Task OptInObservedOccurrencesProduceVisibleResponsesAndAuthenticatedOutcomes()
    {
        string corpusPath = RequiredAbsoluteFile(CorpusVariable);
        string mappingPath = RequiredAbsoluteFile(MappingVariable);
        string outputPath = RequiredAbsoluteOutput(OutputVariable);
        int? maximum = OptionalPositiveInteger(MaxCasesVariable);
        string selectedSource = Environment.GetEnvironmentVariable(SourceVariable) ?? string.Empty;
        bool memoryEnabledAtStart = OptionalBoolean(MemoryBaselineVariable);
        CorpusRow[] rows = ReadCorpus(corpusPath, selectedSource, maximum);
        Dictionary<string, JsonElement> mappings = ReadMappings(mappingPath);
        Assert.That(rows, Is.Not.Empty);
        Assert.That(
            rows.All(row => mappings.ContainsKey(row.MessageId)),
            Is.True,
            "Every selected occurrence must have one independent acceptance mapping.");

        string dataRoot = PrivateDataRootTestSupport.NewPath("goal10-observed-replay");
        string shellTracePath = Path.Combine(dataRoot, "shell-trace.jsonl");
        using var environment = new EnvironmentVariableScope(OwnedEnvironmentVariables);
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", dataRoot);
        Environment.SetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START", "0");
        Directory.CreateDirectory(dataRoot);
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
        File.Delete(outputPath);
        bool previousCompositionBypass = UserMessagePolicy.BypassLlmCompositionForTests;

        try
        {
            UserMessagePolicy.BypassLlmCompositionForTests = false;
            using ShellTrace shellTrace = ShellTrace.TryCreate(shellTracePath)
                ?? throw new InvalidOperationException("Could not create the Goal 10 shell trace.");
            using IDisposable traceScope = ShellTraceSink.Use(shellTrace);
            await using var viewModel = new MainWindowViewModel();
            using var startupTimeout = new CancellationTokenSource(TimeSpan.FromMinutes(5));
            await viewModel.InitializeAsync(startupTimeout.Token);
            await WaitForMindAsync(viewModel, startupTimeout.Token);
            if (memoryEnabledAtStart)
            {
                await PrepareEnabledMemoryBaselineAsync(
                    viewModel,
                    dataRoot);
            }

            string? activeSource = null;
            var elapsed = Stopwatch.StartNew();
            for (int index = 0; index < rows.Length; index++)
            {
                CorpusRow row = rows[index];
                bool independentTrace = row.Source.StartsWith(
                    "probando_gemma4/",
                    StringComparison.Ordinal);
                if (activeSource is not null
                    && (independentTrace || !string.Equals(
                        activeSource,
                        row.Source,
                        StringComparison.Ordinal)))
                {
                    Assert.That(viewModel.StartNewUiSession(), Is.True);
                }
                activeSource = row.Source;

                long traceSequence = LastTraceSequence(shellTracePath);
                int journalRecords = JournalPayloads(dataRoot).Length;
                var turnTimer = Stopwatch.StartNew();
                using var turnTimeout = new CancellationTokenSource(TimeSpan.FromMinutes(3));
                string response = await SubmitAsync(
                    viewModel,
                    row.Text,
                    turnTimeout.Token);
                turnTimer.Stop();

                JsonElement[] trace = ReadTraceAfter(shellTracePath, traceSequence);
                JsonElement[] journal = JournalPayloads(dataRoot)
                    .Skip(journalRecords)
                    .ToArray();
                string statusAfterResponse = viewModel.StatusDescription;
                string cleanupResponse = string.Empty;
                if (independentTrace
                    && statusAfterResponse is (
                        "awaiting_mission_resume" or "Esperando tu aclaración"))
                {
                    using var cleanupTimeout = new CancellationTokenSource(TimeSpan.FromMinutes(2));
                    cleanupResponse = await SubmitAsync(
                        viewModel,
                        "cancelar",
                        cleanupTimeout.Token);
                }

                WriteDurableRow(
                    outputPath,
                    new
                    {
                        schema = "baxy.goal10-observed-product-replay.v1",
                        occurrence_index = index,
                        message_id = row.MessageId,
                        message = row.Text,
                        source = row.Source,
                        source_location = row.SourceLocation,
                        expected_contract = mappings[row.MessageId],
                        response,
                        shell_status = statusAfterResponse,
                        shell_trace = trace,
                        journal_payloads = journal,
                        cleanup_response = cleanupResponse,
                        timing_seconds = turnTimer.Elapsed.TotalSeconds,
                        captured_at_utc = DateTimeOffset.UtcNow,
                        baseline_memory_enabled = memoryEnabledAtStart,
                        execution_state = "captured",
                    });

                if ((index + 1) % 10 == 0 || index + 1 == rows.Length)
                {
                    TestContext.Progress.WriteLine(
                        JsonSerializer.Serialize(new
                        {
                            completed = index + 1,
                            total = rows.Length,
                            elapsed_seconds = elapsed.Elapsed.TotalSeconds,
                        }));
                }
            }

            JsonElement[] results = ReadJsonLines(outputPath);
            Assert.Multiple(() =>
            {
                Assert.That(results, Has.Length.EqualTo(rows.Length));
                Assert.That(
                    results.Select(result => TextProperty(result, "message_id")),
                    Is.Unique);
                Assert.That(
                    results.All(result => !string.IsNullOrWhiteSpace(
                        TextProperty(result, "response"))),
                    Is.True,
                    "Every occurrence must leave exact visible terminal text.");
            });
        }
        finally
        {
            UserMessagePolicy.BypassLlmCompositionForTests = previousCompositionBypass;
            DeleteOwnedDataRoot(dataRoot);
        }
    }

    private static CorpusRow[] ReadCorpus(
        string path,
        string selectedSource,
        int? maximum)
    {
        IEnumerable<CorpusRow> rows = ReadJsonLines(path)
            .Select(static value => new CorpusRow(
                TextProperty(value, "message_id"),
                TextProperty(value, "text_literal"),
                TextProperty(value, "source"),
                TextProperty(value, "source_location")))
            .Where(row => string.IsNullOrEmpty(selectedSource)
                || string.Equals(row.Source, selectedSource, StringComparison.Ordinal))
            .OrderBy(static row => row.Source, StringComparer.Ordinal)
            .ThenBy(static row => LocationOrdinal(row.SourceLocation))
            .ThenBy(static row => row.MessageId, StringComparer.Ordinal);
        if (maximum is not null)
        {
            rows = rows.Take(maximum.Value);
        }
        return rows.ToArray();
    }

    private static Dictionary<string, JsonElement> ReadMappings(string path) =>
        ReadJsonLines(path).ToDictionary(
            static value => TextProperty(value, "message_id"),
            static value => value,
            StringComparer.Ordinal);

    private static long LocationOrdinal(string value)
    {
        ReadOnlySpan<char> span = value.AsSpan();
        int end = span.Length - 1;
        while (end >= 0 && !char.IsAsciiDigit(span[end]))
        {
            end--;
        }
        int start = end;
        while (start >= 0 && char.IsAsciiDigit(span[start]))
        {
            start--;
        }
        return end >= 0 && long.TryParse(span[(start + 1)..(end + 1)], out long result)
            ? result
            : long.MaxValue;
    }

    private static async Task<string> SubmitAsync(
        MainWindowViewModel viewModel,
        string text,
        CancellationToken cancellationToken)
    {
        int previousCount = viewModel.Messages.Count;
        viewModel.Draft = text;
        await viewModel.SubmitAsync(cancellationToken);
        using var projectionTimeout = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken);
        projectionTimeout.CancelAfter(TimeSpan.FromSeconds(5));
        while (!viewModel.Messages
            .Skip(previousCount)
            .Any(static message => !message.IsUser))
        {
            await Task.Delay(TimeSpan.FromMilliseconds(20), projectionTimeout.Token);
        }
        ConversationMessage[] added = viewModel.Messages.Skip(previousCount).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(added, Has.Length.GreaterThanOrEqualTo(2));
            Assert.That(added[0].IsUser, Is.True);
            Assert.That(added[0].Body, Is.EqualTo(text));
            Assert.That(added[^1].IsUser, Is.False);
            Assert.That(added[^1].Speaker, Is.EqualTo("BAXY"));
        });
        return added[^1].Body;
    }

    private static async Task WaitForMindAsync(
        MainWindowViewModel viewModel,
        CancellationToken cancellationToken)
    {
        FieldInfo mindField = typeof(MainWindowViewModel).GetField(
            "_mindClient",
            BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(
                typeof(MainWindowViewModel).FullName,
                "_mindClient");
        while (mindField.GetValue(viewModel) is not MindSidecarClient { IsReady: true })
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (viewModel.HasStartupError)
            {
                Assert.Fail("The shell reported a startup error before the mind became ready.");
            }
            await Task.Delay(TimeSpan.FromMilliseconds(100), cancellationToken);
        }
    }

    private static async Task PrepareEnabledMemoryBaselineAsync(
        MainWindowViewModel viewModel,
        string dataRoot)
    {
        bool previousCompositionBypass = UserMessagePolicy.BypassLlmCompositionForTests;
        try
        {
            // Fixture setup is not an observed response. Keep it synchronous so
            // no hidden composer retry can leak into the first corpus turn.
            UserMessagePolicy.BypassLlmCompositionForTests = true;
            _ = await SubmitAsync(viewModel, "activa la memoria", CancellationToken.None);
            _ = await SubmitAsync(viewModel, "confirmar", CancellationToken.None);
        }
        finally
        {
            UserMessagePolicy.BypassLlmCompositionForTests = previousCompositionBypass;
        }
        JsonElement[] journal = JournalPayloads(dataRoot);
        bool verified = journal.Any(static payload =>
            TextProperty(payload, "phase") == "completed"
            && TextProperty(payload, "operation") == "memory.enable"
            && payload.TryGetProperty("response", out JsonElement response)
            && TextProperty(response, "status") == "completed"
            && response.TryGetProperty("verified", out JsonElement verifiedProperty)
            && verifiedProperty.ValueKind == JsonValueKind.True);
        Assert.That(
            verified,
            Is.True,
            "The replay's enabled-memory baseline must be a verified product operation.");
        Assert.That(
            viewModel.StartNewUiSession(),
            Is.True,
            "The baseline setup must not leak into the observed conversation context.");
    }

    private static JsonElement[] JournalPayloads(string dataRoot)
    {
        string path = Path.Combine(dataRoot, "journal", "missions.jsonl");
        return File.Exists(path)
            ? ReadJsonLines(path)
                .Select(static envelope => envelope.GetProperty("payload").Clone())
                .ToArray()
            : [];
    }

    private static long LastTraceSequence(string path) =>
        ReadJsonLines(path)
            .Select(static value => value.TryGetProperty("seq", out JsonElement sequence)
                ? sequence.GetInt64()
                : 0L)
            .DefaultIfEmpty(0L)
            .Max();

    private static JsonElement[] ReadTraceAfter(string path, long sequence) =>
        ReadJsonLines(path)
            .Where(value => value.TryGetProperty("seq", out JsonElement current)
                && current.GetInt64() > sequence)
            .ToArray();

    private static JsonElement[] ReadJsonLines(string path)
    {
        if (!File.Exists(path))
        {
            return [];
        }
        Exception? lastFailure = null;
        for (int attempt = 0; attempt < 50; attempt++)
        {
            try
            {
                using var stream = new FileStream(
                    path,
                    FileMode.Open,
                    FileAccess.Read,
                    FileShare.ReadWrite | FileShare.Delete);
                using var reader = new StreamReader(stream, Encoding.UTF8);
                return reader.ReadToEnd()
                    .Split(
                        ['\r', '\n'],
                        StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                    .Where(static line => !string.IsNullOrWhiteSpace(line))
                    .Select(static line => JsonDocument.Parse(line).RootElement.Clone())
                    .ToArray();
            }
            catch (Exception exception) when (exception is IOException or JsonException)
            {
                lastFailure = exception;
                Thread.Sleep(TimeSpan.FromMilliseconds(20));
            }
        }
        throw new IOException($"JSONL stayed unavailable: {path}", lastFailure);
    }

    private static void WriteDurableRow(string path, object value)
    {
        byte[] payload = Encoding.UTF8.GetBytes(
            JsonSerializer.Serialize(value) + Environment.NewLine);
        using var stream = new FileStream(
            path,
            FileMode.Append,
            FileAccess.Write,
            FileShare.Read,
            bufferSize: 4096,
            FileOptions.WriteThrough);
        stream.Write(payload);
        stream.Flush(flushToDisk: true);
    }

    private static string TextProperty(JsonElement value, string name) =>
        value.TryGetProperty(name, out JsonElement property)
        && property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? string.Empty
            : string.Empty;

    private static string RequiredAbsoluteFile(string name)
    {
        string value = Environment.GetEnvironmentVariable(name) ?? string.Empty;
        Assert.That(Path.IsPathFullyQualified(value), Is.True, $"{name} must be absolute.");
        Assert.That(File.Exists(value), Is.True, $"{name} must name an existing file.");
        return Path.GetFullPath(value);
    }

    private static string RequiredAbsoluteOutput(string name)
    {
        string value = Environment.GetEnvironmentVariable(name) ?? string.Empty;
        Assert.That(Path.IsPathFullyQualified(value), Is.True, $"{name} must be absolute.");
        return Path.GetFullPath(value);
    }

    private static int? OptionalPositiveInteger(string name)
    {
        string value = Environment.GetEnvironmentVariable(name) ?? string.Empty;
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }
        Assert.That(int.TryParse(value, out int parsed), Is.True, $"{name} must be an integer.");
        Assert.That(parsed, Is.GreaterThan(0), $"{name} must be positive.");
        return parsed;
    }

    private static bool OptionalBoolean(string name)
    {
        string value = Environment.GetEnvironmentVariable(name) ?? string.Empty;
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }
        Assert.That(
            value is "0" or "1" or "false" or "true",
            Is.True,
            $"{name} must be 0, 1, false or true.");
        return value is "1" or "true";
    }

    private static void DeleteOwnedDataRoot(string path)
    {
        string ownedParent = Path.GetFullPath(Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            "BAXY"));
        string fullPath = Path.GetFullPath(path);
        if (!fullPath.StartsWith(
                ownedParent.TrimEnd(Path.DirectorySeparatorChar)
                    + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Refusing to delete an unowned test data root.");
        }
        if (Directory.Exists(fullPath))
        {
            Directory.Delete(fullPath, recursive: true);
        }
    }

    private sealed record CorpusRow(
        string MessageId,
        string Text,
        string Source,
        string SourceLocation);

    private sealed class EnvironmentVariableScope : IDisposable
    {
        private readonly Dictionary<string, string?> _before;

        internal EnvironmentVariableScope(IEnumerable<string> names)
        {
            _before = names
                .Distinct(StringComparer.Ordinal)
                .ToDictionary(
                    static name => name,
                    static name => Environment.GetEnvironmentVariable(name),
                    StringComparer.Ordinal);
        }

        public void Dispose()
        {
            foreach ((string name, string? value) in _before)
            {
                Environment.SetEnvironmentVariable(name, value);
            }
        }
    }
}
