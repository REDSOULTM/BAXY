using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M134 (rounds v4i–v4l2, DEV-F and DEV-D): turns that ended in ⚠ because every draft was refused.
/// <list type="bullet">
/// <item>F-w22-t2, F-w24-t4, D-w15-t3: the file a failed read tried («lease.pdf», «cotizacion-pisos.pdf»,
/// «informe_trimestral.txt») was refused as internal_code; it is the person's thing named back
/// (ObservedResponseLiterals twin of llm._attempted_targets, compared without accents).</item>
/// <item>D-w15-t3: «The file was not found at the specified location.» for known_file_not_found was refused as
/// reversed_result; the mind's _FAILURE_MARKERS read «not found» as the failure told.</item>
/// <item>F-w59-t2: a task titled «…, mañana a las 18:30» quoted back; D-p35-t1: the SWOT with its unsourced point left
/// out. Both are published as the mind composed them.</item>
/// </list>
/// </summary>
[TestFixture]
public sealed class M134RedaccionTests
{
    private const string LeaseNotFound =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"document.pdf.read","polarity":"failure","verified":false,"succeeded":false,"error":"known_file_not_found","target":"lease.pdf","attempted":{"fileName":"lease.pdf","folder":"downloads"}}}""";

    private const string QuoteNotFound =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"document.pdf.read","polarity":"failure","verified":false,"succeeded":false,"error":"known_file_not_found","target":"cotizacion-pisos.pdf","attempted":{"fileName":"cotizacion-pisos.pdf","folder":"downloads"}}}""";

    private const string ReportNotFound =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"document.text.read","polarity":"failure","verified":false,"succeeded":false,"error":"known_file_not_found","target":"informe_trimestral.txt","attempted":{"fileName":"informe_trimestral.txt","folder":"documents"}}}""";

    private const string TaskCreated =
        """{"kind":"operation","operation":"task.create","polarity":"success","verified":true,"succeeded":true,"observed":{"taskId":"55096d60-4904-4865-8a9e-8dfa593cbde5","title":"comprar huevos, leche de avena y tortillas, mañana a las 18:30","details":"","completed":false,"deleted":false,"createdAtUtc":"2026-10-02T22:29:04.6964848+00:00","updatedAtUtc":"2026-10-02T22:29:04.6964848+00:00","version":1}}""";

    private const string AdidasSearch =
        """{"kind": "operation", "operation": "web.search", "polarity": "success", "verified": true, "succeeded": true, "observed": {"version": 1, "query": "Adidas empresa", "count": 2, "results": [{"title": "Adidas", "url": "https://es.wikipedia.org/wiki/Adidas", "snippet": "Adidas AG (pronunciado /ˈadidas/ (); estilizado adidas, con minúsculas, desde 1949) es una compañía multinacional alemana fundada en 1949, con sede en Herzogenaurach, ciudad ubicada en Baviera. Se dedica a la fabricación de equipamiento deportivo y productos de moda (bolsos, camisas, tenis, gafas, etc.). La empresa también es patrocinadora de eventos y figuras deportivas a nivel mundial."}, {"title": "Generación Adidas", "url": "https://es.wikipedia.org/wiki/Generaci%C3%B3n_Adidas", "snippet": "Generación Adidas es una empresa conjunta entre la Major League Soccer y USSF destinadas a elevar el nivel de los jóvenes talentos del fútbol en los Estados Unidos. El programa, auspiciado por Adidas, alienta a la pronta entrada (sin graduación universitaria) de jugadores de Estados Unidos en la MLS . Hasta 2005, el programa fue patrocinado por Nike y fue llamado Proyecto-40. Carlos Parra fue el primer jugador egrasado de proyecto-40 cuando firmó con la liga y fue asignado a MetroStars en 1997."}], "authority": "wikipedia_es_api"}}""";

    private const string Swot =
        "Oye, mira, Adidas sigue siendo esa leyenda urbana que nunca se rinde, aunque a veces se siente un poco perdida "
        + "en el mar de gigantes.\n\n**Fortalezas:**\n"
        + "- Son los reyes del patrocinio deportivo, creando historias épicas con atletas que inspiran a millones a sudar y soñar.\n\n"
        + "**Debilidades:**\n"
        + "- A veces se sienten atrapados en su propia historia, como si el pasado les impidiera correr a la velocidad del presente.\n\n"
        + "**Oportunidades:**\n"
        + "- Hay un hueco enorme para conectar con nuevas audiencias que buscan autenticidad real, no solo logos brillantes.\n\n"
        + "**Amenazas:**\n"
        + "- El mercado está saturado de opciones, y si no logran destacar, se convertirán en un nombre más en una lista interminable.";

    [TestCase(LeaseNotFound, "great, can you summarize the lease PDF in there?",
        "The attempt to read lease.pdf from the Downloads folder failed because the file was not found.")]
    [TestCase(LeaseNotFound, "great, can you summarize the lease PDF in there?",
        "The file lease.pdf in the downloads folder was not found.")]
    [TestCase(QuoteNotFound, "y eso cuanto sale por metro?",
        "No se pudo obtener el precio por metro porque el archivo cotización-pisos.pdf no se encontró en la carpeta de descargas.")]
    [TestCase(ReportNotFound, "traducelo al ingles que es para mi jefa",
        "No pude traducir el informe porque no encontré informe_trimestral.txt en la carpeta Documentos.")]
    [TestCase(ReportNotFound, "traducelo al ingles que es para mi jefa",
        "The file was not found at the specified location.")]
    public async Task TheFailureOfAReadNamingWhatItTriedIsPublished(string source, string request, string reply)
    {
        var draft = new UserMessageDraft(source, "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request, null), Is.Null);
        ModelMessageCompositionOutcome result = await ModelMessageComposer.ComposeAsync(
            draft, request, ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(reply)),
            cpuFallback: false, allowRecovery: false, CancellationToken.None);
        Assert.That(result.Text, Is.EqualTo(reply));
    }

    [TestCase("No pude leer lease.pdf: document.pdf.read falló.", "internal_code")]
    [TestCase("No encontré lease.pdf porque known_file_not_found.", "internal_code")]
    [TestCase("I read lease.pdf for you.", "reversed_result")]
    public void WhatTheFailureDidNotTryIsStillRefused(string reply, string reason)
    {
        var draft = new UserMessageDraft(LeaseNotFound, "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "summarize the lease PDF", null),
            Is.EqualTo(reason));
    }

    [Test]
    public void OnlyTheAttemptedTargetsExempt()
    {
        Assert.That(ObservedResponseLiterals.WithoutObservedIdentifiers("No encontré cotización-pisos.pdf.", QuoteNotFound),
            Is.EqualTo("No encontré ."));
        Assert.That(ObservedResponseLiterals.WithoutObservedIdentifiers("vía document.pdf.read", QuoteNotFound),
            Is.EqualTo("vía document.pdf.read"));
        Assert.That(ObservedResponseLiterals.WithoutObservedIdentifiers("No encontré otro-archivo.pdf.", QuoteNotFound),
            Is.EqualTo("No encontré otro-archivo.pdf."));
    }

    [TestCase(TaskCreated, "status", "yeah sure mañana at 6:30 pm",
        "He creado la tarea \"comprar huevos, leche de avena y tortillas, mañana a las 18:30\" que aún no está completada.")]
    [TestCase(AdidasSearch, "status",
        "Has un análisis de FODA sobre la empresa Adidas. utiliza un tono casual.", Swot)]
    public async Task WhatTheMindComposedIsPublished(string source, string intent, string request, string reply)
    {
        var draft = new UserMessageDraft(source, intent, null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request, null), Is.Null);
        ModelMessageCompositionOutcome result = await ModelMessageComposer.ComposeAsync(
            draft, request, ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(reply)),
            cpuFallback: false, allowRecovery: false, CancellationToken.None);
        Assert.That(result.Text, Is.EqualTo(reply));
    }
}
