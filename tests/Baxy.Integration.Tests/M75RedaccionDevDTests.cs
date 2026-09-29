using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M75 (DEV-D v3l, 2026-09-29): the App's policy twins of the mind's composition fixes. A reply the mind publishes
/// crosses these checks too, so a veto the mind lifts here stays lifted, and its true positives stay vetoed.
/// </summary>
[TestFixture]
public sealed class M75RedaccionDevDTests
{
    private const string Foto = "¿Serías capaz de hacer foto ahora?";
    private const string Traducelo = "traducelo al ingles que es para mi jefa";
    private const string HoraAlla = "y si allá son las 10 de la mañana acá qué hora es";

    // D-p02-t2: whether BAXY is able is answered yes or no; «No puedo hacer fotos» is that answer.
    [TestCase(Foto, "No puedo tomar fotos, pero puedo ayudarte con otras tareas.", null)]
    [TestCase(Foto, "No, no puedo hacer fotos.", null)]
    [TestCase(Foto, "No puedo hacer fotos.", null)]
    [TestCase("Are you able to take a photo?", "I can't take photos.", null)]
    // A failed attempt claimed is still a failure; a limit said to a request that is not the question is too.
    [TestCase(Foto, "No pude hacer la foto.", "looks_like_failure")]
    [TestCase("Are you able to take a photo?", "I couldn't take the photo.", "looks_like_failure")]
    [TestCase("Saca foto ahora", "No puedo hacer fotos.", "looks_like_failure")]
    public void AnAbilityQuestionIsAnsweredWithTheLimit(string userText, string reply, string? reason)
    {
        string language = userText.StartsWith("Are", StringComparison.Ordinal) ? "en" : "es";
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(userText, reply, language), Is.EqualTo(reason));
    }

    // D-w15-t3: a translation of something only pointed at has no text to translate; asking which is the reply.
    [TestCase(Traducelo, "¿Qué texto quieres que traduzca al inglés?", null)]
    [TestCase("translate it to English", "What would you like me to translate?", null)]
    // The text is in the message: the App reads «que es» as a knowledge ask and the question is still unanswered.
    [TestCase("traduce 'buenos días' al inglés, que es para mi jefa", "¿Qué quieres que traduzca?",
        "knowledge_not_answered")]
    [TestCase("¿qué es un exoplaneta?", "¿Qué quieres saber?", "knowledge_not_answered")]
    public void APointedTranslationIsClarifiedByAskingWhatToTranslate(string userText, string question, string? reason)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(userText, question, clarification: true),
            Is.EqualTo(reason));
        if (reason is null)
        {
            var draft = new UserMessageDraft(TurnVisibleFacts.Clarification("ambiguous_request"), "clarification", null);
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(question, draft, userText), Is.Null);
        }
    }

    // D-w02-t2: the mind's last resort for a turn it could not interpret passes the App's error checks.
    [TestCase("No pude entender bien tu mensaje.", HoraAlla)]
    [TestCase("I couldn't quite understand your message.", "and if it's 10 in the morning there, what time is it here")]
    public void TheNotUnderstoodFinalIsAnHonestFailure(string final, string userText)
    {
        var draft = new UserMessageDraft(
            TurnVisibleFacts.Failure("turn_runtime_failure", new JsonObject
            {
                ["operationAttempted"] = false,
                ["retryable"] = true,
            }),
            "error",
            null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(final, draft, userText), Is.Null);
    }
}
