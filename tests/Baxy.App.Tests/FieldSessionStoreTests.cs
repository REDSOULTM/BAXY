using System.IO;
using System.Text;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The conversations kept on this PC (src/Baxy.App/FieldSessionStore.cs). The mind's export carries the whole
/// conversation, secrets the view masked and what memory calls read included: it never lies on disk in clear.
/// </summary>
[TestFixture]
public sealed class FieldSessionStoreTests
{
    private const string Secret = "hunter2Xy!9Qz";
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown()
    {
        try
        {
            Directory.Delete(_root, recursive: true);
        }
        catch (IOException)
        {
        }
    }

    [Test]
    public void ASavedSessionIsNotReadableOnDiskAndComesBackWhole()
    {
        var store = new FieldSessionStore(_root);

        Assert.That(store.Save(Session("abc123")), Is.True);

        string file = Path.Combine(_root, "sessions", "abc123.json");
        Assert.That(File.Exists(file), Is.True);
        byte[] onDisk = File.ReadAllBytes(file);
        Assert.That(Contains(onDisk, Secret), Is.False, "the secret lies in clear on disk");
        Assert.That(Contains(onDisk, "contraseña"), Is.False, "the conversation lies in clear on disk");

        FieldSessionStore.Session? loaded = store.Load("abc123");
        Assert.That(loaded, Is.Not.Null);
        Assert.That(loaded!.Mind!.ToJsonString(), Does.Contain(Secret));
        Assert.That((string?)loaded.Items[0]!["text"], Is.EqualTo("mi contraseña es " + Secret));
        Assert.That(loaded.Label, Is.EqualTo("Contraseña"));
        Assert.That(store.List().Select(static s => s.Id), Is.EqualTo(new[] { "abc123" }));
    }

    [Test]
    public void ASessionKeptInClearBeforeIsReadOnceAndKeptSealed()
    {
        Directory.CreateDirectory(Path.Combine(_root, "sessions"));
        string file = Path.Combine(_root, "sessions", "old42.json");
        File.WriteAllText(file, new JsonObject
        {
            ["schema"] = "baxy.field-session.v1",
            ["id"] = "old42",
            ["label"] = "Contraseña",
            ["created"] = "2026-10-20T10:00:00.0000000+00:00",
            ["updated"] = "2026-10-20T10:05:00.0000000+00:00",
            ["items"] = new JsonArray(new JsonObject { ["who"] = "you", ["text"] = "mi contraseña es " + Secret }),
            ["mind"] = new JsonArray(new JsonObject { ["role"] = "user", ["content"] = "mi contraseña es " + Secret }),
        }.ToJsonString());
        var store = new FieldSessionStore(_root);

        Assert.That(store.List().Select(static s => s.Id), Is.EqualTo(new[] { "old42" }));
        Assert.That(store.Load("old42")?.Mind?.ToJsonString(), Does.Contain(Secret));
        Assert.That(Contains(File.ReadAllBytes(file), Secret), Is.False, "the old session stayed in clear");
    }

    // BAXY Renew al máximo 11.4: «olvida todo» and the view's «borrar» leave no conversation behind but the one shown.
    [Test]
    public void DeletingAllLeavesOnlyTheConversationKept()
    {
        var store = new FieldSessionStore(_root);
        foreach (string id in (string[])["old1", "old2", "now3"])
        {
            Assert.That(store.Save(Session(id)), Is.True);
        }

        File.WriteAllText(Path.Combine(_root, "sessions", "old4.json.tmp"), "half");

        Assert.That(store.DeleteAll(keep: "now3"), Is.EqualTo(2));

        Assert.That(Directory.GetFiles(Path.Combine(_root, "sessions")).Select(Path.GetFileName),
            Is.EqualTo(new[] { "now3.json" }));
        Assert.That(store.DeleteAll(), Is.EqualTo(1));
        Assert.That(store.List(), Is.Empty);
    }

    private static FieldSessionStore.Session Session(string id) => new(
        id,
        "Contraseña",
        DateTimeOffset.UtcNow.AddMinutes(-5),
        DateTimeOffset.UtcNow,
        new JsonArray(new JsonObject { ["who"] = "you", ["text"] = "mi contraseña es " + Secret }),
        new JsonArray(
            new JsonObject { ["role"] = "user", ["content"] = "mi contraseña es " + Secret },
            new JsonObject { ["role"] = "tool", ["content"] = "{\"value\":\"" + Secret + "\"}" }));

    private static bool Contains(byte[] haystack, string needle) =>
        haystack.AsSpan().IndexOf(Encoding.UTF8.GetBytes(needle)) >= 0
        || haystack.AsSpan().IndexOf(Encoding.Unicode.GetBytes(needle)) >= 0;
}
