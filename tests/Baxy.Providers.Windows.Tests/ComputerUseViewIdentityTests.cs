using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría final V3 (2026-10-15): a look of a named application that no window is, exactly, never reads another
/// window in its place (the person's, in front): it fails with the visible windows as candidates, so the model can
/// name one, and the worker is not asked for any tree.
/// </summary>
[TestFixture]
public sealed class ComputerUseViewIdentityTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // No window is titled like it and no process is named like it.
    private static readonly string Absent = "Aplicacion-" + Guid.NewGuid().ToString("N");

    [Test]
    public async Task ANamedApplicationWithoutAWindowGivesCandidatesAndReadsNoWindow()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json($$"""{"application":"{{Absent}}","includeText":true,"limit":60}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("application_window_not_found"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("candidates").ValueKind, Is.EqualTo(JsonValueKind.Array));
            Assert.That(worker.Commands, Is.Empty, "no window's tree is walked in the named one's place");
        });
    }
}
