using System.IO;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Settings → Behavior (owner's order of 2026-11-08): the person's own texts are kept only when written, go to the mind
/// with its catalog and change nothing of the catalog; with none, the mind's request is the very one sent before.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class PersonBehaviorTests
{
    private string _root = "";

    [SetUp]
    public void SetUp() => _root = Directory.CreateTempSubdirectory("baxy-behavior-").FullName;

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    private static List<OperationDescriptor> Catalog() =>
        [.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
            ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))];

    [Test]
    public void WithNoTextOfThePersonsTheMindsRequestIsTheOneSentBefore()
    {
        var behavior = new PersonBehavior(_root);
        Assert.That(behavior.ForMind(), Is.Null);
        string before = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), applicationCatalog: null).ToJsonString();
        string now = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, behavior.ForMind()).ToJsonString();
        Assert.That(now, Is.EqualTo(before));
    }

    [Test]
    public void ThePersonsTextsGoWithTheCatalogAndLeaveItAsItWas()
    {
        var behavior = new PersonBehavior(_root);
        Assert.That(behavior.Apply(new JsonObject { ["personality"] = "  Eres un mayordomo con humor seco. ", ["preferences"] = "Llámame capitán." }), Is.Null);
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), null, null, new PersonBehavior(_root).ForMind());
        JsonObject factory = MindSidecarClient.CreateCatalogConfigureRequest(Catalog(), applicationCatalog: null);
        Assert.Multiple(() =>
        {
            Assert.That(request["behavior"]!.AsObject().Select(static pair => (pair.Key, (string?)pair.Value)),
                Is.EqualTo(new[] { ("personality", "Eres un mayordomo con humor seco."), ("preferences", "Llámame capitán.") }));
            Assert.That(request["capabilities"]!.ToJsonString(), Is.EqualTo(factory["capabilities"]!.ToJsonString()));
        });
    }

    [Test]
    public void ATextTooLongOrNotTextIsRefusedAndNothingIsKept()
    {
        var behavior = new PersonBehavior(_root);
        Assert.That(behavior.Apply(new JsonObject { ["replies"] = "Breve." }), Is.Null);
        Assert.Multiple(() =>
        {
            Assert.That(behavior.Apply(new JsonObject { ["replies"] = "Otra.", ["preferences"] = new string('a', PersonBehavior.MaxChars + 1) }),
                Is.EqualTo("behavior_too_long"));
            Assert.That(behavior.Apply(new JsonObject { ["personality"] = 3 }), Is.EqualTo("behavior_invalid_text"));
            Assert.That(behavior.Texts().ToJsonString(), Is.EqualTo("""{"replies":"Breve."}"""));
            Assert.That(behavior.Apply(new JsonObject { ["preferences"] = new string('a', PersonBehavior.MaxChars) }), Is.Null);
        });
    }

    [Test]
    public void BlankPutsOneBackAndResetPutsAllBack()
    {
        var behavior = new PersonBehavior(_root);
        behavior.Apply(new JsonObject { ["personality"] = "Seco.", ["replies"] = "Corto." });
        Assert.That(behavior.Apply(new JsonObject { ["personality"] = " " }), Is.Null);
        Assert.That(behavior.Texts().ToJsonString(), Is.EqualTo("""{"replies":"Corto."}"""));
        Assert.That(behavior.Apply(new JsonObject { ["reset"] = true }), Is.Null);
        Assert.Multiple(() =>
        {
            Assert.That(behavior.ForMind(), Is.Null);
            Assert.That(File.Exists(Path.Combine(_root, PersonBehavior.FileName)), Is.False);
        });
    }

    [Test]
    public void AChangeAgainstTheRunningMindNeedsARelaunchOnce()
    {
        var behavior = new PersonBehavior(_root);
        behavior.Started(behavior.ForMind());
        Assert.That(behavior.NeedsSwitch, Is.False);
        behavior.Apply(new JsonObject { ["replies"] = "Corto." });
        Assert.That(behavior.NeedsSwitch, Is.True);
        behavior.Started(behavior.ForMind());
        Assert.That(behavior.NeedsSwitch, Is.False);
    }

    [Test]
    public void TheNameAndIdentityAreShownFixedAndNeverKept()
    {
        // Owner's limit of 2026-11-08: BAXY is always called BAXY; the identity is the mind's, not a text of the person's.
        var behavior = new PersonBehavior(_root);
        Assert.That(behavior.Apply(new JsonObject { ["identity"] = "Eres Max." }), Is.Null);
        Assert.That(behavior.ForMind(), Is.Null);
        var hello = new JsonObject
        {
            ["identity"] = "Eres BAXY y sólo BAXY.",
            ["factory"] = new JsonObject { ["personality"] = "", ["replies"] = "Breve.", ["preferences"] = "" },
        };
        JsonObject view = behavior.Json(hello, switching: false);
        Assert.Multiple(() =>
        {
            Assert.That((string?)view["identity"], Is.EqualTo("Eres BAXY y sólo BAXY."));
            Assert.That((string?)view["factory"]!["replies"], Is.EqualTo("Breve."));
            Assert.That(view["texts"]!.AsObject().ContainsKey("identity"), Is.False);
        });
    }

    [Test]
    public void WithNoMindStartedYetAChangeWaitsForTheNextStartAndLeavesTheViewFree()
    {
        // Review of b497af005: with no mind ever up (a failed start, no runtime), «switching» stayed true for good and
        // locked every box of the tab.
        var behavior = new PersonBehavior(_root);
        Assert.That(behavior.Apply(new JsonObject { ["replies"] = "Corto." }), Is.Null);
        Assert.That(behavior.NeedsSwitch, Is.False);
        Assert.That((bool?)behavior.Json(null, switching: false)["switching"], Is.False);
        Assert.That(behavior.Apply(new JsonObject { ["reset"] = "sí" }), Is.EqualTo("behavior_invalid_text"));
    }

    // REV_APP PRM-2 (2026-11-09): what the person writes in Behavior was kept in clear, beside a history that is sealed
    // (FieldSessionStore). It is sealed as the history is, and opens only for this Windows user.
    [Test]
    public void WhatThePersonWroteIsNotKeptInClear()
    {
        Assert.That(new PersonBehavior(_root).Apply(new JsonObject { ["preferences"] = "Mi perra se llama Canela." }), Is.Null);

        string kept = System.Text.Encoding.Latin1.GetString(File.ReadAllBytes(Path.Combine(_root, PersonBehavior.FileName)));
        Assert.Multiple(() =>
        {
            Assert.That(kept, Does.Not.Contain("Canela").And.Not.Contain("preferences"));
            Assert.That((string?)new PersonBehavior(_root).Texts()["preferences"], Is.EqualTo("Mi perra se llama Canela."));
        });
    }

    [Test]
    public void ATextKeptInClearBeforeIsReadAndSealedThatOnce()
    {
        string path = Path.Combine(_root, PersonBehavior.FileName);
        File.WriteAllText(path, new JsonObject { ["replies"] = "Corto y sin emojis." }.ToJsonString());

        string? read = (string?)new PersonBehavior(_root).Texts()["replies"];

        Assert.Multiple(() =>
        {
            Assert.That(read, Is.EqualTo("Corto y sin emojis."));
            Assert.That(System.Text.Encoding.Latin1.GetString(File.ReadAllBytes(path)), Does.Not.Contain("emojis"));
            Assert.That((string?)new PersonBehavior(_root).Texts()["replies"], Is.EqualTo("Corto y sin emojis."));
        });
    }

    // The clear file was read as text: one saved by hand with the mark of UTF-8 or a blank before it was the person's too.
    [Test]
    public void ATextKeptInClearWithAMarkBeforeItIsStillThePersons()
    {
        string path = Path.Combine(_root, PersonBehavior.FileName);
        File.WriteAllText(path, "\r\n" + new JsonObject { ["replies"] = "Corto y sin emojis." }.ToJsonString(),
            new System.Text.UTF8Encoding(encoderShouldEmitUTF8Identifier: true));

        Assert.That((string?)new PersonBehavior(_root).Texts()["replies"], Is.EqualTo("Corto y sin emojis."));
        Assert.That(System.Text.Encoding.Latin1.GetString(File.ReadAllBytes(path)), Does.Not.Contain("emojis"));
    }

    [Test]
    public void AnUnreadableFileIsTheFactorysTexts()
    {
        File.WriteAllText(Path.Combine(_root, PersonBehavior.FileName), "{ no es json");
        Assert.That(new PersonBehavior(_root).ForMind(), Is.Null);
    }

    [Test]
    public async Task TheViewKeepsThemThroughItsRoute()
    {
        System.Reflection.FieldInfo field = typeof(MainWindowViewModel)
            .GetField("_behavior", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!;
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            field.SetValue(viewModel, new PersonBehavior(_root));
            await using var view = new ChannelHarness(viewModel);

            (int status, JsonObject body) = await view.SendAsync("PUT", "/settings/behavior", new JsonObject { ["replies"] = "Corto y formal." });
            Assert.That(status, Is.EqualTo(200));
            Assert.That((string?)body["texts"]!["replies"], Is.EqualTo("Corto y formal."));
            Assert.That(body["texts"]!["personality"], Is.Null);
            Assert.That((int?)body["maxChars"], Is.EqualTo(PersonBehavior.MaxChars));

            (status, body) = await view.SendAsync("PUT", "/settings/behavior", new JsonObject { ["replies"] = new string('a', 900) });
            Assert.That((status, (string?)body["error"]), Is.EqualTo((409, "behavior_too_long")));

            (status, body) = await view.SendAsync("GET", "/settings/behavior");
            Assert.That((status, (string?)body["texts"]!["replies"]), Is.EqualTo((200, "Corto y formal.")));
            // With no engine here no mind starts; the switch ends and the next start takes them.
            Assert.That(() => viewModel.ExternalModelState.Switching, Is.False.After(5000, 50));
            field.SetValue(viewModel, null);
        }
    }
}
