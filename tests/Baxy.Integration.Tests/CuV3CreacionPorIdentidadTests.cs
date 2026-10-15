using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 20, palanca P4 (la parte del App). v3-08: «Agregar página» creó la página y el teclado quedó en su «Título de
/// página» vacío, pero la primera vista ya tenía un «Título de página» vacío (la página que estaba) y el juez rechazó
/// la cita como «seen_at_start». La primera vista guarda ahora los ids (UIA runtime id) de sus partes vacías y la
/// enfocada; una parte enfocada del mismo nombre con otro id, tras un clic creador que trajo algo nuevo, es nueva. Las
/// vistas son las del diagnóstico 8 de r18_tramo1.json, recortadas a lo que se juzga.
/// </summary>
[TestFixture]
public sealed class CuV3CreacionPorIdentidadTests
{
    private const string OldTitle = "42.3348.4.11";
    private const string NewTitle = "42.3348.4.97";

    private static JsonObject View(string focusedId, string? extraKind = null)
    {
        var view = JsonNode.Parse($$$"""
            {"window":{"title":"Sin título - OneNote","process":"onenote",
              "focused":{"kind":"Document","name":"Título de página","value":"","i":4}},
             "controls":[
              {"i":0,"kind":"Button","name":"Agregar página","id":"42.1","state":"","value":null},
              {"i":1,"kind":"TreeItem","name":"Crear una nueva sección","id":"42.2","state":"","value":null},
              {"i":2,"kind":"ListItem","name":"Comprar pan, leche y huevos","id":"42.3","state":"","value":null},
              {"i":3,"kind":"ListItem","name":"Sin título","id":"42.4","state":"selected","value":null},
              {"i":4,"kind":"Document","name":"Título de página","id":"{{{focusedId}}}","state":"focused","value":""}]}
            """)!.AsObject();
        if (extraKind is not null)
        {
            ((JsonArray)view["controls"]!).Add(new JsonObject
            {
                ["i"] = 5,
                ["kind"] = extraKind,
                ["name"] = "Plantillas de página",
                ["id"] = "42.9",
                ["state"] = "",
            });
        }

        return view;
    }

    private static JsonArray FirstIds() => ComputerUseSuccessCheck.FirstIds(View(OldTitle));

    [Test]
    public void TheFirstLookKeepsTheIdsOfItsEmptyAndFocusedParts()
    {
        JsonArray ids = FirstIds();

        Assert.That(ids.Select(id => (string?)id), Is.EquivalentTo(new[] { OldTitle }));
    }

    // Revisión 1 de P4: «crea un evento nuevo» pulsó «Nuevo evento» (broughtNew) y el foco quedó en el «Agregar un
    // título» vacío (id 9.2) de un formulario con «Guardar» y «Descartar»; la primera vista ya tenía un «Agregar un
    // título» vacío de otro formulario (id 9.1). El evento no existe hasta guardarlo.
    private static JsonObject EventView(string focusedId, params string[] buttons)
    {
        var controls = new JsonArray
        {
            new JsonObject { ["i"] = 0, ["kind"] = "Button", ["name"] = "Nuevo evento", ["id"] = "9.5", ["state"] = "" },
        };
        foreach (string button in buttons)
        {
            controls.Add(new JsonObject
            {
                ["i"] = controls.Count,
                ["kind"] = "Button",
                ["name"] = button,
                ["id"] = $"9.{controls.Count + 10}",
                ["state"] = "",
            });
        }

        controls.Add(new JsonObject
        {
            ["i"] = controls.Count,
            ["kind"] = "Edit",
            ["name"] = "Agregar un título",
            ["id"] = focusedId,
            ["state"] = "focused",
            ["value"] = "",
        });
        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = "Calendario",
                ["process"] = "calendario",
                ["focused"] = new JsonObject
                {
                    ["kind"] = "Edit",
                    ["name"] = "Agregar un título",
                    ["value"] = "",
                    ["i"] = controls.Count - 1,
                },
            },
            ["controls"] = controls,
        };
    }

    // Estabilización R16: that the empty part of a form still to save is no new part by identity, and that every button
    // that saves or confirms holds it, is the mind's judge's (cu_first_look._new_part_by_identity, _commit_on_offer:
    // tests/test_cu_v3_creacion_por_identidad.py); the App's twins (NewPartByIdentity, CommitOnOffer, FormButtonCited
    // and EvidenceRefusal) went. The App still gives the mind the first look's ids.
    [Test]
    public void TheFirstLookOfTheEventKeepsTheIdOfItsEmptyTitle()
    {
        Assert.That(ComputerUseSuccessCheck.FirstIds(EventView("9.1")).Select(id => (string?)id), Is.EquivalentTo(new[] { "9.1" }));
    }

    // Revisión 3 de P4: el «Guardar» de la barra de acceso rápido de Office está en toda vista (vistas en vivo de
    // tests/data: cu_v3_vistas_buscar.json word_insertar, cu_semejanza_vistas.json Word, PowerPoint y Paint); no es
    // un formulario que trajo el subobjetivo.
    private static JsonObject WordView(string bulletsState) => JsonNode.Parse($$$"""
        {"window":{"title":"Documento1 - Word","process":"WINWORD","focused":{"kind":"Document","name":"Documento1"}},
         "controls":[
          {"i":0,"kind":"Button","name":"Guardar","state":""},
          {"i":1,"kind":"Button","name":"Deshacer","state":""},
          {"i":2,"kind":"TabItem","name":"Inicio","state":"selected"},
          {"i":3,"kind":"SplitButton","name":"Viñetas","state":"{{{bulletsState}}}"},
          {"i":4,"kind":"Document","name":"Documento1","state":"focused","value":"pan leche"}]}
        """)!.AsObject();

    [Test]
    public void WordsQuickAccessSaveIsNoFormToSave()
    {
        JsonObject view = WordView("on");
        view["newTextAfterClick"] = new JsonArray();
        string firstLook = ComputerUseSuccessCheck.LookText(WordView(string.Empty));
        // Estabilización R16: the done citing «Viñetas» is the mind's judge's (tests/test_cu_v3_creacion_por_identidad.py,
        // test_word_s_quick_access_save_is_no_form_to_save); the App reads whether a «Guardar» was brought.
        Assert.Multiple(() =>
        {
            // The same «Guardar» that the click made appear is a form's.
            JsonObject brought = WordView("on");
            brought["newTextAfterClick"] = new JsonArray("Guardar");
            Assert.That(ComputerUseSuccessCheck.BroughtThisSubgoal(
                (JsonObject)brought["controls"]![0]!, brought, firstLook), Is.True);
            Assert.That(ComputerUseSuccessCheck.BroughtThisSubgoal((JsonObject)view["controls"]![0]!, view, firstLook),
                Is.False);
        });
    }

    [Test]
    public void TheMindsJudgeGetsTheIds()
    {
        var state = new JsonObject { ["subgoalFirstIds"] = FirstIds() };
        JsonObject view = View(NewTitle);

        JsonObject judged = ComputerUseMission.ForTheJudge(ComputerUseMission.CompactForTheMind(view), state, null, view);

        Assert.Multiple(() =>
        {
            Assert.That(judged["firstIds"]!.AsArray().Select(id => (string?)id), Is.EqualTo(new[] { OldTitle }));
            Assert.That((string?)judged["focusedId"], Is.EqualTo(NewTitle));
            Assert.That(judged["controls"]!.AsArray().OfType<JsonObject>().All(control => control["id"] is null),
                "the ids stay out of the controls the model reads");
        });
    }
}
