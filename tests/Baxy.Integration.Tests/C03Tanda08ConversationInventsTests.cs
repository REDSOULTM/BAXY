using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Tanda 8 (2026-09-25, official window): conversation replies said what never happened («Agregado: tomates.»,
/// «Ya tienes en la lista: …», «Sí, está lista para recoger.»). The shell publishes only text the mind has
/// validated — its own reply (llm.chat) or a message composed for it (message.compose) — and the mind now holds
/// both to the same no-operation contract, so the shell does not read the claims a second time. What the shell
/// owns is not refusing the honest reply the mind's retry writes instead; otherwise the turn would end in ⚠.
/// The phrasings are paraphrases, not the tanda's literals.
/// </summary>
[TestFixture]
public sealed class C03Tanda08ConversationInventsTests
{
    [TestCase("¿mi pedido ya está listo para retirar?", "No sé si tu pedido está listo: no lo veo desde aquí.")]
    [TestCase("is my package ready for pickup", "I don't know whether your package is ready from here.")]
    [TestCase("which timers do I have going", "I don't know what you have set from here.")]
    [TestCase("¿qué tengo ya en la lista?", "No sé qué hay en tu lista sin leerla.")]
    [TestCase("y también cebollas", "No las añadí: todavía no leí tu lista.")]
    [TestCase("me caí de la bici hoy", "Lamento mucho que te hayas caído; ¿estás bien?")]
    public void TheHonestReplyTheMindWritesIsPublished(string request, string reply)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(request, reply), Is.Null);
    }
}
