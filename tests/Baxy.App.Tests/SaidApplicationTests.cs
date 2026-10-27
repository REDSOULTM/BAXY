using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// An app.open of an application the person did not name, at a place only another application has, opens that one there
/// (src/Baxy.App/SaidApplication.cs). E2e E014, «abre la configuración de sonido»: the model wrote «Configuración del
/// sistema» (msconfig) with place sound 34 times in the PC's practice runs and once on the notebook (int3 s0).
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class SaidApplicationTests
{
    [Test]
    public void AnApplicationNotNamedAtAPlaceOfAnotherOneOpensThatOne()
    {
        (JsonObject Arguments, string Note)? ruled = Heard("abre la configuración de sonido")
            .Rule("app.open", Open("Configuración del sistema", "sound"));

        Assert.That(ruled, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That((string?)ruled!.Value.Arguments["appId"], Is.EqualTo("Configuración"));
            Assert.That((string?)ruled.Value.Arguments["place"], Is.EqualTo("sound"));
            Assert.That(ruled.Value.Note, Does.Contain("the person did not name Configuración del sistema"));
            Assert.That(ruled.Value.Note, Does.Contain("app_open with appId \"Configuración del sistema\" and no place"));
        });
    }

    // Nothing changes when the person named the application, it has the place, no place was asked, several applications
    // have the place, or no words of the person's hold (a heartbeat).
    [TestCase("abre la configuración del sistema en sonido", "Configuración del sistema", "sound")]
    [TestCase("abre la configuración de sonido", "Configuración", "sound")]
    [TestCase("abre la configuración de sonido", "configuracion", "sound")]
    [TestCase("abre la configuración de sonido", "Configuración del sistema", null)]
    [TestCase("abre la tienda", "Discord", "store")]
    [TestCase("", "Configuración del sistema", "sound")]
    public void OtherwiseTheCallRunsAsItIs(string words, string appId, string? place) =>
        Assert.That(Heard(words).Rule("app.open", Open(appId, place)), Is.Null);

    [Test]
    public void OnlyAnOpening()
    {
        Assert.That(Heard("abre la configuración de sonido").Rule("app.close", Open("Configuración del sistema", "sound")),
            Is.Null);
    }

    [Test]
    public void AfterClearNoWordsHold()
    {
        SaidApplication said = Heard("abre la configuración de sonido");
        said.Clear();

        Assert.That(said.Rule("app.open", Open("Configuración del sistema", "sound")), Is.Null);
    }

    [Test]
    public void WithTheAidOffNothingChanges()
    {
        string? before = Environment.GetEnvironmentVariable("BAXY_AYUDAS");
        Environment.SetEnvironmentVariable("BAXY_AYUDAS", "said_folder");
        try
        {
            Assert.That(Heard("abre la configuración de sonido").Rule("app.open", Open("Configuración del sistema", "sound")),
                Is.Null);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_AYUDAS", before);
        }
    }

    // In the turn loop: the call that goes to the engine is the one opened at the place's application.
    [Test]
    public async Task TheTurnLoopSendsTheOpeningOfThePlacesApplication()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "app.open",
                    ["arguments"] = Open("Configuración del sistema", "sound"),
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "conversation",
                    ["reply"] = "Listo.",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var core = new CoreProcessClient();
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, Process.GetCurrentProcess());
        var steps = new List<NativeTurnStep>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
        });

        await loop.RunAsync("abre la configuración de sonido", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.That(steps.Select(static step => ((string?)step.Arguments["appId"], (string?)step.Arguments["place"])),
            Is.EqualTo(new[] { ("Configuración", "sound") }));
    }

    private static SaidApplication Heard(string words)
    {
        var said = new SaidApplication();
        said.Heard(words);
        return said;
    }

    private static JsonObject Open(string appId, string? place)
    {
        var call = new JsonObject { ["appId"] = appId };
        if (place is not null)
            call["place"] = place;
        return call;
    }
}
