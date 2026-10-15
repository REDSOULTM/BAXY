using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo W (t-scroll-4, journal of limites1 2026-10-12 01:58): «abrí C:\Windows\System32 en el explorer y select el
/// archivo calc.exe». Ctrl+L put the keyboard on the folder window's address bar and Explorer showed its address history
/// in a pop-up window that folder window owns («Host de ventanas emergentes», no control of it focused, held in front by
/// its owner). The mission kept that pop-up as its window (born.kept.owned) and every look read only the list: the model
/// asked for the address field, the view had none, and the mission ended «no vi en la pantalla un control con el que
/// seguir». A pop-up that does not hold the keyboard while its owner does is the owner's, never the mission's window
/// instead of it; a menu or a dialog that holds the keyboard is still read and kept.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    // The windows of the journal: the folder window and the pop-up it owns.
    private const long WFolder = 38080422L;
    private const long WPopup = 53612474L;
    private const int WExplorer = 51344;

    // The folder window as the journal's first look listed it (foreground false: read behind before the key); after
    // Ctrl+L its address bar is an Edit that holds the keyboard.
    private static JsonObject WFolderWindow(bool addressFocused)
    {
        JsonArray controls =
        [
            Control(0, "RadioButton", "Detalles", "selected readonly"), Control(1, "TreeItem", "Inicio", value: "Inicio"),
            Control(2, "TreeItem", "Downloads", value: "Downloads"), Control(3, "TreeItem", "Este equipo", "expanded", "Este equipo"),
            Control(4, "TreeItem", "M.2 Samsung (C:)", "selected collapsed", "M.2 Samsung (C:)"),
            Control(5, "ListItem", "Intelectra_Galactico_Agil_18s", value: "Intelectra_Galactico_Agil_18s"),
            Control(6, "ListItem", "BAXY-traspaso-2026-09-21", value: "BAXY-traspaso-2026-09-21"),
            Control(7, "TabItem", "Downloads", "selected"), Control(8, "SplitButton", "M.2 Samsung (C:)"),
            Control(9, "SplitButton", "Nombre", "collapsed readonly"),
        ];
        if (addressFocused)
        {
            controls.Add(Control(10, "Edit", "Barra de direcciones", "focused", "C:\\Users\\Persona\\Downloads"));
        }

        JsonObject view = Tied(Window("Downloads - Explorador de archivos", "explorer", WExplorer, true, controls), WFolder);
        view["window"]!["foreground"] = addressFocused;
        if (addressFocused)
        {
            view["window"]!["focused"] = new JsonObject { ["i"] = 10, ["kind"] = "Edit", ["name"] = "Barra de direcciones" };
        }

        return view;
    }

    // The pop-up of the journal: the folder window owns it, it came after the key, it is in front through its owner,
    // and none of its controls holds the keyboard (the list of addresses under the bar).
    private static JsonObject WAddressHistory(string? focusedEntry = null)
    {
        string[] addresses =
        [
            "D:\\Perfil\\Documentos\\baxy-prueba-v3", "C:\\Users\\Public", "D:\\R36S Ejemplo", "G:\\psp",
            "C:\\Program Files\\Apollo", "D:\\SteamLibrary\\steamapps\\common\\Juego",
        ];
        var controls = new JsonArray();
        int index = 0;
        foreach (string address in addresses)
        {
            controls.Add(Control(index++, "ListItem", address, address == focusedEntry ? "focused" : string.Empty));
        }

        controls.Add(Control(index++, "Window", "Ventana emergente"));
        foreach (string address in addresses)
        {
            controls.Add(Control(index++, "Text", address));
        }

        JsonObject view = Window("Host de ventanas emergentes", "explorer", WExplorer, false, controls);
        view["window"]!["hwnd"] = WPopup;
        view["window"]!["root"] = WPopup;
        view["window"]!["owner"] = WFolder;
        view["window"]!["born"] = true;
        view["window"]!["foreground"] = true;
        view["window"]!["focused"] = focusedEntry is null
            ? null
            : new JsonObject { ["i"] = Array.IndexOf(addresses, focusedEntry), ["kind"] = "ListItem", ["name"] = focusedEntry };
        return view;
    }

    // The provider says «born» only of a window that is none of the mission's windows the look names.
    private static JsonObject WAsTheProviderTells(JsonObject look, JsonObject view)
    {
        if (look["windows"] is JsonArray windows && windows.Any(node => (long?)node == (long?)view["window"]?["root"]))
        {
            ((JsonObject)view["window"]!).Remove("born");
        }

        return view;
    }

    // A look of the folder window alone: the pop-up is known for it and the folder window comes first.
    private static bool WOwnerLook(JsonObject look) =>
        Knows(look, WPopup) && look["windows"] is JsonArray { Count: > 0 } windows && (long?)windows[0] == WFolder;

    private static readonly JsonObject WArguments = new()
    {
        ["goal"] = "ir a c:\\windows\\system32",
        ["application"] = "Explorador de archivos",
    };

    private const string WRequest =
        "abrí C:\\Windows\\System32 en el explorer y select el archivo calc.exe, pero no lo abras eh, solo seleccionado";

    [Test]
    public async Task EstabW_TScroll4TheAddressHistoryUnderTheBarNeverTakesTheFolderWindowsPlace()
    {
        // The journal's sequence: the folder window, Ctrl+L, then the pop-up on every look that names the mission's
        // windows (it stays while the bar has the keyboard) and the folder window with its bar focused on a look of it.
        bool keyed = false;
        var harness = new Harness
        {
            Screen = look => !keyed || look["windows"] is null ? WFolderWindow(addressFocused: keyed)
                : WOwnerLook(look) ? WFolderWindow(addressFocused: true)
                : WAddressHistory(),
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.key.press", new JsonObject { ["key"] = "ctrl_l" }),
            1 => Step("input.text.type", new JsonObject { ["text"] = "c:\\windows\\system32" }),
            _ => new MindComputerUseStep("none", new JsonObject(), string.Empty),
        };
        harness.Receipt = (operation, _) =>
        {
            keyed |= operation == "input.key.press";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = (JsonObject)WArguments.DeepClone();

        await ComputerUseMission.RunAsync(harness.Context(_root), Execution(WRequest, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests.Count, Is.GreaterThanOrEqualTo(2));
            Assert.That(harness.Requests.Skip(1).Select(request => request.View["window"]?["title"]?.ToString()),
                Is.All.EqualTo("Downloads - Explorador de archivos"), "after Ctrl+L the model sees the folder window with its bar");
            Assert.That(harness.Requests[1].View["window"]?["focused"]?["name"]?.ToString(), Is.EqualTo("Barra de direcciones"));
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.key.press", "input.text.type" }));
            Assert.That((long?)harness.Acts[1].Arguments["window"], Is.EqualTo(WFolder), "the address goes to the folder window");
            // Neither kept nor refused: no look names the pop-up as the mission's, and only the owner's looks know it.
            Assert.That(harness.Looks.Where(look => look["windows"] is JsonArray windows && windows.Any(node => (long?)node == WPopup)), Is.Empty);
            Assert.That(harness.Looks.Where(look => Knows(look, WPopup)).All(WOwnerLook), Is.True);
        });
    }

    [TestCase("menu", TestName = "EstabW_AMenuInAPopUpThatHoldsTheKeyboardIsStillReadAndKept")]
    [TestCase("entry", TestName = "EstabW_TheAddressHistoryWithTheKeyboardOnAnEntryIsStillReadAndKept")]
    public async Task EstabW_APopUpThatHoldsTheKeyboardIsTheLook(string kind)
    {
        // Contracases (t-menu-3, v3-37, v3-40: every pop-up menu of the banks shows «foco: MenuItem …»; and the list of
        // addresses once the keyboard went down into it): the pop-up holds the keyboard, so it is read, kept as the
        // mission's (owned) and no look of its owner is taken in its place.
        bool opened = false;
        JsonObject Popup()
        {
            if (kind == "entry")
            {
                return WAddressHistory(focusedEntry: "C:\\Users\\Public");
            }

            JsonObject menu = WAddressHistory();
            menu["controls"] = new JsonArray(Control(0, "MenuItem", "Copiar ruta de acceso", "focused"), Control(1, "MenuItem", "Propiedades"));
            menu["window"]!["focused"] = new JsonObject { ["i"] = 0, ["kind"] = "MenuItem", ["name"] = "Copiar ruta de acceso" };
            return menu;
        }

        var harness = new Harness
        {
            Screen = look => !opened || look["windows"] is null || Knows(look, WPopup) ? WFolderWindow(addressFocused: false) : WAsTheProviderTells(look, Popup()),
        };
        // A first act brings the pop-up, a second one is decided on it (the look after it names the pop-up first).
        harness.Mind = request => request.History.Count switch
        {
            0 when kind == "entry" => Step("input.key.press", new JsonObject { ["key"] = "arrow_down" }),
            0 => Step("input.visible.click", new JsonObject { ["label"] = "M.2 Samsung (C:)", ["index"] = 8, ["manner"] = "open" }),
            1 when kind == "entry" => Step("input.key.press", new JsonObject { ["key"] = "arrow_down" }),
            1 => Step("input.visible.click", new JsonObject { ["label"] = "Propiedades", ["index"] = 1 }),
            _ => new MindComputerUseStep("none", new JsonObject(), string.Empty),
        };
        harness.Receipt = (_, _) =>
        {
            opened = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = (JsonObject)WArguments.DeepClone();

        await ComputerUseMission.RunAsync(harness.Context(_root), Execution(WRequest, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests[1].View["window"]?["title"]?.ToString(), Is.EqualTo("Host de ventanas emergentes"));
            Assert.That(harness.Looks.Where(WOwnerLook), Is.Empty, "a pop-up with the keyboard costs no look of its owner");
            Assert.That(harness.Looks.Skip(2).Any(look => look["windows"] is JsonArray { Count: > 0 } windows && (long?)windows[0] == WPopup),
                Is.True, "kept as the mission's latest window (owned)");
        });
    }

    [Test]
    public async Task EstabW_AnOwnedWindowWhoseOwnerHasNoKeyboardEitherIsReadAgainAndKept()
    {
        // Contracase: a dialog the folder window owns read in front with no control focused (one whose tree does not tell
        // its focus), and its owner's look holds no keyboard either (the provider reads a modal dialog through its owner).
        // One look of the owner, then the dialog is read again and kept as before (the save-as and open dialogs of the
        // banks hold their file name field: they never cost that look).
        bool opened = false;
        JsonObject Dialog()
        {
            JsonObject dialog = Window("Opciones de carpeta", "explorer", WExplorer, false,
                [Control(0, "TabItem", "General", "selected"), Control(1, "Button", "Aceptar"), Control(2, "Button", "Cancelar")]);
            dialog["window"]!["hwnd"] = WPopup;
            dialog["window"]!["root"] = WPopup;
            dialog["window"]!["owner"] = WFolder;
            dialog["window"]!["born"] = true;
            dialog["window"]!["foreground"] = true;
            return dialog;
        }

        var harness = new Harness
        {
            Screen = look => !opened || look["windows"] is null ? WFolderWindow(addressFocused: false)
                : WOwnerLook(look) ? WFolderWindow(addressFocused: false)
                : WAsTheProviderTells(look, Dialog()),
        };
        harness.Mind = request => request.History.Count == 0
            ? Step("input.visible.click", new JsonObject { ["label"] = "Nombre", ["index"] = 9 })
            : new MindComputerUseStep("none", new JsonObject(), string.Empty);
        harness.Receipt = (_, _) =>
        {
            opened = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = (JsonObject)WArguments.DeepClone();

        await ComputerUseMission.RunAsync(harness.Context(_root), Execution(WRequest, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests[1].View["window"]?["title"]?.ToString(), Is.EqualTo("Opciones de carpeta"));
            Assert.That(harness.Looks.Count(WOwnerLook), Is.EqualTo(1), "one look of the owner, then the dialog again");
        });
    }
}
