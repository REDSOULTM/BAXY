using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MemoryTurnSessionTests
{
    [Test]
    public void SameMemoryOperationComparesIdentityMissionAndInvocation()
    {
        PreparedOperation left = PreparedOperation.Create(
            "app.open",
            new JsonObject { ["appId"] = "windows.notepad" });
        PreparedOperation right = PreparedOperation.Create(
            "app.open",
            new JsonObject { ["appId"] = "windows.notepad" });

        Assert.Multiple(() =>
        {
            Assert.That(MemoryTurnSession.IsSame(left, left), Is.True);
            Assert.That(MemoryTurnSession.IsSame(left, right), Is.False);
            Assert.That(MemoryTurnSession.IsSame(null, left), Is.False);
        });
    }

    [Test]
    public void MissingConfirmationFailsClosedWithoutCallingCore()
    {
        var session = new MemoryTurnSession(
            new MemoryTurnSession.Host
            {
                Core = static () => throw new AssertionException("Core must not run."),
                Protector = static () => throw new AssertionException("Protector must not run."),
                Publish = static (_, _) => throw new AssertionException("Publish must not run."),
                SetStatus = static _ => throw new AssertionException("Status must not change."),
                HasPendingAudio = static () => false,
                RecoverNotes = static _ => throw new AssertionException("Notes must not recover."),
                ContinuePublic = static (_, _, _) =>
                    throw new AssertionException("Public continuation must not run."),
            });
        var registry = new RetryableOperationRegistry(
            Path.Combine(Path.GetTempPath(), "baxy-memory-missing-" + Guid.NewGuid() + ".json"));

        Assert.That(
            async () => await session.HandleConfirmationAsync(
                "sí",
                registry,
                CancellationToken.None),
            Throws.InvalidOperationException);
        Assert.That(session.HasConfirmation, Is.False);
        Assert.That(session.HasPendingOperation, Is.False);
    }
}
