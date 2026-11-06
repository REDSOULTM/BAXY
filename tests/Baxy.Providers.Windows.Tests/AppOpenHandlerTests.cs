using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew (notebook): what app.open says back. A place its application does not have is refused with what was
/// asked; a verified opening names the program of the window it verified as a view names it, and whether that window
/// holds the front as the opening answers (F004: the window of another application did).
/// </summary>
[TestFixture]
public sealed class AppOpenHandlerTests
{
    // Ajuste c4 (banco ciego c3, causa 4): what was asked is said, and no other application: placeIn named the ones that
    // have the place, and the model opened one of them (C3-089: Epic Games Launcher for Luanti's «game»).
    [Test]
    public async Task APlaceOfAnotherApplicationIsRefusedWithWhatWasAsked()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\mspaint.exe");

        OperationOutcome outcome = await Handler(provider).ExecuteAsync(
            Invocation("""{"appId":"Paint","place":"library"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("place_not_of_application"));
            Assert.That(outcome.Result!.Value.GetProperty("appId").GetString(), Is.EqualTo("Paint"));
            Assert.That(outcome.Result!.Value.GetProperty("place").GetString(), Is.EqualTo("library"));
            Assert.That(outcome.Result!.Value.TryGetProperty("placeIn", out _), Is.False);
            Assert.That(provider.Calls, Is.Zero);
        });
    }

    // Ajuste c4 (banco ciego c3, causa 4: C3-051, C3-052, C3-089, C3-092): the refusal sent the model to the application
    // that has the place («app_open with appId "Configuración" and place "captions"» for LibreOffice Writer, Epic Games
    // Launcher for Luanti's «game»), and the one asked for never opened. With the aid app_places it says how the
    // application named opens, and its own places when it has some; never another application. With BAXY_AYUDAS=none,
    // the facts alone. The application the person's words name instead is SaidApplication's (aid place_owner), which
    // knows those words.
    // Encargo 34: the call that opens it comes first, with its argument written, and what this one did not open last.
    [TestCase("all", "LibreOffice Writer", "captions", "app_open {\"appId\":\"LibreOffice Writer\"} opens LibreOffice "
        + "Writer itself; this call opened nothing: captions is not a place of LibreOffice Writer")]
    [TestCase("all", "Luanti", "game", "app_open {\"appId\":\"Luanti\"} opens Luanti itself; this call opened nothing: "
        + "game is not a place of Luanti")]
    [TestCase("all", "Spotify", "library", "app_open {\"appId\":\"Spotify\"} opens Spotify itself; it also opens "
        + "straight at a place of its own, by app_open with place: home, results (placeValue: what to search), search; "
        + "this call opened nothing: library is not a place of Spotify")]
    [TestCase("none", "LibreOffice Writer", "captions", null)]
    public async Task APlaceOfAnotherApplicationSaysHowTheNamedOneOpens(
        string aids, string appId, string place, string? hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        var provider = new VerifiedOpening(@"C:\Program Files\Applicationpplication.exe");

        OperationOutcome outcome = await Handler(provider).ExecuteAsync(
            Invocation(JsonSerializer.Serialize(new { appId, place })), CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("place_not_of_application"));
            Assert.That(result.TryGetProperty("next", out JsonElement next) ? next.GetString() : null, Is.EqualTo(hint));
            Assert.That(provider.Calls, Is.Zero);
        });
    }

    // The Calculator is launched by System32\calc.exe, and the window verified is CalculatorApp's: the opening names it
    // CalculatorApp, as the window in front would be named (foregroundHeldBy) and the keys sent to it (sentTo).
    [Test]
    public async Task AVerifiedOpeningNamesTheProgramOfTheWindowItVerifiedNotItsLauncher()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\calc.exe");
        var read = new List<long>();

        OperationOutcome outcome = await Handler(provider, window =>
        {
            read.Add(window);
            return new OpenedWindowFront(true, "CalculatorApp");
        }).ExecuteAsync(Invocation("""{"appId":"Calculadora"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(read, Is.EqualTo(new[] { 777L }), "the name is the verified window's");
            Assert.That(outcome.Result!.Value.GetProperty("displayName").GetString(), Is.EqualTo("Calculadora"));
            Assert.That(outcome.Result!.Value.GetProperty("processName").GetString(), Is.EqualTo("CalculatorApp"));
        });
    }

    // No name was read for the verified window: none is said (never the launcher's in its place).
    [Test]
    public async Task AVerifiedWindowWithoutANameReadNamesNoProgram()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\calc.exe");

        OperationOutcome outcome = await Handler(provider, static _ => new OpenedWindowFront(true, null))
            .ExecuteAsync(Invocation("""{"appId":"Calculadora"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.TryGetProperty("processName", out _), Is.False);
        });
    }

    [Test]
    public async Task AnOpenedWindowThatHoldsTheFrontSaysSo()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\notepad.exe");
        var read = new List<long>();

        OperationOutcome outcome = await Handler(provider, window =>
        {
            read.Add(window);
            return new OpenedWindowFront(true, "Notepad");
        }).ExecuteAsync(Invocation("""{"appId":"Bloc de notas","foreground":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(read, Is.EqualTo(new[] { 777L }));
            Assert.That(outcome.Result!.Value.GetProperty("foreground").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.TryGetProperty("foregroundHeldBy", out _), Is.False);
        });
    }

    // F004: «abre la calculadora y luego escribe hola en el bloc de notas». The Notepad window is verified open, and the
    // Calculator opened just before holds the front: the opening says so, by the window's title and program.
    [Test]
    public async Task AnOpenedWindowBehindAnotherApplicationNamesTheWindowInFront()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\notepad.exe");

        OperationOutcome outcome = await Handler(provider, static _ => new OpenedWindowFront(false, "Notepad", "Calculadora", "CalculatorApp"))
            .ExecuteAsync(Invocation("""{"appId":"Bloc de notas","foreground":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("foreground").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("foregroundHeldBy").GetProperty("title").GetString(),
                Is.EqualTo("Calculadora"));
            Assert.That(outcome.Result!.Value.GetProperty("foregroundHeldBy").GetProperty("process").GetString(),
                Is.EqualTo("CalculatorApp"));
        });
    }

    // NB-R1 P1.12 (en vivo, «escribe en el bloc de notas: …»): the opening gave only its windowId, a text the window
    // operations take, and the model typed with window 1 and 125, numbers it made up (input_window_not_found). The
    // opening says too the window number the input operations take, under the name of their argument.
    [Test]
    public async Task AVerifiedOpeningGivesTheWindowNumberTheInputOperationsTake()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\notepad.exe");
        var handler = new AppOpenHandler(
            provider,
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            windowIdFor: static window => window == 777 ? "w-777" : null,
            frontOf: static _ => new OpenedWindowFront(true, "Notepad"));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Bloc de notas","foreground":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("window").GetInt64(), Is.EqualTo(777));
            Assert.That(outcome.Result!.Value.GetProperty("windowId").GetString(), Is.EqualTo("w-777"));
        });
    }

    // Encargo 98: the New command raised a dialog instead of a document: the failure says which, and whether it was closed.
    [TestCase(true, "which was closed again")]
    [TestCase(false, "which is still open")]
    public async Task ADialogMetInsteadOfTheNewDocumentIsSaid(bool closed, string said)
    {
        var provider = new DialogMet(new ApplicationDialogMet("Abrir", closed));

        OperationOutcome outcome = await Handler(provider)
            .ExecuteAsync(Invocation("""{"appId":"Bloc de notas","newDocument":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("new_document_not_created"));
            JsonElement dialog = outcome.Result!.Value.GetProperty("dialogOpened");
            Assert.That(dialog.GetProperty("title").GetString(), Is.EqualTo("Abrir"));
            Assert.That(dialog.GetProperty("closed").GetBoolean(), Is.EqualTo(closed));
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Does.Contain("«Abrir»").And.Contain(said));
        });
    }

    // Nobody in front (Windows reports no foreground window): not held, and no window is named.
    [Test]
    public async Task NoWindowInFrontIsNotTheOpenedOneAndNamesNone()
    {
        var provider = new VerifiedOpening(@"C:\Windows\System32\notepad.exe");

        OperationOutcome outcome = await Handler(provider, static _ => new OpenedWindowFront(false, "Notepad"))
            .ExecuteAsync(Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Result!.Value.GetProperty("foreground").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.TryGetProperty("foregroundHeldBy", out _), Is.False);
        });
    }

    // Round A: Steam opened and verified, and its library's address could not be handed over: the place failed, not the
    // launch, and the opening already happened. Revisión 2026-10-22 (C-4): the failure says the application is open,
    // with the window id the window operations take, so nothing tells it as not opened.
    [Test]
    public async Task APlaceThatCouldNotBeHandedOverAfterAVerifiedOpeningIsNotALaunchFailure()
    {
        var provider = new VerifiedOpening(@"C:\Program Files (x86)\Steam\steam.exe");
        var handler = new AppOpenHandler(
            provider,
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            new RefusedPlace(),
            windowIdFor: static window => window == 777 ? "w-777" : null,
            frontOf: static _ => new OpenedWindowFront(true, "steam"));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"library"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(provider.Calls, Is.EqualTo(1));
            Assert.That(outcome.ErrorCode, Is.EqualTo("place_not_opened"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            JsonElement result = outcome.Result!.Value;
            Assert.That(result.GetProperty("appId").GetString(), Is.EqualTo("Steam"));
            Assert.That(result.GetProperty("displayName").GetString(), Is.EqualTo("Steam"));
            Assert.That(result.GetProperty("opened").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("windowId").GetString(), Is.EqualTo("w-777"));
            Assert.That(result.GetProperty("window").GetInt64(), Is.EqualTo(777));
            Assert.That(result.GetProperty("place").GetString(), Is.EqualTo("library"));
        });
    }

    // pc-ayudas (aid place_unverified): a place handed over is only asked for; the result says so and how to look (F019
    // said «abrí Steam en la biblioteca» from placeRequested alone). With BAXY_AYUDAS=none it is the result it was.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task APlaceHandedOverSaysItWasOnlyAskedForAndHowToLook(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        var handler = new AppOpenHandler(
            new VerifiedOpening(@"C:\Program Files (x86)\Steam\steam.exe"),
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            new HandedPlace(),
            frontOf: static _ => new OpenedWindowFront(true, "steamwebhelper"));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"library"}"""), CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(result.GetProperty("placeRequested").GetBoolean(), Is.True);
            // Revisión 2026-10-22 (C-5): with the aids on or off, a structured fact says the place was not read back.
            Assert.That(result.GetProperty("effectReadBack").GetBoolean(), Is.False);
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("Steam was asked to show its library; whether it shows now was "
                    + "not checked: input_visible_controls can look before saying so"));
            }
        });
    }

    // Renew al máximo (6.2): whether the application's window changed from its drawing before the address is said
    // (placeWindowChanged), aids on or off, and only that: a change does not prove the place arrived. Unknown (no
    // drawing read) is not said. With the aid place_unverified, a window that did not change is said in its sentence.
    [TestCase("all", true, null)]
    [TestCase("all", false, "Steam was asked to show its library; its window did not change within 5 s; whether it "
        + "shows now was not checked: input_visible_controls can look before saying so")]
    [TestCase("all", null, "Steam was asked to show its library; whether it shows now was not checked: "
        + "input_visible_controls can look before saying so")]
    [TestCase("none", false, null)]
    public async Task APlaceHandedOverSaysWhetherTheWindowChanged(string aids, bool? changed, string? sentence)
    {
        using IDisposable setting = ModelAids.Use(aids);
        var handler = new AppOpenHandler(
            new VerifiedOpening(@"C:\Program Files (x86)\Steam\steam.exe"),
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            new DrawnPlace(changed),
            frontOf: static _ => new OpenedWindowFront(true, "steamwebhelper"));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"library"}"""), CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(result.TryGetProperty("placeWindowChanged", out JsonElement said)
                ? said.GetBoolean() : (bool?)null, Is.EqualTo(changed));
            if (sentence is not null)
                Assert.That(result.GetProperty("next").GetString(), Is.EqualTo(sentence));
            if (aids == "none")
                Assert.That(result.TryGetProperty("next", out _), Is.False);
        });
    }

    // Renew al máximo (6.2): the place opener's watch of the window's drawing says changed, unchanged within its time,
    // or nothing when no drawing could be read (before the address, or during the watch).
    // Each frame is one drawing read in turn; the last one is read again from then on. Only an unchanged drawing waits
    // out the watch, so the others get time enough to be read on a loaded machine.
    [TestCase(new[] { "a", "a", "b" }, true)]
    [TestCase(new[] { "a" }, false)]
    [TestCase(new[] { "a", "a", null }, null)]
    [TestCase(new string?[] { null }, null)]
    public void ThePlaceWatchSaysWhetherTheWindowsDrawingChanged(string?[] frames, bool? expected)
    {
        int read = 0;
        VisibleControlSurface.CapturedWindow? Frame(int index) =>
            frames[Math.Min(index, frames.Length - 1)] is { } sha
                ? new VisibleControlSurface.CapturedWindow(4660, [], 0, 0, 10, 10, sha) : null;
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, CancellationToken token) =>
            ValueTask.FromResult(Frame(++read));

        bool? changed = ShellApplicationPlaceOpener.AwaitPlaceDrawn(
            Frame(0), Capture, static _ => Thread.Sleep(1), TimeSpan.FromMilliseconds(expected == false ? 50 : 5000));

        Assert.That(changed, Is.EqualTo(expected));
    }

    // Fase 3, H9 (practice e2e, «abre Steam y ve a la biblioteca» with Steam cold): the window's drawing came back black,
    // the capture threw, and the exception stopped the core (exit 70: engine_no_answer, the turn lost). A drawing that
    // cannot be read is no drawing read: before the address the watch says nothing; during it, it keeps looking.
    [TestCase(new[] { "a", "!", "b" }, true)]
    [TestCase(new[] { "a", "!" }, false)]
    public void AnUnreadableDrawingDuringThePlaceWatchIsLookedAtAgain(string[] frames, bool expected)
    {
        int read = 0;
        VisibleControlSurface.CapturedWindow Frame(int index) =>
            frames[Math.Min(index, frames.Length - 1)] is var sha && sha != "!"
                ? new VisibleControlSurface.CapturedWindow(4660, [], 0, 0, 10, 10, sha)
                : throw new IOException("Window content capture came back black.");
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(Frame(++read));

        bool? changed = ShellApplicationPlaceOpener.AwaitPlaceDrawn(
            Frame(0), Capture, static _ => Thread.Sleep(1), TimeSpan.FromMilliseconds(expected ? 5000 : 50));

        Assert.That(changed, Is.EqualTo(expected));
    }

    [Test]
    public void AnUnreadableDrawingBeforeTheAddressIsNoDrawing()
    {
        static ValueTask<VisibleControlSurface.CapturedWindow?> Black(nint window, CancellationToken token) =>
            throw new IOException("Window content capture came back black.");

        Assert.That(ShellApplicationPlaceOpener.Drawing(4660, Black), Is.Null);
    }

    // Renew al máximo (6.3, aid open_recovery): a failed opening says, as facts, whether its launch was issued (and an
    // instance it reused), and where the model can look before telling the person: after a launch whose window was not
    // verified, or a launch Windows did not take. Only the facts of the provider's receipt; with BAXY_AYUDAS=none, or
    // another aid alone, it is the result it was.
    // Encargo 34: the look comes first, as the call with its argument written.
    [TestCase("all", "verification_failed", true, false, true,
        "window_application_status {\"name\":\"Bloc de notas\"} tells whether a window of Bloc de notas shows now, "
        + "before saying it opened or not; a launch of Bloc de notas was issued and no window of it was verified")]
    [TestCase("open_recovery", "verification_failed", false, false, true,
        "window_application_status {\"name\":\"Bloc de notas\"} tells whether a window of Bloc de notas shows now, "
        + "before saying it opened or not; no window of Bloc de notas was verified")]
    [TestCase("all", "inventory_failed", false, true, true,
        "window_application_status {\"name\":\"Bloc de notas\"} tells whether a window of Bloc de notas shows now, "
        + "before saying it opened or not; Bloc de notas was already running and no window of it was verified")]
    [TestCase("all", "launch_failed", false, false, true,
        "window_application_status {\"name\":\"Bloc de notas\"} tells whether Bloc de notas is open already; the "
        + "launch of Bloc de notas was not issued (Windows did not take it)")]
    [TestCase("all", "inventory_failed", false, false, true, null)]
    [TestCase("all", "new_document_not_created", true, false, true, null)]
    [TestCase("none", "verification_failed", true, false, false, null)]
    [TestCase("none", "launch_failed", false, false, false, null)]
    [TestCase("place_unverified", "verification_failed", true, false, false, null)]
    public async Task AFailedOpeningSaysWhetherItsLaunchWasIssuedAndWhereToLook(
        string aids, string code, bool launchIssued, bool reused, bool facts, string? next)
    {
        using IDisposable setting = ModelAids.Use(aids);

        OperationOutcome outcome = await Handler(new FailedOpening(code, launchIssued, reused))
            .ExecuteAsync(Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);
        JsonElement? result = outcome.Result;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(launchIssued || reused));
            Assert.That(result?.TryGetProperty("launchIssued", out JsonElement issued) == true
                ? issued.GetBoolean() : (bool?)null, Is.EqualTo(facts ? launchIssued : null));
            Assert.That(result?.TryGetProperty("alreadyRunning", out JsonElement running) == true
                ? running.GetBoolean() : (bool?)null, Is.EqualTo(facts && reused ? true : null));
            Assert.That(result?.TryGetProperty("next", out JsonElement said) == true ? said.GetString() : null,
                Is.EqualTo(next));
        });
    }

    // Renew al máximo (velocidad, E014): an opening that ended on its application's frame shown empty says so, as a fact
    // with the aids on or off, and the hint says what was seen instead of a window, never that it opened.
    // uso-108 C12: the code a process of the launch died of is said beside the failure, only then.
    [Test]
    public async Task AnOpeningWhoseProcessDiedSaysItsCode()
    {
        OperationOutcome died = await Handler(new FailedOpening("verification_failed", true, false, exitedWithError: "0xC0000135"))
            .ExecuteAsync(Invocation("""{"appId":"Programa"}"""), CancellationToken.None);
        OperationOutcome waited = await Handler(new FailedOpening("verification_failed", true, false))
            .ExecuteAsync(Invocation("""{"appId":"Programa"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(died.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(died.Result!.Value.GetProperty("exitedWithError").GetString(), Is.EqualTo("0xC0000135"));
            Assert.That(waited.Result!.Value.TryGetProperty("exitedWithError", out _), Is.False);
        });
    }

    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AnOpeningEndedOnAnEmptyFrameSaysWhatItSaw(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);

        OperationOutcome outcome = await Handler(new FailedOpening("verification_failed", true, false, emptyFrame: true))
            .ExecuteAsync(Invocation("""{"appId":"Configuración","place":"sound"}"""), CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(result.GetProperty("emptyFrame").GetBoolean(), Is.True);
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("Windows shows a window frame of Configuración with nothing of "
                    + "Configuración inside it (its program does not draw there); no window of it was verified"));
            }
        });
    }

    // Contracaso (6.3): the closest installed names of a name that matched none are said as before, with the aid or not.
    [TestCase("all")]
    [TestCase("none")]
    public async Task ANameThatMatchedNoneKeepsItsCandidates(string aids)
    {
        using IDisposable setting = ModelAids.Use(aids);

        OperationOutcome outcome = await Handler(new FailedOpening("app_not_found", false, false, ["Bloc de notas"]))
            .ExecuteAsync(Invocation("""{"appId":"Bloc"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_not_found"));
            Assert.That(outcome.Result!.Value.GetProperty("candidates").EnumerateArray().Select(name => name.GetString()),
                Is.EqualTo(new[] { "Bloc de notas" }));
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
        });
    }

    // Banco de entorno del NB (R17: «Opera GX» → app_not_found with «Navegador Opera GX» among the candidates; two of three
    // runs gave up there). The one installed name that holds the name asked leads the next as the call, with the model's
    // other arguments as written; nothing was opened. With the aid off, or no holder, no such next.
    [TestCase("all", "Navegador Opera GX", true)]
    [TestCase("none", "Navegador Opera GX", false)]
    [TestCase("all", null, false)]
    public async Task ANameOneInstalledNameHoldsLeadsWithTheCallThatNamesIt(string aids, string? holder, bool told)
    {
        using IDisposable setting = ModelAids.Use(aids);
        var opening = new FailedOpening("app_not_found", false, false, ["Navegador Opera GX", "Opera Mail"])
        {
            NameHolder = holder,
        };

        OperationOutcome outcome = await Handler(opening)
            .ExecuteAsync(Invocation("""{"appId":"Opera GX","foreground":true,"forControl":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_not_found"));
            bool hasNext = outcome.Result!.Value.TryGetProperty("next", out JsonElement next);
            Assert.That(hasNext, Is.EqualTo(told));
            if (told)
                Assert.That(next.GetString(), Does.StartWith(
                    """app_open {"appId":"Navegador Opera GX","foreground":true,"forControl":true} opens Navegador Opera GX"""));
        });
    }

    // Encargo 18 (banco de uso, U08/U14/U15: «Calculator» ambiguous, asked again the same until the calls ran out): an
    // ambiguous opening says its candidates and that each, written as it is there, is an appId the opening takes; a
    // candidate's identity with a path's signs reaches the provider (it was refused as invalid_application before it).
    [Test]
    public async Task AnAmbiguousOpeningSaysEachCandidateIsAnAppIdItTakes()
    {
        using IDisposable setting = ModelAids.Use("all");
        string[] candidates = [@"Vortex (C:\Herramientas\Vortex\vortex.exe)", "Vortex (Nexus.Vortex_b2c3d4!App)"];

        OperationOutcome ambiguous = await Handler(new FailedOpening("app_ambiguous", false, false, candidates))
            .ExecuteAsync(Invocation("""{"appId":"Vortex"}"""), CancellationToken.None);
        OperationOutcome byPath = await Handler(new FailedOpening("app_not_found", false, false))
            .ExecuteAsync(Invocation("""{"appId":"C:\\Herramientas\\Vortex\\vortex.exe"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(ambiguous.ErrorCode, Is.EqualTo("app_ambiguous"));
            Assert.That(ambiguous.Result!.Value.GetProperty("candidates").EnumerateArray().Select(name => name.GetString()),
                Is.EqualTo(candidates));
            Assert.That(ambiguous.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(
                "nothing was opened: more than one installed application answers to Vortex; app_open with appId set to "
                + "one of candidates, written exactly as it is there, opens that one"));
            Assert.That(byPath.ErrorCode, Is.EqualTo("app_not_found"));
        });
    }

    // Contracaso: an opening with no place says nothing of one.
    [Test]
    public async Task AnOpeningWithNoPlaceCarriesNoPlaceHint()
    {
        OperationOutcome outcome = await Handler(new VerifiedOpening(@"C:\Windows\System32\notepad.exe"))
            .ExecuteAsync(Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
            Assert.That(outcome.Result!.Value.TryGetProperty("effectReadBack", out _), Is.False);
        });
    }

    // BAXY Renew cu (C04): a game's page asked for by the game's title opens by the number its catalog found, and the
    // game found is named back; a title nothing bears opens nothing and says so.
    [Test]
    public async Task AGamePageAskedForByTitleOpensByTheNumberFoundAndNamesTheGame()
    {
        var opened = new List<string>();
        var titles = new FoundTitles(new GameTitle("289070", "Sid Meier's Civilization VI"));

        OperationOutcome outcome = await SteamHandler(opened, titles).ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"game","placeValue":"Sid Meier Civilization VI"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(titles.Asked, Is.EqualTo(new[] { "steam:Sid Meier Civilization VI" }));
            Assert.That(opened, Is.EqualTo(new[] { "steam://store/289070" }));
            JsonElement game = outcome.Result!.Value.GetProperty("placeGame");
            Assert.That(game.GetProperty("number").GetString(), Is.EqualTo("289070"));
            Assert.That(game.GetProperty("name").GetString(), Is.EqualTo("Sid Meier's Civilization VI"));
        });
    }

    [Test]
    public async Task AGameNumberIsNotLookedUpAndATitleNothingBearsOpensNothing()
    {
        var opened = new List<string>();
        var titles = new FoundTitles(null);
        AppOpenHandler handler = SteamHandler(opened, titles);

        OperationOutcome byNumber = await handler.ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"game","placeValue":"367520"}"""), CancellationToken.None);
        OperationOutcome unknown = await handler.ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"game","placeValue":"Juego Que No Existe"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(byNumber.Succeeded, Is.True, byNumber.ErrorCode);
            Assert.That(byNumber.Result!.Value.TryGetProperty("placeGame", out _), Is.False);
            Assert.That(unknown.ErrorCode, Is.EqualTo("game_title_not_found"));
            Assert.That(unknown.Result!.Value.GetProperty("title").GetString(), Is.EqualTo("Juego Que No Existe"));
            Assert.That(titles.Asked, Is.EqualTo(new[] { "steam:Juego Que No Existe" }));
            Assert.That(opened, Is.EqualTo(new[] { "steam://store/367520" }), "a title nothing bears opens nothing");
        });
    }

    // Renew al máximo: game.store.page's title «1942» was taken as a store number (steam://store/1942, another game
    // or none). A title said as such is searched as a title whatever its characters; app.open's own digits stay a
    // number.
    [Test]
    public async Task AGamePageTitleOfDigitsIsSearchedAsATitle()
    {
        var opened = new List<string>();
        var titles = new FoundTitles(new GameTitle("1234560", "1942"));
        var page = new GameStoreHandler("game.store.page", "game", "title", SteamHandler(opened, titles).ExecuteAsync);

        OperationOutcome outcome = await page.ExecuteAsync(Invocation("""{"title":"1942"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(titles.Asked, Is.EqualTo(new[] { "steam:1942" }));
            Assert.That(opened, Is.EqualTo(new[] { "steam://store/1234560" }));
            JsonElement game = outcome.Result!.Value.GetProperty("placeGame");
            Assert.That(game.GetProperty("name").GetString(), Is.EqualTo("1942"));
        });
    }

    // Banco de uso 2026-11-03 (U33): a game's store page asked for on a PC without the store's client failed app_not_found
    // although the store has the page on the web. A place whose data declare its web page says it, filled with the game
    // found, and what opens it; nothing is opened.
    [Test]
    public async Task AGamePageWithNoClientSaysItsPageOnTheWeb()
    {
        var opened = new List<string>();
        var titles = new FoundTitles(new GameTitle("1234561", "Granja Inventada"));
        var handler = new AppOpenHandler(
            new FailedOpening("app_not_found", false, false),
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            new RecordedPlace(opened),
            frontOf: static _ => new OpenedWindowFront(true, "steamwebhelper"),
            games: titles);
        var page = new GameStoreHandler("game.store.page", "game", "title", handler.ExecuteAsync);

        OperationOutcome outcome = await page.ExecuteAsync(Invocation("""{"title":"granja inventada"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_not_found"));
            Assert.That(outcome.Result!.Value.GetProperty("placeWebUrl").GetString(),
                Is.EqualTo("https://store.steampowered.com/app/1234561"));
            Assert.That(outcome.Result!.Value.GetProperty("placeGame").GetProperty("name").GetString(),
                Is.EqualTo("Granja Inventada"));
            // Encargo 28 (U33): the call that opens it comes first, written with its address; nothing opened, after it.
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Does.StartWith(
                "browser_navigate_set {\"url\":\"https://store.steampowered.com/app/1234561\"} opens this place's page")
                .And.Contain("this call opened nothing"));
            Assert.That(opened, Is.Empty);
        });
    }

    // Renew al máximo (auditoría de flujos): a title search that got no answer (no network) opens nothing and says so,
    // never that no game bears the title.
    [Test]
    public async Task AGameTitleSearchWithNoAnswerIsSaidAsSuch()
    {
        var opened = new List<string>();
        OperationOutcome outcome = await SteamHandler(opened, new FailedTitles()).ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"game","placeValue":"Hades"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("game_title_search_failed"));
            Assert.That(outcome.Result!.Value.GetProperty("title").GetString(), Is.EqualTo("Hades"));
            Assert.That(opened, Is.Empty);
        });
    }

    // Uso real 04-11 (F26): an opening with no place listed the application's places in its result, and one of them was
    // told as where it opened. It names none, aids on or off; a place asked for still says it was only asked for.
    [TestCase("all")]
    [TestCase("none")]
    public async Task AnOpeningWithNoPlaceNamesNoPlace(string aids)
    {
        using IDisposable setting = ModelAids.Use(aids);

        OperationOutcome outcome = await SteamHandler([], new FoundTitles(null)).ExecuteAsync(
            Invocation("""{"appId":"Steam"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
            Assert.That(outcome.Result!.Value.GetRawText(), Does.Not.Contain("community"));
        });
    }

    // Encargo 80: asked to open Settings and say whether the mode is light or dark, the model walked its pages and told a
    // theme's name as the mode. An application whose data declare a read says that call first, opened with no place.
    [TestCase("all", "{\"appId\":\"Settings\"}", true)]
    [TestCase("all", "{\"appId\":\"Configuración\"}", true)]
    [TestCase("all", "{\"appId\":\"Settings\",\"place\":\"sound\"}", false)]
    [TestCase("none", "{\"appId\":\"Settings\"}", false)]
    public async Task AnOpeningWithNoPlaceSaysTheReadItsApplicationsDataDeclare(string aids, string call, bool said)
    {
        using IDisposable setting = ModelAids.Use(aids);

        OperationOutcome outcome = await SteamHandler([], new FoundTitles(null)).ExecuteAsync(
            Invocation(call), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            string next = outcome.Result!.Value.TryGetProperty("next", out JsonElement written)
                ? written.GetString()!
                : string.Empty;
            if (said)
            {
                Assert.That(next, Does.StartWith("system_settings_status {\"setting\":\"color_mode\"} reads Windows' light "
                    + "or dark mode"));
                Assert.That(next, Does.Not.Contain("place"));
            }
            else
            {
                Assert.That(next, Does.Not.Contain("system_settings_status"));
            }
        });
    }

    // BAXY Renew cu (C04 variant): a place the application has, refused for its value (a game's name given to its
    // library), is told apart from a place it does not have, with what each of its places takes; nothing is opened.
    [Test]
    public async Task APlaceRefusedForItsValueSaysWhatEachPlaceTakes()
    {
        using IDisposable setting = ModelAids.Use("all");
        var opened = new List<string>();

        OperationOutcome outcome = await SteamHandler(opened, new FoundTitles(null)).ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"library","placeValue":"Hollow Knight"}"""), CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("place_value_not_taken"));
            Assert.That(result.GetProperty("placeValue").GetString(), Is.EqualTo("Hollow Knight"));
            Assert.That(result.GetProperty("next").GetString(), Does.Contain("game (placeValue: the game's name)"));
            // P2.15: the opening's hint («also opens») read as an opening done; a refusal says first that nothing opened.
            Assert.That(result.GetProperty("next").GetString(), Does.StartWith("nothing was opened."));
            Assert.That(result.GetProperty("next").GetString(), Does.Not.Contain("also"));
            Assert.That(opened, Is.Empty);
        });
    }

    // Revisión 2026-10-22 (B-APP-3): a value that does not fit its place, or a value given with no place, is a value
    // not taken, never a place of another application (Steam has «game»); with the aids off too it says the places of
    // its application and what each takes. Nothing is looked up or opened.
    [TestCase("""{"appId":"Steam","placeValue":"Rocket League"}""", null)]
    [TestCase("""{"appId":"Steam","place":"game","placeValue":"12345678901234567"}""", "game")]
    [TestCase("""{"appId":"Steam","place":"library","placeValue":"Hollow Knight"}""", "library")]
    public async Task AValueItsPlaceDoesNotTakeSaysThePlacesAndWhatEachTakes(string arguments, string? place)
    {
        using IDisposable setting = ModelAids.Use("none");
        var opened = new List<string>();
        var titles = new FoundTitles(null);

        OperationOutcome outcome = await SteamHandler(opened, titles).ExecuteAsync(Invocation(arguments), CancellationToken.None);
        JsonElement result = outcome.Result!.Value;
        Dictionary<string, string?> places = result.GetProperty("places").EnumerateArray().ToDictionary(
            static entry => entry.GetProperty("place").GetString()!,
            static entry => entry.TryGetProperty("takes", out JsonElement takes) ? takes.GetString() : null);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("place_value_not_taken"));
            Assert.That(result.TryGetProperty("place", out JsonElement asked) ? asked.GetString() : null, Is.EqualTo(place));
            Assert.That(places["game"], Is.EqualTo("game"));
            Assert.That(places["results"], Is.EqualTo("query"));
            Assert.That(places["library"], Is.Null);
            Assert.That(titles.Asked, Is.Empty);
            Assert.That(opened, Is.Empty);
        });
    }

    // A search's text is never a game's title to look up.
    [Test]
    public async Task ASearchTextIsNotLookedUpAsAGame()
    {
        var titles = new FoundTitles(null);

        OperationOutcome outcome = await SteamHandler([], titles).ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"results","placeValue":"batman"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(titles.Asked, Is.Empty);
        });
    }

    // BAXY Renew cu (C03 en frío): Steam started by this opening shows its sign-in first and the place handed then was
    // lost. The data says it starts behind its sign-in: once its window settles the place goes again, and the receipt
    // names that window. Contracases: already running, or an application the data does not mark, waits for nothing.
    // Renew al máximo (auditoría de flujos): Steam in the notification area shows a window new to the opening from a
    // process that was already running: no sign-in to wait for (it waited the whole 30 s for its window to go away).
    [TestCase("Steam", "library", false, true, 2, 999)]
    [TestCase("Steam", "library", true, false, 1, 777)]
    [TestCase("Steam", "library", false, false, 1, 777)]
    [TestCase("Configuración", "display", false, true, 1, 777)]
    public async Task AnApplicationStartedBehindItsSignInGetsItsPlaceAgainOnceItsWindowSettles(
        string app, string place, bool running, bool startedNow, int handed, long window)
    {
        var opened = new List<string>();
        int waited = 0;
        // The opening's own clock: a process created at the moment it began was started by it, however long this test
        // takes to reach it (read from the wall clock, a cold run alone left it more than a clock tick behind).
        var handler = new AppOpenHandler(
            new VerifiedOpening(@"C:\Program Files (x86)\Steam\steam.exe", running,
                startedNow ? OpeningStarted.UtcTicks : 638900000000000000),
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            new RecordedPlace(opened),
            frontOf: static _ => new OpenedWindowFront(true, "steamwebhelper"),
            settle: (_, _, _) => { waited++; return ValueTask.FromResult(999L); },
            time: new FixedTime(OpeningStarted));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation($$"""{"appId":"{{app}}","place":"{{place}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(opened, Has.Count.EqualTo(handed));
            Assert.That(waited, Is.EqualTo(handed - 1));
            Assert.That(outcome.Result!.Value.GetProperty("windowHandle").GetInt64(), Is.EqualTo(window));
        });
    }

    // Al máximo, flujos: the wait for that window (up to 30 s) held a thread asleep inside app.open, under the engine's
    // one execution at a time; it is awaited, and the opening answers once it settles.
    [Test]
    public async Task TheWaitForTheSignInWindowHoldsNoThread()
    {
        var opened = new List<string>();
        var settled = new TaskCompletionSource<long>(TaskCreationOptions.RunContinuationsAsynchronously);
        var handler = new AppOpenHandler(
            new VerifiedOpening(@"C:\Program Files (x86)\Steam\steam.exe", false, OpeningStarted.UtcTicks),
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            new RecordedPlace(opened),
            frontOf: static _ => new OpenedWindowFront(true, "steamwebhelper"),
            settle: (_, _, _) => new ValueTask<long>(settled.Task),
            time: new FixedTime(OpeningStarted));

        ValueTask<OperationOutcome> opening = handler.ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"library"}"""), CancellationToken.None);
        bool answeredBeforeTheWindowSettled = opening.IsCompleted;
        settled.SetResult(999);
        OperationOutcome outcome = await opening;

        Assert.Multiple(() =>
        {
            Assert.That(answeredBeforeTheWindowSettled, Is.False);
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(opened, Has.Count.EqualTo(2));
            Assert.That(outcome.Result!.Value.GetProperty("windowHandle").GetInt64(), Is.EqualTo(999));
        });
    }

    // The moment an opening under test begins, on its own clock.
    private static readonly DateTimeOffset OpeningStarted = new(2026, 10, 25, 12, 0, 0, TimeSpan.Zero);

    private sealed class FixedTime(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }

    private static AppOpenHandler SteamHandler(List<string> opened, IGameTitles titles) => new(
        new VerifiedOpening(@"C:\Program Files (x86)\Steam\steam.exe"),
        new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
        new RecordedPlace(opened),
        frontOf: static _ => new OpenedWindowFront(true, "steamwebhelper"),
        games: titles);

    private sealed class FoundTitles(GameTitle? found) : IGameTitles
    {
        internal List<string> Asked { get; } = [];

        public ValueTask<GameTitle?> FindAsync(string catalog, string title, CancellationToken cancellationToken)
        {
            Asked.Add($"{catalog}:{title}");
            return ValueTask.FromResult(found);
        }
    }

    private sealed class FailedTitles : IGameTitles
    {
        public ValueTask<GameTitle?> FindAsync(string catalog, string title, CancellationToken cancellationToken) =>
            throw new GameTitleSearchFailedException(new HttpRequestException("simulated offline store"));
    }

    // Renew al máximo (guarda msconfig): E014 «abre la configuración de sonido» asked app.open for «Configuración del
    // sistema», which is msconfig, and it opened elevated without asking (the incidente del 2026-10-15 disabled 256
    // services from that window). An opening whose name resolves to a tool that configures Windows itself (the system
    // tools no click acts on) waits for the person's yes, bound to that invocation, and launches nothing before it;
    // Windows' Settings app and Notepad open straight. Through the engine, with the provider's own catalog resolution.
    [TestCase("Configuración del sistema", true)]
    [TestCase("Servicios", true)]
    [TestCase("Configuración", false)]
    [TestCase("Bloc de notas", false)]
    public async Task OpeningASystemToolWaitsForTheYesAndLaunchesNothing(string appId, bool asks)
    {
        var platform = new SystemToolsPlatform();

        OperationResponse response = await OpenThroughEngine(platform, appId, confirm: false);

        Assert.Multiple(() =>
        {
            if (asks)
            {
                Assert.That(response.Status, Is.EqualTo(OperationStatuses.Pending));
                Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
                Assert.That(platform.Activated, Is.Empty, "nothing is launched before the yes");
            }
            else
            {
                Assert.That(response.ErrorCode, Is.Not.EqualTo("confirmation_required"));
                Assert.That(platform.Activated, Is.EqualTo(new[] { appId }));
            }
        });
    }

    // The yes given to that same invocation launches it.
    [Test]
    public async Task ASystemToolOpensOnTheYesToThatInvocation()
    {
        var platform = new SystemToolsPlatform();

        OperationResponse response = await OpenThroughEngine(platform, "Configuración del sistema", confirm: true);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.Not.EqualTo("confirmation_required"));
            Assert.That(platform.Activated, Is.EqualTo(new[] { "Configuración del sistema" }));
        });
    }

    // E014 (int3 s1): a system tool asked for at a place it does not have is refused by the opening, launching nothing,
    // with no yes asked first (the person was asked to open msconfig at «sonido» and the opening then failed).
    [Test]
    public async Task ASystemToolAtAPlaceItDoesNotHaveIsRefusedWithoutAsking()
    {
        var platform = new SystemToolsPlatform();

        OperationResponse response = await OpenThroughEngine(
            platform, "Configuración del sistema", confirm: false, place: "sound");

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("place_not_of_application"));
            Assert.That(platform.Activated, Is.Empty);
        });
    }

    // Revisión del núcleo (q-core): a value with no place (or one its place does not take) is refused by the opening too,
    // launching nothing (place_value_not_taken); asking the yes for msconfig first asked for nothing, as E014 int3 s1.
    [Test]
    public async Task ASystemToolWithAValueAndNoPlaceIsRefusedWithoutAsking()
    {
        var platform = new SystemToolsPlatform();

        OperationResponse response = await OpenThroughEngine(
            platform, "Configuración del sistema", confirm: false, placeValue: "sonido");

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("place_value_not_taken"));
            Assert.That(platform.Activated, Is.Empty);
        });
    }

    // Revisión del núcleo (q-core): clipboard.paste.into opens its application through app.open; a system tool named
    // there asks as app.open does, and nothing is launched before the yes. It launched msconfig without asking.
    [TestCase(true, "Configuración del sistema")]
    [TestCase(false, "Bloc de notas")]
    public async Task APasteIntoASystemToolWaitsForTheYesAndLaunchesNothing(bool asks, string appId)
    {
        var platform = new SystemToolsPlatform();
        AppOpenHandler open = Handler(new WindowsInstalledApplicationOpenProvider(platform));
        var handler = new PasteIntoNewDocumentHandler(new NoPaste(), open.ExecuteAsync, openPreflight: open);
        string root = Path.Combine(Path.GetTempPath(), "baxy-paste-system-tool-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                Path.Combine(root, "journal.jsonl"),
                new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
            using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
            OperationResponse response = await engine.ExecuteAsync(
                new OperationRequest(
                    ProtocolTypes.OperationRequest,
                    Guid.NewGuid().ToString("D"),
                    Guid.NewGuid().ToString("D"),
                    Guid.NewGuid().ToString("D"),
                    "clipboard.paste.into",
                    JsonSerializer.SerializeToElement(new { appId })),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                if (asks)
                {
                    Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
                    Assert.That(platform.Activated, Is.Empty, "nothing is launched before the yes");
                }
                else
                {
                    Assert.That(response.ErrorCode, Is.Not.EqualTo("confirmation_required"));
                    Assert.That(platform.Activated, Is.EqualTo(new[] { appId }));
                }
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private sealed class NoPaste : IOperationHandler
    {
        public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("clipboard.paste");

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
            ValueTask.FromResult(OperationOutcome.Failure("clipboard_empty"));
    }

    // The rule is the one clicks are refused by (SystemToolProcesses, the applets of lote 4 c): the program a shortcut
    // runs, a console of the MMC host, an applet by its .cpl or run by rundll32. Contracasos: the Sound applet the person
    // asks for, Notepad, a document.
    [TestCase(@"C:\WINDOWS\system32\msconfig.exe", null, true)]
    [TestCase(@"C:\WINDOWS\regedit.exe", null, true)]
    [TestCase(@"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\taskschd.msc", null, true)]
    [TestCase(@"C:\WINDOWS\system32\compmgmt.msc", null, true)]
    [TestCase(@"C:\WINDOWS\system32\firewall.cpl", null, true)]
    [TestCase(@"C:\WINDOWS\system32\rundll32.exe", "shell32.dll,Control_RunDLL ncpa.cpl", true)]
    [TestCase(@"C:\WINDOWS\system32\rundll32.exe", "shell32.dll,Control_RunDLL mmsys.cpl", false)]
    [TestCase(@"C:\WINDOWS\system32\notepad.exe", null, false)]
    [TestCase(@"C:\Users\persona\Documents\msconfig.txt", null, false)]
    [TestCase(null, null, false)]
    public void ALaunchIsASystemToolByTheRuleClicksAreRefusedBy(string? target, string? arguments, bool expected) =>
        Assert.That(VisibleControlSurface.SystemToolLaunch(target, arguments), Is.EqualTo(expected));

    private static async Task<OperationResponse> OpenThroughEngine(
        SystemToolsPlatform platform, string appId, bool confirm, string? place = null, string? placeValue = null)
    {
        AppOpenHandler handler = Handler(new WindowsInstalledApplicationOpenProvider(platform));
        string root = Path.Combine(Path.GetTempPath(), "baxy-system-tool-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                Path.Combine(root, "journal.jsonl"),
                new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
            using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
            var request = new OperationRequest(
                ProtocolTypes.OperationRequest,
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                "app.open",
                placeValue is not null
                    ? place is null
                        ? JsonSerializer.SerializeToElement(new { appId, placeValue })
                        : JsonSerializer.SerializeToElement(new { appId, place, placeValue })
                    : place is null
                        ? JsonSerializer.SerializeToElement(new { appId })
                        : JsonSerializer.SerializeToElement(new { appId, place }));
            OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
            if (confirm && response.ErrorCode == "confirmation_required")
            {
                response = await engine.ExecuteAsync(
                    request with { ConfirmationToken = response.Result!.Value.GetProperty("token").GetString() },
                    CancellationToken.None);
            }

            return response;
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    /// <summary>
    /// The Start catalog as Windows lists it: msconfig and the Services console by the shortcuts of Windows' tools, the
    /// Settings app and Notepad as packaged applications. An activation is recorded and refused (nothing runs).
    /// </summary>
    private sealed class SystemToolsPlatform : IInstalledApplicationPlatform
    {
        private static readonly InstalledApplicationEntry[] Catalog =
        [
            new("Configuración del sistema", @"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\msconfig.exe",
                @"C:\WINDOWS\system32\msconfig.exe"),
            new("Servicios", @"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\services.msc",
                @"C:\WINDOWS\system32\services.msc"),
            new("Configuración", "windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel"),
            new("Bloc de notas", "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"),
        ];

        public List<string> Activated { get; } = [];

        public ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(CancellationToken cancellationToken) =>
            ValueTask.FromResult<IReadOnlyList<InstalledApplicationEntry>>(Catalog);

        public IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry) => [];

        public bool Activate(InstalledApplicationEntry entry)
        {
            Activated.Add(entry.Name);
            return false;
        }

        public void RequestForeground(long windowHandle)
        {
        }

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }

    private sealed class RecordedPlace(List<string> opened) : IApplicationPlaceOpener
    {
        public PlaceOpening Open(string address, bool keepFront, long applicationWindow)
        {
            opened.Add(address);
            return new(true);
        }
    }

    private sealed class HandedPlace : IApplicationPlaceOpener
    {
        public PlaceOpening Open(string address, bool keepFront, long applicationWindow) => new(true);
    }

    private sealed class DrawnPlace(bool? changed) : IApplicationPlaceOpener
    {
        public PlaceOpening Open(string address, bool keepFront, long applicationWindow) => new(true, WindowChanged: changed);
    }

    private sealed class RefusedPlace : IApplicationPlaceOpener
    {
        public PlaceOpening Open(string address, bool keepFront, long applicationWindow) => new(false);
    }

    private static AppOpenHandler Handler(IApplicationOpenProvider provider, Func<long, OpenedWindowFront>? frontOf = null) => new(
        provider,
        new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
        frontOf: frontOf ?? (static _ => new OpenedWindowFront(true, "Notepad")));

    private static OperationInvocation Invocation(string arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments);
        return new OperationInvocation("request", "mission", "invocation", document.RootElement.Clone());
    }

    /// <summary>An opening that failed with a code, as the provider's receipt tells it.</summary>
    private sealed class FailedOpening(
        string code, bool launchIssued, bool reused, IReadOnlyList<string>? candidates = null, bool emptyFrame = false,
        string? exitedWithError = null)
        : IApplicationOpenProvider
    {
        internal string? NameHolder { get; init; }

        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            var receipt = new ApplicationLaunchReceipt(
                request.InvocationId, request.ApplicationId, launchIssued, reused, ProcessId: null,
                ProcessCreationTimeUtcTicks: null, ExecutablePath: null, PackageFamilyName: null, PackageFullName: null,
                WindowHandle: null, code);
            return ValueTask.FromResult(new ApplicationOpenResult(
                Succeeded: launchIssued || reused, Verified: false, request.ApplicationId, AlreadyRunning: reused,
                ProcessId: null, WindowHandle: null, code, receipt, Candidates: candidates, EmptyFrame: emptyFrame,
                NameHolder: NameHolder, ExitedWithError: exitedWithError));
        }
    }

    /// <summary>A window of a program already running, verified for the opening asked.</summary>
    private sealed class DialogMet(ApplicationDialogMet dialog) : IApplicationOpenProvider
    {
        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            var receipt = new ApplicationLaunchReceipt(
                request.InvocationId, request.ApplicationId, LaunchIssued: true, ReusedExisting: false,
                ProcessId: 4242, ProcessCreationTimeUtcTicks: 638900000000000000, @"C:\Programas\editor.exe",
                PackageFamilyName: null, PackageFullName: null, WindowHandle: 777, ErrorCode: "new_document_not_created");
            return ValueTask.FromResult(new ApplicationOpenResult(
                Succeeded: true, Verified: false, request.ApplicationId, AlreadyRunning: false,
                ProcessId: 4242, WindowHandle: 777, ErrorCode: "new_document_not_created", receipt, DialogOpened: dialog));
        }
    }

    private sealed class VerifiedOpening(
        string executablePath, bool running = true, long created = 638900000000000000) : IApplicationOpenProvider
    {
        internal int Calls { get; private set; }

        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            Calls++;
            var receipt = new ApplicationLaunchReceipt(
                request.InvocationId, request.ApplicationId, LaunchIssued: !running, ReusedExisting: running,
                ProcessId: 4242, ProcessCreationTimeUtcTicks: created, executablePath,
                PackageFamilyName: null, PackageFullName: null, WindowHandle: 777, ErrorCode: null);
            return ValueTask.FromResult(new ApplicationOpenResult(
                Succeeded: true, Verified: true, request.ApplicationId, AlreadyRunning: running,
                ProcessId: 4242, WindowHandle: 777, ErrorCode: null, receipt));
        }
    }
}
