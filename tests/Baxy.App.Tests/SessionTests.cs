using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>Opening a kept conversation and starting a new one (MainWindowViewModel) against the fake mind.</summary>
[TestFixture]
public sealed class SessionTests
{
    [Test]
    public async Task ATurnSentWhileASessionOpensRunsInThatSessionWhole()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["hold"] = new JsonObject { ["session.load"] = "go" } });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var kept = new ConversationMessage("BAXY", "lo de ayer", false, DateTimeOffset.Now);
            Task<bool> opening = viewModel.OpenSessionAsync(
                new JsonArray(new JsonObject { ["role"] = "user", ["content"] = "ayer" }), [kept], CancellationToken.None);
            Assert.That(await fake.WaitSeenAsync("session.load"), Is.True);

            Task turn = viewModel.SubmitAsync(new MissionInput("hola", MissionInputSource.Text),
                System.Diagnostics.Stopwatch.GetTimestamp(), CancellationToken.None);
            await Task.Delay(300);
            fake.Open("go");
            Assert.That(await opening, Is.True);
            await turn;

            Assert.That(viewModel.Messages.Select(static m => (m.IsUser, m.Body)), Is.EqualTo(new[]
            {
                (false, "lo de ayer"),
                (true, "hola"),
                (false, "hola"),
            }), "the turn ran across the opening and lost the person's words");
        }
    }

    [Test]
    public async Task ANewConversationTheMindCouldNotStartLeavesTheCurrentOne()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["fail"] = new JsonArray("session.new") });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            viewModel.Messages.Add(new ConversationMessage("Tú", "hola", true, DateTimeOffset.Now));

            bool started = await viewModel.StartNewUiSessionAsync(CancellationToken.None);

            Assert.That(await fake.WaitSeenAsync("session.new"), Is.True);
            Assert.That(started, Is.False, "the view started over while the model kept the old conversation");
            Assert.That(viewModel.Messages.Select(static m => m.Body), Is.EqualTo(new[] { "hola" }));
        }
    }

    [Test]
    public async Task ANewConversationStartsOnceTheMindStartedIt()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            viewModel.Messages.Add(new ConversationMessage("Tú", "hola", true, DateTimeOffset.Now));

            Assert.That(await viewModel.StartNewUiSessionAsync(CancellationToken.None), Is.True);

            Assert.That(fake.Seen, Does.Contain("session.new"));
            Assert.That(viewModel.Messages, Is.Empty);
        }
    }
}
