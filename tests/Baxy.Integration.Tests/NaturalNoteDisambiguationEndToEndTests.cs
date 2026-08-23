using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.App;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed partial class NaturalNoteDisambiguationEndToEndTests
{
    [Test]
    public async Task ConversationReadsTrashesAndRestoresTheChosenDuplicateOnly()
    {
        await WithIsolatedDataRootAsync(async root =>
        {
            await using var viewModel = CreateShellPipelineViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);

            _ = await SubmitAsync(viewModel, "Crea una nota llamada Compras con leche");
            _ = await SubmitAsync(viewModel, "create a note called Compras with pan");

            string readPrompt = await SubmitAsync(viewModel, "read the note called Compras");
            AssertPromptIsPrivate(readPrompt, 2);
            int milkChoice = FindChoice(readPrompt, "leche");
            string read = await SubmitAsync(viewModel, $"choose la {milkChoice}");
            Assert.That(read, Does.Contain("note.read"));
            Assert.That(read, Does.Contain("leche"));

            string trashPrompt = await SubmitAsync(viewModel, "delete the note called Compras");
            AssertPromptIsPrivate(trashPrompt, 2);
            int panChoice = FindChoice(trashPrompt, "pan");
            string trashed = await SubmitAsync(viewModel, panChoice.ToString(System.Globalization.CultureInfo.InvariantCulture));
            Assert.That(trashed, Does.Contain("note.trash"));
            Assert.That(trashed, Does.Contain("success"));

            var store = new LocalNoteStore(Path.Combine(root, "notes-store"));
            NoteRecord milk = store.List(NoteListScope.All).Single(static note => note.Content == "leche");
            NoteRecord pan = store.List(NoteListScope.All).Single(static note => note.Content == "pan");
            Assert.Multiple(() =>
            {
                Assert.That(milk.IsTrashed, Is.False);
                Assert.That(milk.Revision, Is.EqualTo(1));
                Assert.That(pan.IsTrashed, Is.True);
                Assert.That(pan.Revision, Is.EqualTo(2));
            });

            string restorePrompt = await SubmitAsync(
                viewModel,
                "restaura la nota Compras de la papelera");
            AssertPromptIsPrivate(restorePrompt, 2);
            int restorePanChoice = FindChoice(restorePrompt, "pan");
            string restored = await SubmitAsync(viewModel, $"the {Ordinal(restorePanChoice)} one");
            Assert.That(restored, Does.Contain("note.restore"));
            Assert.That(restored, Does.Contain("success"));

            NoteRecord[] final = store.List(NoteListScope.All).ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(final, Has.Length.EqualTo(2));
                Assert.That(final, Has.All.Matches<NoteRecord>(static note => !note.IsTrashed));
                Assert.That(final.Single(static note => note.Content == "leche").Revision, Is.EqualTo(1));
                Assert.That(final.Single(static note => note.Content == "pan").Revision, Is.EqualTo(3));
                Assert.That(
                    viewModel.Messages.Where(static message => !message.IsUser),
                    Has.None.Matches<ConversationMessage>(static message =>
                        UuidPattern().IsMatch(message.Body)
                        || (message.Body.TrimStart().StartsWith('{')
                            && !UserMessagePolicy.IsStructuredFacts(message.Body))
                        || message.Body.TrimStart().StartsWith('[')));
            });

            AssertOutboxEmpty(root);
        });
    }

    [Test]
    public async Task CancellationAndANewFullCommandNeverMutateAnOldChoice()
    {
        await WithIsolatedDataRootAsync(async root =>
        {
            await using var viewModel = CreateShellPipelineViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            _ = await SubmitAsync(viewModel, "Crea una nota llamada Ideas con azul");
            _ = await SubmitAsync(viewModel, "Crea una nota llamada Ideas con verde");

            string prompt = await SubmitAsync(viewModel, "borra la nota Ideas");
            AssertPromptIsPrivate(prompt, 2);
            string canceled = await SubmitAsync(viewModel, "never mind");
            Assert.That(canceled, Is.EqualTo("Cancelé la selección. No hice cambios."));

            _ = await SubmitAsync(viewModel, "borra la nota Ideas");
            string replacement = await SubmitAsync(viewModel, "anota nueva tarea");
            Assert.That(replacement, Does.Contain("note.create"));
            Assert.That(replacement, Does.Contain("nueva tarea"));

            string bareNumber = await SubmitAsync(viewModel, "1");
            Assert.That(bareNumber, Is.EqualTo(NaturalNoteRequestParser.Guidance));

            var store = new LocalNoteStore(Path.Combine(root, "notes-store"));
            NoteRecord[] ideas = store.List(NoteListScope.All)
                .Where(static note => note.Title == "Ideas")
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(ideas, Has.Length.EqualTo(2));
                Assert.That(ideas, Has.All.Matches<NoteRecord>(static note => !note.IsTrashed && note.Revision == 1));
                Assert.That(store.List(NoteListScope.All), Has.One.Matches<NoteRecord>(static note => note.Title == "nueva tarea"));
            });
            AssertOutboxEmpty(root);
        });
    }

    [Test]
    public async Task StaleChoiceFailsClosedAndClearsItsTerminalRetryIdentity()
    {
        await WithIsolatedDataRootAsync(async root =>
        {
            await using var viewModel = CreateShellPipelineViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            _ = await SubmitAsync(viewModel, "Crea una nota llamada Viaje con norte");
            _ = await SubmitAsync(viewModel, "Crea una nota llamada Viaje con sur");

            string prompt = await SubmitAsync(viewModel, "trash the note called Viaje");
            int northChoice = FindChoice(prompt, "norte");
            var store = new LocalNoteStore(Path.Combine(root, "notes-store"));
            NoteRecord north = store.List(NoteListScope.All).Single(static note => note.Content == "norte");
            _ = store.Trash(north.Id);
            _ = store.Restore(north.Id);

            string stale = await SubmitAsync(
                viewModel,
                northChoice.ToString(System.Globalization.CultureInfo.InvariantCulture));
            Assert.That(stale, Does.Contain("note_selection_stale"));

            NoteRecord[] after = store.List(NoteListScope.All).ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(after, Has.All.Matches<NoteRecord>(static note => !note.IsTrashed));
                Assert.That(after.Single(static note => note.Content == "norte").Revision, Is.EqualTo(3));
                Assert.That(after.Single(static note => note.Content == "sur").Revision, Is.EqualTo(1));
            });
            AssertOutboxEmpty(root);
        });
    }

    [Test]
    public async Task ChoiceUsesTheSameCaseAndFormCEquivalenceAsTitleLookup()
    {
        await WithIsolatedDataRootAsync(async root =>
        {
            await using var viewModel = CreateShellPipelineViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            _ = await SubmitAsync(viewModel, "Crea una nota llamada CAFÉ con mayúsculas");
            _ = await SubmitAsync(viewModel, "Crea una nota llamada cafe\u0301 con combinada");

            string prompt = await SubmitAsync(viewModel, "read the note called café");
            AssertPromptIsPrivate(prompt, 2);
            int uppercaseChoice = FindChoice(prompt, "mayúsculas");
            string read = await SubmitAsync(
                viewModel,
                uppercaseChoice.ToString(System.Globalization.CultureInfo.InvariantCulture));

            var store = new LocalNoteStore(Path.Combine(root, "notes-store"));
            Assert.Multiple(() =>
            {
                Assert.That(read, Does.Contain("note.read"));
                Assert.That(read, Does.Contain("mayúsculas"));
                Assert.That(store.List(NoteListScope.All), Has.Length.EqualTo(2));
                Assert.That(store.List(NoteListScope.All), Has.All.Matches<NoteRecord>(static note => note.Revision == 1));
            });
            AssertOutboxEmpty(root);
        });
    }

    [Test]
    public async Task RestartRecoversThePersistedUuidSelectionBeforeAnyEffect()
    {
        await WithIsolatedDataRootAsync(async root =>
        {
            var store = new LocalNoteStore(Path.Combine(root, "notes-store"));
            NoteRecord first = store.Create("Archivo", "uno");
            NoteRecord selected = store.Create("Archivo", "dos");
            string outbox = Path.Combine(root, "shell", "retry-outbox.v1.json");
            var route = new RoutedOperation(
                "note.trash",
                new JsonObject
                {
                    ["noteId"] = selected.Id.ToString("D"),
                    ["expectedTitle"] = selected.Title,
                    ["expectedRevision"] = selected.Revision,
                    ["expectedIsTrashed"] = selected.IsTrashed,
                });
            PreparedOperation persisted = new RetryableOperationRegistry(outbox).GetOrAdd(route);

            await using var viewModel = CreateShellPipelineViewModel();
            var announcements = new List<ConversationMessage>();
            viewModel.MessageAdded += message =>
            {
                if (!message.IsUser)
                {
                    announcements.Add(message);
                }
            };
            await viewModel.InitializeAsync(CancellationToken.None);

            ConversationMessage recovery = announcements.Last();
            Assert.Multiple(() =>
            {
                Assert.That(recovery.Body, Does.Contain("no volveré a interpretar el número"));
                Assert.That(recovery.AccessibleText, Does.Contain("opción que ya elegiste"));
                Assert.That(recovery.Body, Does.Not.Contain(selected.Id.ToString("D")));
                Assert.That(store.Read(selected.Id).Revision, Is.EqualTo(1));
            });

            string result = await SubmitAsync(viewModel, "continue");
            Assert.That(result, Does.Contain("note.trash"));
            Assert.That(result, Does.Contain("success"));

            NoteRecord selectedAfter = store.Read(selected.Id, includeTrashed: true);
            NoteRecord firstAfter = store.Read(first.Id);
            Assert.Multiple(() =>
            {
                Assert.That(selectedAfter.IsTrashed, Is.True);
                Assert.That(selectedAfter.Revision, Is.EqualTo(2));
                Assert.That(firstAfter.IsTrashed, Is.False);
                Assert.That(firstAfter.Revision, Is.EqualTo(1));
                Assert.That(persisted.InvocationId, Is.Not.Empty);
            });
            AssertOutboxEmpty(root);
        });
    }

    [Test]
    public async Task RestartRecoversTheOriginalAmbiguityBeforeAnyChoice()
    {
        await WithIsolatedDataRootAsync(async root =>
        {
            string originalPrompt;
            await using (var firstViewModel = CreateShellPipelineViewModel())
            {
                await firstViewModel.InitializeAsync(CancellationToken.None);
                _ = await SubmitAsync(firstViewModel, "Crea una nota llamada Clave con alfa");
                _ = await SubmitAsync(firstViewModel, "Crea una nota llamada Clave con beta");
                originalPrompt = await SubmitAsync(firstViewModel, "borra la nota Clave");
                AssertPromptIsPrivate(originalPrompt, 2);
            }

            await using var restartedViewModel = CreateShellPipelineViewModel();
            await restartedViewModel.InitializeAsync(CancellationToken.None);
            ConversationMessage recovery = restartedViewModel.Messages.Last();
            Assert.Multiple(() =>
            {
                Assert.That(recovery.Body, Does.Contain("note_recovery_pending"));
                Assert.That(recovery.Body, Does.Contain("enviar a la papelera"));
                Assert.That(UuidPattern().IsMatch(recovery.Body), Is.False);
            });

            string replayedPrompt = await SubmitAsync(restartedViewModel, "continuar");
            Assert.That(replayedPrompt, Is.EqualTo(originalPrompt));
            int betaChoice = FindChoice(replayedPrompt, "beta");
            string result = await SubmitAsync(
                restartedViewModel,
                betaChoice.ToString(System.Globalization.CultureInfo.InvariantCulture));
            Assert.That(result, Does.Contain("note.trash"));
            Assert.That(result, Does.Contain("success"));

            var store = new LocalNoteStore(Path.Combine(root, "notes-store"));
            Assert.Multiple(() =>
            {
                Assert.That(
                    store.List(NoteListScope.All).Single(static note => note.Content == "alfa").IsTrashed,
                    Is.False);
                Assert.That(
                    store.List(NoteListScope.All).Single(static note => note.Content == "beta").IsTrashed,
                    Is.True);
            });
            AssertOutboxEmpty(root);
        });
    }

    private static async Task WithIsolatedDataRootAsync(Func<string, Task> body)
    {
        string root = PrivateDataRootTestSupport.NewPath("natural-note-choice-e2e");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);
        try
        {
            await body(root);
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

    private static MainWindowViewModel CreateShellPipelineViewModel() =>
        new(static route => route.ResolveStandaloneOperation());

    private static async Task<string> SubmitAsync(MainWindowViewModel viewModel, string text)
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
        });
        return added[1].Body;
    }

    private static int FindChoice(string prompt, string preview)
    {
        string line = prompt.Split('\n')
            .Single(candidate => candidate.Contains($"«{preview}»", StringComparison.Ordinal));
        int separator = line.IndexOf('.', StringComparison.Ordinal);
        return int.Parse(line.AsSpan(0, separator), System.Globalization.CultureInfo.InvariantCulture);
    }

    private static void AssertPromptIsPrivate(string prompt, int expectedCount)
    {
        Assert.Multiple(() =>
        {
            Assert.That(prompt, Does.Contain($"Encontré {expectedCount} notas"));
            Assert.That(prompt, Does.Contain("No hice cambios"));
            Assert.That(UuidPattern().IsMatch(prompt), Is.False);
            Assert.That(prompt.TrimStart(), Does.Not.StartWith("{"));
            Assert.That(prompt.TrimStart(), Does.Not.StartWith("["));
        });
    }

    private static string Ordinal(int number) => number switch
    {
        1 => "first",
        2 => "second",
        3 => "third",
        4 => "fourth",
        5 => "fifth",
        _ => throw new ArgumentOutOfRangeException(nameof(number)),
    };

    private static void AssertOutboxEmpty(string root)
    {
        using JsonDocument outbox = JsonDocument.Parse(
            File.ReadAllText(Path.Combine(root, "shell", "retry-outbox.v1.json")));
        Assert.That(outbox.RootElement.GetProperty("entries").GetArrayLength(), Is.Zero);
    }

    [GeneratedRegex(
        "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex UuidPattern();
}
