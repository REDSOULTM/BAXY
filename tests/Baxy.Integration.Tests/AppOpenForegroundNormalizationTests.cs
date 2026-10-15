using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// v3 point 0 (arreglo 4), owner's rule: a bare «abre X» outside computer use brings the application to the front; an
/// opening the plan makes for a computer-use mission stays behind the person's window unless the mind asked for the
/// front; an explicit «foreground» is never changed; other operations get nothing.
/// </summary>
[TestFixture]
public sealed class AppOpenForegroundNormalizationTests
{
    [Test]
    public void AStandaloneOpeningComesToTheFront()
    {
        JsonObject normalized = MindArgumentNormalization.Normalize(
            "app.open", "abre spotify", new JsonObject { ["appId"] = "Spotify" });

        Assert.That((bool?)normalized["foreground"], Is.True);
    }

    [Test]
    public void AnOpeningForAComputerUseMissionStaysBehind()
    {
        JsonObject normalized = MindArgumentNormalization.Normalize(
            "app.open", "abre steam y ve a la biblioteca", new JsonObject { ["appId"] = "Steam" }, beforeComputerUse: true);

        Assert.That(normalized.ContainsKey("foreground"), Is.False);
    }

    [TestCase(true, false)]
    [TestCase(false, true)]
    public void AnExplicitForegroundIsKept(bool beforeComputerUse, bool said)
    {
        JsonObject normalized = MindArgumentNormalization.Normalize(
            "app.open", "abre steam", new JsonObject { ["appId"] = "Steam", ["foreground"] = said }, beforeComputerUse);

        Assert.That((bool?)normalized["foreground"], Is.EqualTo(said));
    }

    [Test]
    public void TheAliasIsStillCanonicalAndTheExtractedArgumentsAreNotChanged()
    {
        var extracted = new JsonObject { ["appId"] = "notepad" };

        JsonObject normalized = MindArgumentNormalization.Normalize("app.open", "abre el bloc de notas", extracted);

        Assert.Multiple(() =>
        {
            Assert.That((string?)normalized["appId"], Is.EqualTo("windows.notepad"));
            Assert.That((bool?)normalized["foreground"], Is.True);
            Assert.That(extracted.ContainsKey("foreground"), Is.False);
        });
    }

    // v3 r5a M5: an opening the plan makes for a computer-use mission is for control (the person's rights for a program
    // Windows would raise unasked); another operation is not, nor a mission's click. cu-v3-elevacion (r9 v3-23, v3-65):
    // a standalone «abre X» is too, since the next turn works on the window it opened; only a request that asks for
    // administrator rights keeps the shell's path.
    [Test]
    public void EveryOpeningIsForControlUnlessAdministratorRightsAreAsked()
    {
        var extracted = new JsonObject { ["appId"] = "Steam" };
        JsonObject mission = MindArgumentNormalization.Normalize(
            "app.open", "abre steam y ve a la biblioteca", extracted, beforeComputerUse: true);
        JsonObject standalone = MindArgumentNormalization.Normalize("app.open", "abre steam", new JsonObject { ["appId"] = "Steam" });
        JsonObject other = MindArgumentNormalization.Normalize(
            "app.installed", "tengo steam?", new JsonObject { ["name"] = "Steam" }, beforeComputerUse: true);
        var click = new JsonObject { ["label"] = "Biblioteca" };
        ComputerUseMission.MarkOpeningForControl("input.visible.click", click);
        var opening = new JsonObject { ["appId"] = "Steam" };
        ComputerUseMission.MarkOpeningForControl("app.open", opening);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)mission["forControl"], Is.True);
            Assert.That(extracted.ContainsKey("forControl"), Is.False, "the extracted arguments are not changed");
            Assert.That((bool?)standalone["forControl"], Is.True);
            Assert.That(other.ContainsKey("forControl"), Is.False);
            Assert.That(click.ContainsKey("forControl"), Is.False);
            Assert.That((bool?)opening["forControl"], Is.True);
        });
    }

    // Twins of r9 (v3-65 «abre servicios», v3-23 «abre el visor de eventos», v3-22 «abrí el administrador de tareas»)
    // and their counter-cases: asked as administrator (Spanish, English, Spanglish), the opening keeps the shell's path.
    [TestCase("abre servicios", "Servicios", true)]
    [TestCase("abre el visor de eventos", "Visor de eventos", true)]
    [TestCase("abrí el administrador de tareas", "Administrador de tareas", true)]
    [TestCase("open task manager", "Administrador de tareas", true)]
    [TestCase("abrí el administrador de tareas como administrador", "Administrador de tareas", false)]
    [TestCase("abre servicios como admin", "Servicios", false)]
    [TestCase("abre el Visor de Eventos con permisos de administrador", "Visor de eventos", false)]
    [TestCase("open services as administrator", "Servicios", false)]
    [TestCase("abrime el task manager as admin porfa", "Administrador de tareas", false)]
    [TestCase("abre la consola elevada de servicios", "Servicios", false)]
    // Review of cu-v3-elevacion (finding 3): «elevado/elevated» about something else asks for no rights.
    [TestCase("abrí servicios y decime cuáles tienen un consumo elevado", "Servicios", true)]
    [TestCase("open task manager and check whether CPU is elevated", "Administrador de tareas", true)]
    [TestCase("abrime el task manager, la CPU está muy elevada", "Administrador de tareas", true)]
    [TestCase("open services in an elevated window", "Servicios", false)]
    public void AStandaloneOpeningHasThePersonsRightsUnlessAdministratorIsAsked(string request, string appId, bool personRights)
    {
        JsonObject normalized = MindArgumentNormalization.Normalize("app.open", request, new JsonObject { ["appId"] = appId });

        Assert.Multiple(() =>
        {
            Assert.That(normalized.ContainsKey("forControl"), Is.EqualTo(personRights));
            Assert.That((bool?)normalized["foreground"], Is.True);
        });
    }

    // Review of cu-v3-elevacion (finding 2): a «forControl» the extractor wrote never decides. «abre servicios» with a
    // model's false still opens with the person's rights (the console is not raised unasked); «como administrador» with
    // a model's true still keeps the shell's path; in a plan for a mission too.
    [TestCase("abre servicios", false, false, true)]
    [TestCase("abre servicios", true, false, true)]
    [TestCase("abre servicios y cambiala a la vista estándar", false, true, true)]
    [TestCase("abre servicios como administrador", true, false, false)]
    [TestCase("open services as administrator", false, false, false)]
    [TestCase("abrime services as admin y fijate el spooler", true, true, false)]
    public void AnExtractedForControlNeverDecides(string request, bool extracted, bool beforeComputerUse, bool personRights)
    {
        var arguments = new JsonObject { ["appId"] = "Servicios", ["forControl"] = extracted };

        JsonObject normalized = MindArgumentNormalization.Normalize("app.open", request, arguments, beforeComputerUse);

        Assert.Multiple(() =>
        {
            Assert.That(normalized.ContainsKey("forControl"), Is.EqualTo(personRights));
            if (personRights)
                Assert.That((bool?)normalized["forControl"], Is.True);
            Assert.That((bool?)arguments["forControl"], Is.EqualTo(extracted), "the extracted arguments are not changed");
        });
    }

    // molestia-ayudantes (riesgos-fusion 5): «abre paisaje.jpg en Fotos» is a file the person asked to see: it comes to
    // the front as a bare «abre X» does. The rights stay app.open's: a file.open gets no «forControl» argument.
    [TestCase("abre paisaje.jpg en Fotos")]
    [TestCase("open notes.txt in notepad")]
    [TestCase("ábreme el informe.docx con word porfa")]
    public void AFileThePersonAskedToSeeComesToTheFront(string request)
    {
        var extracted = new JsonObject { ["folder"] = "pictures", ["name"] = "paisaje.jpg", ["application"] = "Fotos" };

        JsonObject normalized = MindArgumentNormalization.Normalize("file.open", request, extracted);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)normalized["foreground"], Is.True);
            Assert.That(normalized.ContainsKey("forControl"), Is.False);
            Assert.That(extracted.ContainsKey("foreground"), Is.False, "the extracted arguments are not changed");
        });
    }

    // Review of molestia-ayudantes, 5: a file opened with its default program (no «application») is one the person
    // asked to see too: it carries «foreground», so the App lets the program it starts take the front (the adapter's
    // shell opening reads no argument of it). Outside a mission only; the contracase below holds for it as well.
    [TestCase("abre paisaje.jpg", false, true)]
    [TestCase("open notes.txt", false, true)]
    [TestCase("abre notas.txt y escribe hola", true, false)]
    public void AFileOpenedWithItsDefaultProgramFollowsTheSameRule(string request, bool forMission, bool shown)
    {
        var extracted = new JsonObject { ["folder"] = "pictures", ["name"] = "paisaje.jpg" };

        JsonObject normalized = MindArgumentNormalization.Normalize(
            "file.open", request, extracted, beforeComputerUse: forMission);

        Assert.Multiple(() =>
        {
            Assert.That(normalized.ContainsKey("foreground"), Is.EqualTo(shown));
            if (shown)
                Assert.That((bool?)normalized["foreground"], Is.True);
            Assert.That(normalized.ContainsKey("forControl"), Is.False);
        });
    }

    // Contracases: a file the plan opens for a computer-use mission to work in stays behind; an explicit «foreground»
    // is kept.
    [Test]
    public void AFileOpenedForAMissionStaysBehindAndAnExplicitForegroundIsKept()
    {
        JsonObject forMission = MindArgumentNormalization.Normalize(
            "file.open", "abre notas.txt en el bloc de notas y escribe hola",
            new JsonObject { ["folder"] = "documents", ["name"] = "notas.txt", ["application"] = "Bloc de notas" },
            beforeComputerUse: true);
        JsonObject said = MindArgumentNormalization.Normalize(
            "file.open", "abre notas.txt",
            new JsonObject { ["folder"] = "documents", ["name"] = "notas.txt", ["foreground"] = false });

        Assert.Multiple(() =>
        {
            Assert.That(forMission.ContainsKey("foreground"), Is.False);
            Assert.That((bool?)said["foreground"], Is.False);
        });
    }

    [Test]
    public void AnotherOperationGetsNoForeground()
    {
        var extracted = new JsonObject { ["name"] = "Spotify" };

        JsonObject normalized = MindArgumentNormalization.Normalize("app.installed", "tengo spotify?", extracted);

        Assert.That(normalized.ContainsKey("foreground"), Is.False);
    }
}
