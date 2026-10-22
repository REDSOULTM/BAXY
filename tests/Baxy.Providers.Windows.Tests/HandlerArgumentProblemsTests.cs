using System.Reflection;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Network;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// P5.3 (errores accionables): a handler that refuses its arguments says which and what is wrong with each, in the
/// kernel's own shape (<see cref="ArgumentProblem"/>), so the model can correct the call in one turn; nothing past the
/// refusal is touched (the stores and providers here throw if reached).
/// </summary>
[TestFixture]
public sealed class HandlerArgumentProblemsTests
{
    [TestCase("https://example.com/page")]
    [TestCase("example .com")]
    public async Task APingToAUrlNamesTheHost(string host)
    {
        OperationOutcome outcome = await new NetworkPingHandler(Unreached<INetworkDiagnosticProvider>())
            .ExecuteAsync(Invocation(JsonSerializer.Serialize(new { host })), CancellationToken.None);

        ArgumentProblem problem = outcome.ArgumentProblems.Single();
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(problem.Name, Is.EqualTo("host"));
            Assert.That(problem.Problem, Is.EqualTo("expected a host name or an IP address, not a URL"));
        });
    }

    [TestCase("{}")]
    [TestCase("""{"noteId":"8d7f6f0e-3c55-4a43-9a3c-6f1f0b0e4b11","title":"Compras"}""")]
    public async Task ANoteIsSelectedByExactlyOneOfItsIdAndItsTitle(string arguments)
    {
        OperationOutcome outcome = await new ReadNoteHandler(Unreached<INoteStore>())
            .ExecuteAsync(Invocation(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(outcome.ArgumentProblems.Single().OneOf, Is.EqualTo(new[] { "noteId", "title" }));
        });
    }

    [Test]
    public async Task ASnapshotGoesOnlyWithTheNoteId()
    {
        OperationOutcome outcome = await new ReadNoteHandler(Unreached<INoteStore>())
            .ExecuteAsync(Invocation("""{"title":"Compras","expectedRevision":2,"expectedIsTrashed":false}"""),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(outcome.ArgumentProblems.Select(static problem => problem.Name),
                Is.EqualTo(new[] { "expectedRevision", "expectedIsTrashed" }));
            Assert.That(outcome.ArgumentProblems.Select(static problem => problem.Problem).Distinct(),
                Is.EqualTo(new[] { "only with noteId" }));
        });
    }

    [Test]
    public async Task AnIncompleteSnapshotNamesWhatItLacks()
    {
        OperationOutcome outcome = await new ReadNoteHandler(Unreached<INoteStore>())
            .ExecuteAsync(Invocation("""{"noteId":"8d7f6f0e-3c55-4a43-9a3c-6f1f0b0e4b11","expectedRevision":2}"""),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(outcome.ArgumentProblems.Select(static problem => problem.Name),
                Is.EqualTo(new[] { "expectedTitle", "expectedIsTrashed" }));
            Assert.That(outcome.ArgumentProblems.Select(static problem => problem.Problem).Distinct(),
                Is.EqualTo(new[] { "required and missing" }));
        });
    }

    // A handler's own check of what its schema already says is answered with the schema's problem, nearest included.
    [Test]
    public async Task AHandlersCheckOfItsSchemaNamesTheSchemasProblem()
    {
        OperationOutcome sort = await new ProcessListHandler(Unreached<IProcessStatusProvider>())
            .ExecuteAsync(Invocation("""{"sort":"mem"}"""), CancellationToken.None);
        OperationOutcome level = await new AudioVolumeHandler(Unreached<IAudioControlProvider>())
            .ExecuteAsync(Invocation("""{"level":101}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sort.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(sort.ArgumentProblems.Single().Name, Is.EqualTo("sort"));
            Assert.That(sort.ArgumentProblems.Single().Nearest, Is.EqualTo("memory"));
            Assert.That(sort.ArgumentProblems.Single().Allowed, Is.EqualTo(new[] { "cpu", "memory", "name" }));
            Assert.That(level.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(level.ArgumentProblems.Single().Name, Is.EqualTo("level"));
            Assert.That(level.ArgumentProblems.Single().Problem, Does.StartWith("expected an integer from 0 to 100"));
        });
    }

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", JsonDocument.Parse(arguments).RootElement.Clone());

    private static T Unreached<T>() where T : class => DispatchProxy.Create<T, UnreachedProxy>();

    public class UnreachedProxy : DispatchProxy
    {
        protected override object? Invoke(MethodInfo? targetMethod, object?[]? args) =>
            throw new InvalidOperationException("reached past the refusal: " + targetMethod?.Name);
    }
}
