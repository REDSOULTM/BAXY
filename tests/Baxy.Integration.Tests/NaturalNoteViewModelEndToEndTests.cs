using System.Text.Json;
using Baxy.App;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class NaturalNoteViewModelEndToEndTests
{
    [Test]
    public async Task NaturalConversationCompletesTheDurableNoteLifecycleWithoutJson()
    {
        string root = PrivateDataRootTestSupport.NewPath("natural-note-e2e");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);

        try
        {
            await using (var viewModel = new MainWindowViewModel(
                static route => route.ResolveStandaloneOperation()))
            {
                await viewModel.InitializeAsync(CancellationToken.None);
                Assert.That(viewModel.IsReady, Is.True);

                string created = await SubmitAsync(
                    viewModel,
                    "Crea una nota llamada Compras con leche y pan");
                Assert.That(created, Does.Contain("note.create"));

                string read = await SubmitAsync(
                    viewModel,
                    "read the note called Compras");
                Assert.That(read, Does.Contain("note.read"));
                Assert.That(read, Does.Contain("leche y pan"));

                string trashed = await SubmitAsync(
                    viewModel,
                    "delete the note called Compras");
                Assert.That(trashed, Does.Contain("note.trash"));

                string trashedList = await SubmitAsync(
                    viewModel,
                    "show me my trashed notes");
                Assert.That(trashedList, Does.Contain("note.list"));

                string restored = await SubmitAsync(
                    viewModel,
                    "restaura la nota Compras de la papelera");
                Assert.That(restored, Does.Contain("note.restore"));

                string activeList = await SubmitAsync(viewModel, "muéstrame mis notas");
                Assert.That(activeList, Does.Contain("note.list"));

                Assert.That(
                    viewModel.Messages.Where(static message => !message.IsUser),
                    Has.None.Matches<ConversationMessage>(static message =>
                        (message.Body.TrimStart().StartsWith('{')
                            && !UserMessagePolicy.IsStructuredFacts(message.Body))
                        || message.Body.TrimStart().StartsWith('[')));
            }

            var independentStore = new LocalNoteStore(Path.Combine(root, "notes-store"));
            NoteRecord[] notes = independentStore.List(NoteListScope.All).ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(notes, Has.Length.EqualTo(1));
                Assert.That(notes[0].Title, Is.EqualTo("Compras"));
                Assert.That(notes[0].Content, Is.EqualTo("leche y pan"));
                Assert.That(notes[0].IsTrashed, Is.False);
                Assert.That(notes[0].Revision, Is.EqualTo(3));
            });

            string outboxPath = Path.Combine(root, "shell", "retry-outbox.v1.json");
            using JsonDocument outbox = JsonDocument.Parse(await File.ReadAllTextAsync(outboxPath));
            Assert.That(outbox.RootElement.GetProperty("entries").GetArrayLength(), Is.Zero);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static async Task<string> SubmitAsync(
        MainWindowViewModel viewModel,
        string text)
    {
        int previousCount = viewModel.Messages.Count;
        viewModel.Draft = text;
        await viewModel.SubmitAsync(CancellationToken.None);

        ConversationMessage[] added = viewModel.Messages.Skip(previousCount).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(added, Has.Length.EqualTo(2));
            Assert.That(added[0].IsUser, Is.True);
            Assert.That(added[0].Body, Is.EqualTo(text));
            Assert.That(added[1].IsUser, Is.False);
            Assert.That(added[1].Speaker, Is.EqualTo("BAXY"));
        });
        return added[1].Body;
    }
}
