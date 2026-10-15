using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 20 P6, la parte del App. v3-16 (pasada r18, model_calls request 8): el done citó «paisaJe.Jpg | Restablecer | 9»,
/// literalmente la línea «texto TL» de la vista (sus líneas unidas por « | »), y se rechazó porque la vista une sus
/// líneas con un espacio. Una cita partida está en la vista cuando cada trozo lo está; lo visto al empezar exige que al
/// menos un trozo sea nuevo. Y la traza «computer_use.surface» dice por qué la vista tomó, o no, la ventana de
/// contenido de un marco que sólo mostraba su cromo.
/// </summary>
[TestFixture]
public sealed class CuV3CitaPartidaTests
{
    // v2-v3-16 paso 3: el marco con su cromo y lo que el OCR leyó del editor.
    private static JsonObject EditorSeen() => (JsonObject)JsonNode.Parse("""
        {"window":{"title":"paisaje.jpg","process":"Photos"},
         "controls":[{"i":0,"kind":"Button","name":"Minimize"},{"i":3,"kind":"Button","name":"Atrás"},
          {"i":8,"kind":"TitleBar","name":"paisaje.jpg"}],
         "text":{"TL":["paisaJe.Jpg","Restablecer","9"],"TR":["Opciones para guardar v","Cancelar"],"C":["16:9"],
          "B":["1920 x 1080","Libre"]}}
        """)!;

    [Test]
    public void V3_16_ACitationOfAWholeListedLineIsInTheView()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ViewContains(EditorSeen(), "paisaJe.Jpg | Restablecer | 9"), Is.True);
            Assert.That(ComputerUseSuccessCheck.ViewContains(EditorSeen(), "Restablecer | 16:9"), Is.True);
            Assert.That(ComputerUseSuccessCheck.CitationPieces("paisaJe.Jpg | Restablecer | 9"),
                Is.EqualTo(new[] { "paisaJe.Jpg", "Restablecer", "9" }));
            // Counter-case: one piece the view does not hold and the citation is not in it.
            Assert.That(ComputerUseSuccessCheck.ViewContains(EditorSeen(), "paisaJe.Jpg | Filtros"), Is.False);
            Assert.That(ComputerUseSuccessCheck.ViewContains(EditorSeen(), "Restablecer | Monocromo | 9"), Is.False);
        });
    }

    [Test]
    public void TheSurfaceOfAChromeOnlyFrameIsTraced()
    {
        JsonObject taken = EditorSeen();
        taken["window"]!["surface"] = new JsonObject { ["reason"] = "under", ["exStyle"] = "08280080", ["owner"] = 0 };
        JsonObject refused = EditorSeen();
        refused["window"]!["surface"] = new JsonObject { ["reason"] = "app_window", ["exStyle"] = "02040100", ["owner"] = 65802 };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.SurfaceTrace(taken, 3), Is.EqualTo("step.3.under.ex.08280080.owner.0"));
            Assert.That(ComputerUseMission.SurfaceTrace(refused, 4), Is.EqualTo("step.4.app_window.ex.02040100.owner.1010a"));
            // A look of a window whose tree is its own says nothing of it.
            Assert.That(ComputerUseMission.SurfaceTrace(EditorSeen(), 3), Is.Null);
        });
    }
}
