using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
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
            Assert.That(outcome.Result!.Value.GetProperty("placeIn").EnumerateArray().Select(name => name.GetString()),
                Does.Contain("Steam"));
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
    // launch, and the opening already happened.
    [Test]
    public async Task APlaceThatCouldNotBeHandedOverAfterAVerifiedOpeningIsNotALaunchFailure()
    {
        var provider = new VerifiedOpening(@"C:\Program Files (x86)\Steam\steam.exe");
        var handler = new AppOpenHandler(
            provider,
            new LaunchProvenance(static _ => null, new PersonInputLedger(static () => true, static () => true, static () => 1)),
            new RefusedPlace(),
            frontOf: static _ => new OpenedWindowFront(true, "steam"));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Steam","place":"library"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(provider.Calls, Is.EqualTo(1));
            Assert.That(outcome.ErrorCode, Is.EqualTo("place_not_opened"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
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
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("Steam was asked to show its library; whether it shows now was "
                    + "not checked: input_visible_controls can look before saying so"));
            }
        });
    }

    // Contracaso: an opening with no place says nothing of one.
    [Test]
    public async Task AnOpeningWithNoPlaceCarriesNoPlaceHint()
    {
        OperationOutcome outcome = await Handler(new VerifiedOpening(@"C:\Windows\System32\notepad.exe"))
            .ExecuteAsync(Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);
        Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
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

    // BAXY Renew cu (aid app_places): opened with no place, an application with places of its own names them and what
    // each takes; with BAXY_AYUDAS=none it is the result it was.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AnOpeningWithNoPlaceNamesThePlacesItsApplicationOpensAt(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);

        OperationOutcome outcome = await SteamHandler([], new FoundTitles(null)).ExecuteAsync(
            Invocation("""{"appId":"Steam"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("Steam also opens straight at a place of its own, by app_open "
                    + "with place: community, game (placeValue: the game's name), library, results (placeValue: what to "
                    + "search), store"));
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

    /// <summary>A window of a program already running, verified for the opening asked.</summary>
    private sealed class VerifiedOpening(string executablePath) : IApplicationOpenProvider
    {
        internal int Calls { get; private set; }

        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            Calls++;
            var receipt = new ApplicationLaunchReceipt(
                request.InvocationId, request.ApplicationId, LaunchIssued: false, ReusedExisting: true,
                ProcessId: 4242, ProcessCreationTimeUtcTicks: 638900000000000000, executablePath,
                PackageFamilyName: null, PackageFullName: null, WindowHandle: 777, ErrorCode: null);
            return ValueTask.FromResult(new ApplicationOpenResult(
                Succeeded: true, Verified: true, request.ApplicationId, AlreadyRunning: true,
                ProcessId: 4242, WindowHandle: 777, ErrorCode: null, receipt));
        }
    }
}
