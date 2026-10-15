using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Pasada r15b, segunda vuelta (2026-10-09), la parte del App. t-scroll-3 «Go to Settings, Personalization, Fonts,
/// scroll down to Times New Roman and open its page»: Configuración ya estaba abierta (app.open la halló corriendo,
/// alreadyRunning true); la misión entró a Personalización y Fuentes, escribió, bajó y pulsó «Times New Roman» (la
/// página cambió); su último clic en el mismo nombre dejó el árbol como estaba y el App paró con
/// computer_use_already_there_unconfirmed: el final dijo «you were already in Times New Roman», falso, porque fueron
/// los pasos de la misión los que llevaron la ventana ahí. Los pasos son los de la evidencia (v2-t-scroll-3),
/// recortados a lo que se juzga, con la forma que RecordResponse les da (todo app.open, input.key.press e
/// input.text.type ok llevan changed:true).
/// </summary>
[TestFixture]
public sealed class CuV3HonestidadR15b2ScrollMenuTests
{
    // v2-t-scroll-3, último turno: los pasos de la misión, recortados.
    private const string ScrollSteps = """
        [{"step":1,"operation":"app.open","source":"procedure","appId":"Configuración","ok":true,"alreadyRunning":true,"sameView":true,"changed":true},
         {"step":2,"operation":"input.visible.click","label":"Personalización","kind":"ListItem","ok":true,"surfaceChanged":true,"changed":true},
         {"step":6,"operation":"input.text.type","text":"fuentes","index":4,"ok":true,"method":"setvalue","changed":true},
         {"step":9,"operation":"input.scroll","direction":"down","ok":true},
         {"step":10,"operation":"input.visible.click","label":"Times New Roman","kind":"Text","ok":true,"method":"pointer","surfaceChanged":true},
         {"step":12,"operation":"input.text.type","text":"times new roman","ok":true,"method":"keyboard","changed":true},
         {"step":17,"operation":"input.visible.click","label":"Times New Roman","kind":"Button","ok":true,"method":"invoke","surfaceChanged":false}]
        """;

    [Test]
    public void AMissionThatBroughtTheWindowThereNeverStopsAsAlreadyThere()
    {
        JsonArray steps = JsonNode.Parse(ScrollSteps)!.AsArray();
        Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow(steps), Is.True);
    }

    [Test]
    public void AWindowFoundOnThePlaceWithOnlyTheClickThatLeftItAsItWasStillMayBeAlreadyThere()
    {
        // Live v2-s12: Steam already running on its library; the learned click on «BIBLIOTECA» only opened its menu.
        JsonArray found = JsonNode.Parse("""
            [{"step":1,"operation":"app.open","appId":"Steam","ok":true,"alreadyRunning":true,"sameView":true,"changed":true},
             {"step":2,"operation":"input.visible.click","label":"BIBLIOTECA","ok":true,"surfaceChanged":false,"changed":false}]
            """)!.AsArray();
        Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow(found), Is.False);

        // A step that failed changed nothing the mission can claim; the last step itself is the click judged.
        JsonArray failed = JsonNode.Parse("""
            [{"step":1,"operation":"input.text.type","text":"x","ok":false},
             {"step":2,"operation":"input.visible.click","label":"Inicio","ok":true,"surfaceChanged":true}]
            """)!.AsArray();
        Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow(failed), Is.False);

        // The application opened by the mission (not found running) moved the window.
        JsonArray opened = JsonNode.Parse("""
            [{"step":1,"operation":"app.open","appId":"Steam","ok":true,"alreadyRunning":false,"changed":true},
             {"step":2,"operation":"input.visible.click","label":"BIBLIOTECA","ok":true,"surfaceChanged":false}]
            """)!.AsArray();
        Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow(opened), Is.True);
    }

    [Test]
    public void AnApplicationFoundRunningAndAKeyThatChangedNothingNeverCountAsMovingTheWindow()
    {
        // Review of the branch (finding 1): RecordResponse marks every ok app.open and input.key.press changed:true;
        // a mission that only found its application running and pressed a key that changed nothing still may stop as
        // already there.
        JsonArray found = JsonNode.Parse("""
            [{"step":1,"operation":"app.open","appId":"Configuración","ok":true,"alreadyRunning":true,"changed":true},
             {"step":2,"operation":"input.key.press","key":"escape","ok":true,"changed":true},
             {"step":3,"operation":"input.visible.click","label":"Fuentes","ok":true,"surfaceChanged":false,"changed":false}]
            """)!.AsArray();
        Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow(found), Is.False);

        // Counter-cases: a key whose receipt saw the surface change moved it, and so did an app.open that made a new
        // document in an application already running.
        JsonArray keyed = JsonNode.Parse("""
            [{"step":1,"operation":"app.open","appId":"Configuración","ok":true,"alreadyRunning":true,"changed":true},
             {"step":2,"operation":"input.key.press","key":"enter","ok":true,"surfaceChanged":true,"changed":true},
             {"step":3,"operation":"input.visible.click","label":"Fuentes","ok":true,"surfaceChanged":false,"changed":false}]
            """)!.AsArray();
        Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow(keyed), Is.True);

        JsonArray made = JsonNode.Parse("""
            [{"step":1,"operation":"app.open","appId":"Bloc de notas","ok":true,"alreadyRunning":true,"newDocument":true,"changed":true},
             {"step":2,"operation":"input.visible.click","label":"Archivo","ok":true,"surfaceChanged":false,"changed":false}]
            """)!.AsArray();
        Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow(made), Is.True);
    }
}
