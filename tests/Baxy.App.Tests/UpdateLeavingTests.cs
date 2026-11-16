using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// MEN3 (VIVO24B, 15-11-2026): to «Baxi, actualízate» BAXY closed for the update with the turn unanswered until the new
/// version said «Me actualicé». The engine asks the App to exit before the install's receipt reaches the turn: closing
/// waits for that receipt and BAXY's own line about it (FieldProductChannel.BeforeClosingAsync).
/// </summary>
[TestFixture]
public sealed class UpdateLeavingTests
{
    private const string Line = "Voy a actualizarme a la 1.5.5; me cierro y vuelvo en un momento.";

    [Test]
    public async Task ClosingAsTheInstallerStartsWaitsForItsReceiptAndSaysWhereBaxyGoes()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            NativeTurnLoop.Host host = HostOf(viewModel);
            host.StepStarted!("c1", UpdatePanel.Operation, new JsonObject { ["action"] = "install" });
            // The exit event comes first: the receipt is still on its way.
            Task closing = view.Channel.BeforeClosingAsync();
            await Task.Delay(300);
            Assert.That(closing.IsCompleted, Is.False, "closing waits for the install's receipt");

            host.StepCompleted!(Step(installerStarted: true));
            await closing;

            Assert.That(Said(view), Has.One.EqualTo(Line));
        }
    }

    [Test]
    public async Task AnInstallThatDidNotStartAndAnyOtherExitHaveNothingToWaitFor()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            Stopwatch plain = Stopwatch.StartNew();
            await view.Channel.BeforeClosingAsync();
            plain.Stop();

            NativeTurnLoop.Host host = HostOf(viewModel);
            host.StepStarted!("c1", UpdatePanel.Operation, new JsonObject { ["action"] = "install" });
            host.StepCompleted!(Step(installerStarted: false));
            Stopwatch failed = Stopwatch.StartNew();
            await view.Channel.BeforeClosingAsync();
            failed.Stop();

            Assert.Multiple(() =>
            {
                Assert.That(plain.Elapsed, Is.LessThan(TimeSpan.FromSeconds(1)));
                Assert.That(failed.Elapsed, Is.LessThan(TimeSpan.FromSeconds(1)));
                Assert.That(Said(view), Has.None.StartsWith("Voy a actualizarme"));
            });
        }
    }

    private static NativeTurnStep Step(bool installerStarted) =>
        new(UpdatePanel.Operation, new JsonObject { ["action"] = "install" },
            installerStarted ? OperationStatuses.Completed : OperationStatuses.Failed, Verified: false,
            installerStarted ? null : "baxy_update_installer_not_started", 12,
            new JsonObject
            {
                ["observed"] = new JsonObject
                {
                    ["installed"] = "1.5.4", ["latest"] = "1.5.5", ["installerStarted"] = installerStarted, ["updated"] = false,
                },
            }.ToJsonString(), "c1", Sent: true);

    private static NativeTurnLoop.Host HostOf(MainWindowViewModel viewModel)
    {
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
        return (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
    }

    private static IEnumerable<string?> Said(ChannelHarness view) =>
        view.Sink.Items.Where(static i => (string?)i["who"] == "sys").Select(static i => (string?)i["text"]);
}
