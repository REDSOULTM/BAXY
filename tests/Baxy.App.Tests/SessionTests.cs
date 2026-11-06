using System.IO;
using System.Text.Json.Nodes;
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

    // BAXY Renew al máximo 11.4: the view's «borrar todo» deletes every kept conversation, only by its own request.
    [Test]
    public async Task DeletingAllConversationsLeavesNoneKept()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            Assert.That(store.Save(Kept("old1")) && store.Save(Kept("old2")), Is.True);
            string log = WriteLog();

            Assert.That((await view.SendAsync("DELETE", "/sessions")).Status, Is.EqualTo(400));
            Assert.That(store.List(), Has.Count.EqualTo(2));

            (int status, JsonObject body) = await view.SendAsync("DELETE", "/sessions", new JsonObject { ["scope"] = "all" });

            Assert.That(status, Is.EqualTo(200));
            Assert.That((int?)body["deleted"], Is.EqualTo(2));
            Assert.That(store.List(), Is.Empty);
            Assert.That(File.Exists(log), Is.False, "the conversation log stayed in clear text");
            Assert.That(fake.Seen, Does.Contain("session.new"));
        }
    }

    // BAXY Renew al máximo 11.4: memory forgot everything (the chat's «olvida todo»): the kept conversations go with it.
    [Test]
    public async Task ForgettingEverythingDeletesTheKeptConversations()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            Assert.That(store.Save(Kept("old1")), Is.True);
            string log = WriteLog();

            // The chat's memory.forget of everything, as the loop tells it (NativeTurnLoop.Host.ForgotEverything).
            const System.Reflection.BindingFlags Private =
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
            var loop = (NativeTurnLoop)typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            ((NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!).ForgotEverything!();

            Assert.That(store.List(), Is.Empty);
            Assert.That(File.Exists(log), Is.False, "the conversation log stayed in clear text");
        }
    }

    // A line of the private conversation log where the view model keeps it (ConversationLog.CreateDefault).
    private static string WriteLog()
    {
        string folder = Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "conversation");
        new ConversationLog(folder).Append(new ConversationMessage("BAXY", "Tu ciudad es Viña del Mar.", false,
            DateTimeOffset.Now));
        string log = Path.Combine(folder, "conversation.v1.jsonl");
        Assert.That(File.Exists(log), Is.True);
        return log;
    }

    private static FieldSessionStore.Session Kept(string id) => new(id, "Ayer", DateTimeOffset.UtcNow.AddDays(-1),
        DateTimeOffset.UtcNow.AddDays(-1), new JsonArray(new JsonObject { ["who"] = "you", ["text"] = "hola" }), null);
}
