using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría del Core (w8): task.create kept no key of its invocation, so the same invocation run again (the core ended
/// after the task was written and before the journal closed it) made a second task. It is keyed by the invocation now,
/// as note.create: the same invocation finds the task it made.
/// </summary>
[TestFixture]
public sealed class TaskCreateIdempotencyTests
{
    [Test]
    public async Task TheSameInvocationRunAgainGivesBackTheTaskItMade()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        var handler = new CreateTaskHandler(store);

        OperationOutcome first = await handler.ExecuteAsync(Invocation("i-1", "Comprar pan"), CancellationToken.None);
        OperationOutcome again = await handler.ExecuteAsync(Invocation("i-1", "Comprar pan"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Succeeded && again.Succeeded, Is.True, again.ErrorCode);
            Assert.That(again.Result!.Value.GetProperty("taskId").GetString(),
                Is.EqualTo(first.Result!.Value.GetProperty("taskId").GetString()));
            Assert.That(store.List(TaskListStatus.All, includeDeleted: true, limit: 50).MatchCount, Is.EqualTo(1));
        });
    }

    // Contracases: another invocation is another task; the same invocation with another task is a conflict, named, and
    // writes nothing.
    [Test]
    public async Task AnotherInvocationIsAnotherTaskAndTheSameOneWithAnotherTaskIsAConflict()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        var handler = new CreateTaskHandler(store);

        await handler.ExecuteAsync(Invocation("i-1", "Comprar pan"), CancellationToken.None);
        OperationOutcome other = await handler.ExecuteAsync(Invocation("i-2", "Comprar pan"), CancellationToken.None);
        OperationOutcome conflict = await handler.ExecuteAsync(Invocation("i-1", "Pagar la luz"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(other.Succeeded, Is.True, other.ErrorCode);
            Assert.That(conflict.Succeeded, Is.False);
            Assert.That(conflict.ErrorCode, Is.EqualTo("idempotency_conflict"));
            Assert.That(conflict.EffectMayHaveOccurred, Is.False);
            Assert.That(store.List(TaskListStatus.All, includeDeleted: true, limit: 50).MatchCount, Is.EqualTo(2));
        });
    }

    private static OperationInvocation Invocation(string invocationId, string title) =>
        new("request", "mission", invocationId, JsonSerializer.SerializeToElement(new { title }));

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-task-tests", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true);
        }
    }
}
