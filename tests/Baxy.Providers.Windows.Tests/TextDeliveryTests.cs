using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3, point 0, fix 1: a mission's text and keys reach its window without the keyboard or the foreground when
/// its field takes them (UI Automation's SetValue, the edit control's messages, a queued key), and only what no
/// message reaches goes by the keyboard. Every effect goes to fakes; nothing is sent on the desktop.
/// </summary>
[TestFixture]
public sealed class TextDeliveryTests
{
    private static readonly nint Edit = 4661;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(
        FakeDesktopKeyboard keyboard, FakeFieldMessages messages, FakeViewedFields? fields = null) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, messages);

    private static FakeFieldMessages Notepad(string content = "", bool takesReplace = true) =>
        new FakeFieldMessages { TakesReplace = takesReplace }.WithField(Edit, "RichEditD2DPT", content);

    [Test]
    public async Task AnEmptyViewedFieldTakesTheTextBySetValueWithoutTheFront()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"","nativeHwnd":0,"method":"setvalue","delivered":true}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"mouse","window":4660,"index":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("setvalue"));
            Assert.That(fields.Requests.Single(), Is.EqualTo(("4.2.7", "mouse")));
            Assert.That(keyboard.Fronted, Is.Empty, "nothing was brought to the front");
            Assert.That(keyboard.Texts, Is.Empty, "nothing was typed on the keyboard");
        });
    }

    [Test]
    public async Task ASetValueWhoseRereadDiffersIsNotVerified()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"","nativeHwnd":0,"method":"setvalue","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"mouse","window":4660,"index":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // A document, or a field whose text must be kept, is never replaced: the edit control inserts at its caret.
    [Test]
    public async Task AFieldWithTextIsWrittenAtItsCaretByItsEditControl()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = Notepad("Querido Ron: ");
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Document","className":"RichEditD2DPT","nativeHwnd":4661,"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"mañana a las 5","window":4660,"index":0}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("em_replacesel"));
            Assert.That(messages.Content[Edit], Is.EqualTo("Querido Ron: mañana a las 5"));
            Assert.That(keyboard.Fronted, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Práctica V5E023 («agrega al final»: «nos vemos el lunesHola equipo…», and «agregué al final» said): the receipt says
    // where the text read back landed in what the field held, by the caret the control had; with the aid off, nothing.
    [TestCase(0, "Hola equipo.", "nos vemos el lunesHola equipo.",
        "the text went in at the start of the text the field already had, before it")]
    [TestCase(12, "Hola equipo.", "Hola equipo.nos vemos el lunes",
        "the text went in at the end of the text the field already had, after it")]
    [TestCase(4, "Hola equipo.", "Holanos vemos el lunes equipo.",
        "the text went in inside the text the field already had, neither at its start nor at its end")]
    public async Task ATextReadBackInAFieldSaysWhereItLandedInWhatTheFieldHad(
        int caret, string held, string written, string landed)
    {
        foreach (string aids in new[] { Baxy.Providers.Windows.Infrastructure.ModelAids.CaretPlace, "none" })
        {
            using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
            FakeFieldMessages messages = Notepad(held);
            messages.Selected[Edit] = (caret, caret);

            ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), messages).InvokeAsync(
                "input.text.type", Json("""{"text":"nos vemos el lunes","window":4660}"""), CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(messages.Content[Edit], Is.EqualTo(written));
                Assert.That(receipt.Result?.TryGetProperty("landed", out JsonElement said) == true ? said.GetString() : null,
                    Is.EqualTo(aids == "none" ? null : landed), aids);
            });
        }
    }

    // The same fact for a text typed by the keyboard into the focused edit control of the window in front, read back.
    [Test]
    public async Task ATextTypedAndReadBackInTheFocusedEditControlSaysWhereItLanded()
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(
            Baxy.Providers.Windows.Infrastructure.ModelAids.CaretPlace);
        FakeFieldMessages notepad = Notepad("lista: ");
        notepad.Selected[Edit] = (0, 0);
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(4660, 4242, "Sin título: Bloc de notas"),
            FrontProcess = "Notepad",
            EachCharacter = typed => notepad.Content[Edit] = notepad.Content[Edit].Insert(typed, "hola"[typed].ToString()),
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, notepad).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(notepad.Content[Edit], Is.EqualTo("holalista: "));
            Assert.That(receipt.Result?.GetProperty("landed").GetString(),
                Is.EqualTo("the text went in at the start of the text the field already had, before it"));
        });
    }

    // Only what the two reads show: no text before, a selection replaced, a read missing, a text that is not there, or
    // one the reads place in more than one way (typing «a» into «aaa»), and nothing is said.
    [TestCase("ab", "x", "xab", "the text went in at the start of the text the field already had, before it")]
    [TestCase("ab", "c", "abc", "the text went in at the end of the text the field already had, after it")]
    [TestCase("ab", "b", "abb", null)]
    [TestCase("", "hola", "hola", null)]
    [TestCase("chau", "hola", "hola", null)]
    [TestCase(null, "hola", "holachau", null)]
    [TestCase("aaa", "a", "aaaa", null)]
    [TestCase("ab", "x", "ayb", null)]
    public void WhereATextLandedIsSaidOnlyWhenTheReadsPlaceItOneWay(string? was, string text, string now, string? landed) =>
        Assert.That(WindowsTextDelivery.Landed(was, now, text), Is.EqualTo(landed));

    [Test]
    public async Task AnEditControlThatIgnoresTheReplacementTakesQueuedCharacters()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = Notepad(takesReplace: false);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("wm_char"));
            Assert.That(messages.Content[Edit], Is.EqualTo("hola"));
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    [Test]
    public async Task WithoutAFieldTheWindowsOwnFocusTakesTheText()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = Notepad();

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"lista: pan","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("win32_edit_message_reread"));
            Assert.That(messages.Content[Edit], Is.EqualTo("lista: pan"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // A field drawn without a window of its own and without a writable value (a Chromium contenteditable): no
    // message reaches it, the keyboard path takes the text and the receipt says so. r25 review (finding 1): only when
    // the field has the keyboard's focus (the worker's «focused»); without it nothing is sent (ComputerUseTiposUiaTests).
    [Test]
    public async Task AFieldNoMessageReachesFallsToTheKeyboard()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"","nativeHwnd":0,"focused":true,"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(keyboard.Fronted, Is.EqualTo(new nint[] { 4660 }));
            Assert.That(keyboard.Texts.Single(), Is.EqualTo("hola"));
        });
    }

    // Contracase: a field of another window (a view taken of something else) gets nothing, by no path.
    [Test]
    public async Task AFieldOfAnotherWindowsViewGetsNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("""{"ok":true}""") { ViewWindow = 9999 };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, Notepad(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_identity_stale"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(fields.Requests, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // Contracase: an edit control outside the mission's window (another process's) is never written to. The field has
    // the keyboard's focus here, so the mission's window may take it by keyboard (r25 review: never without it).
    [Test]
    public async Task AnEditControlOutsideTheMissionWindowGetsNoMessage()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = Notepad();
        messages.Outside.Add(Edit);
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"Edit","nativeHwnd":4661,"focused":true,"method":"","delivered":false}""");

        _ = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(messages.Content[Edit], Is.Empty, "no message reached the foreign control");
            Assert.That(keyboard.Fronted, Is.EqualTo(new nint[] { 4660 }), "the mission's own window took the keyboard");
        });
    }

    [Test]
    public async Task AWindowThatIsGoneGetsNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        var messages = new FakeFieldMessages { Alive = false };

        ExternalCapabilityReceipt key = await Adapter(keyboard, messages).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);
        ExternalCapabilityReceipt text = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(key.ErrorCode, Is.EqualTo("input_window_not_found"));
            Assert.That(text.ErrorCode, Is.EqualTo("input_window_not_found"));
            Assert.That(key.EffectMayHaveOccurred || text.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Fronted, Is.Empty);
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // hwnds are recycled: a window whose process changed while the characters were queued gets no more of them.
    [Test]
    public async Task QueuedCharactersStopWhenTheWindowsIdentityChanges()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = Notepad(takesReplace: false);
        messages.IdentityChangesAfterChars = 2;

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_changed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(messages.Content[Edit], Is.EqualTo("ho"));
        });
    }

    [TestCase("enter", (ushort)0x0D)]
    [TestCase("tab", (ushort)0x09)]
    [TestCase("arrow_down", (ushort)0x28)]
    public async Task ASingleKeyReachesAClassicControlAsQueuedMessages(string key, ushort virtualKey)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.key.press", Json($$"""{"key":"{{key}}","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("postmessage"));
            Assert.That(messages.Keys.Single(), Is.EqualTo((Edit, virtualKey)));
            Assert.That(keyboard.Fronted, Is.Empty);
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    // Contracases: a chord carries modifiers a message cannot, and a focus drawn by Chromium or XAML ignores queued
    // keys; both go by the keyboard to the mission's window brought to the front.
    [TestCase("ctrl_a", "Edit")]
    [TestCase("enter", "Chrome_RenderWidgetHostHWND")]
    [TestCase("enter", "Windows.UI.Input.InputSite.WindowClass")]
    public async Task WhatNoMessageReachesGoesByTheKeyboard(string key, string focusClass)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, focusClass, string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.key.press", Json($$"""{"key":"{{key}}","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(messages.Keys, Is.Empty);
            Assert.That(keyboard.Fronted, Is.EqualTo(new nint[] { 4660 }));
        });
    }

    [Test]
    public async Task AFieldNamedOutsideAMissionWindowIsRefused()
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, Notepad()).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","index":1}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("desktop_interaction_argument_invalid"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Contracases (adversarial review): EM_REPLACESEL writes into a read-only edit control, so a read-only, password or
    // disabled control gets nothing, by messages or by the keyboard, with or without a field named, and the receipt
    // says nothing happened.
    [TestCase(0x0800L, false, null)]
    [TestCase(0x0020L, false, null)]
    [TestCase(0L, true, null)]
    [TestCase(0x0800L, false, 2)]
    [TestCase(0x0020L, false, 2)]
    public async Task AReadOnlyPasswordOrDisabledEditControlGetsNothing(long style, bool disabled, int? index)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "registro");
        messages.Styles[Edit] = style | 0x0004;
        if (disabled)
            messages.Disabled.Add(Edit);
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"Edit","nativeHwnd":4661,"method":"","delivered":false}""");
        string arguments = index is null
            ? """{"text":"hola","window":4660}"""
            : $$"""{"text":"hola","window":4660,"index":{{index}}}""";

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_writable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(messages.Content[Edit], Is.EqualTo("registro"), "no message wrote into it");
            Assert.That(keyboard.Texts, Is.Empty, "nor did the keyboard");
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // Counter-contracase: the styles an ordinary multi-line edit carries (ES_MULTILINE, ES_AUTOVSCROLL, ES_WANTRETURN,
    // WS_CHILD | WS_VISIBLE | WS_VSCROLL) do not stop it.
    [Test]
    public async Task AnOrdinaryMultilineEditControlStillTakesTheText()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", string.Empty);
        messages.Styles[Edit] = 0x50201044;

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(messages.Content[Edit], Is.EqualTo("hola"));
        });
    }

    // Contracase: a field whose worker answer says read-only, password or disabled (a field without a window of its
    // own, so no style to read) is refused before any effect; the keyboard does not take it instead.
    [TestCase("\"readOnly\":true")]
    [TestCase("\"password\":true")]
    [TestCase("\"enabled\":false")]
    public async Task AViewedFieldThatTakesNoTextIsRefusedWithoutTheKeyboard(string flag)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"","nativeHwnd":0,"method":"","delivered":false,"""
            + flag + "}");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_writable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // Adversarial review: the receipt states the front read before the delivery and after it. A SetValue that brought
    // the mission's window to the front (measured on a XAML search box) is reported and the front goes back to the
    // person's window.
    [Test]
    public async Task AFrontTheDeliveryMovedIsReportedAndGivenBack()
    {
        var keyboard = new FakeDesktopKeyboard { Front = new DesktopForeground(0x9999, 777, "Correo") };
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"method":"setvalue","delivered":true}""")
        {
            OnField = () => keyboard.Now = new DesktopForeground(4660, 4242, "Configuración"),
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"mouse","window":4660,"index":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("foregroundProcessIdBefore").GetInt32(), Is.EqualTo(777));
            Assert.That(receipt.Result?.GetProperty("foregroundProcessIdAfter").GetInt32(), Is.EqualTo(4242));
            Assert.That(receipt.Result?.GetProperty("foregroundTitleBefore").GetString(), Is.EqualTo("Correo"));
            Assert.That(receipt.Result?.GetProperty("frontChanged").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("frontRestored").GetBoolean(), Is.True);
            // Merge of fable/cu-v3-pausa: bringing a window up now takes a lease (wait for a pause, then give back);
            // handing the person's window back is not a lease, so it goes by GiveFront and nothing is fronted.
            Assert.That(keyboard.GivenBack, Is.EqualTo(new nint[] { 0x9999 }), "only the person's window, back to the front");
            Assert.That(keyboard.Fronted, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Contracases: a front that did not move is reported unchanged and nothing is brought anywhere; a front another
    // process took meanwhile (not the mission's) is reported, never fought.
    [TestCase(false)]
    [TestCase(true)]
    public async Task AFrontTheDeliveryDidNotTakeIsLeftAlone(bool anotherTookIt)
    {
        var keyboard = new FakeDesktopKeyboard { Front = new DesktopForeground(0x9999, 777, "Correo") };
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"method":"setvalue","delivered":true}""")
        {
            OnField = () =>
            {
                if (anotherTookIt)
                    keyboard.Now = new DesktopForeground(0x7777, 555, "Chat");
            },
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"mouse","window":4660,"index":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("frontChanged").GetBoolean(), Is.EqualTo(anotherTookIt));
            Assert.That(receipt.Result?.GetProperty("frontRestored").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("foregroundProcessIdAfter").GetInt32(), Is.EqualTo(anotherTookIt ? 555 : 777));
            Assert.That(keyboard.Fronted, Is.Empty);
            Assert.That(keyboard.GivenBack, Is.Empty);
        });
    }

    // Revision 1 of r24b (banco r23, v1): SetValue «Spotify» into a store's search box left the keyboard's focus on
    // another control, and the Enter that followed went there: the search never ran. The key now goes only once UI
    // Automation put the focus on that field and re-read it, and its receipt says where («focusAt»).
    [Test]
    public async Task TheEnterAfterAValueSetWithoutFocusGoesOnlyOnceTheFieldHoldsIt()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"method":"setvalue","delivered":true,"focused":false}""")
        {
            FocusAnswer = """{"ok":true,"error":"","focused":true,"controlId":"4.2.7"}""",
        };
        WindowsDesktopInteractionAdapter adapter = Adapter(keyboard, new FakeFieldMessages(), fields);

        ExternalCapabilityReceipt typed = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"Spotify","window":4660,"index":3}"""), CancellationToken.None);
        ExternalCapabilityReceipt enter = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(typed.Verified, Is.True);
            Assert.That(enter.Verified, Is.True);
            Assert.That(fields.Focuses, Is.EqualTo(new[] { "4.2.7" }));
            Assert.That(enter.Result?.GetProperty("focusAt").GetString(), Is.EqualTo("4.2.7"));
            Assert.That(enter.Result?.GetProperty("authority").GetString(), Is.Not.EqualTo("win32_sendinput_return_count"));
            Assert.That(keyboard.Chords.Single(), Is.EqualTo(new ushort[] { 0x0D }));
        });
    }

    // Contracase: the focus did not reach the field (the worker said no, or did not answer): nothing is pressed, and the
    // focus asked is said as an effect that may have occurred.
    [TestCase("""{"ok":true,"error":"","focused":false}""")]
    [TestCase(null)]
    public async Task TheEnterWhoseFieldDidNotTakeTheFocusIsNotPressed(string? focusAnswer)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"method":"setvalue","delivered":true,"focused":false}""")
        {
            FocusAnswer = focusAnswer,
        };
        WindowsDesktopInteractionAdapter adapter = Adapter(keyboard, new FakeFieldMessages(), fields);

        await adapter.InvokeAsync("input.text.type", Json("""{"text":"Spotify","window":4660,"index":3}"""), CancellationToken.None);
        ExternalCapabilityReceipt enter = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(enter.Verified, Is.False);
            Assert.That(enter.ErrorCode, Is.EqualTo("input_field_not_focused"));
            // Ronda final 17: the focus was asked of the window: it may have moved (an effect), though no key went.
            Assert.That(enter.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    // Contracases: a value set where the focus already was (or a worker that does not say) needs no focus; a key to
    // another window, or after another text, is not held by the earlier field.
    [TestCase(""","focused":true""", 4660, false)]
    [TestCase("", 4660, false)]
    [TestCase(""","focused":false""", 4661, false)]
    [TestCase(""","focused":false""", 4660, true)]
    public async Task AKeyWithoutAFieldWaitingForTheFocusGoesAsBefore(string focused, int keyWindow, bool typedAgain)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            "{\"ok\":true,\"error\":\"\",\"kind\":\"Edit\",\"className\":\"TextBox\",\"nativeHwnd\":0,\"method\":\"setvalue\",\"delivered\":true" + focused + "}");
        WindowsDesktopInteractionAdapter adapter = Adapter(keyboard, new FakeFieldMessages(), fields);

        await adapter.InvokeAsync("input.text.type", Json("""{"text":"Spotify","window":4660,"index":3}"""), CancellationToken.None);
        if (typedAgain)
            await adapter.InvokeAsync("input.text.type", Json("""{"text":"x","window":4660}"""), CancellationToken.None);
        ExternalCapabilityReceipt enter = await adapter.InvokeAsync(
            "input.key.press", Json("{\"key\":\"enter\",\"window\":" + keyWindow + "}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(enter.Verified, Is.True);
            Assert.That(fields.Focuses, Is.Empty);
            Assert.That(enter.Result?.TryGetProperty("focusAt", out _), Is.False);
            Assert.That(keyboard.Chords.Last(), Is.EqualTo(new ushort[] { 0x0D }));
        });
    }

    // Revision 3 of r24b (finding 3a, probe through the bridge): the field was removed or its id went stale, so the
    // focus failed once. Only that key is refused: the focus owed is spent, and the keys after it go as before, in this
    // mission and the next.
    [Test]
    public async Task AFocusThatFailedIsSpentAndTheKeysAfterItGo()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"method":"setvalue","delivered":true,"focused":false}""")
        {
            FocusAnswer = """{"ok":false,"error":"visible_control_identity_stale"}""",
        };
        WindowsDesktopInteractionAdapter adapter = Adapter(keyboard, new FakeFieldMessages(), fields);

        await adapter.InvokeAsync("input.text.type", Json("""{"text":"Spotify","window":4660,"index":3}"""), CancellationToken.None);
        ExternalCapabilityReceipt refused = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);
        var later = new List<ExternalCapabilityReceipt>();
        foreach (string key in new[] { "enter", "escape", "page_down", "tab" })
            later.Add(await adapter.InvokeAsync(
                "input.key.press", Json("{\"key\":\"" + key + "\",\"window\":4660}"), CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("input_field_not_focused"));
            Assert.That(later.Select(receipt => receipt.Verified), Is.All.True);
            Assert.That(later.Select(receipt => receipt.Result?.TryGetProperty("focusAt", out _)), Is.All.False);
            Assert.That(fields.Focuses, Has.Count.EqualTo(1), "only the act right after the value asked for the focus");
            Assert.That(keyboard.Chords, Has.Count.EqualTo(4));
        });
    }

    // Revision 3 of r24b (finding 3b, probe «tardía»): a value set without the focus, then a click on a result, then a
    // page down. The click spent the focus owed: the key goes where the person's view now is, never back to the box.
    // Contracase: the act right after the value (no click in between) still focuses the field.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AClickAfterTheValueVoidsTheFocusOwedToTheBox(bool clicked)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"method":"setvalue","delivered":true,"focused":false}""")
        {
            FocusAnswer = """{"ok":true,"error":"","focused":true,"controlId":"4.2.7"}""",
        };
        WindowsDesktopInteractionAdapter adapter = Adapter(keyboard, new FakeFieldMessages(), fields);

        await adapter.InvokeAsync("input.text.type", Json("""{"text":"Spotify","window":4660,"index":3}"""), CancellationToken.None);
        if (clicked)
            fields.Clicks++;
        ExternalCapabilityReceipt pageDown = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pageDown.Verified, Is.True);
            Assert.That(fields.Focuses, Has.Count.EqualTo(clicked ? 0 : 1));
            Assert.That(pageDown.Result?.TryGetProperty("focusAt", out _), Is.EqualTo(!clicked));
        });
    }

    // Revision 3 of r24b (finding 3): the focus owed lasts one step's time; a key long after (a later mission) is not
    // held by it. Contracase: within that time it is.
    [TestCase(WindowsDesktopInteractionAdapter.PendingFocusLifetimeMilliseconds + 1, 0)]
    [TestCase(WindowsDesktopInteractionAdapter.PendingFocusLifetimeMilliseconds - 1, 1)]
    public async Task TheFocusOwedExpiresAfterAStepsTime(long elapsed, int focuses)
    {
        long now = 1_000;
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"method":"setvalue","delivered":true,"focused":false}""")
        {
            FocusAnswer = """{"ok":true,"error":"","focused":true,"controlId":"4.2.7"}""",
        };
        var adapter = new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages())
        {
            Ticks = () => now,
        };

        await adapter.InvokeAsync("input.text.type", Json("""{"text":"Spotify","window":4660,"index":3}"""), CancellationToken.None);
        now += elapsed;
        ExternalCapabilityReceipt enter = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(enter.Verified, Is.True);
            Assert.That(fields.Focuses, Has.Count.EqualTo(focuses));
        });
    }

    // BAXY Renew (notebook), F004: «abre la calculadora y luego escribe hola en el bloc de notas». The Notepad was opened,
    // the Calculator held the front, and «hola» was typed with no window named: the keys went to the Calculator. The
    // receipt names the window they were sent to and, with no edit control of it to read the text back from, does not
    // say the text was written (its effect stays possible).
    [Test]
    public async Task ATextTypedWithNoWindowIntoAnotherApplicationNamesItAndIsNotVerified()
    {
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(0x5678, 3364, "Calculadora"),
            FrontProcess = "CalculatorApp",
        };
        FakeFieldMessages notepad = Notepad();

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, notepad).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("title").GetString(), Is.EqualTo("Calculadora"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("CalculatorApp"));
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.False);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "hola" }));
            Assert.That(notepad.Content[Edit], Is.Empty, "nothing reached the Notepad");
        });
    }

    // Renew al máximo (w5, F004): with sentTo «Calculadora» the reply still said «no pude comprobar que escribiste hola en
    // el Bloc de notas» and blamed a focus change never tried. With the aid typed_target_next the receipt says, as a
    // sentence, the one window the text went into and that nothing was opened or brought up for it; with
    // BAXY_AYUDAS=none only the facts, as before.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task ATextTypedWithNoWindowSaysTheOneApplicationItWentInto(string aids, bool told)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(0x5678, 3364, "Calculadora"),
            FrontProcess = "CalculatorApp",
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, Notepad()).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        bool hasNext = receipt.Result!.Value.TryGetProperty("next", out JsonElement next);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(hasNext, Is.EqualTo(told));
            if (told)
            {
                Assert.That(next.GetString(), Does.Contain("into the window in front, of Calculadora (CalculatorApp)"));
                Assert.That(next.GetString(), Does.Contain("no other application received it"));
                Assert.That(next.GetString(), Does.Contain("no application was opened or brought to the front"));
                Assert.That(next.GetString(), Does.Contain("it was not read back there"));
                // Holdout v5 (V5E066): how the window of another application is reached, as the one look that gives
                // its number and the text typed again with it.
                Assert.That(next.GetString(), Does.Contain("input_visible_controls with application"));
                Assert.That(next.GetString(), Does.EndWith("input_text_type with window set to that number"));
                Assert.That(next.GetString(), Does.Not.Contain("not written to a file"), "a text not read back is no completed one");
            }
        });
    }

    // The sentence for a text read back says no doubt, and one sent to the application just opened says so; only the
    // one sent to the window in front names the look that reaches another application's window.
    [Test]
    public void TheTypedTargetSentenceFollowsTheReadBackAndTheOpening()
    {
        string read = WindowsDesktopInteractionAdapter.TypedInto("Sin título: Bloc de notas", "Notepad", true, true);
        string opened = WindowsDesktopInteractionAdapter.TypedInto("", "Notepad", false, false);
        Assert.Multiple(() =>
        {
            Assert.That(read, Does.Contain("of Sin título: Bloc de notas (Notepad)"));
            Assert.That(read, Does.Not.Contain("not read back"));
            Assert.That(read, Does.Contain("input_visible_controls with application"));
            Assert.That(opened, Does.Contain("window of Notepad, the application just opened"));
            Assert.That(opened, Does.Not.Contain("brought to the front"));
            Assert.That(opened, Does.EndWith("it was not read back there"));
            Assert.That(opened, Does.Not.Contain("input_visible_controls"));
        });
    }

    // The same text with the Notepad in front: its edit control has the focus, and «hola» is read back there.
    [Test]
    public async Task ATextTypedWithNoWindowIsVerifiedWhenItIsReadBackInTheFocusedEditControl()
    {
        FakeFieldMessages notepad = Notepad("lista: ");
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(4660, 4242, "Sin título: Bloc de notas"),
            FrontProcess = "Notepad",
            EachCharacter = typed => notepad.Content[Edit] += "hola"[typed],
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, notepad).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("win32_sendinput_and_edit_text_reread"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("Notepad"));
        });
    }

    // BAXY Renew al máximo (e2e E017, pc-lote-A-s1): «lista: pilas, cables» typed into a busy Notepad landed as «lista
    // ilas, cables». The editor takes a key only when it gets to it (here: one each time its length is asked), and a
    // key sent while the one before is still queued is lost. Each character waits for the editor to have taken the
    // ones before it, and the read-back for the last: the text lands whole and is read back.
    [Test]
    public async Task ATextTypedIntoABusyEditorWaitsForEachKeyToBeTakenAndIsReadBack()
    {
        const string typed = "lista: pilas, cables";
        FakeFieldMessages notepad = Notepad("hola desde BAXY");
        var queued = new Queue<char>();
        notepad.BeforeLength = field =>
        {
            if (queued.TryDequeue(out char key))
                notepad.Content[field] += key;
        };
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(4660, 4242, "*hola desde BAXY: Bloc de notas"),
            FrontProcess = "Notepad",
            EachSent = key =>
            {
                if (queued.Count == 0)
                    queued.Enqueue(key);
            },
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, notepad).InvokeAsync(
            "input.text.type", Json($$"""{"text":"{{typed}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.True);
            Assert.That(notepad.Content[Edit], Is.EqualTo("hola desde BAXY" + typed));
        });
    }

    // A focused edit control that never takes the keys (they went elsewhere) is waited for once: the rest of the text
    // goes at the keyboard's pace, whole, and it is not read back.
    [Test]
    public async Task AnEditControlThatDoesNotTakeTheKeysIsWaitedForOnlyOnce()
    {
        const string typed = "lista: pilas, cables";
        FakeFieldMessages field = Notepad("otra cosa");
        int lengthReads = 0;
        field.BeforeLength = _ => lengthReads++;
        var keyboard = new FakeDesktopKeyboard { Front = new DesktopForeground(4660, 4242, "Formulario") };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, field).InvokeAsync(
            "input.text.type", Json($$"""{"text":"{{typed}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { typed }));
            Assert.That(lengthReads, Is.LessThan(2 * 61), "one bounded wait, not one per character");
        });
    }

    // The focused edit control's text did not take the keys (they went elsewhere), or it is a password box, whose text
    // is never read: not verified, and nothing of the control's text is in the receipt.
    [TestCase(false)]
    [TestCase(true)]
    public async Task ATextTypedWithNoWindowThatIsNotReadBackIsNotVerified(bool password)
    {
        FakeFieldMessages field = Notepad("secreto");
        if (password)
            field.Styles[Edit] = 0x0020;
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(4660, 4242, "Iniciar sesión"),
            EachCharacter = typed => { if (password) field.Content[Edit] += "hola"[typed]; },
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, field).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("secreto"));
        });
    }

    // A field whose text is longer than the delivery reads: its length matching the insertion proves nothing, so
    // the text is not verified, its effect stays possible, and it is not typed a second time.
    [TestCase(false)]
    [TestCase(true)]
    public async Task ATextInAFieldTooLongToReadIsNotVerified(bool overSelection)
    {
        var keyboard = new FakeDesktopKeyboard();
        string held = new('x', WindowsTextDelivery.ReadableText + 1);
        FakeFieldMessages messages = Notepad(held);
        if (overSelection)
            messages.Selected[Edit] = (0, 4);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(messages.Content[Edit], Is.EqualTo(overSelection ? "hola" + held[4..] : held + "hola"),
                "the text went in once, by EM_REPLACESEL");
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // The same with no window named: the keys reached the focused edit control, whose text is too long to read back.
    [Test]
    public async Task ATextTypedWithNoWindowIntoAFieldTooLongToReadIsNotReadBack()
    {
        FakeFieldMessages notepad = Notepad(new string('x', WindowsTextDelivery.ReadableText + 1));
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(4660, 4242, "Sin título: Bloc de notas"),
            FrontProcess = "Notepad",
            EachCharacter = typed => notepad.Content[Edit] += "hola"[typed],
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, notepad).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.False);
        });
    }

    // FT/proveedores goal (E2): Word's document window is «_WwG», no Win32 edit control, so a text typed into it with no
    // window named was never read back. The paragraph at its caret is read by UI Automation before and after the keys
    // (of the front's own process): the text in it, the paragraph grown by its length, is read back. Word's AutoFormat
    // turned the typed ' into ’ and -- into –: those typographic substitutions are the text typed.
    private static readonly nint WordDocument = 4671;

    private static string Caret(string paragraph, int processId = 4242, bool bounded = false, int selection = 0) =>
        JsonSerializer.Serialize(new
        {
            ok = true,
            error = "",
            processId,
            kind = "Document",
            unit = "paragraph",
            text = paragraph + "\r",
            length = paragraph.Length + 1,
            bounded,
            selectionLength = selection,
        });

    private static (FakeDesktopKeyboard Keyboard, FakeFieldMessages Messages) Word(Action<int>? eachCharacter) =>
        (new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(4660, 4242, "Documento1 - Word"),
            FrontProcess = "WINWORD",
            EachCharacter = eachCharacter,
        }, new FakeFieldMessages().WithField(WordDocument, "_WwG", string.Empty));

    [TestCase("hola mundo", "hola mundo")]
    [TestCase("it's a test -- ok", "it’s a test – ok")]
    [TestCase("dijo \"si\"", "dijo “si”")]
    public async Task ATextTypedWithNoWindowIntoAWordDocumentIsReadBackInItsCaretParagraph(string typed, string written)
    {
        string paragraph = "Querido Juan: ";
        var fields = new FakeViewedFields("{}") { CaretAnswer = () => Caret(paragraph) };
        (FakeDesktopKeyboard keyboard, FakeFieldMessages messages) = Word(index =>
        {
            if (index == typed.Length - 1)
                paragraph += written;
        });

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json(JsonSerializer.Serialize(new { text = typed })), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("readBackBounded").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("win32_sendinput_and_uia_text_reread"));
            Assert.That(fields.CaretRequests, Has.Count.EqualTo(2), "one read before the keys, one after");
            Assert.That(fields.CaretRequests, Is.All.EqualTo(((nint)4660, 4242)), "only the front's own process is asked for");
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("Querido"), "nothing of the paragraph is in the receipt");
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { typed }));
        });
    }

    // FT/proveedores goal (review of receipts): a text for a named window whose keys went by the keyboard is read back
    // where a read-back can be taken (here Word's paragraph at the caret): found, verified; not there, not verified and
    // its effect possible (before, the named window was told verified by the count of keys Windows accepted).
    [TestCase(true)]
    [TestCase(false)]
    public async Task ATextTypedForANamedWindowIsHeldToItsReadBack(bool lands)
    {
        string paragraph = "Querido Juan: ";
        var fields = new FakeViewedFields("{}") { CaretAnswer = () => Caret(paragraph) };
        (FakeDesktopKeyboard keyboard, FakeFieldMessages messages) = Word(index =>
        {
            if (lands && index == "hola mundo".Length - 1)
                paragraph += "hola mundo";
        });

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola mundo","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "hola mundo" }), "the keyboard path took it");
            Assert.That(receipt.Verified, Is.EqualTo(lands), receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.EqualTo(lands));
            if (!lands)
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            }
        });
    }

    // The keys went in but the paragraph at the caret does not hold the text (they went elsewhere, or Word rewrote it
    // beyond quotes and dashes), the paragraph only held it already, the worker answered nothing or failed, a read was
    // cut at its bound, or a selection was there to be replaced: the honest input_text_not_read_back, its effect
    // possible.
    [TestCase("nothing")]
    [TestCase("already")]
    [TestCase("rewritten")]
    [TestCase("silent")]
    [TestCase("failed")]
    [TestCase("bounded")]
    [TestCase("selection")]
    public async Task ATextTypedWithNoWindowIntoAWordDocumentThatIsNotReadBackIsNotVerified(string how)
    {
        string paragraph = how == "already" ? "hola mundo hola mundo" : "Querido Juan: ";
        var fields = new FakeViewedFields("{}")
        {
            CaretAnswer = how switch
            {
                "silent" => null,
                "failed" => () => """{"ok":false,"error":"caret_text_not_found"}""",
                "bounded" => () => Caret(paragraph, bounded: true),
                "selection" => () => Caret(paragraph, selection: 4),
                _ => () => Caret(paragraph),
            },
        };
        (FakeDesktopKeyboard keyboard, FakeFieldMessages messages) = Word(index =>
        {
            if (index == 9 && how is not ("nothing" or "already"))
                paragraph += how == "rewritten" ? "hola Mundo" : "hola mundo";
        });

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola mundo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("win32_sendinput_return_count"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("Querido"));
            if (how == "bounded")
                Assert.That(receipt.Result?.GetProperty("readBackBounded").GetBoolean(), Is.True, "a cut read says it was cut");
        });
    }

    // A worker that answers for a document of another process (the focus moved to another application's window) is not
    // taken: its paragraph, even holding the text, proves nothing about the window the keys were sent to.
    [Test]
    public async Task ACaretParagraphOfAnotherProcessIsNeverTakenForTheFrontsDocument()
    {
        string paragraph = string.Empty;
        var fields = new FakeViewedFields("{}") { CaretAnswer = () => Caret(paragraph, processId: 9999) };
        (FakeDesktopKeyboard keyboard, FakeFieldMessages messages) = Word(index =>
        {
            if (index == 3)
                paragraph = "hola";
        });

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(fields.CaretRequests, Is.All.EqualTo(((nint)4660, 4242)));
            Assert.That(receipt.Result?.TryGetProperty("readBackBounded", out _), Is.False, "no caret mark was taken");
        });
    }

    // A focused edit control keeps its Win32 read-back: UI Automation is asked only when that mark is missing.
    [Test]
    public async Task AnEditControlInFrontIsReadBackByItsMessagesWithoutAskingUiAutomation()
    {
        FakeFieldMessages notepad = Notepad();
        var fields = new FakeViewedFields("{}") { CaretAnswer = () => Caret(string.Empty) };
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(4660, 4242, "Sin título: Bloc de notas"),
            EachCharacter = typed => notepad.Content[Edit] += "hola"[typed],
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, notepad, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("win32_sendinput_and_edit_text_reread"));
            Assert.That(fields.CaretRequests, Is.Empty);
        });
    }

    [TestCase("", "hola", "hola", true)]
    [TestCase("a ", "it's", "a it’s", true)]
    [TestCase("", "x -- y", "x — y", true)]
    [TestCase("", "\"si\"", "«si»", true)]
    // Word's AutoCorrect capital on a sentence's first letter is the text typed (measured live); any other change is not.
    [TestCase("", "hola mundo", "Hola mundo", true)]
    [TestCase("", "hola mundo", "hola Mundo", false)]
    [TestCase("", "hola mundo", "Hola Mundo", false)]
    [TestCase("hola", "hola", "hola", false)]
    [TestCase("hola", "hola", "holaX", false)]
    [TestCase("hola", "hola", "holahola", true)]
    [TestCase("", "", "", false)]
    public void TheCaretParagraphHoldsTheTextOnlyThroughQuoteAndDashSubstitutions(
        string before, string typed, string after, bool holds) =>
        Assert.That(WindowsTextDelivery.CaretHolds(
            new CaretText(before + "\r", "paragraph", false, 0), new CaretText(after + "\r", "paragraph", false, 0), typed),
            Is.EqualTo(holds));

    [Test]
    public void TheCaretParagraphIsNotComparedAcrossUnits() =>
        Assert.That(WindowsTextDelivery.CaretHolds(
            new CaretText("", "paragraph", false, 0), new CaretText("hola", "line", false, 0), "hola"), Is.False);

    // The worker's «textcaret» only reads: it is not run under the front keeper, never falls back to the window in
    // front, stops its walk at the first element of another process, refuses a password and never reads a whole
    // document (only the caret's paragraph or line, bounded and said so).
    [Test]
    public void TheWorkersCaretReadStaysInTheWindowsProcessAndReadsOnlyTheCaretParagraph()
    {
        string path = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(path), "the worker script is copied next to the tests");
        string script = File.ReadAllText(path, System.Text.Encoding.UTF8);
        int at = script.IndexOf("function Do-TextCaret(", StringComparison.Ordinal);
        Assert.That(at, Is.GreaterThanOrEqualTo(0));
        string body = script[at..script.IndexOf("\nfunction ", at + 1, StringComparison.Ordinal)];

        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Contain("elseif($cmd -eq 'textcaret'){ Send-Line (Do-TextCaret $request) }"));
            Assert.That(body, Does.Contain("Get-Root ([long]$request.hwnd)").And.Not.Contain("-Front"));
            Assert.That(body, Does.Contain("if($nodeProcess -ne $process){ break }"));
            Assert.That(body, Does.Contain("$owner -ne $process"));
            Assert.That(body, Does.Contain("IsPassword"));
            Assert.That(body, Does.Contain("TextUnit]::Paragraph").And.Contain("TextUnit]::Line"));
            Assert.That(body, Does.Not.Contain("DocumentRange").And.Not.Contain("GetText(-1)"));
            Assert.That(body, Does.Contain("bounded=$bounded"));
        });
    }

    // Práctica V5E023: the view's caret of its focused text (Get-CaretPlace) only compares the selection with the whole
    // text, reads at most a character before it and three after, is asked only of a focused edit or document with a
    // value read (never a password's), and is said only when read.
    [Test]
    public void TheViewsCaretIsReadByComparingItsSelectionWithTheWholeTextOnly()
    {
        string path = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(path), "the worker script is copied next to the tests");
        string script = File.ReadAllText(path, System.Text.Encoding.UTF8);
        int at = script.IndexOf("function Get-CaretPlace(", StringComparison.Ordinal);
        Assert.That(at, Is.GreaterThanOrEqualTo(0));
        string body = script[at..script.IndexOf("\nfunction ", at + 1, StringComparison.Ordinal)];

        Assert.Multiple(() =>
        {
            Assert.That(body, Does.Contain("GetSelection()").And.Contain("CompareEndpoints").And.Contain("MoveEndpointByRange"));
            Assert.That(body, Does.Contain("GetText(1)").And.Contain("GetText(3)").And.Not.Contain("GetText(-1)"));
            Assert.That(body, Does.Not.Contain("SetFocus").And.Not.Contain(".Select(").And.Not.Contain("ScrollIntoView"));
            Assert.That(script, Does.Contain(
                "if(($focused.kind -eq 'Edit' -or $focused.kind -eq 'Document') -and -not [string]::IsNullOrEmpty([string]$focused.value)){"));
            Assert.That(script, Does.Contain(
                "if($caret.Length -gt 0){ $focusedOut | Add-Member -NotePropertyName caret -NotePropertyValue $caret }"));
        });
    }

    [TestCase("Edit", true)]
    [TestCase("RichEditD2DPT", true)]
    [TestCase("RICHEDIT50W", true)]
    [TestCase("WindowsForms10.EDIT.app.0.141b42a_r6_ad1", true)]
    [TestCase("Chrome_RenderWidgetHostHWND", false)]
    [TestCase("Windows.UI.Core.CoreWindow", false)]
    [TestCase("Button", false)]
    [TestCase("", false)]
    public void TheEditControlsAreTheWin32EditClasses(string className, bool expected) =>
        Assert.That(WindowsTextDelivery.IsEditClass(className), Is.EqualTo(expected));

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }
}

/// <summary>The fields of a last view of window 4660: index → identity, and the worker's scripted «field» answer.</summary>
internal sealed class FakeViewedFields(string answer) : IViewedFields
{
    internal nint ViewWindow { get; init; } = 4660;

    internal List<(string ControlId, string? Text)> Requests { get; } = [];

    internal List<bool> Replaces { get; } = [];

    // What happens on the desktop while the worker sets the value (the front moving, measured on a XAML search box).
    internal Action? OnField { get; init; }

    public bool TryViewedField(int index, out nint window, out string controlId)
    {
        window = ViewWindow;
        controlId = index switch { 3 => "4.2.7", _ => "4.2." + index };
        return true;
    }

    public ValueTask<JsonDocument?> FieldAsync(
        nint window, string controlId, string? text, bool replace, CancellationToken cancellationToken)
    {
        Requests.Add((controlId, text));
        Replaces.Add(replace);
        OnField?.Invoke();
        return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));
    }

    // The entries asked for by pattern («entry»), apart from the texts written.
    internal List<(string ControlId, string Text)> Entries { get; } = [];

    public ValueTask<JsonDocument?> EntryAsync(nint window, string controlId, string text, CancellationToken cancellationToken)
    {
        Entries.Add((controlId, text));
        return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));
    }

    // Revision 1 of r24b: the worker's «focus» answer (null: it does not answer) and the fields it was asked to focus.
    internal string? FocusAnswer { get; init; }

    internal List<string> Focuses { get; } = [];

    // Revision 3 of r24b: the clicks the visible controls' adapter made (a test counts one by hand).
    public long Clicks { get; set; }

    public ValueTask<JsonDocument?> FocusAsync(nint window, string controlId, CancellationToken cancellationToken)
    {
        Focuses.Add(controlId);
        return ValueTask.FromResult(FocusAnswer is null ? null : JsonDocument.Parse(FocusAnswer));
    }

    // FT/proveedores goal (E2): the worker's «textcaret» answer, read anew each time (null: it does not answer), and the
    // windows and processes it was asked to read.
    internal Func<string>? CaretAnswer { get; init; }

    internal List<(nint Window, int ProcessId)> CaretRequests { get; } = [];

    public ValueTask<JsonDocument?> CaretTextAsync(nint window, int processId, int maximum, CancellationToken cancellationToken)
    {
        CaretRequests.Add((window, processId));
        return ValueTask.FromResult(CaretAnswer is null ? null : JsonDocument.Parse(CaretAnswer()));
    }
}

/// <summary>Window 4660 of process 4242 with its child controls, their class and text, as window messages see them.</summary>
internal sealed class FakeFieldMessages : IFieldMessages
{
    private readonly Dictionary<nint, string> _classes = [];
    private int _chars;

    internal bool Alive { get; init; } = true;

    internal bool TakesReplace { get; init; } = true;

    // Whether EM_SETSEL selects the whole text (a control that ignores it keeps its caret at the end).
    internal bool TakesSelectAll { get; init; } = true;

    private readonly HashSet<nint> _allSelected = [];

    internal int? IdentityChangesAfterChars { get; set; }

    internal Dictionary<nint, string> Content { get; } = [];

    // A selection the control holds (absent: the caret at the end of its text), replaced by EM_REPLACESEL.
    internal Dictionary<nint, (int Start, int End)> Selected { get; } = [];

    internal HashSet<nint> Outside { get; } = [];

    // GWL_STYLE by control (0 when absent) and the controls that are disabled.
    internal Dictionary<nint, long> Styles { get; } = [];

    internal HashSet<nint> Disabled { get; } = [];

    internal List<(nint Field, ushort Key)> Keys { get; } = [];

    internal nint Focus { get; private set; }

    internal FakeFieldMessages WithField(nint hwnd, string className, string content)
    {
        _classes[hwnd] = className;
        Content[hwnd] = content;
        Focus = hwnd;
        return this;
    }

    public WindowIdentity Identity(nint window) =>
        !Alive ? new WindowIdentity(window, 0, 0)
        : IdentityChangesAfterChars is int limit && _chars >= limit ? new WindowIdentity(window, 4243, 99)
        : new WindowIdentity(window, 4242, 7);

    public bool Belongs(nint window, nint field) => window == 4660 && _classes.ContainsKey(field) && !Outside.Contains(field);

    public string ClassName(nint hwnd) => _classes.GetValueOrDefault(hwnd, string.Empty);

    public long Style(nint hwnd) => Styles.GetValueOrDefault(hwnd);

    public bool IsEnabled(nint hwnd) => !Disabled.Contains(hwnd);

    // Whether the window's GUI thread reports its focus (a window opened behind may report none).
    internal bool ReportsFocus { get; init; } = true;

    public nint FocusOf(nint window) => ReportsFocus && Belongs(window, Focus) ? Focus : 0;

    public nint SoleEditOf(nint window)
    {
        nint[] edits = _classes.Keys
            .Where(hwnd => Belongs(window, hwnd) && WindowsTextDelivery.IsEditClass(_classes[hwnd]) && IsEnabled(hwnd))
            .ToArray();
        return edits.Length == 1 ? edits[0] : 0;
    }

    // Called before each WM_GETTEXTLENGTH is answered (a busy editor takes a key it had queued meanwhile).
    internal Action<nint>? BeforeLength { get; set; }

    public int TextLength(nint hwnd)
    {
        BeforeLength?.Invoke(hwnd);
        return Content.TryGetValue(hwnd, out string? text) ? text.Length : -1;
    }

    public string? Text(nint hwnd, int length) => Content.GetValueOrDefault(hwnd);

    public (int Start, int End)? Selection(nint hwnd) =>
        !Content.TryGetValue(hwnd, out string? text) ? null
        : _allSelected.Contains(hwnd) ? (0, text.Length)
        : Selected.TryGetValue(hwnd, out (int Start, int End) range) ? range
        : (text.Length, text.Length);

    public bool SelectAll(nint hwnd)
    {
        if (TakesSelectAll && Content.ContainsKey(hwnd))
            _allSelected.Add(hwnd);
        return true;
    }

    public bool ReplaceSelection(nint hwnd, string text)
    {
        if (TakesReplace && Content.TryGetValue(hwnd, out string? content))
        {
            Content[hwnd] = _allSelected.Remove(hwnd) ? text
                : Selected.Remove(hwnd, out (int Start, int End) range) ? content[..range.Start] + text + content[range.End..]
                : content + text;
        }

        return true;
    }

    public bool PostChar(nint hwnd, char character)
    {
        if (_allSelected.Remove(hwnd))
            Content[hwnd] = string.Empty;
        Content[hwnd] += character;
        _chars++;
        return true;
    }

    public int PostKey(nint hwnd, ushort virtualKey)
    {
        Keys.Add((hwnd, virtualKey));
        return 2;
    }

    public ValueTask SettleAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;
}
