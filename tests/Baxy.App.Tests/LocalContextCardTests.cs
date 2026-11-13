using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// VRAM4 (2026-11-12; the owner: «Baxi debe de funcionar en un hardware de 4 GB… Tiene que caber en 4 GB»): with
/// «Automático» the mind fits its context to the video memory free at its start (llm_server.fit_card). The App tells it
/// what the person's profile needs, shows the cells it took, and says a profile the card does not hold whole, with the one
/// that fits, on the running model and on the breakdown card of a start that failed.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class LocalContextCardTests
{
    private string _root = "";
    private string? _before;
    private string? _needs;

    [SetUp]
    public void SetUp()
    {
        _root = Directory.CreateTempSubdirectory("baxy-card-").FullName;
        _before = Environment.GetEnvironmentVariable(LocalContext.Variable);
        _needs = Environment.GetEnvironmentVariable(LocalContext.NeedsVariable);
        Environment.SetEnvironmentVariable(LocalContext.Variable, null);
        Environment.SetEnvironmentVariable(LocalContext.NeedsVariable, null);
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable(LocalContext.Variable, _before);
        Environment.SetEnvironmentVariable(LocalContext.NeedsVariable, _needs);
        Directory.Delete(_root, recursive: true);
    }

    private static string? Fitting(int cells) => ToolProfile.LargestFitting(cells, null, null);

    [Test]
    public void TheMindIsToldWhatThePersonsProfileNeeds()
    {
        var context = new LocalContext(_root);
        context.ApplyEnvironment("cuda", 30073);
        Assert.That(Environment.GetEnvironmentVariable(LocalContext.NeedsVariable), Is.EqualTo("30073"));
        // «Automático» still gives the mind no context of the App's: it is the mind that fits it to the card.
        Assert.That(Environment.GetEnvironmentVariable(LocalContext.Variable), Is.Null);
        context.ApplyEnvironment("cuda");
        Assert.That(Environment.GetEnvironmentVariable(LocalContext.NeedsVariable), Is.Null);
    }

    [Test]
    public void AutomaticIsShownAsTheCellsTheMindTook()
    {
        var context = new LocalContext(_root);
        context.ApplyEnvironment("cuda", 30073);
        Assert.That((int?)context.Json(null, "cuda", switching: false)["automatic"], Is.EqualTo(77824));
        context.Started(ownModel: true, context: 32768);
        Assert.That((int?)context.Json(null, "cuda", switching: false)["automatic"], Is.EqualTo(32768));
        // Another model's mind says nothing of BAXY's own server.
        context.Started(ownModel: false, context: 32768);
        Assert.That((int?)context.Json(null, "cuda", switching: false)["automatic"], Is.EqualTo(77824));
        // Nor do cells the person chose change what «Automático» would take.
        Assert.That(context.Apply(new JsonObject { ["context"] = 65536 }, prefixTokens: null), Is.Null);
        context.ApplyEnvironment("cuda", 30073);
        context.Started(ownModel: true, context: 65536);
        Assert.That((int?)context.Json(null, "cuda", switching: false)["automatic"], Is.EqualTo(77824));
    }

    [Test]
    public void AProfileTheCardDoesNotHoldWholeIsSaidWithTheOneThatFits()
    {
        var found = LocalContext.CardFound.From(new JsonObject { ["freeMb"] = 3400, ["needMb"] = 3881, ["context"] = 61440, ["fitsContext"] = 32768 });
        Assert.That(found, Is.EqualTo(new LocalContext.CardFound(3400, 3881, 61440, 32768)));
        var context = new LocalContext(_root);
        context.ApplyEnvironment("cuda", 55034);
        Assert.That(context.CardShort("completo", Fitting), Is.Null);
        context.Started(ownModel: true, context: 61440, cardShort: found);
        JsonObject said = context.CardShort("completo", Fitting)!;
        Assert.Multiple(() =>
        {
            Assert.That((string?)said["profile"], Is.EqualTo("completo"));
            Assert.That((int?)said["freeMb"], Is.EqualTo(3400));
            Assert.That((int?)said["needMb"], Is.EqualTo(3881));
            Assert.That((string?)said["fittingProfile"], Is.EqualTo("esencial"));
        });
        // A start with room says nothing.
        context.Started(ownModel: true, context: 77824);
        Assert.That(context.CardShort("completo", Fitting), Is.Null);
    }

    [Test]
    public void AStartThatFailedOnACardShortOfMemoryKeepsWhatItFound()
    {
        var reply = new JsonObject
        {
            ["type"] = "error",
            ["startup"] = new JsonObject
            {
                ["cause"] = "lectura_lenta", ["tokensPerS"] = 47, ["needMinutes"] = 31,
                ["cardShort"] = new JsonObject { ["freeMb"] = 3400, ["needMb"] = 3881, ["context"] = 61440 },
            },
        };
        MindStartupFailure failure = MindStartupFailure.FromReply(reply)!;
        Assert.That(failure.CardShort, Is.EqualTo(new LocalContext.CardFound(3400, 3881, 61440, null)));
        var context = new LocalContext(_root);
        context.Failed(failure.CardShort);
        JsonObject said = context.CardShort("completo", Fitting)!;
        Assert.That((int?)said["freeMb"], Is.EqualTo(3400));
        Assert.That(said["fittingProfile"], Is.Null);
        // The next failure with no card found (another cause) does not keep the old one.
        context.Failed(null);
        Assert.That(context.CardShort("completo", Fitting), Is.Null);
        Assert.That(LocalContext.CardFound.From(new JsonObject { ["freeMb"] = 3400 }), Is.Null);
    }
}
