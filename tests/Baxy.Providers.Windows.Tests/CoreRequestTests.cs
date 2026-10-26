using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// H9 (engine_no_answer opening Steam cold): a provider's IOException («Window content capture came back black») left the
/// engine, as the engine lets an unexpected one go with the invocation started, and the core's loop let it end the core
/// (exit 70): the App saw the channel closed and the turn was lost. The core answers that request failed with its effect
/// uncertain and reads the next; what must still stop it (its own cancellation, the journal's integrity and capacity)
/// still does.
/// </summary>
[TestFixture]
public sealed class CoreRequestTests
{
    private const string PersonalDetail = "C:\\Users\\persona\\Documentos\\carta.docx";

    [Test]
    public async Task AHandlerThatThrowsIsAnsweredFailedWithItsEffectUncertainAndStaysStarted()
    {
        var handler = new ThrowingHandler(() => new IOException("Window content capture came back black " + PersonalDetail));
        await using var core = await Core.OpenAsync(handler);
        OperationRequest request = Request();

        OperationResponse response = await CoreRequest.ExecuteAsync(
            core.Engine, request, core.Diagnostics, CancellationToken.None);
        string? started = await core.Journal.FindStartedFingerprintAsync(request.InvocationId, CancellationToken.None);
        CompletedInvocation? completed = await core.Journal.FindCompletedAsync(request.InvocationId, CancellationToken.None);
        using JsonDocument facts = JsonDocument.Parse(response.Message);
        byte[] line = ProtocolJson.SerializeBoundedToUtf8Bytes(response, 1024 * 1024);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.Verified, Is.False);
            Assert.That(response.Replayed, Is.False);
            Assert.That(response.ErrorCode, Is.EqualTo(CoreRequest.UnexpectedFailureCode));
            Assert.That(response.EffectMayHaveOccurred, Is.True);
            Assert.That(response.CauseCode, Is.EqualTo(nameof(IOException)));
            Assert.That(response.Result, Is.Null);
            Assert.That(response.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(response.RequestId, Is.EqualTo(request.RequestId));
            // What the model reads: the code, the cause and that the effect is uncertain; never the exception's text.
            Assert.That(facts.RootElement.GetProperty("status").GetString(), Is.EqualTo(OperationStatuses.Failed));
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo(CoreRequest.UnexpectedFailureCode));
            Assert.That(facts.RootElement.GetProperty("cause").GetString(), Is.EqualTo(nameof(IOException)));
            Assert.That(facts.RootElement.GetProperty("effectUncertain").GetBoolean(), Is.True);
            Assert.That(response.Message, Does.Not.Contain("persona").And.Not.Contain("black"));
            Assert.That(line, Is.Not.Empty);
            // The journal keeps the start and no terminal: the effect may stand.
            Assert.That(started, Is.EqualTo(RequestFingerprint.Compute(request)));
            Assert.That(completed, Is.Null);
            // One line to stderr, with the type and without the exception's text.
            Assert.That(core.Diagnostics.ToString(), Does.Contain(nameof(IOException)));
            Assert.That(core.Diagnostics.ToString(), Does.Not.Contain("persona").And.Not.Contain("black"));
            Assert.That(core.Diagnostics.ToString().TrimEnd().Split('\n'), Has.Length.EqualTo(1));
        });
    }

    // Decisión del dueño 2026-10-25 («que Baxy no te moleste todo el tiempo… sino para cosas que realmente son
    // peligrosas»): the retry of an app.open that threw (low reversible, nothing in its arguments asks) runs again
    // without asking to reconcile it (it asked before); the next request runs too.
    [Test]
    public async Task TheRetryOfAReversibleInvocationThatThrewRunsAndTheNextRequestRuns()
    {
        var handler = new ThrowingHandler(() => new IOException("Window content capture came back black"), times: 1);
        await using var core = await Core.OpenAsync(handler);
        OperationRequest request = Request();

        OperationResponse failed = await CoreRequest.ExecuteAsync(
            core.Engine, request, core.Diagnostics, CancellationToken.None);
        OperationResponse retry = await CoreRequest.ExecuteAsync(
            core.Engine, request with { RequestId = Guid.NewGuid().ToString("D") }, core.Diagnostics, CancellationToken.None);
        OperationResponse next = await CoreRequest.ExecuteAsync(
            core.Engine, Request(), core.Diagnostics, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(failed.ErrorCode, Is.EqualTo(CoreRequest.UnexpectedFailureCode));
            Assert.That(retry.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(next.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.ExecutionCount, Is.EqualTo(3));
        });
    }

    // A provider's own timeout (a cancellation the core did not ask for) is a failure of that request like any other.
    [Test]
    public async Task ACancellationTheCoreDidNotAskForIsAnswered()
    {
        var handler = new ThrowingHandler(() => new TaskCanceledException("provider deadline"));
        await using var core = await Core.OpenAsync(handler);

        OperationResponse response = await CoreRequest.ExecuteAsync(
            core.Engine, Request(), core.Diagnostics, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo(CoreRequest.UnexpectedFailureCode));
            Assert.That(response.CauseCode, Is.EqualTo(nameof(TaskCanceledException)));
            Assert.That(response.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task TheCoresOwnCancellationStillLeaves()
    {
        using var shutdown = new CancellationTokenSource();
        var handler = new ThrowingHandler(() =>
        {
            shutdown.Cancel();
            return new OperationCanceledException(shutdown.Token);
        });
        await using var core = await Core.OpenAsync(handler);

        Assert.That(
            async () => await CoreRequest.ExecuteAsync(core.Engine, Request(), core.Diagnostics, shutdown.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(core.Diagnostics.ToString(), Is.Empty);
    }

    // Both are IOExceptions: a journal that cannot be trusted or cannot record stops the core as before (exit 74, 70).
    [Test]
    public async Task TheJournalsIntegrityStillLeaves()
    {
        await using var core = await Core.OpenAsync(new ThrowingHandler(() => new JournalIntegrityException("bad")));

        Assert.That(
            async () => await CoreRequest.ExecuteAsync(core.Engine, Request(), core.Diagnostics, CancellationToken.None),
            Throws.TypeOf<JournalIntegrityException>());
        Assert.That(core.Diagnostics.ToString(), Is.Empty);
    }

    [Test]
    public async Task TheJournalsCapacityStillLeaves()
    {
        await using var core = await Core.OpenAsync(new ThrowingHandler(() => new JournalCapacityException("full")));

        Assert.That(
            async () => await CoreRequest.ExecuteAsync(core.Engine, Request(), core.Diagnostics, CancellationToken.None),
            Throws.TypeOf<JournalCapacityException>());
        Assert.That(core.Diagnostics.ToString(), Is.Empty);
    }

    // Revisión del núcleo (q-core): a response the protocol refuses (a handler's error code out of the protocol's
    // alphabet) threw JsonException from the core's write, out of the loop, and ended the core (exit 70) after the effect.
    // That request is answered failed with its effect uncertain, and the core reads the next.
    [Test]
    public async Task AResponseTheProtocolRefusesIsAnsweredFailedInsteadOfEndingTheCore()
    {
        await using var core = await Core.OpenAsync(new AnsweringHandler(OperationOutcome.Failure("Access-Denied")));
        OperationRequest request = Request();

        OperationResponse response = await CoreRequest.ExecuteAsync(
            core.Engine, request, core.Diagnostics, CancellationToken.None);
        OperationResponse answered = ProtocolJson.DeserializeResponse(
            CoreRequest.ToLine(request, response, 1024 * 1024, core.Diagnostics));

        Assert.Multiple(() =>
        {
            Assert.That(answered.RequestId, Is.EqualTo(request.RequestId));
            Assert.That(answered.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(answered.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(answered.ErrorCode, Is.EqualTo(CoreRequest.UnexpectedFailureCode));
            Assert.That(answered.EffectMayHaveOccurred, Is.True);
        });
    }

    private sealed class AnsweringHandler(OperationOutcome outcome) : IOperationHandler
    {
        public OperationDefinition Definition { get; } = new(ProductCatalog.GetRequired("app.open"));

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
            ValueTask.FromResult(outcome);
    }

    private static OperationRequest Request() => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "app.open",
        JsonSerializer.SerializeToElement(new { appId = "Steam" }));

    private sealed class Core : IAsyncDisposable
    {
        private readonly string _root;

        private Core(string root, FileInvocationJournal journal, MissionEngine engine)
        {
            _root = root;
            Journal = journal;
            Engine = engine;
        }

        public FileInvocationJournal Journal { get; }

        public MissionEngine Engine { get; }

        public StringWriter Diagnostics { get; } = new();

        public static async Task<Core> OpenAsync(IOperationHandler handler)
        {
            string root = Path.Combine(Path.GetTempPath(), "baxy-core-request-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                Path.Combine(root, "journal.jsonl"),
                new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
            return new Core(root, journal, new MissionEngine(new OperationRegistry([handler]), journal));
        }

        public async ValueTask DisposeAsync()
        {
            Engine.Dispose();
            await Journal.DisposeAsync();
            Diagnostics.Dispose();
            Directory.Delete(_root, recursive: true);
        }
    }

    /// <summary>app.open whose first <paramref name="times"/> runs throw what <paramref name="failure"/> makes, then
    /// succeed verified.</summary>
    private sealed class ThrowingHandler(Func<Exception> failure, int times = int.MaxValue) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } = new(ProductCatalog.GetRequired("app.open"));

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
        {
            ExecutionCount++;
            if (ExecutionCount <= times)
            {
                throw failure();
            }

            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }
}
