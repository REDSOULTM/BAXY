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
            Func<Task> turn = static () => throw new KeyNotFoundException("la clave de Ñuñoa");

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
                Assert.That(File.ReadAllText(log), Does.Not.Contain("Ñuñoa"));
            });
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
