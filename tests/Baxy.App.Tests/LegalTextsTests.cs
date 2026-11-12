using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// REV_LEGAL LEG-15 (2026-11-09): the licenses and the privacy policy went in the package's folder (scripts/build_steam.ps1:
/// <c>licenses\</c> beside <c>app\</c>) and nothing in the App opened them. Settings › Privacidad asks the host to open them.
/// </summary>
[TestFixture]
public sealed class LegalTextsTests
{
    private string _root = null!;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-legal-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(_root, "app"));
        Directory.CreateDirectory(Path.Combine(_root, "licenses"));
        File.WriteAllText(Path.Combine(_root, "licenses", "PRIVACIDAD.md"), "# Privacidad");
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    [Test]
    public async Task ThePrivacyPolicyAndTheLicensesOfThePackageAreOpenedFromSettings()
    {
        using var fake = new FakeMind();
        var opened = new List<string>();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            view.Channel.LegalStart = Path.Combine(_root, "app");
            view.Channel.OpenShell = path => { opened.Add(path); return true; };

            // VIS3 (VIVO6 fila 4): the policy is a .md, and on a Windows with no program for .md the shell started «Open
            // with» and said it had opened it. Its text is read in Settings; only the licenses' folder goes to Explorer.
            (int read, JsonObject policy) = await view.SendAsync("GET", "/settings/legal/privacy");
            Assert.That((read, (string?)policy["text"]), Is.EqualTo((200, "# Privacidad")));
            Assert.That((await view.SendAsync("POST", "/settings/legal/open", new JsonObject { ["doc"] = "licenses" })).Status, Is.EqualTo(200));
            Assert.That((await view.SendAsync("POST", "/settings/legal/open", new JsonObject { ["doc"] = "privacy" })).Status, Is.EqualTo(400));
            Assert.That((await view.SendAsync("POST", "/settings/legal/open", new JsonObject { ["doc"] = "C:\\Windows" })).Status, Is.EqualTo(400));
            Assert.That(opened, Is.EqualTo(new[] { Path.Combine(_root, "licenses") }));

            // a copy without them says so, and opens nothing
            opened.Clear();
            Directory.Delete(Path.Combine(_root, "licenses"), recursive: true);
            (int status, JsonObject body) = await view.SendAsync("GET", "/settings/legal/privacy");
            Assert.That((status, (string?)body["error"]), Is.EqualTo((404, "legal_not_found")));
            (status, body) = await view.SendAsync("POST", "/settings/legal/open", new JsonObject { ["doc"] = "licenses" });
            Assert.That((status, (string?)body["error"]), Is.EqualTo((404, "legal_not_found")));
            Assert.That(opened, Is.Empty);
        }
    }
}
