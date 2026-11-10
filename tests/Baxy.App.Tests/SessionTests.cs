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

    // Owner, 2026-11-08: «al momento de yo darle a nueva conversación … que el LLM reciba la instrucción de darle un
    // nombre a la conversación … para después yo poder ubicarla». The new one opens first; the name comes after it.
    [Test]
    public async Task TheConversationThatClosesIsNamedByTheModelOnceTheNewOneOpened()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject { ["session.title"] = new JsonObject { ["type"] = "session.titled", ["title"] = "Saludo inicial" } },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string closing = await TalkAsync(view, viewModel, "hola");
            int revision = SessionsRevision(view);

            Assert.That((await view.SendAsync("POST", "/sessions/new")).Status, Is.EqualTo(200));

            Assert.That(await ViewModelHarness.UntilAsync(() => store.Load(closing)?.Label == "Saludo inicial"), Is.True,
                "the model's name never reached the kept conversation");
            // the name is kept first and told to the view right after (FieldProductChannel): under load the disk could be
            // read between the two (APP1, full suite 10-11: 1 of 1185)
            bool told = await ViewModelHarness.UntilAsync(() => SessionsRevision(view) > revision);
            Assert.Multiple(() =>
            {
                List<string> seen = [.. fake.Seen];
                Assert.That(seen.IndexOf("session.title"), Is.GreaterThan(seen.IndexOf("session.new")),
                    "the person waited for the name before the new conversation opened");
                Assert.That(Requests(fake, "session.title").Single()["conversation"], Is.InstanceOf<JsonArray>());
                Assert.That(told, Is.True, "the view was never told the name changed");
            });
        }
    }

    [Test]
    public async Task AConversationThePersonNamedKeepsTheirName()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject { ["session.title"] = new JsonObject { ["type"] = "session.titled", ["title"] = "Saludo inicial" } },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string closing = await TalkAsync(view, viewModel, "hola");
            Assert.That((await view.SendAsync("POST", "/sessions/rename", new JsonObject { ["id"] = closing, ["title"] = "Mi saludo" })).Status,
                Is.EqualTo(200));

            Assert.That((await view.SendAsync("POST", "/sessions/new")).Status, Is.EqualTo(200));
            await Task.Delay(800);

            Assert.That(fake.Seen, Does.Not.Contain("session.title"));
            Assert.That(store.Load(closing)?.Label, Is.EqualTo("Mi saludo"));
        }
    }

    // REV_APP HIS-1 (2026-11-09): the name the person gave the open conversation lived in memory until its next save, so
    // a BAXY that ended any other way than by its own close lost it after the panel had shown it done.
    [Test]
    public async Task TheNameThePersonGivesTheOpenConversationIsKeptAtOnce()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string open = await TalkAsync(view, viewModel, "hola");
            Assert.That(await ViewModelHarness.UntilAsync(() => store.Load(open) is not null), Is.True);

            Assert.That((await view.SendAsync("POST", "/sessions/rename", new JsonObject { ["id"] = open, ["title"] = "Mi saludo" })).Status,
                Is.EqualTo(200));

            Assert.That(store.Load(open)?.Label, Is.EqualTo("Mi saludo"), "the name was only in memory");
            Assert.That(store.Load(open)?.LabelBy, Is.EqualTo(FieldSessionStore.LabelByPerson));
        }
    }

    // REV_APP HIS-1: a name that could not be written is not said done, and the conversation keeps the one it had.
    [Test]
    public async Task ANameThatCouldNotBeKeptIsNotSaidDone()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string open = await TalkAsync(view, viewModel, "hola");
            Assert.That(await ViewModelHarness.UntilAsync(() => store.Load(open) is not null), Is.True);

            using (NoWriting(open))
            {
                Assert.That((await view.SendAsync("POST", "/sessions/rename", new JsonObject { ["id"] = open, ["title"] = "Mi saludo" })).Status,
                    Is.Not.EqualTo(200), "a name that was not written was said done");
            }

            JsonObject current = await CurrentAsync(view);
            Assert.That((string?)current["label"], Is.EqualTo("hola"));
            Assert.That(store.Load(open)?.Label, Is.EqualTo("hola"));
        }
    }

    // REV_APP ASY-b and HIS-1: the save after each turn threw its result away, so a conversation the disk did not take
    // looked kept until BAXY closed. The history says it while it is so, and no more once a save went through.
    [Test]
    public async Task AConversationTheDiskDidNotTakeSaysSoUntilItIsKept()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string open = (string)(await CurrentAsync(view))["id"]!;
            Assert.That((bool?)(await view.SendAsync("GET", "/sessions")).Body["unsaved"], Is.False);
            int revision = SessionsRevision(view);

            using (NoWriting(open))
            {
                await TalkAsync(view, viewModel, "hola");
                Assert.That(await UnsavedBecomesAsync(view, true), Is.True, "nothing said the conversation was not kept");
                Assert.That(store.Load(open), Is.Null);
                Assert.That(SessionsRevision(view), Is.GreaterThan(revision), "the view was never told to read the history again");
            }

            Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "sigo" })).Status, Is.EqualTo(200));
            Assert.That(await UnsavedBecomesAsync(view, false), Is.True, "it still said not kept after a save went through");
            Assert.That(store.Load(open), Is.Not.Null);
        }
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task WithoutTheModelsNameTheConversationKeepsItsFirstWords(bool fails)
    {
        using var fake = new FakeMind();
        fake.Script(fails
            ? new JsonObject { ["fail"] = new JsonArray("session.title") }
            : new JsonObject { ["reply"] = new JsonObject { ["session.title"] = new JsonObject { ["type"] = "session.titled", ["title"] = "" } } });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string closing = await TalkAsync(view, viewModel, "qué hora es en Tokio");

            Assert.That((await view.SendAsync("POST", "/sessions/new")).Status, Is.EqualTo(200));
            Assert.That(await fake.WaitSeenAsync("session.title"), Is.True);
            await Task.Delay(500);

            Assert.That(store.Load(closing)?.Label, Is.EqualTo("qué hora es en Tokio"));
        }
    }

    // MEN1-M5 (AMD2 §7, RX 7600 on Vulkan): the person writes in the new conversation while the model names the one that
    // closed. Their turn goes to the mind at once and the name gives way to it (the fake's «yield», as Mind.title_of);
    // behind the name the turn stayed in the App until it answered, which here it never does by itself.
    [Test]
    public async Task ATurnWrittenWhileTheClosedConversationIsNamedDoesNotWaitForTheName()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string closing = await TalkAsync(view, viewModel, "hola");
            fake.Script(new JsonObject
            {
                ["hold"] = new JsonObject { ["session.title"] = "never" },
                ["yield"] = new JsonArray("session.title"),
                ["reply"] = new JsonObject { ["session.title"] = new JsonObject { ["type"] = "session.titled", ["title"] = "" } },
            });
            Assert.That((await view.SendAsync("POST", "/sessions/new")).Status, Is.EqualTo(200));
            Assert.That(await fake.WaitSeenAsync("session.title"), Is.True);

            Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "sigo" })).Status, Is.EqualTo(200));
            bool written = await fake.WaitSeenAsync("turn.decide", count: 2, seconds: 3);
            bool answered = await ViewModelHarness.UntilAsync(() => !viewModel.IsBusy && viewModel.Messages.Count >= 2, seconds: 5);

            List<string> seen = [.. fake.Seen];
            Assert.Multiple(() =>
            {
                Assert.That(written, Is.True, "the turn waited in the App behind the conversation's name");
                Assert.That(answered, Is.True, "the turn was not answered while the name was still asked");
                Assert.That(seen.IndexOf("session.title"), Is.GreaterThan(seen.IndexOf("session.new")));
                Assert.That(seen.LastIndexOf("turn.decide"), Is.GreaterThan(seen.IndexOf("session.title")));
                Assert.That(viewModel.Messages.Select(static message => message.Body), Is.EqualTo(new[] { "sigo", "hola" }),
                    "the new conversation is not the turn and its answer");
                Assert.That(store.Load(closing)?.Label, Is.EqualTo("hola"), "the conversation that closed lost its first words");
            });
        }
    }

    // INT17, revisión ciega: the conversation that closes went whole to the company to be named while BAXY thought by API,
    // even one the person had only with the model on this PC (opened from the history, or before switching). Only a model
    // on this PC names it; by API it keeps its first words. Ollama runs on this PC: it names it as BAXY's own does.
    [TestCase(false)]
    [TestCase(true)]
    public async Task AConversationIsNamedOnlyByAModelOnThisPc(bool ollama)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject { ["session.title"] = new JsonObject { ["type"] = "session.titled", ["title"] = "Saludo inicial" } },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            var store = new FieldSessionStore(MemoryOperationProtector.ResolveDataRoot());
            string closing = await TalkAsync(view, viewModel, "hola");
            ThinksElsewhere(viewModel.ExternalModelState, local: ollama);
            try
            {
                Assert.That((await view.SendAsync("POST", "/sessions/new")).Status, Is.EqualTo(200));
                if (ollama)
                {
                    Assert.That(await ViewModelHarness.UntilAsync(() => store.Load(closing)?.Label == "Saludo inicial"), Is.True);
                }
                else
                {
                    await Task.Delay(800);
                    Assert.That(fake.Seen, Does.Not.Contain("session.title"), "the conversation went to the company to be named");
                    Assert.That(store.Load(closing)?.Label, Is.EqualTo("hola"));
                }
            }
            finally
            {
                ThinksElsewhere(viewModel.ExternalModelState, local: null);
            }
        }
    }

    // REV_VISTA V-03 (P1, 2026-11-09): the header said «N pedidos · todo local» and the rail «Todo local» of a conversation
    // that had gone to a company's API, once the API was off. Each turn by API is marked where the conversation is kept (the
    // transcript, saved with the session), so the view can say it of this conversation, also when it is opened again later.
    // Ollama runs on this PC: its turns are not marked.
    [Test]
    public async Task ATurnByApiIsMarkedInTheConversationAndTheMarkStaysWithIt()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            string conversation = await TalkAsync(view, viewModel, "uno en este PC");
            try
            {
                ThinksElsewhere(viewModel.ExternalModelState, local: true);
                _ = await TalkAsync(view, viewModel, "dos con Ollama");
                ThinksElsewhere(viewModel.ExternalModelState, local: false);
                _ = await TalkAsync(view, viewModel, "tres por API");
            }
            finally
            {
                ThinksElsewhere(viewModel.ExternalModelState, local: null);
            }

            _ = await TalkAsync(view, viewModel, "cuatro en este PC");
            string[] ByApi(IEnumerable<JsonObject> items) => [.. items
                .Where(static i => (string?)i["who"] is "you" or "baxy" && (bool?)i["api"] == true)
                .Select(static i => (string?)i["who"] + ":" + ((string?)i["text"] ?? string.Empty))];
            JsonObject[] replies = [.. view.Sink.Items.Where(static i => (string?)i["who"] == "baxy")];
            Assert.That(replies, Has.Length.EqualTo(4));
            string[] expected = ["you:tres por API", "baxy:" + (string?)replies[2]["text"]];
            Assert.That(ByApi(view.Sink.Items), Is.EqualTo(expected));

            // kept with the conversation: opened again, it still says which turns went out
            Assert.That((await view.SendAsync("POST", "/sessions/new")).Status, Is.EqualTo(200));
            Assert.That((await view.SendAsync("POST", "/sessions/load", new JsonObject { ["id"] = conversation })).Status, Is.EqualTo(200));
            JsonArray reopened = (JsonArray)view.Sink.Events.Last(static e => (string?)e["type"] == "transcript")["items"]!;
            Assert.That(ByApi(reopened.OfType<JsonObject>()), Is.EqualTo(expected));
        }
    }

    // PRV1 D7 (INFORME_PRV1 §9, 2026-11-10): «Olvidar todo» takes the kept conversations and the conversation's log too
    // (OnEverythingForgotten), and the memory panel offered it only with memories: with none, nothing in the interface could
    // delete them. The host says what else it keeps, for the panel to offer the button whenever there is any of it.
    [Test]
    public async Task WhatForgettingEverythingTakesBesidesTheMemoriesIsSaid()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            JsonObject kept = (await view.SendAsync("GET", "/kept")).Body;
            Assert.That(((int?)kept["conversations"], (bool?)kept["log"]), Is.EqualTo((0, false)));

            _ = await TalkAsync(view, viewModel, "hola");
            Assert.That((bool?)(await view.SendAsync("GET", "/kept")).Body["log"], Is.True, "the conversation's log holds its words");
            Assert.That((await view.SendAsync("POST", "/sessions/new")).Status, Is.EqualTo(200));
            int? conversations = null;
            for (int tries = 0; tries < 50 && conversations != 1; tries++)
            {
                conversations = (int?)(await view.SendAsync("GET", "/kept")).Body["conversations"];
                if (conversations != 1)
                {
                    await Task.Delay(100);
                }
            }

            Assert.That(conversations, Is.EqualTo(1), "the closed conversation is kept; the one on screen is not counted, it stays");
        }
    }

    // VIS2 blind review (P1, 2026-11-10): a long conversation drops its oldest items (FieldTranscript.MaximumItems), and with
    // them the turns by API: the header said «todo local» again. The first item kept carries «apiBefore» instead.
    [Test]
    public void ATurnByApiThatFallsOffALongConversationLeavesItsMarkOnTheFirstKept()
    {
        var transcript = new FieldTranscript();
        transcript.You("por API", byApi: true);
        transcript.Words("Respondido por la API.", null, byApi: true);
        for (int turn = 0; turn < FieldTranscript.MaximumItems / 2; turn++)
        {
            transcript.You("local " + turn);
            transcript.Words("Listo.", null);
        }

        JsonArray kept = transcript.Snapshot();
        Assert.Multiple(() =>
        {
            Assert.That(kept, Has.Count.EqualTo(FieldTranscript.MaximumItems));
            Assert.That(kept.OfType<JsonObject>().Count(static i => (bool?)i["api"] == true), Is.Zero);
            Assert.That((bool?)kept[0]!["apiBefore"], Is.True, "what went out before the kept items is still said");
            Assert.That(kept.OfType<JsonObject>().Count(static i => i["apiBefore"] is not null), Is.EqualTo(1));
        });
    }

    // As ExternalModel is once its translator answers (StartAsync): connected to a company's API, or to Ollama on this PC;
    // null, back to BAXY's own model. Only the state: no translator runs here.
    private static void ThinksElsewhere(ExternalModel model, bool? local)
    {
        const System.Reflection.BindingFlags Private = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
        typeof(ExternalModel).GetProperty(nameof(ExternalModel.Active), Private)!.SetValue(model, local is not null);
        typeof(ExternalModel).GetField("_activeLocal", Private)!.SetValue(model, local == true);
    }

    // A turn of the person's in the conversation on screen, answered; the conversation's id.
    private static async Task<string> TalkAsync(ChannelHarness view, MainWindowViewModel viewModel, string text)
    {
        Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = text })).Status, Is.EqualTo(200));
        Assert.That(await ViewModelHarness.UntilAsync(() => !viewModel.IsBusy && viewModel.Messages.Count >= 2), Is.True);
        JsonArray sessions = (JsonArray)(await view.SendAsync("GET", "/sessions")).Body["sessions"]!;
        return (string)sessions.OfType<JsonObject>().Single(static s => (bool?)s["current"] == true)["id"]!;
    }

    private static async Task<JsonObject> CurrentAsync(ChannelHarness view) =>
        ((JsonArray)(await view.SendAsync("GET", "/sessions")).Body["sessions"]!).OfType<JsonObject>()
            .Single(static s => (bool?)s["current"] == true);

    private static async Task<bool> UnsavedBecomesAsync(ChannelHarness view, bool unsaved)
    {
        var clock = System.Diagnostics.Stopwatch.StartNew();
        while (clock.Elapsed < TimeSpan.FromSeconds(10))
        {
            if ((bool?)(await view.SendAsync("GET", "/sessions")).Body["unsaved"] == unsaved)
            {
                return true;
            }

            await Task.Delay(20);
        }

        return false;
    }

    // While it lives, the conversation's file cannot be written: a folder sits where the store writes its copy first.
    private static NoWrite NoWriting(string id) =>
        new(Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "sessions", id + ".json.tmp"));

    private sealed class NoWrite : IDisposable
    {
        private readonly string _folder;

        internal NoWrite(string folder)
        {
            _folder = folder;
            Directory.CreateDirectory(folder);
        }

        public void Dispose() => Directory.Delete(_folder);
    }

    private static int SessionsRevision(ChannelHarness view) => view.Sink.Events
        .Where(static e => (string?)e["type"] == "surfaces")
        .Select(static e => (int?)e["sessions_revision"] ?? 0)
        .DefaultIfEmpty(0)
        .Last();

    private static List<JsonObject> Requests(FakeMind fake, string type) =>
    [
        .. File.ReadAllLines(Path.Combine(fake.Folder, "requests.jsonl"))
            .Select(static line => (JsonObject)JsonNode.Parse(line)!)
            .Where(r => (string?)r["type"] == type),
    ];

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
