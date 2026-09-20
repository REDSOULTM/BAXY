using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class MindShellEndToEndTests
{
    private static readonly JsonSerializerOptions AttestationJsonOptions = new()
    {
        WriteIndented = true,
    };

    private const string ContractTraceEnvironmentVariable =
        "BAXY_MIND_CONTRACT_TRACE";
    private const string PhysicalAttestationEnvironmentVariable =
        "BAXY_MIND_SHELL_E2E_ATTESTATION";

    private static readonly string[] MindEnvironmentVariables =
    [
        "BAXY_DATA_DIR",
        MindSidecarClient.PythonEnvironmentVariable,
        MindSidecarClient.PythonPathEnvironmentVariable,
        "BAXY_MIND_LLM_GGUF",
        "BAXY_MIND_LLAMA_SERVER",
        "BAXY_MIND_NGL",
        "BAXY_MIND_STT_DIR",
        "BAXY_VOICE_WAKE_ON_START",
        "HF_HUB_OFFLINE",
        ContractTraceEnvironmentVariable,
        PhysicalAttestationEnvironmentVariable,
    ];

    [TestCase("no abras Steam, dime la hora")]
    [TestCase("don't launch Steam, tell me the time")]
    [TestCase("no abras el bloc de notas")]
    [TestCase("Dime la hora y el estado del audio.")]
    [TestCase("Dime la hora, revisa el estado del audio y dime el uso de CPU.")]
    [TestCase("Dime la hora y no silencies el audio.")]
    public async Task ConstraintsAndCompoundRequestsCrossTheMindDecisionBoundary(string request)
    {
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            _ = await SubmitAsync(viewModel, request);
            JsonElement decision = ReadTrace(tracePath).Single(entry =>
                entry.GetProperty("type").GetString() == "turn.decide");
            Assert.That(decision.GetProperty("text").GetString(), Is.EqualTo(request));
            Assert.That(viewModel.HasPendingPlan, Is.False);
        });
    }

    [Test]
    public async Task PersonalQuestionExecutesItsSelectedReadInsteadOfBecomingConversation()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string result = await SubmitAsync(viewModel, "What is in my task list?");
            Assert.That(result, Does.Contain("\"operation\":\"task.list\""));
            Assert.That(result, Does.Contain("\"verified\":true"));
            Assert.That(result, Does.Not.Contain("\"kind\":\"conversation\""));
            Assert.That(ReadTrace(tracePath).Count(entry =>
                entry.GetProperty("type").GetString() == "turn.decide"), Is.EqualTo(1));
            Assert.That(viewModel.HasPendingPlan, Is.False);
            AssertOutboxEmpty(dataRoot);
        });
    }

    [TestCase("me llamo emmanuel, dime hola emmanuel", "Hola Emmanuel, ¿cómo estás?", "es")]
    [TestCase("me llamo Albeda", "Hola Albeda, encantado de conocerte.", "es")]
    [TestCase("my favorite city is Lima", "What do you enjoy most about Lima?", "en")]
    public async Task ImplicitPersonalContextReachesConversationWithoutPersistence(
        string request, string reply, string language)
    {
        const string variable = "BAXY_MIND_CONTRACT_TURN_RESULT";
        using var environment = new EnvironmentVariableScope([variable]);
        Environment.SetEnvironmentVariable(variable, new JsonObject
        {
            ["kind"] = "conversation",
            ["effectOperations"] = new JsonArray(),
            ["reply"] = reply,
            ["question"] = string.Empty,
            ["responseLanguage"] = language,
        }.ToJsonString());
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
            long before = new FileInfo(journalPath).Length;
            string result = await SubmitAsync(viewModel, request);
            Assert.That(result, Is.EqualTo(reply));
            JsonElement decision = ReadTrace(tracePath).Single(entry =>
                entry.GetProperty("type").GetString() == "turn.decide");
            Assert.That(decision.GetProperty("text").GetString(), Is.EqualTo(request));
            Assert.That(new FileInfo(journalPath).Length, Is.EqualTo(before),
                "Personal context must not invoke persistent memory or another effect.");
            Assert.That(viewModel.HasPendingPlan, Is.False);
            Assert.That(File.Exists(Path.Combine(dataRoot, "shell", "retry-outbox.v1.json")), Is.False);
        });
    }

    [TestCase("Me llamo Lina.", "¿Cómo me llamo?", true)]
    [TestCase("My name is Priya.", "What is my name?", true)]
    [TestCase("Me llamo Renata.", "¿Cómo me llamo?", true)]
    [TestCase("Me llamo Lina.", "What name have you saved in private memory?", false)]
    [TestCase("Mi hermana se llama Lina.", "¿Cómo me llamo?", false)]
    [TestCase("hola", "¿Cómo me llamo?", false)]
    public async Task CurrentNameConversationDoesNotBecomeAnUnrequestedPersistentRead(
        string declaration, string recall, bool usesConversation)
    {
        const string variable = "BAXY_MIND_CONTRACT_TURN_RESULT";
        using var environment = new EnvironmentVariableScope([variable]);
        bool english = declaration.StartsWith("My", StringComparison.Ordinal);
        string reply = english ? "Your name is Priya." : "Te llamas Lina.";
        Environment.SetEnvironmentVariable(variable, new JsonObject
        {
            ["kind"] = "conversation",
            ["effectOperations"] = new JsonArray(),
            ["reply"] = reply,
            ["question"] = string.Empty,
            ["responseLanguage"] = english ? "en" : "es",
        }.ToJsonString());
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            _ = await SubmitAsync(viewModel, declaration);
            string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
            long before = new FileInfo(journalPath).Length;
            int decisionsBefore = ReadTrace(tracePath).Count(entry => Property(entry, "type") == "turn.decide");
            string result = await SubmitAsync(viewModel, recall);
            JsonElement[] decisions = ReadTrace(tracePath).Where(entry => Property(entry, "type") == "turn.decide").ToArray();
            if (usesConversation)
            {
                Assert.Multiple(() =>
                {
                    Assert.That(decisions.Length, Is.EqualTo(decisionsBefore + 1));
                    Assert.That(result, Is.EqualTo(reply));
                    Assert.That(new FileInfo(journalPath).Length, Is.EqualTo(before),
                        "The current human name stays in conversation; no persistent read or write.");
                    Assert.That(File.Exists(Path.Combine(dataRoot, "shell", "retry-outbox.v1.json")), Is.False);
                });
                AssertHistoryContainsUser(decisions[^1], declaration);
            }
            else
            {
                Assert.Multiple(() =>
                {
                    Assert.That(decisions.Length, Is.EqualTo(decisionsBefore));
                    Assert.That(result, Does.Contain("memory_disabled"));
                    Assert.That(new FileInfo(journalPath).Length, Is.GreaterThan(before));
                });
                AssertOutboxEmpty(dataRoot);
            }
            Assert.That(viewModel.HasPendingPlan, Is.False);
        });
    }

    [Test]
    public async Task ImplicitPersonalContextCannotAuthorizeAModelProposedMemoryWrite()
    {
        const string variable = "BAXY_MIND_CONTRACT_TURN_RESULT";
        using var environment = new EnvironmentVariableScope([variable]);
        Environment.SetEnvironmentVariable(variable, new JsonObject
        {
            ["kind"] = "action",
            ["operation"] = "memory.save",
            ["effectOperations"] = new JsonArray("memory.save"),
            ["reply"] = string.Empty,
            ["question"] = string.Empty,
        }.ToJsonString());
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
            long before = new FileInfo(journalPath).Length;
            string result = await SubmitAsync(viewModel, "me llamo Albeda");
            Assert.That(ReadTrace(tracePath).Count(entry =>
                entry.GetProperty("type").GetString() == "turn.decide"), Is.EqualTo(1));
            Assert.That(result, Does.Contain("memory_needs_explicit_request"));
            Assert.That(new FileInfo(journalPath).Length, Is.EqualTo(before));
            Assert.That(viewModel.HasPendingPlan, Is.False);
            Assert.That(File.Exists(Path.Combine(dataRoot, "shell", "retry-outbox.v1.json")), Is.False);
        });
    }

    // CONVERSATION1150/002, /007 y KNOWLEDGE1149/004: una recuperación que trae la pregunta
    // validada de la mente es una pregunta, no un fallo; no inventa datos personales, no
    // ejecuta nada y no deja un plan pendiente.
    [Test]
    public async Task DecisionRecoveryAsksInsteadOfInventingPersonalData()
    {
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            string result = await SubmitAsync(viewModel, "What is on my to do list?");
            Assert.That(result, Does.Contain("\"kind\":\"clarification\""));
            Assert.That(result, Does.Contain("\"cause\":\"ambiguous_request\""));
            Assert.That(result, Does.Not.Contain("\"kind\":\"conversation\""));
            Assert.That(result, Does.Not.Contain("task"));
            Assert.That(viewModel.HasPendingPlan, Is.False);
            _ = await SubmitAsync(viewModel, "Explícame la fotosíntesis");
            JsonElement next = ReadTrace(tracePath).Last(entry =>
                entry.GetProperty("type").GetString() == "turn.decide");
            Assert.That(next.GetProperty("pendingClarification").GetBoolean(), Is.False);
        });
    }

    [Test]
    public async Task RejectedUnsupportedReplyKeepsItsCatalogBoundaryDuringComposition()
    {
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            string result = await SubmitAsync(viewModel,
                "abre la aplicación C03ProgramaInexistente20260906");
            Assert.That(result, Does.Contain("\"cause\":\"out_of_catalog\""));
            Assert.That(result, Does.Not.Contain("\"kind\":\"conversation\""));
            Assert.That(ReadTrace(tracePath).Count(entry =>
                entry.GetProperty("type").GetString() == "turn.decide"), Is.EqualTo(1));
            Assert.That(viewModel.HasPendingPlan, Is.False);
        });
    }

    [TestCase("cancelar")]
    [TestCase("cancel that")]
    [TestCase("cancela eso")]
    public async Task CancellingPendingClarificationDoesNotReinterpretTheOriginalRequest(string cancellation)
    {
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            _ = await SubmitAsync(viewModel, "Haz eso");
            int decisions = ReadTrace(tracePath).Count(entry =>
                entry.GetProperty("type").GetString() == "turn.decide");
            string cancelled = await SubmitAsync(viewModel, cancellation);
            Assert.That(cancelled, Does.Contain("clarification_cancelled"));
            Assert.That(ReadTrace(tracePath).Count(entry =>
                entry.GetProperty("type").GetString() == "turn.decide"), Is.EqualTo(decisions));
            Assert.That(viewModel.StatusDescription, Does.Not.Contain("aclaración"));
        });
    }

    [Test]
    public async Task LateVoiceCancellationAcknowledgementDoesNotInvalidateModelWork()
    {
        using var environment = new EnvironmentVariableScope(MindEnvironmentVariables);
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable, FindPython());
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable,
            Path.Combine(FindRepositoryRoot(), "tests", "fixtures", "mind_turn_contract"));
        await using var mind = new MindSidecarClient();
        Assert.That(await mind.TryStartAsync([], TimeSpan.FromSeconds(10), CancellationToken.None), Is.True);
        Task<MindComposedMessage?> current = mind.ComposeUserMessageAsync("current", "conversation",
            new JsonObject { ["situation"] = "Current reply", ["fixtureDelayMilliseconds"] = 400 },
            TimeSpan.FromSeconds(2), CancellationToken.None);

        Assert.That(await mind.VoiceCancelAsync(TimeSpan.FromMilliseconds(60), CancellationToken.None), Is.False);
        Assert.That(mind.IsReady, Is.True, "A missing voice acknowledgement is not a dead model transport.");
        Assert.That((await current)?.Text, Is.EqualTo("Current reply"));
        MindComposedMessage? next = await mind.ComposeUserMessageAsync("next", "conversation",
            new JsonObject { ["situation"] = "Next reply" },
            TimeSpan.FromSeconds(2), CancellationToken.None);
        Assert.That(next?.Text, Is.EqualTo("Next reply"));
    }

    [Test]
    public async Task MissingDecisionReportsMindUnavailabilityInsteadOfAmbiguousUserInput()
    {
        const string failureVariable = "BAXY_MIND_CONTRACT_DECISION_UNAVAILABLE";
        using var environment = new EnvironmentVariableScope([failureVariable]);
        Environment.SetEnvironmentVariable(failureVariable, "1");
        await WithContractMindAsync(async (viewModel, _, _) =>
        {
            string result = await SubmitAsync(viewModel, "abre Paint");
            Assert.That(result, Does.Contain("\"cause\":\"mind_unavailable\""));
            Assert.That(result, Does.Not.Contain("ambiguous_request"));
        });
    }

    [Test]
    public async Task QueuedCompositionKeepsItsOwnExecutionBudgetAndTheSidecarReady()
    {
        using var environment = new EnvironmentVariableScope(MindEnvironmentVariables);
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable, FindPython());
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable,
            Path.Combine(FindRepositoryRoot(), "tests", "fixtures", "mind_turn_contract"));
        await using var mind = new MindSidecarClient();
        Assert.That(await mind.TryStartAsync([], TimeSpan.FromSeconds(10), CancellationToken.None), Is.True);

        Task<MindComposedMessage?> slow = mind.ComposeUserMessageAsync("slow", "conversation",
            new JsonObject { ["situation"] = "First reply", ["fixtureDelayMilliseconds"] = 800 },
            TimeSpan.FromSeconds(3), CancellationToken.None);
        Task<MindComposedMessage?> queued = mind.ComposeUserMessageAsync("next", "conversation",
            new JsonObject { ["situation"] = "Next reply" },
            TimeSpan.FromMilliseconds(400), CancellationToken.None);
        Assert.That(mind.HasActiveRequest, Is.True);
        MindComposedMessage?[] replies = await Task.WhenAll(slow, queued);
        Assert.Multiple(() =>
        {
            Assert.That(replies[0]?.Text, Is.EqualTo("First reply"));
            Assert.That(replies[1]?.Text, Is.EqualTo("Next reply"));
            Assert.That(mind.IsReady, Is.True);
            Assert.That(mind.HasActiveRequest, Is.False);
        });
    }

    [Test]
    public async Task ProgressFromARetiredRequestCannotReachTheCurrentTurn()
    {
        using var environment = new EnvironmentVariableScope(MindEnvironmentVariables);
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable, FindPython());
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable,
            Path.Combine(FindRepositoryRoot(), "tests", "fixtures", "mind_turn_contract"));
        await using var mind = new MindSidecarClient();
        Assert.That(await mind.TryStartAsync([], TimeSpan.FromSeconds(10), CancellationToken.None), Is.True);
        var signals = new System.Collections.Concurrent.ConcurrentQueue<string>();
        mind.TurnSignalReceived += signals.Enqueue;

        MindComposedMessage? result = await mind.ComposeUserMessageAsync("current", "conversation",
            new JsonObject { ["situation"] = "Current reply", ["fixtureTurnSignals"] = true },
            TimeSpan.FromSeconds(2), CancellationToken.None);

        Assert.That(result?.Text, Is.EqualTo("Current reply"));
        Assert.That(signals, Has.Count.EqualTo(1));
        Assert.That(signals, Does.Not.Contain("retired-request"));
    }

    [Test]
    public async Task CancellingAQueuedCompositionDoesNotInvalidateTheActiveRequest()
    {
        using var environment = new EnvironmentVariableScope(MindEnvironmentVariables);
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable, FindPython());
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable,
            Path.Combine(FindRepositoryRoot(), "tests", "fixtures", "mind_turn_contract"));
        await using var mind = new MindSidecarClient();
        Assert.That(await mind.TryStartAsync([], TimeSpan.FromSeconds(10), CancellationToken.None), Is.True);
        Task<MindComposedMessage?> slow = mind.ComposeUserMessageAsync("slow", "conversation",
            new JsonObject { ["situation"] = "First reply", ["fixtureDelayMilliseconds"] = 800 },
            TimeSpan.FromSeconds(3), CancellationToken.None);
        using var cancellation = new CancellationTokenSource();
        Task<MindComposedMessage?> queued = mind.ComposeUserMessageAsync("next", "conversation",
            new JsonObject(), TimeSpan.FromMilliseconds(400), cancellation.Token);
        await cancellation.CancelAsync();
        Assert.That(async () => await queued, Throws.InstanceOf<OperationCanceledException>());
        Assert.That((await slow)?.Text, Is.EqualTo("First reply"));
        Assert.That(mind.IsReady, Is.True);
    }

    [Test]
    public async Task ContextualConversationAndClarificationCrossTheMindProcessBoundary()
    {
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            // Con la composición puenteada se publica el borrador de hechos:
            // C03 retiró las frases fijas de TurnVisibleFacts.
            Assert.That(
                await SubmitAsync(viewModel, "Hola"),
                Does.Contain("\"kind\":\"welcome\""));
            Assert.That(
                await SubmitAsync(viewModel, "Explícame la fotosíntesis"),
                Does.Contain("convierte luz"));
            Assert.That(
                await SubmitAsync(viewModel, "¿Por qué?"),
                Does.Contain("clorofila"));
            Assert.That(
                await SubmitAsync(viewModel, "¿Qué?"),
                Is.EqualTo("En simple: la planta usa la luz como fuente de energía."));
            Assert.That(
                await SubmitAsync(viewModel, "Haz eso"),
                Is.EqualTo("¿Qué acción concreta quieres que haga?"));

            JsonElement[] trace = ReadTrace(tracePath);
            JsonElement[] turns = trace
                .Where(static entry => Property(entry, "type") == "turn.decide")
                .ToArray();
            Assert.Multiple(() =>
            {
                // «Hola» se reconoce como saludo en el shell y no gasta turno.
                Assert.That(turns, Has.Length.EqualTo(4));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") is "arguments" or "plan"));
            });

            AssertHistoryContainsAssistant(
                turns.Single(static entry => Property(entry, "text") == "¿Por qué?"),
                "convierte luz");
            AssertHistoryContainsAssistant(
                turns.Single(static entry => Property(entry, "text") == "¿Qué?"),
                "clorofila");
            AssertHistoryContainsUser(
                turns.Single(static entry => Property(entry, "text") == "Haz eso"),
                "Explícame la fotosíntesis");
        });
    }

    [Test]
    public async Task PriorUserFactCrossesTheMindBoundaryAndIsUsedForRecall()
    {
        const string nonce = "Nimbo7391";
        const string introduction =
            "Presento una palabra temporal: " + nonce + ".";
        const string recall = "¿Qué palabra temporal presenté?";

        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            string acknowledgement = await SubmitAsync(viewModel, introduction);
            string answer = await SubmitAsync(viewModel, recall);

            JsonElement[] trace = ReadTrace(tracePath);
            JsonElement recallTurn = trace.Single(entry =>
                Property(entry, "type") == "turn.decide"
                && Property(entry, "text") == recall);
            JsonElement[] history = recallTurn.GetProperty("history")
                .EnumerateArray()
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(acknowledgement, Does.Not.Contain(nonce));
                Assert.That(answer, Does.Contain(nonce));
                Assert.That(
                    history,
                    Has.Some.Matches<JsonElement>(entry =>
                        Property(entry, "role") == "user"
                        && Property(entry, "content") == introduction));
                Assert.That(
                    history,
                    Has.Some.Matches<JsonElement>(entry =>
                        Property(entry, "role") == "assistant"
                        && Property(entry, "content") == acknowledgement));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") is "arguments" or "plan"));
            });
        });
    }

    [Test]
    public async Task PendingClarificationDoesNotErasePriorUserFacts()
    {
        const string nonce = "Nimbo7391";
        const string introduction = "Presento una palabra temporal: " + nonce + ".";
        const string recall = "¿Qué palabra temporal presenté?";
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            await SubmitAsync(viewModel, introduction);
            await SubmitAsync(viewModel, "Haz eso");
            Assert.That(viewModel.StatusDescription, Is.EqualTo("Esperando tu aclaración"));

            string answer = await SubmitAsync(viewModel, recall);
            JsonElement decision = ReadTrace(tracePath).Single(entry =>
                Property(entry, "type") == "turn.decide"
                && Property(entry, "text") == recall);
            AssertHistoryContainsUser(decision, introduction);
            Assert.Multiple(() =>
            {
                Assert.That(answer, Does.Contain(nonce));
                Assert.That(decision.GetProperty("pendingClarification").GetBoolean(), Is.False);
                Assert.That(ReadTrace(tracePath), Has.None.Matches<JsonElement>(static entry =>
                    Property(entry, "type") is "arguments" or "plan"));
            });
            Assert.That(File.Exists(Path.Combine(dataRoot, "shell", "retry-outbox.v1.json")), Is.False);
        });
    }

    [Test]
    public async Task SelfContainedOrdersSupersedePendingTurnClarification()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            Assert.That(
                await SubmitAsync(viewModel, "Haz eso"),
                Is.EqualTo("¿Qué acción concreta quieres que haga?"));
            Assert.That(
                viewModel.StatusDescription,
                Is.EqualTo("Esperando tu aclaración"));
            string time = await SubmitAsync(viewModel, "Dime la hora actual");
            string plan = await SubmitAsync(
                viewModel,
                "Dime la hora y revisa la CPU");

            JsonElement[] trace = ReadTrace(tracePath);
            JsonElement[] turns = trace
                .Where(static entry => Property(entry, "type") == "turn.decide")
                .ToArray();
            Assert.Multiple(() =>
            {
                // La hora se encamina de forma determinista y no gasta turno.
                Assert.That(turns, Has.Length.EqualTo(2));
                Assert.That(time, Does.Contain("system.time"));
                Assert.That(time, Does.Contain("\"polarity\":\"success\""));
                Assert.That(plan, Does.Contain("mission_completed"));
                Assert.That(plan, Does.Contain("system.status"));
                Assert.That(
                    turns.Select(static entry => Property(entry, "text")),
                    Is.EqualTo(new[]
                    {
                        "Haz eso",
                        "Dime la hora y revisa la CPU",
                    }));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") == "turn.decide"
                        && Property(entry, "text")?.Contains(
                                "Aclaración confiable del usuario",
                                StringComparison.Ordinal) == true));
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    [TestCase("What name have you saved in private memory?", "memory.recall")]
    [TestCase("¿Qué nombre tienes guardado en tu memoria privada?", "memory.recall")]
    [TestCase("do you have memory", "memory.status")]
    [TestCase("tienes memoria", "memory.status")]
    public async Task ExplicitPrivateMemoryRequestSupersedesMindClarification(
        string request, string operation)
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            _ = await SubmitAsync(viewModel, "Haz eso");
            Assert.That(viewModel.StatusDescription, Is.EqualTo("Esperando tu aclaración"));
            string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
            long before = new FileInfo(journalPath).Length;
            int decisionsBefore = ReadTrace(tracePath).Count(entry => Property(entry, "type") == "turn.decide");

            string result = await SubmitAsync(viewModel, request);
            using var journal = new FileStream(journalPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            using var reader = new StreamReader(journal);
            string persisted = await reader.ReadToEndAsync();

            Assert.Multiple(() =>
            {
                Assert.That(ReadTrace(tracePath).Count(entry => Property(entry, "type") == "turn.decide"),
                    Is.EqualTo(decisionsBefore), "The typed private route must not be reclassified as a public slot reply.");
                Assert.That(new FileInfo(journalPath).Length, Is.GreaterThan(before));
                Assert.That(persisted, Does.Contain(operation));
                if (operation == "memory.recall")
                {
                    Assert.That(result, Does.Contain("memory_disabled"));
                }
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    [TestCase("Recuerda mi nombre")]
    [TestCase("I want you to save my name")]
    public async Task PrivateMissingValueReplacesPublicClarificationWithoutInventingIt(string request)
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            _ = await SubmitAsync(viewModel, "Haz eso");
            string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
            long before = new FileInfo(journalPath).Length;
            int decisionsBefore = ReadTrace(tracePath).Count(entry => Property(entry, "type") == "turn.decide");

            string question = await SubmitAsync(viewModel, request);
            string cancellation = await SubmitAsync(viewModel, "cancelar");

            Assert.Multiple(() =>
            {
                Assert.That(question, Does.Contain("memory_save_needs_content"));
                Assert.That(cancellation, Does.Contain("memory_cancelled"));
                Assert.That(new FileInfo(journalPath).Length, Is.EqualTo(before));
                Assert.That(ReadTrace(tracePath).Count(entry => Property(entry, "type") == "turn.decide"),
                    Is.EqualTo(decisionsBefore));
            });
            Assert.That(File.Exists(Path.Combine(dataRoot, "shell", "retry-outbox.v1.json")), Is.False);
        });
    }

    [Test]
    public async Task ClarificationFragmentPreservesAndResumesTheObjective()
    {
        const string clarifiedObjective =
            "Haz eso\nAclaración confiable del usuario: mañana a las 9";

        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            Assert.That(
                await SubmitAsync(viewModel, "Haz eso"),
                Is.EqualTo("¿Qué acción concreta quieres que haga?"));
            Assert.That(
                await SubmitAsync(viewModel, "mañana a las 9"),
                Is.EqualTo("¿Puedes concretar lo que necesitas?"));
            Assert.That(
                viewModel.StatusDescription,
                Is.EqualTo("Esperando tu aclaración"));

            JsonElement[] turns = ReadTrace(tracePath)
                .Where(static entry => Property(entry, "type") == "turn.decide")
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(turns, Has.Length.EqualTo(3));
                Assert.That(
                    turns.Select(static entry => Property(entry, "text")),
                    Is.EqualTo(new[]
                    {
                        "Haz eso",
                        "mañana a las 9",
                        clarifiedObjective,
                    }));
                // Context is preserved while the first reading remains
                // independent of pending-objective authorization.
                AssertHistoryContainsUser(turns[1], "Haz eso");
                Assert.That(turns[1].GetProperty("pendingClarification").GetBoolean(), Is.False);
            });
        });
    }

    [TestCase("Set the volume, por favor.")]
    [TestCase("Ajusta el volumen, por favor.")]
    [TestCase("Set the speaker volume, please.")]
    public async Task RejectedClarificationWordingKeepsThePendingObjective(string request)
    {
        const string question = "¿Quieres que ajuste el volumen de la salida a un nivel específico?";
        Assert.That(UserMessagePolicy.IsSafeConversationReply(request, question, "mixed"), Is.False);
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            string first = await SubmitAsync(viewModel, request);
            Assert.That(viewModel.StatusDescription, Is.EqualTo("Esperando tu aclaración"),
                first + " | " + string.Join(" | ", ReadTrace(tracePath)
                    .Select(static entry => Property(entry, "type") + ":" + Property(entry, "text"))));
            await SubmitAsync(viewModel, "Al 40%, please.");
            string?[] requests = ReadTrace(tracePath)
                .Where(static entry => Property(entry, "type") == "turn.decide")
                .Select(static entry => Property(entry, "text"))
                .ToArray();
            Assert.That(requests, Does.Contain(
                request + "\nAclaración confiable del usuario: Al 40%, please."));
        });
    }

    [Test]
    public async Task SafeArgumentFreeClockRequestReachesTheRealCoreWithoutATurn()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string answer = await SubmitAsync(viewModel, "Dime la hora actual");

            JsonElement[] trace = ReadTrace(tracePath);
            Assert.Multiple(() =>
            {
                // La hora tiene encaminamiento determinista: no pide decisión
                // al modelo y aun así pasa por el Core real.
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") == "turn.decide"
                        && Property(entry, "text") == "Dime la hora actual"));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") == "arguments"));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") == "plan"));
                Assert.That(answer, Does.Contain("system.time"));
                Assert.That(answer, Does.Contain("\"polarity\":\"success\""));
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    [TestCase("y la fecha?")]
    [TestCase("and the date?")]
    public async Task GroundedContextualDateReachesCoreOutsideTheClockFastPath(string request)
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            await SubmitAsync(viewModel, "Dime la hora actual");
            string answer = await SubmitAsync(viewModel, request);
            JsonElement decision = ReadTrace(tracePath).Single(entry =>
                Property(entry, "type") == "turn.decide"
                && Property(entry, "text") == request);
            AssertHistoryContainsUser(decision, "Dime la hora actual");
            Assert.Multiple(() =>
            {
                Assert.That(answer, Does.Contain("system.time"));
                Assert.That(answer, Does.Contain("\"polarity\":\"success\""));
                Assert.That(answer, Does.Contain("localUtcOffsetMinutes"));
                Assert.That(answer, Does.Contain("utc"));
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    // D3 (DECISIONES_DUENO_2026-09-20.md): navigating no longer asks; the Core
    // confirmation mechanics are exercised on a work_loss operation whose target
    // process does not exist, so a confirmation would change nothing.
    [Test]
    public async Task SimpleMindActionPreservesCoreConfirmationInsteadOfClaimingSuccess()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string prompt = await SubmitAsync(
                viewModel,
                "Terminá el proceso baxy-proceso-inexistente");

            JsonElement[] trace = ReadTrace(tracePath);
            Assert.Multiple(() =>
            {
                Assert.That(prompt, Does.Contain("confirmation"));
                Assert.That(prompt, Does.Contain("confirmar"));
                Assert.That(prompt, Does.Contain("cancelar"));
                Assert.That(prompt, Does.Not.Contain("Terminé"));
                Assert.That(
                    trace.Count(static entry =>
                        Property(entry, "type") == "arguments"
                        && Property(entry, "operation")
                            == "system.process.terminate.named"),
                    Is.EqualTo(1));
                Assert.That(
                    new DurableRetryStore(
                        Path.Combine(dataRoot, "shell", "retry-outbox.v1.json"))
                        .Load(),
                    Has.Count.EqualTo(1));
            });

            string cancelled = await SubmitAsync(viewModel, "cancelar");
            Assert.That(cancelled, Does.Contain("cancel").IgnoreCase);
            AssertOutboxEmpty(dataRoot);
        });
    }

    [TestCase("What is in my task list?", "task.list")]
    [TestCase("Dime la hora y revisa la CPU", "mission_completed")]
    [TestCase("Dime la hora actual", "system.time")]
    [TestCase("and the date?", "system.time")]
    [TestCase("Explícame la fotosíntesis", "fotosíntesis")]
    [TestCase("What name have you saved in private memory?", "memory_disabled")]
    [TestCase("¿Qué nombre tienes guardado en tu memoria privada?", "memory_disabled")]
    public async Task IndependentRequestSupersedesUnstartedConfirmationWithoutReclassifying(
        string request, string expected)
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            _ = await SubmitAsync(viewModel, "Terminá el proceso baxy-proceso-inexistente");
            Assert.That(viewModel.HasPendingPlan, Is.True);
            string answer = await SubmitAsync(viewModel, request);
            Assert.Multiple(() =>
            {
                Assert.That(answer, Does.Contain(expected));
                Assert.That(viewModel.HasPendingPlan, Is.False);
                Assert.That(ReadTrace(tracePath).Count(entry =>
                    Property(entry, "type") == "turn.decide"
                    && Property(entry, "text") == request), Is.LessThanOrEqualTo(1),
                    "The independent decision must be reused, not sent to the model twice.");
                Assert.That(ReadTrace(tracePath).Count(entry =>
                    Property(entry, "type") == "arguments"
                    && Property(entry, "operation") == "system.process.terminate.named"), Is.EqualTo(1),
                    "The old action must not be prepared or resumed again.");
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    [TestCase("mañana a las 9")]
    [TestCase("Opera")]
    [TestCase("la segunda")]
    [TestCase("tal vez")]
    public async Task SlotOrUncertainReplyRetainsTheExactPendingConfirmation(string fragment)
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            _ = await SubmitAsync(viewModel, "Terminá el proceso baxy-proceso-inexistente");
            string outbox = Path.Combine(dataRoot, "shell", "retry-outbox.v1.json");
            byte[] before = File.ReadAllBytes(outbox);
            string answer = await SubmitAsync(viewModel, fragment);
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.HasPendingPlan, Is.True);
                Assert.That(answer, Does.Contain("confirmation"));
                Assert.That(File.ReadAllBytes(outbox), Is.EqualTo(before),
                    "A fragment cannot replace the invocation or its durable retry identity.");
                Assert.That(ReadTrace(tracePath).Count(entry =>
                    Property(entry, "type") == "arguments"), Is.EqualTo(1));
            });
            _ = await SubmitAsync(viewModel, "cancelar");
            AssertOutboxEmpty(dataRoot);
        });
    }

    [Test]
    public async Task ReplacementRequestGetsItsOwnConfirmationInsteadOfReusingTheOldOne()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            const string request = "Terminá el proceso baxy-proceso-inexistente";
            _ = await SubmitAsync(viewModel, request);
            string outbox = Path.Combine(dataRoot, "shell", "retry-outbox.v1.json");
            PreparedOperation before = new DurableRetryStore(outbox).Load().Single();
            string answer = await SubmitAsync(viewModel, request);
            PreparedOperation after = new DurableRetryStore(outbox).Load().Single();
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.HasPendingPlan, Is.True);
                Assert.That(answer, Does.Contain("confirmation"));
                Assert.That(after.InvocationId, Is.Not.EqualTo(before.InvocationId));
                Assert.That(after.MissionId, Is.Not.EqualTo(before.MissionId));
                Assert.That(new DurableRetryStore(outbox).Load(), Has.Count.EqualTo(1));
                Assert.That(ReadTrace(tracePath).Count(entry =>
                    Property(entry, "type") == "turn.decide"
                    && Property(entry, "text") == request), Is.EqualTo(2));
            });
            _ = await SubmitAsync(viewModel, "cancelar");
            AssertOutboxEmpty(dataRoot);
        });
    }

    [Test]
    public async Task ReadOnlyCompositePlanTraversesPlannerAndRealCoreWithoutEffects()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string answer = await SubmitAsync(
                viewModel,
                "Dime la hora y revisa la CPU");

            JsonElement[] trace = ReadTrace(tracePath);
            JsonElement planRequest = trace.Single(static entry =>
                Property(entry, "type") == "plan");
            Assert.Multiple(() =>
            {
                Assert.That(
                    trace.Count(static entry => Property(entry, "type") == "turn.decide"),
                    Is.EqualTo(1));
                Assert.That(
                    trace.Count(static entry => Property(entry, "type") == "plan"),
                    Is.EqualTo(1));
                Assert.That(
                    planRequest.GetProperty("expectedOperations")
                        .EnumerateArray()
                        .Select(static value => value.GetString()),
                    Is.EqualTo(new[] { "system.time", "system.status" }));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") == "arguments"));
                Assert.That(answer, Does.Contain("mission_completed"));
                Assert.That(answer, Does.Contain("system.time"));
                Assert.That(answer, Does.Contain("system.status"));
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    [Test]
    public async Task GenericPlanWithoutPreservedEffectsStillReachesPlanner()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string answer = await SubmitAsync(
                viewModel,
                "Revisa el estado general");

            JsonElement[] trace = ReadTrace(tracePath);
            JsonElement planRequest = trace.Single(static entry =>
                Property(entry, "type") == "plan");
            Assert.Multiple(() =>
            {
                Assert.That(
                    planRequest.TryGetProperty(
                        "expectedOperations",
                        out _),
                    Is.False);
                Assert.That(answer, Does.Contain("mission_completed"));
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    [Test]
    [Explicit("Real-runtime read-only shell/Core proof; execute through run_mind_shell_e2e_gate.ps1.")]
    [Category("PhysicalMindShellGate")]
    public async Task OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations()
    {
        string dataRoot = PrivateDataRootTestSupport.NewPath("mind-shell-physical");
        string attestationPath =
            Environment.GetEnvironmentVariable(PhysicalAttestationEnvironmentVariable)
            ?? string.Empty;
        string shellTracePath = Path.Combine(dataRoot, "model-authored-visible-path.jsonl");
        bool previousCompositionBypass = UserMessagePolicy.BypassLlmCompositionForTests;
        using var environment = new EnvironmentVariableScope(MindEnvironmentVariables);
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", dataRoot);
        Environment.SetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START", "0");
        Directory.CreateDirectory(dataRoot);

        try
        {
            UserMessagePolicy.BypassLlmCompositionForTests = false;
            Assert.That(
                Path.IsPathFullyQualified(attestationPath),
                Is.True,
                $"{PhysicalAttestationEnvironmentVariable} must be an absolute gate-owned path.");
            Assert.Multiple(() =>
            {
                Assert.That(MindSidecarClient.IsConfigured, Is.True);
                Assert.That(
                    File.Exists(Environment.GetEnvironmentVariable(
                        MindSidecarClient.PythonEnvironmentVariable)),
                    Is.True);
                Assert.That(
                    File.Exists(Environment.GetEnvironmentVariable(
                        "BAXY_MIND_LLM_GGUF")),
                    Is.True);
            });

            try
            {
                using (ShellTrace? shellTrace = ShellTrace.TryCreate(shellTracePath))
                using (IDisposable shellTraceScope = ShellTraceSink.Use(
                           shellTrace
                           ?? throw new InvalidOperationException(
                               "The gate could not create its owned shell trace.")))
                await using (var viewModel = new MainWindowViewModel())
                {
                    // The CPU fallback preserves the exact same battery and
                    // assertions, but measured local generations can exceed
                    // 20 s. Its wall-clock gate budget must not cancel a valid
                    // in-flight turn merely because accelerated decode is off.
                    using var timeout = new CancellationTokenSource(
                        MindSidecarClient.IsCpuFallbackProfile
                            ? TimeSpan.FromMinutes(20)
                            : TimeSpan.FromMinutes(5));
                    await viewModel.InitializeAsync(timeout.Token);
                    await WaitForMindAsync(viewModel, timeout.Token);

                    string nonce = string.Concat(
                        "Nimbo",
                        RandomNumberGenerator.GetInt32(1000, 10_000));
                    string greeting = await SubmitAsync(viewModel, "Hola", timeout.Token);
                    string knowledge = await SubmitAsync(
                        viewModel,
                        "Explícame brevemente la fotosíntesis",
                        timeout.Token);
                    string why = await SubmitAsync(viewModel, "¿Por qué?", timeout.Token);
                    string what = await SubmitAsync(viewModel, "¿Qué?", timeout.Token);
                    string nonceIntroduction = await SubmitAsync(
                        viewModel,
                        $"Explica en una frase por qué la palabra inventada «{nonce}» suena amistosa.",
                        timeout.Token);
                    string nonceRecall = await SubmitAsync(
                        viewModel,
                        "¿Qué palabra inventada mencioné en mi pregunta anterior?",
                        timeout.Token);
                    string clarification = await SubmitAsync(viewModel, "Haz eso", timeout.Token);
                    string time = await SubmitAsync(viewModel, "Dime la hora actual", timeout.Token);
                    string plan = await SubmitAsync(
                        viewModel,
                        "Dime la hora y revisa la CPU",
                        timeout.Token);
                    string threeStepPlan = await SubmitAsync(
                        viewModel,
                        "Dime la hora, revisa el estado del equipo y lista los procesos activos.",
                        timeout.Token);
                    string maximumReadOnlyPlan = await SubmitAsync(
                        viewModel,
                        "Dime la hora; lista las tareas; lista las notas; lista los procesos activos; "
                            + "dime la hora; lista las tareas; lista las notas; lista los procesos activos.",
                        timeout.Token);

                    Assert.Multiple(() =>
                    {
                        AssertNaturalMindReply(greeting);
                        AssertNaturalMindReply(knowledge);
                        AssertNaturalMindReply(why);
                        AssertNaturalMindReply(what);
                        AssertNaturalMindReply(nonceIntroduction);
                        AssertNaturalMindReply(nonceRecall);
                        Assert.That(
                            nonceRecall,
                            Does.Contain(nonce).IgnoreCase,
                            "The real model did not recover the per-run nonce from conversation history.");
                        AssertNaturalMindReply(clarification);
                        Assert.That(clarification, Does.Contain("?").Or.Contain("¿"));
                        AssertNaturalMindReply(time);
                        Assert.That(time, Does.Match(@"\d"));
                        AssertNaturalMindReply(plan);
                        Assert.That(plan, Does.Contain("CPU"));
                        AssertNaturalMindReply(threeStepPlan);
                        AssertNaturalMindReply(maximumReadOnlyPlan);
                        Assert.That(maximumReadOnlyPlan, Does.Contain("8"));
                    });
                    AssertOutboxEmpty(dataRoot);
                }

                JsonElement[] visibleTrace = ReadTrace(shellTracePath);
                JsonElement[] compositionStarts = visibleTrace
                    .Where(static entry =>
                        Property(entry, "stage") == ShellTraceStages.ComposeStart)
                    .ToArray();
                JsonElement[] compositionEnds = visibleTrace
                    .Where(static entry =>
                        Property(entry, "stage") == ShellTraceStages.ComposeEnd)
                    .ToArray();
                Assert.Multiple(() =>
                {
                    Assert.That(
                        compositionStarts,
                        Has.Length.GreaterThanOrEqualTo(4),
                        "The time and all three composite-plan responses did not enter message.compose.");
                    Assert.That(
                        compositionEnds,
                        Has.Length.EqualTo(compositionStarts.Length));
                    Assert.That(
                        compositionStarts.All(start => compositionEnds.Any(end =>
                            string.Equals(
                                Property(end, "id"),
                                Property(start, "id"),
                                StringComparison.Ordinal)
                            && end.GetProperty("seq").GetInt64()
                                > start.GetProperty("seq").GetInt64())),
                        Is.True,
                        "A model composition did not reach its bounded completion boundary.");
                });
                TestContext.Progress.WriteLine(
                    $"Model-authored visible responses: composeStart={compositionStarts.Length}, composeEnd={compositionEnds.Length}, traceSha256={Sha256(shellTracePath)}.");
            }
            finally
            {
                string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
                if (File.Exists(journalPath)
                    && File.Exists(string.Concat(journalPath, ".anchor")))
                {
                    await WriteAuthenticatedCoreAttestationAsync(
                        dataRoot,
                        attestationPath,
                        CancellationToken.None);
                }
            }
        }
        finally
        {
            UserMessagePolicy.BypassLlmCompositionForTests = previousCompositionBypass;
            DeleteOwnedDataRoot(dataRoot);
        }
    }

    private static async Task WithContractMindAsync(
        Func<MainWindowViewModel, string, string, Task> body)
    {
        string repositoryRoot = FindRepositoryRoot();
        string fixtureRoot = Path.Combine(
            repositoryRoot,
            "tests",
            "fixtures",
            "mind_turn_contract");
        string python = FindPython();
        string dataRoot = PrivateDataRootTestSupport.NewPath("mind-shell-contract");
        string tracePath = Path.Combine(dataRoot, "mind-contract-trace.jsonl");
        using var environment = new EnvironmentVariableScope(MindEnvironmentVariables);
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", dataRoot);
        Environment.SetEnvironmentVariable(
            MindSidecarClient.PythonEnvironmentVariable,
            python);
        Environment.SetEnvironmentVariable(
            MindSidecarClient.PythonPathEnvironmentVariable,
            fixtureRoot);
        Environment.SetEnvironmentVariable(
            ContractTraceEnvironmentVariable,
            tracePath);
        Environment.SetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START", "0");
        Directory.CreateDirectory(dataRoot);

        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True);
                Assert.That(viewModel.HasStartupError, Is.False);
            });
            await body(viewModel, dataRoot, tracePath);
        }
        finally
        {
            DeleteOwnedDataRoot(dataRoot);
        }
    }

    private static async Task<string> SubmitAsync(
        MainWindowViewModel viewModel,
        string text,
        CancellationToken cancellationToken = default)
    {
        int previousCount = viewModel.Messages.Count;
        viewModel.Draft = text;
        await viewModel.SubmitAsync(cancellationToken);
        ConversationMessage[] added = viewModel.Messages.Skip(previousCount).ToArray();
        string diagnostic = string.Concat(
            text,
            "; composition_failure=",
            viewModel.LastMessageCompositionFailure ?? "none",
            "; status=",
            viewModel.StatusDescription);
        Assert.Multiple(() =>
        {
            Assert.That(added, Has.Length.GreaterThanOrEqualTo(2), diagnostic);
            Assert.That(added[0].IsUser, Is.True, diagnostic);
            Assert.That(added[0].Body, Is.EqualTo(text), diagnostic);
            Assert.That(added[^1].IsUser, Is.False, diagnostic);
            Assert.That(added[^1].Speaker, Is.EqualTo("BAXY"), diagnostic);
        });
        return added[^1].Body;
    }

    private static async Task WaitForMindAsync(
        MainWindowViewModel viewModel,
        CancellationToken cancellationToken)
    {
        FieldInfo mindField = typeof(MainWindowViewModel).GetField(
            "_mindClient",
            BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(
                typeof(MainWindowViewModel).FullName,
                "_mindClient");
        while (mindField.GetValue(viewModel) is not MindSidecarClient { IsReady: true })
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (viewModel.HasStartupError)
            {
                Assert.Fail("The shell reported a startup error before the mind became ready.");
            }

            await Task.Delay(TimeSpan.FromMilliseconds(100), cancellationToken);
        }
    }

    private static void AssertNaturalMindReply(string reply)
    {
        Assert.Multiple(() =>
        {
            Assert.That(reply, Is.Not.Empty);
            Assert.That(reply, Does.Not.Contain("turn.result"));
            Assert.That(reply, Does.Not.Contain("No pude interpretar esa petición"));
            Assert.That(reply, Does.Not.Contain("inteligencia local no está disponible"));
        });
    }

    private static JsonElement[] ReadTrace(string path)
    {
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream);
        var rows = new List<JsonElement>();
        while (reader.ReadLine() is { } line)
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            rows.Add(JsonDocument.Parse(line).RootElement.Clone());
        }

        return [.. rows];
    }

    private static string? Property(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static void AssertHistoryContainsAssistant(
        JsonElement request,
        string expectedFragment)
    {
        Assert.That(
            request.GetProperty("history")
                .EnumerateArray()
                .Any(turn =>
                    Property(turn, "role") == "assistant"
                    && (Property(turn, "content") ?? string.Empty).Contains(
                        expectedFragment,
                        StringComparison.Ordinal)),
            Is.True,
            $"The contextual request did not carry assistant history containing '{expectedFragment}'.");
    }

    private static void AssertHistoryContainsUser(
        JsonElement request,
        string expectedFragment)
    {
        Assert.That(
            request.GetProperty("history")
                .EnumerateArray()
                .Any(turn =>
                    Property(turn, "role") == "user"
                    && (Property(turn, "content") ?? string.Empty).Contains(
                        expectedFragment,
                        StringComparison.Ordinal)),
            Is.True,
            $"The contextual request did not carry user history containing '{expectedFragment}'.");
    }

    private static void AssertOutboxEmpty(string dataRoot)
    {
        string path = Path.Combine(dataRoot, "shell", "retry-outbox.v1.json");
        using JsonDocument outbox = JsonDocument.Parse(File.ReadAllText(path));
        Assert.That(
            outbox.RootElement.GetProperty("entries").GetArrayLength(),
            Is.Zero);
    }

    private static async Task WriteAuthenticatedCoreAttestationAsync(
        string dataRoot,
        string attestationPath,
        CancellationToken cancellationToken)
    {
        string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
        string anchorPath = string.Concat(journalPath, ".anchor");
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(journalPath), Is.True);
            Assert.That(File.Exists(anchorPath), Is.True);
        });

        await using (FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                         journalPath,
                         CreateJournalAuthenticator(dataRoot, journalPath),
                         cancellationToken))
        {
            // Opening the journal validates the authenticated hash chain and
            // its durable tail anchor. No result is trusted before this point.
        }

        JsonElement[] envelopes = File.ReadLines(journalPath)
            .Where(static line => !string.IsNullOrWhiteSpace(line))
            .Select(static line => JsonDocument.Parse(line).RootElement.Clone())
            .ToArray();
        JsonElement[] payloads = envelopes
            .Select(static envelope => envelope.GetProperty("payload"))
            .ToArray();
        JsonElement[] started = payloads
            .Where(static payload =>
                Property(payload, "phase") == "started")
            .ToArray();
        JsonElement[] completed = payloads
            .Where(static payload =>
                Property(payload, "phase") is "completed" or "retained_completed")
            .ToArray();

        string[] expectedOperations =
        [
            "memory.status",
            "system.time",
            "system.time",
            "system.status",
            "system.time",
            "system.status",
            "system.process.list",
            "system.time",
            "task.list",
            "note.list",
            "system.process.list",
            "system.time",
            "task.list",
            "note.list",
            "system.process.list",
        ];
        string[] observedOperations = completed
            .Select(static payload => Property(payload, "operation") ?? string.Empty)
            .Order(StringComparer.Ordinal)
            .ToArray();
        string[] startedOperations = started
            .Select(static payload => Property(payload, "operation") ?? string.Empty)
            .Order(StringComparer.Ordinal)
            .ToArray();
        string[] expectedSorted = expectedOperations
            .Order(StringComparer.Ordinal)
            .ToArray();
        string[] startedInvocations = started
            .Select(static payload => Property(payload, "invocationId") ?? string.Empty)
            .Order(StringComparer.Ordinal)
            .ToArray();
        string[] completedInvocations = completed
            .Select(static payload => Property(payload, "invocationId") ?? string.Empty)
            .Order(StringComparer.Ordinal)
            .ToArray();
        string[] distinctStartedInvocations = startedInvocations
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        string[] distinctCompletedInvocations = completedInvocations
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        bool invocationPairsValid =
            startedInvocations.All(static invocation =>
                !string.IsNullOrWhiteSpace(invocation))
            && completedInvocations.All(static invocation =>
                !string.IsNullOrWhiteSpace(invocation))
            && distinctStartedInvocations.Length == startedInvocations.Length
            && distinctCompletedInvocations.Length == completedInvocations.Length
            && completedInvocations.SequenceEqual(
                startedInvocations,
                StringComparer.Ordinal);
        bool startedOperationsMatchCompleted = invocationPairsValid
            && completed.All(completedPayload =>
            {
                string? invocationId = Property(completedPayload, "invocationId");
                string? operation = Property(completedPayload, "operation");
                return started.Any(startedPayload =>
                    string.Equals(
                        Property(startedPayload, "invocationId"),
                        invocationId,
                        StringComparison.Ordinal)
                    && string.Equals(
                        Property(startedPayload, "operation"),
                        operation,
                        StringComparison.Ordinal));
            });
        bool knownPhasesOnly =
            payloads.Length == started.Length + completed.Length;

        var completions = completed
            .OrderBy(static payload => payload.GetProperty("sequence").GetInt64())
            .Select(static payload =>
            {
                JsonElement response = payload.GetProperty("response");
                return new
                {
                    sequence = payload.GetProperty("sequence").GetInt64(),
                    operation = Property(payload, "operation"),
                    status = Property(response, "status"),
                    verified = response.GetProperty("verified").GetBoolean(),
                    replayed = response.GetProperty("replayed").GetBoolean(),
                    effect_may_have_occurred =
                        response.TryGetProperty("effectMayHaveOccurred", out JsonElement effect)
                        && effect.GetBoolean(),
                };
            })
            .ToArray();
        var attestation = new
        {
            schema = "baxy-mind-shell-core-attestation-v1",
            journal_integrity_validated = true,
            journal_authentication = JournalHmacAuthenticator.Algorithm,
            journal_sha256 = Sha256(journalPath),
            anchor_sha256 = Sha256(anchorPath),
            journal_records = envelopes.Length,
            started_records = started.Length,
            completed_records = completed.Length,
            journal_structure_valid =
                knownPhasesOnly
                && invocationPairsValid
                && startedOperationsMatchCompleted,
            invocation_pairs_valid = invocationPairsValid,
            started_operations_match_completed = startedOperationsMatchCompleted,
            expected_read_only_operations_observed =
                startedOperations.SequenceEqual(expectedSorted, StringComparer.Ordinal)
                && observedOperations.SequenceEqual(expectedSorted, StringComparer.Ordinal),
            operation_counts = new
            {
                memory_status = completed.Count(static payload =>
                    Property(payload, "operation") == "memory.status"),
                system_time = completed.Count(static payload =>
                    Property(payload, "operation") == "system.time"),
                system_status = completed.Count(static payload =>
                    Property(payload, "operation") == "system.status"),
                system_process_list = completed.Count(static payload =>
                    Property(payload, "operation") == "system.process.list"),
                task_list = completed.Count(static payload =>
                    Property(payload, "operation") == "task.list"),
                note_list = completed.Count(static payload =>
                    Property(payload, "operation") == "note.list"),
            },
            completions,
        };
        WriteJsonAtomic(attestationPath, attestation);
    }

    private static JournalHmacAuthenticator CreateJournalAuthenticator(
        string dataRoot,
        string journalPath)
    {
        var protectedPayload = new WindowsProtectedPayload(
            Path.Combine(dataRoot, "security", "private-payload.v1.key"));
        var keyStore = new WindowsJournalAuthenticationKeyStore(
            Path.Combine(dataRoot, "security", "journal-hmac.v2.key"),
            protectedPayload);
        byte[] key = keyStore.LoadOrCreate(
            allowCreate: !File.Exists(journalPath)
                && !File.Exists(string.Concat(journalPath, ".anchor")));
        try
        {
            return new JournalHmacAuthenticator(key);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(key);
        }
    }

    private static string Sha256(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path)))
            .ToLowerInvariant();

    private static void WriteJsonAtomic(string path, object value)
    {
        string fullPath = Path.GetFullPath(path);
        string directory = Path.GetDirectoryName(fullPath)
            ?? throw new InvalidOperationException("The attestation path has no parent.");
        Directory.CreateDirectory(directory);
        string temporaryPath = Path.Combine(
            directory,
            string.Concat(
                ".",
                Path.GetFileName(fullPath),
                ".",
                Guid.NewGuid().ToString("N"),
                ".tmp"));
        try
        {
            File.WriteAllText(
                temporaryPath,
                string.Concat(
                    JsonSerializer.Serialize(
                        value,
                        AttestationJsonOptions),
                    Environment.NewLine),
                new System.Text.UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            File.Move(temporaryPath, fullPath, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "global.json"))
                && Directory.Exists(Path.Combine(current.FullName, "src", "baxy_mind")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("Could not locate the BAXY repository root.");
    }

    private static string FindPython()
    {
        // The turn contract fixture under tests/fixtures is stdlib only, so any
        // Python 3 runs it. Look where Windows actually keeps one instead of at
        // a single fixed path that exists only on the machine that made it.
        foreach (string candidate in PythonCandidates())
        {
            if (File.Exists(candidate) && ReportsPython3(candidate))
            {
                return candidate;
            }
        }

        Assert.Ignore(
            "environment: no Python 3 interpreter is available (Windows launcher "
            + "or PATH), so the deterministic mind contract cannot run on this "
            + "machine. Missing prerequisite, not a regression.");
        throw new InvalidOperationException("Assert.Ignore did not end the test.");
    }

    private static IEnumerable<string> PythonCandidates()
    {
        yield return Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "py.exe");
        foreach (string directory in (Environment.GetEnvironmentVariable("PATH") ?? string.Empty)
            .Split(
                Path.PathSeparator,
                StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            yield return Path.Combine(directory, "python.exe");
        }
    }

    private static bool ReportsPython3(string executable)
    {
        // The Microsoft Store app alias sits on PATH by default and is not an
        // interpreter, so a candidate has to prove it runs before it is used.
        try
        {
            using Process? process = Process.Start(new ProcessStartInfo(executable)
            {
                Arguments = "-c \"import sys; print(sys.version_info.major)\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
            });
            if (process is null)
            {
                return false;
            }

            string reported = process.StandardOutput.ReadToEnd().Trim();
            return process.WaitForExit(10_000)
                && process.ExitCode == 0
                && reported == "3";
        }
        catch (Exception exception)
            when (exception is System.ComponentModel.Win32Exception or IOException)
        {
            return false;
        }
    }

    private static void DeleteOwnedDataRoot(string path)
    {
        string ownedParent = Path.GetFullPath(Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            "BAXY"));
        string fullPath = Path.GetFullPath(path);
        if (!fullPath.StartsWith(
                ownedParent.TrimEnd(Path.DirectorySeparatorChar)
                    + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Refusing to delete an unowned test data root.");
        }

        if (Directory.Exists(fullPath))
        {
            Directory.Delete(fullPath, recursive: true);
        }
    }

    private sealed class EnvironmentVariableScope : IDisposable
    {
        private readonly Dictionary<string, string?> _before;

        internal EnvironmentVariableScope(IEnumerable<string> names)
        {
            _before = names
                .Distinct(StringComparer.Ordinal)
                .ToDictionary(
                    static name => name,
                    static name => Environment.GetEnvironmentVariable(name),
                    StringComparer.Ordinal);
        }

        public void Dispose()
        {
            foreach ((string name, string? value) in _before)
            {
                Environment.SetEnvironmentVariable(name, value);
            }
        }
    }
}
