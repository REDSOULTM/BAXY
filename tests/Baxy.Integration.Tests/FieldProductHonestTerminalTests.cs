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
}
