using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M159 (DEV-I v4w I-s048 «pasame la ventana de spotify a la derecha»): a snapped window whose own minimum is
/// larger than the half carries that fact to the mind (fitsInHalf false, the half's width beside the window's own),
/// so the reply never says «en la mitad derecha» alone. A window that fits sends the same receipt as before.
/// </summary>
[TestFixture]
public sealed class M159SnapBeyondHalfFactTests
{
    [Test]
    public async Task AWindowWiderThanHalfCarriesTheHalfItDidNotFit()
    {
        var provider = new SnapProvider(new WindowActionResult(true, true,
            new WindowCandidate("win_spotify", 77, "Spotify", "normal", true, 722, 0, 814, 816, "Spotify"),
            null, new WindowRequestedSize(768, 816)));

        JsonElement result = await SnapAsync(provider, "right");

        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("side").GetString(), Is.EqualTo("right"));
            Assert.That(result.GetProperty("window").GetProperty("width").GetInt32(), Is.EqualTo(814));
            Assert.That(result.GetProperty("fitsInHalf").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("halfWidth").GetInt32(), Is.EqualTo(768));
            Assert.That(result.TryGetProperty("halfHeight", out _), Is.False, "the height fits: not said");
        });
    }

    [Test]
    public async Task AWindowThatFitsSendsTheSameReceiptAsBefore()
    {
        var provider = new SnapProvider(new WindowActionResult(true, true,
            new WindowCandidate("win_word", 12, "WINWORD", "normal", true, 0, 0, 768, 816, "Word"), null));

        JsonElement result = await SnapAsync(provider, "left");

        Assert.That(
            result.EnumerateObject().Select(static property => property.Name),
            Is.EqualTo(new[] { "version", "side", "window" }));
    }

    private static async Task<JsonElement> SnapAsync(IWindowControlProvider provider, string side)
    {
        IOperationHandler handler = WindowControlHandlers.Create(provider)
            .Single(static handler => handler.Definition.Name == "window.snap");
        using JsonDocument arguments = JsonDocument.Parse(
            $$"""{"windowId":"win_fcee2653bf13d46a190ccd42e1c24d5e","side":"{{side}}"}""");
        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", arguments.RootElement),
            CancellationToken.None);
        Assert.That(outcome.Succeeded && outcome.Verified, Is.True);
        return outcome.Result!.Value;
    }

    private sealed class SnapProvider(WindowActionResult result) : IWindowControlProvider
    {
        public ValueTask<WindowActionResult> SnapAsync(
            string windowId, string side, CancellationToken cancellationToken) =>
            ValueTask.FromResult(result);

        public ValueTask<WindowResolveResult> ResolveForegroundAsync(CancellationToken cancellationToken) =>
            throw new NotSupportedException();

        public ValueTask<WindowResolveResult> ResolveAsync(string processName, int limit,
            CancellationToken cancellationToken, bool byTitle = false, int offset = 0) =>
            throw new NotSupportedException();

        public ValueTask<WindowActionResult> ExecuteAsync(string windowId, WindowControlAction action,
            CancellationToken cancellationToken) =>
            throw new NotSupportedException();

        public ValueTask<WindowActionResult> SetBoundsAsync(string windowId, int? x, int? y, int? width,
            int? height, CancellationToken cancellationToken) =>
            throw new NotSupportedException();

        public ValueTask<WindowCloseResult> CloseAsync(string windowId, CancellationToken cancellationToken) =>
            throw new NotSupportedException();
    }
}
