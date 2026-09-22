using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class FieldProductHonestTerminalTests
{
    [TearDown]
    public void TearDown() => FieldPublicationInjection.Reset();

    [Test]
    public void AlreadyPublishedBaxyTextIsNotSilence()
    {
        JsonObject[] events =
        [
            new()
            {
                ["type"] = "activity",
                ["entry"] = new JsonObject
                {
                    ["src"] = "BAXY",
                    ["msg"] = "The local clock shows 20:27.",
                },
            },
        ];

        Assert.That(
            ProductConductor.LastPublishedBaxyText(events),
            Is.EqualTo("The local clock shows 20:27."));
    }

    [Test]
    public async Task SilenceAfterAdmissionIsADetectableNonSuccess()
    {
        await using MainWindowViewModel viewModel = ReadyViewModel();
        await using ProductConductor conductor = ProductConductor.Create(
            viewModel,
            CancellationToken.None);
        FieldPublicationInjection.Mode = FieldPublicationInjectionMode.Silence;

        ProductTurnResult result = await conductor.TurnAsync(
            "Hola, ¿qué puedes hacer?",
            TimeSpan.FromMilliseconds(400),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Terminal, Is.EqualTo(ProductTurnTerminal.Silence));
            Assert.That(result.FinalText, Is.Null);
            Assert.That(result.TimedOut, Is.True);
            Assert.That(result.Diagnostic, Does.Contain("timeout"));
            Assert.That(result.Posterior.IsBusy, Is.False);
            Assert.That(
                result.PublicEvents.Any(static item =>
                    (string?)item["type"] == "activity"
                    && (string?)item["entry"]?["src"] == "BAXY"),
                Is.False);
        });
    }

    [Test]
    public async Task FilteredPublicationIsADetectableNonSuccess()
    {
        await using MainWindowViewModel viewModel = ReadyViewModel();
        await using ProductConductor conductor = ProductConductor.Create(
            viewModel,
            CancellationToken.None);
        FieldPublicationInjection.Mode = FieldPublicationInjectionMode.Filter;
        FieldHttpResponse session = await conductor.NewSessionAsync();
        IReadOnlyList<System.Text.Json.Nodes.JsonObject> events =
            conductor.Sink.Snapshot();
        ProductTurnResult later = await conductor.TurnAsync(
            "Hola",
            TimeSpan.FromSeconds(2),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(session.Status, Is.EqualTo(200));
            Assert.That(
                events.Any(static item => (string?)item["type"] == "publication_discard"),
                Is.True);
            Assert.That(
                events.Any(static item =>
                    (string?)item["type"] == "activity"
                    && (string?)item["entry"]?["src"] == "BAXY"),
                Is.False);
            Assert.That(
                viewModel.Messages.Any(static message => !message.IsUser),
                Is.True);
            Assert.That(viewModel.HasPendingPlan, Is.False);
            Assert.That(later.FinalText, Is.Null);
            Assert.That(later.Terminal, Is.Not.EqualTo(ProductTurnTerminal.PublishedFinal));
            Assert.That(viewModel.HasPendingPlan, Is.EqualTo(later.Posterior.HasPendingPlan));
        });
    }

    [Test]
    public async Task AcceptanceWithoutPublishedFinalIsADetectableNonSuccess()
    {
        await using MainWindowViewModel viewModel = ReadyViewModel();
        await using ProductConductor conductor = ProductConductor.Create(
            viewModel,
            CancellationToken.None);
        ProductTurnResult result = await conductor.TurnAsync(
            "Hola",
            TimeSpan.FromSeconds(2),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(
                result.Terminal,
                Is.EqualTo(ProductTurnTerminal.AcceptedWithoutFinal));
            Assert.That(result.FinalText, Is.Null);
            Assert.That(result.Admission.Status, Is.EqualTo(200));
            Assert.That(
                result.PublicEvents.Any(static item =>
                    (string?)item["type"] == "activity"
                    && (string?)item["entry"]?["src"] == "BAXY"),
                Is.False);
        });
    }

    private static MainWindowViewModel ReadyViewModel()
    {
        var viewModel = new MainWindowViewModel();
        PropertyInfo ready = typeof(MainWindowViewModel).GetProperty(
            nameof(MainWindowViewModel.IsReady))!;
        ready.SetValue(viewModel, true);
        return viewModel;
    }

    [TestCase(false)]
    [TestCase(true)]
    public async Task CompositionFailureProjectsARecoverableStateWithoutInventingProse(
        bool recoverWithNewTurn)
    {
        await using MainWindowViewModel viewModel = ReadyViewModel();
        var sink = new CollectingFieldEventSink();
        await using var telemetry = new FieldTelemetrySampler();
        await using var channel = new FieldProductChannel(
            viewModel, sink, telemetry, CancellationToken.None);
        var pending = new PendingModelMessage(
            new UserMessageDraft("{}", "status", null),
            "What time is it?", new JsonObject(), "t0");

        // Exercise the queue's exhaustion/publication callbacks at the actual
        // view-model boundary. No server or invented failure activity is needed.
        await InvokeCallbackAsync(viewModel, "PublishCompositionFailureAsync",
            pending, "retry_exhausted");
        Assert.Multiple(() =>
        {
            Assert.That(LastState(sink.Snapshot()), Is.EqualTo("error"));
            Assert.That(LastState(channel.CreateSocketBootstrap()), Is.EqualTo("error"));
            Assert.That(viewModel.IsInputEnabled, Is.True);
            Assert.That(viewModel.HasCompositionError, Is.True);
            Assert.That(sink.Snapshot().Any(item =>
                (string?)item["type"] == "composition_failed"
                && (string?)item["cause"] == "retry_exhausted"), Is.True);
            // d8eb8836 (owner session 2026-09-21 16:08): a failed composition leaves
            // exactly one BAXY line, the fixed fallback with its diagnostic code;
            // nothing else is written and no prose is invented.
            List<JsonObject> activity = sink.Snapshot().Where(item =>
                (string?)item["type"] == "activity").ToList();
            Assert.That(activity, Has.Count.EqualTo(1));
            Assert.That((string?)activity[0]["entry"]?["src"], Is.EqualTo("BAXY"));
            Assert.That((string?)activity[0]["entry"]?["msg"],
                Is.EqualTo(MainWindowViewModel.CompositionFailureFallback("retry_exhausted")));
        });

        if (recoverWithNewTurn)
        {
            viewModel.BeginTurnPresentation("What time is it?", DateTimeOffset.UtcNow);
            Assert.That(LastState(sink.Snapshot()), Is.EqualTo("thinking"));
        }
        else
        {
            await InvokeCallbackAsync(viewModel, "PublishComposedMessageAsync",
                "The clock shows 06:39.", null, pending);
            Assert.That(LastState(sink.Snapshot()), Is.EqualTo("idle"));
            Assert.That(ProductConductor.LastPublishedBaxyText(sink.Snapshot()),
                Is.EqualTo("The clock shows 06:39."));
        }

        Assert.That(viewModel.HasCompositionError, Is.False);
        Assert.That(LastState(channel.CreateSocketBootstrap()), Is.Not.EqualTo("error"));
    }

    private static string? LastState(IReadOnlyList<JsonObject> events) =>
        (string?)events.Last(item => (string?)item["type"] == "state")["value"];

    private static async Task InvokeCallbackAsync(
        MainWindowViewModel viewModel, string methodName, params object?[] arguments)
    {
        MethodInfo callback = typeof(MainWindowViewModel).GetMethod(
            methodName, BindingFlags.Instance | BindingFlags.NonPublic)!;
        await (Task)callback.Invoke(viewModel, arguments)!;
    }
}
