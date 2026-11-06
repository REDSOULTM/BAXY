using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The conductor (Baxy.exe --conductor, ProductConductorHost) mounts the product as the window does. Final6: it made the
/// view model without the view's channel, so BAXY's own readings (assistant.status) and the conversations asked by voice
/// (conversation.*) failed there as unavailable although the model chose them well.
/// </summary>
[TestFixture]
public sealed class ConductorProductTests
{
    // Uso 84 (AMD RX 7600): a mind still preparing 200 s after the start (its model reading its prompt prefix) is waited
    // for; once it is not preparing, the grace it was left runs out as before.
    [Test]
    public void TheConductorWaitsForAMindStillPreparingPastItsGrace()
    {
        DateTime start = new(2026, 11, 4, 0, 0, 0, DateTimeKind.Utc);
        DateTime deadline = start + ProductConductorHost.MindGrace;
        DateTime late = start.AddSeconds(200);

        Assert.That(ProductConductorHost.MindDeadline(deadline, late, preparing: true), Is.GreaterThan(late));
        Assert.That(ProductConductorHost.MindDeadline(deadline, late, preparing: false), Is.EqualTo(deadline));
        Assert.That(ProductConductorHost.MindDeadline(deadline, late, preparing: false), Is.LessThan(late));
    }
    // Before (the view model alone, as final6's conductor had it): unavailable. Mounted as the conductor mounts it: done.
    [TestCase("assistant.status", """{"scope":"internet"}""", false, "own_readings_unavailable")]
    [TestCase("assistant.status", """{"scope":"internet"}""", true, null)]
    [TestCase("conversation.rename", """{"title":"Plan de la semana"}""", false, "conversations_unavailable")]
    [TestCase("conversation.rename", """{"title":"Plan de la semana"}""", true, null)]
    public async Task TheConductorServesWhatTheWindowServes(string operation, string arguments, bool mounted,
        string? error)
    {
        using var fake = new FakeMind();
        fake.Script(ConversationVoiceTests.Calling(operation, (JsonObject)JsonNode.Parse(arguments)!));
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var telemetry = new FieldTelemetrySampler(static () => null))
        {
            FieldProductChannel? view = mounted ? ProductConductorHost.Mount(viewModel, telemetry, CancellationToken.None)
                : null;
            try
            {
                ViewModelHarness.AcceptTurns(viewModel);
                // The engine counts as running and the calls have their outbox, as at start (OwnReadingsTests).
                const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
                typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(viewModel.CoreClient, true);
                typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(viewModel.CoreClient,
                    Process.GetCurrentProcess());
                typeof(MainWindowViewModel).GetField("_retryableOperations", Private)!.SetValue(viewModel,
                    new RetryableOperationRegistry());
                await viewModel.SubmitAsync(new MissionInput("dime qué salió a internet", MissionInputSource.Text),
                    Stopwatch.GetTimestamp(), CancellationToken.None);

                JsonObject result = ConversationVoiceTests.Observation(fake);
                Assert.Multiple(() =>
                {
                    Assert.That((string?)result["status"], Is.EqualTo(mounted ? "completed" : "failed"));
                    Assert.That((string?)result["error"], Is.EqualTo(error));
                });
            }
            finally
            {
                if (view is not null)
                {
                    await view.DisposeAsync();
                }
            }
        }
    }
}
