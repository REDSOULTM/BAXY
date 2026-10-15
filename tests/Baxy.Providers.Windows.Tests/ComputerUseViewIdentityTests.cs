using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 26: a look of a named application that has no window, asked with <c>identityIfAbsent</c>, says only who is
/// in front: the same <c>window</c> object as any look, marked <c>identityOnly</c>, with no controls and no text; the
/// worker is not asked, so no tree of the person's window is walked. That mark is the one condition the App reads
/// (ComputerUseMission: a look so marked holds no check and only an opening is decided on it). Counter-case: the
/// same look without the argument asks the worker for the window's view, as always.
/// </summary>
[TestFixture]
public sealed class ComputerUseViewIdentityTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // No window is titled like it and no process is named like it.
    private static readonly string Absent = "Aplicacion-" + Guid.NewGuid().ToString("N");

    [Test]
    public async Task ALookOfAnApplicationWithoutAWindowSaysOnlyWhoIsInFront()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls",
            Json($$"""{"application":"{{Absent}}","identityIfAbsent":true,"includeText":true,"limit":60}"""),
            CancellationToken.None);

        Assert.That(worker.Commands, Is.Empty, "the worker walks no tree for who is in front");
        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");
        JsonElement view = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(view.GetProperty("identityOnly").GetBoolean(), Is.True);
            Assert.That(view.GetProperty("window").GetProperty("requested").GetBoolean(), Is.False);
            Assert.That(view.GetProperty("window").TryGetProperty("process", out _), Is.True, "who is in front");
            Assert.That(view.GetProperty("controls").GetArrayLength(), Is.Zero);
            Assert.That(view.TryGetProperty("text", out _), Is.False, "no text of a window that is not the mission's");
            Assert.That(view.GetProperty("surface").GetString(), Is.Empty, "no capture");
        });
    }

    [Test]
    public async Task WithoutTheArgumentTheWindowInFrontIsReadAsAlways()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json($$"""{"application":"{{Absent}}","limit":60}"""), CancellationToken.None);

        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");
        Assert.That(worker.Commands, Has.Some.Contains("\"cmd\":\"view\""), "the window in front is walked");
    }
}
