using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The person's Sí or No (POST /confirmation/answer, the toast): it answers the call whose card they pressed, now, or it
/// says why not; it is never taken and lost.
/// </summary>
[TestFixture]
public sealed class ConfirmationAnswerTests
{
    [Test]
    public async Task AnAnswerPressedWhileATurnRunsIsRefusedNotLost()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            WaitingCalls.Ask(viewModel);
            WaitingCalls.Busy(viewModel, true);

            (int status, JsonObject body) = await view.SendAsync("POST", "/confirmation/answer", new JsonObject { ["approve"] = true });

            Assert.That(status, Is.EqualTo(409));
            Assert.That((string?)body["error"], Is.EqualTo("turn_in_progress"));
            Assert.That(viewModel.HasPendingConfirmation, Is.True);
        }
    }

    [Test]
    public async Task AnAnswerForACardThatIsNotTheWaitingOneIsRefused()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            WaitingCalls.Ask(viewModel);

            (int status, JsonObject body) = await view.SendAsync("POST", "/confirmation/answer",
                new JsonObject { ["approve"] = true, ["card"] = "k1-000000" });

            Assert.That(status, Is.EqualTo(409));
            Assert.That((string?)body["error"], Is.EqualTo("card_not_pending"));
            Assert.That(viewModel.HasPendingConfirmation, Is.True);
        }
    }

    [Test]
    public async Task AnAnswerForTheWaitingCardIsTaken()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            WaitingCalls.Ask(viewModel);
            string card = (string)view.Sink.Items.Single(static i => (string?)i["who"] == "card")["id"]!;

            (int status, JsonObject body) = await view.SendAsync("POST", "/confirmation/answer",
                new JsonObject { ["approve"] = false, ["card"] = card });

            Assert.That(status, Is.EqualTo(200));
            Assert.That((bool?)body["ok"], Is.True);
            Assert.That(viewModel.Messages.Select(static m => m.Body), Does.Contain("No"));
        }
    }

    [Test]
    public async Task AToastPressedForAProposalThatEndedDoesNotAnswerTheNextOne()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            ViewModelHarness.AcceptTurns(viewModel);
            NativeTurnConfirmation first = WaitingCalls.Ask(viewModel);
            WaitingCalls.Resolve(viewModel, "dropped");
            NativeTurnConfirmation second = WaitingCalls.Ask(viewModel);

            Assert.That(await viewModel.AnswerConfirmationAsync(true, System.Diagnostics.Stopwatch.GetTimestamp(),
                CancellationToken.None, first), Is.False, "a late press on the first toast approved the second call");
            Assert.That(viewModel.Messages, Is.Empty);

            Assert.That(await viewModel.AnswerConfirmationAsync(false, System.Diagnostics.Stopwatch.GetTimestamp(),
                CancellationToken.None, second), Is.True);
        }
    }
}
