using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// A heartbeat's proposal card (FieldProductChannel): it says it went out as a Windows notification only when the host
/// sent it as one, never from the activity the view reads later.
/// </summary>
[TestFixture]
public sealed class ProposalCardTests
{
    [Test]
    public async Task AProposalIsSaidNotifiedOnlyOnceTheHostNotifiedIt()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            NativeTurnConfirmation asked = WaitingCalls.Ask(viewModel);
            JsonObject card = view.Sink.Items.Single(static i => (string?)i["who"] == "card");
            Assert.That(card["notified"], Is.Null);

            Notify(viewModel, asked);

            card = view.Sink.Items.Single(static i => (string?)i["who"] == "card");
            Assert.That((bool?)card["notified"], Is.True);
        }
    }

    [Test]
    public async Task ANotificationOfAnotherCallLeavesTheCardAsItIs()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            NativeTurnConfirmation asked = WaitingCalls.Ask(viewModel);

            Notify(viewModel, asked with { });

            Assert.That(view.Sink.Items.Single(static i => (string?)i["who"] == "card")["notified"], Is.Null);
        }
    }

    // The view model asks for the Windows notification of a proposal as it does (ProposalNotificationRequested).
    private static void Notify(MainWindowViewModel viewModel, NativeTurnConfirmation asked)
    {
        var raise = (Action<string, string, NativeTurnConfirmation>?)typeof(MainWindowViewModel)
            .GetField(nameof(MainWindowViewModel.ProposalNotificationRequested), BindingFlags.Instance | BindingFlags.NonPublic)!
            .GetValue(viewModel);
        Assert.That(raise, Is.Not.Null);
        raise!("¿Busco el clima de mañana?", "estás jugando", asked);
    }
}
