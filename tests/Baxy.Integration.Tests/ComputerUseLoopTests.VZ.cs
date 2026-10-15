using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo VZ (imp3d imp-dc-voz, Normal, fable/estab-fase3 03e76b060): «en Discord entrá al canal Cotele» asked before
/// pressing «Cotele!!!😎, Canal de voz, Choche»; after «sí» the same mission pressed «Cotele!!!😎 (canal de voz), RED,
/// duración de la llamada: 0 m» in the server list and asked a second time. The act the person confirmed is theirs for
/// the rest of the mission; another act keeps its own question; in bypass nothing asks.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string VzSearchResult = "Cotele!!!😎, Canal de voz, Choche";
    private const string VzServerList = "Cotele!!!😎 (canal de voz), RED, duración de la llamada: 0 m";

    // The Discord window of the live run after the join (journal-caso, 02:05:42): the server list, the voice panel.
    private static JsonObject VzDiscord() => Window("Cotele!!!😎 | Choche - Discord", "Discord", 9676, true,
    [
        Control(5, "ListItem", VzSearchResult, "selected"),
        Control(7, "Hyperlink", VzServerList),
        Control(8, "Hyperlink", "General (canal de voz), RED"),
        Control(9, "Button", "Enviar"),
        Control(10, "Button", "Desconectar"),
    ]);

    // MissionEngine's policy in front of every act (R29BehindTheKernelsPolicy) in the mode given, with the second send
    // that carries the Kernel's token (MindPlanSession: ExecuteConfirmed).
    private static ComputerUseMission.Context VzBehindTheKernel(
        ComputerUseMission.Context inner, ConfirmationMode mode, List<string> asked, List<string> confirmed) => new()
        {
            Execute = (prepared, timeout, cancellation) =>
            {
                var definition = new OperationDefinition(ProductCatalog.GetRequired(prepared.OperationName));
                if (RiskPolicy.Evaluate(definition.Risk, mode, prepared.OperationName, prepared.Arguments)
                    != PolicyDecision.RequireConfirmation)
                {
                    return inner.Execute(prepared, timeout, cancellation);
                }

                asked.Add(prepared.Arguments.GetProperty("label").GetString()!);
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
            ExecuteConfirmed = (prepared, token, timeout, cancellation) =>
            {
                confirmed.Add(prepared.Arguments.GetProperty("label").GetString()!);
                return inner.Execute(prepared, timeout, cancellation);
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

    // Turn 1 asks for the search result, «sí» presses it (RecordConfirmedStep), and the mission resumes on the step the
    // model takes next.
    private async Task<(ComputerUseMission.Result First, ComputerUseMission.Result Resumed, Harness Harness)> VzConfirmThenPress(
        string secondLabel, int secondIndex, List<string> asked, List<string> confirmed)
    {
        int requests = 0;
        var harness = new Harness
        {
            Screen = _ => VzDiscord(),
            Mind = _ => ++requests switch
            {
                1 => Step("input.visible.click", new JsonObject { ["label"] = VzSearchResult, ["index"] = 5 }),
                2 => Step("input.visible.click", new JsonObject { ["label"] = secondLabel, ["index"] = secondIndex }),
                _ => Step("none", new JsonObject()),
            },
        };
        var arguments = new JsonObject { ["goal"] = "entrá al canal Cotele", ["application"] = "Discord" };
        PendingMindPlanExecution execution = Execution("en Discord entrá al canal Cotele", arguments);
        ComputerUseMission.Context context = VzBehindTheKernel(harness.Context(_root), ConfirmationMode.Normal, asked, confirmed);

        ComputerUseMission.Result first = await ComputerUseMission.RunAsync(context, execution, arguments, CancellationToken.None);
        Assert.That(first.Confirmation, Is.Not.Null, "the join is asked first");
        PreparedOperation pressed = first.Confirmation!.Prepared;
        using JsonDocument receipt = JsonDocument.Parse("""{"name":"Cotele!!!😎, Canal de voz, Choche","selected":true,"kind":"ListItem"}""");
        ComputerUseMission.RecordConfirmedStep(execution, pressed, new OperationResponse(
            ProtocolTypes.OperationResponse, pressed.InvocationId, pressed.MissionId, pressed.InvocationId,
            OperationStatuses.Completed, "{}", true, false, receipt.RootElement.Clone(), null));

        ComputerUseMission.Result resumed = await ComputerUseMission.RunAsync(context, execution, arguments, CancellationToken.None);
        return (first, resumed, harness);
    }

    [Test]
    public async Task VZ_ImpDcVoz_TheChannelConfirmedIsNotAskedAgainWhenTheMissionPressesItElsewhere()
    {
        var asked = new List<string>();
        var confirmed = new List<string>();

        (_, ComputerUseMission.Result resumed, Harness harness) = await VzConfirmThenPress(VzServerList, 7, asked, confirmed);

        Assert.Multiple(() =>
        {
            Assert.That(resumed.Confirmation, Is.Null, "the person already said yes to joining Cotele");
            Assert.That(asked, Is.EqualTo(new[] { VzSearchResult, VzServerList }), "the Kernel still asks for each invocation");
            Assert.That(confirmed, Is.EqualTo(new[] { VzServerList }), "answered with that invocation's own token");
            Assert.That(harness.Acts.Select(act => (string?)act.Arguments["label"]), Does.Contain(VzServerList));
        });
    }

    // Contracases: an act other than the one confirmed (sending, another voice channel) keeps its own question.
    [TestCase("Enviar", 9)]
    [TestCase("General (canal de voz), RED", 8)]
    public async Task VZ_ImpDcVoz_AnotherActAfterTheYesIsAskedItself(string label, int index)
    {
        var asked = new List<string>();
        var confirmed = new List<string>();

        (_, ComputerUseMission.Result resumed, Harness harness) = await VzConfirmThenPress(label, index, asked, confirmed);

        Assert.Multiple(() =>
        {
            Assert.That(resumed.Confirmation, Is.Not.Null);
            Assert.That(resumed.Confirmation?.Prepared.Arguments.GetProperty("label").GetString(), Is.EqualTo(label));
            Assert.That(confirmed, Is.Empty);
            Assert.That(harness.Acts.Select(act => (string?)act.Arguments["label"]), Does.Not.Contain(label));
        });
    }

    [Test]
    public async Task VZ_ImpDcVoz_InBypassNothingIsAsked()
    {
        int requests = 0;
        var harness = new Harness
        {
            Screen = _ => VzDiscord(),
            Mind = _ => ++requests switch
            {
                1 => Step("input.visible.click", new JsonObject { ["label"] = VzSearchResult, ["index"] = 5 }),
                2 => Step("input.visible.click", new JsonObject { ["label"] = VzServerList, ["index"] = 7 }),
                _ => Step("none", new JsonObject()),
            },
        };
        var asked = new List<string>();
        var confirmed = new List<string>();
        var arguments = new JsonObject { ["goal"] = "entrá al canal Cotele", ["application"] = "Discord" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            VzBehindTheKernel(harness.Context(_root), ConfirmationMode.Bypass, asked, confirmed),
            Execution("en Discord entrá al canal Cotele", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Confirmation, Is.Null);
            Assert.That(asked, Is.Empty);
            Assert.That(confirmed, Is.Empty);
            Assert.That(harness.Acts.Select(act => (string?)act.Arguments["label"]), Is.EqualTo(new[] { VzSearchResult, VzServerList }));
        });
    }
}
