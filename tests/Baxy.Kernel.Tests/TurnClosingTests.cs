using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// When a turn of the native tool loop takes no more calls (src/Baxy.App/TurnClosing.cs, linked here: the App has no
/// test project).
/// </summary>
[TestFixture]
public sealed class TurnClosingTests
{
    private static readonly TimeSpan Soon = TimeSpan.FromSeconds(5);

    [Test]
    public void DifferentCallsInTimeKeepTheTurnOpenUntilTheMoveCap()
    {
        var closing = new TurnClosing();
        for (int call = 1; call < TurnClosing.MaximumModelCalls; call++)
        {
            Assert.That(closing.AfterCall(call, Soon, "web.fetch", $"{{\"url\":\"https://a.example/{call}\"}}",
                Result("completed")), Is.False, $"call {call}");
        }

        Assert.That(closing.AfterCall(TurnClosing.MaximumModelCalls, Soon, "web.fetch", "{\"url\":\"https://b.example\"}",
            Result("completed")), Is.True);
    }

    // E5: four app.open of a console app, each verification_failed after 30 s, and no answer in time. After two the
    // model may still change course (e2e E011: two calculator_window_not_found, then app.open): the third closes it.
    [Test]
    public void TheSameFailedCallThreeTimesClosesTheTurnTwiceDoesNot()
    {
        var closing = new TurnClosing();
        Assert.That(closing.AfterCall(1, Soon, "app.open", "{\"appId\":\"cmd\"}",
            Result("failed", "verification_failed")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "app.open", "{\"appId\":\"cmd\"}",
            Result("failed", "verification_failed")), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"cmd\"}",
            Result("failed", "verification_failed")), Is.True);
    }

    // E022: the same page fetched eight times until the results overflowed the context.
    [Test]
    public void TheSameCompletedCallThreeTimesClosesTheTurn()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://www.rfc-editor.org/info/rfc2324/\"}";
        Assert.That(closing.AfterCall(1, Soon, "web.fetch", page, Result("completed")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "web.fetch", page, Result("completed")), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "web.fetch", page, Result("completed")), Is.True);
    }

    [Test]
    public void AFailureWithOtherArgumentsOrAnotherOutcomeIsANewTry()
    {
        var closing = new TurnClosing();
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "app.open", "{\"appId\":\"cmd\"}",
                Result("failed", "verification_failed")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "app.open", "{\"appId\":\"terminal\"}",
                Result("failed", "verification_failed")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"terminal\"}",
                Result("failed", "launch_failed")), Is.False);
            // The first call again: its second appearance in the turn, not yet the third.
            Assert.That(closing.AfterCall(4, Soon, "app.open", "{\"appId\":\"cmd\"}",
                Result("failed", "verification_failed")), Is.False);
        });
    }

    // Feria 2026-10-27: a navigation and a new tab alternated 16 times in 55 s with no answer, up to the move cap; each
    // call broke the other's run. The same call with the same result a third time in the turn closes it, in a row or not.
    [Test]
    public void TwoCallsThatAlternateCloseTheTurnAtTheThirdAppearance()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://a.example/\"}";
        const string tab = "{\"action\":\"new_tab\"}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "browser.navigate", page, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "browser.control", tab, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "browser.navigate", page, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(4, Soon, "browser.control", tab, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(5, Soon, "browser.navigate", page, Result("completed")), Is.True);
        });
    }

    // Uso-108 (B4): a capture has a new id and moment each time, so a loop that looks at one still screen was only ended
    // by the move cap or the time. The same bytes a third time close the turn, as any read; other bytes are work going on.
    [Test]
    public void TheSameImageCapturedThreeTimesClosesTheTurn()
    {
        var closing = new TurnClosing();
        string[] results = [Captured('a', "sha1"), Captured('b', "sha1"), Captured('c', "sha1")];
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "capture.active.window", "{}", results[0]), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "capture.active.window", "{}", results[1]), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "capture.active.window", "{}", results[2]), Is.True);
        });
    }

    [Test]
    public void CounterCaseCapturesOfAScreenThatChangesKeepTheTurnOpen()
    {
        var closing = new TurnClosing();
        Assert.Multiple(() =>
        {
            for (int call = 1; call < 6; call++)
                Assert.That(closing.AfterCall(call, Soon, "capture.active.window", "{}", Captured('a', "sha" + call)), Is.False);
        });
    }

    // Vision of each new capture of one image: another id in the arguments, the server's other words each time.
    [Test]
    public void VisionOfTheSameBytesThreeTimesClosesTheTurnHoweverItIsWorded()
    {
        var closing = new TurnClosing();
        string Asked(char id) => $$"""{"captureId":"capture_{{new string(id, 32)}}"}""";
        string Told(char id, string words) =>
            $$$"""{"status":"completed","observed":{"captureId":"capture_{{{new string(id, 32)}}}","captureSha256":"s1","description":"{{{words}}}"}}""";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "vision.describe", Asked('a'), Told('a', "una ventana")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "vision.describe", Asked('b'), Told('b', "la misma ventana")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "vision.describe", Asked('c'), Told('c', "otra forma de decirlo")), Is.True);
        });
    }

    private static string Captured(char id, string sha) =>
        "{\"status\":\"completed\",\"observed\":{\"captureId\":\"capture_" + new string(id, 32) + "\",\"sha256\":\"" + sha
        + "\",\"createdAtUtc\":\"2026-11-04T23:0" + id + "\","
        + "\"activeWindow\":{\"captureStartedAtUtc\":\"" + id + "\",\"captureCompletedAtUtc\":\"" + id + "\",\"isClipped\":false}}}";

    // Review of R1: «read me the whole page» scrolls and looks in turn. A scroll that moved says nothing of what it
    // brought (WindowsScrollAdapter: the same result each time) and each look has the same arguments, but each look sees
    // more of the page: a read that sees something not seen before in the turn is work going on, up to the move cap.
    [Test]
    public void ScrollingAndLookingAtNewContentKeepsTheTurnOpenUntilTheMoveCap()
    {
        var closing = new TurnClosing();
        const string scroll = "{\"direction\":\"down\",\"amount\":5}";
        const string look = "{\"includeText\":true}";
        string[] parts = ["Inicio", "Historia", "Geografía", "Economía", "Cultura", "Deporte", "Véase también"];
        Assert.Multiple(() =>
        {
            for (int call = 1; call < TurnClosing.MaximumModelCalls; call++)
            {
                Assert.That(call % 2 == 1
                    ? closing.AfterCall(call, Soon, "input.scroll", scroll, Result("completed"))
                    : closing.AfterCall(call, Soon, "input.visible.controls", look, View(parts[call / 2 - 1])),
                    Is.False, $"call {call}");
            }

            Assert.That(closing.AfterCall(TurnClosing.MaximumModelCalls, Soon, "input.scroll", scroll,
                Result("completed")), Is.True);
        });
    }

    // A look that sees what it saw before is no progress: scrolling a page that no longer moves still closes the turn.
    [Test]
    public void ScrollingAndLookingAtTheSameContentClosesTheTurn()
    {
        var closing = new TurnClosing();
        const string scroll = "{\"direction\":\"down\",\"amount\":5}";
        const string look = "{\"includeText\":true}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "input.scroll", scroll, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "input.visible.controls", look, View("final")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "input.scroll", scroll, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(4, Soon, "input.visible.controls", look, View("final")), Is.False);
            Assert.That(closing.AfterCall(5, Soon, "input.scroll", scroll, Result("completed")), Is.True);
        });
    }

    // Feria 2026-10-27 again: a new tab's result carries the browser's count of tabs, another each time; only what a
    // read sees is progress, so the effects that alternate still close the turn.
    [Test]
    public void AnEffectWithAnotherResultEachTimeIsNoProgress()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://a.example/\"}";
        const string tab = "{\"action\":\"new_tab\"}";
        string Tabs(int count) => $"{{\"status\":\"completed\",\"observed\":{{\"tabCount\":{count}}}}}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "browser.navigate", page, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "browser.control", tab, Tabs(2)), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "browser.navigate", page, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(4, Soon, "browser.control", tab, Tabs(3)), Is.False);
            Assert.That(closing.AfterCall(5, Soon, "browser.navigate", page, Result("completed")), Is.True);
        });
    }

    // Review of the fix: a read that sees the same words again, with other numbers or in another order (a list sorted by
    // load), sees nothing new, so the same failed call between two such reads still closes the turn at its third time.
    [Test]
    public void AReadWithTheSameWordsInAnotherOrderIsNoProgress()
    {
        var closing = new TurnClosing();
        const string open = "{\"appId\":\"cmd\"}";
        const string byLoad = "{\"sort\":\"cpu\"}";
        string Processes(string first, int load, string second) =>
            "{\"status\":\"completed\",\"observed\":{\"processes\":["
            + $"{{\"name\":\"{first}\",\"cpuPercent\":{load}.5}},{{\"name\":\"{second}\",\"cpuPercent\":1.25}}]}}}}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "app.open", open, Result("failed", "verification_failed")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "system.process.list", byLoad, Processes("cmd", 3, "explorer")),
                Is.False);
            Assert.That(closing.AfterCall(3, Soon, "app.open", open, Result("failed", "verification_failed")), Is.False);
            Assert.That(closing.AfterCall(4, Soon, "system.process.list", byLoad, Processes("explorer", 7, "cmd")),
                Is.False);
            Assert.That(closing.AfterCall(5, Soon, "app.open", open, Result("failed", "verification_failed")), Is.True);
        });
    }

    // Review of the branch: a form filled field by field, the same key between each typing, is work going on: each
    // typing was a call not made before, so the key's third time is no loop.
    [Test]
    public void TheSameKeyBetweenNewCallsKeepsTheTurnOpen()
    {
        var closing = new TurnClosing();
        const string tab = "{\"key\":\"tab\"}";
        Assert.Multiple(() =>
        {
            for (int field = 0; field < 4; field++)
            {
                Assert.That(closing.AfterCall(2 * field + 1, Soon, "input.text.type", $"{{\"text\":\"campo {field}\"}}",
                    Result("completed")), Is.False, $"typing {field}");
                Assert.That(closing.AfterCall(2 * field + 2, Soon, "input.key.press", tab, Result("completed")),
                    Is.False, $"key {field}");
            }
        });
    }

    // E011 (base 0be0f9de9): two calculator_window_not_found, then app.open and the sum. Counting over the whole turn
    // keeps it: the failure appeared twice, and the sum that completes is another result.
    [Test]
    public void TwoEqualFailuresThenAnotherCallAndTheSameCallCompletingKeepTheTurnOpen()
    {
        var closing = new TurnClosing();
        const string sum = "{\"expression\":\"2+2\"}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "calculator.expression.evaluate", sum,
                Result("failed", "calculator_window_not_found")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "calculator.expression.evaluate", sum,
                Result("failed", "calculator_window_not_found")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"calculator\"}", Result("completed")),
                Is.False);
            Assert.That(closing.AfterCall(4, Soon, "calculator.expression.evaluate", sum, Result("completed")),
                Is.False);
        });
    }

    [Test]
    public void AWaitingConfirmationIsNotAFailureToRepeat()
    {
        var closing = new TurnClosing();
        Assert.That(closing.AfterCall(1, Soon, "shell.command.run", "{\"command\":\"python --version\"}",
            Result("pending", "confirmation_required")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "shell.command.run", "{\"command\":\"python --version\"}",
            Result("pending", "confirmation_required")), Is.False);
    }

    [Test]
    public void TheTurnsTimeClosesIt()
    {
        var closing = new TurnClosing();
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, TurnClosing.Budget - TimeSpan.FromSeconds(1), "app.open",
                "{\"appId\":\"steam\"}", Result("completed")), Is.False);
            Assert.That(closing.AfterCall(2, TurnClosing.Budget, "input.text.type", "{\"text\":\"hola\"}",
                Result("completed")), Is.True);
        });
    }

    // Al máximo 7.7: three looks at a window that is still loading, each with another view, are three results: the turn
    // went on (before, the third closed it and the model read «same result»).
    [Test]
    public void TheSameCallWithAnotherResultIsNotARepeat()
    {
        var closing = new TurnClosing();
        const string look = "{\"application\":\"steam\"}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "input.visible.controls", look, View("Cargando…")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "input.visible.controls", look, View("Biblioteca")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "input.visible.controls", look, View("Biblioteca · Tienda")),
                Is.False);
        });
    }

    [Test]
    public void TheSameCallWithTheSameResultThreeTimesClosesTheTurn()
    {
        var closing = new TurnClosing();
        const string look = "{\"application\":\"steam\"}";
        Assert.That(closing.AfterCall(1, Soon, "input.visible.controls", look, View("Cargando…")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "input.visible.controls", look, View("Cargando…")), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "input.visible.controls", look, View("Cargando…")), Is.True);
    }

    // How long a call took is not its result: the same console output thrice, each in its own time, is a repeat.
    [Test]
    public void TheTimeACallTookIsNotPartOfItsResult()
    {
        var closing = new TurnClosing();
        const string command = "{\"command\":\"python --version\"}";
        Assert.That(closing.AfterCall(1, Soon, "shell.command.run", command, ConsoleRun(812)), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "shell.command.run", command, ConsoleRun(790)), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "shell.command.run", command, ConsoleRun(805)), Is.True);
    }

    // Holdout v4 (the Steam library, «Biblioteca» 7 times): the click's own count of its unchanged repeats, and the «next»
    // it brings, differ on each repeat and are not its result: the same unchanged click thrice still closes the turn.
    [Test]
    public void AClicksCountOfItsUnchangedRepeatsIsNotPartOfItsResult()
    {
        var closing = new TurnClosing();
        const string click = "{\"label\":\"Biblioteca\"}";
        const string first = "{\"status\":\"failed\",\"error\":\"visible_button_postread_unchanged\"}";
        string Again(int times) => "{\"status\":\"failed\",\"error\":\"visible_button_postread_unchanged\","
            + $"\"observed\":{{\"unchangedInARow\":{times},\"next\":\"changed nothing {times} times\"}}}}";
        Assert.That(closing.AfterCall(1, Soon, "input.visible.click", click, first), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "input.visible.click", click, Again(2)), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "input.visible.click", click, Again(3)), Is.True);
    }

    // Holdout v5 (en vivo, «maximiza Paint»): the same window read 13 times, each with a new single-use windowId
    // (WindowsWindowControlProvider.Issue): the handle is not part of the result, the same read thrice closes the turn.
    [Test]
    public void AWindowsSingleUseHandleIsNotPartOfItsResult()
    {
        var closing = new TurnClosing();
        const string paint = "{\"applicationName\":\"Paint\"}";
        string Read(char digit) => "{\"status\":\"completed\",\"observed\":{\"windows\":[{\"windowId\":\"win_"
            + new string(digit, 32) + "\",\"state\":\"maximized\"}]}}";
        Assert.That(closing.AfterCall(1, Soon, "window.resolve", paint, Read('0')), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "window.resolve", paint, Read('1')), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "window.resolve", paint, Read('a')), Is.True);
    }

    // Uso real 2026-11-02: the same navigation six times in a row, each unconfirmed, until the turn's time ran out; what
    // each failure said it checked (whether a window changed, what kind of address it showed) was another diagnosis of
    // the same failure each time, and no two results were the same. A failed effect is its status and code.
    [Test]
    public void TheSameFailedEffectWithAnotherDiagnosisEachTimeClosesTheTurnAtItsThirdTime()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://shop.example/market\"}";
        string Unconfirmed(bool changed, string seen) =>
            "{\"status\":\"failed\",\"error\":\"user_browser_navigation_unconfirmed\",\"effectUncertain\":true,"
            + "\"observed\":{\"version\":1,\"requestedUrl\":\"https://shop.example/market\",\"browser\":\"Navegador\","
            + $"\"linkSent\":true,\"windowChanged\":{(changed ? "true" : "false")},\"addressSeen\":\"{seen}\"}}}}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "browser.navigate", page, Unconfirmed(true, "page_from_before")),
                Is.False);
            Assert.That(closing.AfterCall(2, Soon, "browser.navigate", page, Unconfirmed(false, "not_read")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "browser.navigate", page, Unconfirmed(true, "unreadable")), Is.True);
        });
    }

    // What a completed effect read back is still its result: the same navigation arriving at two pages is two results.
    [Test]
    public void TheSameCompletedEffectThatArrivedElsewhereIsNotARepeat()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://shop.example/market\"}";
        string Arrived(string final) =>
            $"{{\"status\":\"completed\",\"verification\":\"readback\",\"observed\":{{\"finalUrl\":\"{final}\"}}}}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "browser.navigate", page, Arrived("https://shop.example/a")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "browser.navigate", page, Arrived("https://shop.example/b")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "browser.navigate", page, Arrived("https://shop.example/c")), Is.False);
        });
    }

    private static string Result(string status, string? error = null) =>
        error is null ? $"{{\"status\":\"{status}\"}}" : $"{{\"status\":\"{status}\",\"error\":\"{error}\"}}";

    private static string View(string text) =>
        $"{{\"status\":\"completed\",\"view\":\"window 1 Steam\\n{text}\"}}";

    private static string ConsoleRun(int milliseconds) =>
        "{\"status\":\"completed\",\"observed\":{\"exitCode\":9009,\"stdout\":\"\",\"durationMs\":"
        + milliseconds + ",\"effectReadBack\":false}}";
}
