using System.IO;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M146 (DEV-D/F/G/H v4m–v4q, 2026-10-03): composition vetoes that killed correct replies and left the turn with no
/// final. The App's side of tests/test_c03_m146_vetos_de_mas.py.
/// <list type="bullet">
/// <item>F-w34-t2 «¿Y si al final somos ocho?»: the consulted recipe for eight, which the mind published, was refused
/// here as internal_code twice (v4o, v4p): the page's «(del tamaño de una uña)» folded to «una una», a stutter. A stutter
/// is the same word as written; «ñ» is a letter and «esta está» two words.</item>
/// <item>G-s087, G-s116, F-w47-t4: the drafts the mind now lets out are accepted here as well.</item>
/// <item>H-w37-t1: «El router está conectado a internet.» stays refused here; the mind now reads the person's words
/// as this twin does (UserMessagePolicy.LeakedInternalTerm), so it retries instead of publishing it.</item>
/// </list>
/// </summary>
[TestFixture]
public sealed class M146VetosDeMasTests
{
    private static readonly JsonNode Evidence = JsonNode.Parse(File.ReadAllText(Path.Combine(
        FindRepositoryRoot(), "tests", "data", "c03_m146_evidence.json")))!;

    private const string Recipe =
        """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"query":"receta tortilla de patatas","count":1,"results":[{"title":"Tortilla de patatas","url":"https://es.wikibooks.org/wiki/Artes_culinarias/Recetas/Tortilla_de_patatas","snippet":"Ingredientes (para 4 personas): 8 huevos, 1 kg de patatas, 1 cebolla. Se parte la cebolla en cuadraditos pequeños (del tamaño de una uña)."}],"reference":"recipe","servings":4,"authority":"wikibooks_es_api"}}""";

    private const string PdfAbsent =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"document.pdf.read","polarity":"failure","verified":false,"succeeded":false,"error":"known_file_not_found","target":"contrato de alquiler.pdf","attempted":{"fileName":"contrato de alquiler.pdf","folder":"documents"}}}""";

    private const string SpotifyJazz =
        """{"kind":"status","polarity":"success","cause":"mission_completed","stepCount":2,"steps":["{\"kind\":\"operation\",\"operation\":\"app.open\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"appId\":\"Spotify\",\"displayName\":\"Spotify\",\"alreadyRunning\":true,\"windowHandle\":262790},\"readOnly\":false}","{\"kind\":\"operation\",\"operation\":\"media.play.query\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"version\":1,\"provider\":\"spotify\",\"title\":\"Vendla - After Winter Comes Spring\",\"query\":\"jazz tranquilo\",\"playbackStatus\":\"playing\",\"authority\":\"spotify_windows_uia_postread\"},\"readOnly\":false}"],"completedRequest":"Abrí Spotify y pon algo de jazz tranquilo."}""";

    private const string Online =
        """{"kind":"operation","operation":"network.status","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"online":true,"connectedInterfaceCount":14,"interfaceTypes":["53","ethernet"]}}""";

    private const string BostonNote =
        """{"kind":"operation","operation":"note.create","polarity":"success","verified":true,"succeeded":true,"observed":{"title":"en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro","content":"En noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro?","revision":1,"isTrashed":false}}""";

    private static string? Reason(string source, string intent, string reply, string request, string? prior = null) =>
        UserMessagePolicy.ModelResponseRejectionReason(reply, new UserMessageDraft(source, intent, null), request, prior);

    // F-w34-t2 v4o/v4p: the published draft, word for word, over its recorded search.
    [Test]
    public void TheRecipeForEightIsNoStutter()
    {
        JsonNode row = Evidence["F-w34-t2"]!;
        Assert.That(
            Reason((string)row["situation"]!, "status", (string)row["draft"]!, (string)row["user"]!,
                "Oye, ¿cómo se hace una tortilla de patatas para cuatro personas? Con cebolla, eh, que en casa somos de cebolla"),
            Is.Null);
    }

    [TestCase("Se parte la cebolla en cuadraditos pequeños (del tamaño de una uña) y se doran en la sartén.")]
    [TestCase("Pica el ajo en trocitos del tamaño de una uña.")]
    [TestCase("Esta está lista: la tortilla para ocho lleva 16 huevos.")]
    public void AWordWithItsMarksIsNotTheWordWithout(string reply)
    {
        Assert.That(Reason(Recipe, "status", reply, "¿Y si al final somos ocho?"), Is.Null);
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason("¿cómo corto la cebolla para la tortilla?", reply),
            Is.Not.EqualTo("repeated_word"));
    }

    // What does not change: the same word written twice is still a stutter, in a report and in talk.
    [TestCase("Se parte la cebolla cebolla en cuadraditos.")]
    [TestCase("Está sonando sonando la canción.")]
    public void TheSameWordTwiceIsStillAStutter(string reply)
    {
        Assert.That(Reason(Recipe, "status", reply, "¿Y si al final somos ocho?"), Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason("¿cómo corto la cebolla?", reply),
            Is.EqualTo("repeated_word"));
    }

    // G-s087 v4p/v4q: the first and the third draft, which the mind now lets out.
    [TestCase("No pude leer el contrato de alquiler porque el archivo no se encontró en la carpeta documentos.")]
    [TestCase("No pude leer el contrato porque el archivo no se encontró en la carpeta de documentos.")]
    public void TheMissingContractIsTold(string reply)
    {
        Assert.That(
            Reason(PdfAbsent, "error", reply, "resúmeme el pdf del contrato de alquiler que tengo en documentos, porfa"),
            Is.Null);
    }

    // G-s116 v4p/v4q: the first and the third draft.
    [TestCase("Abrí Spotify y reproduciendo \"Vendla - After Winter Comes Spring\" para que tengas jazz tranquilo mientras trabajas.")]
    [TestCase("Abrí Spotify y ya está reproduciendo \"Vendla - After Winter Comes Spring\" en modo jazz tranquilo.")]
    public void TheMissionPlaybackIsTold(string reply)
    {
        Assert.That(
            Reason(SpotifyJazz, "status", reply,
                "abrí spotify y ponime algo de jazz tranqui, que estoy laburando y necesito algo de fondo"),
            Is.Null);
    }

    // H-w37-t1 v4q: refused here on the person's words, and accepted when the person said the word.
    [Test]
    public void TheRouterNobodySaidIsStillJargon()
    {
        Assert.That(
            Reason(Online, "status", "El router está conectado a internet.", "toy conectado a internet? me anda re lento todo"),
            Is.EqualTo("unsafe_language"));
        Assert.That(
            Reason(Online, "status", "Sí, el router está conectado a internet.", "mi router está conectado a internet?"),
            Is.Null);
    }

    // F-w47-t4: what the retry is now told to write, the note named by its quoted title.
    [Test]
    public void TheNoteIsNamedByItsQuotedTitle()
    {
        Assert.That(
            Reason(BostonNote, "status",
                "Guardé la nota «en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro».",
                "Apúntamelo en una nota, que luego se me olvida"),
            Is.Null);
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(System.AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("No repository root above the test directory.");
    }
}
