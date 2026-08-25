using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
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

    [Test]
    public async Task ContextualConversationAndClarificationCrossTheMindProcessBoundary()
    {
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            Assert.That(
                await SubmitAsync(viewModel, "Hola"),
                Is.EqualTo("¡Hola! Estoy aquí para ayudarte."));
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
                Assert.That(turns, Has.Length.EqualTo(5));
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
    public async Task UnavailableMindDecisionNeverClaimsThatTheRequestWasAmbiguous()
    {
        await WithContractMindAsync(async (viewModel, _, _) =>
        {
            string answer = await SubmitAsync(viewModel, "FORCE_DECISION_UNAVAILABLE");

            Assert.Multiple(() =>
            {
                Assert.That(answer, Does.Contain("compose_unavailable"));
                Assert.That(answer, Does.Not.Contain("ambiguous_request"));
            });
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
            JsonElement timeFacts = ParseFacts(time);
            JsonElement planFacts = ParseFacts(plan);
            string[] planSteps = planFacts.GetProperty("steps").EnumerateArray()
                .Select(static step => step.GetString() ?? string.Empty)
                .ToArray();

            JsonElement[] trace = ReadTrace(tracePath);
            JsonElement[] turns = trace
                .Where(static entry => Property(entry, "type") == "turn.decide")
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(turns, Has.Length.EqualTo(3));
                Assert.That(timeFacts.GetProperty("operation").GetString(), Is.EqualTo("system.time"));
                Assert.That(
                    timeFacts.GetProperty("observed").GetProperty("localTime").GetString(),
                    Is.Not.Empty);
                Assert.That(planFacts.GetProperty("cause").GetString(), Is.EqualTo("mission_completed"));
                Assert.That(planFacts.GetProperty("stepCount").GetInt32(), Is.EqualTo(2));
                Assert.That(planSteps, Has.Some.Contains("\"operation\":\"system.time\""));
                Assert.That(planSteps, Has.Some.Contains("\"operation\":\"system.status\""));
                Assert.That(
                    turns.Select(static entry => Property(entry, "text")),
                    Is.EqualTo(new[]
                    {
                        "Haz eso",
                        "Dime la hora actual",
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
                Assert.That(
                    turns[1].GetProperty("history").GetArrayLength(),
                    Is.EqualTo(0));
            });
        });
    }

    [Test]
    public async Task NewUiSessionDiscardsPendingTurnClarification()
    {
        await WithContractMindAsync(async (viewModel, _, tracePath) =>
        {
            Assert.That(
                await SubmitAsync(viewModel, "Haz eso"),
                Is.EqualTo("¿Qué acción concreta quieres que haga?"));
            Assert.That(viewModel.StartNewUiSession(), Is.True);
            Assert.That(
                await SubmitAsync(viewModel, "mañana a las 9"),
                Is.EqualTo("¿Puedes concretar lo que necesitas?"));

            JsonElement[] turns = ReadTrace(tracePath)
                .Where(static entry => Property(entry, "type") == "turn.decide")
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(turns, Has.Length.EqualTo(2));
                Assert.That(
                    turns.Select(static entry => Property(entry, "text")),
                    Is.EqualTo(new[] { "Haz eso", "mañana a las 9" }));
                Assert.That(
                    turns,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "text")?.Contains(
                            "Aclaración confiable del usuario",
                            StringComparison.Ordinal) == true));
            });
        });
    }

    [Test]
    public async Task SafeArgumentFreeActionTraversesTurnDecisionAndRealCore()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string answer = await SubmitAsync(viewModel, "Dime la hora actual");
            JsonElement answerFacts = ParseFacts(answer);

            JsonElement[] trace = ReadTrace(tracePath);
            JsonElement decision = trace.Single(static entry =>
                Property(entry, "type") == "turn.decide"
                && Property(entry, "text") == "Dime la hora actual");
            Assert.Multiple(() =>
            {
                Assert.That(Property(decision, "text"), Is.EqualTo("Dime la hora actual"));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") == "arguments"));
                Assert.That(
                    trace,
                    Has.None.Matches<JsonElement>(static entry =>
                        Property(entry, "type") == "plan"));
                Assert.That(answerFacts.GetProperty("operation").GetString(), Is.EqualTo("system.time"));
                Assert.That(
                    answerFacts.GetProperty("observed").GetProperty("localTime").GetString(),
                    Is.Not.Empty);
            });
            AssertOutboxEmpty(dataRoot);
        });
    }

    [Test]
    public async Task SimpleMindActionPreservesCoreConfirmationInsteadOfClaimingSuccess()
    {
        await WithContractMindAsync(async (viewModel, dataRoot, tracePath) =>
        {
            string prompt = await SubmitAsync(
                viewModel,
                "Navega Opera a https://example.com/");
            JsonElement promptFacts = ParseFacts(prompt);

            JsonElement[] trace = ReadTrace(tracePath);
            Assert.Multiple(() =>
            {
                Assert.That(promptFacts.GetProperty("kind").GetString(), Is.EqualTo("confirmation"));
                Assert.That(promptFacts.GetProperty("cause").GetString(), Is.EqualTo("step_needs_confirmation"));
                Assert.That(
                    promptFacts.GetProperty("choices").EnumerateArray()
                        .Select(static choice => choice.GetString()),
                    Is.EqualTo(new[] { "confirmar", "confirm", "cancelar", "cancel" }));
                Assert.That(
                    trace.Count(static entry =>
                        Property(entry, "type") == "arguments"
                        && Property(entry, "operation")
                            == "browser.navigate.named"),
                    Is.EqualTo(1));
                Assert.That(
                    new DurableRetryStore(
                        Path.Combine(dataRoot, "shell", "retry-outbox.v1.json"))
                        .Load(),
                    Has.Count.EqualTo(1));
            });

            string cancelled = await SubmitAsync(viewModel, "cancelar");
            Assert.That(
                ParseFacts(cancelled).GetProperty("cause").GetString(),
                Is.EqualTo("mission_cancelled_partial"));
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
            JsonElement answerFacts = ParseFacts(answer);
            string[] answerSteps = answerFacts.GetProperty("steps").EnumerateArray()
                .Select(static step => step.GetString() ?? string.Empty)
                .ToArray();

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
                Assert.That(answerFacts.GetProperty("cause").GetString(), Is.EqualTo("mission_completed"));
                Assert.That(answerFacts.GetProperty("stepCount").GetInt32(), Is.EqualTo(2));
                Assert.That(answerSteps, Has.Some.Contains("\"operation\":\"system.time\""));
                Assert.That(answerSteps, Has.Some.Contains("\"operation\":\"system.status\""));
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
            JsonElement answerFacts = ParseFacts(answer);

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
                Assert.That(answerFacts.GetProperty("cause").GetString(), Is.EqualTo("mission_completed"));
                Assert.That(answerFacts.GetProperty("stepCount").GetInt32(), Is.EqualTo(2));
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
            Assert.That(reply.TrimStart(), Does.Not.StartWith("{"));
            Assert.That(reply.TrimStart(), Does.Not.StartWith("["));
            Assert.That(reply, Does.Not.Contain("turn.result"));
            Assert.That(reply, Does.Not.Contain("operation"));
            Assert.That(reply, Does.Not.Contain("No pude interpretar esa petición"));
            Assert.That(reply, Does.Not.Contain("inteligencia local no está disponible"));
        });
    }

    private static JsonElement[] ReadTrace(string path)
    {
        Exception? lastFailure = null;
        for (int attempt = 0; attempt < 50; attempt++)
        {
            try
            {
                return File.ReadAllLines(path)
                    .Where(static line => !string.IsNullOrWhiteSpace(line))
                    .Select(static line => JsonDocument.Parse(line).RootElement.Clone())
                    .ToArray();
            }
            catch (Exception exception) when (exception is IOException or JsonException)
            {
                lastFailure = exception;
                Thread.Sleep(TimeSpan.FromMilliseconds(20));
            }
        }

        throw new IOException("The mind contract trace stayed unavailable.", lastFailure);
    }

    private static JsonElement ParseFacts(string source)
    {
        Assert.That(UserMessagePolicy.IsStructuredFacts(source), Is.True);
        using JsonDocument document = JsonDocument.Parse(source);
        return document.RootElement.Clone();
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
