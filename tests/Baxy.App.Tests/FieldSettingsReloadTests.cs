using System.IO;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// pc-f6-ajustes: baxy.settings.set writes BAXY's own settings from the engine into the file the App read at its start.
/// The App reads it again when that call ends, and a switch of the view never writes back what it read before.
/// </summary>
[TestFixture]
public sealed class FieldSettingsReloadTests
{
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-field-settings-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    [Test]
    public void TheWakeSoundIsOnUntilThePersonSwitchesItOff()
    {
        // Uso real 03-11: the owner said «BAXY» and heard nothing; the sound was off by default and never switched on.
        var settings = new FieldSettings(_root);
        bool before = settings.WakeSound;

        settings.ApplyGeneral(new JsonObject { ["wakeSound"] = false });

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.True);
            Assert.That(settings.WakeSound, Is.False);
        });
    }

    [Test]
    public void MinimizingKeepsTheWindowInTheTaskbarUntilThePersonChoosesTheTray()
    {
        // Owner, 2026-11-08: «al minimizar se manda a la bandeja», as a choice in Settings beside «Al cerrar la ventana».
        var settings = new FieldSettings(_root);
        bool before = settings.MinimizeToTray;

        settings.ApplyGeneral(new JsonObject { ["minimizeToTray"] = true });

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.False);
            Assert.That(settings.MinimizeToTray, Is.True);
            Assert.That(new FieldSettings(_root).MinimizeToTray, Is.True);
            Assert.That((bool?)settings.GeneralJson((true, null))["minimizeToTray"], Is.True);
        });
    }

    [Test]
    public void TheOverlayIsOnInTheBottomRightUntilThePersonChoosesOtherwiseAndAWrongChoiceWritesNothing()
    {
        // Owner, 2026-11-08: the overlay that says what BAXY does while it is behind, with its corner, size, see-through,
        // how long the end stays, kept off full-screen windows, and answering cards from it off unless chosen.
        var settings = new FieldSettings(_root);
        OverlaySettings before = settings.Overlay;

        OverlaySettings? after = settings.ApplyOverlay(new JsonObject { ["corner"] = "tl", ["size"] = "l", ["opacity"] = 60, ["hideSeconds"] = 0, ["answer"] = true });
        OverlaySettings? refused = settings.ApplyOverlay(new JsonObject { ["corner"] = "middle", ["size"] = "s" });

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.EqualTo(new OverlaySettings(true, "br", "m", 78, 8, true, false)));
            Assert.That(after, Is.EqualTo(new OverlaySettings(true, "tl", "l", 60, 0, true, true)));
            Assert.That(refused, Is.Null);
            Assert.That(new FieldSettings(_root).Overlay, Is.EqualTo(after), "kept, and the refused change wrote nothing");
            Assert.That((string?)settings.OverlayJson()["corner"], Is.EqualTo("tl"));
        });
    }

    [Test]
    public void WhatThePcPlaysIsIgnoredUntilThePersonSwitchesItOff()
    {
        // Uso real 03-11: a song's words went into a request; the echo cancellation is on unless the owner says no.
        var settings = new FieldSettings(_root);
        bool before = settings.EchoCancel;

        settings.ApplyGeneral(new JsonObject { ["echoCancel"] = false });

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.True);
            Assert.That(settings.EchoCancel, Is.False);
            Assert.That(new FieldSettings(_root).EchoCancel, Is.False);
            Assert.That((bool?)settings.GeneralJson((true, null))["echoCancel"], Is.False);
        });
    }

    [Test]
    public void WhatTheEngineWroteIsReadAgain()
    {
        var settings = new FieldSettings(_root);
        long until = DateTimeOffset.UtcNow.AddHours(1).ToUnixTimeMilliseconds();
        FieldSettingsStore.Write(_root, new JsonObject { ["voiceMuted"] = true, ["quiet"] = "1h", ["quietUntil"] = until });

        bool before = settings.VoiceMuted;
        settings.Reload();

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.False);
            Assert.That(settings.VoiceMuted, Is.True);
            Assert.That(settings.QuietUntil?.ToUnixTimeMilliseconds(), Is.EqualTo(until));
            Assert.That(settings.QuietSpan, Is.EqualTo("1h"));
        });
    }

    [Test]
    public void AViewSwitchKeepsWhatTheEngineWrote()
    {
        var settings = new FieldSettings(_root);
        FieldSettingsStore.Write(_root, new JsonObject { ["web"] = false });

        settings.ApplyGeneral(new JsonObject { ["weather"] = false });

        Assert.That(FieldSettingsStore.TryRead(_root, out JsonObject file), Is.True);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)file["web"], Is.False);
            Assert.That((bool?)file["weather"], Is.False);
            Assert.That(settings.WebAllowed, Is.False);
        });
    }

    // REV_APP ASY-b (2026-11-09): a setting that could not be written was not said, and the file's old value came back by
    // itself with the next reading (another switch, or a setting changed from the chat): «Búsqueda web» switched off was on
    // again with nobody asking.
    [Test]
    public void AChoiceThatCouldNotBeWrittenIsSaidAndHoldsUntilItIs()
    {
        var settings = new FieldSettings(_root);
        settings.ApplyGeneral(new JsonObject { ["web"] = true });
        bool saidBefore = (bool?)settings.GeneralJson((true, null))["unsaved"] == true;
        // The file cannot be written: its temporary's name is taken by a folder.
        string blocked = Path.Combine(_root, FieldSettingsStore.FileName + ".tmp");
        Directory.CreateDirectory(blocked);

        settings.ApplyGeneral(new JsonObject { ["web"] = false });
        bool offAtOnce = !settings.WebAllowed;
        bool said = (bool?)settings.GeneralJson((true, null))["unsaved"] == true;
        settings.Reload();
        bool offAfterAReading = !settings.WebAllowed;
        settings.ApplyGeneral(new JsonObject { ["wakeSound"] = false });
        bool offAfterAnotherSwitch = !settings.WebAllowed;
        settings.ApplyProposals(new JsonObject { ["quiet"] = "1h" }, DateTimeOffset.UtcNow);
        bool saidInProposals = (bool?)settings.ProposalsJson()["unsaved"] == true;
        bool saidInTheOverlay = (bool?)settings.OverlayJson()["unsaved"] == true;

        // It can be written again, and the engine wrote a setting of its own meanwhile (the chat's baxy.settings.set).
        Directory.Delete(blocked);
        FieldSettingsStore.Write(_root, new JsonObject { ["web"] = true, ["voiceMuted"] = true });
        settings.Reload();

        Assert.That(FieldSettingsStore.TryRead(_root, out JsonObject file), Is.True);
        Assert.Multiple(() =>
        {
            Assert.That(saidBefore, Is.False, "a choice that was written says nothing");
            Assert.That(offAtOnce, Is.True);
            Assert.That(said, Is.True, "the view is told the choice is not in the file");
            Assert.That(offAfterAReading, Is.True, "reading the file again must not bring the old value back");
            Assert.That(offAfterAnotherSwitch, Is.True, "nor another switch");
            Assert.That(saidInProposals, Is.True);
            Assert.That(saidInTheOverlay, Is.True);
            Assert.That(settings.WebAllowed, Is.False, "the person's choice, not the file's old one");
            Assert.That(settings.VoiceMuted, Is.True, "and what the engine wrote is read");
            Assert.That(settings.WakeSound, Is.False);
            Assert.That(settings.QuietSpan, Is.EqualTo("1h"));
            Assert.That((bool?)file["web"], Is.False, "written once the file could be");
            Assert.That((bool?)file["wakeSound"], Is.False);
            Assert.That((bool?)file["voiceMuted"], Is.True);
            Assert.That((bool?)settings.GeneralJson((true, null))["unsaved"], Is.False, "and no longer said");
        });
    }
}
