using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

public sealed class NaturalMemoryRequestParserTests
{
    [TestCase("¿Quién eres?")]
    [TestCase("Who are you?")]
    public void ConversationalIdentityFlowsToTheMind(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute), result.ToString());
            Assert.That(result.MustNotClaimStandaloneRoute, Is.False, result.ToString());
        });
    }

    [Test]
    public void AmbiguousAudioDeviceRequestFlowsToTheMindPlanner()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "puedes cambiar el dispositivo");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute), result.ToString());
            Assert.That(result.MustNotClaimStandaloneRoute, Is.False, result.ToString());
        });
    }

    [TestCase("my favorite city is Lima")]
    [TestCase("i'm a developer")]
    [TestCase("me llamo Albeda")]
    public void ImplicitPersonalFactsDoNotPersistWithoutASaveRequest(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute));
            Assert.That(result.Operation, Is.Null);
            Assert.That(result.MustNotPersist, Is.True);
        });
    }

    [TestCase("Quiero que me recuerdes como red", "red")]
    [TestCase("Necesito que me recuerdes como Alicia", "Alicia")]
    [TestCase("I want you to remember me as Jordan", "Jordan")]
    [TestCase("I'd like you to remember me as Renée", "Renée")]
    public void ExplicitRememberMeAsRequestsRouteANameSave(string text, string expectedName)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.save"));
            Assert.That(
                result.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo("name"));
            Assert.That(
                result.Operation?.PrivateArguments["value"]?.GetValue<string>(),
                Is.EqualTo(expectedName));
        });
    }

    [TestCase("No quiero que me recuerdes como red")]
    [TestCase("I don't want you to remember me as Jordan")]
    public void NegatedRememberMeAsRequestsNeverPersist(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.Not.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("what do you know about me")]
    [TestCase("que tienes guardado sobre mi")]
    [TestCase("cosa ricordi di me")]
    public void HistoricalMemoryInspectionRoutesPrivately(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.recall"));
            Assert.That(
                result.Operation?.PrivateArguments["scope"]?.GetValue<string>(),
                Is.EqualTo("all"));
        });
    }

    [Test]
    public void ExplicitGenericFactUsesStablePrivateSelector()
    {
        MemoryParseResult first = NaturalMemoryRequestParser.Classify(
            "Recuerda que mi editor favorito es VS Code");
        MemoryParseResult second = NaturalMemoryRequestParser.Classify(
            "Recuerda que mi editor favorito es VS Code");

        Assert.Multiple(() =>
        {
            Assert.That(first.Operation?.Name, Is.EqualTo("memory.save"));
            Assert.That(
                first.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Does.StartWith("historical_fact_"));
            Assert.That(
                second.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo(first.Operation?.PrivateArguments["selector"]?.GetValue<string>()));
        });
    }

    [Test]
    public void GenericPersonalTopicForgetRoutesPrivatelyAndRequiresConfirmation()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "olvidate de mi direccion vieja");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.forget"));
            Assert.That(
                result.Operation?.PrivateArguments["scope"]?.GetValue<string>(),
                Is.EqualTo("topic"));
            Assert.That(
                result.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo("mi direccion vieja"));
            Assert.That(
                result.Operation?.PrivateArguments["confirmationRequired"]?.GetValue<bool>(),
                Is.True);
        });
    }

    [TestCase("olvida lo anterior")]
    [TestCase("olvida todo lo que sabes")]
    [TestCase("forget everything you know")]
    public void UnderspecifiedDestructiveForgetRequiresClarification(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Clarify));
            Assert.That(result.Operation, Is.Null);
            Assert.That(result.MustNotDelete, Is.True);
        });
    }

    [TestCase("abrí el administrador de tareas")]
    [TestCase("ouvre le gestionnaire des tâches")]
    public void ApplicationAdministratorWordsDoNotBecomeAuthorityMemory(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute));
            Assert.That(result.MustNotChangeAuthority, Is.False);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [Test]
    public void AccentedSessionForgetRoutesPrivatelyWithoutDeletingPersistentMemory()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "olvidá lo anterior de esta conversación");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.forget"));
            Assert.That(
                result.Operation?.PrivateArguments["scope"]?.GetValue<string>(),
                Is.EqualTo("session"));
            Assert.That(
                result.Operation?.PrivateArguments["mustNotDeletePersistent"]?.GetValue<bool>(),
                Is.True);
        });
    }

    [Test]
    public void ItalianPersistentLanguagePreferenceRoutesPrivately()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "parla in inglese da adesso in poi");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.save"));
            Assert.That(
                result.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo("language"));
            Assert.That(
                result.Operation?.PrivateArguments["value"]?.GetValue<string>(),
                Is.EqualTo("en"));
        });
    }

    [TestCaseSource(nameof(PositiveOracleCases))]
    public void RoutesEveryAuditedSaveRecallAndForgetRow(
        string text,
        string expectedOperation,
        string expectedArgumentsJson,
        string messageId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, messageId);
            Assert.That(operation, Is.Not.Null, messageId);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation), messageId);
        });
        AssertCanonicalArguments(operation!, expectedArgumentsJson, messageId);
    }

    [TestCaseSource(nameof(CorrectionOracleCases))]
    public void RoutesEveryAuditedCorrectionRow(
        string text,
        string expectedOperation,
        string expectedArgumentsJson,
        string messageId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, messageId);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation), messageId);
        });
        AssertCanonicalArguments(operation!, expectedArgumentsJson, messageId);
    }

    [TestCaseSource(nameof(HardNegativeOracleCases))]
    public void HonorsEveryHardNegativeBehavioralContract(
        string text,
        string expectedOutcome,
        string? expectedOperation,
        string expectedJson,
        string category,
        string messageId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);
        MemoryParseOutcome expectedTypedOutcome = ExpectedOutcome(expectedOutcome);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedTypedOutcome), $"{category}: {messageId}");
            Assert.That(parsed, Is.EqualTo(expectedTypedOutcome == MemoryParseOutcome.Route), messageId);
            Assert.That(operation is null, Is.EqualTo(expectedTypedOutcome != MemoryParseOutcome.Route), messageId);
        });

        if (expectedTypedOutcome == MemoryParseOutcome.Route)
        {
            Assert.Multiple(() =>
            {
                Assert.That(result.Operation?.Name, Is.EqualTo(expectedOperation), messageId);
                Assert.That(operation?.Name, Is.EqualTo(result.Operation?.Name), messageId);
                Assert.That(
                    operation?.PrivateArguments.ToJsonString(),
                    Is.EqualTo(result.Operation?.PrivateArguments.ToJsonString()),
                    messageId);
            });
            if (string.Equals(category, "session_context_forget", StringComparison.Ordinal))
            {
                Assert.Multiple(() =>
                {
                    Assert.That(
                        result.Operation?.PrivateArguments["scope"]?.GetValue<string>(),
                        Is.EqualTo("session"),
                        messageId);
                    Assert.That(result.Operation?.PrivateArguments["selector"], Is.Null, messageId);
                    Assert.That(
                        result.Operation?.PrivateArguments["confirmationRequired"]?.GetValue<bool>(),
                        Is.False,
                        messageId);
                    Assert.That(
                        result.Operation?.PrivateArguments["mustNotDeletePersistent"]?.GetValue<bool>(),
                        Is.True,
                        messageId);
                });
            }
        }
        else if (expectedTypedOutcome == MemoryParseOutcome.ConfirmSensitiveSave)
        {
            bool expectedDraft = messageId is
                "msg_5309236d37a921dd31cd" or "msg_f15a5d00c9a2401647fb";
            Assert.That(result.Operation is not null, Is.EqualTo(expectedDraft), messageId);
            if (expectedDraft)
            {
                string expectedSelector = messageId == "msg_5309236d37a921dd31cd"
                    ? "password"
                    : "api_key";
                string privateValue = result.Operation?.PrivateArguments["value"]?.GetValue<string>()
                    ?? throw new InvalidDataException("El borrador sensible no tiene valor privado.");
                Assert.Multiple(() =>
                {
                    Assert.That(result.Operation?.Name, Is.EqualTo("memory.save"), messageId);
                    Assert.That(
                        result.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                        Is.EqualTo(expectedSelector),
                        messageId);
                    Assert.That(
                        result.Operation?.PrivateArguments["sensitivity"]?.GetValue<string>(),
                        Is.EqualTo("secret"),
                        messageId);
                    Assert.That(privateValue, Is.Not.Empty, messageId);
                    Assert.That(
                        expectedSelector == "password"
                            ? privateValue.All(char.IsDigit)
                            : privateValue.StartsWith("sk-", StringComparison.Ordinal)
                                && !privateValue.Contains("memory", StringComparison.OrdinalIgnoreCase),
                        Is.True,
                        messageId);
                });
            }
        }
        else
        {
            Assert.That(result.Operation, Is.Null, messageId);
        }

        AssertSafetyContracts(result, expectedJson, expectedOutcome, messageId);
    }

    [TestCase(
        "RECUERDA   que my favorite color is verde!!!",
        "memory.save",
        "favorite_color",
        "verde")]
    [TestCase(
        "Remember that my name is Zoë.",
        "memory.save",
        "name",
        "Zoë")]
    [TestCase(
        "Recuerda durante esta sesión que mi proyecto se llama Ágora",
        "memory.save",
        "project_name",
        "Ágora")]
    [TestCase(
        "remember that I prefer short responses",
        "memory.save",
        "response_style",
        "short")]
    [TestCase(
        "recuerda que I prefer dark mode",
        "memory.save",
        "display_mode",
        "dark")]
    [TestCase(
        "WHAT'S MY FAVORITE COLOR?",
        "memory.recall",
        "favorite_color",
        null)]
    [TestCase(
        "forget my favorite color",
        "memory.forget",
        "favorite_color",
        null)]
    [TestCase(
        "Quel est mon nom, s'il vous plaît?",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "wie heiße ich",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "Erinnere dich an meinen Firmennamen",
        "memory.recall",
        "employer",
        null)]
    [TestCase(
        "Quien soy yo?",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "Was ist mein Name noch mal?",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "Was ist meine bevorzugte Einstellung?",
        "memory.recall",
        "preference",
        null)]
    public void RoutesBoundedSpanishEnglishAndSpanglishVariations(
        string text,
        string expectedOperation,
        string expectedSelector,
        string? expectedValue)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation));
            Assert.That(
                operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo(expectedSelector));
            if (expectedValue is not null)
            {
                Assert.That(
                    operation?.PrivateArguments["value"]?.GetValue<string>(),
                    Is.EqualTo(expectedValue));
            }
        });
    }

    [TestCase("activa la memoria", "memory.configure", "enabled", true)]
    [TestCase("enable memory", "memory.configure", "enabled", true)]
    [TestCase("desactiva la memoria", "memory.configure", "enabled", false)]
    [TestCase("disable memory", "memory.configure", "enabled", false)]
    public void RoutesExplicitMemoryConsentControls(
        string text,
        string expectedOperation,
        string property,
        bool expectedValue)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation));
            Assert.That(
                operation?.PrivateArguments[property]?.GetValue<bool>(),
                Is.EqualTo(expectedValue));
        });
    }

    [TestCase("tienes memoria", "memory.status")]
    [TestCase("do you have memory", "memory.status")]
    [TestCase(
        "Hey, please, is your personal local-memory store working right now",
        "memory.status")]
    [TestCase(
        "Oye, please check whether tu personal local-memory store está working ahora",
        "memory.status")]
    [TestCase(
        "Baxy, escucha: Cuando puedas, comprueba si tus recuerdos privados de este PC están operativos",
        "memory.status")]
    [TestCase(
        "Baxy, listen: One quick request, please: check whether your private memories on this PC are operational",
        "memory.status")]
    [TestCase(
        "Cuando tengas un minuto, please check si tus private memories de este PC est\u00e1n operational",
        "memory.status")]
    [TestCase(
        "Oye, Baxy: cuando tengas un minuto, please check si tus private memories de este PC est\u00e1n operational.",
        "memory.status")]
    [TestCase(
        "Che, Baxy: porfa, when you have a minute, please check si tus private memories de este PC est\u00e1n operational.",
        "memory.status")]
    [TestCase(
        "Che, Baxy: one small request, porfa: est\u00e1 working ahora tu personal local-memory store.",
        "memory.status")]
    [TestCase("lista mi memoria", "memory.list")]
    [TestCase("list my memories", "memory.list")]
    [TestCase("exporta mi memoria", "memory.export")]
    [TestCase("export my memory", "memory.export")]
    public void RoutesExplicitInspectionAndRedactedExportControls(
        string text,
        string expectedOperation)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation));
            Assert.That(operation?.PrivateArguments["version"]?.GetValue<int>(), Is.EqualTo(1));
            if (string.Equals(expectedOperation, "memory.export", StringComparison.Ordinal))
            {
                Assert.That(
                    operation?.PrivateArguments["includeSecrets"]?.GetValue<bool>(),
                    Is.False);
            }
        });
    }

    [TestCase("Dime cómo está la memoria local de Baxy")]
    [TestCase("Baxy, por favor: dime cómo está la memoria local de Baxy.")]
    [TestCase("Consulta el estado de tus recuerdos locales")]
    [TestCase("Baxy, por favor: consulta el estado de tus recuerdos locales.")]
    [TestCase("Show the status of Baxy's local memory")]
    [TestCase("Baxy, please: show the status of Baxy's local memory.")]
    [TestCase("Check whether local memory is enabled")]
    [TestCase("Baxy, please: check whether local memory is enabled.")]
    [TestCase("Checkea el estado de Baxy memory")]
    [TestCase("Baxy, porfa: checkea el estado de Baxy memory.")]
    [TestCase("Dime whether tu personal local-memory store está operational en este device")]
    [TestCase("Verifica si tus memorias privadas locales están activas ahora mismo")]
    [TestCase("Let me know the operational state of the personal memory Baxy keeps locally right now")]
    [TestCase("Aclárame whether la private memory guardada locally está working on este computer")]
    [TestCase("Te paso una indicación específica para el equipo: dime cómo está la memoria local de Baxy")]
    [TestCase("Here is a specific request for the PC: check whether local memory is enabled")]
    // The frame's word classes are completed from the language rather than
    // from the wordings a corpus used, and this border must match the Python
    // one exactly. "ordenador" is the ordinary Spanish-from-Spain word for a
    // computer; without it the frame was never stripped for those speakers.
    [TestCase("Esta orden es para el ordenador: dime cómo está la memoria local de Baxy")]
    [TestCase("Va un encargo para la máquina: dime cómo está la memoria local de Baxy")]
    [TestCase("Atiende este mandato en el portátil: dime cómo está la memoria local de Baxy")]
    [TestCase("Recibe esta solicitud de la computadora: dime cómo está la memoria local de Baxy")]
    [TestCase("This errand goes to the laptop: check whether local memory is enabled")]
    [TestCase("Take care of the following on the machine: check whether local memory is enabled")]
    [TestCase("For this computer right now, please check whether local memory is enabled")]
    [TestCase("Baxy, haz esto: comprueba si tus recuerdos privados locales están operativos")]
    public void RoutesGeneralizationSurfaceStatusRequests(string text)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"));
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1));
        });
    }

    [TestCaseSource(nameof(BlindR2MemoryCases))]
    public void RoutesBlindR2MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR2MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v2.jsonl");
        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR2MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR3MemoryCases))]
    public void RoutesBlindR3MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR3MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v3.jsonl");
        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR3MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR4MemoryCases))]
    public void RoutesBlindR4MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR4MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v4.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR4MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR5MemoryCases))]
    public void RoutesBlindR5MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR5MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v5.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR5MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR6MemoryCases))]
    public void RoutesBlindR6MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR6MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v6.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR6MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR7MemoryCases))]
    public void RoutesBlindR7MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR7MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v7.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR7MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR8MemoryCases))]
    public void RoutesBlindR8MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR8MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v8.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR8MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR9MemoryCases))]
    public void RoutesBlindR9MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR9MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v9.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR9MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR10MemoryCases))]
    public void RoutesBlindR10MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR10MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v10.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR10MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR11MemoryCases))]
    public void RoutesBlindR11MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR11MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v11.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR11MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR12MemoryCases))]
    public void RoutesBlindR12MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR12MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v12.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR12MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR13MemoryCases))]
    public void RoutesBlindR13MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR13MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v13.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR13MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR14MemoryCases))]
    public void RoutesBlindR14MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR14MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v14.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR14MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR15MemoryCases))]
    public void RoutesBlindR15MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR15MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v15.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR15MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR16MemoryCases))]
    public void RoutesBlindR16MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR16MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v16.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR16MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR17MemoryCases))]
    public void RoutesBlindR17MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR17MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v17.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR17MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR18MemoryCases))]
    public void RoutesBlindR18MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR18MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v18.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR18MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR19MemoryCases))]
    public void RoutesBlindR19MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR19MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v19.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR19MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR20MemoryCases))]
    public void RoutesBlindR20MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR20MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v20.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR20MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindR21MemoryCases))]
    public void RoutesBlindR21MemoryStatusRequests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindR21MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_holdout_v21.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindR21MemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCurrentTreeR22GeneralizationMemoryCases))]
    public void RoutesBlindCurrentTreeR22GeneralizationMemoryStatusRequests(
        string text,
        string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCurrentTreeR22GeneralizationMemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_current_tree_r22.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName(
                    $"RoutesBlindCurrentTreeR22GeneralizationMemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCurrentTreeR25GeneralizationMemoryCases))]
    public void RoutesBlindCurrentTreeR25GeneralizationMemoryStatusRequests(
        string text,
        string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCurrentTreeR25GeneralizationMemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_current_tree_r25.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName(
                    $"RoutesBlindCurrentTreeR25GeneralizationMemoryStatusRequests({caseId})");
        }
    }

    // Written before the R26 corpus is sealed, on purpose. This file is itself
    // a sealed measurement source, so adding the method afterwards is what
    // voided R24: the probe refused to open a population whose measurement code
    // had changed since preregistration. The source yields nothing until the
    // corpus exists.
    [TestCaseSource(nameof(BlindCurrentTreeR26GeneralizationMemoryCases))]
    public void RoutesBlindCurrentTreeR26GeneralizationMemoryStatusRequests(
        string text,
        string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCurrentTreeR26GeneralizationMemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_current_tree_r26.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName(
                    $"RoutesBlindCurrentTreeR26GeneralizationMemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCurrentTreeR27GeneralizationMemoryCases))]
    public void RoutesBlindCurrentTreeR27GeneralizationMemoryStatusRequests(
        string text,
        string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCurrentTreeR27GeneralizationMemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_current_tree_r27.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName(
                    $"RoutesBlindCurrentTreeR27GeneralizationMemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCurrentTreeR28GeneralizationMemoryCases))]
    public void RoutesBlindCurrentTreeR28GeneralizationMemoryStatusRequests(
        string text,
        string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCurrentTreeR28GeneralizationMemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "generalization_product_current_tree_r28.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName(
                    $"RoutesBlindCurrentTreeR28GeneralizationMemoryStatusRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(CatalogSeenMemoryCases))]
    public void RoutesEveryReviewedCatalogMemoryOperation(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> CatalogSeenMemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "development",
            "catalog_seen_scenarios_r2_dependency_complete.jsonl");

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesEveryReviewedCatalogMemoryOperation({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCatalogSurfaceR22MemoryCases))]
    public void RoutesBlindCatalogSurfaceR22MemoryRequests(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCatalogSurfaceR22MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "catalog_surface_holdout_r22.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesBlindCatalogSurfaceR22MemoryRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCatalogSurfaceR23MemoryCases))]
    public void RoutesBlindCatalogSurfaceR23MemoryRequests(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCatalogSurfaceR23MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "catalog_surface_holdout_r23.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesBlindCatalogSurfaceR23MemoryRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCatalogSurfaceR24MemoryCases))]
    public void RoutesBlindCatalogSurfaceR24MemoryRequests(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCatalogSurfaceR24MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "catalog_surface_holdout_r24.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesBlindCatalogSurfaceR24MemoryRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCatalogSurfaceR25MemoryCases))]
    public void RoutesBlindCatalogSurfaceR25MemoryRequests(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCatalogSurfaceR25MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "catalog_surface_holdout_r25.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesBlindCatalogSurfaceR25MemoryRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCatalogSurfaceR26MemoryCases))]
    public void RoutesBlindCatalogSurfaceR26MemoryRequests(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCatalogSurfaceR26MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "catalog_surface_holdout_r26.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesBlindCatalogSurfaceR26MemoryRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCurrentTreeR1MemoryCases))]
    public void RoutesBlindCurrentTreeR1MemoryRequests(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCurrentTreeR1MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "catalog_surface_current_tree_r1.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesBlindCurrentTreeR1MemoryRequests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindCurrentTreeR2MemoryCases))]
    public void RoutesBlindCurrentTreeR2MemoryRequests(
        string text,
        string expectedWireOperation,
        string caseId)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        MemoryParseOutcome expectedOutcome = string.Equals(
            expectedWireOperation,
            "memory.sensitive.save",
            StringComparison.Ordinal)
                ? MemoryParseOutcome.ConfirmSensitiveSave
                : MemoryParseOutcome.Route;

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(expectedOutcome), caseId);
            Assert.That(result.Operation, Is.Not.Null, caseId);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindCurrentTreeR2MemoryCases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "catalog_surface_current_tree_r2.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            if (!string.Equals(
                    root.GetProperty("owner").GetString(),
                    "app_private_memory_parser",
                    StringComparison.Ordinal))
            {
                continue;
            }

            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            string targetOperation = root.GetProperty("target_operation").GetString()!;
            yield return new TestCaseData(text, targetOperation, caseId)
                .SetName($"RoutesBlindCurrentTreeR2MemoryRequests({caseId})");
        }
    }

    [TestCase(
        "Desactiva la memoria local de BAXY; con esto finaliza mi pedido.",
        "memory.disable")]
    [TestCase(
        "Enable BAXY's private local memory; this concludes the task.",
        "memory.enable")]
    [TestCase(
        "Muéstrame la lista de recuerdos locales que guardaste; mi solicitud queda completa aquí.",
        "memory.list")]
    [TestCase(
        "What do you remember about my preferred editor; my request is finished for now.",
        "memory.recall")]
    [TestCase(
        "Tell me whether local memory is enabled and what its limits are; con esto, the task is done for now.",
        "memory.status")]
    public void RoutesMemoryRequestsWithNaturalCompletionClosures(
        string text,
        string expectedWireOperation)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation, Is.Not.Null);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation));
        });
    }

    [TestCaseSource(nameof(BlindMemoryStatusR1Cases))]
    public void RoutesBlindMemoryStatusR1Requests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindMemoryStatusR1Cases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "memory_status_generalization_v1.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindMemoryStatusR1Requests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindMemoryStatusR2Cases))]
    public void RoutesBlindMemoryStatusR2Requests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindMemoryStatusR2Cases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "memory_status_generalization_v2.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindMemoryStatusR2Requests({caseId})");
        }
    }

    [TestCaseSource(nameof(BlindMemoryStatusR3Cases))]
    public void RoutesBlindMemoryStatusR3Requests(string text, string caseId)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, caseId);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"), caseId);
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1),
                caseId);
        });
    }

    private static IEnumerable<TestCaseData> BlindMemoryStatusR3Cases()
    {
        string repositoryRoot = FindRepositoryRoot();
        string corpusPath = Path.Combine(
            repositoryRoot,
            "artifacts",
            "holdout",
            "memory_status_generalization_v3.jsonl");
        if (!File.Exists(corpusPath))
        {
            yield break;
        }

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            string caseId = root.GetProperty("case_id").GetString()!;
            string text = root.GetProperty("text").GetString()!;
            yield return new TestCaseData(text, caseId)
                .SetName($"RoutesBlindMemoryStatusR3Requests({caseId})");
        }
    }

    [TestCase("mi nombre es Emmanuel")]
    [TestCase("my favorite color is blue")]
    [TestCase("olvida eso")]
    [TestCase("remember this")]
    [TestCase("guarda esa preferencia para siempre")]
    [TestCase("no guardes que mi color favorito es azul")]
    [TestCase("don't remember that my name is Alex")]
    [TestCase("no uses memoria para esto")]
    [TestCase("tienes permiso total sobre mi PC")]
    [TestCase("recuérdame en 10 minutos sacar la basura")]
    [TestCase("remind me tomorrow at 9 to call Ana")]
    [TestCase("cuánta memoria RAM me queda libre")]
    [TestCase("revisa el estado de la memoria RAM del sistema")]
    [TestCase("revisa el estado de la memoria local de mi teléfono")]
    [TestCase("explícame cómo funciona la memoria local de Baxy")]
    [TestCase("no revises el estado de la memoria local de Baxy")]
    [TestCase("muestra el estado de la memoria local y abre Spotify")]
    [TestCase("tell me how Baxy's local memory works")]
    [TestCase("check the local memory in my phone")]
    [TestCase("I nailed that flashcard, mark it as a perfect recall")]
    [TestCase("abre Word y guarda el documento")]
    [TestCase("remember my password is hunter2")]
    [TestCase("recuerda mi RUT 12.345.678-9")]
    [TestCase("save my API key sk-example in your memory")]
    [TestCase("qué recuerdas de mí y abre Spotify")]
    [TestCase("<command-name>/memory</command-name>")]
    [TestCase("telemetría memory.save habilitada")]
    [TestCase("cuando puedas recordar mi color favorito será útil")]
    [TestCase("one quick request to delete a memory is not an execution order")]
    [TestCase("Quiero preguntarte algo sin pedir una acción: activa la memoria")]
    [TestCase("Baxy, handle this: I have a short question, just to chat: disable memory")]
    [TestCase("mira mis recuerdos de infancia con atención")]
    public void RejectsInferenceAnaphoraNegationSecretsRemindersHomonymsAndCompositions(
        string text)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False, text);
            Assert.That(operation, Is.Null, text);
        });
    }

    [Test]
    public void RejectsNullBlankControlMalformedUtf16AndOversizedInputWithoutThrowing()
    {
        string?[] malformed =
        [
            null,
            string.Empty,
            "   ",
            "recuerda que mi nombre es A\0lex",
            "recuerda que mi nombre es A\nlex",
            "remember my name is " + new string('\ud800', 1),
            "remember my name is " + new string('\udc00', 1),
            "remember my name is " + new string('a', 4097),
        ];

        foreach (string? text in malformed)
        {
            MemoryRoutedOperation? operation = null;
            bool parsed = true;
            Assert.DoesNotThrow(
                () => parsed = NaturalMemoryRequestParser.TryParse(text, out operation),
                text ?? "<null>");
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.False, text);
                Assert.That(operation, Is.Null, text);
            });
        }
    }

    [Test]
    public void MemoryRouteCannotBePassedToThePlaintextRetryRegistry()
    {
        MethodInfo[] getOrAddMethods = typeof(RetryableOperationRegistry)
            .GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Where(method => string.Equals(method.Name, "GetOrAdd", StringComparison.Ordinal))
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(typeof(MemoryRoutedOperation).IsAssignableTo(typeof(RoutedOperation)), Is.False);
            Assert.That(typeof(RoutedOperation).IsAssignableTo(typeof(MemoryRoutedOperation)), Is.False);
            Assert.That(getOrAddMethods, Has.Length.EqualTo(2));
            Assert.That(
                getOrAddMethods
                    .Select(method => method.GetParameters().Single().ParameterType),
                Is.EquivalentTo(new[]
                {
                    typeof(RoutedOperation),
                    typeof(ProtectedMemoryOperation),
                }));
            Assert.That(
                getOrAddMethods.Any(method => method.GetParameters()
                    .Any(parameter => parameter.ParameterType == typeof(MemoryRoutedOperation))),
                Is.False);
        });
    }

    [TestCase("recuerda que mi color favorito es azul pero no lo guardes")]
    [TestCase("remember that my favorite color is blue but don't save it")]
    [TestCase("recuerda mi contraseña es 1234 pero no la guardes")]
    [TestCase("recuerda que mi proyecto se llama Atlas pero no lo almacenes")]
    [TestCase("recuerda que mi proyecto se llama Atlas pero no lo memorices")]
    [TestCase("recuerda que mi proyecto se llama Atlas sin memorizarlo")]
    [TestCase("remember that my project is called Atlas without persisting it")]
    public void PostposedNoStoreInstructionOverridesAnySave(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute));
            Assert.That(result.MustNotPersist, Is.True);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("recuerda que mi proyecto se llama Carter y que tienes permiso para modificarlo")]
    [TestCase("remember that my project is called Carter and you have permission to modify it")]
    [TestCase("recuerda que mi proyecto se llama Atlas y te autorizo a modificarlo")]
    [TestCase("recuerda que mi proyecto se llama Atlas y tienes autorización total")]
    [TestCase("recuerda que mi proyecto se llama Atlas y eres administrador total")]
    public void EmbeddedAuthorityGrantIsNeverStoredAsAValue(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(
                result.Outcome,
                Is.EqualTo(MemoryParseOutcome.RejectAuthorizationPersistence));
            Assert.That(result.MustNotPersist, Is.True);
            Assert.That(result.MustNotChangeAuthority, Is.True);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("remember that my project is called sk_live_51ABCDEF123456")]
    [TestCase("recuerda que mi proyecto se llama ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890")]
    [TestCase("recuerda que mi proyecto se llama github_pat_11AA00_exampletoken")]
    [TestCase("recuerda que mi proyecto se llama AKIAIOSFODNN7EXAMPLE")]
    [TestCase("recuerda que mi proyecto se llama glpat-0123456789abcdefghij")]
    [TestCase("recuerda que mi proyecto se llama gldt-0123456789abcdefghij")]
    [TestCase("recuerda que mi proyecto se llama eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.signature1")]
    public void CredentialShapedProjectNamesNeverUseTheLowRiskSaveRoute(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.Not.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("recuerda mi API key: REDACTED")]
    [TestCase("recuerda mi API key: <REDACTED>")]
    [TestCase("recuerda mi API key: ***")]
    [TestCase("recuerda mi API key: [REMOVED]")]
    [TestCase("recuerda mi API key: [CENSORED]")]
    [TestCase("recuerda mi API key: (CENSORED)")]
    [TestCase("recuerda mi API key: N/A")]
    public void RedactedSensitivePlaceholdersNeverCreateAnExecutableDraft(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.ConfirmSensitiveSave));
            Assert.That(result.MustNotPersist, Is.True);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [Test]
    public void RoutedPrivateArgumentsAreImmutableSnapshots()
    {
        MemoryParseResult sensitive = NaturalMemoryRequestParser.Classify(
            "recuerda mi contraseña es 1234");
        MemoryParseResult forget = NaturalMemoryRequestParser.Classify(
            "borra mi color favorito");
        JsonObject sensitiveClone = sensitive.Operation!.PrivateArguments;
        JsonObject forgetClone = forget.Operation!.PrivateArguments;

        sensitiveClone["sensitivity"] = "normal";
        sensitiveClone["value"] = "changed";
        forgetClone["confirmationRequired"] = false;

        Assert.Multiple(() =>
        {
            Assert.That(
                sensitive.Operation.PrivateArguments["sensitivity"]?.GetValue<string>(),
                Is.EqualTo("secret"));
            Assert.That(
                sensitive.Operation.PrivateArguments["value"]?.GetValue<string>(),
                Is.EqualTo("1234"));
            Assert.That(
                forget.Operation.PrivateArguments["confirmationRequired"]?.GetValue<bool>(),
                Is.True);
        });
    }

    [Test]
    public void TypedMemoryResultsRedactPrivateArgumentsFromDiagnosticText()
    {
        const string canary = "sk-BAXY-PARSER-CANARY";
        var operation = new MemoryRoutedOperation(
            "memory.save",
            new JsonObject
            {
                ["version"] = 1,
                ["selector"] = "api_key",
                ["sensitivity"] = "secret",
                ["value"] = canary,
            });
        MemoryParseResult result = MemoryParseResult.ConfirmSensitiveSave(operation);

        Assert.Multiple(() =>
        {
            Assert.That(operation.ToString(), Does.Not.Contain(canary));
            Assert.That(operation.ToString(), Does.Contain("[REDACTED]"));
            Assert.That(result.ToString(), Does.Not.Contain(canary));
            Assert.That(result.ToString(), Does.Contain("[REDACTED]"));
        });
    }

    [Test]
    public void TypedMemoryResultFactoriesRejectMissingRoutesAndInvalidSensitiveDrafts()
    {
        var invalidSensitiveDraft = new MemoryRoutedOperation(
            "memory.recall",
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "all",
                ["selector"] = null,
            });
        var downgradedSecret = new MemoryRoutedOperation(
            "memory.save",
            new JsonObject
            {
                ["version"] = 1,
                ["selector"] = "api_key",
                ["value"] = "sk-BAXY-DIRECT-CANARY",
                ["kind"] = "fact",
                ["retention"] = "persistent",
                ["sensitivity"] = "normal",
                ["tags"] = new JsonArray(),
            });
        var unconfirmedForget = new MemoryRoutedOperation(
            "memory.forget",
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "all",
                ["selector"] = null,
                ["confirmationRequired"] = false,
            });

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MemoryParseResult.Route(null!),
                Throws.TypeOf<ArgumentNullException>());
            Assert.That(
                () => MemoryParseResult.ConfirmSensitiveSave(invalidSensitiveDraft),
                Throws.TypeOf<ArgumentException>());
            Assert.That(
                () => MemoryParseResult.Route(downgradedSecret),
                Throws.TypeOf<ArgumentException>());
            Assert.That(
                () => MemoryParseResult.Route(unconfirmedForget),
                Throws.TypeOf<ArgumentException>());
        });
    }

    private static IEnumerable<TestCaseData> PositiveOracleCases() =>
        LoadCanonicalCases(["memory.save", "memory.recall", "memory.forget"]);

    private static IEnumerable<TestCaseData> CorrectionOracleCases() =>
        LoadCanonicalCases(["memory.correct"]);

    private static IEnumerable<TestCaseData> LoadCanonicalCases(string[] operations)
    {
        OracleData oracle = LoadOracleData();
        using JsonDocument oracleDocument = JsonDocument.Parse(
            File.ReadAllText(oracle.OraclePath, Encoding.UTF8));

        foreach (JsonElement canonicalCase in oracleDocument.RootElement
            .GetProperty("canonical_cases")
            .EnumerateArray())
        {
            string operation = canonicalCase.GetProperty("operation").GetString()!;
            if (!operations.Contains(operation, StringComparer.Ordinal))
            {
                continue;
            }

            string argumentsJson = canonicalCase.GetProperty("arguments").GetRawText();
            foreach (JsonElement idElement in canonicalCase.GetProperty("ids").EnumerateArray())
            {
                string messageId = idElement.GetString()!;
                yield return new TestCaseData(
                    oracle.TextById[messageId],
                    operation,
                    argumentsJson,
                    messageId)
                    .SetName($"NaturalMemory_{operation.Replace('.', '_')}_{messageId}");
            }
        }
    }

    private static IEnumerable<TestCaseData> HardNegativeOracleCases()
    {
        OracleData oracle = LoadOracleData();
        using JsonDocument oracleDocument = JsonDocument.Parse(
            File.ReadAllText(oracle.OraclePath, Encoding.UTF8));

        foreach (JsonElement hardCase in oracleDocument.RootElement
            .GetProperty("hard_negative_cases")
            .EnumerateArray())
        {
            string category = hardCase.GetProperty("category").GetString()!;
            JsonElement expected = hardCase.GetProperty("expected");
            string outcome = expected.GetProperty("outcome").GetString()!;
            string? operation = expected.TryGetProperty("operation", out JsonElement operationElement)
                ? operationElement.GetString()
                : null;

            foreach (JsonElement idElement in hardCase.GetProperty("ids").EnumerateArray())
            {
                string messageId = idElement.GetString()!;
                yield return new TestCaseData(
                    oracle.TextById[messageId],
                    outcome,
                    operation,
                    expected.GetRawText(),
                    category,
                    messageId)
                    .SetName($"NaturalMemory_hard_negative_{category}_{messageId}");
            }
        }
    }

    private static MemoryParseOutcome ExpectedOutcome(string outcome) => outcome switch
    {
        "route_specialized" => MemoryParseOutcome.Route,
        "clarify" => MemoryParseOutcome.Clarify,
        "ask_to_save" => MemoryParseOutcome.AskToSave,
        "confirm_sensitive_save" => MemoryParseOutcome.ConfirmSensitiveSave,
        "session_context_only" => MemoryParseOutcome.SessionContextOnly,
        "reject_authorization_persistence" => MemoryParseOutcome.RejectAuthorizationPersistence,
        "do_not_claim_standalone_memory_route" or "no_memory_route" =>
            MemoryParseOutcome.NoRoute,
        _ => throw new InvalidDataException($"Resultado de oracle desconocido: {outcome}."),
    };

    private static void AssertSafetyContracts(
        MemoryParseResult result,
        string expectedJson,
        string expectedOutcome,
        string messageId)
    {
        using JsonDocument document = JsonDocument.Parse(expectedJson);
        foreach (JsonProperty property in document.RootElement.EnumerateObject())
        {
            if (!property.Name.StartsWith("must_not_", StringComparison.Ordinal))
            {
                continue;
            }

            bool expected = property.Value.GetBoolean();
            bool actual = property.Name switch
            {
                "must_not_persist_before_confirmation"
                    or "must_not_persist"
                    or "must_not_persist_before_consent" => result.MustNotPersist,
                "must_not_delete" => result.MustNotDelete,
                "must_not_change_authority" => result.MustNotChangeAuthority,
                "must_not_invent" => result.MustNotInvent,
                "must_not_delete_persistent" =>
                    result.Operation?.PrivateArguments["mustNotDeletePersistent"]
                        ?.GetValue<bool>() ?? false,
                _ => throw new InvalidDataException(
                    $"Garantía de oracle desconocida: {property.Name}."),
            };
            Assert.That(actual, Is.EqualTo(expected), $"{messageId}: {property.Name}");
        }

        Assert.Multiple(() =>
        {
            Assert.That(
                result.MustNotClaimStandaloneRoute,
                Is.EqualTo(string.Equals(
                    expectedOutcome,
                    "do_not_claim_standalone_memory_route",
                    StringComparison.Ordinal)),
                messageId);
            bool expectsMask = document.RootElement.TryGetProperty(
                "mask_public_projection",
                out JsonElement maskElement)
                && maskElement.GetBoolean();
            Assert.That(result.MaskPublicProjection, Is.EqualTo(expectsMask), messageId);
        });
    }

    private static void AssertCanonicalArguments(
        MemoryRoutedOperation operation,
        string expectedArgumentsJson,
        string messageId)
    {
        using JsonDocument expectedDocument = JsonDocument.Parse(expectedArgumentsJson);
        JsonElement expected = expectedDocument.RootElement;
        JsonObject actual = operation.PrivateArguments;

        Assert.That(actual["version"]?.GetValue<int>(), Is.EqualTo(1), messageId);
        foreach (JsonProperty property in expected.EnumerateObject())
        {
            string actualName = property.Name switch
            {
                "expires" => "expiryPolicy",
                "old_value" => "expectedValue",
                "confirmation" => "confirmationRequired",
                _ => property.Name,
            };

            if (string.Equals(property.Name, "confirmation", StringComparison.Ordinal))
            {
                Assert.That(actual[actualName]?.GetValue<bool>(), Is.True, messageId);
                continue;
            }

            JsonNode? actualNode = actual[actualName];
            if (property.Value.ValueKind == JsonValueKind.Null)
            {
                Assert.That(actualNode, Is.Null, $"{messageId}: {actualName}");
            }
            else
            {
                object? expectedValue = property.Value.ValueKind switch
                {
                    JsonValueKind.String => property.Value.GetString(),
                    JsonValueKind.True => true,
                    JsonValueKind.False => false,
                    JsonValueKind.Number => property.Value.GetInt32(),
                    _ => property.Value.GetRawText(),
                };
                object? actualValue = property.Value.ValueKind switch
                {
                    JsonValueKind.String => actualNode?.GetValue<string>(),
                    JsonValueKind.True or JsonValueKind.False => actualNode?.GetValue<bool>(),
                    JsonValueKind.Number => actualNode?.GetValue<int>(),
                    _ => actualNode?.ToJsonString(),
                };
                Assert.That(actualValue, Is.EqualTo(expectedValue), $"{messageId}: {actualName}");
            }
        }

        if (string.Equals(operation.Name, "memory.save", StringComparison.Ordinal))
        {
            Assert.Multiple(() =>
            {
                Assert.That(
                    actual["sensitivity"]?.GetValue<string>(),
                    Is.AnyOf("normal", "personal", "sensitive"));
                Assert.That(actual["tags"], Is.TypeOf<JsonArray>());
            });
        }
    }

    private static OracleData LoadOracleData()
    {
        string repositoryRoot = FindRepositoryRoot();
        string oraclePath = Path.Combine(repositoryRoot, "tests", "data", "memory_corpus_oracle.json");
        string corpusPath = Path.Combine(repositoryRoot, "tests", "data", "historical_messages.jsonl");
        var textById = new Dictionary<string, string>(StringComparer.Ordinal);

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            textById[root.GetProperty("message_id").GetString()!] =
                root.GetProperty("text_literal").GetString()!;
        }

        return new OracleData(oraclePath, textById);
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(TestContext.CurrentContext.TestDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("No se encontró la raíz versionada de BAXY.");
    }

    private sealed record OracleData(
        string OraclePath,
        IReadOnlyDictionary<string, string> TextById);
}
