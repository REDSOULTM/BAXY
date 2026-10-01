using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M101b (DEV-D v4a D-p16-t1, D-w08-t3): the two empty finals of v4a. A verified search told as not found by «no
/// results …» is the search's not-found, not a reversed result (twin of the mind's _SEARCH_NOT_FOUND_CLAUSE); the
/// reminder finals the mind now writes from the facts are published. The phrasings are our own.
/// </summary>
[TestFixture]
public sealed class M101bSinVaciosTests
{
    private const string ParkingSearch =
        """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"query":"covered parking near the Palmeras Hotel","count":2,"results":[{"title":"parking","url":"https://www.openstreetmap.org/way/1","snippet":"Calle del Mar, Centro, Curicó","distanceMeters":300},{"title":"parking","url":"https://www.openstreetmap.org/way/2","snippet":"Avenida Brasil, Curicó","distanceMeters":650}],"authority":"openstreetmap_nominatim"}}""";

    private const string ReminderCreated =
        """{"kind":"operation","operation":"reminder.create","polarity":"success","verified":true,"succeeded":true}""";

    private const string ReminderPast =
        """{"kind":"operation","operation":"reminder.create","polarity":"failure","verified":false,"succeeded":false,"error":"invalid_reminder"}""";

    private static async Task<string?> PublishedAsync(UserMessageDraft draft, string userText, string mindText)
    {
        ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
            draft, userText, ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(mindText, Reproducible: true)),
            cpuFallback: false, allowRecovery: true, CancellationToken.None);
        return outcome.Text;
    }

    [TestCase("No results mention covered parking near the Palmeras Hotel.")]
    [TestCase("Covered parking near the Palmeras Hotel was not found in the results.")]
    [TestCase("Sin resultados sobre estacionamiento techado cerca del Hotel Palmeras.")]
    public async Task ASearchToldAsNotFoundIsPublished(string mindText)
    {
        var draft = new UserMessageDraft(ParkingSearch, "status", null);
        Assert.That(
            await PublishedAsync(draft, "Oh, I meant covered parking near the Palmeras Hotel.", mindText),
            Is.EqualTo(mindText));
    }

    [Test]
    public async Task AFailureBesideTheNotFoundIsStillReversed()
    {
        var draft = new UserMessageDraft(ParkingSearch, "status", null);
        Assert.That(
            await PublishedAsync(draft, "covered parking near the Palmeras Hotel",
                "No results mention covered parking. I couldn't open the map either."),
            Is.Null);
    }

    [TestCase(ReminderCreated, "status", "Creé el recordatorio.")]
    [TestCase(ReminderPast, "error", "No pude crear el recordatorio: la hora indicada ya pasó o no es válida.")]
    public async Task TheReminderFinalFromItsFactsIsPublished(string source, string intent, string mindText)
    {
        var draft = new UserMessageDraft(source, intent, null);
        Assert.That(await PublishedAsync(draft, "avísame una hora antes del partido", mindText), Is.EqualTo(mindText));
    }
}
