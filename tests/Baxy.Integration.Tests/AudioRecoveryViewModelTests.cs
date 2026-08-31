using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class AudioRecoveryViewModelTests
{
    [Test]
    public async Task RestartOffersContinueBlocksDifferentActionsAndPreservesIdentityUntilTerminal()
    {
        string root = PrivateDataRootTestSupport.NewPath("audio-viewmodel-recovery");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);
        var pendingRoute = new RoutedOperation(
            AudioOperationIds.Volume,
            // This deliberately invalid level exercises the complete UI/core recovery path
            // without opening or mutating the physical audio endpoint.
            new JsonObject { ["level"] = 101 });
        string outboxPath = Path.Combine(root, "shell", "retry-outbox.v1.json");
        PreparedOperation original = new RetryableOperationRegistry(outboxPath)
            .GetOrAdd(pendingRoute);

        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True);
                Assert.That(viewModel.StatusDescription,
                    Is.EqualTo("Esperando comprobar el audio"));
                Assert.That(viewModel.Messages, Has.Some.Matches<ConversationMessage>(message =>
                    !message.IsUser
                    && message.Body.Contains("audio_volume_pending",
                        StringComparison.Ordinal)));
                Assert.That(viewModel.Messages, Has.Some.Matches<ConversationMessage>(message =>
                    message.Body.Contains("continuar", StringComparison.Ordinal)
                    && message.Body.Contains("retry", StringComparison.Ordinal)));
            });

            viewModel.Draft = "anota comprar leche";
            await viewModel.SubmitAsync(CancellationToken.None);

            PreparedOperation[] afterBlockedAction = new RetryableOperationRegistry(outboxPath)
                .SnapshotPendingOperations()
                .ToArray();
            var noteStore = new LocalNoteStore(Path.Combine(root, "notes-store"));
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.Messages[^1].Body,
                    Does.Contain("audio_volume_pending").Or.Contain("pending"));
                Assert.That(noteStore.List(NoteListScope.All), Is.Empty);
                Assert.That(afterBlockedAction, Has.Length.EqualTo(1));
                Assert.That(afterBlockedAction[0].MissionId, Is.EqualTo(original.MissionId));
                Assert.That(afterBlockedAction[0].InvocationId, Is.EqualTo(original.InvocationId));
                Assert.That(afterBlockedAction[0].Matches(pendingRoute), Is.True);
            });

            viewModel.Draft = "pon el volumen a 40";
            await viewModel.SubmitAsync(CancellationToken.None);
            PreparedOperation[] afterDifferentAudio = new RetryableOperationRegistry(outboxPath)
                .SnapshotPendingOperations()
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.Messages[^1].Body,
                    Does.Contain("pending").Or.Contain("audio_volume"));
                Assert.That(afterDifferentAudio, Has.Length.EqualTo(1));
                Assert.That(afterDifferentAudio[0].InvocationId,
                    Is.EqualTo(original.InvocationId));
            });

            viewModel.Draft = "continuar";
            await viewModel.SubmitAsync(CancellationToken.None);

            PreparedOperation[] afterTerminal = new RetryableOperationRegistry(outboxPath)
                .SnapshotPendingOperations()
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.Messages[^1].Body,
                    Does.Contain("invalid").Or.Contain("101").Or.Contain("failure"));
                Assert.That(afterTerminal, Is.Empty);
                Assert.That(noteStore.List(NoteListScope.All), Is.Empty);
            });
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
}
