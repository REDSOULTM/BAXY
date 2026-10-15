using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class CoreDisconnectRecoveryViewModelTests
{
    // 2026-09-28: baxy-core ended during «captura la ventana activa». The App kept
    // the plan pending with input disabled, and every later turn, «cancelar» and a
    // new session got agent_not_ready until it was closed. A lost core is said once,
    // restarted without its stale plan, and the next turn is answered.
    [Test]
    public async Task LostCoreWithAPendingPlanRestartsWithoutThePlanAndAnswersTheNextTurn()
    {
        string root = PrivateDataRootTestSupport.NewPath("core-disconnect-recovery");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);

        try
        {
            await using var viewModel = new MainWindowViewModel(
                static route => route.ResolveStandaloneOperation());
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.That(viewModel.IsReady, Is.True);

            MindPlanSession plans = GetPrivateField<MindPlanSession>(viewModel, "_mindPlans");
            plans.Begin(new PendingMindPlanExecution(
                "captura la ventana activa",
                [new MindPlanStep("capture", "capture.active.window", "Captura la ventana activa.",
                    [], "literal", new JsonObject())]));
            Assert.That(viewModel.HasPendingPlan, Is.True);

            Process lostCore = CoreProcess(viewModel);
            int lostCoreId = lostCore.Id;
            int welcomes = CountWelcomes(viewModel);
            Assert.That(welcomes, Is.EqualTo(1));
            lostCore.Kill();

            var deadline = Stopwatch.StartNew();
            while (deadline.Elapsed < TimeSpan.FromSeconds(60)
                && !(viewModel.IsInputEnabled && CoreProcessOrNull(viewModel)?.Id is { } id && id != lostCoreId))
            {
                await Task.Delay(50);
            }

            await viewModel.WaitForCoreRecoveryAsync();
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True, "the core was not restarted");
                Assert.That(viewModel.IsInputEnabled, Is.True);
                Assert.That(viewModel.HasStartupError, Is.False);
                Assert.That(viewModel.HasPendingPlan, Is.False);
                Assert.That(CoreProcess(viewModel).Id, Is.Not.EqualTo(lostCoreId));
                Assert.That(viewModel.Messages, Has.Some.Matches<ConversationMessage>(message =>
                    !message.IsUser && message.Body.Contains("core_disconnected", StringComparison.Ordinal)));
                Assert.That(CountWelcomes(viewModel), Is.EqualTo(welcomes),
                    "a recovered core continues the conversation without greeting again");
            });

            int previousCount = viewModel.Messages.Count;
            viewModel.Draft = "qué hora es";
            await viewModel.SubmitAsync(CancellationToken.None);
            ConversationMessage answer = viewModel.Messages.Skip(previousCount).Last();
            Assert.Multiple(() =>
            {
                Assert.That(answer.IsUser, Is.False);
                Assert.That(answer.Body, Does.Contain("system.time"), answer.Body);
                Assert.That(answer.Body, Does.Contain("\"polarity\":\"success\""), answer.Body);
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static int CountWelcomes(MainWindowViewModel viewModel) =>
        viewModel.Messages.Count(message =>
            !message.IsUser && message.Body.Contains("\"welcome\"", StringComparison.Ordinal));

    private static Process CoreProcess(MainWindowViewModel viewModel) =>
        CoreProcessOrNull(viewModel) ?? throw new AssertionException("The view model has no core process.");

    private static Process? CoreProcessOrNull(MainWindowViewModel viewModel)
    {
        CoreProcessClient? client = GetPrivateField<CoreProcessClient?>(viewModel, "_coreClient");
        return client is null ? null : GetPrivateField<Process?>(client, "_process");
    }

    private static T GetPrivateField<T>(object owner, string name)
    {
        FieldInfo? field = owner.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic);
        Assert.That(field, Is.Not.Null, name);
        return (T)field!.GetValue(owner)!;
    }
}
