using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// pc-f6-sesiones (APLAZADOS f4-accesibilidad, 2026-10-25): the conversations asked by voice (conversation.*), run by
/// the App on the conversations its view's channel keeps (FieldProductChannel), never by the engine and never asking.
/// </summary>
[TestFixture]
public sealed class ConversationVoiceTests
{
    // «empieza una conversación nueva»: the turn that asks stays in the conversation on screen, whole, and the new one
    // starts once that turn let go; the result said so before the model answered.
    [Test]
    public async Task ANewConversationAskedByVoiceStartsAfterTheAnswerThatSaidIt()
    {
        using var fake = new FakeMind();
        fake.Script(Calling("conversation.new", new JsonObject()));
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string before = CurrentId(view);

            Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "empieza una conversación nueva" }))
                .Status, Is.EqualTo(200));
            Assert.That(await fake.WaitSeenAsync("session.new"), Is.True, "no new conversation started");
            Assert.That(await ViewModelHarness.UntilAsync(() => CurrentId(view) != before), Is.True);

            JsonObject result = Observation(fake);
            Assert.Multiple(() =>
            {
                Assert.That((string?)result["status"], Is.EqualTo("completed"));
                Assert.That((string?)result["opens"], Is.EqualTo("new_conversation"));
                Assert.That((bool?)result["afterThisAnswer"], Is.True);
                // The conversation on screen took its title from the person's first words, as the panel shows it.
                Assert.That((string?)result["thisAnswerStaysIn"], Is.EqualTo("empieza una conversación nueva"));
                Assert.That(fake.Seen.ToList().IndexOf("session.new"),
                    Is.GreaterThan(fake.Seen.ToList().LastIndexOf("turn.continue")),
                    "the mind started over inside the turn that asked");
                Assert.That(store.Load(before)?.Items.Select(static i => (string?)i?["text"]),
                    Is.EqualTo(new[] { "empieza una conversación nueva", "Listo." }),
                    "the turn that asked was not kept whole in its own conversation");
                Assert.That(viewModel.Messages, Is.Empty);
            });
        }
    }

    // «vuelve a la conversación de ayer»: the kept one opens after the answer, with what it held.
    [Test]
    public async Task AKeptConversationAskedByItsTitleOpensAfterTheAnswer()
    {
        using var fake = new FakeMind();
        fake.Script(Calling("conversation.open", new JsonObject { ["conversation"] = "ayer" }));
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            Assert.That(store.Save(Kept("old1", "Ayer", days: 1)), Is.True);

            Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "vuelve a la de ayer" })).Status,
                Is.EqualTo(200));
            Assert.That(await ViewModelHarness.UntilAsync(() => CurrentId(view) == "old1"), Is.True,
                "the conversation asked for did not open");

            JsonObject result = Observation(fake);
            Assert.Multiple(() =>
            {
                Assert.That((string?)result["status"], Is.EqualTo("completed"));
                Assert.That((string?)result["opens"]?["id"], Is.EqualTo("old1"));
                Assert.That((string?)result["opens"]?["title"], Is.EqualTo("Ayer"));
                Assert.That((bool?)result["afterThisAnswer"], Is.True);
                Assert.That(viewModel.Messages.Select(static m => m.Body), Is.EqualTo(new[] { "hola" }));
            });
        }
    }

    // A call whose arguments do not fit the catalog's schema opens nothing and says which argument is wrong.
    [Test]
    public async Task AnOpeningWithoutWhichConversationOpensNothing()
    {
        using var fake = new FakeMind();
        fake.Script(Calling("conversation.open", new JsonObject()));
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            string before = CurrentId(view);

            await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "abre una conversación" });
            Assert.That(await fake.WaitSeenAsync("turn.continue"), Is.True);
            Assert.That(await ViewModelHarness.UntilAsync(() => !viewModel.IsBusy), Is.True);

            Assert.That((string?)Observation(fake)["error"], Is.EqualTo("invalid_arguments"));
            Assert.That(CurrentId(view), Is.EqualTo(before));
            Assert.That(fake.Seen, Does.Not.Contain("session.new").And.Not.Contain("session.load"));
        }
    }

    // «¿qué conversaciones tengo?», «llama a esta Plan», «a la de ayer ponle Viaje»: the list says which is which and
    // when, a rename is read back, and a title that answers to several or none renames nothing.
    [Test]
    public async Task TheConversationsAreListedAndRenamedByVoice()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            Assert.That(store.Save(Kept("old1", "Ayer", days: 1)) && store.Save(Kept("old2", "Viaje a Lima", days: 3))
                && store.Save(Kept("old3", "Viaje a Cusco", days: 4)), Is.True);

            JsonObject listed = Run(viewModel, "conversation.list", new JsonObject());
            JsonArray conversations = listed["conversations"]!.AsArray();
            Assert.Multiple(() =>
            {
                Assert.That((string?)listed["verification"], Is.EqualTo("output_only"));
                Assert.That((int?)listed["totalCount"], Is.EqualTo(4));
                Assert.That(conversations.Select(static c => (string?)c?["title"]),
                    Is.EqualTo(new[] { "Conversación nueva", "Ayer", "Viaje a Lima", "Viaje a Cusco" }));
                Assert.That((bool?)conversations[0]?["current"], Is.True);
                Assert.That((string?)conversations[0]?["when"], Is.EqualTo("ahora"));
                Assert.That((string?)conversations[1]?["when"], Does.StartWith("ayer "));
            });

            JsonObject current = Run(viewModel, "conversation.rename", new JsonObject { ["title"] = "Plan" });
            JsonObject kept = Run(viewModel, "conversation.rename",
                new JsonObject { ["conversation"] = "AYER", ["title"] = "Viaje a Arica" });
            JsonObject several = Run(viewModel, "conversation.rename",
                new JsonObject { ["conversation"] = "viaje a", ["title"] = "Otro" });
            JsonObject none = Run(viewModel, "conversation.rename",
                new JsonObject { ["conversation"] = "Navidad", ["title"] = "Otro" });

            Assert.Multiple(() =>
            {
                Assert.That((string?)current["verification"], Is.EqualTo("readback"));
                Assert.That((string?)current["conversation"]?["title"], Is.EqualTo("Plan"));
                Assert.That(view.Sink.Events.Last(static e => (string?)e["type"] == "session")["label"]?.GetValue<string>(),
                    Is.EqualTo("Plan"));
                Assert.That((string?)kept["verification"], Is.EqualTo("readback"));
                Assert.That((string?)kept["previousTitle"], Is.EqualTo("Ayer"));
                Assert.That(store.Load("old1")?.Label, Is.EqualTo("Viaje a Arica"));
                Assert.That((string?)several["error"], Is.EqualTo("conversation_ambiguous"));
                Assert.That(several["matches"]?.AsArray().Select(static c => (string?)c?["id"]),
                    Is.EqualTo(new[] { "old1", "old2", "old3" }));
                Assert.That((string?)none["error"], Is.EqualTo("conversation_not_found"));
                Assert.That(store.Load("old2")?.Label, Is.EqualTo("Viaje a Lima"));
            });
        }
    }

    // The mind calls the operation once and then answers in words.
    internal static JsonObject Calling(string operation, JsonObject arguments) => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "action",
                ["operation"] = operation,
                ["arguments"] = arguments,
            },
            ["turn.continue"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "conversation",
                ["reply"] = "Listo.",
            },
        },
    };

    // What the model read back from the call (the turn.continue that followed it).
    internal static JsonObject Observation(FakeMind fake) =>
        (JsonObject)JsonNode.Parse((string)fake.Requests("turn.continue")[0]["observation"]!)!;

    private static JsonObject Run(MainWindowViewModel viewModel, string operation, JsonObject arguments) =>
        (JsonObject)JsonNode.Parse(viewModel.Conversation!(operation, arguments)!)!;

    // The conversation on screen, as the panel reads it.
    private static string CurrentId(ChannelHarness view)
    {
        FieldHttpResponse response = view.Channel.HandleHttpAsync("GET", "/sessions", null).GetAwaiter().GetResult();
        return (string)JsonNode.Parse(response.Body)!["sessions"]!.AsArray()
            .First(static s => (bool?)s?["current"] == true)!["id"]!;
    }

    private static FieldSessionStore.Session Kept(string id, string label, int days) => new(id, label,
        DateTimeOffset.UtcNow.AddDays(-days), DateTimeOffset.UtcNow.AddDays(-days),
        new JsonArray(new JsonObject { ["who"] = "you", ["text"] = "hola" }), null);
}
