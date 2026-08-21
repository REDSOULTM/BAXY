using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.Routines;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class Goal05CatalogExecutionMatrixTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    private string _dataRoot = null!;

    [SetUp]
    public void SetUp() => _dataRoot = PrivateDataRootTestSupport.NewPath("goal05-matrix");

    [TearDown]
    public void TearDown()
    {
        if (Directory.Exists(_dataRoot))
        {
            Directory.Delete(_dataRoot, recursive: true);
        }
    }

    [Test]
    public void EveryCatalogOperationHasAnObservationOrAnUnverifiableReason()
    {
        IReadOnlyList<Goal05CatalogObservation.Row> rows = Goal05CatalogObservation.ClassifyCatalog();
        Assert.Multiple(() =>
        {
            Assert.That(rows, Has.Count.EqualTo(ProductCatalog.Descriptors.Count));
            Assert.That(rows.Select(row => row.Operation), Is.EqualTo(ProductCatalog.OperationNames));
            Assert.That(
                rows.Where(row => row.Verdict == "observed"),
                Has.All.Matches<Goal05CatalogObservation.Row>(row =>
                    !string.IsNullOrWhiteSpace(row.Observation)
                    && row.Reason is null
                    && row.Surface is "isolated_store" or "live_windows"));
            Assert.That(
                rows.Where(row => row.Verdict == "unverifiable"),
                Has.All.Matches<Goal05CatalogObservation.Row>(row =>
                    !string.IsNullOrWhiteSpace(row.Reason) && row.Surface == "none"));
        });
    }

    [Test]
    public void NoGenericVerificationStrategyOrRegistryExists()
    {
        string[] bannedFragments =
        [
            "VerificationStrategy",
            "VerifierRegistry",
            "IEffectVerifier",
            "IVerifierBus",
            "PluginVerifier",
        ];
        string[] names =
        [
            .. typeof(MissionEngine).Assembly.GetTypes().Select(type => type.Name),
            .. typeof(AppOpenHandler).Assembly.GetTypes().Select(type => type.Name),
            .. typeof(Baxy.Providers.Windows.Audio.WindowsAudioControlProvider).Assembly
                .GetTypes()
                .Select(type => type.Name),
        ];
        string[] hits = names
            .Where(name => bannedFragments.Any(fragment =>
                name.Contains(fragment, StringComparison.Ordinal)))
            .ToArray();
        Assert.That(hits, Is.Empty, string.Join(", ", hits));
        Assert.That(
            ProductCatalog.Descriptors.Select(descriptor => descriptor.VerifierContractId)
                .Distinct(StringComparer.Ordinal)
                .Count(),
            Is.EqualTo(ProductCatalog.Descriptors.Count));
        Goal05Scratch.Write(
            "direct-checks.log",
            $"types_scanned={names.Length} banned_hits=0 unique_verifier_ids={ProductCatalog.Descriptors.Count}{Environment.NewLine}");
    }

    [Test]
    public async Task IsolatedStoresObserveClaimedStateWithoutExecutorReturnCodes()
    {
        string notesRoot = Path.Combine(_dataRoot, "notes");
        var notes = new LocalNoteStore(notesRoot);
        OperationOutcome created = await new CreateNoteHandler(notes).ExecuteAsync(
            Invocation("note.create", """{"title":"Goal05 isolated","content":"postread"}"""),
            CancellationToken.None);
        string noteId = created.Result!.Value.GetProperty("noteId").GetString()!;
        NoteRecord observed = notes.Read(Guid.Parse(noteId));

        string filesRoot = Path.Combine(_dataRoot, "filesystem");
        var files = new LocalFilesystemProvider(filesRoot);
        IOperationHandler write = FilesystemHandlers.Create(files)
            .Single(handler => handler.Definition.Name == "filesystem.write.text");
        OperationOutcome written = await write.ExecuteAsync(
            Invocation(
                "filesystem.write.text",
                """{"relativePath":"goal05.txt","text":"goal05-matrix"}"""),
            CancellationToken.None);
        string resourceId = written.Result!.Value.GetProperty("resourceId").GetString()!;
        string sha = written.Result.Value.GetProperty("sha256").GetString()!;
        IOperationHandler hash = FilesystemHandlers.Create(files)
            .Single(handler => handler.Definition.Name == "filesystem.hash");
        OperationOutcome hashed = await hash.ExecuteAsync(
            Invocation("filesystem.hash", $$"""{"resourceId":"{{resourceId}}"}"""),
            CancellationToken.None);

        var tasks = new LocalTaskStore(Path.Combine(_dataRoot, "tasks"));
        IOperationHandler createTask = TaskHandlers.Create(tasks)
            .Single(handler => handler.Definition.Name == "task.create");
        OperationOutcome task = await createTask.ExecuteAsync(
            Invocation("task.create", """{"title":"Goal05 task"}"""),
            CancellationToken.None);
        string taskId = task.Result!.Value.GetProperty("taskId").GetString()!;

        string due = DateTimeOffset.UtcNow.AddHours(1).ToString("O", CultureInfo.InvariantCulture);
        IOperationHandler reminder = ReminderHandlers.Create(
                new LocalTaskStore(Path.Combine(_dataRoot, "reminders")),
                TimeProvider.System)
            .Single(handler => handler.Definition.Name == "reminder.create");
        OperationOutcome reminderCreated = await reminder.ExecuteAsync(
            Invocation("reminder.create", $$"""{"title":"Goal05 reminder","dueUtc":"{{due}}"}"""),
            CancellationToken.None);

        var routines = new LocalRoutineStore(Path.Combine(_dataRoot, "routines"));
        IOperationHandler routine = RoutineHandlers.Create(routines)
            .Single(handler => handler.Definition.Name == "routine.phrase.create");
        OperationOutcome routineCreated = await routine.ExecuteAsync(
            Invocation(
                "routine.phrase.create",
                """{"name":"Goal05","phrase":"frase mvp","action":"capture.screenshot"}"""),
            CancellationToken.None);
        string routineId = routineCreated.Result!.Value.GetProperty("routine")
            .GetProperty("routineId").GetString()!;

        Assert.Multiple(() =>
        {
            Assert.That(created.Succeeded && created.Verified, Is.True);
            Assert.That(observed.Content, Is.EqualTo("postread"));
            Assert.That(written.Succeeded && written.Verified, Is.True);
            Assert.That(hashed.Result!.Value.GetProperty("sha256").GetString(), Is.EqualTo(sha));
            Assert.That(task.Succeeded && task.Verified, Is.True);
            Assert.That(tasks.Read(Guid.Parse(taskId)).Title, Is.EqualTo("Goal05 task"));
            Assert.That(reminderCreated.Succeeded && reminderCreated.Verified, Is.True);
            Assert.That(routineCreated.Succeeded && routineCreated.Verified, Is.True);
            Assert.That(routines.Read(Guid.Parse(routineId), includeDeleted: false).Name, Is.EqualTo("Goal05"));
        });
    }

    [Test]
    [CancelAfter(120_000)]
    public async Task LiveCoreExercisesRestorableOperationsTwice()
    {
        var live = new List<object>();
        var log = new StringBuilder();
        int? launchedNotepadPid = null;
        int? originalVolume = null;
        string? originalClipboard = null;

        await using Goal05CoreSession session = await Goal05CoreSession.StartAsync(_dataRoot);
        try
        {
            for (int round = 1; round <= 2; round++)
            {
                OperationResponse status = await SendAsync(
                    session, "audio.status", "{}", live, log, round);
                if (status.Status == OperationStatuses.Completed && status.Verified)
                {
                    JsonElement audioState = status.Result!.Value.GetProperty("state");
                    originalVolume ??= audioState.GetProperty("volumePercent").GetInt32();
                    int current = audioState.GetProperty("volumePercent").GetInt32();
                    int target = current >= 100 ? 99 : current + 1;
                    OperationResponse volume = await SendAsync(
                        session,
                        "audio.volume",
                        $$"""{"level":{{target}}}""",
                        live,
                        log,
                        round);
                    if (volume.Status == OperationStatuses.Completed && volume.Verified)
                    {
                        int observed = volume.Result!.Value.GetProperty("final")
                            .GetProperty("volumePercent").GetInt32();
                        Assert.That(Math.Abs(observed - target), Is.LessThanOrEqualTo(2));
                    }
                }

                OperationResponse note = await SendAsync(
                    session,
                    "note.create",
                    $$"""{"title":"Goal05 live {{round}}","content":"core-jsonl"}""",
                    live,
                    log,
                    round);
                Assert.That(note.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(note.Verified, Is.True);
                string noteId = note.Result!.Value.GetProperty("noteId").GetString()!;
                OperationResponse read = await SendAsync(
                    session,
                    "note.read",
                    $$"""{"noteId":"{{noteId}}"}""",
                    live,
                    log,
                    round);
                Assert.That(read.Result!.Value.GetProperty("content").GetString(), Is.EqualTo("core-jsonl"));

                OperationResponse opened = await SendAsync(
                    session,
                    "app.open",
                    """{"appId":"windows.notepad"}""",
                    live,
                    log,
                    round);
                if (opened.Status == OperationStatuses.Completed && opened.Verified)
                {
                    bool already = opened.Result!.Value.GetProperty("alreadyRunning").GetBoolean();
                    int processId = opened.Result.Value.GetProperty("processId").GetInt32();
                    if (!already)
                    {
                        launchedNotepadPid = processId;
                    }
                }

                _ = await SendAsync(session, "app.status", "{}", live, log, round);
                _ = await SendAsync(session, "app.installed", """{"name":"notepad"}""", live, log, round);
                _ = await SendAsync(session, "system.time", "{}", live, log, round);
                _ = await SendAsync(session, "system.identity", "{}", live, log, round);
                _ = await SendAsync(session, "system.status", """{"scope":"summary"}""", live, log, round);
                _ = await SendAsync(session, "system.process.list", """{"limit":5,"sort":"name"}""", live, log, round);
                _ = await SendAsync(session, "network.status", "{}", live, log, round);
                _ = await SendAsync(session, "window.active", "{}", live, log, round);
                _ = await SendAsync(
                    session,
                    "window.resolve",
                    """{"process":"notepad","limit":5}""",
                    live,
                    log,
                    round);
                _ = await SendAsync(
                    session,
                    "window.application.status",
                    """{"name":"notepad"}""",
                    live,
                    log,
                    round);
            }

            _ = await SendAsync(session, "network.dns.status", "{}", live, log, round: 0);
            _ = await SendAsync(session, "network.ip.list", "{}", live, log, round: 0);
            _ = await SendAsync(session, "network.port.list", """{"limit":5}""", live, log, round: 0);
            _ = await SendAsync(
                session,
                "system.settings.status",
                """{"setting":"brightness"}""",
                live,
                log,
                round: 0);

            if (launchedNotepadPid is int launchedPid)
            {
                OperationResponse resolved = await SendAsync(
                    session,
                    "window.resolve",
                    """{"process":"notepad","limit":20}""",
                    live,
                    log,
                    round: 0);
                if (resolved.Status == OperationStatuses.Completed
                    && resolved.Result is { } resolvedResult
                    && resolvedResult.TryGetProperty("windows", out JsonElement windows))
                {
                    foreach (JsonElement window in windows.EnumerateArray())
                    {
                        if (window.GetProperty("processId").GetInt32() != launchedPid)
                        {
                            continue;
                        }

                        string windowId = window.GetProperty("windowId").GetString()!;
                        OperationResponse closed = await SendAsync(
                            session,
                            "app.close",
                            $$"""{"windowId":"{{windowId}}"}""",
                            live,
                            log,
                            round: 0);
                        if (closed.Status == OperationStatuses.Completed)
                        {
                            launchedNotepadPid = null;
                        }

                        break;
                    }
                }
            }

            originalClipboard = await TryReadClipboardAsync(session, live, log);
            OperationResponse written = await SendAsync(
                session,
                "clipboard.write.text",
                """{"text":"baxy-goal05-clipboard"}""",
                live,
                log,
                round: 0);
            if (written.Status == OperationStatuses.Completed)
            {
                OperationResponse reread = await SendAsync(
                    session,
                    "clipboard.read.text",
                    """{"maxCharacters":64}""",
                    live,
                    log,
                    round: 0);
                if (reread.Status == OperationStatuses.Completed)
                {
                    Assert.That(
                        reread.Result!.Value.GetProperty("text").GetString(),
                        Is.EqualTo("baxy-goal05-clipboard"));
                }
            }

            _ = await SendAsync(session, "capture.screenshot", "{}", live, log, round: 0);

            if (originalVolume is int level)
            {
                _ = await SendAsync(
                    session,
                    "audio.volume",
                    $$"""{"level":{{level}}}""",
                    live,
                    log,
                    round: 0);
            }

            if (originalClipboard is not null)
            {
                _ = await SendAsync(
                    session,
                    "clipboard.write.text",
                    JsonSerializer.Serialize(new { text = originalClipboard }),
                    live,
                    log,
                    round: 0);
            }
        }
        finally
        {
            CloseLaunchedNotepad(launchedNotepadPid);
        }

        PublishMatrix(live, log.ToString());
        Assert.That(
            live.Count,
            Is.GreaterThan(4),
            "Live Core did not exercise the restorable subset.");
    }

    private static async Task<OperationResponse> SendAsync(
        Goal05CoreSession session,
        string operation,
        string arguments,
        List<object> live,
        StringBuilder log,
        int round)
    {
        OperationRequest request = new(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            operation,
            JsonDocument.Parse(arguments).RootElement.Clone());
        OperationResponse response = await session.SendAsync(request);
        if (response.Status == OperationStatuses.Pending
            && string.Equals(response.ErrorCode, "confirmation_required", StringComparison.Ordinal)
            && response.Result is { } challenge)
        {
            string token = challenge.GetProperty("token").GetString()!;
            response = await session.SendAsync(request with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                ConfirmationToken = token,
            });
        }

        live.Add(new
        {
            operation,
            round,
            status = response.Status,
            verified = response.Verified,
            errorCode = response.ErrorCode,
            effectMayHaveOccurred = response.EffectMayHaveOccurred,
            messageStartsListo = response.Message.StartsWith("Listo", StringComparison.Ordinal),
        });
        log.Append("round=").Append(round)
            .Append(" op=").Append(operation)
            .Append(" status=").Append(response.Status)
            .Append(" verified=").Append(response.Verified)
            .Append(" error=").Append(response.ErrorCode)
            .AppendLine();
        return response;
    }

    private static async Task<string?> TryReadClipboardAsync(
        Goal05CoreSession session,
        List<object> live,
        StringBuilder log)
    {
        OperationResponse response = await SendAsync(
            session,
            "clipboard.read.text",
            """{"maxCharacters":4096}""",
            live,
            log,
            round: 0);
        if (response.Status != OperationStatuses.Completed || response.Result is null)
        {
            return null;
        }

        return response.Result.Value.TryGetProperty("text", out JsonElement text)
            ? text.GetString()
            : null;
    }

    private static void CloseLaunchedNotepad(int? processId)
    {
        if (processId is not int pid)
        {
            return;
        }

        try
        {
            using var process = Process.GetProcessById(pid);
            if (process.HasExited || !string.Equals(process.ProcessName, "notepad", StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            process.CloseMainWindow();
            if (!process.WaitForExit(2000))
            {
                process.Kill(entireProcessTree: true);
                process.WaitForExit(2000);
            }
        }
        catch (Exception)
        {
            // Best-effort restore: do not leave a notepad this session launched.
        }
    }

    private static void PublishMatrix(List<object> live, string log)
    {
        var rows = Goal05CatalogObservation.ClassifyCatalog()
            .Select(row => new
            {
                row.Operation,
                row.VerifierContractId,
                row.Risk,
                row.Observation,
                row.Verdict,
                row.Surface,
                row.Reason,
            })
            .ToArray();
        var report = new
        {
            schema = "baxy.goal05-execution-matrix.v1",
            measuredAtUtc = DateTimeOffset.UtcNow.ToString("O"),
            catalogOperations = rows.Length,
            observed = rows.Count(row => row.Verdict == "observed"),
            unverifiable = rows.Count(row => row.Verdict == "unverifiable"),
            liveRuns = live,
            rows,
        };
        string json = JsonSerializer.Serialize(report, JsonOptions) + Environment.NewLine;
        Goal05Scratch.Write("execution-matrix.json", json);
        Goal05Scratch.Write("matrix-run.log", log);
        string? repo = FindRepoRoot();
        if (repo is not null)
        {
            string published = Path.Combine(repo, "documentacion", "base", "05_MATRIZ_EJECUCION.json");
            Directory.CreateDirectory(Path.GetDirectoryName(published)!);
            File.WriteAllText(published, json);
        }
    }

    private static string? FindRepoRoot()
    {
        string? directory = AppContext.BaseDirectory;
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory, "Baxy.slnx")))
            {
                return directory;
            }

            directory = Path.GetDirectoryName(directory);
        }

        return null;
    }

    private static OperationInvocation Invocation(string operation, string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(json).RootElement.Clone());
}

internal sealed class Goal05CoreSession : IAsyncDisposable
{
    private readonly Process _process;
    private readonly Task<string> _stderr;

    private Goal05CoreSession(Process process, Task<string> stderr)
    {
        _process = process;
        _stderr = stderr;
    }

    public static async Task<Goal05CoreSession> StartAsync(string dataRoot)
    {
        string corePath = Path.Combine(AppContext.BaseDirectory, "baxy-core.dll");
        Assert.That(File.Exists(corePath), Is.True, $"Core binary missing at {corePath}");
        var startInfo = new ProcessStartInfo
        {
            FileName = Environment.GetEnvironmentVariable("DOTNET_HOST_PATH") ?? "dotnet",
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardInputEncoding = new UTF8Encoding(false, true),
            StandardOutputEncoding = new UTF8Encoding(false, true),
            StandardErrorEncoding = new UTF8Encoding(false, true),
        };
        startInfo.ArgumentList.Add(corePath);
        startInfo.Environment["BAXY_DATA_DIR"] = dataRoot;
        startInfo.Environment["DOTNET_NOLOGO"] = "1";
        var process = new Process { StartInfo = startInfo };
        Assert.That(process.Start(), Is.True);
        Task<string> stderr = process.StandardError.ReadToEndAsync();
        try
        {
            _ = await ReadRequiredLineAsync(process).ConfigureAwait(false);
            return new Goal05CoreSession(process, stderr);
        }
        catch
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }

            process.Dispose();
            throw;
        }
    }

    public async Task<OperationResponse> SendAsync(OperationRequest request)
    {
        byte[] payload = ProtocolJson.SerializeToUtf8Bytes(request);
        await _process.StandardInput.WriteLineAsync(Encoding.UTF8.GetString(payload)).ConfigureAwait(false);
        await _process.StandardInput.FlushAsync().ConfigureAwait(false);
        string line = await ReadRequiredLineAsync(_process).ConfigureAwait(false);
        return ProtocolJson.DeserializeResponse(Encoding.UTF8.GetBytes(line));
    }

    public async ValueTask DisposeAsync()
    {
        if (!_process.HasExited)
        {
            _process.StandardInput.Close();
            try
            {
                await _process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(5)).ConfigureAwait(false);
            }
            catch (TimeoutException)
            {
                _process.Kill(entireProcessTree: true);
                await _process.WaitForExitAsync().ConfigureAwait(false);
            }
        }

        string stderr = await _stderr.ConfigureAwait(false);
        int exitCode = _process.ExitCode;
        _process.Dispose();
        Assert.That(exitCode, Is.Zero, stderr);
    }

    private static async Task<string> ReadRequiredLineAsync(Process process)
    {
        string? line = await process.StandardOutput
            .ReadLineAsync()
            .WaitAsync(TimeSpan.FromSeconds(30))
            .ConfigureAwait(false);
        if (line is null)
        {
            throw new EndOfStreamException("BAXY core closed stdout unexpectedly.");
        }

        return line;
    }
}
