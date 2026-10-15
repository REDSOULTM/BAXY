using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo E5 (bancos fw2, fw3, e5c1, e5c2 on 7b906ce49: v3, x3, x4, c5 failed 0/15 whenever Configuración was already
/// open at the case's start, and passed whenever it was closed): the sub-goal's first look was the open window on
/// «Inicio», the mind's rule opened the section by its address (app.open, placeOpened) and the section came selected;
/// the check «control:X:current» never held because an opening «moved nothing», the rule clicked the section again
/// (select only), the model's «done» was refused (the name was on screen before) and its retry said «none»: «no vi un
/// control» with the page on screen. The encoder (cold at 13–16 s in every bank, ready at ~19–23 s) took no part.
/// </summary>
[TestFixture]
public sealed class EstabE5LugarAbiertoTests
{
    private static readonly string[] Sections =
    [
        "Inicio", "Sistema", "Bluetooth y dispositivos", "Red e Internet", "Personalización", "Aplicaciones", "Cuentas",
        "Hora e idioma", "Juegos", "Accesibilidad", "Privacidad y seguridad", "Windows Update",
    ];

    // The look of the case's step 3 (model_calls.jsonl of evidencia_fw3/v2-<case>): the side list with the section
    // selected and focused, its header (Button and Text in T) and two entries of its page.
    private static JsonObject Settings(string section, params string[] page)
    {
        var controls = new JsonArray
        {
            new JsonObject { ["i"] = 1, ["kind"] = "Button", ["name"] = "Minimizar Configuración", ["zone"] = "TR" },
            new JsonObject { ["i"] = 4, ["kind"] = "Edit", ["name"] = "Cuadro de búsqueda, Buscar una opción", ["zone"] = "T" },
            new JsonObject { ["i"] = 5, ["kind"] = "Button", ["name"] = "Atrás", ["zone"] = "TL" },
        };
        int index = 7;
        foreach (string name in Sections)
        {
            controls.Add(new JsonObject
            {
                ["i"] = index++,
                ["kind"] = "ListItem",
                ["name"] = name,
                ["state"] = name == section ? "selected focused" : "",
                ["zone"] = index <= 10 ? "TL" : "L",
            });
        }

        controls.Add(new JsonObject { ["i"] = index++, ["kind"] = "Button", ["name"] = section, ["zone"] = "T" });
        foreach (string entry in page)
        {
            controls.Add(new JsonObject { ["i"] = index++, ["kind"] = "ListItem", ["name"] = entry, ["state"] = "", ["zone"] = "C" });
        }

        controls.Add(new JsonObject { ["i"] = index, ["kind"] = "Text", ["name"] = section, ["zone"] = "T" });
        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = "Configuración",
                ["process"] = "SystemSettings",
                ["requested"] = true,
                ["focused"] = new JsonObject { ["kind"] = "ListItem", ["name"] = section },
            },
            ["controls"] = controls,
            // The sub-goal's first look: the window the harness left on «Inicio».
            ["selectedAtStart"] = new JsonArray("inicio"),
        };
    }

    // Step 1: the mind's rule opened the section by its address on the running window (journal: alreadyRunning,
    // placeOpened, frontChanged).
    private static JsonObject Opening(bool placeOpened) => new()
    {
        ["step"] = 1,
        ["operation"] = "app.open",
        ["appId"] = "Configuración",
        ["ok"] = true,
        ["changed"] = true,
        ["alreadyRunning"] = true,
        ["placeOpened"] = placeOpened,
    };

    // Step 2: the click rule pressed the section already selected (receipt: method select, selected, no surface change).
    private static JsonObject Click(string label) => new()
    {
        ["step"] = 2,
        ["operation"] = "input.visible.click",
        ["label"] = label,
        ["name"] = label,
        ["kind"] = "ListItem",
        ["ok"] = true,
        ["method"] = "select",
        ["selected"] = true,
        ["surfaceChanged"] = false,
        ["changed"] = true,
        ["broughtNew"] = false,
        ["appeared"] = new JsonArray(),
    };

    private static JsonObject Before(params (string Step, string Selected)[] looks)
    {
        var before = new JsonObject();
        foreach ((string step, string selected) in looks)
        {
            before[step] = new JsonArray(selected);
        }

        return before;
    }

    [TestCase("v3", "Sistema", "control:sistema:current|title:sistema|page:sistema|control:system:current|title:system|page:system|mark:sistema|mark:system", "Pantalla", "Sonido")]
    [TestCase("x3", "Accesibilidad", "control:accesibilidad:current|title:accesibilidad|page:accesibilidad|control:accessibility:current|title:accessibility|page:accessibility|mark:accesibilidad|mark:accessibility", "Tamaño de texto", "Lupa")]
    [TestCase("x4", "Personalización", "control:personalization:current|title:personalization|page:personalization|control:personalizacion:current|title:personalizacion|page:personalizacion|mark:personalization|mark:personalizacion", "Fondo", "Temas")]
    [TestCase("c5", "Personalización", "control:personalizacion:current|title:personalizacion|page:personalizacion|control:personalization:current|title:personalization|page:personalization|mark:personalizacion|mark:personalization", "Colores", "Temas")]
    public void TheSectionOpenedByItsAddressOnTheOpenWindowIsReached(string bankCase, string section, string check, string first, string second)
    {
        JsonObject afterOpening = Settings(section, first, second);
        afterOpening["selectedBeforeClick"] = Before(("1", "inicio"));
        JsonObject afterClick = Settings(section, first, second);
        afterClick["selectedBeforeClick"] = Before(("1", "inicio"), ("2", ComputerUseSuccessCheck.Fold(section)));
        Assert.Multiple(() =>
        {
            // The look right after the opening already holds it (the rule's second click and the model are never asked).
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, afterOpening, [Opening(placeOpened: true)], out string? by),
                Is.True, bankCase);
            Assert.That(by, Does.StartWith("control:"), bankCase);
            // The real sequence of fw2/fw3: the opening, then the click on the section already chosen.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, afterClick, [Opening(placeOpened: true), Click(section)], out _),
                Is.True, bankCase);
        });
    }

    // Counter-case: an opening that only brought the window up (no place by its address) still moves nothing; the
    // section shown selected with no act that moved the window there is not where it is.
    [Test]
    public void AnOpeningThatOpenedNoPlaceStillMovesNothing()
    {
        JsonObject view = Settings("Sistema", "Pantalla", "Sonido");
        view["selectedBeforeClick"] = Before(("1", "inicio"));
        Assert.That(ComputerUseSuccessCheck.Evaluate("control:sistema:current", view, [Opening(placeOpened: false)], out _), Is.False);
    }

    // Counter-case: after the place opened by its address, another section a later click only selected (its page never
    // drawn) is not reached; the opening is never the act that chose an entry chosen after it.
    [Test]
    public void ASectionOnlySelectedAfterThePlaceOpenedIsNotReached()
    {
        JsonObject view = Settings("Accesibilidad", "Pantalla", "Sonido");
        view["selectedBeforeClick"] = Before(("1", "inicio"), ("2", "sistema"));
        Assert.That(ComputerUseSuccessCheck.Evaluate("control:accesibilidad:current", view,
            [Opening(placeOpened: true), Click("Accesibilidad")], out _), Is.False);
    }
}
