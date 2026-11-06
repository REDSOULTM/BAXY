using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-108 (campos), from the comparison with agent-desktop: what the worker reads of a field and what the receipt says
/// when a value does not match. The worker's functions run on described elements (no window is read or touched); the same
/// behaviours on real controls are in <see cref="CamposLiveCheck"/>.
/// </summary>
[TestFixture]
public sealed class CamposUiaTests
{
    private const nint Edit = 4661;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(FakeDesktopKeyboard keyboard, FakeFieldMessages messages, FakeViewedFields? fields = null) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, messages);

    // C10: a format character inside a name. PowerShell's -ceq compares by culture and already ignores the direction marks,
    // not U+200B; the fold compares them all out, whichever comparer runs after it. Contracases: other letters stay other.
    [TestCase("‎Guardar‏", "Guardar", true)]
    [TestCase("Guardar", "‪Guardar‬", true)]
    [TestCase("⁦Guardar⁩", "guardar", true)]
    [TestCase("؜Guardar", "Guardar", true)]
    [TestCase("Guar​dar", "Guardar", true)]
    [TestCase("Guardar", "Guardarr", false)]
    [TestCase("‎Guardar", "Abrir", false)]
    public void ADirectionMarkDoesNotChangeWhichNameItIs(string name, string label, bool same)
    {
        JsonElement answer = WorkerFunctions.Run(["Test-NameMatch", "Get-LabelFolded", "Format-Name", "Get-Cut"], $$"""
            $name=$env:BAXY_CASE_NAME; $label=$env:BAXY_CASE_LABEL
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject ([bool](Test-NameMatch $name @($label)))))
            """.Replace("$env:BAXY_CASE_NAME", Literal(name), StringComparison.Ordinal)
            .Replace("$env:BAXY_CASE_LABEL", Literal(label), StringComparison.Ordinal));
        Assert.That(answer.GetBoolean(), Is.EqualTo(same));
    }

    [Test]
    public void ANameIsShownWithoutItsDirectionMarksAndKeepsItsJoiner()
    {
        string joined = "Dev \U0001F469‍\U0001F4BB";
        JsonElement answer = WorkerFunctions.Run(["Format-Name", "Get-Cut"], $$"""
            $values=@((Format-Name {{Literal("‎Guardar‏")}}), (Format-Name {{Literal("‪Cerrar ⁦ya⁩‬")}}), (Format-Name {{Literal(joined)}}), (Format-Name {{Literal("‎")}}))
            [Console]::Out.Write((ConvertTo-Json -Compress $values))
            """);
        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[] { "Guardar", "Cerrar ya", joined, string.Empty }));
    }

    [TestCase("‎Guardar‏", "Guardar")]
    [TestCase("Guar​dar", "guardar")]
    public void TheRecognizedTextFoldsWithoutItsFormatCharacters(string shown, string label) =>
        Assert.That(WindowsVisibleOcrLocator.Fold(shown), Is.EqualTo(WindowsVisibleOcrLocator.Fold(label)));

    [Test]
    public void TheRecognizedTextKeepsAJoiner() =>
        Assert.That(WindowsVisibleOcrLocator.Fold("a‍b"), Is.Not.EqualTo(WindowsVisibleOcrLocator.Fold("ab")));

    // C7, measured on a real RICHEDIT50W (CamposLiveCheck): its value ends in one paragraph mark that is no content («\r»
    // emptied, «hola\r» written). agent-desktop: crates/windows/src/tree/properties/element_properties.rs:215-252, one final
    // mark, RichEdit classes only. Contracases: a plain edit control keeps it, and only one goes.
    [TestCase("RICHEDIT50W", "hola\r", "hola")]
    [TestCase("RICHEDIT50W", "\r", "")]
    [TestCase("RichEdit20W", "a\r\nb\r\r", "a\r\nb\r")]
    [TestCase("WindowsForms10.RichEdit20W.app.0.2bf8098_r6_ad1", "hola\r", "hola")]
    [TestCase("RICHEDIT50W", "hola", "hola")]
    [TestCase("Edit", "hola\r", "hola\r")]
    [TestCase("", "hola\r", "hola\r")]
    public void ARichEditsFinalMarkIsNotItsText(string className, string value, string read)
    {
        JsonElement answer = WorkerFunctions.Run(["Get-FieldText", "Get-PlainValue"], FieldNode + $$"""
            $node=(Node {{Literal(value)}} $null '' {{Literal(className)}})
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject ([string](Get-FieldText $node 'Edit' 64).text)))
            """);
        Assert.That(answer.GetString(), Is.EqualTo(read));
    }

    // C8, measured on Edge with a page of the test's own (CamposChromiumLiveCheck): an empty contenteditable (a Group with
    // no value) answers its document range with its accessible name, so it read as a field holding text. agent-desktop
    // PR #400. Contracases: a field that holds other text, and a value, which is read as it is. A field that really holds
    // its own name reads as empty: nothing tells the two apart, and that only makes an Enter not ask.
    [TestCase("Group", "Escribe aqui", "Escribe aqui", 64, "")]
    [TestCase("Edit", "Escribe aqui", "Escribe aqui", 64, "")]
    [TestCase("Group", "hola", "Escribe aqui", 64, "hola")]
    [TestCase("Group", "\n", "Escribe aqui", 64, "\n")]
    [TestCase("Group", "hola", "", 64, "hola")]
    [TestCase("Group", "012345678", "0123456789abc", 8, "")]
    public void AnEmptyRichFieldIsNotItsOwnName(string kind, string text, string name, int max, string read)
    {
        JsonElement answer = WorkerFunctions.Run(["Get-FieldText", "Get-PlainValue"], FieldNode + $$"""
            $node=(Node $null {{Literal(text)}} {{Literal(name)}} '')
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject ([string](Get-FieldText $node {{Literal(kind)}} {{max}}).text)))
            """);
        Assert.That(answer.GetString(), Is.EqualTo(read));
    }

    // Review of uso-108, item 1: on a dead element the value's getter raises, PowerShell swallows it and [string] of the null
    // was «», so «no read» looked like «the field is empty», and after a SetValue that raised on an empty field, «refused».
    [Test]
    public void AReadThatGaveNothingIsNoReadNotAnEmptyValue()
    {
        JsonElement answer = WorkerFunctions.Run(["Wait-ValueSet", "Get-ValueRead", "Get-PlainValue"], """
            Add-Type -TypeDefinition @'
            public class BaxyDead { public string Value { get { throw new System.InvalidOperationException("gone"); } } }
            public class BaxyLive { public string Value { get { return ""; } } }
            '@
            $dead=[pscustomobject]@{ Current=(New-Object BaxyDead) }
            $live=[pscustomobject]@{ Current=(New-Object BaxyLive) }
            $results=@(
              ($null -eq (Wait-ValueSet { Get-ValueRead $dead '' } 'hola' 40)),
              ($null -eq (Wait-ValueSet { Get-ValueRead $live '' } 'hola' 40)),
              ((Wait-ValueSet { Get-ValueRead $live '' } '' 40) -ceq ''))
            [Console]::Out.Write((ConvertTo-Json -Compress $results))
            """);
        Assert.That(answer.EnumerateArray().Select(item => item.GetBoolean()), Is.EqualTo(new[] { true, false, true }));
    }

    // Review of uso-108, item 2 (a, b): a field whose text lives in child elements (role=textbox in Chromium) has no window and
    // no value route. Empty, the keyboard writes it: with the focus it has, or with the focus UI Automation puts in it,
    // read again, and a replacement of nothing is that same insertion.
    private const string RichEmpty = """{"ok":true,"error":"","kind":"Edit","className":"","nativeHwnd":0,"enabled":true,"readOnly":false,"password":false,"valueLength":0,"selected":false,"editPending":false,"method":"","delivered":false,"textInChildren":true,"focused":false}""";

    [TestCase(false)]
    [TestCase(true)]
    public async Task AnEmptyRichFieldIsFocusedAndTyped(bool replace)
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RichEmpty) { FocusAnswer = """{"ok":true,"focused":true}""" };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json($$"""{"text":"hola","window":4660,"index":0,"replace":{{(replace ? "true" : "false")}}}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_field_not_reachable"));
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_field_not_replaceable"));
            Assert.That(fields.Focuses, Has.Count.EqualTo(1), "the focus was asked");
            Assert.That(string.Concat(keyboard.Texts), Is.EqualTo("hola"));
        });
    }

    [Test]
    public async Task AnEmptyFieldWithTheFocusIsReplacedAsAnInsertion()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RichEmpty.Replace("\"focused\":false", "\"focused\":true", StringComparison.Ordinal));
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0,"replace":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_field_not_replaceable"));
            Assert.That(fields.Focuses, Is.Empty, "it had it");
            Assert.That(string.Concat(keyboard.Texts), Is.EqualTo("hola"));
        });
    }

    // Contracase: the focus not taken: nothing goes to wherever it is. The focus was asked of the window: an effect either way.
    [Test]
    public async Task ARichFieldThatDoesNotTakeTheFocusGetsNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RichEmpty) { FocusAnswer = """{"ok":true,"focused":false}""" };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_focused"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Contracases: a rich field that holds text (where the caret is, nothing says), and a replacement of text, stay refused; so
    // does an empty field with no focus and no sign that its text lives in children (the existing rule).
    [TestCase("\"valueLength\":5,\"textInChildren\":true,\"focused\":false", false, "input_field_not_reachable")]
    [TestCase("\"valueLength\":5,\"textInChildren\":true,\"focused\":true", true, "input_field_not_replaceable")]
    [TestCase("\"valueLength\":0,\"focused\":false", true, "input_field_not_replaceable")]
    [TestCase("\"valueLength\":0,\"focused\":true,\"kind\":\"Document\"", true, "input_field_not_replaceable")]
    public async Task WhatWasRefusedStaysRefused(string facts, bool replace, string code)
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields($$"""{"ok":true,"error":"","className":"","nativeHwnd":0,"enabled":true,"method":"","delivered":false,{{facts}}{{(facts.Contains("kind", StringComparison.Ordinal) ? "" : ",\"kind\":\"Edit\"")}}}""");
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json($$"""{"text":"hola","window":4660,"index":0,"replace":{{(replace ? "true" : "false")}}}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Opera GX 138 (measured on an own instance, base 0 of 12): its address bar's SetValue raises E_FAIL and writes nothing, so
    // a replacement was refused where the keyboard works: focus by UI Automation, the whole text selected and read back,
    // keys, and the value read must be the text whole, not merely hold it.
    private const string RefusedHolding = """{"ok":false,"error":"field_setvalue_refused","kind":"Edit","className":"","nativeHwnd":0,"enabled":true,"readOnly":false,"password":false,"valueLength":12,"selected":false,"editPending":false,"method":"","delivered":false,"focused":false}""";

    private static string ValueRead(string text) =>
        JsonSerializer.Serialize(new { ok = true, kind = "Edit", id = "1", unit = "value", text, length = text.Length, bounded = false });

    [Test]
    public async Task AValueThatRefusesSetValueIsReplacedByTheKeyboard()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RefusedHolding) { FocusAnswer = """{"ok":true,"focused":true}""", SelectsFocusedText = true, ValueAnswer = () => ValueRead("nuevo") };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"nuevo","window":4660,"index":0,"replace":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(fields.Focuses, Has.Count.EqualTo(1));
            Assert.That(fields.FocusSelections, Has.Count.EqualTo(1));
            Assert.That(string.Concat(keyboard.Texts), Is.EqualTo("nuevo"));
        });
    }

    // Contracase: what stayed is not the text (an old part left, an address completed by the field): not verified, and said.
    [Test]
    public async Task AReplacementThatLeavesAnythingElseIsNotVerified()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RefusedHolding) { FocusAnswer = """{"ok":true,"focused":true}""", SelectsFocusedText = true, ValueAnswer = () => ValueRead("nuevo y viejo") };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"nuevo","window":4660,"index":0,"replace":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(receipt.Result?.GetProperty("fieldNow").GetString(), Is.EqualTo("nuevo y viejo"));
        });
    }

    // Contracases: the whole text not selected, or the focus not taken: not one key.
    [TestCase(true, false, "input_field_not_replaceable")]
    [TestCase(false, true, "input_field_not_focused")]
    public async Task WithoutTheFocusAndTheWholeSelectionNothingIsTyped(bool focus, bool select, string code)
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RefusedHolding) { FocusAnswer = focus ? """{"ok":true,"focused":true}""" : """{"ok":true,"focused":false}""", SelectsFocusedText = select };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"nuevo","window":4660,"index":0,"replace":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Review of uso-108, item 3: an empty field written and erased through SetValue was touched: a failure after it cannot say
    // nothing happened.
    [Test]
    public async Task AFieldWrittenAndErasedIsNotToldUntouched()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RichEmpty.Replace("\"focused\":false", "\"erased\":true,\"focused\":false", StringComparison.Ordinal))
        {
            FocusAnswer = """{"ok":false,"error":"visible_control_identity_stale"}""",
        };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0}"""), CancellationToken.None);
        Assert.That(receipt.EffectMayHaveOccurred, Is.True);
    }

    // Review of uso-108, item 2 (c, d). At the keyboard's pace, with a timer of 1 ms (36 ms measured), what fits is the budget
    // over 37. A longer text on a Chromium surface goes at a faster pace, measured whole; anywhere else it is refused before
    // its first key.
    [Test]
    public void WhatFitsIsMeasuredAtThePaceTheTimerGives() =>
        Assert.That(WindowsDesktopInteractionAdapter.TypingBudgetMs / WindowsDesktopInteractionAdapter.TypedCharacterMs, Is.EqualTo(1891));

    [Test]
    public async Task ALongTextForARichFieldGoesAtTheSurfacesPace()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RichEmpty) { FocusAnswer = """{"ok":true,"focused":true}""" };
        string text = new('a', 4000);
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json($$"""{"text":"{{text}}","window":4660,"index":0}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_text_too_long_to_type"));
            Assert.That(keyboard.Paces, Is.EqualTo(new[] { WindowsDesktopKeyboard.SurfacePace }));
            Assert.That(string.Concat(keyboard.Texts), Is.EqualTo(text));
        });
    }

    // Contracases: a text that fits keeps the keyboard's pace, on any field.
    [Test]
    public async Task ATextThatFitsKeepsTheKeyboardsPace()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(4660);
        var fields = new FakeViewedFields(RichEmpty) { FocusAnswer = """{"ok":true,"focused":true}""" };
        await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0}"""), CancellationToken.None);
        Assert.That(keyboard.Paces, Is.Empty.Or.All.EqualTo(0));
    }

    // C8: what that false text did to the keyboard's read-back: the name before, «hola» after, never grew by the text.
    [TestCase("", "hola", true)]
    [TestCase("Escribe aqui", "hola", false)]
    public void AnEmptyFieldReadAsEmptyCanBeSeenToTakeTheText(string before, string after, bool holds) =>
        Assert.That(WindowsTextDelivery.CaretHolds(new CaretText(before, "value", false, 0), new CaretText(after, "value", false, 0), "hola"), Is.EqualTo(holds));

    // A11: a field whose IsPassword could not be read is not known to be no password: its value is not read. agent-desktop:
    // crates/windows/src/tree/properties/element_properties.rs:38-44. Measured here: PowerShell swallows what a property getter
    // raises, so the old catch never ran and the read gave a false. Contracases: a field that says it is none, read as ever.
    [Test]
    public void AFieldNotKnownToBeNoPasswordIsNotRead()
    {
        JsonElement answer = WorkerFunctions.Run(["Test-HeldText", "Test-MaybePassword", "Get-FieldText", "Get-PlainValue"], """
            Add-Type -TypeDefinition @'
            public class BaxyRaises {
              public bool? Says;
              public object ControlType { get { return new BaxyKind(); } }
              public string ClassName { get { return ""; } }
              public string Name { get { return ""; } }
              public bool IsPassword { get { if (Says == null) throw new System.InvalidOperationException("not read"); return Says.Value; } }
            }
            public class BaxyKind { public string ProgrammaticName { get { return "ControlType.Edit"; } } }
            '@
            $script:reads=0
            function Described($password){
              $current=New-Object BaxyRaises; $current.Says=$password
              $field=[pscustomobject]@{ Current=$current }
              $field | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value {
                param($which,[ref]$out)
                if($which -ne [System.Windows.Automation.ValuePattern]::Pattern){ return $false }
                $value=[pscustomobject]@{ IsReadOnly=$false }
                $value | Add-Member -MemberType ScriptProperty -Name Value -Value { $script:reads++; 'clave' }
                $out.Value=[pscustomobject]@{ Current=$value }; return $true
              }
              return $field
            }
            $results=@()
            foreach($password in @($null,$true,$false)){
              $script:reads=0
              $held=[bool](Test-HeldText @(Described $password))
              $results+=@{ held=$held; reads=$script:reads }
            }
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject $results))
            """);
        Assert.Multiple(() =>
        {
            Assert.That(answer[0].GetProperty("reads").GetInt32(), Is.Zero, "the read failed: not read");
            Assert.That(answer[0].GetProperty("held").GetBoolean(), Is.False);
            Assert.That(answer[1].GetProperty("reads").GetInt32(), Is.Zero, "a password: not read");
            Assert.That(answer[2].GetProperty("reads").GetInt32(), Is.GreaterThan(0), "no password: read");
            Assert.That(answer[2].GetProperty("held").GetBoolean(), Is.True);
        });
    }

    // agent-desktop PR #565: a read-back that touched the value once is not one that held; a value the application took and
    // then put back is told as written otherwise. Contracases: one that stays, and one that shows late (r2 M3).
    [Test]
    public void AValueThatGoesBackDidNotHold()
    {
        JsonElement answer = WorkerFunctions.Run(["Wait-ValueSet"], """
            function Sequence([string[]]$seen){
              $state=@{ n=0 }
              return { $at=[Math]::Min($state.n,$seen.Count-1); $state.n++; $seen[$at] }.GetNewClosure()
            }
            $results=@(
              (Wait-ValueSet (Sequence @('hola','viejo')) 'hola' 300),
              (Wait-ValueSet (Sequence @('hola')) 'hola' 300),
              (Wait-ValueSet (Sequence @('viejo','hola')) 'hola' 300),
              (Wait-ValueSet (Sequence @('viejo','h','hola')) 'hola' 300))
            $watch=[System.Diagnostics.Stopwatch]::StartNew()
            $null=Wait-ValueSet (Sequence @('hola')) 'hola' 300
            $results+=[string]($watch.ElapsedMilliseconds -ge 90 -and $watch.ElapsedMilliseconds -lt 400)
            [Console]::Out.Write((ConvertTo-Json -Compress $results))
            """);
        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "viejo", // taken, then put back
            "hola",  // held
            "hola",  // late, then held
            "hola",  // old, a part, then the whole (agent-desktop #190: never decided on the first differing read)
            "True",  // holding costs about 100 ms
        }));
    }

    // B12: what stayed in the field when a value does not match. agent-desktop #190, four outcomes: equal is verified; equal
    // to before is unwritten (fieldUnchanged); anything else is what it holds now (fieldNow); no read says nothing.
    [TestCase("""{"ok":true,"kind":"Edit","className":"","method":"setvalue","delivered":false,"fieldUnchanged":true}""", "fieldUnchanged", "True")]
    [TestCase("""{"ok":true,"kind":"Edit","className":"","method":"setvalue","delivered":false,"fieldNow":"3,00 cm"}""", "fieldNow", "3,00 cm")]
    public async Task AValueThatDoesNotMatchSaysWhatStayed(string worker, string property, string shown)
    {
        ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), new FakeFieldMessages(), new FakeViewedFields(worker)).InvokeAsync(
            "input.text.type", Json("""{"text":"3","window":4660,"index":0}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty(property).ToString(), Is.EqualTo(shown));
        });
    }

    // Review of uso-108: the check of the window in front may wait seconds; a person who went to another window meanwhile
    // does not get the keys in it, unasked. The control: the front stays, and the key goes.
    [TestCase(false, 1)]
    [TestCase(true, 0)]
    public async Task AKeyWithNoWindowGoesOnlyToTheFrontItAsked(bool frontChanged, int keysSent)
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.FrontReads.Enqueue(keyboard.Front);
        if (frontChanged)
            keyboard.FrontReads.Enqueue(keyboard.Front with { Window = 0x5678 });
        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages()).InvokeAsync(
            "input.key.press", Json("""{"key":"tab"}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(keysSent));
            if (frontChanged)
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_changed"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            }
        });
    }

    // Review of uso-108: the worker said the window does not respond before touching the field (Get-Root): nothing was written.
    [Test]
    public async Task AFieldOfAWindowThatDoesNotRespondIsToldWithNothingWritten()
    {
        const string worker = """{"ok":false,"error":"window_not_responding"}""";
        var keyboard = new FakeDesktopKeyboard();
        ExternalCapabilityReceipt written = await Adapter(keyboard, new FakeFieldMessages(), new FakeViewedFields(worker)).InvokeAsync(
            "input.text.type", Json("""{"text":"3","window":4660,"index":0}"""), CancellationToken.None);
        ExternalCapabilityReceipt chosen = await Adapter(keyboard, new FakeFieldMessages(), new FakeViewedFields(worker)).InvokeAsync(
            "input.text.type", Json("""{"text":"Arial","window":4660,"index":0,"entry":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            foreach (ExternalCapabilityReceipt receipt in new[] { written, chosen })
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("window_not_responding"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            }

            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    [TestCase("""{"ok":true,"kind":"Edit","className":"","method":"setvalue","delivered":false}""", false)]
    [TestCase("""{"ok":true,"kind":"Edit","className":"","method":"setvalue","delivered":true}""", true)]
    public async Task NoReadOrAMatchAddsNothingOfThat(string worker, bool verified)
    {
        ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), new FakeFieldMessages(), new FakeViewedFields(worker)).InvokeAsync(
            "input.text.type", Json("""{"text":"3","window":4660,"index":0}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(verified));
            string said = receipt.Result?.ToString() ?? string.Empty;
            Assert.That(said, Does.Not.Contain("fieldNow"));
            Assert.That(said, Does.Not.Contain("fieldUnchanged"));
        });
    }

    // B12 on a window's own edit control: a replaced value the control did not take.
    [Test]
    public async Task AReplacedValueTheControlDidNotTakeIsToldUnchanged()
    {
        FakeFieldMessages messages = new FakeFieldMessages { TakesReplace = false, TakesChars = false }.WithField(Edit, "Edit", "1366");
        var fields = new FakeViewedFields("""{"ok":true}""");
        fields.Ids[0] = "42." + Edit;
        ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"800","window":4660,"index":0,"replace":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.Result?.GetProperty("fieldUnchanged").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task AReplacedValueTheControlReshapedIsToldAsItStayed()
    {
        FakeFieldMessages messages = new FakeFieldMessages { ReshapesTo = "800,00 px" }.WithField(Edit, "Edit", "1366");
        var fields = new FakeViewedFields("""{"ok":true}""");
        fields.Ids[0] = "42." + Edit;
        ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"800","window":4660,"index":0,"replace":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.Result?.GetProperty("fieldNow").GetString(), Is.EqualTo("800,00 px"));
        });
    }

    // Contracase: an insertion's field may be a whole document: nothing of it is said.
    [Test]
    public async Task AnInsertionNotTakenSaysNothingOfTheField()
    {
        FakeFieldMessages messages = new FakeFieldMessages { TakesReplace = false, TakesChars = false }.WithField(Edit, "Edit", "un documento");
        var fields = new FakeViewedFields("""{"ok":true}""");
        fields.Ids[0] = "42." + Edit;
        ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.Result?.ToString() ?? string.Empty, Does.Not.Contain("documento"));
            Assert.That(receipt.Result?.ToString() ?? string.Empty, Does.Not.Contain("fieldNow"));
        });
    }

    // A cut value says so.
    [Test]
    public void AValueTooLongIsCutWithAnEllipsis() =>
        Assert.That(WindowsTextDelivery.ValueNow(new string('a', 130)), Is.EqualTo(new string('a', 120) + "\u2026"));

    // A3: a list never read is not a list without that entry (agent-desktop: windows/src/actions/select.rs:161-178, PR #256;
    // #517 for a popup still empty). Contracases: entries read and none of that name; the list's cut is said.
    [TestCase("""{"ok":true,"kind":"ComboBox","entry":true,"method":"","delivered":false,"enabled":true,"listNotRead":true}""", "input_list_not_read", false)]
    [TestCase("""{"ok":true,"kind":"ComboBox","entry":true,"method":"","delivered":false,"enabled":true,"listNotRead":true,"expanded":true}""", "input_list_not_read", true)]
    [TestCase("""{"ok":true,"kind":"ComboBox","entry":true,"method":"","delivered":false,"enabled":true,"entries":["Rojo"],"expanded":true}""", "input_entry_not_found", true)]
    public async Task AListNeverReadIsNotAListWithoutThatEntry(string worker, string code, bool mayHave)
    {
        ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), new FakeFieldMessages(), new FakeViewedFields(worker)).InvokeAsync(
            "input.text.type", Json("""{"text":"Verde","window":4660,"index":0,"entry":true}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.EffectMayHaveOccurred, Is.EqualTo(mayHave));
        });
    }

    [TestCase("""{"ok":true,"kind":"ComboBox","entry":true,"method":"","enabled":true,"entries":["Uno","Dos"],"entriesTotal":45,"expanded":true}""", 45, true)]
    [TestCase("""{"ok":true,"kind":"ComboBox","entry":true,"method":"","enabled":true,"entries":["Uno","Dos"],"entriesPartial":true,"expanded":true}""", 0, true)]
    [TestCase("""{"ok":true,"kind":"ComboBox","entry":true,"method":"","enabled":true,"entries":["Uno","Dos"],"entriesTotal":2,"expanded":true}""", 0, false)]
    public async Task AListCutSaysSo(string worker, int count, bool cut)
    {
        ExternalCapabilityReceipt receipt = await Adapter(new FakeDesktopKeyboard(), new FakeFieldMessages(), new FakeViewedFields(worker)).InvokeAsync(
            "input.text.type", Json("""{"text":"Verde","window":4660,"index":0,"entry":true}"""), CancellationToken.None);
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_entry_not_found"));
            Assert.That(result.GetProperty("candidates").GetArrayLength(), Is.EqualTo(2));
            Assert.That(result.TryGetProperty("truncated", out _), Is.EqualTo(cut));
            Assert.That(result.TryGetProperty("candidateCount", out JsonElement all) ? all.GetInt32() : 0, Is.EqualTo(count));
        });
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            throw new AssertionException("a field's text starts no process");
    }

    // A described element for Get-FieldText: its value, its own text, its name and its class.
    private const string FieldNode = """
        function Node($value,$text,$name,$class){
          $node=[pscustomobject]@{ Value=$value; Text=$text; Current=[pscustomobject]@{ Name=$name; ClassName=$class } }
          $node | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value {
            param($which,[ref]$out)
            if($which -eq [System.Windows.Automation.ValuePattern]::Pattern -and $null -ne $this.Value){
              $out.Value=[pscustomobject]@{ Current=[pscustomobject]@{ Value=$this.Value } }; return $true }
            if($which -eq [System.Windows.Automation.TextPattern]::Pattern -and $null -ne $this.Text){
              $range=[pscustomobject]@{ Text=$this.Text }
              $range | Add-Member -MemberType ScriptMethod -Name GetText -Value { param($most) if($this.Text.Length -gt $most){ return $this.Text.Substring(0,$most) }; return $this.Text }
              $out.Value=[pscustomobject]@{ DocumentRange=$range }; return $true }
            return $false
          }
          return $node
        }

        """;

    // A string as a PowerShell expression: the script travels as text and its characters as their numbers.
    private static string Literal(string value) =>
        "(-join @(" + string.Join(',', value.Select(static character => "[char]" + (int)character).DefaultIfEmpty("''")) + "))";
}
