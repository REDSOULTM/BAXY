using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M93 (held-out v3v t10 «abrí el bloc de notas», HEAD 30861483 with M89): app.open ended in inventory_failed and the
/// three honest drafts died in the mind («No pude confirmar si el Bloc de notas se abrió porque el sistema no pudo leer
/// la lista de programas y ventanas abiertos.» twice as reversed_polarity, «El Bloc de notas no pudo abrirse porque…»
/// as missing_failure); the turn ended in ⚠. The shell's twin reads «no pudo abrirse» as the failure told too.
/// </summary>
[TestFixture]
public sealed class M93HeldoutOpenUnconfirmedTests
{
    private const string OpenNotConfirmed =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"app.open","polarity":"failure","verified":false,"succeeded":false,"error":"inventory_failed"}}""";

    [TestCase("No pude confirmar si el Bloc de notas se abrió porque el sistema no pudo leer la lista de programas y ventanas abiertos.")]
    [TestCase("El Bloc de notas no pudo abrirse porque el sistema no pudo leer la lista de programas abiertos.")]
    [TestCase("No puedo confirmar si el Bloc de notas se abrió porque el sistema no pudo leer la lista de programas y ventanas abiertos.")]
    public void TheUnconfirmedOpenToldAsSuchIsTheFailure(string reply)
    {
        var draft = new UserMessageDraft(OpenNotConfirmed, "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "abrí el bloc de notas"), Is.Null);
    }

    [TestCase("Abrí el Bloc de notas.")]
    [TestCase("El Bloc de notas se abrió.")]
    public void AnOpenClaimedStillReversesTheFailure(string reply)
    {
        var draft = new UserMessageDraft(OpenNotConfirmed, "error", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "abrí el bloc de notas"), Is.Not.Null);
    }
}
