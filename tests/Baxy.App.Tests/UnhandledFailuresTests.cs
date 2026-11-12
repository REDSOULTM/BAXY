using System.IO;
using System.Reflection;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// What nothing caught (src/Baxy.App/UnhandledFailures.cs, MainWindowViewModel.RunGatedTurnAsync): a turn that throws
/// any exception ends as a failed turn and BAXY goes on; the exception is recorded by its type and method, never its
/// message (auditoría de la App, 2026-10-23).
/// </summary>
[TestFixture]
public sealed class UnhandledFailuresTests
{
    [Test]
    public async Task ATurnThatThrowsAnyExceptionEndsAsAFailedTurnAndIsRecorded()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel { Sound = static _ => { } };
        await using (viewModel)
        {
            MethodInfo run = typeof(MainWindowViewModel).GetMethod("RunTurnAsync",
                BindingFlags.Instance | BindingFlags.NonPublic)!;
            Func<Task> turn = static () => throw new KeyNotFoundException("la clave de Viña");

            await (Task)run.Invoke(viewModel, ["hola", turn, CancellationToken.None, null])!;

            string log = Path.Combine(fake.DataRoot, "diagnostics", "unhandled.v1.jsonl");
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.LastTurnFailure, Is.EqualTo("turn_failed"));
                Assert.That(viewModel.IsBusy, Is.False);
                Assert.That(File.Exists(log), Is.True);
            });
            JsonNode? line = JsonNode.Parse(File.ReadLines(log).Last());
            Assert.Multiple(() =>
            {
                Assert.That((string?)line?["source"], Is.EqualTo("turn"));
                Assert.That((string?)line?["type"], Is.EqualTo(typeof(KeyNotFoundException).FullName));
                Assert.That(File.ReadAllText(log), Does.Not.Contain("Viña"));
            });
        }
    }

    [TestCase("startup", "UnsafePrivateStoragePathException", "PreparePrivateDataRoot")]
    [TestCase("dispatcher", "InvalidOperationException", "<Main>b__0")]
    [TestCase("dispatcher", null, "unknown")]
    public void TheTraceKeepsWhatFailedInsteadOfInvalid(string source, string? type, string site)
    {
        string detail = UnhandledFailures.TraceDetail(source, type, site);

        Assert.Multiple(() =>
        {
            Assert.That(ShellTrace.SanitizeLabel(detail), Is.EqualTo(detail));
            Assert.That(detail, Does.StartWith(source + "."));
        });
    }

    // REV_APP ASY-b (2026-11-09): a task started and left («_ = …Async()») that failed was recorded only when the
    // collector found it, as «task», which may be never before BAXY closes. Watched, it is recorded when it fails.
    [Test]
    public void ATaskNobodyAwaitsIsRecordedUnderItsNameWhenItFails()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        try
        {
            var failing = new TaskCompletionSource();
            var cancelled = new TaskCompletionSource();
            var done = new TaskCompletionSource();
            UnhandledFailures.Watch(failing.Task, "conversation.save", folder);
            UnhandledFailures.Watch(cancelled.Task, "conversation.name", folder);
            UnhandledFailures.Watch(done.Task, "conversation.name", folder);
            string log = Path.Combine(folder, "unhandled.v1.jsonl");

            cancelled.SetCanceled();
            done.SetResult();
            Assert.That(File.Exists(log), Is.False, "a task that ended or was cancelled is no failure");

            failing.SetException(new InvalidDataException("la carpeta de alguien"));

            Assert.That(File.Exists(log), Is.True, "recorded when it failed, with no collection in between");
            string text = File.ReadAllText(log);
            JsonNode? line = JsonNode.Parse(text);
            Assert.Multiple(() =>
            {
                Assert.That((string?)line?["source"], Is.EqualTo("conversation.save"));
                Assert.That((string?)line?["type"], Is.EqualTo(typeof(InvalidDataException).FullName));
                Assert.That(text, Does.Not.Contain("alguien"));
            });
        }
        finally
        {
            if (Directory.Exists(folder))
            {
                Directory.Delete(folder, recursive: true);
            }
        }
    }

    [Test]
    public void AnExceptionIsRecordedByItsTypeAndMethodNeverItsMessage()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        try
        {
            Exception thrown;
            try
            {
                throw new InvalidCastException("el secreto.txt de alguien");
            }
            catch (InvalidCastException exception)
            {
                thrown = exception;
            }

            UnhandledFailures.Record("dispatcher", new AggregateException(thrown), folder);

            string text = File.ReadAllText(Path.Combine(folder, "unhandled.v1.jsonl"));
            JsonNode? line = JsonNode.Parse(text);
            Assert.Multiple(() =>
            {
                Assert.That((string?)line?["source"], Is.EqualTo("dispatcher"));
                Assert.That((string?)line?["type"], Is.EqualTo(typeof(InvalidCastException).FullName));
                Assert.That((string?)line?["site"], Is.EqualTo(nameof(AnExceptionIsRecordedByItsTypeAndMethodNeverItsMessage)));
                Assert.That(text, Does.Not.Contain("secreto"));
            });
        }
        finally
        {
            if (Directory.Exists(folder))
            {
                Directory.Delete(folder, recursive: true);
            }
        }
    }
}
