using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M101 (DEV-D v3z D-s037, D-s042, D-p31-t2, D-w10-t4): an empty visible final is impossible. Each final the mind now
/// writes when every draft died (or the draft a wrong veto used to kill) must also pass the shell's acceptance, or the
/// App's queue exhausts into «no_response;retry_exhausted» again. The phrasings are our own.
/// </summary>
[TestFixture]
public sealed class M101SinVaciosTests
{
    private const string YoutubeUnverified =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"media.play.youtube","polarity":"failure","verified":false,"succeeded":false,"error":"youtube_playback_not_verified_watch_ready0_playing_network2_source_none","cause":"external_effect_ambiguous","effectUncertain":true,"target":"cumbia villera"}}""";

    private const string MicrophoneAlreadyMuted =
        """{"kind":"operation","operation":"audio.microphone.mute","polarity":"failure","verified":false,"succeeded":false,"error":"microphone_already_muted"}""";

    private const string MicrophoneMuted =
        """{"kind":"operation","operation":"audio.microphone.mute","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"baselineMuted":false,"muted":true,"authority":"windows_core_audio_capture_endpoint_postread"}}""";

    // Owner script v3z2 t45 «silencia mi microfono» (already muted): «estaba ya» and «no hubo ningún cambio» tell the
    // state that held (twin of the mind), and the mind's floor from the facts is published.
    [TestCase(MicrophoneAlreadyMuted, "El micrófono estaba ya silenciado, por lo que no hubo ningún cambio.")]
    [TestCase(MicrophoneAlreadyMuted, "El micrófono ya estaba silenciado.")]
    [TestCase(MicrophoneMuted, "El micrófono está silenciado.")]
    public async Task TheMicrophoneStateIsPublished(string source, string mindText)
    {
        var draft = new UserMessageDraft(source, "status", null);
        Assert.That(await PublishedAsync(draft, "mutea el micro porfa", mindText), Is.EqualTo(mindText));
    }

    private static async Task<string?> PublishedAsync(UserMessageDraft draft, string userText, string mindText)
    {
        ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
            draft, userText, ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(mindText, Reproducible: true)),
            cpuFallback: false, allowRecovery: true, CancellationToken.None);
        return outcome.Text;
    }

    // D-s037, D-s042: the limit the mind says from the decision when every draft died, or keeps from a draft that named
    // the thing asked.
    [TestCase("Quiero sacar una foto del volcán, mejor que salga el lago.", "Eso no lo hago: sacar una foto del volcán.")]
    [TestCase("quiero empanadas de una panadería del barrio", "Eso no lo hago: lo de empanadas de una panadería del barrio.")]
    [TestCase("¿puedes comprarme un pastel?", "Eso no lo hago.")]
    [TestCase("quiero sacar una foto del volcán", "No tomo fotos de volcanes.")]
    [TestCase("can you book a table on Titan?", "I don't do that: book a table on Titan.")]
    public async Task TheLimitSaidFromTheDecisionIsPublished(string userText, string mindText)
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Failure("out_of_catalog"), "error", null);
        Assert.That(await PublishedAsync(draft, userText, mindText), Is.EqualTo(mindText));
    }

    // D-w10-t4: the opened YouTube page is the failure's cause fact; the unconfirmed playback is reported naming its
    // target, and a claimed success is still refused.
    [TestCase("He abierto YouTube, pero no he podido confirmar si la cumbia villera está sonando.", true)]
    [TestCase("La página de YouTube se abrió, pero no pude confirmar que «cumbia villera» esté sonando.", true)]
    [TestCase("The YouTube page opened, but I couldn't confirm that «cumbia villera» is playing.", true)]
    [TestCase("Listo, ya suena la cumbia villera.", false)]
    public async Task TheUnconfirmedPlaybackIsReportedNamingItsTarget(string mindText, bool published)
    {
        var draft = new UserMessageDraft(YoutubeUnverified, "error", null);
        string? text = await PublishedAsync(draft, "ponme cumbia villera en YouTube mientras cocino", mindText);
        Assert.That(text, published ? Is.EqualTo(mindText) : Is.Null);
    }

    // D-p31-t2: a draft that says it did not manage to understand is the turn failure told (twin of the mind).
    [TestCase("¿y estás completamente seguro de eso?", "No logré interpretar bien lo que me dijiste.")]
    [TestCase("and are you completely sure about that?", "I couldn't work out what you meant.")]
    public async Task TheTurnFailureSaysItsCause(string userText, string mindText)
    {
        var draft = new UserMessageDraft(
            TurnVisibleFacts.Failure("turn_runtime_failure", new JsonObject
            {
                ["operationAttempted"] = false,
                ["retryable"] = true,
            }),
            "error",
            null);
        Assert.That(await PublishedAsync(draft, userText, mindText), Is.EqualTo(mindText));
    }
}
