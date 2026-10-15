using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización D (the owner's decision of 2026-10-10, «no molestar» in its simple form) and its revision (H2, H6):
/// the mission tells the Core that it runs while its loop does and that it ended at every end (reached, stopped,
/// waiting for a confirmation, cancelled, thrown); the Core takes the mission's window to the front before each act and
/// gives the person's window the front back once the mission ended, behind an act still in flight (ForegroundSequenceTests).
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    // What the Core is told, in order, with the acts in between.
    private sealed class FrontSignal : IMissionFrontSignal
    {
        internal List<string> Events { get; } = [];

        public void MissionBegins() => Events.Add("begin");

        public void MissionEnds() => Events.Add("end");
    }

    private static Harness FrontHarness(FrontSignal signal, Func<ComputerUseStepRequest, MindComputerUseStep?> mind) => new()
    {
        Screen = _ =>
        {
            JsonObject view = Window("Spotify Premium", "Spotify", 41, true, [Control(0, "Button", "Buscar"), Control(1, "Button", "Inicio")]);
            view["window"]!["hwnd"] = 500;
            return view;
        },
        Mind = mind,
        Receipt = (operation, _) =>
        {
            signal.Events.Add(operation);
            return new JsonObject { ["surfaceChanged"] = true };
        },
    };

    private static JsonObject FrontArguments(string check) => new()
    {
        ["goal"] = "ir a buscar",
        ["application"] = "Spotify",
        ["successCheck"] = check,
    };

    // Reached, or stopped without a step after acting: the mission runs around its acts and ends once, after them.
    [TestCase(true, TestName = "reached: begun before the act, ended after it")]
    [TestCase(false, TestName = "stopped: begun before the act, ended after it")]
    public async Task TheMissionRunsAroundItsActsAndEndsOnceAfterThem(bool reach)
    {
        var signal = new FrontSignal();
        Harness harness = FrontHarness(signal, request => request.History.Count == 0
            ? Step("input.visible.click", new JsonObject { ["label"] = "Buscar" })
            : new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible"));
        JsonObject arguments = FrontArguments(reach ? "stepDone:input.visible.click:buscar" : "title:biblioteca");

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, front: signal), Execution("andá a buscar en spotify", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.EqualTo(reach));
            Assert.That((long?)harness.Acts.Single().Arguments["window"], Is.EqualTo(500), "the act names the mission's window");
            Assert.That(signal.Events, Is.EqualTo(new[] { "begin", "input.visible.click", "end" }));
        });
    }

    // H6: a mission that waits for the person's confirmation ends too (the person answers in their own window).
    [Test]
    public async Task AMissionWaitingForAConfirmationEnds()
    {
        var signal = new FrontSignal();
        var harness = new Harness
        {
            Screen = _ => R29Obs(),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Iniciar Transmisión", ["index"] = 46 }),
        };
        var asked = new List<string>();
        var arguments = new JsonObject { ["goal"] = "vale, vuelve a activarlo", ["application"] = "OBS Studio (64bit)" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            R29BehindTheKernelsPolicy(harness.Context(_root, front: signal), asked), Execution("vale, vuelve a activarlo", arguments),
            arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Confirmation, Is.Not.Null);
            Assert.That(signal.Events, Is.EqualTo(new[] { "begin", "end" }));
        });
    }

    // H6: a turn cancelled after an act, and an act that throws, end the mission as well.
    [TestCase(false, TestName = "cancelled after the act: ended")]
    [TestCase(true, TestName = "an act that throws: ended")]
    public void AMissionCancelledOrThrownEnds(bool throws)
    {
        var signal = new FrontSignal();
        using var cancel = new CancellationTokenSource();
        Harness harness = FrontHarness(signal, _ => Step("input.visible.click", new JsonObject { ["label"] = "Buscar" }));
        harness.Receipt = (operation, _) =>
        {
            signal.Events.Add(operation);
            if (throws)
            {
                throw new NotSupportedException("the act broke");
            }

            cancel.Cancel();
            return new JsonObject { ["surfaceChanged"] = true };
        };
        JsonObject arguments = FrontArguments("title:biblioteca");

        Exception? thrown = Assert.CatchAsync(async () => await ComputerUseMission.RunAsync(
            harness.Context(_root, front: signal), Execution("andá a buscar en spotify", arguments), arguments, cancel.Token));

        Assert.Multiple(() =>
        {
            Assert.That(thrown, throws ? Is.TypeOf<NotSupportedException>() : Is.InstanceOf<OperationCanceledException>());
            Assert.That(signal.Events, Is.EqualTo(new[] { "begin", "input.visible.click", "end" }));
        });
    }

    // Contracase: a mission that only looks runs and ends without an act, so the Core takes no front for it.
    [Test]
    public async Task AMissionThatOnlyLooksSendsNoAct()
    {
        var signal = new FrontSignal();
        Harness harness = FrontHarness(signal, _ =>
            new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible"));
        JsonObject arguments = FrontArguments("title:biblioteca");

        _ = await ComputerUseMission.RunAsync(
            harness.Context(_root, front: signal), Execution("mirá spotify", arguments), arguments, CancellationToken.None);

        Assert.That(signal.Events, Is.EqualTo(new[] { "begin", "end" }));
    }
}
