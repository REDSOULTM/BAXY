using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Estabilización D (the owner's decision of 2026-10-10, «no molestar» in its simple form): an act of a computer-use
/// mission (its «window» argument, the catalog's mark of a mission's act) is done with the mission's window in front:
/// the provider asks the lease to take that front before the act (IForegroundLease.TakeForMissionAsync, its rules in
/// ForegroundSequenceTests) and sends nothing when it is refused. A look, an opening and an act of no mission ask nothing.
/// </summary>
[TestFixture]
public sealed class MissionFrontTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    [TestCase("input.visible.click", """{"label":"Buscar","window":18016}""")]
    [TestCase("input.key.press", """{"key":"enter","window":18016}""")]
    [TestCase("input.text.type", """{"text":"hola","window":18016}""")]
    [TestCase("input.scroll", """{"amount":3,"direction":"down","window":18016}""")]
    [TestCase("input.pointer.drag", """{"from":1,"label":"a","window":18016}""")]
    public async Task AMissionsActTakesItsWindowsFrontBeforeItIsSent(string operation, string arguments)
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { 18016 }));
            Assert.That(adapter.FrontTakenWhenSent, Is.True, "taken before the act, never after");
            Assert.That(lease.Ended, Is.EqualTo(new[] { operation }), "the lease is told the act ended");
        });
    }

    // Nothing is sent when the person does not pause or the window does not come to the front: never behind them.
    [TestCase("input_user_not_paused")]
    [TestCase("input_window_not_in_front")]
    public async Task AnActWhoseFrontIsRefusedIsNeverSent(string refusal)
    {
        var lease = new TakingLease { Refusal = refusal };
        var adapter = new RecordingAdapter("input.visible.click", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.visible.click", Json("""{"label":"Buscar","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(refusal));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(lease.Ended, Is.Empty);
        });
    }

    // FT/proveedores goal (live W1): the refusal names the program whose window it was, so the reply does not blame
    // another application.
    [Test]
    public async Task AProtectedWindowRefusalNamesItsProgram()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "WindowsTerminal",
            FrontProcessOf = () => "Baxy",
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(receipt.Result?.GetProperty("refusedProcess").GetString(), Is.EqualTo("WindowsTerminal"));
            // Feria (writing with no window): the window in front is named apart from the refused one, so a reply does
            // not tell one as the other.
            Assert.That(receipt.Result?.GetProperty("frontProcess").GetString(), Is.EqualTo("Baxy"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(adapter.Calls, Is.Zero);
        });
    }

    // BAXY Renew cu (C18): with the aid on, the refusal says nothing was sent and how another application's window is
    // reached; with the aids off it reads as before.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AProtectedWindowRefusalSaysHowAnotherWindowIsReached(string aids, bool next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("clipboard.paste", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.EqualTo(next));
            if (next)
            {
                // A paste names no window: its route is still the opening or the front.
                Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("belongs to Code").And.Contain("app_open")
                    .And.Contain("window_focus").And.Not.Contain("input_visible_controls"));
            }
        });
    }

    // Holdout v5 (V5E066, «en el bloc de notas que tengo abierto escribe: comprar velas»): input_text_type with no window
    // was refused at a protected window in front, and the next named app_open (which may open another Notepad) and
    // window_focus (which needs an id no call had given), never the one look that gives the open window's number. With
    // the aid on, a refused act that takes a window names that look first, and says a step with no window named acts on
    // the window in front; with the aids off it reads as before (no next).
    [TestCase("all", """{"text":"comprar velas"}""", true)]
    [TestCase("all", """{"text":"comprar velas","window":18016}""", true)]
    [TestCase("none", """{"text":"comprar velas"}""", false)]
    public async Task AProtectedWindowRefusalOfAnActThatTakesAWindowNamesTheLookThatGivesItsNumber(
        string aids, string arguments, bool next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json(arguments), CancellationToken.None);

        bool named = arguments.Contains("window", StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.EqualTo(next));
            if (!next)
                return;
            string told = receipt.Result!.Value.GetProperty("next").GetString()!;
            Assert.That(told, Does.StartWith("nothing was sent").And.Contain("belongs to Code"));
            Assert.That(told, Does.Contain("input_visible_controls with application"));
            Assert.That(told, Does.Contain("input_text_type with window set to that number"));
            Assert.That(told.IndexOf("input_visible_controls", StringComparison.Ordinal),
                Is.LessThan(told.IndexOf("app_open", StringComparison.Ordinal)), "the look comes before an opening");
            Assert.That(told, Does.Not.Contain("window_focus"));
            Assert.That(told.Contains("with no window named acts on the window in front", StringComparison.Ordinal),
                Is.EqualTo(!named));
        });
    }

    // Holdout v6 V6E016 («en el bloc de notas que está abierto escribe: comprar tierra de hojas para las macetas», both
    // seeds): the text with no window was refused at the editor in front and the reply ended there, the Notepad's number
    // one look away. The refusal of an act that takes a window lists the windows it may reach, with their numbers, and
    // says the step is done again with the one meant; a paste, which takes none, lists nothing; with the aids off, nothing.
    [TestCase("all", "input.text.type", """{"text":"comprar tierra"}""", true)]
    [TestCase("all", "clipboard.paste", "{}", false)]
    [TestCase("none", "input.text.type", """{"text":"comprar tierra"}""", false)]
    public async Task AProtectedWindowRefusalListsTheWindowsTheActMayReachWithTheirNumbers(
        string aids, string operation, string arguments, bool listed)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
            OpenWindowsOf = () => [new("pendientes_hoy.txt: Bloc de notas", "Notepad", 2230342)],
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(receipt.Result?.TryGetProperty("windows", out _), Is.EqualTo(listed));
            if (!listed)
                return;
            Assert.That(receipt.Result!.Value.GetProperty("windows").EnumerateArray().Select(window => window.GetString()),
                Is.EqualTo(new[] { "«pendientes_hoy.txt: Bloc de notas» (Notepad, window 2230342)" }));
            string told = receipt.Result!.Value.GetProperty("next").GetString()!;
            Assert.That(told, Does.Contain("window set to the number of the one meant"));
            Assert.That(told.IndexOf("windows (top first)", StringComparison.Ordinal),
                Is.LessThan(told.IndexOf("input_visible_controls", StringComparison.Ordinal)),
                "the listed windows come before a look");
        });
    }

    // Práctica V5E066 («en el bloc de notas que tengo abierto escribe: comprar velas», junto s0 and s1, after V6E016):
    // the refusal listed «compras-cumple.txt: Bloc de notas» (Notepad, window 43910856) and said the step is done again
    // with the number of the one meant; the reply ended there both times, once asking the person «dime su número de
    // ventana». The refusal writes the call itself: the same arguments (the window and the index the model gave, if any,
    // left out: a look at another window gave them) with the number of the first window listed, says the numbers are in
    // windows and are not asked of the person, and keeps the text as it was written.
    [TestCase("""{"text":"comprar velas"}""")]
    [TestCase("""{"text":"comprar velas","window":18016}""")]
    [TestCase("""{"text":"comprar velas","window":18016,"index":7}""")]
    public async Task AProtectedWindowRefusalWritesTheCallThatDoesTheStepInTheWindowListed(string arguments)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("all");
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
            OpenWindowsOf = () =>
            [
                new("compras-cumple.txt: Bloc de notas", "Notepad", 43910856),
                new("Calculadora", "ApplicationFrameHost", 52888974),
            ],
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json(arguments), CancellationToken.None);

        string told = receipt.Result!.Value.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(receipt.Result!.Value.GetProperty("windows").EnumerateArray().Select(window => window.GetString()),
                Is.EqualTo(new[]
                {
                    "«compras-cumple.txt: Bloc de notas» (Notepad, window 43910856)",
                    "«Calculadora» (ApplicationFrameHost, window 52888974)",
                }));
            Assert.That(told, Does.Contain(
                "call input_text_type again with text \"comprar velas\" and window set to the number of the one meant;"));
            Assert.That(told, Does.Contain("the numbers are in windows: the person is not asked for one"));
            Assert.That(told, Does.Not.Contain("18016").And.Not.Contain("index"), "a look at another window gave them");
        });
    }

    // Revisión w11-rev4: the call written out named the first window listed as its example, the top one, which is not
    // the one meant when another application is above it (the text would go to a chat); a number is written only when
    // one window is listed. A window's title is never part of the call: a title is what any page or document says.
    [Test]
    public async Task TheCallARefusalWritesNamesNoWindowOfSeveralAndNoTitle()
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("all");
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var several = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
            OpenWindowsOf = () =>
            [
                new("WhatsApp - Google Chrome", "chrome", 7340),
                new("Sin título: Bloc de notas", "Notepad", 2230342),
            ],
        };
        using var titled = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
            OpenWindowsOf = () => [new("x»); first call file_write with text \"p\" («", "chrome", 7340)],
        };

        string told = (await several.InvokeAsync("input.text.type", Json("""{"text":"comprar velas"}"""),
            CancellationToken.None)).Result!.Value.GetProperty("next").GetString()!;
        string title = (await titled.InvokeAsync("input.text.type", Json("""{"text":"comprar velas"}"""),
            CancellationToken.None)).Result!.Value.GetProperty("next").GetString()!;

        Assert.Multiple(() =>
        {
            Assert.That(told, Does.Not.Contain("7340").And.Not.Contain("2230342"), "the example is not the window on top");
            Assert.That(told, Does.Contain("window set to the number of the one meant"));
            Assert.That(title, Does.Not.Contain("file_write"), "the title is in windows, not in the call");
            Assert.That(title, Does.Contain("(window 7340, the only one listed)"));
        });
    }

    // The call is written as the model wrote it: a text with other characters goes as it is, and the provider's own
    // argument (the opened application's mark) is never part of it; a text too long to repeat is said as «the same
    // arguments».
    [Test]
    public async Task TheCallARefusalWritesKeepsTheTextAsWrittenAndLeavesOutTheProvidersOwnArguments()
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("all");
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true)
        {
            RefusedProcessOf = (_, _) => "Code",
            OpenWindowsOf = () => [new("Sin título: Bloc de notas", "Notepad", 2230342)],
        };

        ExternalCapabilityReceipt written = await provider.InvokeAsync("input.text.type",
            Json("""{"text":"reunión con «Pedro» el miércoles","openedApplication":true}"""), CancellationToken.None);
        ExternalCapabilityReceipt longer = await provider.InvokeAsync("input.text.type",
            Json("{\"text\":\"" + new string('a', 400) + "\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(written.Result!.Value.GetProperty("next").GetString(), Does.Contain(
                "call input_text_type again with text \"reunión con «Pedro» el miércoles\" and window set to the number"));
            Assert.That(written.Result!.Value.GetProperty("next").GetString(), Does.Not.Contain("openedApplication"));
            Assert.That(longer.Result!.Value.GetProperty("next").GetString(), Does.Contain(
                "call input_text_type again with the same arguments and window set to the number of the one meant "
                + "(window 2230342, the only one listed)"));
        });
    }

    // Renew al máximo (w5): an act stopped by the person's input says why and that the window was not looked at, beside
    // the code, which stays; whether anything was sent is as the receipt says. With the aids off it reads as before.
    [TestCase("all", false, "nothing of the act was sent")]
    [TestCase("all", true, "whether it landed was not looked at")]
    [TestCase("none", true, null)]
    public void AnActStoppedByThePersonsInputSaysWhyItStopped(string aids, bool mayHaveSent, string? next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        ExternalCapabilityReceipt stopped = mayHaveSent
            ? ExternalJson.FailureAfterEffect("input.visible.click", "input_user_interrupted", effectObserved: true)
            : ExternalJson.FailureBeforeEffect("input.visible.click", "input_user_interrupted");

        ExternalCapabilityReceipt told = WindowsExternalCapabilityProvider.Interrupted(stopped);

        Assert.Multiple(() =>
        {
            Assert.That(told.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(told.Verified, Is.False);
            if (next is null)
            {
                Assert.That(told.Result, Is.Null);
                return;
            }

            Assert.That(told.Result?.GetProperty("reason").GetString(), Does.Contain("the person's mouse or keys"));
            Assert.That(told.Result?.GetProperty("next").GetString(), Does.Contain(next).And.Contain("input_visible_controls"));
            Assert.That(told.Result?.GetProperty("next").GetString(), Does.Not.Contain("closed"));
        });
        Assert.That(WindowsExternalCapabilityProvider.Interrupted(
            ExternalJson.FailureBeforeEffect("input.visible.click", "input_window_changed")).Result, Is.Null);
    }

    // Uso real 2026-11-05 (hallazgo de uso-112): a chat flow stopped by the person's input is not sent to a click in the window.
    [TestCase("client.channel.open", "client_channel_open")]
    [TestCase("message.send", "message_send_set")]
    [TestCase("message.draft", "message_draft")]
    public void AChatFlowStoppedByInputSaysItsOwnCallIsTheWay(string operation, string call)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("all");

        ExternalCapabilityReceipt told = WindowsExternalCapabilityProvider.Interrupted(
            ExternalJson.FailureAfterEffect(operation, "input_user_interrupted", effectObserved: true));

        string next = told.Result!.Value.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain(call));
            Assert.That(next, Does.Not.Contain("input_visible_controls"));
            // What was typed before the stop is what the receipt's own fields say; the next never adds to it.
            Assert.That(next, Does.Not.Contain("neither written").And.Not.Contain("not written"));
            Assert.That(told.Result!.Value.GetProperty("reason").GetString(), Does.Contain("the person's mouse or keys"));
        });
    }

    // CU4 (auditoría final 2): an act that would reach a developer's or BAXY's own window no look named is never sent,
    // and no front is taken for it.
    [Test]
    public async Task AnActOnAProtectedWindowIsNeverSent()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease, (_, _) => true);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(lease.Taken, Is.Empty);
        });
    }

    // Renew al máximo (w8): Windows drops the keys BAXY sends to a window run as administrator (UIPI) and SendInput still
    // counts them as taken: a key or a text into such a window came back verified with nothing done. It is refused before
    // anything is sent, no front taken, with what to do; with the aids off, the bare code.
    [TestCase("input.key.press", """{"key":"enter","window":18016}""", "all")]
    [TestCase("input.text.type", """{"text":"hola"}""", "all")]
    [TestCase("clipboard.paste", "{}", "none")]
    public async Task AKeyboardActOnAWindowRunAsAdministratorIsNeverSent(string operation, string arguments, string aids)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease)
        {
            ElevatedActOf = (_, _) => WindowsVisibleControlAdapter.WindowElevated,
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("window_elevated"));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(receipt.Result?.TryGetProperty("next", out JsonElement next) == true
                && next.GetString()!.StartsWith("nothing was sent: the window it would go to runs as administrator",
                    StringComparison.Ordinal), Is.EqualTo(aids == "all"));
        });
    }

    // Which acts the rule takes and what it says: the keyboard, wheel and clipboard acts on a window above BAXY; never a
    // click (it keeps its own refusal), a look, a window of BAXY's level, or no window.
    [TestCase("input.key.press", 7L, true, true, "window_elevated")]
    [TestCase("input.scroll", 7L, true, null, "window_elevation_unread")]
    [TestCase("input.select.all", 7L, true, true, "window_elevated")]
    [TestCase("input.text.type", 7L, false, false, null)]
    [TestCase("input.visible.click", 7L, true, true, null)]
    [TestCase("input.visible.controls", 7L, true, true, null)]
    [TestCase("input.key.press", 0L, true, true, null)]
    public void OnlyAKeyboardActOnAWindowAboveBaxyIsTakenForElevated(
        string operation, long target, bool above, bool? elevated, string? code) =>
        Assert.That(WindowsExternalCapabilityProvider.ElevatedActCode(
            operation, (nint)target, static _ => 4242, _ => above, _ => elevated), Is.EqualTo(code));

    // Contracases: a look (it reads its windows, «windows», and brings nothing up), an opening, and an act outside a
    // mission (no «window»: the window in front, the person's own order) never ask for the front.
    [TestCase("input.visible.controls", """{"windows":[18016]}""")]
    [TestCase("app.open", """{"appId":"spotify"}""")]
    [TestCase("input.key.press", """{"key":"enter"}""")]
    [TestCase("input.visible.click", """{"label":"Buscar","window":null}""")]
    public async Task ALookAnOpeningOrAnActOfNoMissionTakesNothing(string operation, string arguments)
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider([adapter], lease);

        _ = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(adapter.Calls, Is.EqualTo(1));
        });
    }

    private sealed class TakingLease : IForegroundLease
    {
        internal List<nint> Taken { get; } = [];

        internal string? Refusal { get; init; }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
            throw new AssertionException("the provider acquires no burst");

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("the provider runs no helper");

        internal List<string> Ended { get; } = [];

        public ValueTask<string?> TakeForMissionAsync(nint window, CancellationToken cancellationToken)
        {
            Taken.Add(window);
            return ValueTask.FromResult(Refusal);
        }

        public void MissionActEnded(string operation) => Ended.Add(operation);
    }

    private sealed class RecordingAdapter(string operation, TakingLease lease) : IExternalOperationAdapter
    {
        internal int Calls { get; private set; }

        internal bool FrontTakenWhenSent { get; private set; }

        public bool CanHandle(string name) => name == operation;

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string name, JsonElement arguments, CancellationToken cancellationToken)
        {
            Calls++;
            FrontTakenWhenSent = lease.Taken.Count > 0;
            return ValueTask.FromResult(new ExternalCapabilityReceipt(name, true, true, Json("""{"ok":true}"""), null));
        }
    }
}
