using Baxy.Providers.Windows.External;
using NUnit.Framework;
using static Baxy.Providers.Windows.External.EspnScheduleSource;

namespace Baxy.Providers.Windows.Tests;

// M168 (D77): las respuestas reales de la API pública de ESPN, descargadas una vez el 2026-10-05 con el User-Agent de
// D32 (Fixtures/Espn; los calendarios recortados a sus primeros partidos, la búsqueda a sus equipos), leídas como las
// lee el proveedor, con el reloj y la zona horaria fijos (Santiago en octubre, UTC-03:00). El equipo y si se pide el
// próximo partido o el último los escribe el modelo (web.search source=sports, team, wants).
[TestFixture]
public sealed class EspnScheduleSourceTests
{
    internal static readonly DateTimeOffset Now = new(2026, 10, 5, 14, 0, 0, TimeSpan.Zero);

    internal static readonly TimeZoneInfo Santiago =
        TimeZoneInfo.CreateCustomTimeZone("BAXY-test-UTC-03", TimeSpan.FromHours(-3), "UTC-03", "UTC-03");

    internal static string Fixture(string name) =>
        File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory, "Fixtures", "Espn", name));

    private static readonly Uri Source = new("https://site.api.espn.com/");

    private static readonly TeamHit Lakers = new("13", "Los Angeles Lakers", "basketball", "nba");

    private static readonly TeamHit Boca = new("5", "Boca Juniors", "soccer", "arg.1");

    // The first team ESPN ranks whose calendar is read here, as ESPN names it: an NBA team, a football team of a league
    // read, or a national side; never a women's league (coded «.w»), a college team or another sport.
    [Test]
    public void TheTeamIsTheFirstOneEspnRanksOfALeagueReadHere()
    {
        Assert.Multiple(() =>
        {
            Assert.That(PickTeam(Fixture("search_lakers.json")), Is.EqualTo(Lakers));
            Assert.That(PickTeam(Fixture("search_boca.json")), Is.EqualTo(Boca));
            Assert.That(PickTeam(Fixture("search_chile.json")), Is.EqualTo(new TeamHit("207", "Chile", "soccer", "fifa.worldq.conmebol")));
            Assert.That(PickTeam(Fixture("search_america.json"))?.Id, Is.EqualTo("227"));
            Assert.That(PickTeam(Fixture("search_arsenal.json"))?.Id, Is.EqualTo("359"));
            // ESPN ranks the NBA's Spurs first for «spurs»: that is the team, and the receipt names it.
            Assert.That(PickTeam(Fixture("search_spurs.json"))?.Name, Is.EqualTo("San Antonio Spurs"));
            // ESPN knows no team of the name.
            Assert.That(PickTeam(Fixture("search_xyzzy.json")), Is.Null);
        });
    }

    [Test]
    public void TheNextGameIsReadAsTheCalendarGivesItInThisPcsTime()
    {
        Match? next = Answer(Fixture("nba_lakers_schedule.json"), Lakers, Wanted.Next, Now, Santiago, Source);

        Assert.That(next, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(next!.Value.Team, Is.EqualTo("Los Angeles Lakers"));
            Assert.That(next.Value.Opponent, Is.EqualTo("Sacramento Kings"));
            Assert.That(next.Value.Home, Is.False);
            // 2026-10-06T02:00Z is Monday at 23:00 in Santiago.
            Assert.That(next.Value.Start, Is.EqualTo(new DateTimeOffset(2026, 10, 5, 23, 0, 0, TimeSpan.FromHours(-3))));
            Assert.That(next.Value.Start.Offset, Is.EqualTo(TimeSpan.FromHours(-3)));
            Assert.That(next.Value.StartTimeAnnounced, Is.True);
            Assert.That(next.Value.State, Is.EqualTo("pre"));
            Assert.That(next.Value.Competition, Is.EqualTo("NBA Preseason"));
            Assert.That(next.Value.Venue, Is.EqualTo("Golden 1 Center"));
            Assert.That(next.Value.Url, Does.StartWith("https://www.espn.com/nba/game/_/gameId/401898716"));
        });
    }

    [Test]
    public void TheNextMatchAcrossCompetitionsAndAKickOffNotYetSet()
    {
        string body = Fixture("soccer_boca_fixtures.json");
        Match? next = Answer(body, Boca, Wanted.Next, Now, Santiago, Source);
        // After the Vasco da Gama match, the next one's time is still to be announced.
        Match? later = Answer(body, Boca, Wanted.Next, new DateTimeOffset(2026, 10, 15, 0, 0, 0, TimeSpan.Zero), Santiago, Source);

        Assert.Multiple(() =>
        {
            Assert.That(next?.Opponent, Is.EqualTo("Instituto (Córdoba)"));
            Assert.That(next?.Start, Is.EqualTo(new DateTimeOffset(2026, 10, 9, 19, 30, 0, TimeSpan.FromHours(-3))));
            Assert.That(next?.Competition, Is.EqualTo("Argentine Liga Profesional de Fútbol"));
            Assert.That(next?.Venue, Is.EqualTo("Monumental Presidente Perón"));
            Assert.That(later?.Opponent, Is.EqualTo("Talleres (Córdoba)"));
            Assert.That(later?.Home, Is.True);
            Assert.That(later?.StartTimeAnnounced, Is.False);
        });
    }

    [Test]
    public void TheLastMatchWithItsScoreAsGiven()
    {
        Match? last = Answer(Fixture("soccer_boca_results.json"), Boca, Wanted.Last, Now, Santiago, Source);

        Assert.Multiple(() =>
        {
            Assert.That(last?.Opponent, Is.EqualTo("Unión (Santa Fe)"));
            Assert.That(last?.Completed, Is.True);
            Assert.That(last?.TeamScore, Is.EqualTo("3"));
            Assert.That(last?.OpponentScore, Is.EqualTo("0"));
            Assert.That(last?.Home, Is.True);
            Assert.That(last?.Start, Is.EqualTo(new DateTimeOffset(2026, 10, 2, 21, 30, 0, TimeSpan.FromHours(-3))));
        });
    }

    [Test]
    public void NothingIsInventedWhenTheCalendarHasNoneOfWhatWasAsked()
    {
        Assert.Multiple(() =>
        {
            // No preseason game played yet: no last game.
            Assert.That(Answer(Fixture("nba_lakers_schedule.json"), Lakers, Wanted.Last, Now, Santiago, Source), Is.Null);
            // Every fixture already past.
            Assert.That(Answer(Fixture("soccer_boca_fixtures.json"), Boca, Wanted.Next,
                new DateTimeOffset(2027, 1, 1, 0, 0, 0, TimeSpan.Zero), Santiago, Source), Is.Null);
        });
    }

    [Test]
    public void EachCalendarIsAskedWithOneAddress()
    {
        Assert.Multiple(() =>
        {
            Assert.That(SearchUri("universidad de chile").AbsoluteUri,
                Is.EqualTo("https://site.api.espn.com/apis/search/v2?query=universidad%20de%20chile&limit=8&type=team"));
            Assert.That(ScheduleUris(Boca, Wanted.Next).Select(static uri => uri.AbsoluteUri),
                Is.EqualTo(new[] { "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/5/schedule?fixture=true" }));
            Assert.That(ScheduleUris(Boca, Wanted.Last).Select(static uri => uri.AbsoluteUri),
                Is.EqualTo(new[] { "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/5/schedule" }));
            Assert.That(ScheduleUris(Lakers, Wanted.Next)[0].AbsoluteUri,
                Is.EqualTo("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/schedule"));
        });
    }
}
