using System.Reflection;
using System.Text.Json.Nodes;
using System.Windows;
using Microsoft.Web.WebView2.Wpf;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The view's event sockets (src/Baxy.App/FieldUiBridge.cs): they belong to the document that opened them, and a
/// document that leaves takes them with it (auditoría de la App, 2026-10-23: each one left stayed, and every event went
/// once more to each).
/// </summary>
[TestFixture]
public sealed class FieldUiBridgeTests
{
    [Test]
    [Apartment(ApartmentState.STA)]
    public async Task TheSocketsOfADocumentThatLeavesAreForgotten()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            var window = new Window();
            var bridge = new FieldUiBridge(window, new WebView2(), viewModel, new FieldTelemetrySampler(static () => null),
                CancellationToken.None);
            await using (bridge)
            {
                MethodInfo open = typeof(FieldUiBridge).GetMethod("OpenSocket", BindingFlags.Instance | BindingFlags.NonPublic)!;
                foreach (string id in (string[])["s1", "s2"])
                {
                    open.Invoke(bridge, [new JsonObject
                    {
                        ["socketId"] = id,
                        ["url"] = "wss://" + HistoricalFieldOriginPolicy.VirtualHost + "/events",
                    }]);
                }

                Assert.That(bridge.OpenSockets, Is.EqualTo(2));

                bridge.DocumentLeaving();

                Assert.That(bridge.OpenSockets, Is.Zero);
            }

            window.Close();
        }
    }

    // APP1 (BRG-a, review of the App 2026-11-09): only a closed list of exceptions was answered; any other left the view's
    // request with no answer for the 30 s the bridge gives one. Whatever the handling throws is answered at once, and what
    // the list did not expect is kept.
    [Test]
    public async Task ARequestIsAnsweredWhateverItsHandlingThrowsAndTheUnexpectedIsKept()
    {
        const string Failed = "The local BAXY bridge could not complete the request.";
        List<string> kept = [];
        void Keep(Exception failure) => kept.Add(failure.GetType().Name);

        string? fine = await FieldUiBridge.AnswerAsync(static () => Task.CompletedTask, static () => false, Keep);
        string? expected = await FieldUiBridge.AnswerAsync(static () => throw new System.IO.IOException(), static () => false, Keep);
        string? unexpected = await FieldUiBridge.AnswerAsync(
            static () => throw new System.Net.Http.HttpRequestException("the search failed"), static () => false, Keep);
        string? ownTime = await FieldUiBridge.AnswerAsync(
            static () => Task.FromException(new TaskCanceledException()), static () => false, Keep);
        string? closing = await FieldUiBridge.AnswerAsync(
            static () => Task.FromException(new OperationCanceledException()), static () => true, Keep);

        Assert.Multiple(() =>
        {
            Assert.That(fine, Is.Null);
            Assert.That(expected, Is.EqualTo(Failed));
            Assert.That(unexpected, Is.EqualTo(Failed), "an exception outside the list is answered too");
            Assert.That(ownTime, Is.EqualTo(Failed), "a call cancelled by its own time is no closing BAXY");
            Assert.That(closing, Is.EqualTo("BAXY is closing"));
            Assert.That(kept, Is.EqualTo(new[] { nameof(System.Net.Http.HttpRequestException), nameof(TaskCanceledException) }));
        });
    }

    [Test]
    public void TheViewLeavesTheWindowsResizeBorderFreeUnlessTheWindowIsMaximized()
    {
        // Owner, 2026-11-08: the frameless window could not be resized; the WebView covered the border WindowChrome sizes
        // it from. The view now stands that border off, and fills the screen when maximized (there is no border then).
        Assert.Multiple(() =>
        {
            Assert.That(MainWindow.WebViewMargin(WindowState.Normal), Is.EqualTo(new Thickness(MainWindow.ResizeBorder)));
            Assert.That(MainWindow.ResizeBorder, Is.GreaterThanOrEqualTo(4));
            Assert.That(MainWindow.WebViewMargin(WindowState.Maximized), Is.EqualTo(new Thickness(0)));
        });
    }
}
