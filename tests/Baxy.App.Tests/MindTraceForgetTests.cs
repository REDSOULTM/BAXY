using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Auditoría de la mente (2026-10-23): after «olvida todo» or deleting every conversation, the mind's trace kept the
/// person's words in clear text; the App asks the mind to forget it (trace.forget) on both paths.
/// </summary>
[TestFixture]
public sealed class MindTraceForgetTests
{
    [Test]
    public async Task DeletingAllConversationsAsksTheMindToForgetItsTrace()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (int status, _) = await view.SendAsync("DELETE", "/sessions", new JsonObject { ["scope"] = "all" });

            Assert.That(status, Is.EqualTo(200));
            Assert.That(await fake.WaitSeenAsync("trace.forget"), Is.True);
            List<string> seen = [.. fake.Seen];
            Assert.That(seen.IndexOf("session.new"), Is.LessThan(seen.IndexOf("trace.forget")),
                "the trace was forgotten before the mind left the conversation");
        }
    }

    [Test]
    public async Task ForgettingEverythingAsksTheMindToForgetItsTrace()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ((Action)typeof(MainWindowViewModel).GetField("EverythingForgotten",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!.GetValue(viewModel)!)();

            Assert.That(await fake.WaitSeenAsync("trace.forget"), Is.True);
        }
    }

    [Test]
    public async Task AMindThatIsNotUpIsNotAskedAndSaysSo()
    {
        await using (var viewModel = new MainWindowViewModel())
        {
            Assert.That(await viewModel.ForgetMindTraceAsync(CancellationToken.None), Is.False);
        }
    }
}
