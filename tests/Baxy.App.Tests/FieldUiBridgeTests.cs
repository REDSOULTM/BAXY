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
}
