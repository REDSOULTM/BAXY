using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo IMP2: the finals the mind now says from its floor, over the live facts of their turns (imp1 on the notebook,
/// banco fix2 g1), are published by the App as they are. g1 (banco fix2, 2 of 2): «Llegué a «BIBLIOTECA», pero lo que
/// sigue no lo puedo hacer: …» carried no «no puedo» in a row and died here as reversed_result, so the App's twin said
/// «No pude hacerlo en «Steam»: el buscador de ese lugar…» without the place nor the offer; the data now say «no puedo
/// hacer lo que sigue».
/// </summary>
[TestFixture]
public sealed class EstabImp2FinalsTests
{
    // banco fix2 g1, compose_audit (floor_first).
    private const string G1 = """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"mission.computer.use","polarity":"failure","verified":false,"succeeded":false,"error":"computer_use_limit_place_search","observed":{"goal":"ir a biblioteca; luego buscar Cuphead","application":"Steam","reached":false,"stepCount":1,"steps":[{"step":1,"operation":"app.open","source":"model","subgoal":0,"appId":"Steam","place":"library","ok":true,"alreadyRunning":true,"frontChanged":true,"frontRestored":true,"placeOpened":true,"changed":true}],"window":{"title":"Steam","process":"steamwebhelper","requested":true,"root":265376,"foreground":false,"rect":{"x":1,"y":1,"w":1918,"h":1018},"coveredBy":{"title":"@Ron92 - Discord","process":"Discord"}},"joined":false,"elapsedMs":3485,"modelMs":12,"authority":"shell_loop_over_uia_ocr_postread","subgoals":[{"goal":"ir a biblioteca","application":"Steam","reached":true,"stepCount":1,"satisfiedBy":"mark:biblioteca","successCheck":"control:biblioteca:current|title:biblioteca|page:biblioteca|control:library:current|title:library|page:library|mark:biblioteca|mark:library","numbers":["PARCHE 5.01","14"],"witness":{"atom":"mark:biblioteca","via":"mark.TL","shown":"BIBLIOTECA ink=blue","read":"2621253a-9525-41b7-9e5e-7d77cdaa0b35"},"arrivedAs":"BIBLIOTECA","acted":true},{"goal":"buscar Cuphead","application":"Steam","reached":false,"stepCount":0,"successCheck":"stepDone:input.text.type&stepDone:input.key.press:enter&text:cuphead"}],"screen":{"title":"Steam","values":[{"name":"BIBLIOTECA","state":"selected"},{"name":".Modo_demO.TM v","state":"selected"}],"numbers":["PARCHE 5.01","14"],"lines":["PARCHE 5.01","LISTA","CAMBIOS","ASCENDED TEROS ERUPTS OCTOBER","14","u"],"controlLines":[0,1,2,3,4,5]},"stoppedBy":"computer_use_limit_place_search"}}}""";

    // imp1 imp-steam-instalar, compose_audit.
    private const string SteamInstall = """{"kind":"operation","operation":"game.install.named","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"jobId":"steam_job_d0f718abb62c271e6665a051","appId":"40800","name":"Super Meat Boy","state":"queued","bytesDownloaded":0,"bytesTotal":0,"authority":"steam_manifest_transition"}}""";

    // imp1 imp-wa-enviar, compose_audit (floor_first).
    private const string WhatsAppResolve = """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"message.recipient.resolve","polarity":"failure","verified":false,"succeeded":false,"error":"search_focus_not_verified","cause":"external_effect_ambiguous","effectUncertain":true,"target":"Música","attempted":{"channel":"whatsapp","recipient":"Música"},"notDone":[{"operation":"message.send","target":"Música"}]}}""";

    // imp1 imp-dc-salir-voz's mission, stopped as the mind now stops it (cu_chats.call_not_found).
    private const string NoCall = """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"mission.computer.use","polarity":"failure","verified":false,"succeeded":false,"error":"computer_use_limit_call_not_found","observed":{"goal":"hacer clic en desconectar","application":"Discord","reached":false,"stepCount":1,"steps":[{"step":1,"operation":"input.visible.click","source":"model","label":"desconectar","ok":false,"error":"visible_button_not_found"}],"window":{"title":"Cotele!!!😎 | Choche - Discord","process":"Discord","requested":true},"stoppedBy":"computer_use_limit_call_not_found"}}}""";

    // imp3 imp-wa-leer's mission, reached (its situation, without the screen lines).
    private const string WhatsAppRead = """{"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,"observed":{"goal":"ir a musica; y responder: leé lo último que me escribieron en Música","application":"WhatsApp","reached":true,"satisfiedBy":"page:musica"}}""";

    // The same, with the chat's lines its final reads (screen.chatLines, read by NoteTheChatLinesAsync).
    private const string WhatsAppReadLines = """{"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,"observed":{"goal":"ir a musica; y responder: leé lo último que me escribieron en Música","application":"WhatsApp","reached":true,"satisfiedBy":"page:musica","screen":{"title":"(5) WhatsApp","chatLines":[{"text":"nos vemos a las nueve","x":0.262,"y":0.7,"w":0.11,"h":0.0153},{"text":"21:10","x":0.38,"y":0.706,"w":0.02,"h":0.0105}]}}}""";

    [TestCase(G1, "error", "buscá Cuphead en mi biblioteca de Steam",
        "Llegué a «BIBLIOTECA», pero no puedo hacer lo que sigue: el buscador de la biblioteca no me deja escribir; si querés, lo busco en la tienda.")]
    [TestCase(SteamInstall, "status", "instalá Super Meat Boy en Steam", "Listo, empecé a instalar el juego «Super Meat Boy».")]
    [TestCase(WhatsAppResolve, "error", "en WhatsApp mandale a Música \"prueba BAXY imp\"",
        "No pude enviar el mensaje a «Música», porque el buscador de chats no tomó el nombre, así que no abrí el chat ni envié nada.")]
    [TestCase(WhatsAppRead, "status", "en WhatsApp leé lo último que me escribieron en Música",
        "En lo que muestra el chat, lo último es tuyo: no hay mensajes de otra persona.")]
    [TestCase(WhatsAppReadLines, "status", "en WhatsApp leé lo último que me escribieron en Música",
        "Lo último que te escribieron fue «nos vemos a las nueve» (21:10).")]
    [TestCase(NoCall, "error", "en Discord salí del canal de voz", "No estás en ningún canal de voz ni llamada, así que no pulsé nada.")]
    public void TheFloorsFinalIsPublishedAsItIs(string source, string intent, string userText, string final)
    {
        var draft = new UserMessageDraft(source, intent, null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(final, draft, userText, null), Is.Null);
    }

    [Test]
    public void ContracaseTheOldWordingOfTheLimitWasReadAsAReversedResult()
    {
        var draft = new UserMessageDraft(G1, "error", null);
        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
                "Llegué a «BIBLIOTECA», pero lo que sigue no lo puedo hacer: el buscador de la biblioteca no me deja escribir; si querés, lo busco en la tienda.",
                draft, "buscá Cuphead en mi biblioteca de Steam", null), Is.EqualTo("reversed_result"));
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, busqué Cuphead en tu biblioteca.", draft, "buscá Cuphead en mi biblioteca de Steam", null),
                Is.EqualTo("reversed_result"));
        });
    }
}
