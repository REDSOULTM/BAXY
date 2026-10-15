using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24, palanca «emergentes-del-dueno-y-menus-que-se-reabren» (App side): opening a menu entry whose only action is
/// to open is pressing it (t-menu-3). Review 1 of ronda 24 (finding 3): the list of suggestions a field shows under a
/// typed text stays a window the mission owns, with its entries to press, until its entries can be shown in the owner's
/// view; refusing it lost the suggestion to choose and left its window refused for the whole mission.
/// </summary>
[TestFixture]
public sealed class EmergentesDelDuenoMissionTests
{
    private static JsonObject Open(string label, string kind, string method = "expand", bool opened = true, string manner = "open") => new()
    {
        ["step"] = 1,
        ["operation"] = "input.visible.click",
        ["label"] = label,
        ["name"] = label,
        ["kind"] = kind,
        ["manner"] = manner,
        ["method"] = method,
        ["opened"] = opened,
        ["ok"] = true,
    };

    [Test]
    public void TMenu3OpeningAMenuBarEntryIsItsPress()
    {
        JsonObject view = Open("Ver", "MenuItem");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OpenIsItsPress(view), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyOpened(view), Is.False);
            Assert.That(ComputerUseSuccessCheck.Pressed(view), Is.True);
            // The mind gets the App's verdict.
            JsonArray history = ComputerUseMission.HistoryForMind(new JsonArray(view.DeepClone()), 0);
            Assert.That((bool?)history[0]!["openPress"], Is.True);
        });
    }

    [Test]
    public void AnArrowAComboBoxOrAContextMenuStayOnlyOpened()
    {
        Assert.Multiple(() =>
        {
            // Contracases: the split button «Nueva pestaña» acts by itself (v3-37); a combo box chooses no value; a
            // context menu presses nothing; an entry not read open is no press.
            Assert.That(ComputerUseSuccessCheck.OnlyOpened(Open("Nueva pestaña", "SplitButton")), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyOpened(Open("Tamaño", "ComboBox")), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyOpened(Open("Ver", "MenuItem", manner: "menu")), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyOpened(Open("Ver", "MenuItem", opened: false)), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyOpened(Open("Ver", "MenuItem", method: "invoke")), Is.True);
            JsonArray history = ComputerUseMission.HistoryForMind(new JsonArray(Open("Nueva pestaña", "SplitButton")), 0);
            Assert.That(history[0]!["openPress"], Is.Null);
        });
    }

    private static JsonObject Born(long hwnd, long owner, JsonObject? focused, params (string Kind, string Name)[] controls)
    {
        var list = new JsonArray();
        int index = 0;
        foreach ((string kind, string name) in controls)
            list.Add(new JsonObject { ["i"] = index++, ["kind"] = kind, ["name"] = name });
        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["hwnd"] = hwnd,
                ["root"] = hwnd,
                ["owner"] = owner,
                ["born"] = true,
                ["title"] = string.Empty,
                ["focused"] = focused,
            },
            ["controls"] = list,
        };
    }

    private static JsonObject State() => new()
    {
        ["objective"] = "en el Explorador andá a c:\\windows\\system32 y seleccioná calc.exe sin abrirlo",
        ["application"] = "Explorador de archivos",
        ["windows"] = new JsonArray(4660L),
    };

    private static JsonArray Steps(string lastOperation) => new(
        new JsonObject { ["step"] = 1, ["operation"] = "input.key.press", ["key"] = "ctrl_l", ["ok"] = true },
        new JsonObject { ["step"] = 2, ["operation"] = lastOperation, ["text"] = "c:\\windows\\system32", ["label"] = "Dirección", ["ok"] = true });

    [Test]
    public void TheSuggestionListUnderTheTypedPathKeepsItsEntriesToChoose()
    {
        // «escribí C:\Us en la barra de direcciones y elegí la sugerencia C:\Users»: the suggestion is chosen on it.
        JsonObject suggestions = Born(5000, 4660, null,
            ("List", "Sugerencias"), ("ListItem", "C:\\Windows\\System32"), ("ListItem", "C:\\Windows\\SysWOW64"), ("ScrollBar", "Vertical"));
        JsonObject state = State();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.KeepsBorn(state, suggestions, Steps("input.text.type"), DateTimeOffset.UtcNow, out string why), Is.True);
            Assert.That(why, Is.EqualTo("owned"));
            Assert.That(state["refused"], Is.Null);
        });
    }

    [Test]
    public void AModalDialogOrAListAClickOpenedIsStillTheMissionsSurface()
    {
        // Contracase: the mission's own dialog (a field and a button to accept) takes the keyboard and is a surface.
        JsonObject dialog = Born(5001, 4660, new JsonObject { ["kind"] = "Edit", ["name"] = "Nombre de archivo" },
            ("Edit", "Nombre de archivo"), ("Button", "Guardar"), ("Button", "Cancelar"));
        // Contracase: the same dialog read without the keyboard still has a field and buttons.
        JsonObject dialogNoFocus = Born(5002, 4660, null, ("ListItem", "Documentos"), ("Button", "Aceptar"));
        // Contracase: a list born of a click (a combo box's entries to choose) is a surface.
        JsonObject comboList = Born(5003, 4660, null, ("List", "Tamaño"), ("ListItem", "11"), ("ListItem", "12"));
        // Contracase: a menu the opener showed keeps its entries to press.
        JsonObject menu = Born(5004, 4660, null, ("MenuItem", "Zoom"), ("MenuItem", "Barra de estado"));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.KeepsBorn(State(), dialog, Steps("input.text.type"), DateTimeOffset.UtcNow, out string a), Is.True);
            Assert.That(a, Is.EqualTo("owned"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(State(), dialogNoFocus, Steps("input.text.type"), DateTimeOffset.UtcNow, out string b), Is.True);
            Assert.That(b, Is.EqualTo("owned"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(State(), comboList, Steps("input.visible.click"), DateTimeOffset.UtcNow, out string c), Is.True);
            Assert.That(c, Is.EqualTo("owned"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(State(), menu, Steps("input.text.type"), DateTimeOffset.UtcNow, out string d), Is.True);
            Assert.That(d, Is.EqualTo("owned"));
        });
    }
}
