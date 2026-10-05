using Baxy.Providers.Windows.External;
using NUnit.Framework;
using static Baxy.Providers.Windows.External.EspnScheduleSource;

namespace Baxy.Providers.Windows.Tests;

// M168 (D77): las respuestas reales de la API pública de ESPN, descargadas una vez el 2026-10-05 con el User-Agent de
// D32 (Fixtures/Espn; los calendarios recortados a sus primeros partidos, la búsqueda a sus equipos), leídas como las
// lee el proveedor, con el reloj y la zona horaria fijos (Santiago en octubre, UTC-03:00).
[TestFixture]
public sealed class EspnScheduleSourceTests
{
    internal static readonly DateTimeOffset Now = new(2026, 10, 5, 14, 0, 0, TimeSpan.Zero);

    internal static readonly TimeZoneInfo Santiago =
        TimeZoneInfo.CreateCustomTimeZone("BAXY-test-UTC-03", TimeSpan.FromHours(-3), "UTC-03", "UTC-03");

    internal static string Fixture(string name) =>
        File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory, "Fixtures", "Espn", name));

    private static readonly Uri Source = new("https://site.api.espn.com/");

    [Test]
    public void TheRowsAskWhenATeamPlaysNext()
    {
        Assert.Multiple(() =>
        {
            // DEV-G G-w42-t1 and DEV-I I-w29-t2, as the mind restated them.
            Assert.That(Parse("When do the Lakers play next?"), Is.EqualTo(new MatchAsk("lakers", null, Wanted.Next, SportHint.Any)));
            // DEV-H H-w44-t1: «match», «kick off» say football.
            Assert.That(Parse("What time does the Arsenal match kick off tonight?"),
                Is.EqualTo(new MatchAsk("arsenal", null, Wanted.Next, SportHint.Soccer)));
            // DEV-I I-w12-t3 and I-w26-t1.
            Assert.That(Parse("¿Cuándo juega Boca de nuevo?"), Is.EqualTo(new MatchAsk("boca", null, Wanted.Next, SportHint.Any)));
            Assert.That(Parse("¿A qué hora juega Chile el martes?"), Is.EqualTo(new MatchAsk("chile", null, Wanted.Next, SportHint.Any)));
            // DEV-F F-s018 (the rival picks the match), DEV-G G-s037 (unrestated), DEV-H H-s106, H-w23-t4.
            Assert.That(Parse("¿A qué hora juega el América contra Chivas este fin de semana?"),
                Is.EqualTo(new MatchAsk("america", "chivas", Wanted.Next, SportHint.Any)));
            Assert.That(Parse("aq hora juega el america este fin d semana??")?.Team, Is.EqualTo("america"));
            Assert.That(Parse("¿A qué hora juega Colo-Colo el domingo?")?.Team, Is.EqualTo("colo colo"));
            Assert.That(Parse("Who are the Lakers playing tonight?")?.Team, Is.EqualTo("lakers"));
            // Our own: the raw message with its tail, «tip-off», a name of several words, an alias.
            Assert.That(Parse("when do the Lakers play next? my buddy wants to come over and watch it")?.Team,
                Is.EqualTo("lakers"));
            Assert.That(Parse("what time is tip-off for the Nuggets")?.Sport, Is.EqualTo(SportHint.Basketball));
            Assert.That(Parse("¿cuándo es el próximo partido del Real Madrid?")?.Team, Is.EqualTo("real madrid"));
            Assert.That(Parse("a qué hora juega la U")?.Team, Is.EqualTo("universidad de chile"));
            Assert.That(Parse("cuando juega la Roja")?.Team, Is.EqualTo("chile"));
            Assert.That(Parse("when does Barça play next")?.Team, Is.EqualTo("barcelona"));
            Assert.That(Parse("what time do Spurs kick off on Saturday")?.Team, Is.EqualTo("tottenham hotspur"));
            Assert.That(Parse("when do the Spurs play next")?.Team, Is.EqualTo("spurs"));
        });
    }

    [Test]
    public void TheRowsAskHowTheLastMatchWent()
    {
        Assert.Multiple(() =>
        {
            // DEV-I I-w12-t1, I-w29-t1, I-s084 and I-s014.
            Assert.That(Parse("¿Cómo salió Boca anoche?"), Is.EqualTo(new MatchAsk("boca", null, Wanted.Last, SportHint.Any)));
            Assert.That(Parse("Did the Lakers win last night?"), Is.EqualTo(new MatchAsk("lakers", null, Wanted.Last, SportHint.Any)));
            Assert.That(Parse("¿Cómo salió la U anoche contra Colo-Colo?"),
                Is.EqualTo(new MatchAsk("universidad de chile", "colo colo", Wanted.Last, SportHint.Any)));
            Assert.That(Parse("quien gano el superclasico colo colo vs la u el domingo"),
                Is.EqualTo(new MatchAsk("colo colo", "universidad de chile", Wanted.Last, SportHint.Any)));
            Assert.That(Parse("how did Arsenal do last night, did they win?")?.Wants, Is.EqualTo(Wanted.Last));
        });
    }

    [Test]
    public void WhatIsNotAMatchOfANamedTeamIsNotAsked()
    {
        Assert.Multiple(() =>
        {
            // Nothing that does not change: an encyclopedia, the news, a currency, the coach, the weather.
            Assert.That(Parse("¿Quién es LeBron James?"), Is.Null);
            Assert.That(Parse("noticias del Barça"), Is.Null);
            Assert.That(Parse("¿Cuánto está el dólar hoy?"), Is.Null);
            Assert.That(Parse("Who is the Lakers' current head coach?"), Is.Null);
            Assert.That(Parse("is it going to rain in Manchester this afternoon?"), Is.Null);
            Assert.That(Parse("who won the nba finals 2026"), Is.Null);
            // A match nobody named.
            Assert.That(Parse("What time is the match today?"), Is.Null);
            Assert.That(Parse("¿A qué hora es que juega mi equipo hoy?"), Is.Null);
            // A result word with no match and no day.
            Assert.That(Parse("¿cómo salió el examen de Pedro?"), Is.Null);
        });
    }

    [Test]
    public void TheTeamIsTheFirstOneEspnRanksOfALeagueReadHere()
    {
        Assert.Multiple(() =>
        {
            Assert.That(PickTeam(Fixture("search_lakers.json"), Parse("When do the Lakers play next?")!),
                Is.EqualTo(new TeamHit("13", "Los Angeles Lakers", "basketball", "nba")));
            Assert.That(PickTeam(Fixture("search_boca.json"), Parse("¿Cuándo juega Boca de nuevo?")!),
                Is.EqualTo(new TeamHit("5", "Boca Juniors", "soccer", "arg.1")));
            Assert.That(PickTeam(Fixture("search_chile.json"), Parse("¿A qué hora juega Chile el martes?")!)?.Id,
                Is.EqualTo("207"));
            Assert.That(PickTeam(Fixture("search_chile.json"), Parse("a qué hora juega la U")!)?.Id, Is.EqualTo("4139"));
            Assert.That(PickTeam(Fixture("search_america.json"), Parse("cuando juega el América")!)?.Id, Is.EqualTo("227"));
            Assert.That(PickTeam(Fixture("search_arsenal.json"), Parse("What time does the Arsenal match kick off tonight?")!)?.Id,
                Is.EqualTo("359"));
            // «Spurs» alone is the NBA's (ESPN ranks it first); said of football, Tottenham.
            Assert.That(PickTeam(Fixture("search_spurs.json"), Parse("when do the Spurs play next")!)?.Id, Is.EqualTo("24"));
            Assert.That(PickTeam(Fixture("search_spurs.json"), Parse("what time do Spurs kick off on Saturday")!)?.Id,
                Is.EqualTo("367"));
            // A team ESPN does not know, or a name its teams do not carry: none.
            Assert.That(PickTeam(Fixture("search_xyzzy.json"), Parse("when does Xyzzy Quux play next")!), Is.Null);
            Assert.That(PickTeam(Fixture("search_boca.json"), Parse("when does Bocanegra FC play next")!), Is.Null);
        });
    }

    [Test]
    public void TheNextGameIsSaidInThisPcsTime()
    {
        var lakers = new TeamHit("13", "Los Angeles Lakers", "basketball", "nba");
        List<(string Title, string Url, string Snippet)>? answer = Answer(
            Fixture("nba_lakers_schedule.json"), lakers, Parse("When do the Lakers play next?")!, Now, Santiago, Source);

        Assert.That(answer, Has.Count.EqualTo(1));
        Assert.Multiple(() =>
        {
            Assert.That(answer![0].Title, Is.EqualTo("Los Angeles Lakers vs Sacramento Kings"));
            Assert.That(answer[0].Url, Does.StartWith("https://www.espn.com/nba/game/_/gameId/401898716"));
            // 2026-10-06T02:00Z is Monday at 23:00 in Santiago.
            Assert.That(answer[0].Snippet, Is.EqualTo(
                "Next game: Los Angeles Lakers play away against Sacramento Kings on Monday 2026-10-05 at 23:00 local "
                + "time (UTC-03:00), NBA Preseason, at Golden 1 Center."));
        });
    }

    [Test]
    public void TheNextMatchAcrossCompetitionsAndTheOneAgainstTheRivalNamed()
    {
        var boca = new TeamHit("5", "Boca Juniors", "soccer", "arg.1");
        string body = Fixture("soccer_boca_fixtures.json");
        Assert.Multiple(() =>
        {
            Assert.That(Answer(body, boca, Parse("¿Cuándo juega Boca de nuevo?")!, Now, Santiago, Source)![0].Snippet,
                Is.EqualTo("Next match: Boca Juniors play away against Instituto (Córdoba) on Friday 2026-10-09 at 19:30 "
                    + "local time (UTC-03:00), Argentine Liga Profesional de Fútbol, at Monumental Presidente Perón."));
            Assert.That(Answer(body, boca, Parse("cuándo juega Boca contra Vasco")!, Now, Santiago, Source)![0].Snippet,
                Does.StartWith("Next match: Boca Juniors play at home against Vasco da Gama on Tuesday 2026-10-13 at 21:30"));
        });
    }

    [Test]
    public void AKickOffNotYetSetIsSaidAsNotAnnounced()
    {
        var boca = new TeamHit("5", "Boca Juniors", "soccer", "arg.1");
        string snippet = Answer(Fixture("soccer_boca_fixtures.json"), boca, Parse("a qué hora juega Boca contra Talleres")!,
            Now, Santiago, Source)![0].Snippet;
        Assert.That(snippet, Is.EqualTo(
            "Next match: Boca Juniors play at home against Talleres (Córdoba) on Sunday 2026-10-18 (the start time is "
            + "still to be announced, TBD), Argentine Liga Profesional de Fútbol, at Alberto José Armando (La Bombonera)."));
        Assert.That(snippet, Does.Not.Match(@"\d{2}:\d{2}"));
    }

    [Test]
    public void ANationalSideAndAnEnglishClub()
    {
        Assert.Multiple(() =>
        {
            // DEV-I I-w26-t1 «a que hora juega chile el martes».
            Assert.That(Answer(Fixture("soccer_chile_fixtures.json"), new TeamHit("207", "Chile", "soccer", "fifa.worldq.conmebol"),
                    Parse("¿A qué hora juega Chile el martes?")!, Now, Santiago, Source)![0].Snippet,
                Is.EqualTo("Next match: Chile play away against Mexico on Tuesday 2026-10-06 at 23:30 local time (UTC-03:00), "
                    + "International Friendly, at Los Angeles Memorial Coliseum."));
            // DEV-H H-w44-t1, in London's time on that day (UTC+01:00).
            TimeZoneInfo london = TimeZoneInfo.CreateCustomTimeZone("BAXY-test-UTC+01", TimeSpan.FromHours(1), "UTC+01", "UTC+01");
            Assert.That(Answer(Fixture("soccer_arsenal_fixtures.json"), new TeamHit("359", "Arsenal", "soccer", "eng.1"),
                    Parse("What time does the Arsenal match kick off tonight?")!, Now, london, Source)![0].Snippet,
                Does.StartWith("Next match: Arsenal play at home against Leeds United on Saturday 2026-10-10 at 12:30 local "
                    + "time (UTC+01:00), English Premier League"));
        });
    }

    [Test]
    public void TheLastMatchWithItsScore()
    {
        var boca = new TeamHit("5", "Boca Juniors", "soccer", "arg.1");
        string body = Fixture("soccer_boca_results.json");
        Assert.Multiple(() =>
        {
            // DEV-I I-w12-t1 «che como salio boca anoche?».
            Assert.That(Answer(body, boca, Parse("¿Cómo salió Boca anoche?")!, Now, Santiago, Source)![0].Snippet,
                Is.EqualTo("Last match: Boca Juniors beat Unión (Santa Fe) 3-0 at home, on Friday 2026-10-02 at 21:30 local "
                    + "time (UTC-03:00), Argentine Liga Profesional de Fútbol, at Alberto José Armando (La Bombonera)."));
            Assert.That(Answer(body, boca, Parse("¿Cómo le fue a Boca contra Racing el domingo? ¿ganó?")!, Now, Santiago, Source)![0].Snippet,
                Does.StartWith("Last match: Boca Juniors beat Racing Club 3-2 away, on Sunday 2026-09-27 at 17:00"));
        });
    }

    [Test]
    public void NothingIsInventedWhenTheCalendarHasNoneOfWhatWasAsked()
    {
        var lakers = new TeamHit("13", "Los Angeles Lakers", "basketball", "nba");
        var boca = new TeamHit("5", "Boca Juniors", "soccer", "arg.1");
        Assert.Multiple(() =>
        {
            // No preseason game played yet: no last game.
            Assert.That(Answer(Fixture("nba_lakers_schedule.json"), lakers, Parse("Did the Lakers win last night?")!,
                Now, Santiago, Source), Is.Null);
            // Every fixture already past.
            Assert.That(Answer(Fixture("soccer_boca_fixtures.json"), boca, Parse("¿Cuándo juega Boca de nuevo?")!,
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
            Assert.That(ScheduleUris(new TeamHit("5", "Boca Juniors", "soccer", "arg.1"), Wanted.Next).Select(static uri => uri.AbsoluteUri),
                Is.EqualTo(new[] { "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/5/schedule?fixture=true" }));
            Assert.That(ScheduleUris(new TeamHit("5", "Boca Juniors", "soccer", "arg.1"), Wanted.Last).Select(static uri => uri.AbsoluteUri),
                Is.EqualTo(new[] { "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/5/schedule" }));
            Assert.That(ScheduleUris(new TeamHit("13", "Los Angeles Lakers", "basketball", "nba"), Wanted.Next)[0].AbsoluteUri,
                Is.EqualTo("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/schedule"));
        });
    }
}
