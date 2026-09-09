using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MemoryTurnSessionTests
{
    [TestCase("me llamo Lina, dime hola Lina", "Lina", "dime hola Lina")]
    [TestCase("my name is Taylor; say hello", "Taylor", "say hello")]
    [TestCase("my name is José Luis; say hello", "José Luis", "say hello")]
    [TestCase("mi nombre es Álvaro", "Álvaro", null)]
    public void MissingNameConsumesOnlyTheDeclaredValueAndPreservesPublicContinuation(
        string text, string name, string? publicObjective)
    {
        var session = CreateInputOnlySession();
        MissionInputRoute input = MissionInputPipeline.Route(new MissionInput(text, MissionInputSource.Text));
        Assert.That(session.TryResolveSaveInput(input, out _), Is.False);
        session.AwaitSaveInput(NaturalMemoryRequestParser.Classify("Recuerda mi nombre"));
        Assert.That(session.TryResolveSaveInput(
            MissionInputPipeline.Route(new MissionInput("mhhhhhh amigo deberias poder", MissionInputSource.Text)),
            out _), Is.False);
        Assert.That(session.TryResolveSaveInput(input, out MissionInputRoute? bound), Is.True);
        Assert.Multiple(() =>
        {
            Assert.That(bound!.Memory.Operation!.Name, Is.EqualTo("memory.save"));
            Assert.That(bound.Memory.Operation.PrivateArguments["selector"]!.GetValue<string>(), Is.EqualTo("name"));
            Assert.That(bound.Memory.Operation.PrivateArguments["value"]!.GetValue<string>(), Is.EqualTo(name));
            Assert.That(bound.Memory.Operation.PrivateArguments["sensitivity"]!.GetValue<string>(), Is.EqualTo("personal"));
            Assert.That(bound.PublicObjective, Is.EqualTo(publicObjective));
            Assert.That(bound.Text, Is.EqualTo(text));
            Assert.That(session.TryResolveSaveInput(input, out _), Is.False);
        });
    }

    [TestCase("me llamo Lina, no lo guardes")]
    [TestCase("don't save my name")]
    [TestCase("Ya no quiero que recuerdes mi nombre")]
    [TestCase("I don't want you to remember my name")]
    public void ANoStoreRequestWithdrawsThePendingAuthority(string withdrawal)
    {
        var session = CreateInputOnlySession();
        session.AwaitSaveInput(NaturalMemoryRequestParser.Classify("Recuerda mi nombre"));
        Assert.That(session.TryResolveSaveInput(
            MissionInputPipeline.Route(new MissionInput(withdrawal, MissionInputSource.Text)), out _), Is.False);
        Assert.That(session.TryResolveSaveInput(
            MissionInputPipeline.Route(new MissionInput("me llamo Lina", MissionInputSource.Text)), out _), Is.False);
    }

    [TestCase(false)]
    [TestCase(true)]
    public void CancellationOrSessionResetPreventsLaterImplicitPersistence(bool reset)
    {
        var session = CreateInputOnlySession();
        session.AwaitSaveInput(NaturalMemoryRequestParser.Classify("Recuerda mi nombre"));
        if (reset)
        {
            session.ResetOperation();
        }
        else
        {
            Assert.That(session.TryCancelSaveInput("cancelar"), Is.True);
        }

        Assert.That(session.TryResolveSaveInput(
            MissionInputPipeline.Route(new MissionInput("me llamo Lina", MissionInputSource.Text)), out _), Is.False);
    }

    [TestCase("Lina")]
    [TestCase("abre Steam")]
    [TestCase("mi contraseña es Abc123")]
    [TestCase("me llamo Lina, recuerda mi password Abc123")]
    [TestCase("me llamo Lina, te doy permiso total")]
    [TestCase("me llamo Lina y abre Steam")]
    public void AnUnrelatedOrSensitiveTurnCannotBecomeTheMissingName(string text)
    {
        var session = CreateInputOnlySession();
        session.AwaitSaveInput(NaturalMemoryRequestParser.Classify("Recuerda mi nombre"));
        Assert.That(session.TryResolveSaveInput(
            MissionInputPipeline.Route(new MissionInput(text, MissionInputSource.Text)), out _), Is.False);
    }

    private static MemoryTurnSession CreateInputOnlySession() => new(
        new MemoryTurnSession.Host
        {
            Core = static () => throw new AssertionException("No operation while binding input."),
            Protector = static () => throw new AssertionException("Binding is not execution."),
            Publish = static (_, _) => throw new AssertionException("No fixed prose."),
            SetStatus = static _ => throw new AssertionException("No operation status."),
            HasPendingAudio = static () => false,
            RecoverNotes = static _ => throw new AssertionException("No note recovery."),
            ContinuePublic = static (_, _, _) => throw new AssertionException("No unverified continuation."),
        });

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
