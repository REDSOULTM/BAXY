using System.IO;
using Baxy.Kernel.Journal;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// DIAX11: what the core set right at its start is told once, with the truth: a half-done journal write set aside
/// (vivo Radeon H-012), and an own browser profile that had taken the person's Microsoft account discarded (H-006).
/// </summary>
[TestFixture]
internal sealed class StartRepairsTests
{
    private string _dataRoot = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _dataRoot = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(Path.Combine(_dataRoot, "journal"));
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_dataRoot, recursive: true);

    [Test]
    public void ASetAsideJournalTailIsToldOnceAndANewOneAgain()
    {
        SetAside("missions.jsonl.damaged-20261116063000000");

        string? line = StartRepairs.OnStart(_dataRoot, english: false, [], () => { }, out Action told);
        told();

        Assert.Multiple(() =>
        {
            Assert.That(line, Does.Contain("La aparté sin borrar nada").And.Contain("sigue anotado"));
            Assert.That(line, Does.Not.Contain("navegador"));
            Assert.That(StartRepairs.OnStart(_dataRoot, english: false, [], () => { }, out _), Is.Null, "told once");
        });

        SetAside("missions.jsonl.damaged-20261117080000000");
        Assert.That(StartRepairs.OnStart(_dataRoot, english: true, [], () => { }, out _),
            Does.Contain("set it aside, deleting nothing"));
    }

    [Test]
    public void ADiscardedBrowserProfileIsToldOnceAndForgotten()
    {
        bool forgotten = false;

        string? line = StartRepairs.OnStart(_dataRoot, english: false, ["edge"], () => forgotten = true, out Action told);

        Assert.Multiple(() =>
        {
            Assert.That(line, Does.Contain("un Edge aparte").And.Contain("Ya no").And.Contain("no los toqué"));
            // REVX2 DX11-1: only what BAXY knows. It saw an account in its Edge profile; not whose, not that it synced.
            Assert.That(line, Does.Not.Contain("él solo").And.Not.Contain("tu cuenta de Microsoft")
                .And.Not.Contain("sincronizaba"));
            Assert.That(forgotten, Is.False, "forgotten only once it was told");
        });
        told();
        Assert.That(forgotten, Is.True);
    }

    // REVX2 DX11-2: the tail could not be copied aside (FileInvocationJournal leaves a «.not-kept» mark): told as it
    // is, never as kept; once.
    [Test]
    public void ATailThatCouldNotBeKeptIsToldAsItIs()
    {
        SetAside("missions.jsonl.damaged-20261116090000000" + FileInvocationJournal.NotKeptSuffix);

        string? line = StartRepairs.OnStart(_dataRoot, english: false, [], () => { }, out Action told);
        told();

        Assert.Multiple(() =>
        {
            Assert.That(line, Does.Contain("No pude guardar copia").And.Contain("sigue anotado"));
            Assert.That(line, Does.Not.Contain("sin borrar nada"));
            Assert.That(StartRepairs.OnStart(_dataRoot, english: false, [], () => { }, out _), Is.Null, "told once");
            Assert.That(StartRepairs.Line(journalTail: false, tailNotKept: true, browserAccount: false, english: true),
                Does.Contain("could not keep a copy"));
        });
    }

    [Test]
    public void NothingSetRightSaysNothing()
    {
        File.WriteAllText(Path.Combine(_dataRoot, "journal", "missions.jsonl"), string.Empty);

        Assert.That(StartRepairs.OnStart(_dataRoot, english: false, [], () => { }, out _), Is.Null);
        Assert.That(StartRepairs.OnStart(Path.Combine(_dataRoot, "missing"), english: false, [], () => { }, out _),
            Is.Null);
    }

    private void SetAside(string name) => File.WriteAllText(Path.Combine(_dataRoot, "journal", name), "{{{\n");
}
