using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 02-11 (encargo 2, B): two texts typed into the message box of a desktop chat ended input_text_not_read_back
/// while they may have been written. Measured on a rich text box drawn by Chromium (a contenteditable with paragraphs,
/// as chat composers are): it publishes no value (ControlType Group, no ValuePattern), so the focused field's value was
/// never read («focus_not_a_field»); and the paragraph at its caret, read by TextPattern as for a word processor's
/// document, left the empty box and read the text beside it (the last message shown), so the box could never be seen to
/// grow by the text. The field's own text is its TextPattern's document range: «\n» before, the text after. The worker's
/// function runs on described elements.
/// </summary>
[TestFixture]
public sealed class FieldTextReadBackTests
{
    [Test]
    public void AFieldWithoutAValueIsReadByItsOwnText()
    {
        JsonElement answer = WorkerFunctions.Run(["Get-FieldText", "Get-PlainValue"], """
            function Node($value,$text){
              $node=[pscustomobject]@{ Value=$value; Text=$text }
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
            function Read($node,$kind){ $read=Get-FieldText $node $kind 8; if($null -eq $read){ '<null>' } else { [string]$read.text } }
            $values=@(
              (Read (Node 'hola' 'otro') 'Edit'),
              (Read (Node 'hola' $null) 'ComboBox'),
              (Read (Node $null "`nhola") 'Group'),
              (Read (Node $null 'hola') 'Edit'),
              (Read (Node $null '0123456789') 'Group'),
              (Read (Node $null 'hola') 'Document'),
              (Read (Node $null $null) 'Group'),
              (Read (Node 'hola' $null) 'Group'),
              (Read (Node $null 'C:\> dir') 'Text'),
              (Read (Node $null 'cmd output') 'Custom'),
              (Read (Node $null 'a label') 'Pane'))
            [Console]::Out.Write((ConvertTo-Json -Compress $values))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "hola",        // a field's value, as before
            "hola",        // a combo box's value, as before
            "\nhola",      // a rich text box with no value: its own text
            "hola",        // an edit field with no value: its own text
            "012345678",   // read one past the bound, so the caller can tell it was cut
            "<null>",      // a document (a word processor's, a page) is never read whole
            "<null>",      // neither a value nor a text
            "<null>",      // a value of what is no field kind is not taken
            // Encargo 10 (punto 4): a control with a TextPattern that is no editable field —a terminal, a control of its
            // own, a label— is never read as a field's value.
            "<null>",      // a terminal's text
            "<null>",      // a control of its own
            "<null>",      // a label (a Pane with text)
        }));
    }

    // Encargo 17 (banco uso-cf8d, U27: a copy with nothing selected in Windows 11's Notepad said no text length, its text
    // area being a Document with no value): what there is to copy in the focused element, as a length only: a field's
    // own text (Get-FieldText), else any element's TextPattern document range, read one past the bound; -1 with neither.
    [Test]
    public void TheTextToCopyIsMeasuredByTheDocumentRangeWhenNoValueGivesIt()
    {
        JsonElement answer = WorkerFunctions.Run(["Get-FieldText", "Get-PlainValue", "Get-TextLength"], """
            function Node($value,$text){
              $node=[pscustomobject]@{ Value=$value; Text=$text }
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
            $values=@(
              (Get-TextLength (Node $null 'tres lineas') 'Document' 64),
              (Get-TextLength (Node $null '0123456789') 'Document' 8),
              (Get-TextLength (Node 'hola' 'otro texto') 'Edit' 64),
              (Get-TextLength (Node $null '') 'Document' 64),
              (Get-TextLength (Node $null $null) 'Document' 64))
            [Console]::Out.Write((ConvertTo-Json -Compress $values))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetInt32()), Is.EqualTo(new[]
        {
            11,  // a document with no value: its document range's length
            9,   // read one past the bound, so the caller can tell it was cut
            4,   // a field's value, as Get-FieldText reads it
            0,   // an empty document: nothing to copy
            -1,  // no value and no text pattern: unknown
        }));
    }

    // Auditoría de falsedades 2026-11-04 (P6): an undeclared Enter asks while a field of its window that takes text holds
    // text. The S03 chat's view: its composer «Escribe un mensaje» holding the message, its history «Mensajes» read-only.
    // A read-only field, a password and a blank rich text box hold nothing a key would send; a composer with text, an
    // editable field with no value whose own text is there (a rich text box) do.
    [Test]
    public void AWindowHoldsTextWhenAFieldThatTakesTextHasSome()
    {
        JsonElement answer = WorkerFunctions.Run(["Get-FieldText", "Get-PlainValue", "Test-HeldText", "Test-MaybePassword"], """
            function Node($kind,$value,$text,$readOnly,$password){
              $node=[pscustomobject]@{ Value=$value; Text=$text; ReadOnly=$readOnly
                Current=[pscustomobject]@{ ControlType=[pscustomobject]@{ ProgrammaticName=('ControlType.'+$kind) }; IsPassword=$password } }
              $node | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value {
                param($which,[ref]$out)
                $has=$false
                if($which -eq [System.Windows.Automation.ValuePattern]::Pattern -and $null -ne $this.Value){
                  $out.Value=[pscustomobject]@{ Current=[pscustomobject]@{ Value=$this.Value; IsReadOnly=$this.ReadOnly } }; $has=$true }
                elseif($which -eq [System.Windows.Automation.TextPattern]::Pattern -and $null -ne $this.Text){
                  $range=[pscustomobject]@{ Text=$this.Text }
                  $range | Add-Member -MemberType ScriptMethod -Name GetText -Value { param($most) if($this.Text.Length -gt $most){ return $this.Text.Substring(0,$most) }; return $this.Text }
                  $out.Value=[pscustomobject]@{ DocumentRange=$range }; $has=$true }
                return $has
              }
              return $node
            }
            $history=Node 'Edit' 'Yo: Llego como a las siete' $null $true $false
            $search=Node 'Edit' '' $null $false $false
            $composer=Node 'Edit' 'Llego como a las siete' $null $false $false
            $values=@(
              (Test-HeldText @($search,$composer,$history)),
              (Test-HeldText @($search,(Node 'Edit' '' $null $false $false),$history)),
              (Test-HeldText @((Node 'Edit' 'secreto' $null $false $true))),
              (Test-HeldText @((Node 'Group' $null "`n" $false $false))),
              (Test-HeldText @((Node 'Group' $null "`nhola" $false $false))),
              (Test-HeldText @((Node 'Edit' '   ' $null $false $false))),
              (Test-HeldText @()),
            # Held-out of a subagent that did not see the change: a chat's draft with the focus on the menu bar; a contact
            # form's comment with the focus on «Limpiar»; a rich text box's draft with the focus on the conversations; a
            # chat whose only text is its read-only history; a sign-in window with only its password filled and a rich
            # note holding a line break.
            (Test-HeldText @((Node 'Edit' "Hola, como estas?`nBien, y tu?" $null $true $false),(Node 'Edit' 'Manana llevo las bebidas' $null $false $false))),
            (Test-HeldText @((Node 'Edit' '' $null $false $false),(Node 'Edit' 'Quiero cambiar la fecha de la reserva al viernes' $null $false $false))),
            (Test-HeldText @((Node 'Group' $null 'Quien se anota con el carbon?' $false $false),(Node 'Edit' '' $null $false $false))),
            (Test-HeldText @((Node 'Edit' "Te mande el archivo ayer`nGracias, ya lo vi" $null $true $false),(Node 'Edit' '' $null $false $false))),
            (Test-HeldText @((Node 'Edit' '' $null $false $false),(Node 'Edit' 'secreto' $null $false $true),(Node 'Group' $null "`n" $false $false))))
            [Console]::Out.Write((ConvertTo-Json -Compress $values))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetBoolean()), Is.EqualTo(new[]
        {
            true,   // the composer holds the message written in it
            false,  // the same chat with the composer empty: only the read-only history has text
            false,  // a password is never read
            false,  // a blank rich text box
            true,   // a rich text box (no value) with its own text
            false,  // blanks only
            false,  // no field at all
            true, true, true, false, false, // the held-out, as their writer expected Enter to ask or not
        }));
    }

    // Uso real 03-11 (G8, a text typed into a web translator in Opera, not read back): Chromium builds its accessibility
    // tree on demand, and its first answer to «what has the focus» is the web view's container, which says of itself that
    // it has no keyboard focus (measured on Edge 156 and Opera GX 138); 100 ms later it is the focused text area. Such an
    // answer is read again, bounded, until the element has the focus by its own word; an answer that has it, or none, is
    // taken at once.
    [Test]
    public void AFocusedElementThatSaysItHasNoFocusIsReadAgainUntilItSettles()
    {
        JsonElement answer = WorkerFunctions.Run(["Get-SettledFocus"], """
            Add-Type -TypeDefinition @'
            public static class FakeFocus {
              public static System.Collections.Generic.Queue<object> Nodes = new System.Collections.Generic.Queue<object>();
              public static int Reads;
              public static object FocusedElement { get { Reads++; return Nodes.Count > 1 ? Nodes.Dequeue() : (Nodes.Count == 1 ? Nodes.Peek() : null); } }
            }
            '@
            $AE=[FakeFocus]
            function Node($name,$has){ [pscustomobject]@{ Name=$name; Current=[pscustomobject]@{ HasKeyboardFocus=$has } } }
            function Settle($nodes){
              [FakeFocus]::Nodes.Clear(); [FakeFocus]::Reads=0
              foreach($node in $nodes){ [FakeFocus]::Nodes.Enqueue($node) }
              $found=Get-SettledFocus
              $name='<null>'; if($null -ne $found){ $name=$found.Name }
              return ('{0}/{1}' -f $name,[FakeFocus]::Reads)
            }
            $values=@(
              (Settle @((Node 'View' $false),(Node 'texto' $true))),
              (Settle @((Node 'View' $false),(Node 'View' $false),(Node 'texto' $true))),
              (Settle @((Node 'Pizarra - Google Chrome' $true))),
              (Settle @((Node 'View' $false))),
              (Settle @()))
            [Console]::Out.Write((ConvertTo-Json -Compress $values))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "texto/2",                     // the container first, the text area on the next read
            "texto/3",                     // a tree that takes longer is still waited for
            "Pizarra - Google Chrome/1",   // an element with the focus is taken at once (a window, a classic field)
            "View/10",                     // a focus that never settles: the last read, after ten
            "<null>/1",                    // nothing answers: nothing, at once
        }));
    }

    // Uso real 03-11 (G8): the three reads of the keyboard's focus a typed text depends on (its field's value, the
    // paragraph at its caret, the kind of field a key lands on) take the settled focus, never the first answer.
    [Test]
    public void TheFocusReadsTakeTheSettledFocus()
    {
        string path = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(path), "the worker script is copied next to the tests");
        string script = File.ReadAllText(path, System.Text.Encoding.UTF8);
        foreach (string function in new[] { "Do-FocusValue", "Do-TextCaret", "Do-FocusKind" })
        {
            int at = script.IndexOf("function " + function + "(", StringComparison.Ordinal);
            Assert.That(at, Is.GreaterThanOrEqualTo(0), function);
            string body = script[at..script.IndexOf("\nfunction ", at + 1, StringComparison.Ordinal)];
            Assert.That(body, Does.Contain("$node=Get-SettledFocus").And.Not.Contain("$AE::FocusedElement"), function);
        }
    }
}
