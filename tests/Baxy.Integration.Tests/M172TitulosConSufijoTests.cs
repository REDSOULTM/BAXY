using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M172 (DEV-I v5b I-s047, DEV-G v4x/v5b G-w14-t1 «oye ponme algo de Mon Laferte en el spotify, lo que sea»): Spotify
/// played «Mon Laferte - Mi Buen Amor - Desde El Teatro Fru Fru», the mind passed the reply that quoted it whole, and
/// this twin refused it as internal_code because «Fru Fru» read as a stutter; the turn ended in ⚠. A word the verified
/// result observed already repeated is data; a repetition it did not observe is still the writer's stutter.
/// </summary>
[TestFixture]
public sealed class M172TitulosConSufijoTests
{
    private const string FruFruPlayed =
        """{"kind":"operation","operation":"media.play.query","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"provider":"spotify","title":"Mon Laferte - Mi Buen Amor - Desde El Teatro Fru Fru","query":"Mon Laferte","playbackStatus":"playing","authority":"spotify_windows_uia_postread"}}""";

    private const string FruFruStatus =
        """{"kind":"operation","operation":"media.status","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"sourceAppUserModelId":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify","title":"Mi Buen Amor - Desde El Teatro Fru Fru","artist":"Mon Laferte","album":"Mi Buen Amor (Desde El Teatro Fru Fru)","playbackStatus":"playing","authority":"windows_smtc_current_session_read"}}""";

    private const string BoraBoraStatus =
        """{"kind":"operation","operation":"media.status","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"sourceAppUserModelId":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify","title":"Bora Bora","artist":"Los Twist","playbackStatus":"playing","authority":"windows_smtc_current_session_read"}}""";

    private const string PlainStatus =
        """{"kind":"operation","operation":"media.status","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"sourceAppUserModelId":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify","title":"Mi Buen Amor","artist":"Mon Laferte","playbackStatus":"playing","authority":"windows_smtc_current_session_read"}}""";

    private const string UnverifiedFruFru =
        """{"kind":"operation","operation":"media.status","polarity":"failure","verified":false,"succeeded":false,"observed":{"version":1,"title":"Mi Buen Amor - Desde El Teatro Fru Fru","artist":"Mon Laferte"}}""";

    private const string IS047 = "oye ponme algo de Mon Laferte en el spotify, lo que sea";

    // I-s047 / G-w14-t1: the retry the mind passed, word for word; I-s049 «what's this song called?»; and our own.
    [TestCase(FruFruPlayed, IS047,
        "Ahora se está reproduciendo la canción «Mon Laferte - Mi Buen Amor - Desde El Teatro Fru Fru» en Spotify.")]
    [TestCase(FruFruStatus, "what's this song called?",
        "The song is called \"Mi Buen Amor - Desde El Teatro Fru Fru\" and it is performed by Mon Laferte.")]
    [TestCase(FruFruStatus, "¿y desde dónde es esta versión?", "Es «Mi Buen Amor» de Mon Laferte, desde el Teatro Fru Fru.")]
    [TestCase(BoraBoraStatus, "cómo se llama esta", "Está sonando Bora Bora de Los Twist.")]
    public void AWordTheResultObservedRepeatedIsNoStutter(string source, string request, string reply)
    {
        var draft = new UserMessageDraft(source, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request, null), Is.Null);
    }

    // What does not change: a repetition the result did not observe (with it or without it elsewhere in the reply),
    // and the same title over a result that verified nothing.
    [TestCase(FruFruPlayed, "Está sonando el tema tema «Mi Buen Amor» de Mon Laferte.")]
    [TestCase(FruFruStatus, "The song song is \"Mi Buen Amor\" by Mon Laferte.")]
    [TestCase(PlainStatus, "Está sonando «Mi Buen Amor - Desde El Teatro Fru Fru» de Mon Laferte.")]
    [TestCase(UnverifiedFruFru, "Está sonando «Mi Buen Amor - Desde El Teatro Fru Fru» de Mon Laferte.")]
    public void ARepetitionTheResultDidNotObserveIsStillRefused(string source, string reply)
    {
        var draft = new UserMessageDraft(source, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, IS047, null),
            Is.EqualTo("internal_code"));
    }
}
