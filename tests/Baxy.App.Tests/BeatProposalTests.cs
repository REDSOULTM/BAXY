using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// R10.1 (src/Baxy.App/NativeTurnLoop.cs, BeatProposes): a heartbeat acts alone only on what is harmless and
/// reversible; anything else it proposes and the person says «sí». Trace nb-beat-none-pC, P026: airplane mode switched
/// on at 8 % battery with nobody asking.
/// </summary>
[TestFixture]
public sealed class BeatProposalTests
{
    // What a heartbeat changes alone, as the owner can review it: a reversible change that reaches no window of the
    // person's, sends nothing out and cuts no connection, called with no arguments (media.control then goes to BAXY's
    // YouTube tab, a window: it is proposed). An operation joins this list knowingly.
    private static readonly string[] ChangesAlone =
    [
        "app.open", "audio.app.volume.adjust", "audio.app.volume.set", "audio.microphone.mute", "audio.mute",
        "audio.volume", "audio.volume.adjust", "backup.create", "backup.known.create", "backup.known.restore.latest",
        "backup.restore", "desktop.wallpaper.set", "document.presentation.create", "file.compress", "file.edit",
        "file.write", "filesystem.copy", "filesystem.create.directory", "filesystem.move",
        "filesystem.sandbox.move.named", "input.keyboard.open", "media.seek.relative", "memory.correct",
        "memory.disable", "memory.save", "memory.session.clear", "note.create", "note.restore", "note.update",
        "office.document.create", "schedule.alarms", "system.settings.adjust", "task.complete", "task.create",
        "task.reopen", "task.restore", "task.update", "window.minimize", "window.restore",
        // As before R10.1 (owner, 2026-10-15): reads of the screen and of the person's data, which the heartbeat says
        // it looked at, and the settings that are not a system change (brightness, a saved Wi-Fi profile).
        "capture.active.window", "capture.screenshot", "clipboard.read.text", "email.latest.read", "memory.enable",
        "memory.export", "memory.sensitive.save", "ocr.read", "peripheral.scan", "system.settings.set",
        "vision.describe", "wifi.connect", "wifi.connect.named",
        // pc-f6-ajustes: BAXY's own settings (its voice, web search, not interrupting, its proposals' silence) reach no
        // window, send nothing out, and the view's Settings shows them.
        "baxy.settings.set",
    ];

    [TestCase("system.settings.set", "{\"setting\":\"airplane_mode\",\"value\":1}")]
    [TestCase("wifi.radio.set", "{\"state\":false}")]
    [TestCase("bluetooth.radio.set", "{\"state\":false}")]
    [TestCase("display.mode.set", "{\"width\":1280,\"height\":720}")]
    [TestCase("clipboard.write.text", "{\"text\":\"x\"}")]
    [TestCase("app.open", "{\"appId\":\"Spotify\",\"foreground\":true}")]
    [TestCase("web.search", "{\"query\":\"x\"}")]
    [TestCase("app.close", "{\"appId\":\"Spotify\"}")]
    public void AHeartbeatProposesWhatIsNotHarmlessAndReversible(string operation, string arguments) =>
        Assert.That(NativeTurnLoop.BeatProposes(ProductCatalog.GetRequired(operation),
            (JsonObject)JsonNode.Parse(arguments)!), Is.True);

    // Measured on the practice scenes (2026-10-22): holding these too took act 4/7 → 1/7 (P007 and P027 lower the
    // brightness, P024 reconnects the home Wi-Fi).
    [TestCase("system.settings.set", "{\"setting\":\"brightness\",\"value\":30}")]
    [TestCase("wifi.connect.named", "{\"ssid\":\"Casa\"}")]
    public void AHeartbeatActsAloneOnAReversibleSettingThatIsNoSystemChange(string operation, string arguments) =>
        Assert.That(NativeTurnLoop.BeatProposes(ProductCatalog.GetRequired(operation),
            (JsonObject)JsonNode.Parse(arguments)!), Is.False);

    [Test]
    public void AHeartbeatChangesAloneOnlyWhatTheOwnerCanReviewHere()
    {
        string[] alone = [.. ProductCatalog.ToolDescriptors
            .Where(static descriptor => descriptor.Risk != Baxy.Contracts.OperationRisks.ReadOnly
                && !NativeTurnLoop.BeatProposes(descriptor, []))
            .Select(static descriptor => descriptor.Name)];

        Assert.That(alone, Is.EquivalentTo(ChangesAlone));
    }
}
