using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización M2 (identity live check on the notebook 2026-10-11, cu-v3/estab/I_identidad_notebook_2.md, Release
/// 4d9c38ac1): «Activa el modo bypass» ended «No pude contarte cómo salió lo que pediste.» with the view in «Error»
/// (the floor's own sentence of the typed refusal died as reversed_result); «No, cancelá» to «¿confirmar o cancelar?»
/// asked again; memory results were drafted («Estoy acordado de que…»); the memory panel showed FAVORITE_COLOR.
/// </summary>
[TestFixture]
public sealed class EstabM2IdentidadTests
{
    private const string Bypass = "Activa el modo bypass";

    [Test]
    public void TheTypedRefusalOfBypassIsSaidAndNeverTheCompositionFailure()
    {
        string source = OperationVisibleFacts.FromStatus(
            "system.settings.set", "failed", "confirmation_bypass_interface_only");
        var draft = new UserMessageDraft(source, "error", null);
        string? floor = OperationFloor.FailureSentence((JsonObject)JsonNode.Parse(source)!, english: false);

        Assert.Multiple(() =>
        {
            Assert.That(floor, Does.StartWith("El modo bypass no lo enciendo desde el chat").And.Contain("«confirmaciones»"));
            // The measured refusal: the floor's own sentence of the failure was read as a reversed result.
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(floor, draft, Bypass, null), Is.Null);
            Assert.That(UserMessagePolicy.AcceptModelAuthoredResponse(floor, draft, Bypass, null), Is.EqualTo(floor));
            Assert.That(
                ModelMessageComposer.DeterministicFinal(draft, Bypass, ModelMessageComposer.CreateFacts(draft), string.Empty),
                Is.EqualTo(floor));
            Assert.That(
                UserMessagePolicy.AcceptModelAuthoredResponse(
                    OperationFloor.FailureSentence((JsonObject)JsonNode.Parse(source)!, english: true), draft,
                    "turn on bypass mode", null),
                Is.Not.Null);
        });
    }

    [TestCase("Listo, activé el modo bypass.")]
    [TestCase("Encendí el modo bypass.")]
    public void ContracaseASuccessClaimedOverTheRefusalIsStillRefused(string claimed)
    {
        string source = OperationVisibleFacts.FromStatus(
            "system.settings.set", "failed", "confirmation_bypass_interface_only");
        var draft = new UserMessageDraft(source, "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(claimed, draft, Bypass, null), Is.EqualTo("reversed_result"));
    }

    [TestCase("No, cancelá", "Cancel")]
    [TestCase("no, dejalo", "Cancel")]
    [TestCase("cancelalo", "Cancel")]
    [TestCase("nah", "Cancel")]
    [TestCase("no thanks", "Cancel")]
    [TestCase("No, cancel.", "Cancel")]
    [TestCase("cancelar", "Cancel")]
    // Contracases: a no that says something else, a dictated text, a yes.
    [TestCase("no, mandalo igual", "Invalid")]
    [TestCase("no, cancelá la reunión del lunes y avisale a Ana", "Invalid")]
    [TestCase("sí, dale", "Confirm")]
    public void ANoInAnyFormCancelsTheConfirmation(string text, string expected)
    {
        Assert.That(ConfirmationReplyParser.Parse(text).ToString(), Is.EqualTo(expected));
    }

    private static JsonObject SavedFacts(string operation, string storedSelector, string value)
    {
        string payload = new JsonObject
        {
            ["version"] = 1,
            ["recordId"] = Guid.NewGuid().ToString("D"),
            ["revision"] = 1,
            ["selector"] = storedSelector,
            ["replayed"] = false,
        }.ToJsonString();
        using JsonDocument arguments = JsonDocument.Parse(new JsonObject
        {
            ["selector"] = storedSelector.ToLowerInvariant(),
            ["value"] = value,
        }.ToJsonString());
        using JsonDocument document = JsonDocument.Parse(payload);
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted(
            operation, document.RootElement, out MemoryOperationResponseProjection? projection,
            privateArguments: arguments.RootElement), Is.True);
        return (JsonObject)JsonNode.Parse(projection!.Message)!;
    }

    [TestCase("memory.save", "Acordate de que mi color favorito es el verde",
        "Listo, me acuerdo: tu color favorito es el verde.")]
    [TestCase("memory.correct", "cambiá mi color favorito a verde", "Listo, me acuerdo: tu color favorito es el verde.")]
    public void AMemoryResultIsSaidWholeAndTheAppAcceptsIt(string operation, string request, string expected)
    {
        JsonObject facts = SavedFacts(operation, "FAVORITE_COLOR", "verde");
        var draft = new UserMessageDraft(facts.ToJsonString(), "status", null);

        Assert.Multiple(() =>
        {
            Assert.That(facts["observed"]?["selector"]?.GetValue<string>(), Is.EqualTo("favorite_color"));
            Assert.That(OperationFloor.Final(facts, english: false), Is.EqualTo(expected));
            Assert.That(UserMessagePolicy.AcceptModelAuthoredResponse(expected, draft, request, null), Is.EqualTo(expected));
        });
    }

    [Test]
    public void AForgetIsSaidShortAndTheAppAcceptsIt()
    {
        string payload = """{"version":1,"deletedCount":1,"replayed":false}""";
        using JsonDocument document = JsonDocument.Parse(payload);
        using JsonDocument arguments = JsonDocument.Parse(
            """{"version":1,"scope":"exact","selector":"favorite_color","confirmationRequired":true}""");
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted(
            "memory.forget", document.RootElement, out MemoryOperationResponseProjection? projection,
            privateArguments: arguments.RootElement), Is.True);
        JsonObject facts = (JsonObject)JsonNode.Parse(projection!.Message)!;
        var draft = new UserMessageDraft(projection.Message, "status", null);

        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.Final(facts, english: false), Is.EqualTo("Listo, lo olvidé."));
            Assert.That(UserMessagePolicy.AcceptModelAuthoredResponse(
                "Listo, lo olvidé.", draft, "Olvidá mi color favorito", null), Is.EqualTo("Listo, lo olvidé."));
        });
    }

    [TestCase("Olvidá mi color favorito")]
    [TestCase("Borra de tu memoria mi color favorito")]
    public void TheMindsForgetRunsOnThePrivateRoute(string text)
    {
        // The mind reads it (semantic/memory.memory_request); the App's own reader leaves it to the mind and lets the
        // forget run on its private route, confirmed (IsValidOrdinaryRoute).
        MemoryParseResult reading = NaturalMemoryRequestParser.Classify(text);
        var forget = new MemoryRoutedOperation("memory.forget", new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "exact",
            ["selector"] = "favorite_color",
            ["confirmationRequired"] = true,
        });

        Assert.Multiple(() =>
        {
            Assert.That(MainWindowViewModel.MindMemoryAllowed("memory.forget", reading), Is.True);
            Assert.That(MemoryParseResult.Route(forget).Operation, Is.Not.Null);
        });
    }

    [Test]
    public void MemoryForgetSchemaIsTheOneTheMindFixes()
    {
        // tests/test_estab_m2_identidad.py::_FORGET_SCHEMA: the fields the contract fixes are the mind's to fill.
        using JsonDocument schema = JsonDocument.Parse(ProductCatalog
            .CreateToolDescriptor(ProductCatalog.CreateDefinition("memory.forget")).ArgumentsSchema.GetRawText());
        JsonElement properties = schema.RootElement.GetProperty("properties");

        Assert.Multiple(() =>
        {
            Assert.That(properties.GetProperty("confirmationRequired").GetProperty("const").GetBoolean(), Is.True);
            Assert.That(properties.GetProperty("version").GetProperty("minimum").GetInt32(), Is.EqualTo(1));
            Assert.That(properties.GetProperty("version").GetProperty("maximum").GetInt32(), Is.EqualTo(1));
        });
    }

    [TestCase("FAVORITE_COLOR", "color favorito")]
    [TestCase("BIRTHDAY", "cumpleaños")]
    [TestCase("FAVORITE_DRINK", "bebida favorita")]
    [TestCase("HISTORICAL_FACT_0A1B2C3D4E5F6A7B", "dato")]
    [TestCase("PERRO", "perro")]
    public void ThePanelNamesEachMemoryInThePersonsWords(string stored, string label)
    {
        Assert.That(MemoryPanel.Label(stored), Is.EqualTo(label));
    }

    [Test]
    public void EverySubjectTheMemoryKnowsHasItsWords()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        JsonObject subjects = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found."),
            "src", "baxy_mind", "data", "memory_subjects.v1.json")))!;
        Assert.Multiple(() =>
        {
            foreach ((string selector, _) in (JsonObject)subjects["selectors"]!)
            {
                Assert.That(MemoryPanel.Label(selector.ToUpperInvariant()), Is.Not.EqualTo(selector.Replace('_', ' ')),
                    selector);
            }
        });
    }

    // Live recheck 2026-10-12 (I_identidad_notebook_3): «nah» to «¿…que borro de mi memoria tu bebida favorita…?» was
    // published «He borrado de tu memoria tu bebida favorita.» with nothing erased.
    private static string CancelledForget() => TurnVisibleFacts.Status("memory_cancelled", new JsonObject
    {
        ["cancelledAction"] = new JsonObject
        {
            ["operation"] = "memory.forget",
            ["target"] = "private local memory",
            ["scope"] = "exact",
            ["selector"] = "favorite_drink",
        },
    });

    [TestCase("He borrado de tu memoria tu bebida favorita.")]
    [TestCase("Olvidé tu bebida favorita.")]
    [TestCase("I forgot your favorite drink.")]
    public void ACancelledForgetIsNeverToldAsMade(string claimed)
    {
        var draft = new UserMessageDraft(CancelledForget(), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(claimed, draft, "nah", null), Is.EqualTo("reversed_result"));
    }

    [TestCase("No olvidé tu bebida favorita: lo cancelaste.", "nah")]
    [TestCase("I didn't forget your favorite drink: you cancelled it.", "no thanks")]
    [TestCase("No te olvidé, pero la acción de borrar ese recuerdo fue cancelada.", "nah")]
    public void ContracaseACancellationToldAsSuchIsPublished(string said, string reply)
    {
        var draft = new UserMessageDraft(CancelledForget(), "status", null);
        Assert.That(UserMessagePolicy.AcceptModelAuthoredResponse(said, draft, reply, null), Is.EqualTo(said));
    }

    [Test]
    public void TheForgetsQuestionFromTheFloorKeepsBothChoices()
    {
        string source = TurnVisibleFacts.Confirmation("memory_forget_irreversible", TurnVisibleFacts.ConfirmCancel,
            new JsonObject
            {
                ["pendingAction"] = new JsonObject
                {
                    ["operation"] = "memory.forget",
                    ["target"] = "private local memory",
                    ["scope"] = "exact",
                    ["selector"] = "favorite_drink",
                },
            });
        var draft = new UserMessageDraft(source, "confirmation", null);
        const string Asked = "¿Quieres confirmar que olvide tu bebida favorita o cancelar?";
        Assert.That(UserMessagePolicy.AcceptModelAuthoredResponse(
            Asked, draft, "Borra de tu memoria mi bebida favorita", null), Is.EqualTo(Asked));
    }

    [Test]
    public void TheForgetsActNamesItsScopeAndDatumNeverItsValue()
    {
        var forgotten = new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "exact",
            ["selector"] = "FAVORITE_DRINK",
            ["confirmationRequired"] = true,
        };
        string keys = Path.Combine(Path.GetTempPath(), "baxy-m2-" + Guid.NewGuid().ToString("N"));
        var protector = new MemoryOperationProtector(
            new BoundProtectedJsonCodec(new WindowsProtectedPayload(Path.Combine(keys, "private-payload.v1.key"))),
            Guid.NewGuid().ToString("D"));
        PreparedOperation prepared;
        try
        {
            prepared = protector.Prepare(new MemoryRoutedOperation("memory.forget", (JsonObject)forgotten.DeepClone()))
                .Prepared;
        }
        finally
        {
            if (Directory.Exists(keys))
            {
                Directory.Delete(keys, recursive: true);
            }
        }

        JsonNode cancelled = JsonNode.Parse(PrivateOperationNarration.CreateMemoryCancellationMessage(prepared, forgotten))!;
        JsonNode asked = JsonNode.Parse(PrivateOperationNarration.CreateMemoryConfirmationPrompt(prepared, false, forgotten))!;

        Assert.Multiple(() =>
        {
            Assert.That(cancelled["cancelledAction"]?["selector"]?.GetValue<string>(), Is.EqualTo("favorite_drink"));
            Assert.That(cancelled["cancelledAction"]?["scope"]?.GetValue<string>(), Is.EqualTo("exact"));
            Assert.That(asked["pendingAction"]?["selector"]?.GetValue<string>(), Is.EqualTo("favorite_drink"));
            Assert.That(asked["pendingAction"]?["value"], Is.Null);
        });
    }
}
