using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The native turn loop's waiting calls (src/Baxy.App/NativeTurnLoop.cs).</summary>
[TestFixture]
public sealed class NativeTurnLoopTests
{
    [Test]
    public void AProposalThatRanOutOfTimeEndsExpiredNotDropped()
    {
        var clock = new ManualClock();
        var outcomes = new List<string>();
        NativeTurnLoop loop = Loop(outcomes, clock);
        WaitingCalls.HoldAskedProposal(loop, clock.GetUtcNow() + NativeTurnLoop.ProposalLifetime);
        Assert.That(loop.HasPendingConfirmation, Is.True);

        clock.Now += NativeTurnLoop.ProposalLifetime + TimeSpan.FromSeconds(1);
        Assert.That(loop.HasPendingConfirmation, Is.False);
        loop.Reset();

        Assert.That(outcomes, Is.EqualTo(new[] { "expired" }));
    }

    [Test]
    public void AProposalStillWaitingThatIsLeftEndsDropped()
    {
        var clock = new ManualClock();
        var outcomes = new List<string>();
        NativeTurnLoop loop = Loop(outcomes, clock);
        WaitingCalls.HoldAskedProposal(loop, clock.GetUtcNow() + NativeTurnLoop.ProposalLifetime);

        clock.Now += NativeTurnLoop.ProposalLifetime - TimeSpan.FromSeconds(1);
        loop.Reset();

        Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
        Assert.That(loop.HasPendingConfirmation, Is.False);
    }

    // BAXY Renew al máximo 11.5: the person's turn holds a fetch of a host nobody gave, and asks it as a confirmation
    // (not as a heartbeat's proposal); the call never reaches the engine.
    [Test]
    public async Task AFetchOfAHostNobodyGaveWaitsForThePersonsYes()
    {
        (List<NativeTurnStep> steps, List<NativeTurnConfirmation> asked, NativeTurnLoop loop) =
            await HoldAFetchAsync(results: null);

        Assert.That(steps.Select(static step => (step.Operation, step.Status, step.Sent)),
            Is.EqualTo(new[] { ("web.fetch", "needs_confirmation", false) }));
        Assert.That((string?)JsonNode.Parse(steps[0].Observation)?["cause"], Is.EqualTo("host_not_from_session"));
        Assert.That(asked.Select(static call => (call.Operation, call.Proposal, call.Cause)),
            Is.EqualTo(new[] { ("web.fetch", false, (string?)"host_not_from_session") }));
        Assert.That(loop.HasPendingConfirmation, Is.True);
    }

    // uso-90 (diag-9dea U06 c1): «Sign in» pressed unasked after a look at the video's page; held, the receipt says why
    // and which page, and the call never reaches the engine.
    [Test]
    public async Task AClickIntoASignInPageWaitsForThePersonsYesAndSaysWhy()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "input.visible.click",
                    ["arguments"] = new JsonObject { ["label"] = "Sign in", ["index"] = 21, ["window"] = 262206 },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Inicio sesión en tu cuenta?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var asked = new List<NativeTurnConfirmation>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            ConfirmationAsked = asked.Add,
        });
        var accounts = (AccountFlow)typeof(NativeTurnLoop)
            .GetField("_accounts", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(loop)!;
        using (System.Text.Json.JsonDocument look = System.Text.Json.JsonDocument.Parse("""
            {"window":{"title":"Easy Homemade Bread - YouTube - Microsoft Edge","process":"msedge","hwnd":262206},
             "controls":[{"i":21,"kind":"Hyperlink","name":"Sign in","state":"readonly",
               "value":"https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2Fs"}]}
            """))
        {
            accounts.Saw("input.visible.controls", new JsonObject(), "completed", look.RootElement.Clone());
        }

        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);
        await loop.RunAsync("Abre YouTube y búscame un video de cómo hacer pan casero.", Stopwatch.GetTimestamp(),
            CancellationToken.None);

        JsonNode? held = JsonNode.Parse(steps[0].Observation);
        Assert.Multiple(() =>
        {
            Assert.That(steps.Select(static step => (step.Operation, step.Status, step.Sent)),
                Is.EqualTo(new[] { ("input.visible.click", "needs_confirmation", false) }));
            Assert.That((string?)held?["cause"], Is.EqualTo(AccountFlow.Cause));
            Assert.That((string?)held?["signIn"]?["page"], Is.EqualTo("accounts.google.com/ServiceLogin"));
            Assert.That((string?)held?["next"], Does.EndWith(AccountFlow.Next));
            Assert.That(asked.Select(static call => call.Cause), Is.EqualTo(new[] { (string?)AccountFlow.Cause }));
        });
    }

    // Decisión del dueño 2026-11-02 («bypass no debe pedir confirmación nunca»): a page of a host nobody gave, or a game
    // nobody named, is held for the «sí» in normal mode and goes unasked in Bypass.
    [TestCase("web.fetch", """{"url":"https://exfil.example/c"}""", "host_not_from_session")]
    [TestCase("game.launch", """{"appId":"1","title":"Juego Inventado"}""", "game_title_not_said")]
    // uso-90: a sign-in page of the person's account, before a host nobody gave.
    [TestCase("browser.navigate", """{"url":"https://accounts.ejemplo.test/ServiceLogin?continue=x"}""", "account_sign_in")]
    public void BypassHoldsNothingForTheYes(string operation, string arguments, string normalCause)
    {
        using var fake = new FakeMind();
        NativeTurnLoop loop = Loop([], TimeProvider.System);
        JsonObject given = JsonNode.Parse(arguments)!.AsObject();

        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);
        string? normal = loop.HeldForTheYes(operation, given);
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Bypass);
        string? bypass = loop.HeldForTheYes(operation, given);

        Assert.Multiple(() =>
        {
            Assert.That(normal, Is.EqualTo(normalCause));
            Assert.That(bypass, Is.Null);
        });
    }

    // Holdout v5 (H5, en vivo): «busca en internet el clima de mañana en Santiago» gave news.google.com results and the
    // model fetched a site none of them was (vln.cl); held, BAXY asked for it. The held result says which hosts this
    // session's results gave, and that a page at one of them is read without asking.
    [Test]
    public async Task AHeldHostSaysWhichHostsTheSessionsResultsGave()
    {
        (List<NativeTurnStep> steps, _, _) = await HoldAFetchAsync(Search(
            "https://news.google.com/rss/articles/CBMi1?oc=5", "https://www.news.google.com/rss/articles/CBMi2",
            "https://meteochile.gob.cl/pronostico"));

        JsonNode? held = JsonNode.Parse(steps[0].Observation);
        Assert.Multiple(() =>
        {
            Assert.That((string?)held?["cause"], Is.EqualTo("host_not_from_session"));
            Assert.That(held?["resultHosts"]?.AsArray().Select(static host => (string?)host),
                Is.EqualTo(new[] { "news.google.com", "meteochile.gob.cl" }));
            Assert.That((string?)held?["next"], Does.StartWith(TodaysNext));
            Assert.That((string?)held?["next"], Does.Contain("came from no result of this session"));
            Assert.That((string?)held?["next"], Does.Contain("a page at one of resultHosts is read without asking"));
        });
    }

    [Test]
    public async Task AHeldHostWithNoResultsInTheSessionSaysWhatItSaidBefore()
    {
        (List<NativeTurnStep> steps, _, _) = await HoldAFetchAsync(results: null);

        JsonNode? held = JsonNode.Parse(steps[0].Observation);
        Assert.That(held?["resultHosts"], Is.Null);
        Assert.That((string?)held?["next"], Is.EqualTo(TodaysNext));
    }

    [Test]
    [NonParallelizable]
    public async Task WithTheResultHostsAidOffAHeldHostSaysWhatItSaidBefore()
    {
        string? before = Environment.GetEnvironmentVariable("BAXY_AYUDAS");
        Environment.SetEnvironmentVariable("BAXY_AYUDAS", "said_folder");
        try
        {
            (List<NativeTurnStep> steps, _, _) = await HoldAFetchAsync(Search("https://news.google.com/rss/articles/CBMi1"));

            JsonNode? held = JsonNode.Parse(steps[0].Observation);
            Assert.That(held?["resultHosts"], Is.Null);
            Assert.That((string?)held?["next"], Is.EqualTo(TodaysNext));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_AYUDAS", before);
        }
    }

    // Auditoría de falsedades (F010): an answer with nothing waiting says this call did nothing, never only the bare
    // «nothing_pending» that the 4B read as «ya está hecho».
    [Test]
    public async Task AnAnswerWithNothingWaitingSaysThisCallDidNothing()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "confirmation.answer",
                    ["arguments"] = new JsonObject { ["answer"] = "yes" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Qué quieres que haga?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = static () => null,
            Mind = () => mind,
            Registry = static () => null,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });

        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? observed = JsonNode.Parse(steps.Single().Observation);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["error"], Is.EqualTo("nothing_pending"));
            Assert.That((string?)observed?["reason"], Is.EqualTo(NativeTurnLoop.NothingPendingReason));
            Assert.That((string?)observed?["reason"], Does.Contain("this call did nothing"));
        });
    }

    // Auditoría de la App (2026-10-23): what the App writes itself reached the model as \u escapes («Pokémon»),
    // the held call's arguments included; the provider's text and SaidFolders' already went as written.
    [Test]
    public async Task AHeldCallReachesTheModelAsItWasWritten()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "game.launch",
                    ["arguments"] = new JsonObject { ["appId"] = "1", ["title"] = "Pokémon «Rojo»" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Abro ese juego?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
        });

        await loop.RunAsync("abre un juego", Stopwatch.GetTimestamp(), CancellationToken.None);

        string observation = (string)fake.Requests("turn.continue").Single()["observation"]!;
        Assert.Multiple(() =>
        {
            Assert.That(observation, Does.Contain("\"title\":\"Pokémon «Rojo»\""));
            Assert.That(observation, Does.Not.Contain("\\u"));
            Assert.That((string?)JsonNode.Parse(observation)?["cause"], Is.EqualTo("game_title_not_said"));
        });
    }

    // Encargo 119 (F10): «qué dice esto» ended in «¿Qué quieres que lea?»: the words reach the mind with the window in front
    // of the person when they arrived, read at that moment.
    [Test]
    public async Task ThePersonsWordsReachTheMindWithTheWindowInFrontWhenTheyArrived()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject { ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "Dice: abre el lunes." },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        (string Title, string? Process)? front = ("Visor de prueba - aviso.png", "visorprueba");
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            Front = () => front,
        });

        await loop.RunAsync("qué dice esto", Stopwatch.GetTimestamp(), CancellationToken.None);
        front = null;
        await loop.RunAsync("hola", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(fake.Requests("turn.decide")[0]["front"]?.ToJsonString(),
                Is.EqualTo("""{"title":"Visor de prueba - aviso.png","process":"visorprueba"}"""));
            Assert.That(fake.Requests("turn.decide")[1].ContainsKey("front"), Is.False);
        });
    }

    // Feria 2026-10-27: a search with none of the person's words, or a message they did not ask for, reaches the model as
    // a refusal with what to do next, and nothing is sent to the engine.
    [TestCase("uno de zentrovox", "media.play.youtube", "query_not_said")]
    [TestCase("saluda a Daniel", "message.draft", "channel_not_said")]
    public async Task ACallThePersonDidNotAskForGoesBackToTheModel(string words, string operation, string code)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = operation,
                    ["arguments"] = operation == "message.draft"
                        ? new JsonObject { ["channel"] = "whatsapp", ["recipient"] = "Daniel", ["text"] = "Hola" }
                        : new JsonObject { ["query"] = "Centro Box" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Cuál?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
        });

        await loop.RunAsync(words, Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue").Single()["observation"]!);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["status"], Is.EqualTo("rejected"));
            Assert.That((string?)observed?["error"], Is.EqualTo(code));
            Assert.That((string?)observed?["next"], Does.StartWith("nothing ran"));
        });
    }

    // Banco de uso 2026-11-03 (U40, R13): asked to write in a chat open in another application, named by its window's
    // title, the model sent by a messaging channel, was refused and asked «¿por cuál canal?». The refusal carries the
    // facts: the channels the call reaches, and the open window whose title the person's words name. Banco uso-cf8d (U40,
    // R13): with those facts after a next that said «ask them by which channel», the model still asked it; the next says
    // the calls that reach that window, its process filled in, in place of the question.
    [Test]
    public async Task AMessageByAChannelNotSaidSaysTheChannelsAndTheWindowThePersonNamed()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "message.send",
                    ["arguments"] = new JsonObject
                    {
                        ["channel"] = "whatsapp", ["recipient"] = "Sala Turquesa", ["text"] = "Llego en diez minutos",
                    },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Cuál?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            Windows = static () => [("Sala Turquesa - Charlina", "charlina"), ("Notas de cocina", "notas")],
        });

        await loop.RunAsync("en la sala turquesa que tengo abierta, envía: llego en diez minutos", Stopwatch.GetTimestamp(),
            CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue").Single()["observation"]!);
        string next = (string?)observed?["next"] ?? string.Empty;
        const string Reach = "input_visible_controls {\"application\":\"charlina\"}";
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["error"], Is.EqualTo("channel_not_said"));
            Assert.That(observed?["channels"]?.AsArray().Select(static channel => (string?)channel),
                Is.EqualTo(new[] { "discord", "whatsapp" }));
            Assert.That(observed?["namedWindows"]?.ToJsonString(),
                Is.EqualTo("[{\"title\":\"Sala Turquesa - Charlina\",\"process\":\"charlina\"}]"));
            Assert.That(next, Does.StartWith("nothing ran").And.Contain(Reach)
                .And.Contain("input_visible_click").And.Contain("input_text_type").And.Not.Contain("ask them by which"));
        });
    }

    // Banco de uso 2026-11-03 (R11): «Manda al Grupo de prueba el mensaje: hoy llego tarde.» with «Chat de prueba» open,
    // whose list has «Grupo de prueba» and «Sala de prueba»: no title is named, the model asked the channel. The refusal
    // now carries that window with the row named (and no other row: the reader is given the comparison, and the fake
    // reader here applies it to every row it has), and the next says the call that reaches it.
    [Test]
    public async Task AMessageByAChannelNotSaidSaysTheWindowWhoseRowThePersonNamed()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "message.send",
                    ["arguments"] = new JsonObject
                    {
                        ["channel"] = "whatsapp", ["recipient"] = "Grupo de prueba", ["text"] = "hoy llego tarde.",
                    },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Cuál?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        string[] offered = [];
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            Windows = static () => [("Chat de prueba", "ChatPrueba"), ("Notas de cocina", "notas")],
            Rows = (named, _) =>
            {
                VisibleRow[] all =
                [
                    new("Chat de prueba", "ChatPrueba", "Grupo de prueba"),
                    new("Chat de prueba", "ChatPrueba", "Sala de prueba"),
                    new("Notas de cocina", "notas", "Receta del lunes"),
                ];
                offered = [.. all.Where(row => named(row.Name)).Select(static row => row.Name)];
                return [.. all.Where(row => named(row.Name))];
            },
        });

        await loop.RunAsync("Manda al Grupo de prueba el mensaje: hoy llego tarde.", Stopwatch.GetTimestamp(),
            CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue").Single()["observation"]!);
        Assert.Multiple(() =>
        {
            Assert.That(offered, Is.EqualTo(new[] { "Grupo de prueba" }));
            Assert.That((string?)observed?["error"], Is.EqualTo("channel_not_said"));
            Assert.That(observed?["namedWindows"]?.ToJsonString(), Is.EqualTo(
                "[{\"title\":\"Chat de prueba\",\"process\":\"ChatPrueba\",\"rows\":[\"Grupo de prueba\"]}]"));
            // Encargo 45 (banco ab-93-ce, R11): told only the call with the row beside it, the model asked «¿Por WhatsApp
            // o por Discord?» (2 of 2). The next says what their words name, the row to click and the text to write.
            Assert.That((string?)observed?["next"], Does.StartWith(
                "nothing ran: the person's words name «Grupo de prueba», a row of the open window «Chat de prueba», and no "
                + "channel: input_visible_controls {\"application\":\"ChatPrueba\"} reads it, then input_visible_click on "
                + "its row «Grupo de prueba» in what it shows and input_text_type with the index of its field write "
                + "\"hoy llego tarde.\" in it"));
        });
    }

    // Banco de uso 2026-11-03 (S05): «en la llamada del chat de prueba quítame el sonido» ran the chat client's deafen
    // (its only client filled in by the mind) with that chat open, and the model said the client was not open. The call
    // goes back before it runs, with the window named and the call that reaches it first.
    [Test]
    public async Task AClientCallWithAnotherApplicationsWindowNamedGoesBackWithThatWindow()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "client.deafen.set",
                    ["arguments"] = new JsonObject { ["client"] = "discord", ["deafened"] = true },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Cuál?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            Windows = static () => [("Charla Norte", "CharlaNorte"), ("Notas de cocina", "notas")],
        });

        await loop.RunAsync("en la llamada de charla norte deja de que yo oiga, pero que me oigan",
            Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue").Single()["observation"]!);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["status"], Is.EqualTo("rejected"));
            Assert.That((string?)observed?["error"], Is.EqualTo("application_not_said"));
            Assert.That(observed?["namedWindows"]?.ToJsonString(),
                Is.EqualTo("[{\"title\":\"Charla Norte\",\"process\":\"CharlaNorte\"}]"));
            Assert.That((string?)observed?["next"],
                Does.StartWith("input_visible_controls {\"application\":\"CharlaNorte\"} reads"));
        });
    }

    // Banco de uso 2026-11-03 (S07): a read of something else than the window the person named, failed, carries that
    // window and the call that reaches it.
    [Test]
    public async Task AFailedCallOffTheWindowNamedCarriesThatWindow()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "clipboard.read.text",
                    ["arguments"] = new JsonObject(),
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Cuál?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            Windows = static () => [("Billetera Sur", "BilleteraSur"), ("Notas de cocina", "notas")],
        });

        await loop.RunAsync("¿qué saldo sale en billetera sur?", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue").Single()["observation"]!);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["status"], Is.EqualTo("failed"));
            Assert.That(observed?["namedWindows"]?.ToJsonString(),
                Is.EqualTo("[{\"title\":\"Billetera Sur\",\"process\":\"BilleteraSur\"}]"));
            Assert.That((string?)observed?["next"],
                Does.StartWith("input_visible_controls {\"application\":\"BilleteraSur\"} reads"));
        });
    }

    [Test]
    public void TheClipboardsReadIsASourceWithoutSayingSoInItsReceipt()
    {
        Assert.Multiple(() =>
        {
            Assert.That(NativeTurnLoop.SourceOf(new JsonObject { ["text"] = "x" }, "clipboard.read.text"), Is.EqualTo("clipboard"));
            Assert.That(NativeTurnLoop.SourceOf(new JsonObject { ["readFrom"] = "Outlook" }, "email.latest.read"), Is.EqualTo("Outlook"));
            Assert.That(NativeTurnLoop.SourceOf(new JsonObject { ["source"] = "web" }, "web.search"), Is.Null);
        });
    }

    // Banco de uso 05-11 (S07): what a privacy-sensitive read holds does not come with a first call the person's words do not
    // ask for; the rest of the receipt does. Controls: a read of another risk, and one with no «text» (a mail's «body» is what
    // encargo 65 reads on).
    [TestCase("clipboard.read.text", "text", true)]
    [TestCase("system.time", "text", false)]
    [TestCase("clipboard.read.text", "body", false)]
    public void AnUnaskedReadGivesNoTextWithItsFirstCall(string operation, string key, bool withheld)
    {
        var facts = new JsonObject
        {
            ["next"] = "input_visible_controls reads them",
            ["observed"] = new JsonObject { [key] = "contenido", ["secretLike"] = "x", ["characterCount"] = 9, ["readFrom"] = "clipboard" },
        };

        NativeTurnLoop.WithholdUnaskedText(facts, operation);

        Assert.Multiple(() =>
        {
            Assert.That(facts["observed"]?[key] is null, Is.EqualTo(withheld));
            Assert.That(facts["observed"]?["secretLike"] is null, Is.EqualTo(withheld));
            Assert.That(facts["observed"]?["characterCount"]?.GetValue<int>(), Is.EqualTo(9));
            Assert.That((string?)facts["next"], withheld
                ? Does.StartWith("input_visible_controls reads them").And.EndWith("call it again")
                : Is.EqualTo("input_visible_controls reads them"));
        });
    }

    // Banco de uso 05-11 (U06): «abre YouTube y búscame…» failed in BAXY's own browser, a tab of the person's Opera had
    // YouTube in its title, and the next led with the call to that window: the model went there and pressed two links in
    // their browser, with their accounts. Nobody had asked for it. A call that acts, failed, says what is there and leaves
    // the asking to the model; a read keeps its way to the tab (encargo 65), and so does a person who said the browser.
    [TestCase("media.play.youtube", "abre YouTube y búscame un video de pan", true, TestName = "an act, the site named: asks first")]
    [TestCase("clipboard.read.text", "qué tengo en YouTube", false, TestName = "a read: the way to the tab stays")]
    [TestCase("media.play.youtube", "en mi Opera abre YouTube y búscame un video de pan", false, TestName = "an act, the browser named: the way stays")]
    public async Task AFailedActOffABrowsersTabLeavesTheAskingToTheModel(string operation, string words, bool asksFirst)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = operation,
                    ["arguments"] = operation == "media.play.youtube" ? new JsonObject { ["query"] = "pan" } : new JsonObject(),
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Cuál?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            Windows = static () => [("Bandeja compartida - Opera", "opera"), ("Notas de cocina", "notas")],
            Rows = static (_, tab) =>
            [
                .. new VisibleRow[]
                {
                    new("Bandeja compartida - Opera", "opera", "Bandeja compartida", Tab: true, Shown: true),
                    new("Bandeja compartida - Opera", "opera", "Mis videos - YouTube", Tab: true),
                }.Where(row => tab(row.Name)),
            ],
        });

        await loop.RunAsync(words, Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue").Single()["observation"]!);
        string? next = (string?)observed?["next"];
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["status"], Is.EqualTo("failed"));
            Assert.That(next, asksFirst
                ? Does.StartWith("this call failed").And.Contain("«Mis videos - YouTube»")
                    .And.Contain("ask").And.Contain("input_visible_controls {\"application\":\"opera\"}")
                : Does.StartWith("input_visible_controls {\"application\":\"opera\"}"));
            Assert.That(observed?["namedWindows"], Is.Not.Null);
        });
    }

    // Encargo 65 (cosecha F2, uso real 03-11): a request for the newest mail of one sender in a webmail open in a tab of
    // the person's browser ran email.latest.read, completed with Outlook's newest mail, and the model said there was no
    // mail from that sender. The turn's first call, completed, whose result names the application it read (readFrom),
    // carries the tab the person's words name and the call that reaches it; a later call, or a source shown by the
    // window named, carries nothing; another receipt's «source» (a search's kind) is not weighed. (assistant.status
    // stands in for any read here: the App reads it itself.)
    [TestCase("Outlook", true)]
    [TestCase("Opera", false)]
    public async Task ACompletedReadOfAnotherApplicationCarriesTheTabThePersonNamed(string source, bool carried)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "assistant.status",
                    ["arguments"] = new JsonObject { ["scope"] = "model" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Cuál?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            Windows = static () => [("Runpod Billing - Opera", "opera"), ("Notas de cocina", "notas")],
            Rows = static (_, tab) =>
            [
                .. new VisibleRow[]
                {
                    new("Runpod Billing - Opera", "opera", "Runpod Billing", Tab: true, Shown: true),
                    new("Runpod Billing - Opera", "opera", "Recibidos (3) - ana@ejemplo.test - Gmail", Tab: true),
                }.Where(row => tab(row.Name)),
            ],
            OwnReading = (_, _) => Task.FromResult(Baxy.Kernel.Operations.OperationOutcome.Success(System.Text.Json.JsonDocument.Parse(
                "{\"sender\":\"avisos@ejemplo.test\",\"source\":\"web\",\"readFrom\":\"" + source + "\"}")
                .RootElement.Clone())),
        });

        await loop.RunAsync("abre en el Gmail lo último que me mandó Codeberg", Stopwatch.GetTimestamp(),
            CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue").Single()["observation"]!);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["status"], Is.EqualTo("completed"));
            Assert.That((string?)observed?["observed"]?["sender"], Is.EqualTo("avisos@ejemplo.test"));
            if (carried)
            {
                Assert.That(observed?["namedWindows"]?.ToJsonString(), Is.EqualTo(
                    "[{\"title\":\"Runpod Billing - Opera\",\"process\":\"opera\",\"tabs\":[{\"title\":\"Recibidos (3) - "
                    + "ana@ejemplo.test - Gmail\",\"shown\":false}]}]"));
                Assert.That((string?)observed?["next"], Does.StartWith("input_visible_controls {\"application\":\"opera\"} "
                    + "(its tab «Recibidos (3) - ana@ejemplo.test - Gmail», not the one shown: input_visible_click on it "
                    + "in what it shows) reads").And.EndWith("this result is of Outlook alone, not of them"));
            }
            else
            {
                Assert.That(observed?["namedWindows"], Is.Null);
                Assert.That(observed?["next"], Is.Null);
            }
        });
    }

    // A failure that says where it looked needs no window to go and look at (file.open of a missing file, with a window
    // titled as the folder named). A failure that does not say it still gets the named window's next (S07).
    [TestCase("""{"status":"failed","error":"file_not_found","observed":{"name":"x.txt","searchedFolders":["desktop"]}}""", true)]
    [TestCase("""{"status":"failed","error":"known_file_not_found","observed":{"searchedFolders":[],"walked":false}}""", true)]
    [TestCase("""{"status":"failed","error":"clipboard_empty","observed":{"version":1}}""", false)]
    [TestCase("""{"status":"failed","error":"clipboard_empty"}""", false)]
    public void AFailureSaysWhereItLookedOnlyWithItsFolders(string observation, bool says)
    {
        Assert.That(NativeTurnLoop.SaysWhereItLooked(JsonNode.Parse(observation)!.AsObject()), Is.EqualTo(says));
    }

    // Auditoría de la App (2026-10-23): the owner's switches are read again when the call is approved; one switched off
    // while it waited does not run it, by the button as by voice.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AnApprovalAfterTheOwnerSwitchedTheCallOffDoesNotRunIt(bool button)
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var steps = new List<NativeTurnStep>();
        var outcomes = new List<string>();
        string? switchedOff = null;
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            ConfirmationResolved = outcomes.Add,
            Refuse = (operation, _) => operation == "web.fetch" ? switchedOff : null,
        });
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(loop.HasPendingConfirmation, Is.True);

        switchedOff = "web_disabled_by_owner";
        var approval = new JsonObject
        {
            ["type"] = "turn.result",
            ["kind"] = "action",
            ["operation"] = "confirmation.answer",
            ["arguments"] = new JsonObject { ["answer"] = "yes" },
        };
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                [button ? "turn.confirm" : "turn.decide"] = approval,
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "La búsqueda web está apagada.",
                },
            },
        });
        if (button)
        {
            await loop.AnswerConfirmationAsync(true, "Sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        }
        else
        {
            await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        }

        NativeTurnStep last = steps[^1];
        Assert.Multiple(() =>
        {
            Assert.That((last.Operation, last.Status, last.Sent), Is.EqualTo(("web.fetch", "rejected", false)));
            Assert.That((string?)JsonNode.Parse(last.Observation)?["error"], Is.EqualTo("web_disabled_by_owner"));
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
        });
    }

    // Uso real 2026-11-02: the step of a call the person said «sí» to says it was asked (the view's Bypass line read
    // the mode only, and called a confirmed send «sin preguntar»); the model's own call is not.
    [TestCase(true)]
    [TestCase(false)]
    public async Task TheStepOfAnApprovedCallSaysItWasAsked(bool button)
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(steps.Single().Asked, Is.False, "held, not run");

        var approval = new JsonObject
        {
            ["type"] = "turn.result",
            ["kind"] = "action",
            ["operation"] = "confirmation.answer",
            ["arguments"] = new JsonObject { ["answer"] = "yes" },
        };
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                [button ? "turn.confirm" : "turn.decide"] = approval,
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "No sé si se abrió.",
                },
            },
        });
        if (button)
            await loop.AnswerConfirmationAsync(true, "Sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        else
            await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        NativeTurnStep ran = steps.Last(step => step.Operation == "web.fetch");
        Assert.Multiple(() =>
        {
            Assert.That((ran.Sent, ran.Asked), Is.EqualTo((true, true)));
            Assert.That((string?)JsonNode.Parse(ran.Observation)?["error"], Is.EqualTo("engine_no_answer"));
        });
    }

    // SIS3 (F1 of REV10; SIS2: «puede ser», «I guess?», «sí, pero mañana» turned brakes on in 10 of 40, because TPV2 took
    // the model making the waiting call again as their yes): whether the person's words are their yes is the mind's to
    // read (Mind._their_answer), and it answers with confirm_pending. The waiting call made again after they spoke is a
    // new call: the waiting one is dropped and the new one is held again for its own «sí», in every mode.
    [TestCase("diario", true)]
    [TestCase("diario", false)]
    [TestCase("avanzado", false)]
    public async Task TheWaitingCallMadeAgainAfterThePersonSpokeIsNotTheirYesAndWaitsAgain(string profile, bool bypass)
    {
        using var fake = new FakeMind();
        fake.Script(SetsProfile("diario", "Tu perfil no tiene memoria. ¿Paso al perfil Diario?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = BrakeLoop(mind, core, steps, outcomes);
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            bypass ? Baxy.Kernel.Policy.ConfirmationMode.Bypass : Baxy.Kernel.Policy.ConfirmationMode.Normal);
        await loop.RunAsync("Recuerda que mi gata se llama Mora", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That((steps.Single().Status, loop.HasPendingConfirmation), Is.EqualTo(("needs_confirmation", true)));

        fake.Script(SetsProfile(profile, "¿Paso al perfil Diario?"));
        await loop.RunAsync("puede ser", Stopwatch.GetTimestamp(), CancellationToken.None);

        NativeTurnStep last = steps[^1];
        Assert.Multiple(() =>
        {
            Assert.That(last.Operation, Is.EqualTo(OwnBrakes.Operation));
            Assert.That((last.Sent, last.Asked), Is.EqualTo((false, false)));
            Assert.That(last.Status, Is.EqualTo("needs_confirmation"));
            Assert.That(outcomes, Has.None.EqualTo("approved"));
            Assert.That(outcomes.FirstOrDefault(), Is.EqualTo("dropped"));
        });
    }

    // SIS3: the mind's confirm_pending yes, given when it read their words as a yes, runs the call that waits.
    [TestCase(true)]
    [TestCase(false)]
    public async Task TheMindsYesToTheWaitingBrakeRunsIt(bool bypass)
    {
        using var fake = new FakeMind();
        fake.Script(SetsProfile("diario", "Tu perfil no tiene memoria. ¿Paso al perfil Diario?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = BrakeLoop(mind, core, steps, outcomes);
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            bypass ? Baxy.Kernel.Policy.ConfirmationMode.Bypass : Baxy.Kernel.Policy.ConfirmationMode.Normal);
        await loop.RunAsync("Recuerda que mi gata se llama Mora", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonObject yes = CallsThenReplies(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = "yes" }, "Listo.");
        yes["reply"]!["turn.decide"]!["theirYes"] = true;
        fake.Script(yes);
        await loop.RunAsync("dale nomás", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcomes.FirstOrDefault(), Is.EqualTo("approved"));
            Assert.That(loop.HasPendingConfirmation, Is.False);
        });
    }

    // TPV2: the same call made again before the person said anything is not their yes: in the turn that held it the
    // question is not published yet (ConfirmationAsk.Unpublished) and the turn goes final at the hold; a turn that ends
    // without asking it drops it (DropUnasked).
    [Test]
    public async Task TheWaitingCallMadeAgainBeforeThePersonSpokeDoesNotRun()
    {
        using var fake = new FakeMind();
        JsonObject call = SetsProfile("diario", string.Empty);
        call["reply"]!["turn.continue"] = call["reply"]!["turn.decide"]!.DeepClone();
        fake.Script(call);
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        NativeTurnLoop loop = BrakeLoop(mind, core, steps, []);
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Bypass);

        await loop.RunAsync("Recuerda que mi gata se llama Mora", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.That(steps.Select(static step => step.Sent), Has.None.True);
        Assert.That(loop.HasPendingConfirmation, Is.False);
    }

    // TPV3 (dueño 10-11: «La memoria está apagada. ¿La activo?» → «sí» → asked again; TPV2: the 4B offers the memory
    // in words, 0 of 18): a memory call refused as off offers memory_enable; the turn ended with BAXY's question; after
    // the person's words the model makes exactly that call: the kernel's challenge for it is answered with their «sí»
    // (its token), with no second question. Controls: a turn that did not end asking, and the offer one turn later leave it
    // held as before.
    // SIS3: only with the mind's reading of their words as a yes to it (theirYes, Mind._their_answer): the model
    // making the call is not their yes by itself.
    [TestCase("La memoria está apagada. ¿La activo?", 1, true, true)]
    [TestCase("La memoria está apagada. ¿La activo?", 1, false, false)]
    [TestCase("La memoria está apagada.", 1, true, false)]
    [TestCase("La memoria está apagada. ¿La activo?", 2, true, false)]
    public async Task TheCallTheEarlierResultOfferedMadeAfterThePersonSpokeIsTheirYes(
        string asked, int turnsLater, bool theirYes, bool runs)
    {
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("memory.list", new JsonObject { ["limit"] = 20, ["offset"] = 0, ["version"] = 1 },
            asked));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<(string Operation, string? Token)>();
        const string Token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
        core.AnswersForTests = (prepared, token) =>
        {
            sent.Add((prepared.OperationName, token));
            if (prepared.OperationName != "memory.enable")
            {
                return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
                    prepared.MissionId, prepared.InvocationId, OperationStatuses.Failed,
                    "{\"status\":\"failed\",\"error\":\"memory_disabled\"}", false, false, null, "memory_disabled");
            }

            return token is null
                ? new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Pending, "{\"status\":\"pending\"}", false, false,
                    JsonDocument.Parse("{\"version\":" + ConfirmationChallengeContract.CurrentVersion + ",\"token\":\""
                        + Token + "\",\"expiresAtUtc\":\"" + DateTimeOffset.UtcNow.AddMinutes(2).ToString("O",
                            System.Globalization.CultureInfo.InvariantCulture)
                        + "\",\"reconciliationRequired\":false}").RootElement.Clone(),
                    ConfirmationChallengeContract.RequiredErrorCode)
                : new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false,
                    null, null);
        };
        var steps = new List<NativeTurnStep>();
        var cards = new List<NativeTurnConfirmation>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            ConfirmationAsked = cards.Add,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("¿Qué recuerdas de mí?", Stopwatch.GetTimestamp(), CancellationToken.None);
        for (int turn = 1; turn < turnsLater; turn++)
        {
            fake.Script(Says("Dime."));
            await loop.RunAsync("eh...", Stopwatch.GetTimestamp(), CancellationToken.None);
        }

        JsonObject enabling = CallsThenReplies("memory.enable", new JsonObject { ["enabled"] = true, ["version"] = 1 },
            "Listo.");
        enabling["reply"]!["turn.decide"]!["theirYes"] = theirYes;
        fake.Script(enabling);
        await loop.RunAsync("sí, dale", Stopwatch.GetTimestamp(), CancellationToken.None);

        NativeTurnStep enable = steps.Last(step => step.Operation == "memory.enable");
        Assert.Multiple(() =>
        {
            Assert.That(sent.Where(static call => call.Operation == "memory.enable").Select(static call => call.Token),
                runs ? Is.EqualTo(new[] { null, Token }) : Is.EqualTo(new string?[] { null }));
            Assert.That((enable.Sent, enable.Asked), Is.EqualTo(runs ? (true, true) : (false, false)));
            Assert.That(enable.Status, runs ? Is.EqualTo(OperationStatuses.Completed) : Is.EqualTo(OperationStatuses.Pending));
            Assert.That(loop.HasPendingConfirmation, Is.EqualTo(!runs));
        });
    }

    // TPV6 (VIVO11, Esencial, 1.4.0: «Crea una nota que diga hola» → note_create off in the profile → «Ajustes →
    // Herramientas» once, a false reason the next, a switch to Diario after three «sí» and «Nota creada» with no note):
    // the call off in the profile waits for the person's «sí» as BAXY's offer to turn on that one tool, in every mode;
    // their «sí» (confirm_pending; SIS3: the same call again is not their yes, it waits again) keeps it on alone and says
    // the request was not done; their «no» leaves the profile as it was. Nothing of the call reaches the engine either way.
    [TestCase("yes", false, true)]
    [TestCase("no", false, false)]
    public async Task AToolOffInTheProfileTurnsOnAloneWithTheirYes(string answer, bool bypass, bool on)
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-tpv6-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("note.create", [], "Las notas están apagadas en tu perfil. ¿Las enciendo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            sent.Add(prepared.OperationName);
            return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null);
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            bypass ? Baxy.Kernel.Policy.ConfirmationMode.Bypass : Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Crea una nota que diga hola", Stopwatch.GetTimestamp(), CancellationToken.None);
        NativeTurnStep offer = steps.Single();
        fake.Script(CallsThenReplies(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = answer }, "Listo."));
        await loop.RunAsync(answer == "no" ? "no, déjalo" : "sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        string result = steps.Last().Observation;
        Assert.Multiple(() =>
        {
            Assert.That(offer.Status, Is.EqualTo("needs_confirmation"));
            Assert.That(offer.Observation, Does.Not.Contain("turnOn").And.Not.Contain("Ajustes"));
            Assert.That(sent, Is.Empty);
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That(profile.Refusal("note.create"), on ? Is.Null : Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Profile, Is.EqualTo(on ? ToolProfile.Personalizado : "esencial"));
            // Nothing else: another tool of Diario stays off.
            Assert.That(profile.Refusal("bluetooth.device.list"), Is.EqualTo(ToolProfile.OffCode));
            // The call did not run, and its result says so: never «completed» (banco TPV6: «La nota se creó»).
            Assert.That(result, on
                ? Does.Contain("\"status\":\"rejected\"").And.Contain(NativeTurnLoop.NotRunToolOn)
                    .And.Not.Contain("completed")
                : Does.Contain("declined_by_person"));
        });
    }

    // ESE6 (GUA3/ESE5 lote A, Esencial with the memory off as it is born: «Recuerda que mi perro se llama Chispo.» → «sí»
    // saved nothing in 18 of 18; ESE5's stub turned the memory's tools on in the profile and left its own switch off, so
    // the save came back memory_disabled and the 4B said «ya tengo la memoria encendida»). A memory.save off in the
    // profile is held with its arguments, sealed as any memory call's, and nothing reaches the engine; the person's «sí»
    // is one step of the App: the memory's tools on in the profile (alone), the memory itself on (memory.enable, with that
    // «sí» as the kernel's confirmation) and that very save sent, whose own receipt is what the model reads, beside what
    // was turned on. Their «no» changes nothing and sends nothing.
    [TestCase("yes")]
    [TestCase("no")]
    public async Task AMemorySaveOffInTheProfileIsSavedInOneStepWithTheirYes(string answer)
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-ese6-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("memory.save", new JsonObject
        {
            ["kind"] = "fact", ["retention"] = "persistent", ["selector"] = "nombre del perro", ["sensitivity"] = "normal",
            ["tags"] = new JsonArray(), ["value"] = "Chispo", ["version"] = 1,
        }, "La memoria está apagada. ¿La enciendo para guardarlo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<(string Operation, string? Token)>();
        const string Token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
        bool memoryOn = false;
        core.AnswersForTests = (prepared, token) =>
        {
            sent.Add((prepared.OperationName, token));
            if (prepared.OperationName == "memory.enable" && token is null)
            {
                return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Pending, "{\"status\":\"pending\"}", false, false,
                    JsonDocument.Parse("{\"version\":" + ConfirmationChallengeContract.CurrentVersion + ",\"token\":\""
                        + Token + "\",\"expiresAtUtc\":\"" + DateTimeOffset.UtcNow.AddMinutes(2).ToString("O",
                            System.Globalization.CultureInfo.InvariantCulture)
                        + "\",\"reconciliationRequired\":false}").RootElement.Clone(),
                    ConfirmationChallengeContract.RequiredErrorCode);
            }

            memoryOn |= prepared.OperationName == "memory.enable";
            return memoryOn
                ? new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null)
                : new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Failed, "{\"status\":\"failed\",\"error\":\"memory_disabled\"}",
                    false, false, null, "memory_disabled");
        };
        var steps = new List<NativeTurnStep>();
        int memoryChanged = 0;
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
            MemoryChanged = () => memoryChanged++,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Recuerda que mi perro se llama Chispo.", Stopwatch.GetTimestamp(), CancellationToken.None);
        NativeTurnStep offer = steps.Single();
        bool heldNothingSent = sent.Count == 0;
        fake.Script(CallsThenReplies(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = answer }, "Listo."));
        await loop.RunAsync(answer == "no" ? "no, déjalo" : "sí, dale", Stopwatch.GetTimestamp(), CancellationToken.None);

        bool yes = answer == "yes";
        IReadOnlyList<JsonObject> continued = fake.Requests("turn.continue");
        // What the model reads of their answer: the save's own receipt, beside what was turned on.
        JsonObject result = JsonNode.Parse((string)continued[^1]["observation"]!)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(offer.Status, Is.EqualTo("needs_confirmation"));
            Assert.That(heldNothingSent, Is.True, "held: nothing reaches the engine before their yes");
            // The offer is the memory and the save, said by the receipt: no profile, no Settings, no other call.
            Assert.That(offer.Observation, Does.Contain(NativeTurnLoop.MemoryOffHeldCause).And.Not.Contain("Ajustes")
                .And.Not.Contain("Settings →").And.Not.Contain("tool_profile").And.Not.Contain("Diario")
                .And.Not.Contain("Chispo"), "a memory call's values stay sealed");
            Assert.That(sent, yes
                ? Is.EqualTo(new (string, string?)[] { ("memory.enable", null), ("memory.enable", Token), ("memory.save", null) })
                : Is.Empty);
            Assert.That(profile.Refusal("memory.save"), yes ? Is.Null : Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Profile, Is.EqualTo(yes ? ToolProfile.Personalizado : "esencial"));
            Assert.That(profile.Refusal("note.create"), Is.EqualTo(ToolProfile.OffCode), "nothing else is turned on");
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That((string?)result["status"], Is.EqualTo(yes ? OperationStatuses.Completed : "cancelled"));
            Assert.That((string?)result["operation"], Is.EqualTo("memory.save"));
            Assert.That(result.ContainsKey("turnedOn"), Is.EqualTo(yes));
            // ESE7: the receipt of the save that turned the memory on says what to tell, both things (1 of 15 without).
            Assert.That((string?)result["next"], yes ? Is.EqualTo(NativeTurnLoop.MemoryOnNext) : Is.Null);
            Assert.That(memoryChanged, yes ? Is.GreaterThan(0) : Is.Zero);
            // The save ran: the mind is not handed a tool to call again (TPV7's toolOn), and nothing says «not run».
            Assert.That(continued.Any(static request => request.ContainsKey("toolOn")), Is.False);
            Assert.That(steps.Last().Observation, Does.Not.Contain(NativeTurnLoop.NotRunToolOn));
        });
    }

    // ESE6: if the memory itself does not turn on (the engine refuses memory.enable), the held save is not sent, and the
    // receipt says the save failed and why, with the tools that did turn on: never «completed».
    [Test]
    public async Task AMemorySaveHeldOffIsNotSentWhenTheMemoryDoesNotTurnOn()
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-ese6-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("memory.save", new JsonObject
        {
            ["kind"] = "fact", ["retention"] = "persistent", ["selector"] = "talla", ["sensitivity"] = "normal",
            ["tags"] = new JsonArray(), ["value"] = "42", ["version"] = 1,
        }, "¿Enciendo la memoria para guardarlo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            sent.Add(prepared.OperationName);
            return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                prepared.InvocationId, OperationStatuses.Failed, "{\"status\":\"failed\",\"error\":\"memory_store_unavailable\"}",
                false, false, null, "memory_store_unavailable");
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Recuerda que calzo 42.", Stopwatch.GetTimestamp(), CancellationToken.None);
        fake.Script(CallsThenReplies(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = "yes" }, "No pude."));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonObject result = JsonNode.Parse(steps.Last().Observation)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.EqualTo(new[] { "memory.enable" }));
            Assert.That((string?)result["status"], Is.EqualTo(OperationStatuses.Failed));
            Assert.That((string?)result["error"], Is.EqualTo(NativeTurnLoop.MemoryNotTurnedOn));
            Assert.That((string?)result["operation"], Is.EqualTo("memory.save"));
            Assert.That(steps.Last().Observation, Does.Not.Contain("completed"));
        });
    }

    // ESE7 (ESE6 §7, Esencial, «Baxi, activa la memoria.» with nothing to save, 2 of 2: the only memory call shown was the
    // save, and the memory was turned on with a filler record nobody asked for). The memory's switch off in the profile is
    // held as the save is, and the person's «sí» turns on the memory's tools (alone) and the memory itself with that very
    // call, once: no save is sent, and the receipt the model reads is the switch's own beside what was turned on.
    [TestCase("yes")]
    [TestCase("no")]
    public async Task TheMemorySwitchOffInTheProfileTurnsTheMemoryOnWithTheirYesAndSavesNothing(string answer)
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-ese7-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("memory.enable", new JsonObject { ["enabled"] = true, ["version"] = 1 },
            "La memoria está apagada. ¿La enciendo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<(string Operation, string? Token)>();
        const string Token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
        core.AnswersForTests = (prepared, token) =>
        {
            sent.Add((prepared.OperationName, token));
            return token is null
                ? new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Pending, "{\"status\":\"pending\"}", false, false,
                    JsonDocument.Parse("{\"version\":" + ConfirmationChallengeContract.CurrentVersion + ",\"token\":\""
                        + Token + "\",\"expiresAtUtc\":\"" + DateTimeOffset.UtcNow.AddMinutes(2).ToString("O",
                            System.Globalization.CultureInfo.InvariantCulture)
                        + "\",\"reconciliationRequired\":false}").RootElement.Clone(),
                    ConfirmationChallengeContract.RequiredErrorCode)
                : new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null,
                    null);
        };
        var steps = new List<NativeTurnStep>();
        int memoryChanged = 0;
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
            MemoryChanged = () => memoryChanged++,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Baxi, activa la memoria.", Stopwatch.GetTimestamp(), CancellationToken.None);
        NativeTurnStep offer = steps.Single();
        bool heldNothingSent = sent.Count == 0;
        fake.Script(CallsThenReplies(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = answer }, "Listo."));
        await loop.RunAsync(answer == "no" ? "no, déjalo" : "sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        bool yes = answer == "yes";
        IReadOnlyList<JsonObject> continued = fake.Requests("turn.continue");
        JsonObject result = JsonNode.Parse((string)continued[^1]["observation"]!)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(offer.Status, Is.EqualTo("needs_confirmation"));
            Assert.That(heldNothingSent, Is.True, "held: nothing reaches the engine before their yes");
            // The offer is the memory alone, said by the receipt: nothing of a save, no profile, no Settings.
            Assert.That(offer.Observation, Does.Contain(NativeTurnLoop.MemoryOffHeldCause).And.Contain("nothing is saved")
                .And.Not.Contain("would save").And.Not.Contain("Ajustes").And.Not.Contain("Settings →")
                .And.Not.Contain("tool_profile").And.Not.Contain("Diario"));
            // The switch, once (asked, and answered with their «sí» as its confirmation), and no save at all.
            Assert.That(sent, yes
                ? Is.EqualTo(new (string, string?)[] { ("memory.enable", null), ("memory.enable", Token) })
                : Is.Empty);
            Assert.That(profile.Refusal("memory.save"), yes ? Is.Null : Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Refusal("memory.disable"), yes ? Is.Null : Is.EqualTo(ToolProfile.OffCode));
            Assert.That(profile.Profile, Is.EqualTo(yes ? ToolProfile.Personalizado : "esencial"));
            Assert.That(profile.Refusal("note.create"), Is.EqualTo(ToolProfile.OffCode), "nothing else is turned on");
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That((string?)result["status"], Is.EqualTo(yes ? OperationStatuses.Completed : "cancelled"));
            Assert.That((string?)result["operation"], Is.EqualTo("memory.enable"));
            Assert.That(result.ContainsKey("turnedOn"), Is.EqualTo(yes));
            Assert.That(result.ContainsKey("next"), Is.False, "the switch's own receipt is the news: no save to tell");
            Assert.That(memoryChanged, yes ? Is.GreaterThan(0) : Is.Zero);
            Assert.That(continued.Any(static request => request.ContainsKey("toolOn")), Is.False);
            Assert.That(steps.Last().Observation, Does.Not.Contain(NativeTurnLoop.NotRunToolOn));
        });
    }

    // MEM3 (VIVO15 fila 3, Completo with the memory's own switch off: «Recuerda que mi perro se llama Chispo.» → «¡Genial,
    // ahora sé que tu perro se llama Chispo!» 5 of 5, nothing called nor offered). With the switch off, the memory call
    // shown with its arguments is held in Completo too, as out of Esencial: nothing reaches the engine, and the person's
    // «sí» turns the memory on and runs that very save, the profile left as it is (nothing to keep on in Completo). The
    // switch, told by the turn (MemorySwitched), brings the tool back. Their «no» changes nothing and sends nothing.
    [TestCase("yes")]
    [TestCase("no")]
    public async Task AMemorySaveWithTheMemorySwitchedOffIsHeldInCompletoAndSavedWithTheirYes(string answer)
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-mem3-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root) { MemoryOff = true };
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("memory.save", new JsonObject
        {
            ["kind"] = "fact", ["retention"] = "persistent", ["selector"] = "nombre del perro", ["sensitivity"] = "normal",
            ["tags"] = new JsonArray(), ["value"] = "Chispo", ["version"] = 1,
        }, "¿Enciendo la memoria para guardar que tu perro se llama Chispo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<(string Operation, string? Token)>();
        const string Token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
        bool memoryOn = false;
        core.AnswersForTests = (prepared, token) =>
        {
            sent.Add((prepared.OperationName, token));
            if (prepared.OperationName == "memory.enable" && token is null)
            {
                return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Pending, "{\"status\":\"pending\"}", false, false,
                    JsonDocument.Parse("{\"version\":" + ConfirmationChallengeContract.CurrentVersion + ",\"token\":\""
                        + Token + "\",\"expiresAtUtc\":\"" + DateTimeOffset.UtcNow.AddMinutes(2).ToString("O",
                            System.Globalization.CultureInfo.InvariantCulture)
                        + "\",\"reconciliationRequired\":false}").RootElement.Clone(),
                    ConfirmationChallengeContract.RequiredErrorCode);
            }

            memoryOn |= prepared.OperationName == "memory.enable";
            return memoryOn
                ? new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null)
                : new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Failed, "{\"status\":\"failed\",\"error\":\"memory_disabled\"}",
                    false, false, null, "memory_disabled");
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
            MemorySwitched = on => profile.MemoryOff = !on,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);
        bool withheldOff = profile.Withheld(["memory.save", "memory.recall"]).SetEquals(["memory.save"]);

        await loop.RunAsync("Recuerda que mi perro se llama Chispo.", Stopwatch.GetTimestamp(), CancellationToken.None);
        NativeTurnStep offer = steps.Single();
        bool heldNothingSent = sent.Count == 0;
        fake.Script(CallsThenReplies(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = answer }, "Listo."));
        await loop.RunAsync(answer == "no" ? "no, déjalo" : "sí, dale", Stopwatch.GetTimestamp(), CancellationToken.None);

        bool yes = answer == "yes";
        JsonObject result = JsonNode.Parse((string)fake.Requests("turn.continue")[^1]["observation"]!)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(withheldOff, Is.True, "switched off, the memory's held call is withheld in Completo, alone");
            Assert.That(offer.Status, Is.EqualTo("needs_confirmation"));
            Assert.That(heldNothingSent, Is.True, "held: nothing reaches the engine before their yes");
            Assert.That(offer.Observation, Does.Contain(NativeTurnLoop.MemoryOffHeldCause).And.Not.Contain("Settings →")
                .And.Not.Contain("tool_profile").And.Not.Contain("Chispo"), "a memory call's values stay sealed");
            Assert.That(sent, yes
                ? Is.EqualTo(new (string, string?)[] { ("memory.enable", null), ("memory.enable", Token), ("memory.save", null) })
                : Is.Empty);
            Assert.That(profile.Profile, Is.EqualTo(ToolProfile.Completo), "nothing to keep on in Completo");
            Assert.That(profile.MemoryOff, Is.EqualTo(!yes));
            Assert.That(profile.Refusal("memory.save"), yes ? Is.Null : Is.EqualTo(ToolProfile.OffCode));
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That((string?)result["status"], Is.EqualTo(yes ? OperationStatuses.Completed : "cancelled"));
            Assert.That((string?)result["operation"], Is.EqualTo("memory.save"));
            Assert.That(result.ContainsKey("turnedOn"), Is.EqualTo(yes));
        });
    }

    // REM7 (REV15 D-3, REV14 B-E3): with their «sí» the profile was changed (ToolOn) before the engine was looked at and
    // before memory.enable, so an engine that failed left the memory's tools on in Personalizado and the memory off, and
    // the switch's own failure was given as it came, without saying so. The memory is turned on first; the profile
    // changes only once it is on, and the receipt says nothing changed.
    [TestCase("memory.save")]
    [TestCase("memory.enable")]
    public async Task AMemoryThatDoesNotTurnOnLeavesTheProfileAsItWasAndSaysSo(string operation)
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-rem7-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root) { MemoryOff = true };
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies(operation, operation == "memory.enable"
            ? new JsonObject { ["enabled"] = true, ["version"] = 1 }
            : new JsonObject
            {
                ["kind"] = "fact", ["retention"] = "persistent", ["selector"] = "talla", ["sensitivity"] = "normal",
                ["tags"] = new JsonArray(), ["value"] = "42", ["version"] = 1,
            }, "¿Enciendo la memoria?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            sent.Add(prepared.OperationName);
            return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                prepared.InvocationId, OperationStatuses.Failed, "{\"status\":\"failed\",\"error\":\"memory_store_unavailable\"}",
                false, false, null, "memory_store_unavailable");
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
            MemoryOff = () => profile.MemoryOff,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Baxi, guárdalo.", Stopwatch.GetTimestamp(), CancellationToken.None);
        fake.Script(CallsThenReplies(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = "yes" }, "No pude."));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonObject result = JsonNode.Parse(steps.Last().Observation)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.EqualTo(new[] { "memory.enable" }));
            Assert.That(profile.Profile, Is.EqualTo("esencial"), "nothing left at half: the profile as it was");
            Assert.That(profile.Refusal("memory.recall"), Is.EqualTo(ToolProfile.OffCode));
            Assert.That((string?)result["status"], Is.EqualTo(OperationStatuses.Failed));
            Assert.That((string?)result["error"], Is.EqualTo(NativeTurnLoop.MemoryNotTurnedOn));
            Assert.That((string?)result["operation"], Is.EqualTo(operation));
            Assert.That((string?)result["next"], Does.Contain("nothing changed"));
            Assert.That(loop.HasPendingConfirmation, Is.False);
        });
    }

    // REM7 (REV15 D-2, D-4): the card of a held memory call had no arguments (sealed: PrivateArguments is {}) and the
    // profile's cause («con tu sí se enciende sólo esta»). It carries the datum the «sí» saves, opened from the sealed call
    // for the person's own card only (a secret: only what it is), and the memory's own cause.
    [TestCase("memory.save", "nombre del perro: Chispo")]
    // INT33J: the case of memory.sensitive.save left (its held channel, 610be96d3, was reverted by INT33G).
    [TestCase("memory.enable", null)]
    public async Task AHeldMemoryCallsCardCarriesItsDatumAndItsOwnCause(string operation, string? datum)
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-rem7-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root) { MemoryOff = true };
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies(operation, operation switch
        {
            "memory.enable" => new JsonObject { ["enabled"] = true, ["version"] = 1 },
            "memory.save" => new JsonObject
            {
                ["kind"] = "fact", ["retention"] = "persistent", ["selector"] = "nombre del perro",
                ["sensitivity"] = "normal", ["tags"] = new JsonArray(), ["value"] = "Chispo", ["version"] = 1,
            },
            _ => new JsonObject
            {
                ["kind"] = "fact", ["retention"] = "persistent", ["selector"] = "clave del candado",
                ["sensitivity"] = "secret", ["tags"] = new JsonArray(), ["value"] = "4071", ["version"] = 1,
            },
        }, "¿Enciendo la memoria?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        core.AnswersForTests = (prepared, _) => new OperationResponse(ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"), prepared.MissionId, prepared.InvocationId, OperationStatuses.Completed,
            "{\"status\":\"completed\"}", true, false, null, null);
        var protector = new MemoryOperationProtector(
            new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D"));
        var cards = new List<NativeTurnConfirmation>();
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            // One protector, as the App's: what it sealed, it opens.
            MemoryProtector = () => protector,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
            MemoryOff = () => profile.MemoryOff,
            ConfirmationAsked = cards.Add,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Baxi, guárdalo.", Stopwatch.GetTimestamp(), CancellationToken.None);

        NativeTurnConfirmation card = cards.Single();
        Assert.Multiple(() =>
        {
            Assert.That(card.Shown, Is.EqualTo(datum));
            Assert.That(card.Cause, Is.EqualTo(operation switch
            {
                "memory.enable" => NativeTurnLoop.MemorySwitchHeldCause,
                "memory.save" => NativeTurnLoop.MemoryOffHeldCause,
                _ => NativeTurnLoop.MemorySecretHeldCause,
            }));
            Assert.That(card.Arguments.ToJsonString(), Is.EqualTo("{}"), "the sealed values stay out of the arguments");
            Assert.That(steps.Single().Observation, Does.Not.Contain("4071").And.Not.Contain("Chispo"));
            // REM7 (REV15 D-2, D-5): the question names what the «sí» saves, a secret only by what it is.
            Assert.That(steps.Single().Observation, operation == "memory.enable"
                ? Does.Not.Contain("name what it would save")
                : Does.Contain("name what it would save").And.Contain("never its value"));
        });
    }

    // REM7 (REV15 D-1): the held memory call's receipt said «BAXY's memory is off on this PC» whatever the switch was; in
    // Esencial chosen with the memory on, that is false. It says the switch the App read, or the profile.
    // REM8 (REV16 M-4): its card too said «la memoria está apagada» with the memory on; it says what holds the call, the
    // switch, the profile or both, as the receipt does.
    [TestCase(true, "esencial")]
    [TestCase(false, "esencial")]
    [TestCase(true, "completo")]
    public async Task AHeldMemoryCallSaysTheSwitchAsTheAppReadIt(bool memoryOff, string chosen)
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-rem7-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root) { MemoryOff = memoryOff };
        // Completo is the profile with no file: nothing to apply.
        Assert.That(chosen == "completo" ? null : profile.Apply(new JsonObject { ["profile"] = chosen }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("memory.save", new JsonObject
        {
            ["kind"] = "fact", ["retention"] = "persistent", ["selector"] = "nombre del perro", ["sensitivity"] = "normal",
            ["tags"] = new JsonArray(), ["value"] = "Chispo", ["version"] = 1,
        }, "¿Lo guardo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            sent.Add(prepared.OperationName);
            return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null);
        };
        var steps = new List<NativeTurnStep>();
        var cards = new List<NativeTurnConfirmation>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
            MemoryOff = () => profile.MemoryOff,
            InProfile = profile.InProfile,
            ConfirmationAsked = cards.Add,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Recuerda que mi perro se llama Chispo.", Stopwatch.GetTimestamp(), CancellationToken.None);

        string offer = steps.Single().Observation;
        string said = (string?)FieldStepProjection.Card("k1", "confirm", "memory.save", new JsonObject(),
            OperationRisks.LowReversible, DateTimeOffset.UtcNow.AddMinutes(2), context: null, english: false,
            cause: cards.Single().Cause)["risk"] ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.Empty);
            Assert.That(said, memoryOff ? Does.StartWith("la memoria está apagada") : Does.StartWith("la memoria está encendida"));
            Assert.That(said, chosen == "completo" ? Does.Not.Contain("herramientas") : Does.Contain("herramientas"));
            Assert.That(said, Does.EndWith("se guarda este dato"));
            Assert.That(offer, Does.Contain(NativeTurnLoop.MemoryOffHeldCause));
            Assert.That(offer, memoryOff
                ? Does.Contain("memory is off on this PC")
                : Does.Not.Contain("memory is off").And.Contain("tool profile"));
            Assert.That(offer, Does.Not.Contain("nothing saved").And.Not.Contain("is empty"));
        });
    }

    // ACT1 (banco TPV7/INT31, Esencial, T01 y T09): after «sí» to the offer the 4B switched to Diario «to turn on the
    // memory», the one call the system text spells. The offer's receipt says which tool is off and the call their yes
    // goes in, which turns on that one, and names no other tool nor profile.
    [Test]
    public async Task TheOfferOfAToolOffInTheProfileSpellsTheCallTheirYesGoesIn()
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-act1-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("note.create", [], "Las notas están apagadas en tu perfil. ¿Las enciendo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
        });

        await loop.RunAsync("Apúntame que el lunes pago el gas", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonObject held = JsonNode.Parse(steps.Single().Observation)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(held["status"]?.GetValue<string>(), Is.EqualTo("needs_confirmation"));
            Assert.That(held["tool"]?.GetValue<string>(), Is.EqualTo(profile.OffFacts("note.create")["tool"]?.GetValue<string>()));
            Assert.That(held["onTheirYes"]?.GetValue<string>(), Is.EqualTo("""confirm_pending {"answer": "yes"}"""));
            Assert.That(steps.Single().Observation, Does.Not.Contain("Diario").And.Not.Contain("tool_profile")
                .And.Not.Contain("memory"));
        });
    }

    // REM2 (REV13 A-2): since SIS3 the same call again after their «sí» is not their yes (it is dropped and held again),
    // so the offer's receipt never sends the model that way: it named «the same call again» as where their answer goes,
    // and the model that repeated it turned nothing on (INFORME_SIS3 N009/N018: «enciendo» with nothing on).
    [Test]
    public async Task TheOfferOfAToolOffNeverSendsTheirAnswerToTheSameCallAgain()
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-rem2-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("note.create", [], "Las notas están apagadas en tu perfil. ¿Las enciendo?"));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
        });

        await loop.RunAsync("Crea una nota que diga hola", Stopwatch.GetTimestamp(), CancellationToken.None);
        string next = JsonNode.Parse(steps.Single().Observation)!["next"]!.GetValue<string>();
        fake.Script(CallsThenReplies("note.create", [], "¿Las enciendo?"));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain("confirm_pending").And.Not.Contain("same call"));
            // What the receipt no longer offers: the repeat is held again and turns nothing on.
            Assert.That(profile.Refusal("note.create"), Is.EqualTo(ToolProfile.OffCode));
            Assert.That(steps.Last().Status, Is.EqualTo("needs_confirmation"));
        });
    }

    // TPV7 (VIVO11, 11-11-2026, Esencial: «Crea una nota que diga hola» → «sí» → «Nota creada: "Hola"» with no
    // note.create; banco TPV6: 2 de 9 «hecho» sin efecto): the tool their «sí» turned on was still a stub with no
    // arguments in the mind until its relaunch, so that turn could only say it. With the engine's catalog holding it, the
    // turn's next request hands the mind the whole tool (toolOn), its result says it is callable now and that the request
    // is not done yet, and the call the model then makes with its arguments is the one that runs.
    [Test]
    public async Task TheToolTheirYesTurnedOnIsHandedWholeToTheMindAndItsCallRunsInThatTurn()
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-tpv7-" + Guid.NewGuid().ToString("N"));
        var profile = new ToolProfile(root);
        Assert.That(profile.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);
        using var fake = new FakeMind();
        JsonObject Calls(string operation, JsonObject arguments) => new()
        {
            ["type"] = "turn.result", ["kind"] = "action", ["operation"] = operation, ["arguments"] = arguments,
        };
        JsonObject Says(string reply) => new() { ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = reply };
        fake.Script(new JsonObject
        {
            ["replies"] = new JsonObject
            {
                ["turn.decide"] = new JsonArray(
                    Calls("note.create", []),
                    Calls(MindStep.ConfirmationAnswer, new JsonObject { ["answer"] = "yes" })),
                ["turn.continue"] = new JsonArray(
                    Says("Las notas están apagadas en tu perfil. ¿Las enciendo?"),
                    Calls("note.create", new JsonObject { ["title"] = "hola", ["content"] = "hola" }),
                    Says("Creé la nota «hola».")),
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        using JsonDocument schema = JsonDocument.Parse("""
            {"type":"object","properties":{"title":{"type":"string"},"content":{"type":"string"}},"required":["content"]}
            """);
        typeof(CoreProcessClient).GetField("_capabilities", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(core,
            new[] { new OperationDescriptor("note.create", schema.RootElement.Clone(), OperationRisks.LowReversible,
                "note.create.v1", "Create a note with a title and its content.") });
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            sent.Add(prepared.OperationName + " " + prepared.Arguments.GetRawText());
            return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null);
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            Refuse = (operation, _) => profile.Refusal(operation),
            OffFacts = profile.OffFacts,
            ToolOn = profile.KeepOn,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("Crea una nota que diga hola", Stopwatch.GetTimestamp(), CancellationToken.None);
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        IReadOnlyList<JsonObject> continued = fake.Requests("turn.continue");
        Assert.Multiple(() =>
        {
            Assert.That(continued, Has.Count.EqualTo(3));
            // Only the request that carries their «sí»'s result hands the tool over, whole.
            Assert.That(continued[0]["toolOn"], Is.Null);
            Assert.That((string?)continued[1]["toolOn"]?["name"], Is.EqualTo("note.create"));
            Assert.That(continued[1]["toolOn"]?["argumentsSchema"]?["properties"]?["content"], Is.Not.Null);
            Assert.That((string?)continued[1]["observation"], Does.Contain(NativeTurnLoop.NotRunToolOn)
                .And.Contain("callable now").And.Contain("NOT done yet").And.Not.Contain("completed"));
            Assert.That(continued[2]["toolOn"], Is.Null);
            // The call with its arguments ran, once, and nothing else did.
            Assert.That(sent, Has.Count.EqualTo(1));
            Assert.That(sent.FirstOrDefault(), Does.StartWith("note.create ").And.Contain("\"content\":\"hola\""));
            Assert.That(steps.Last().Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(profile.Refusal("note.create"), Is.Null);
            Assert.That(profile.Refusal("bluetooth.device.list"), Is.EqualTo(ToolProfile.OffCode));
        });
    }

    // TPV5 (TPV4, juez ciego, Sin frenos: «What did I tell you about…?» → memory_save refused off in the profile → the
    // 4B made the memory_enable its result offered in that same turn → it ran and a memory was saved before the «no»): the
    // call BAXY's own result offered (here memory_disabled's, TPV3), made before the person answered, waits for their «sí»
    // in every mode, and it is not sent.
    [TestCase(true)]
    [TestCase(false)]
    public async Task TheCallBaxyOfferedWaitsForTheYesInEveryMode(bool bypass)
    {
        using var fake = new FakeMind();
        JsonObject script = CallsThenSays("memory.list", new JsonObject { ["limit"] = 20, ["offset"] = 0, ["version"] = 1 });
        script["reply"]!["turn.continue"] = new JsonObject
        {
            ["type"] = "turn.result", ["kind"] = "action", ["operation"] = "memory.enable",
            ["arguments"] = new JsonObject { ["enabled"] = true, ["version"] = 1 },
        };
        fake.Script(script);
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            sent.Add(prepared.OperationName);
            return prepared.OperationName == "memory.list"
                ? new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Failed, "{\"status\":\"failed\",\"error\":\"memory_disabled\"}",
                    false, false, null, "memory_disabled")
                : new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                    prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null);
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            bypass ? Baxy.Kernel.Policy.ConfirmationMode.Bypass : Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("What did I tell you about my neighbour's garden?", Stopwatch.GetTimestamp(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.EqualTo(new[] { "memory.list" }));
            Assert.That(steps.Where(static step => step.Operation == "memory.enable").Select(static step => step.Sent),
                Is.Not.Empty.And.All.False);
        });
    }

    // TPV5 (TPV4 K02, Sin frenos: «sale, va», a «sí», after «¿La activo?» → baxy_exit, 3 of 3): closing BAXY in a turn
    // whose words answer BAXY's question waits for the «sí» in every mode (who has no hands cannot open it again); asked
    // on its own, after a turn that did not end asking, it goes at once.
    [TestCase("Listo, ya lo guardé. ¿Algo más?", true, true)]
    [TestCase("Listo, ya lo guardé. ¿Algo más?", false, true)]
    [TestCase("Listo, ya lo guardé.", true, false)]
    [TestCase("Listo, ya lo guardé.", false, false)]
    public async Task ClosingBaxyAnsweringItsQuestionWaitsForTheYes(string before, bool bypass, bool held)
    {
        using var fake = new FakeMind();
        fake.Script(Says(before));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            sent.Add(prepared.OperationName);
            return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null);
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            bypass ? Baxy.Kernel.Policy.ConfirmationMode.Bypass : Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync("recuerda que el sábado riego las plantas", Stopwatch.GetTimestamp(), CancellationToken.None);
        fake.Script(CallsThenReplies("baxy.exit", [], "¿Cierro BAXY?"));
        await loop.RunAsync("sale, va", Stopwatch.GetTimestamp(), CancellationToken.None);

        AssertExitHeld(sent, steps, loop, held);
    }

    // TPV5 (banco, semilla 1): the turn before offered the memory in a result (memory_disabled) and worded it without
    // «?»; «sale, va» still answers that offer, and closing BAXY waits for the «sí».
    [Test]
    public async Task ClosingBaxyAfterItsOfferWithoutAQuestionWaitsForTheYes()
    {
        using var fake = new FakeMind();
        fake.Script(CallsThenReplies("memory.list", new JsonObject { ["limit"] = 20, ["offset"] = 0, ["version"] = 1 },
            "Tu memoria está apagada. Puedo encenderla."));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var sent = new List<string>();
        core.AnswersForTests = (prepared, _) =>
        {
            if (prepared.OperationName == "memory.list")
            {
                return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
                    prepared.MissionId, prepared.InvocationId, OperationStatuses.Failed,
                    "{\"status\":\"failed\",\"error\":\"memory_disabled\"}", false, false, null, "memory_disabled");
            }

            sent.Add(prepared.OperationName);
            return new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId,
                prepared.InvocationId, OperationStatuses.Completed, "{\"status\":\"completed\"}", true, false, null, null);
        };
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Bypass);

        await loop.RunAsync("recuerda que el dentista me cambió la hora al viernes", Stopwatch.GetTimestamp(),
            CancellationToken.None);
        fake.Script(CallsThenReplies("baxy.exit", [], "¿Cierro BAXY?"));
        await loop.RunAsync("sale, va", Stopwatch.GetTimestamp(), CancellationToken.None);

        AssertExitHeld(sent, steps, loop, held: true);
    }

    private static void AssertExitHeld(List<string> sent, List<NativeTurnStep> steps, NativeTurnLoop loop, bool held) =>
        Assert.Multiple(() =>
        {
            Assert.That(sent, held ? Is.Empty : Is.EqualTo(new[] { "baxy.exit" }));
            Assert.That(steps.Single(static step => step.Operation == "baxy.exit").Sent, Is.EqualTo(!held));
            Assert.That(loop.HasPendingConfirmation, Is.EqualTo(held));
        });

    private static JsonObject CallsThenReplies(string operation, JsonObject arguments, string reply)
    {
        JsonObject script = CallsThenSays(operation, arguments);
        script["reply"]!["turn.continue"]!["reply"] = reply;
        return script;
    }

    private static JsonObject SetsProfile(string profile, string then) => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "action",
                ["operation"] = OwnBrakes.Operation,
                ["arguments"] = new JsonObject { ["setting"] = "tool_profile", ["value"] = profile },
            },
            ["turn.continue"] = new JsonObject { ["type"] = "turn.result", ["kind"] = "clarify", ["question"] = then },
        },
    };

    private static NativeTurnLoop BrakeLoop(
        MindSidecarClient mind, CoreProcessClient core, List<NativeTurnStep> steps, List<string> outcomes) =>
        new(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = static () => new RetryableOperationRegistry(),
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            ConfirmationResolved = outcomes.Add,
            BrakeOn = static brake => brake == "tool_profile",
        });

    // Auditoría de la App (2026-10-23; owner: a call run twice is worse than a replay): a call the engine never
    // answered keeps its invocation through the person's next turn and UncertainLifetime, so the same call made again
    // is the same invocation for the kernel's journal; after that, the same request is a new call.
    [Test]
    public async Task ACallTheEngineNeverAnsweredKeepsItsInvocationForAnIdenticalRetryWithinItsWindow()
    {
        using var fake = new FakeMind();
        fake.Script(CallsThenSays("system.time", new JsonObject()));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var clock = new ManualClock();
        var registry = new RetryableOperationRegistry();
        var steps = new List<NativeTurnStep>();
        NativeTurnLoop loop = UncertainLoop(mind, registry, steps, clock);

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That((string?)JsonNode.Parse(steps[^1].Observation)?["error"], Is.EqualTo("engine_no_answer"));
        PreparedOperation first = Unresolved(registry).Single();

        // The retry in the next turn: the same invocation, whose window starts again with this attempt.
        await loop.RunAsync("inténtalo de nuevo", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(Unresolved(registry), Is.EqualTo(new[] { first }));

        // A different call is its own invocation.
        Assert.That(registry.GetOrAdd(new RoutedOperation("system.time", new JsonObject { ["place"] = "Lima" })),
            Is.Not.SameAs(first));

        // The person's turn after it ends with no call: the window closes, and the same request is a new call.
        fake.Script(Says("Listo."));
        await loop.RunAsync("gracias", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(Unresolved(registry).Where(p => p.OperationName == "system.time" && !p.Arguments.TryGetProperty("place", out _)),
            Is.Empty);
        Assert.That(registry.GetOrAdd(new RoutedOperation("system.time", new JsonObject())).InvocationId,
            Is.Not.EqualTo(first.InvocationId));
    }

    [Test]
    public async Task ACallTheEngineNeverAnsweredIsANewCallAfterItsTimeOrInANewSession()
    {
        using var fake = new FakeMind();
        fake.Script(CallsThenSays("system.time", new JsonObject()));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var clock = new ManualClock();
        var registry = new RetryableOperationRegistry();
        var steps = new List<NativeTurnStep>();
        NativeTurnLoop loop = UncertainLoop(mind, registry, steps, clock);

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None);
        PreparedOperation first = Unresolved(registry).Single();
        clock.Now += NativeTurnLoop.UncertainLifetime + TimeSpan.FromSeconds(1);
        await loop.RunAsync("¿y ahora?", Stopwatch.GetTimestamp(), CancellationToken.None);
        PreparedOperation second = Unresolved(registry).Single();
        Assert.That(second.InvocationId, Is.Not.EqualTo(first.InvocationId));

        // The engine started again is the same session; a new one is not.
        loop.Reset(engineRestarted: true);
        Assert.That(Unresolved(registry), Is.EqualTo(new[] { second }));
        loop.Reset();
        Assert.That(Unresolved(registry), Is.Empty);
    }

    private static JsonObject CallsThenSays(string operation, JsonObject arguments) => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "action", ["operation"] = operation, ["arguments"] = arguments,
            },
            ["turn.continue"] = new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "El motor no respondió.",
            },
        },
    };

    // An engine said ready whose every call fails in transport (ReadyCore): engine_no_answer.
    private static NativeTurnLoop UncertainLoop(MindSidecarClient mind, RetryableOperationRegistry registry,
        List<NativeTurnStep> steps, TimeProvider clock)
    {
        CoreProcessClient core = ReadyCore();
        return new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        }, clock);
    }

    private static PreparedOperation[] Unresolved(RetryableOperationRegistry registry) =>
        [.. ((Dictionary<string, PreparedOperation>)typeof(RetryableOperationRegistry)
            .GetField("_operations", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(registry)!).Values];

    // P0.12 (noche 2026-10-27): the mind's error reply closes the person's turn as the failure it is (after a call, saying
    // so), and a heartbeat's leaves nothing on their screen; a step of a kind the loop does not run never runs as a call.
    // VIVO1 F4 (2026-11-09): the server of another model refused the turn for good (the mind's model_refused): the turn ends
    // with that code, which the screen says with the translator's reason, before a call or after one.
    // REV_APP TUR-1 (2026-11-09): refused after a call ran, the code says so too, as the decision that did not come does.
    [TestCase(false, "decision_unavailable", "request_failed")]
    [TestCase(true, "decision_unavailable_after_call", "request_failed")]
    [TestCase(false, "model_refused", "model_refused")]
    [TestCase(true, "model_refused_after_call", "model_refused")]
    public async Task AnErrorTheMindAnswersClosesTheTurnAsAFailure(bool afterCall, string failure, string code)
    {
        using var fake = new FakeMind();
        var call = new JsonObject
        {
            ["type"] = "turn.result",
            ["kind"] = "action",
            ["operation"] = "system.time",
            ["arguments"] = new JsonObject(),
        };
        fake.Script(afterCall
            ? new JsonObject { ["reply"] = new JsonObject { ["turn.decide"] = call }, ["fail"] = new JsonArray("turn.continue"), ["failCode"] = code }
            : new JsonObject { ["fail"] = new JsonArray("turn.decide", "turn.beat"), ["failCode"] = code });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var steps = new List<NativeTurnStep>();
        var failures = new List<string>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = static () => null,
            Mind = () => mind,
            Registry = static () => null,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = failures.Add,
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None)
            .WaitAsync(TimeSpan.FromSeconds(30));
        if (!afterCall)
        {
            await loop.RunBeatAsync(new JsonObject(), CancellationToken.None).WaitAsync(TimeSpan.FromSeconds(30));
        }

        Assert.Multiple(() =>
        {
            Assert.That(failures, Is.EqualTo(new[] { failure }));
            Assert.That(steps.Select(static step => step.Operation),
                Is.EqualTo(afterCall ? new[] { "system.time" } : Array.Empty<string>()));
            // R7-NB-1: a failure that is not the request's budget is not asked for again.
            Assert.That(fake.Requests("turn.continue"), Has.Count.EqualTo(afterCall ? 1 : 0));
        });
    }

    // R7-NB-1 (CU C03): the decision after app.open ran past the mind's budget and the turn ended with no words. Asked
    // again, as the same decision (the same result and final), the model answers what it did; once, never in a loop.
    [TestCase(1)]
    [TestCase(2)]
    public async Task ADecisionThatDidNotComeAfterACallIsAskedForAgain(int timedOut)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "system.time",
                    ["arguments"] = new JsonObject(),
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "conversation",
                    ["reply"] = "Lo pedí; no miré si se ve.",
                },
            },
            ["time_out"] = new JsonObject { ["turn.continue"] = timedOut },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<string>();
        var failures = new List<string>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = static () => null,
            Mind = () => mind,
            Registry = static () => null,
            MemoryProtector = static () => null,
            Publish = (text, _) => published.Add(text),
            Fail = failures.Add,
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = static _ => { },
        });

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None)
            .WaitAsync(TimeSpan.FromSeconds(30));

        JsonObject[] continued = [.. fake.Requests("turn.continue")];
        Assert.Multiple(() =>
        {
            Assert.That(failures, Is.EqualTo(timedOut == 1 ? Array.Empty<string>() : new[] { "decision_unavailable_after_call" }));
            Assert.That(published, Is.EqualTo(timedOut == 1 ? new[] { "Lo pedí; no miré si se ve." } : Array.Empty<string>()));
            Assert.That(continued, Has.Length.EqualTo(2));
            Assert.That(continued[1]["observation"]?.ToJsonString(), Is.EqualTo(continued[0]["observation"]?.ToJsonString()));
            Assert.That(continued[1]["final"]?.GetValue<bool>(), Is.EqualTo(continued[0]["final"]?.GetValue<bool>()));
        });
    }

    // Auditoría de la App (2026-10-23): told to answer in words (here, the engine is down), a mind that still calls does
    // not get that call run; before, each call ran, came back final again, and the turn never ended.
    [Test]
    public async Task ACallAfterTheMindWasToldToAnswerInWordsDoesNotRun()
    {
        using var fake = new FakeMind();
        var call = new JsonObject
        {
            ["type"] = "turn.result",
            ["kind"] = "action",
            ["operation"] = "system.time",
            ["arguments"] = new JsonObject(),
        };
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject { ["turn.decide"] = call, ["turn.continue"] = call.DeepClone() },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var steps = new List<NativeTurnStep>();
        var failures = new List<string>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = static () => null,
            Mind = () => mind,
            Registry = static () => null,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = failures.Add,
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None)
            .WaitAsync(TimeSpan.FromSeconds(30));

        Assert.Multiple(() =>
        {
            Assert.That(steps.Select(static step => step.Operation), Is.EqualTo(new[] { "system.time" }));
            Assert.That(failures, Is.EqualTo(new[] { "decision_unavailable_after_call" }));
            Assert.That(fake.Requests("turn.continue").Select(static request => (bool?)request["final"]),
                Is.EqualTo(new bool?[] { true }));
        });
    }

    // Auditoría de confirmaciones (2026-10-23): the person's words answer only BAXY's last question. The words right
    // after it still reach the model with the waiting call; a line BAXY publishes in that later turn leaves the question
    // behind, so the call is dropped then and the «sí» to that line is no answer to it.
    [Test]
    public async Task ALineOfALaterTurnLeavesTheQuestionBehindAndDropsTheCall()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes);

        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(loop.HasPendingConfirmation, Is.True);
        Assert.That(published[^1].Route, Is.EqualTo(PublicResponseRoute.Confirmation));

        fake.Script(Says("Son las tres. ¿Te pongo una alarma?"));
        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That((string?)fake.Requests("turn.decide")[1]["pendingConfirmation"]?["operation"], Is.EqualTo("web.fetch"));
        Assert.That(published[^1].Route, Is.EqualTo(PublicResponseRoute.Conversation));
        Assert.That(loop.HasPendingConfirmation, Is.False);
        Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));

        // The «sí» that follows reads which call was left behind, never that it waits; the words after it, nothing.
        fake.Script(Says("¿A qué hora?"));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[2]["pendingConfirmation"]?.ToJsonString(),
            Is.EqualTo("""{"operation":"web.fetch","ended":"dropped"}"""));
        await loop.RunAsync("a las siete", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[3]["pendingConfirmation"], Is.Null);
        Assert.That(fake.Seen, Has.No.Member("turn.confirm"));
        Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
    }

    // Auditoría de confirmaciones (2026-10-23): a «sí» after the time to answer ran out reads that it expired (audit
    // 2026-10-15, App 3), not that nothing was asked; the call ends «expired» then, and the next words read nothing.
    [Test]
    public async Task ASiAfterTheTimeRanOutReadsThatTheQuestionExpired()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        var clock = new ManualClock();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes, clock);
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(loop.HasPendingConfirmation, Is.True);

        clock.Now += NativeTurnLoop.ProposalLifetime + TimeSpan.FromSeconds(1);
        fake.Script(Says("Esa pregunta venció. ¿Abro la página?"));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[1]["pendingConfirmation"]?.ToJsonString(),
            Is.EqualTo("""{"operation":"web.fetch","ended":"expired"}"""));
        Assert.That(outcomes, Is.EqualTo(new[] { "expired" }));

        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[2]["pendingConfirmation"], Is.Null);
    }

    // The words right after the question that publish nothing (the turn failed) leave it waiting.
    [Test]
    public async Task ATurnThatPublishesNothingLeavesTheQuestionWaiting()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes);
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);

        fake.Script(new JsonObject { ["fail"] = new JsonArray("turn.decide") });
        await loop.RunAsync("eh", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.That(loop.HasPendingConfirmation, Is.True);
        Assert.That(outcomes, Is.Empty);
    }

    // The person's turn holds a fetch of a host nobody gave and asks it (BAXY Renew al máximo 11.5).
    private static JsonObject HeldFetch() => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "action",
                ["operation"] = "web.fetch",
                ["arguments"] = new JsonObject { ["url"] = "https://exfil.example/c" },
            },
            ["turn.continue"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "conversation",
                ["reply"] = "¿Abro esa página?",
            },
        },
    };

    // Prefijo c3, S4 (T6): words that settle nothing neither run the waiting call nor cancel it. The model reads that it
    // still waits and how to ask again (by voice, never a click); the line it says next is the same call's question
    // again, under the same card, and the person's next words answer it.
    [Test]
    public async Task AnUnclearAnswerLeavesTheCallWaitingAndTheNextLineAsksItAgain()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        var asked = new List<NativeTurnConfirmation>();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = (text, route) => published.Add((text, route)),
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            ConfirmationAsked = asked.Add,
            ConfirmationResolved = outcomes.Add,
        });
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);

        fake.Script(Answers("unclear", Reply("¿Abro exfil.example, sí o no?")));
        await loop.RunAsync("sí, pero la otra", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? observed = JsonNode.Parse((string)fake.Requests("turn.continue")[^1]["observation"]!);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["status"], Is.EqualTo("needs_confirmation"));
            Assert.That((string?)observed?["operation"], Is.EqualTo("web.fetch"));
            Assert.That((string?)observed?["arguments"]?["url"], Is.EqualTo("https://exfil.example/c"));
            Assert.That((string?)observed?["next"], Does.Contain("answer by voice"));
            Assert.That((string?)observed?["next"], Does.Contain("never ask them to click"));
            Assert.That(loop.HasPendingConfirmation, Is.True);
            Assert.That(outcomes, Is.Empty);
            Assert.That(published[^1], Is.EqualTo(("¿Abro exfil.example, sí o no?", PublicResponseRoute.Confirmation)));
            Assert.That(asked, Has.Count.EqualTo(1));
        });

        fake.Script(Answers("no", Reply("Vale, no la abro.")));
        await loop.RunAsync("no", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((string?)fake.Requests("turn.decide")[^1]["pendingConfirmation"]?["operation"],
                Is.EqualTo("web.fetch"));
            Assert.That((string?)JsonNode.Parse((string)fake.Requests("turn.continue")[^1]["observation"]!)?["error"],
                Is.EqualTo("declined_by_person"));
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That(outcomes, Is.EqualTo(new[] { "declined" }));
        });
    }

    // After an unclear answer the model answers in words: a «sí» it gives itself to the same words runs nothing, and a
    // turn that ends without asking again leaves no call for words that answer no question.
    [Test]
    public async Task AnUnclearAnswerNotAskedAgainRunsNothingAndDropsTheCall()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes);
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);

        fake.Script(Answers("unclear", Answer("yes")));
        await loop.RunAsync("no sé, sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(fake.Requests("turn.continue").Select(static request => (bool?)request["final"]),
                Is.EqualTo(new bool?[] { true, true }));
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
        });
    }

    // REM4 (REV14 A-R3): «no, déjalo», the model's «sí» reached the App as unclear, and its line asked nothing («Vale, lo
    // dejamos.»): that line is no question (no card under it) and the call is dropped when the turn ends, so neither a
    // «Sí» pressed nor the next «perfecto» runs it.
    [Test]
    public async Task AnUnclearAnswerFollowedByALineThatAsksNothingDropsTheCall()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes);
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);

        fake.Script(Answers("unclear", Reply("Vale, lo dejamos.")));
        await loop.RunAsync("no, déjalo", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(published[^1].Text, Is.EqualTo("Vale, lo dejamos."));
            Assert.That(published[^1].Route, Is.Not.EqualTo(PublicResponseRoute.Confirmation));
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
        });
    }

    private static JsonObject Answer(string answer) => new()
    {
        ["type"] = "turn.result",
        ["kind"] = "action",
        ["operation"] = "confirmation.answer",
        ["arguments"] = new JsonObject { ["answer"] = answer },
    };

    // The person's words answer the waiting call with this answer; what the mind decides after its result, then.
    private static JsonObject Answers(string answer, JsonObject then) => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = Answer(answer),
            ["turn.continue"] = then,
        },
    };

    private static JsonObject Reply(string reply) =>
        new() { ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = reply };

    private static JsonObject Says(string reply) => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject { ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = reply },
        },
    };

    private static NativeTurnLoop PersonLoop(MindSidecarClient mind, List<(string Text, string Route)> published,
        List<string> outcomes, TimeProvider? clock = null)
    {
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        return new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = (text, route) => published.Add((text, route)),
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            ConfirmationResolved = outcomes.Add,
        }, clock);
    }

    // The kernel asks again for a call whose earlier attempt may have happened (reconciliationRequired): its card says so.
    [TestCase(true)]
    [TestCase(false)]
    public void AChallengeAfterAnAttemptThatMayHaveRunIsAskedAsSuch(bool reconciliationRequired)
    {
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        var clock = new ManualClock();
        NativeTurnLoop loop = Loop([], clock);
        PreparedOperation prepared = new RetryableOperationRegistry().GetOrAdd(
            new RoutedOperation("system.recyclebin.empty", new JsonObject()));
        object pending = typeof(PendingOperationConfirmation)
            .GetConstructor(Private, [typeof(PreparedOperation), typeof(string), typeof(DateTimeOffset), typeof(bool)])!
            .Invoke([prepared, "token", clock.GetUtcNow().AddMinutes(2), reconciliationRequired]);
        typeof(NativeTurnLoop).GetField("_pending", Private)!.SetValue(loop, pending);

        var asked = (NativeTurnConfirmation?)typeof(NativeTurnLoop).GetMethod("Waiting", Private)!.Invoke(loop, null);

        Assert.That(asked?.EffectStarted, Is.EqualTo(reconciliationRequired));
    }

    // Encargo 83: a click the kernel asks about because it changes a setting of Windows says so on its card: «sale al
    // mundo o no se deshace» would be false of it.
    [Test]
    public void AChallengeAboutASettingOfWindowsSaysSoOnItsCard()
    {
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        var clock = new ManualClock();
        NativeTurnLoop loop = Loop([], clock);
        PreparedOperation prepared = new RetryableOperationRegistry().GetOrAdd(
            new RoutedOperation("input.visible.click", new JsonObject { ["label"] = "Interruptor" }));
        string token = new('A', 43);
        string expires = clock.GetUtcNow().AddMinutes(2).ToString("O", System.Globalization.CultureInfo.InvariantCulture);
        var challenge = new OperationResponse(
            ProtocolTypes.OperationResponse, "r", prepared.MissionId, prepared.InvocationId, OperationStatuses.Pending,
            "asks", false, false,
            JsonDocument.Parse("{\"version\":" + ConfirmationChallengeContract.CurrentVersion + ",\"token\":\"" + token
                + "\",\"expiresAtUtc\":\"" + expires + "\",\"reconciliationRequired\":false,"
                + "\"facts\":{\"systemChange\":{\"control\":\"Interruptor\",\"change\":\"switch\",\"state\":\"off\"}}}")
                .RootElement.Clone(),
            ConfirmationChallengeContract.RequiredErrorCode);
        Assert.That(PendingOperationConfirmation.TryCreate(challenge, prepared, clock, out PendingOperationConfirmation? pending), Is.True);
        typeof(NativeTurnLoop).GetField("_pending", Private)!.SetValue(loop, pending);

        var asked = (NativeTurnConfirmation?)typeof(NativeTurnLoop).GetMethod("Waiting", Private)!.Invoke(loop, null);
        JsonObject card = FieldStepProjection.Card("1", "confirm", asked!.Operation, new JsonObject { ["label"] = "Interruptor" },
            asked.Risk, asked.ExpiresUtc, null, english: false, asked.EffectStarted, asked.Cause);

        Assert.That((string?)card["risk"], Is.EqualTo("cambia un ajuste del sistema"));
    }

    // C16: the «sí» to a heartbeat's proposal is sent again as the kernel's confirmation only for that same invocation and
    // only when its earlier run cannot have acted; one the kernel asks to reconcile is asked to the person as such.
    [TestCase(false, true)]
    [TestCase(true, false)]
    public void AProposalsYesAnswersTheKernelOnlyForAnInvocationThatHasNotRunBefore(bool reconciliationRequired,
        bool answered)
    {
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        var registry = new RetryableOperationRegistry();
        PreparedOperation proposal = registry.GetOrAdd(new RoutedOperation("system.recyclebin.empty", new JsonObject()));
        PreparedOperation other = registry.GetOrAdd(new RoutedOperation("note.trash", new JsonObject()));
        var pending = (PendingOperationConfirmation)typeof(PendingOperationConfirmation)
            .GetConstructor(Private, [typeof(PreparedOperation), typeof(string), typeof(DateTimeOffset), typeof(bool)])!
            .Invoke([proposal, "token", DateTimeOffset.UtcNow.AddMinutes(2), reconciliationRequired]);

        Assert.Multiple(() =>
        {
            Assert.That(pending.AnsweredByProposal(proposal), Is.EqualTo(answered));
            Assert.That(pending.AnsweredByProposal(other), Is.False);
        });
    }

    // e01442da5 (wire.py): message.send is message_send_set to the model (message_send ⊂ message_send_test). The call
    // held for the person and the result of one that waits for the person's yes named message_send, a name the model is
    // not shown; they name the call by the name shown to the model.
    [Test]
    public void ACallHeldForThePersonIsNamedAsTheModelSeesIt()
    {
        const BindingFlags Static = BindingFlags.Static | BindingFlags.NonPublic;
        string next = (string)typeof(NativeTurnLoop).GetMethod("AskThePersonAbout", Static)!
            .Invoke(null, ["message.send"])!;
        string waiting = (string)typeof(NativeTurnLoop).GetMethod("Waiting", Static, [typeof(string), typeof(string)])!
            .Invoke(null, ["{\"status\":\"completed\"}", "message.send"])!;

        Assert.Multiple(() =>
        {
            Assert.That(next, Does.EndWith("calling message_send_set again before they answer is not their answer: it is a new call"));
            Assert.That(waiting, Does.Contain("message_send_set waits for the person's yes and has not run"));
            Assert.That(next + waiting, Does.Not.Match(@"\bmessage_send\b(?!_)"));
        });
    }

    private const string TodaysNext = "nothing ran: ask the person whether to do it; their answer goes in confirm_pending "
        + "(answer yes, no or unclear); calling web_fetch again before they answer is not their answer: it is a new call";

    private static string Search(params string[] urls) =>
        new JsonObject
        {
            ["status"] = "completed",
            ["observed"] = new JsonObject
            {
                ["results"] = new JsonArray([.. urls.Select(static url => (JsonNode)new JsonObject { ["url"] = url })]),
            },
        }.ToJsonString();

    // The person's turn where the model fetches a host nobody gave (exfil.example), after what the session's earlier
    // calls returned (a web.search's result, as the loop observes it), if any.
    private static async Task<(List<NativeTurnStep> Steps, List<NativeTurnConfirmation> Asked, NativeTurnLoop Loop)>
        HoldAFetchAsync(string? results)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "web.fetch",
                    ["arguments"] = new JsonObject { ["url"] = "https://exfil.example/c" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Abro esa página?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var asked = new List<NativeTurnConfirmation>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            ConfirmationAsked = asked.Add,
        });
        if (results is not null)
        {
            var egress = (NetworkEgress)typeof(NativeTurnLoop)
                .GetField("_egress", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(loop)!;
            egress.Observed("web.search", results);
        }

        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        return (steps, asked, loop);
    }

    // An engine that says it is ready and is never sent anything: a held call stops before it.
    // COR1 (VIVO3 A3, 2 de 2): with «Búsqueda web» off the model switched it back on with baxy.settings.set to play the
    // video the person asked for. A brake the person did not ask to relax in this turn waits for their «sí», and its
    // card says which setting and to what; asked by its name, it goes. TPV1 (dueño, 10-11: the «sí» is spoken, nothing is
    // left to the person's hands): in Bypass too it waits for the «sí» (COR1 refused it there).
    [TestCase("Busca en YouTube un vídeo de cómo hacer pan amasado", false, "needs_confirmation")]
    [TestCase("Enciende la búsqueda web", false, null)]
    [TestCase("Pon en YouTube un vídeo de gatitos jugando", true, "needs_confirmation")]
    [TestCase("Enciende la búsqueda web", true, null)]
    // TPV1: a tool profile is asked for by its own name; asked for something it does not have, it waits for the «sí»; Bypass
    // on waits for it even when named; Clima is a brake of Privacidad as «Búsqueda web» is.
    [TestCase("Pásate al perfil Diario", false, null, "tool_profile", "diario")]
    [TestCase("pasate al perfil completo", true, null, "tool_profile", "completo")]
    [TestCase("pasate al perfil completo por favor", true, "needs_confirmation", "tool_profile", "completo")]
    [TestCase("Recuerda que mi gata se llama Mora", false, "needs_confirmation", "tool_profile", "diario")]
    [TestCase("Recuerda que mi gata se llama Mora", true, "needs_confirmation", "tool_profile", "diario")]
    [TestCase("Activa el modo sin frenos", false, "needs_confirmation", "confirmation_bypass", "on")]
    [TestCase("Enciende el clima", false, null, "weather", "on")]
    [TestCase("¿Hará frío el jueves por la tarde?", true, "needs_confirmation", "weather", "on")]
    // The memory is not one: in Bypass memory.enable goes as before (held, the 4B called it again after the person's «sí»).
    [TestCase("Acuérdate de que mi gata se llama Mora", true, null, "memory", "on", "memory.enable")]
    public async Task ABrakeThePersonDidNotAskToRelaxDoesNotChangeUnasked(
        string words, bool bypass, string? stopped, string setting = "web_search", string value = "on",
        string operation = OwnBrakes.Operation)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = operation,
                    ["arguments"] = operation == OwnBrakes.Operation
                        ? new JsonObject { ["setting"] = setting, ["value"] = value }
                        : new JsonObject { ["enabled"] = true },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "La búsqueda web está apagada. ¿La enciendo?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var asked = new List<NativeTurnConfirmation>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            // memory.enable is prepared as every memory call (sealed for the engine) before it is weighed.
            MemoryProtector = () => operation == OwnBrakes.Operation ? null : new MemoryOperationProtector(
                new Baxy.Security.Windows.BoundProtectedJsonCodec(new PlainPayload()), Guid.NewGuid().ToString("D")),
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            ConfirmationAsked = asked.Add,
            BrakeOn = brake => brake == setting,
        });
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            bypass ? Baxy.Kernel.Policy.ConfirmationMode.Bypass : Baxy.Kernel.Policy.ConfirmationMode.Normal);

        await loop.RunAsync(words, Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? first = JsonNode.Parse(steps[0].Observation);
        Assert.Multiple(() =>
        {
            Assert.That(steps[0].Operation, Is.EqualTo(operation));
            if (stopped is null)
            {
                Assert.That(steps[0].Status, Is.Not.EqualTo("needs_confirmation").And.Not.EqualTo("rejected"));
                Assert.That((string?)first?["error"], Is.Not.EqualTo(OwnBrakes.Cause));
                Assert.That(asked, Is.Empty);
                return;
            }

            Assert.That((steps[0].Status, steps[0].Sent), Is.EqualTo((stopped, false)));
            Assert.That((string?)first?["cause"], Is.EqualTo(OwnBrakes.Cause));
            Assert.That((string?)first?["next"], Does.EndWith(OwnBrakes.HeldNext));
            Assert.That(asked.Select(static call => (call.Operation, call.Proposal, call.Cause)),
                Is.EqualTo(new[] { (operation, false, (string?)OwnBrakes.Cause) }));
            Assert.That(loop.HasPendingConfirmation, Is.True);
        });
    }

    // COR1: a brake already relaxed is no change to ask about (the call runs and its receipt says «changed: false»).
    [Test]
    public void ABrakeAlreadyRelaxedIsNotHeld()
    {
        using var fake = new FakeMind();
        Baxy.Kernel.Policy.ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(),
            Baxy.Kernel.Policy.ConfirmationMode.Normal);
        var given = new JsonObject { ["setting"] = "web_search", ["value"] = "on" };
        NativeTurnLoop Built(bool on) => new(new NativeTurnLoop.Host
        {
            Core = static () => null,
            Mind = static () => null,
            Registry = static () => null,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            BrakeOn = _ => on,
        }, TimeProvider.System);

        Assert.Multiple(() =>
        {
            Assert.That(Built(on: true).HeldForTheYes(OwnBrakes.Operation, given), Is.EqualTo(OwnBrakes.Cause));
            Assert.That(Built(on: false).HeldForTheYes(OwnBrakes.Operation, given), Is.Null);
            Assert.That(Loop([], TimeProvider.System).HeldForTheYes(OwnBrakes.Operation, given), Is.EqualTo(OwnBrakes.Cause));
        });
    }

    private static CoreProcessClient ReadyCore()
    {
        var core = new CoreProcessClient();
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, Process.GetCurrentProcess());
        return core;
    }

    private static NativeTurnLoop Loop(List<string> outcomes, TimeProvider clock) => new(new NativeTurnLoop.Host
    {
        Core = static () => null,
        Mind = static () => null,
        Registry = static () => null,
        MemoryProtector = static () => null,
        Publish = static (_, _) => { },
        Fail = static _ => { },
        Notice = static _ => { },
        NoticeHeard = static () => false,
        ConfirmationResolved = outcomes.Add,
    }, clock);

    // Uso-124: the mind's «progress» lines reach the turn's notice, which sounds for a model still reading. The person's
    // words arrived 25 s ago, so the first advance is past SilenceNotice.ReadingSign; with them just arrived there is none.
    [TestCase(25, 1)]
    [TestCase(0, 0)]
    public async Task AModelStillReadingIsHeardOnlyPastItsWait(int arrivedSecondsAgo, int sounds)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject { ["turn.decide"] = new JsonObject { ["every"] = 0.05, ["count"] = 4 } },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        int heard = 0;
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => true,
            StillReading = () => Interlocked.Increment(ref heard),
        });

        long arrived = System.Diagnostics.Stopwatch.GetTimestamp()
            - (long)(arrivedSecondsAgo * (double)System.Diagnostics.Stopwatch.Frequency);
        await loop.RunAsync("hola", arrived, CancellationToken.None);

        Assert.That(heard, Is.EqualTo(sounds));
    }

    // Revisión PCR1, A1 (Feria 2026-10-27 again): on the RX 7600 the notice comes due while the model still decides, so it
    // is asked when the call starts, and its phrase comes once the call ended. With slow notices that phrase was said for a
    // call refused, failed or only waiting for the person's yes («Borrando el archivo…» before «¿Lo borro?»): it is said
    // after its call only when that call completed.
    [TestCase("completed", 1)]
    [TestCase("needs_confirmation", 0)]
    [TestCase("rejected", 0)]
    [TestCase("failed", 0)]
    public async Task WithSlowNoticesAPhraseAfterItsCallIsSaidOnlyWhenTheCallCompleted(string ended, int said)
    {
        using var fake = new FakeMind();
        string operation = ended is "completed" or "failed" ? "conversation.list" : "web.fetch";
        fake.Script(new JsonObject
        {
            ["delay"] = new JsonObject { ["turn.notice"] = 0.3 },
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = operation,
                    ["arguments"] = operation == "web.fetch"
                        ? new JsonObject { ["url"] = "https://exfil.example/c" }
                        : new JsonObject(),
                },
                ["turn.notice"] = new JsonObject
                {
                    ["type"] = "turn.notice.result", ["notice"] = "Leyendo la página.", ["slow"] = true,
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "¿Abro esa página?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var steps = new List<NativeTurnStep>();
        var notices = new List<string>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = phrase => { lock (notices) { notices.Add(phrase); } },
            NoticeHeard = static () => true,
            StepCompleted = steps.Add,
            Refuse = (_, _) => ended == "rejected" ? "web_disabled_by_owner" : null,
            Conversation = (_, _) => ended == "completed" ? """{"status":"completed"}""" : null,
        });

        // The words came 5 s ago: the notice is due at once, while the model decides, and is asked when the call starts.
        long arrived = Stopwatch.GetTimestamp() - 5 * Stopwatch.Frequency;
        await loop.RunAsync("lee la página", arrived, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(steps.Single().Status, Is.EqualTo(ended), "the call ended as the case says");
            Assert.That(mind.NoticesAreSlow, Is.True);
            lock (notices)
            {
                Assert.That(notices, Has.Count.EqualTo(said));
            }
        });
    }

    private sealed class ManualClock : TimeProvider
    {
        internal DateTimeOffset Now { get; set; } = new(2026, 10, 22, 10, 0, 0, TimeSpan.Zero);

        public override DateTimeOffset GetUtcNow() => Now;
    }

    // A payload that seals nothing: the memory calls a test only weighs are prepared as the App prepares them.
    private sealed class PlainPayload : Baxy.Security.Windows.IProtectedPayload
    {
        public string ProtectionMode => "test";

        public byte[] Seal(ReadOnlySpan<byte> plaintext, string purpose) => plaintext.ToArray();

        public byte[] Open(ReadOnlySpan<byte> envelope, string purpose) => envelope.ToArray();
    }
}
