using System.IO;
using Baxy.Installer;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// AUT1 (orden del dueño, 13-11-2026): the BAXY that opens after an update says it started, so the installer lets the
/// one before go, and tells once how the update ended, read from what the installer wrote.
/// </summary>
[TestFixture]
internal sealed class LastUpdateTests
{
    private const string At = "2026-11-13T20:00:00.0000000-03:00";
    private string _folder = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(_folder);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_folder, recursive: true);

    [Test]
    public void TheNewBaxyConfirmsItsStartAndSaysOnceThatItUpdated()
    {
        new UpdateOutcome("1.5.2", "1.5.3", UpdateOutcome.Started, null, 94_000_000, 40, At).Write(_folder);

        string? line = LastUpdate.OnStart(_folder, "1.5.3", english: false, out Action told);

        Assert.Multiple(() =>
        {
            Assert.That(line, Is.EqualTo("Me actualicé a la 1.5.3."));
            Assert.That(UpdateOutcome.IsConfirmed(_folder, "1.5.3"), Is.True, "the installer that waits lets the old BAXY go");
        });
        told();
        Assert.That(LastUpdate.OnStart(_folder, "1.5.3", english: false, out _), Is.Null, "told once");
    }

    [Test]
    public void ItSaysItInEnglishToo()
    {
        new UpdateOutcome("1.5.2", "1.5.3", UpdateOutcome.Installed, null, 1, 1, At).Write(_folder);

        Assert.That(LastUpdate.OnStart(_folder, "1.5.3", english: true, out _), Is.EqualTo("I updated to 1.5.3."));
    }

    [Test]
    public void TheBaxyBeforeNeverConfirmsTheNewOne()
    {
        // The new one did not start and this one, the one before, was opened again.
        new UpdateOutcome("1.5.3", "1.5.4", UpdateOutcome.Started, null, 1, 1, At).Write(_folder);

        string? line = LastUpdate.OnStart(_folder, "1.5.3", english: false, out _);

        Assert.Multiple(() =>
        {
            Assert.That(line, Is.Null, "it does not say it updated");
            Assert.That(UpdateOutcome.IsConfirmed(_folder, "1.5.4"), Is.False);
            Assert.That(UpdateOutcome.IsConfirmed(_folder, "1.5.3"), Is.False);
        });
    }

    // Blind review E-1: the installer writes «installed» once this BAXY confirmed; it is the same update, told already.
    [Test]
    public void TheSameUpdateIsNotToldAgainWhenTheInstallerEndsIt()
    {
        UpdateOutcome started = new("1.5.2", "1.5.3", UpdateOutcome.Started, null, 94_000_000, 40, At);
        started.Write(_folder);
        _ = LastUpdate.OnStart(_folder, "1.5.3", english: false, out Action told);
        told();

        (started with { State = UpdateOutcome.Installed, Seconds = 47 }).Write(_folder);

        Assert.That(LastUpdate.OnStart(_folder, "1.5.3", english: false, out _), Is.Null);
    }

    [TestCase("network", "se cortó la conexión", "sigo desde ahí")]
    [TestCase("slow", "iba tan lenta", "sigo desde ahí")]
    [TestCase("disk", "falta espacio en el disco", "No cambié nada")]
    [TestCase("damaged", "llegó distinto de lo publicado", "No cambié nada")]
    [TestCase("unsigned", "firmada por BAXY", "No cambié nada")]
    [TestCase("open", "no llegué a cerrarme", "No cambié nada")]
    [TestCase("other", "algo falló", "No cambié nada")]
    public void AnUpdateThatFailedIsToldWithItsCauseAndTheVersionItStillIs(string reason, string cause, string also)
    {
        new UpdateOutcome("1.5.3", "1.5.4", UpdateOutcome.Failed, reason, 0, 3, At).Write(_folder);

        string? line = LastUpdate.OnStart(_folder, "1.5.3", english: false, out _);

        Assert.That(line, Does.StartWith("No pude actualizarme a la 1.5.4").And.Contain(cause).And.Contain(also)
            .And.EndWith("sigo en la 1.5.3."));
        Assert.That(UpdateOutcome.IsConfirmed(_folder, "1.5.3"), Is.False);
    }

    [Test]
    public void AnUpdateThatWasUndoneIsToldAsSuch()
    {
        new UpdateOutcome("1.5.3", "1.5.4", UpdateOutcome.RolledBack, UpdateOutcome.NotStarted, 94, 200, At).Write(_folder);

        Assert.That(
            LastUpdate.OnStart(_folder, "1.5.3", english: false, out _),
            Is.EqualTo("Instalé la 1.5.4, pero no arrancó: volví a la 1.5.3, que es la que tienes ahora."));
    }

    [Test]
    public void AnOutcomeOfOtherVersionsOrNoneSaysNothing()
    {
        Assert.That(LastUpdate.OnStart(_folder, "1.5.3", english: false, out _), Is.Null, "no update ever ran");

        new UpdateOutcome("1.4.0", "1.4.1", UpdateOutcome.Failed, "network", 0, 3, At).Write(_folder);

        Assert.That(LastUpdate.OnStart(_folder, "1.5.3", english: false, out _), Is.Null, "not about this BAXY");
        Assert.That(LastUpdate.OnStart(_folder, null, english: false, out _), Is.Null, "a build with no version");
    }

    [Test]
    public void AReceiptThatStartedTheInstallerIsKnownByItsTypedFact()
    {
        Assert.Multiple(() =>
        {
            Assert.That(UpdatePanel.StartedInstaller(new System.Text.Json.Nodes.JsonObject { ["installerStarted"] = true }), Is.True);
            Assert.That(UpdatePanel.StartedInstaller(new System.Text.Json.Nodes.JsonObject { ["installerStarted"] = false }), Is.False);
            Assert.That(UpdatePanel.StartedInstaller(new System.Text.Json.Nodes.JsonObject { ["checked"] = true }), Is.False, "a check starts nothing");
        });
    }

    [Test]
    public void TheNextUpdateIsToldToo()
    {
        UpdateOutcome first = new("1.5.2", "1.5.3", UpdateOutcome.Installed, null, 1, 1, At);
        first.Write(_folder);
        _ = LastUpdate.OnStart(_folder, "1.5.3", english: false, out Action told);
        told();

        (first with { From = "1.5.3", To = "1.5.4", At = "2026-11-20T09:00:00.0000000-03:00" }).Write(_folder);

        Assert.That(LastUpdate.OnStart(_folder, "1.5.4", english: false, out _), Is.EqualTo("Me actualicé a la 1.5.4."));
    }
}
