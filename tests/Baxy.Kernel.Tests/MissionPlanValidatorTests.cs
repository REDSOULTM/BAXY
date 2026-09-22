using System.Text.Json;
using Baxy.Kernel.Planning;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class MissionPlanValidatorTests
{
    [Test]
    public void AcceptsAForwardOnlyTypedDag()
    {
        MissionPlanProposal plan = Plan(
            Step("open", "app.open", "Abre el Bloc de notas.", [], "literal", Json("""
                {"appId":"windows.notepad"}
                """)),
            Step(
                "resolve",
                "window.resolve",
                "Resuelve la ventana recién abierta.",
                ["open"],
                "literal",
                Json("""{"limit":1,"process":"notepad"}""")),
            Step(
                "focus",
                "window.focus",
                "Enfoca la identidad observada.",
                ["resolve"],
                "after_dependencies",
                null));

        Assert.That(() => MissionPlanValidator.Validate(plan), Throws.Nothing);
    }

    // MEME2053 «Tienes algun meme?»: the open defers its arguments to the verified download.
    [Test]
    public void AcceptsAFileOpenDeferredToTheDownloadThatWroteIt()
    {
        MissionPlanProposal plan = Plan(
            Step("download", "web.download", "Descarga la primera imagen que lista el buscador.", [], "literal", Json("""
                {"query":"meme","folder":"pictures"}
                """)),
            Step("open", "file.open", "Abre la imagen descargada.", ["download"], "after_dependencies", null));

        Assert.That(() => MissionPlanValidator.Validate(plan), Throws.Nothing);
        Assert.That(MissionPlanValidator.DependencyAuthorityFields("file.open"), Is.EqualTo(new[] { "folder", "name" }));
    }

    [Test]
    public void RejectsPrivateAndInternalOperations()
    {
        MissionPlanProposal privatePlan = Plan(
            Step("save", "memory.save", "Guarda memoria.", [], "literal", Json("{}")));
        MissionPlanProposal internalPlan = Plan(
            Step("status", "app.status", "Lee salud interna.", [], "literal", Json("{}")));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MissionPlanValidator.Validate(privatePlan),
                Throws.TypeOf<MissionPlanValidationException>());
            Assert.That(
                () => MissionPlanValidator.Validate(internalPlan),
                Throws.TypeOf<MissionPlanValidationException>());
        });
    }

    [Test]
    public void RejectsUnknownAndSchemaInvalidOperations()
    {
        MissionPlanProposal unknown = Plan(
            Step("one", "unknown.tool", "No existe.", [], "literal", Json("{}")));
        MissionPlanProposal invalidArguments = Plan(
            Step("one", "audio.volume", "Cambia volumen.", [], "literal", Json("""
                {"level":101}
                """)));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MissionPlanValidator.Validate(unknown),
                Throws.TypeOf<MissionPlanValidationException>());
            Assert.That(
                () => MissionPlanValidator.Validate(invalidArguments),
                Throws.TypeOf<MissionPlanValidationException>());
        });
    }

    [Test]
    public void RejectsBackwardUnknownDuplicateAndSelfDependencies()
    {
        MissionPlanProposal unknown = Plan(
            Step(
                "one",
                "audio.status",
                "Lee audio.",
                ["later"],
                "after_dependencies",
                null),
            Step("later", "system.time", "Lee hora.", [], "literal", Json("{}")));
        MissionPlanProposal duplicate = Plan(
            Step("one", "audio.status", "Lee audio.", [], "literal", Json("{}")),
            Step(
                "two",
                "system.time",
                "Lee hora.",
                ["one", "one"],
                "after_dependencies",
                null));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MissionPlanValidator.Validate(unknown),
                Throws.TypeOf<MissionPlanValidationException>());
            Assert.That(
                () => MissionPlanValidator.Validate(duplicate),
                Throws.TypeOf<MissionPlanValidationException>());
        });
    }

    [Test]
    public void RequiresDependenciesForDeferredGrounding()
    {
        MissionPlanProposal plan = Plan(
            Step(
                "one",
                "window.focus",
                "Enfoca una ventana.",
                [],
                "after_dependencies",
                null));

        Assert.That(
            () => MissionPlanValidator.Validate(plan),
            Throws.TypeOf<MissionPlanValidationException>());
    }

    [Test]
    public void DependencyBoundOperationsRequireTheCorrectProducerFamily()
    {
        MissionPlanProposal valid = Plan(
            Step(
                "capture",
                "capture.screenshot",
                "Captura la pantalla.",
                [],
                "literal",
                Json("{}")),
            Step(
                "read",
                "ocr.read",
                "Lee la captura verificada.",
                ["capture"],
                "after_dependencies",
                null));
        MissionPlanProposal wrongProducer = Plan(
            Step(
                "create",
                "note.create",
                "Crea una nota.",
                [],
                "literal",
                Json("""{"title":"Prueba","content":"Texto"}""")),
            Step(
                "read",
                "ocr.read",
                "No debe aceptar una nota como captura.",
                ["create"],
                "after_dependencies",
                null));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MissionPlanValidator.Validate(valid),
                Throws.Nothing);
            Assert.That(
                () => MissionPlanValidator.Validate(wrongProducer),
                Throws.TypeOf<MissionPlanValidationException>());
        });
    }

    [TestCase("notification.dismiss", "notification.list.due")]
    [TestCase("reminder.delete", "reminder.resolve.exact")]
    [TestCase("filesystem.read.text", "filesystem.search")]
    [TestCase("filesystem.read.text", "filesystem.list")]
    public void DeferredIdentityConsumersRequireTheirResolvers(
        string consumer,
        string producer)
    {
        MissionPlanProposal wrongProducer = Plan(
            Step("time", "system.time", "Lee la hora.", [], "literal", Json("{}")),
            Step(
                "mutate",
                consumer,
                "Aplica el cambio a la identidad resuelta.",
                ["time"],
                "after_dependencies",
                null));
        MissionPlanProposal correctProducer = Plan(
            Step(
                "resolve",
                producer,
                "Resuelve una identidad exacta.",
                [],
                "literal",
                producer switch
                {
                    "notification.list.due" or "filesystem.list" => Json("{}"),
                    "filesystem.search" => Json("""{"query":"Prueba"}"""),
                    _ => Json("""{"title":"Prueba"}"""),
                }),
            Step(
                "mutate",
                consumer,
                "Aplica el cambio a la identidad resuelta.",
                ["resolve"],
                "after_dependencies",
                null));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MissionPlanValidator.Validate(wrongProducer),
                Throws.TypeOf<MissionPlanValidationException>());
            Assert.That(
                () => MissionPlanValidator.Validate(correctProducer),
                Throws.Nothing);
        });
    }

    [Test]
    public void ConditionalGroundingAcceptsOnlyItsDeclaredProducerFamily()
    {
        MissionPlanProposal valid = Plan(
            Step(
                "create",
                "note.create",
                "Crea una nota.",
                [],
                "literal",
                Json("""{"title":"Prueba","content":"Texto"}""")),
            Step(
                "read",
                "note.read",
                "Lee la nota creada.",
                ["create"],
                "after_dependencies",
                null));
        MissionPlanProposal wrongProducer = Plan(
            Step("time", "system.time", "Lee la hora.", [], "literal", Json("{}")),
            Step(
                "read",
                "note.read",
                "No debe usar la hora como identidad de nota.",
                ["time"],
                "after_dependencies",
                null));
        MissionPlanProposal unknownDataFlow = Plan(
            Step("time", "system.time", "Lee la hora.", [], "literal", Json("{}")),
            Step(
                "status",
                "system.status",
                "No existe un contrato de datos entre estos pasos.",
                ["time"],
                "after_dependencies",
                null));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MissionPlanValidator.Validate(valid),
                Throws.Nothing);
            Assert.That(
                () => MissionPlanValidator.Validate(wrongProducer),
                Throws.TypeOf<MissionPlanValidationException>());
            Assert.That(
                () => MissionPlanValidator.Validate(unknownDataFlow),
                Throws.TypeOf<MissionPlanValidationException>());
        });
    }

    [Test]
    public void RejectsBidiControlAndOversizedPlans()
    {
        MissionPlanProposal bidi = new(
            1,
            "abre la app\u202e",
            [Step("one", "audio.status", "Lee audio.", [], "literal", Json("{}"))]);
        MissionPlanProposal oversized = new(
            1,
            "Consulta el estado.",
            Enumerable.Range(0, MissionPlanValidator.MaximumSteps + 1)
                .Select(index => Step(
                    $"s{index}",
                    "audio.status",
                    "Lee audio.",
                    [],
                    "literal",
                    Json("{}")))
                .ToArray());

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MissionPlanValidator.Validate(bidi),
                Throws.TypeOf<MissionPlanValidationException>());
            Assert.That(
                () => MissionPlanValidator.Validate(oversized),
                Throws.TypeOf<MissionPlanValidationException>());
        });
    }

    private static MissionPlanProposal Plan(params MissionPlanStepProposal[] steps) =>
        new(1, "Completa esta misión compuesta.", steps);

    private static MissionPlanStepProposal Step(
        string id,
        string operation,
        string purpose,
        IReadOnlyList<string> dependencies,
        string mode,
        JsonElement? arguments) =>
        new(id, operation, purpose, dependencies, mode, arguments);

    private static JsonElement Json(string value)
    {
        using JsonDocument document = JsonDocument.Parse(value);
        return document.RootElement.Clone();
    }
}
