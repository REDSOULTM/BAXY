using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo TZ-DC3 (banco zt3 imp-wa-abrir, notebook journal 20:21:18–38 UTC, «en WhatsApp abrí el chat con Abuela»): the
/// chat list's «Abuela» pressed by its text opened the chat only after the look that followed it (the window, under the
/// person's Spotify, drew it late: still the list, the keyboard on the document); the chat showed two steps later, and
/// every later press of «Abuela» put the keyboard into its message box, which the look before that press already listed.
/// The check never took it, the mission pressed on for 10 steps and ended «No pude llegar a «Abuela»» with the chat open.
/// The views are the journal's, by their names; the place's own box new with the sub-goal is the arrival.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string ToAbuela = "control:abuela:current|title:abuela|page:abuela|mark:abuela";

    // The notebook's looks of zt3 (journal-caso.json, «destacados»), by what each one showed.
    private static JsonObject WhatsAppChats(string stage)
    {
        var controls = new JsonArray
        {
            Control(0, "Document", "(5) WhatsApp", stage == "list" ? "readonly focused" : "readonly"),
            Control(1, "Button", "Chats", "on"),
            Control(2, "Edit", "Buscar un chat o iniciar uno nuevo", stage == "search" ? "focused" : ""),
            Control(3, "TabItem", "Todos", "selected"),
            Control(4, "DataItem", "Abuela 16:47 prueba BAXY imp"),
            Control(5, "DataItem", "Abuela 16:47"),
            Control(6, "DataItem", "1 mensaje no leído Mamá 🍓 17:00"),
            Control(7, "Button", "Llamadas", "off"),
            Control(8, "Button", "Estados", "off"),
        };
        if (stage != "list")
        {
            // The chat opened (late): its bubbles, its header and its message box.
            controls.Add(Control(9, "Button", "16:11 Enviado"));
            controls.Add(Control(10, "Button", "16:47 Enviado"));
            controls.Add(Control(11, "Button", "Abuela haz clic aquí para ver la información de contacto"));
            controls.Add(Control(12, "Edit", "Escribir un mensaje para Abuela", stage == "chat" ? "focused" : ""));
        }

        if (stage == "search")
        {
            // The search's recent results under the box the step put the keyboard in.
            controls.Add(Control(13, "Button", "Borrar todo"));
            controls.Add(Control(14, "Button", "Abuela"));
            controls.Add(Control(15, "Button", "Mamá 🍓"));
        }

        JsonObject view = Window("(5) WhatsApp", "msedgewebview2", 60, true, controls);
        view["window"]!["focused"] = stage switch
        {
            "search" => new JsonObject { ["kind"] = "Edit", ["name"] = "Buscar un chat o iniciar uno nuevo" },
            "chat" => new JsonObject { ["kind"] = "Edit", ["name"] = "Escribir un mensaje para Abuela" },
            _ => new JsonObject { ["kind"] = "Document", ["name"] = "(5) WhatsApp" },
        };
        return view;
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task AChatDrawnLateIsReachedWhenAPressPutsTheKeyboardIntoItsBox(bool boxTakesTheKeyboard)
    {
        // Contracase (false): the press of «Abuela» leaves the keyboard in the search: no arrival.
        var harness = new Harness
        {
            Mind = request => request.History.Count switch
            {
                0 => Step("input.visible.click", new JsonObject { ["label"] = "Abuela" }),
                1 => Step("input.visible.click", new JsonObject { ["label"] = "Buscar un chat o iniciar uno nuevo" }),
                _ => Step("input.visible.click", new JsonObject { ["label"] = "Abuela" }),
            },
        };
        harness.Screen = _ =>
        {
            int clicks = harness.Acts.Count(act => act.Operation == "input.visible.click");
            string last = clicks == 0 ? string.Empty : (string?)harness.Acts[^1].Arguments["label"] ?? string.Empty;
            // zt3: the first look and the one after the first press show the list; after the press of the search the
            // chat is open behind the search; after a press of «Abuela» the keyboard is in the chat's box.
            return clicks < 2
                ? WhatsAppChats("list")
                : WhatsAppChats(last == "Abuela" && boxTakesTheKeyboard ? "chat" : "search");
        };
        var arguments = new JsonObject { ["goal"] = "ir a abuela", ["application"] = "WhatsApp", ["successCheck"] = ToAbuela };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en WhatsApp abrí el chat con Abuela", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        int pressed = harness.Acts.Count(act => act.Operation == "input.visible.click");
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"] == true, Is.EqualTo(boxTakesTheKeyboard));
            Assert.That(pressed, Is.EqualTo(3), boxTakesTheKeyboard
                ? "reached with the third press, the first that put the keyboard into the box"
                : "the third press changed nothing: the loop's own guard ends it, never as arrived");
        });
    }

    [Test]
    public void ContracaseABoxListedBeforeTheFirstClickOrAKeyboardThatDidNotMoveIsNoArrival()
    {
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Abuela" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar un chat o iniciar uno nuevo" },
            new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Abuela" },
        };
        JsonObject view = WhatsAppChats("chat");
        view["focusBeforeStep"] = new JsonObject
        {
            ["1"] = "Document|(5) whatsapp",
            ["2"] = "Document|(5) whatsapp",
            ["3"] = "Edit|buscar un chat o iniciar uno nuevo",
        };
        view["controlsBeforeClick"] = new JsonObject
        {
            ["1"] = ComputerUseSuccessCheck.ControlNames(WhatsAppChats("list"), reserved: true),
            ["2"] = ComputerUseSuccessCheck.ControlNames(WhatsAppChats("list"), reserved: true),
            ["3"] = ComputerUseSuccessCheck.ControlNames(WhatsAppChats("search"), reserved: true),
        };

        // zt3 at its third press: the box was listed before that press, not before the sub-goal's first one.
        Assert.That(ComputerUseSuccessCheck.FocusedIntoThePlace(view, "abuela", steps), Is.True);

        // Listed before the first click too: the chat was open from the start.
        view["controlsBeforeClick"]!["1"] = ComputerUseSuccessCheck.ControlNames(WhatsAppChats("chat"), reserved: true);
        Assert.That(ComputerUseSuccessCheck.FocusedIntoThePlace(view, "abuela", steps), Is.False);

        // New with the sub-goal, but the last press left the keyboard where it was.
        view["controlsBeforeClick"]!["1"] = ComputerUseSuccessCheck.ControlNames(WhatsAppChats("list"), reserved: true);
        view["focusBeforeStep"]!["3"] = "Edit|escribir un mensaje para abuela";
        Assert.That(ComputerUseSuccessCheck.FocusedIntoThePlace(view, "abuela", steps), Is.False);
    }

    // banco zt1 c6 (journal 18:42:32–34 UTC): «Mensaje @Ron92» empty before the typing and after it, the keyboard on the
    // chat's document; in zt2 and zt3 the look after it shows the box focused with the text.
    private static JsonObject DiscordDm(string? typed)
    {
        JsonObject view = Window("@Ron92 - Discord", "Discord", 9676, true,
        [
            Control(0, "Document", "@Ron92", typed is null ? "readonly focused" : "readonly",
                "https://discord.com/channels/@me/788990433829060618"),
            Control(1, "TreeItem", "Mensajes directos", "selected"),
            Control(2, "Edit", "Mensaje @Ron92", typed is null ? "" : "focused", typed ?? "\uFEFF"),
            Control(3, "ComboBox", "Buscar .wolfsoultm.4191", "collapsed"),
            Control(4, "Hyperlink", "Ron92 (mensaje directo)", "readonly", "https://discord.com/channels/@me/788990433829060618"),
        ]);
        view["window"]!["focused"] = typed is null
            ? new JsonObject { ["kind"] = "Document", ["name"] = "@Ron92", ["value"] = "https://discord.com/channels/@me/788990433829060618" }
            : new JsonObject { ["kind"] = "Edit", ["name"] = "Mensaje @Ron92", ["value"] = typed };
        return view;
    }

    // Encargo TZ-DC3 (zt1 c6, «antes de parar escribí «prueba BAXY C6»» with the box empty): a text the look after it does
    // not show is marked «arrived» false by the mission, and the two floors (tests/data/cu_floor_twins.json,
    // tz-dc3-c6-*) leave it out of the final. Contracase: the text shown in the box keeps the step as it was.
    [TestCase(false)]
    [TestCase(true)]
    public void ATextTheLookAfterItDoesNotShowIsMarkedNotArrived(bool shown)
    {
        var state = new JsonObject();
        JsonArray steps = [];
        ComputerUseMission.MarkAppeared(state, steps, 0, DiscordDm(typed: null));
        var typing = new JsonObject
        {
            ["step"] = 1,
            ["operation"] = "input.text.type",
            ["text"] = "prueba BAXY C6",
            ["ok"] = true,
            ["method"] = "keyboard",
        };
        steps.Add((JsonNode)typing);
        ComputerUseMission.MarkAppeared(state, steps, 0, DiscordDm(shown ? "prueba BAXY C6" : null));

        Assert.That((bool?)typing["arrived"], shown ? Is.Null : Is.False);
    }
}
