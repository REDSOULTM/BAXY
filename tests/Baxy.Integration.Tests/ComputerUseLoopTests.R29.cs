using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 29, «lo que sale al mundo se confirma»: the loop over the real view of the live pass r27, case v3-53 («en obs
/// silencia el audio del escritorio» → «vale, vuelve a activarlo»), where the model pressed OBS's «Iniciar
/// Transmisión» and nobody was asked. Each act goes through the Kernel's own policy with its exact arguments, as
/// MissionEngine does: going live stops the mission on a confirmation before anything is pressed.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    // v3-53, turn 2, model call of step 2 (model_calls.jsonl): OBS as the model saw it, with its real names.
    private static JsonObject R29Obs() => Window("OBS 32.0.2 - Perfil: Sin Título - Escenas: Sin Título", "obs64", 38800, true,
    [
        Control(2, "CheckBox", "Sólo fuentes activas", "on"),
        Control(4, "CheckBox", "Mezcla monoaural para 'Audio del escritorio'", "off"),
        Control(5, "Slider", "Balance para 'Audio del escritorio'", string.Empty, "50"),
        Control(6, "ComboBox", "Monitorización de audio para 'Audio del escritorio'", "collapsed", "Monitorización desactivada"),
        Control(21, "MenuItem", "Archivo (F)", "collapsed"),
        Control(22, "MenuItem", "Editar", "collapsed"),
        Control(29, "ListItem", "Escena", "selected focused"),
        Control(32, "Button", "Abrir filtros de la escena"),
        Control(33, "Button", "Mover arriba"),
        Control(45, "Button", "Añadir transición configurable"),
        Control(46, "Button", "Iniciar Transmisión"),
        Control(47, "Button", "Iniciar Grabación"),
        Control(48, "Button", "Iniciar Cámara Virtual"),
        Control(52, "Window", "Propiedades de Audio avanzadas", "focused"),
    ], "Iniciar Transmisión", "300 ms", "Iniciar Grabación");

    // The harness's context with the Kernel's policy in front of every act, as MissionEngine evaluates it: an act
    // that asks is answered with its confirmation challenge and never reaches the provider.
    private static ComputerUseMission.Context R29BehindTheKernelsPolicy(ComputerUseMission.Context inner, List<string> asked) => new()
    {
        Execute = (prepared, timeout, cancellation) =>
        {
            var definition = new OperationDefinition(ProductCatalog.GetRequired(prepared.OperationName));
            PolicyDecision policy = RiskPolicy.Evaluate(
                definition.Risk, ConfirmationMode.Normal, prepared.OperationName, prepared.Arguments);
            if (policy != PolicyDecision.RequireConfirmation)
            {
                return inner.Execute(prepared, timeout, cancellation);
            }

            asked.Add(prepared.Arguments.GetRawText());
            return Task.FromResult(new OperationResponse(
                ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId, prepared.InvocationId,
                OperationStatuses.Pending, "Confirmación requerida.", false, false,
                JsonSerializer.SerializeToElement(new
                {
                    version = 1,
                    token = Convert.ToBase64String(new byte[32]).TrimEnd('='),
                    expiresAtUtc = DateTimeOffset.UtcNow.AddMinutes(2)
                        .ToString("O", System.Globalization.CultureInfo.InvariantCulture),
                    reconciliationRequired = false,
                }), "confirmation_required"));
        },
        Decide = inner.Decide,
        Registry = inner.Registry,
        MarkResolved = inner.MarkResolved,
        SetStatus = inner.SetStatus,
        LabelTranslations = inner.LabelTranslations,
        TypedInSession = inner.TypedInSession,
        NowMs = inner.NowMs,
        Delay = inner.Delay,
        Front = inner.Front,
    };

    [Test]
    public async Task R29_V3_53_TheModelsClickOnGoingLiveStopsOnAConfirmationAndPressesNothing()
    {
        var harness = new Harness
        {
            Screen = _ => R29Obs(),
            // The model's own reply in the live pass: {"act":"click","i":46}, which the mind names by the control.
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Iniciar Transmisión", ["index"] = 46 }),
        };
        var asked = new List<string>();
        var arguments = new JsonObject { ["goal"] = "vale, vuelve a activarlo", ["application"] = "OBS Studio (64bit)" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            R29BehindTheKernelsPolicy(harness.Context(_root), asked), Execution("vale, vuelve a activarlo", arguments), arguments,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Confirmation, Is.Not.Null, "the mission waits on the person's answer");
            Assert.That(result.Response, Is.Null, "and has no outcome yet");
            Assert.That(harness.Acts, Is.Empty, "nothing was pressed");
            Assert.That(asked, Has.Count.EqualTo(1));
            Assert.That(result.Confirmation?.Prepared.OperationName, Is.EqualTo("input.visible.click"));
            Assert.That(
                result.Confirmation?.Prepared.Arguments.GetProperty("label").GetString(), Is.EqualTo("Iniciar Transmisión"),
                "bound to the very click it asked about");
        });
    }

    // Contracases on the same screen: the buttons that send nothing out are pressed with no question (recording
    // writes a file on the disk; a scene's filters are a window of the application).
    [TestCase("Iniciar Grabación", 47)]
    [TestCase("Abrir filtros de la escena", 32)]
    [TestCase("Editar", 22)]
    public async Task R29_V3_53_AnOrdinaryButtonOfTheSameScreenIsPressedWithoutAsking(string label, int index)
    {
        int requests = 0;
        var harness = new Harness
        {
            Screen = _ => R29Obs(),
            Mind = _ => ++requests == 1
                ? Step("input.visible.click", new JsonObject { ["label"] = label, ["index"] = index })
                : Step("none", new JsonObject()),
        };
        var asked = new List<string>();
        var arguments = new JsonObject { ["goal"] = "vale, vuelve a activarlo", ["application"] = "OBS Studio (64bit)" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            R29BehindTheKernelsPolicy(harness.Context(_root), asked), Execution("vale, vuelve a activarlo", arguments), arguments,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Confirmation, Is.Null);
            Assert.That(asked, Is.Empty);
            Assert.That(harness.Acts.Select(act => (string?)act.Arguments["label"]), Is.EqualTo(new[] { label }));
        });
    }
}
