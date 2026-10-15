using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 19b (r17 t3-c14 «dame 3 recetas rapidas con atun y arroz…»): a verified search whose writer ran out of time
/// is now told by the mind with that cause (data: operation_floor «searchUntold»); the App publishes it instead of
/// leaving the turn to its composition-failure line. The search shown («Lo busqué») is still refused.
/// </summary>
[TestFixture]
public sealed class CuV3R19bFinalesVetadosTests
{
    private const string RecipeSearch =
        """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"query":"recetas rapidas con atun y arroz","count":1,"results":[{"title":"Arroz con atún fácil y económico","url":"https://www.recetasbaratas.cl/arroz-con-atun/","snippet":"Un arroz con atún listo en 20 minutos con ingredientes de despensa."}]}}""";

    private static async Task<string?> PublishedAsync(string mindText)
    {
        var draft = new UserMessageDraft(RecipeSearch, "status", null);
        ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
            draft, "dame 3 recetas rapidas con atun y arroz q tengo poca plata", ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(mindText, Reproducible: true)),
            cpuFallback: false, allowRecovery: true, CancellationToken.None);
        return outcome.Text;
    }

    [Test]
    public async Task TheTimeThatRanOutIsPublished()
    {
        const string mindText = "Se me acabó el tiempo antes de poder contarte lo que encontré.";
        Assert.That(await PublishedAsync(mindText), Is.EqualTo(mindText));
    }
}
