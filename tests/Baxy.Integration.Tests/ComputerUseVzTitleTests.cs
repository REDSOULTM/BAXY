using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo VZ (imp3d imp-dc-voz, trace t2): «cotele» typed into Discord's «Buscar», Escape, Ctrl+K and the confirmed
/// press of «Cotele!!!😎, Canal de voz, Choche» joined the channel and titled the window «Cotele!!!😎 | Choche -
/// Discord»; the typing still read as the title's echo, the mission went on and pressed the channel again (a second
/// question). A part of the title that is the name by its letters and digits shows the place whole.
/// </summary>
[TestFixture]
public sealed class ComputerUseVzTitleTests
{
    private const string Check = "control:cotele:current|title:cotele|page:cotele|mark:cotele";

    private static JsonArray Steps() =>
    [
        new JsonObject { ["step"] = 4, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "cotele", ["into"] = "Buscar", ["windowTitle"] = "Amigos - Discord" },
        new JsonObject { ["step"] = 5, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "escape" },
        new JsonObject { ["step"] = 6, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "ctrl_k" },
        new JsonObject
        {
            ["step"] = 7, ["operation"] = "input.visible.click", ["ok"] = true, ["confirmed"] = true,
            ["label"] = "Cotele!!!😎, Canal de voz, Choche", ["name"] = "Cotele!!!😎, Canal de voz, Choche",
            ["kind"] = "ListItem", ["selected"] = true,
        },
    ];

    private static JsonObject View(string title, string? searchHolds) => new()
    {
        ["window"] = new JsonObject { ["title"] = title, ["process"] = "Discord", ["requested"] = true },
        ["controls"] = new JsonArray
        {
            new JsonObject { ["i"] = 1, ["kind"] = "Document", ["name"] = "Cotele!!!😎 | Choche", ["value"] = "https://discord.com/channels/7221/7776" },
            new JsonObject { ["i"] = 2, ["kind"] = "Hyperlink", ["name"] = "Cotele!!!😎 / Choche" },
            new JsonObject { ["i"] = 3, ["kind"] = "Edit", ["name"] = "Buscar", ["value"] = searchHolds },
        },
    };

    [Test]
    public void TheJoinedChannelsTitleShowsThePlaceOnceTheSearchLetItGo()
    {
        bool held = ComputerUseSuccessCheck.Evaluate(Check, View("Cotele!!!😎 | Choche - Discord", null), Steps(), out string? by);

        Assert.Multiple(() =>
        {
            Assert.That(held, Is.True);
            Assert.That(by, Is.EqualTo("title:cotele"));
        });
    }

    // Contracases: a box that still holds the query is the echo; a title part that only holds the name inside a longer
    // one («Cotele Fans») is one of the matches.
    [TestCase("Cotele!!!😎 | Choche - Discord", "cotele")]
    [TestCase("Cotele Fans | Choche - Discord", null)]
    public void TheEchoStandsWhileTheBoxHoldsTheQueryOrTheTitleOnlyHoldsTheName(string title, string? searchHolds) =>
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, View(title, searchHolds), Steps(), out _), Is.False);
}
