using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// r22 (2026-10-09): the mind's model could not start (another llama-server held ~4 GB of a 6 GB GPU), the
/// catalog reply was a bare runtime failure, the App retried every minute and turns ended in silence. The cause
/// now crosses the catalog reply, is said from data, and a turn sent meanwhile is told at once.
/// </summary>
[TestFixture]
public sealed class MindStartupHonestTests
{
    private static readonly string[] Causes =
        ["vram_insuficiente", "ram_insuficiente", "proceso_salio", "tiempo", "iniciando"];

    [Test]
    public void TheCatalogReplyCarriesTheStableCause()
    {
        var reply = new JsonObject
        {
            ["type"] = "error",
            ["id"] = "1",
            ["code"] = "request_failed",
            ["message"] = "request_runtime_failure",
            ["startup"] = new JsonObject
            {
                ["cause"] = "proceso_salio",
                ["exitCode"] = 3221225477L,
                ["tail"] = new JsonArray("main: exiting"),
            },
        };

        MindStartupFailure? failure = MindStartupFailure.FromReply(reply);

        Assert.Multiple(() =>
        {
            Assert.That(failure, Is.EqualTo(new MindStartupFailure("proceso_salio", 3221225477L)));
            Assert.That(failure!.TraceLabel, Is.EqualTo("proceso_salio.3221225477"));
            Assert.That(ShellTrace.SanitizeLabel(failure.TraceLabel), Is.EqualTo(failure.TraceLabel));
            Assert.That(new MindStartupFailure("vram_insuficiente", 1).TraceLabel, Is.EqualTo("vram_insuficiente"));
        });
    }

    [Test]
    public void AReadyCatalogOrAnUnknownCauseCarriesNoFailure()
    {
        Assert.Multiple(() =>
        {
            Assert.That(MindStartupFailure.FromReply(new JsonObject { ["type"] = "catalog.ready", ["count"] = 3 }), Is.Null);
            Assert.That(MindStartupFailure.FromReply(new JsonObject
            {
                ["type"] = "error",
                ["startup"] = new JsonObject { ["cause"] = "C:\\Users\\someone" },
            }), Is.Null);
            Assert.That(MindStartupFailure.FromReply(new JsonObject { ["type"] = "error", ["code"] = "request_failed" }), Is.Null);
            Assert.That(MindStartupFailure.FromReply(null), Is.Null);
        });
    }

    [Test]
    public void RetriesWaitLongerEachTimeUpToOneMinute()
    {
        double[] seconds = Enumerable.Range(1, 6)
            .Select(failures => MainWindowViewModel.MindRetryDelay(failures).TotalSeconds)
            .ToArray();

        Assert.That(seconds, Is.EqualTo(new double[] { 10, 20, 40, 60, 60, 60 }));
    }

    [Test]
    public void APersonsTurnRetriesADownMindAtOnce()
    {
        DateTime now = new(2026, 10, 9, 13, 0, 0, DateTimeKind.Utc);
        DateTime later = now.AddSeconds(60);

        Assert.Multiple(() =>
        {
            Assert.That(MainWindowViewModel.MindRetryDue(failed: true, now, later, personTurn: true), Is.True,
                "the person asking does not wait for the scheduled attempt");
            Assert.That(MainWindowViewModel.MindRetryDue(failed: true, now, later, personTurn: false), Is.False,
                "the background queue still waits");
            Assert.That(MainWindowViewModel.MindRetryDue(failed: true, later, later, personTurn: false), Is.True);
            Assert.That(MainWindowViewModel.MindRetryDue(failed: false, later, now, personTurn: true), Is.False,
                "a mind starting or ready is never started again");
        });
    }

    [Test]
    public void EveryCauseHasItsDataSentenceInBothLanguages()
    {
        Assert.Multiple(() =>
        {
            foreach (string cause in Causes)
            {
                string? spanish = OperationFloor.MindStartupSentence(cause, english: false);
                string? english = OperationFloor.MindStartupSentence(cause, english: true);
                Assert.That(spanish, Is.Not.Null.And.Not.Empty, cause);
                Assert.That(english, Is.Not.Null.And.Not.Empty, cause);
                Assert.That(spanish, Is.Not.EqualTo(english), cause);
            }

            Assert.That(OperationFloor.MindStartupSentence(null, english: false), Is.Null);
            Assert.That(OperationFloor.MindStartupSentence("clarification", english: false), Is.Null);
            Assert.That(
                OperationFloor.MindStartupSentence("vram_insuficiente", english: false),
                Is.Not.EqualTo(OperationFloor.MindStartupSentence("tiempo", english: false)));
        });
    }

    [Test]
    public void ATurnTheDownMindCouldNotReadIsToldWithTheCause()
    {
        string facts = TurnVisibleFacts.Failure(
            "mind_unavailable",
            new JsonObject { ["startup"] = "vram_insuficiente" });
        var pending = new PendingModelMessage(
            new UserMessageDraft(facts, "error", null), "abre Paint", new JsonObject(), "t0");

        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.DeciderCouldNotRead(facts), Is.True);
            Assert.That(OperationFloor.MindStartupCause(facts), Is.EqualTo("vram_insuficiente"));
            Assert.That(
                MainWindowViewModel.CompositionFailureFallback(pending, "composer_unavailable"),
                Is.EqualTo(OperationFloor.MindStartupSentence("vram_insuficiente", english: false)));
        });
    }

    [Test]
    public void AFailureWithoutAStartupCauseKeepsTheUsualLine()
    {
        var pending = new PendingModelMessage(
            new UserMessageDraft(TurnVisibleFacts.Failure("mind_unavailable"), "error", null),
            "abre Paint",
            new JsonObject(),
            "t0");

        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.MindStartupCause(TurnVisibleFacts.Failure("mind_unavailable")), Is.Null);
            Assert.That(
                MainWindowViewModel.CompositionFailureFallback(pending, "composer_unavailable"),
                Is.EqualTo(OperationFloor.CompositionFailureSentence("error", english: false)));
        });
    }

    [Test]
    public async Task ATurnSentWhileTheMindIsDownIsPublishedAtOnceWithItsCause()
    {
        await using var viewModel = new MainWindowViewModel();
        typeof(MainWindowViewModel).GetProperty(nameof(MainWindowViewModel.IsReady))!.SetValue(viewModel, true);
        string facts = TurnVisibleFacts.Failure(
            "mind_unavailable",
            new JsonObject { ["startup"] = "ram_insuficiente" });
        int before = viewModel.Messages.Count;
        bool bypass = UserMessagePolicy.BypassLlmCompositionForTests;
        UserMessagePolicy.BypassLlmCompositionForTests = false;
        try
        {
            typeof(MainWindowViewModel).GetMethod("AddMessage", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(
                viewModel,
                ["BAXY", facts, false, false,
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.LocalService), null, null]);
        }
        finally
        {
            UserMessagePolicy.BypassLlmCompositionForTests = bypass;
        }

        Assert.Multiple(() =>
        {
            Assert.That(viewModel.Messages, Has.Count.EqualTo(before + 1));
            Assert.That(
                viewModel.Messages[^1].Body,
                Is.EqualTo(OperationFloor.MindStartupSentence("ram_insuficiente", english: false)));
        });
        await Task.CompletedTask;
    }
}
