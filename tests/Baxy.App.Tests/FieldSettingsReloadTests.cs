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
}
