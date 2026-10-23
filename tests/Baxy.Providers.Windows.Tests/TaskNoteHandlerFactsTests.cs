using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (w5): a task or note refused for its target says what the store holds there now, and a deletion
/// whose target is not there fails before the person is asked for a yes.
/// </summary>
[TestFixture]
public sealed class TaskNoteHandlerFactsTests
{
    // A task.complete retried after it was done (its version moved) came back a bare task_version_conflict; it says the
    // task is completed at its version now, and that nothing was changed.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AStaleTaskVersionSaysTheTaskAsItIsNow(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        LocalTaskRecord created = store.Create("Comprar pan", string.Empty, null);
        store.SetCompleted(created.Id, created.Version, true);

        OperationOutcome outcome = await new CompleteTaskHandler(store).ExecuteAsync(
            Invocation($$"""{"taskId":"{{created.Id:D}}","expectedVersion":{{created.Version}}}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("task_version_conflict"));
            JsonElement current = outcome.Result!.Value.GetProperty("current");
            Assert.That(current.GetProperty("completed").GetBoolean(), Is.True);
            Assert.That(current.GetProperty("version").GetInt64(), Is.EqualTo(created.Version + 1));
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo(
                    $"nothing was changed: the task is completed at version {created.Version + 1} now"));
            }
        });
    }

    // An id no task has says where it was looked (deleted ones included) and where the ids are.
    [Test]
    public async Task AnUnknownTaskIdSaysNoTaskHasIt()
    {
        using IDisposable setting = ModelAids.Use("all");
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        store.Create("Comprar pan", string.Empty, null);

        OperationOutcome outcome = await new CompleteTaskHandler(store).ExecuteAsync(
            Invocation("""{"taskId":"8f1d2c3b-0a4e-4f5d-9c6b-7a8e9f0a1b2c","expectedVersion":1}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("task_not_found"));
            Assert.That(outcome.Result!.Value.GetProperty("searched").GetString(), Is.EqualTo("active and deleted tasks"));
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Does.Contain("task.search or task.list"));
        });
    }

    // A task.delete (it asks the person's yes) whose label is not the task's title failed only after the yes; it fails
    // before asking, saying the exact title, and a matching one goes on to ask.
    [Test]
    public async Task ATaskDeleteWhoseLabelIsNotTheTitleFailsBeforeTheYes()
    {
        using IDisposable setting = ModelAids.Use("all");
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        LocalTaskRecord created = store.Create("Comprar pan", string.Empty, null);
        var handler = new DeleteTaskHandler(store);

        InvocationPreflightResult wrong = await Preflight(handler,
            Json($$"""{"taskId":"{{created.Id:D}}","expectedVersion":1,"reviewLabel":"comprar pan"}"""),
            CancellationToken.None);
        InvocationPreflightResult right = await Preflight(handler,
            Json($$"""{"taskId":"{{created.Id:D}}","expectedVersion":1,"reviewLabel":"Comprar pan"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(wrong.Failure?.ErrorCode, Is.EqualTo("task_version_conflict"));
            Assert.That(wrong.Failure?.EffectMayHaveOccurred, Is.False);
            Assert.That(wrong.Failure?.Result?.GetProperty("next").GetString(),
                Is.EqualTo("nothing was changed: reviewLabel must be the task's exact title, \"Comprar pan\""));
            Assert.That(right, Is.SameAs(InvocationPreflightResult.Proceed));
            Assert.That(store.Read(created.Id).Deleted, Is.False);
        });
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-task-note-facts-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    // Read through the interface the engine reads a handler by.
    private static ValueTask<InvocationPreflightResult> Preflight(
        object handler, JsonElement arguments, CancellationToken cancellationToken) =>
        ((IInvocationPreflight)handler).PreflightAsync(arguments, cancellationToken);

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", Json(arguments));
}
