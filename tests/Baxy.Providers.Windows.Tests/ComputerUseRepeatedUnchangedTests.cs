using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Holdout v4 (en vivo: «abre la biblioteca de Steam» opened Steam without app_open's place and pressed «Biblioteca» 7
/// times, each visible_button_postread_unchanged, 50 s): the same click seen unchanged again right after the last one
/// says how many times in a row, and from the second that pressing it again shows the same, with the places its
/// application opens straight at.
/// </summary>
[TestFixture]
public sealed class ComputerUseRepeatedUnchangedTests
{
    private const string PendingClick =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"pending\":true,\"name\":\"Biblioteca\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false," +
        "\"selected\":false,\"toggled\":false}";

    private const string UnchangedControl =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
        "\"name\":\"Biblioteca\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false}";

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    [Test]
    public async Task TheSameClickUnchangedTwiceInARowSaysSoAndAnotherClickStartsAgain()
    {
        var worker = new RoutedWorker(request => (string?)request["cmd"] switch
        {
            "click" => PendingClick,
            "postread" => UnchangedControl,
            _ => null,
        });
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "same"));
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: Capture);

        async Task<ExternalCapabilityReceipt> Click(string label) => await adapter.InvokeAsync(
            "input.visible.click", Json($$"""{"label":"{{label}}","window":4660}"""), CancellationToken.None);

        ExternalCapabilityReceipt first = await Click("Biblioteca");
        ExternalCapabilityReceipt second = await Click("Biblioteca");
        ExternalCapabilityReceipt third = await Click("Biblioteca");
        ExternalCapabilityReceipt other = await Click("Tienda");

        Assert.Multiple(() =>
        {
            Assert.That(new[] { first, second, third, other }.Select(receipt => receipt.ErrorCode),
                Has.All.EqualTo("visible_button_postread_unchanged"));
            Assert.That(first.Result?.TryGetProperty("unchangedInARow", out _) ?? false, Is.False);
            Assert.That(second.Result?.GetProperty("unchangedInARow").GetInt32(), Is.EqualTo(2));
            Assert.That(second.Result?.GetProperty("next").GetString(),
                Does.StartWith("this click on «Biblioteca» changed nothing 2 times in a row"));
            Assert.That(third.Result?.GetProperty("unchangedInARow").GetInt32(), Is.EqualTo(3));
            Assert.That(other.Result?.TryGetProperty("unchangedInARow", out _) ?? false, Is.False);
        });
    }

    [Test]
    public void TheRepeatedClickNamesThePlacesItsApplicationOpensStraightAt()
    {
        string steam = WindowsVisibleControlAdapter.RepeatedUnchangedNext("Library", 2, "Steam");
        string none = WindowsVisibleControlAdapter.RepeatedUnchangedNext("Aceptar", 2, "Bloc de notas");

        Assert.Multiple(() =>
        {
            Assert.That(steam, Does.Contain("app_open with appId \"Steam\" and place \"library\", "));
            Assert.That(steam, Does.Contain("\"results\" (placeValue: the query)"));
            Assert.That(none, Does.Not.Contain("app_open"));
            Assert.That(none, Does.EndWith("each time the window looked the same after it as before it"));
        });
    }

    private sealed class RoutedWorker(Func<JsonObject, string?> answer) : IUiaWorker
    {
        public ValueTask PrewarmAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            string? text = answer((JsonObject)JsonNode.Parse(commandJson)!);
            return ValueTask.FromResult(text is null ? null : JsonDocument.Parse(text));
        }
    }
}
