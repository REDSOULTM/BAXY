using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// A control without a UI Automation Name is not mute when its application names it another way (v3, point 3): its
/// help text (WPF publishes a text ToolTip there), the name of the label that labels it (LabeledBy, a form field) or
/// its AutomationId read as words, in that order. The view lists it with <c>nameSource</c> and a click by label finds
/// it. The worker's own functions are taken from the script by its syntax tree and run on described elements: no
/// window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseFallbackNameTests
{
    [Test]
    public void AnAutomationIdIsReadAsWordsOnlyWhenItIsOne()
    {
        JsonElement answer = RunWorker("""
            $cases=@(
              @('SettingsButton','Button',''), @('close_button','Button',''), @('NewTabMenuItem','MenuItem',''),
              @('XMLParserView','Pane',''), @('Page2','TabItem',''), @('SearchBox','Edit',''),
              @('12345','Button',''), @('{3F2504E0-4F89-11D3-9A0C-0305E82C3301}','Button',''),
              @('3F2504E04F8911D39A0C0305E82C3301','Button',''), @('item_3fa85f64e1','ListItem',''),
              @('Button','Button',''), @('x1','Button',''), @('','Button',''),
              @('button1','Button',''), @('textBox1','Edit',''), @('Button1','Button',''), @('uid_12','Button',''),
              @('radix-:r3:','Button',''), @('a8Xk2Lq9','Button',''), @('Item_1_2','ListItem',''),
              @('ListViewItem','ListItem','ListViewItem'), @('System.Windows.Controls.Button','Button',''),
              @('PART_CloseButton','Button',''), @('CloseWindowButton','Button',''), @('Tab2','TabItem',''),
              @('ListViewItem','ListItem','ListBoxItem'))
            [Console]::Out.Write((ConvertTo-Json -Compress @($cases | ForEach-Object { Get-ReadableId $_[0] $_[1] $_[2] })))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "Settings",          // the trailing word that only repeats the control's type is dropped
            "close",             // separators split words
            "New Tab",           // a two-word type is dropped whole
            "XML Parser View",   // an acronym stays one word
            "Page 2",            // a number beside a word stays
            "Search Box",        // a word that is not the type stays
            "",                  // a number names nothing
            "",                  // nor a GUID with braces
            "",                  // nor one without separators
            "",                  // nor a hash inside an id
            "",                  // the type alone names nothing
            "",                  // no word of two letters or more
            "",
            "",                  // a designer's default name: a lowercase type and its ordinal
            "",                  // the same with a two-word type
            "",                  // the control's own type and a number
            "",                  // a short lowercase word and an ordinal
            "",                  // a generated DOM id: a single letter is no word
            "",                  // letters and digits alternating: a hash
            "",                  // more numbers than words: an index
            "",                  // the control's own class name says what it is
            "",                  // a qualified name (namespace, class) is no label
            "Close",             // WPF's template-part prefix is dropped
            "Close Window",      // counter-case: a verb and a noun before the type stay
            "Tab 2",             // counter-case: a capitalised word beside a number stays
            "List View",         // counter-case: the same id under another class name is read
        }));
    }

    [Test]
    public void TheFallbackFollowsHelpTextThenLabelThenAutomationIdAndNeverReplacesAName()
    {
        JsonElement answer = RunWorker("""
            $Actionable=@('Button','MenuItem','ListItem','Edit')
            function Fake([string]$name,[string]$kind,[string]$help,[string]$aid,$label){
              $props=[pscustomobject]@{ Name=$name; ControlType=[pscustomobject]@{ ProgrammaticName=('ControlType.'+$kind) };
                                        HelpText=$help; AutomationId=$aid; LabeledBy=$label; IsOffscreen=$false }
              return [pscustomobject]@{ Cached=$props; Current=$props }
            }
            $label=[pscustomobject]@{ Cached=[pscustomobject]@{ Name='Correo electrónico' } }
            $elements=@(
              (Fake 'Guardar' 'Button' 'Guarda el archivo' 'SaveButton' $null),
              (Fake '' 'Button' '  Ajustes  ' 'SettingsButton' $label),
              (Fake '' 'Edit' '' 'EmailBox' $label),
              (Fake '' 'Button' '' 'NotificationsButton' $null),
              (Fake '' 'Button' '   ' '12345' $null),
              (Fake '' 'Pane' 'Panel lateral' 'SidebarPane' $null),
              (Fake '' 'Group' '' 'ToolbarGroup' $null))
            [Console]::Out.Write((ConvertTo-Json -Compress @($elements | ForEach-Object { $s=Get-ShownName $_; $s.name+'|'+$s.source })))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "Guardar|",                         // its own Name rules: the help text never replaces it
            "Ajustes|helpText",                 // help text first, trimmed
            "Correo electrónico|labeledBy",     // a form field takes its label's name
            "Notifications|automationId",       // last, the readable AutomationId
            "|",                                // a blank help text and a number name nothing
            "|",                                // a pane without a Name stays nameless: it is not actionable
            "|",                                // nor a group
        }));
    }

    [Test]
    public void AClickByLabelFindsAControlNamedOnlyByItsFallback()
    {
        JsonElement answer = RunWorker("""
            # Find-Named catches the UIA exception of a control gone mid-walk: its type is loaded as the worker loads it.
            Add-Type -AssemblyName UIAutomationClient
            $Actionable=@('Button','MenuItem','ListItem','Edit')
            $script:TitledKinds=@('ControlType.TabItem','ControlType.ListItem','ControlType.TreeItem','ControlType.Hyperlink')
            function Fake([string]$name,[string]$kind,[string]$help,[string]$aid){
              $props=[pscustomobject]@{ Name=$name; ControlType=[pscustomobject]@{ ProgrammaticName=('ControlType.'+$kind) };
                                        HelpText=$help; AutomationId=$aid; LabeledBy=$null; IsOffscreen=$false }
              return [pscustomobject]@{ Cached=$props; Current=$props; Tag=$aid }
            }
            $script:Fakes=@(
              (Fake '' 'Button' 'Ajustes' 'GearButton'),
              (Fake '' 'Button' '' 'NotificationsButton'),
              (Fake 'Inicio' 'Button' 'Ajustes rápidos' 'HomeButton'),
              (Fake '' 'Pane' 'Buscar' 'SearchPane'))
            function Get-Descendants($root){ return $script:Fakes }
            # Ronda 21: Find-Named looks in Get-LookupScope, whose walk of the shown tree is faked like the whole one.
            function Get-ShownDescendants($root,$hwnd,$seconds){ return $script:Fakes }
            $found=@(
              @(Find-Named $null @('Ajustes')),
              @(Find-Named $null @('Notifications')),
              @(Find-Named $null @('Buscar')),
              @(Find-Named $null @('Ajustes rápidos')))
            [Console]::Out.Write((ConvertTo-Json -Compress @($found | ForEach-Object { (@($_ | ForEach-Object { $_.Tag }) -join ',') })))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "GearButton",           // by its help text
            "NotificationsButton",  // by its readable AutomationId
            "",                     // a pane is never named by its help text, so never clicked by it
            "",                     // a named control is found by its Name, never by its help text
        }));
    }

    // Auditoría C10: a row whose title only holds the label is never the control pressed for it; its name comes back as
    // a candidate. Counter-case: the exact name, folded (case, accents), is the one found and no candidate is noted.
    [Test]
    public void ARowThatOnlyHoldsTheLabelIsACandidateNeverTheControlFound()
    {
        JsonElement answer = RunWorker("""
            Add-Type -AssemblyName UIAutomationClient
            $Actionable=@('Button','ListItem')
            $script:TitledKinds=@('ControlType.TabItem','ControlType.ListItem','ControlType.TreeItem','ControlType.Hyperlink')
            function Test-SystemMenu($el){ return $false }
            function Fake([string]$name,[string]$kind){
              $props=[pscustomobject]@{ Name=$name; ControlType=[pscustomobject]@{ ProgrammaticName=('ControlType.'+$kind) }; IsOffscreen=$false }
              return [pscustomobject]@{ Cached=$props; Current=$props; Tag=$name }
            }
            $script:Fakes=@((Fake 'Bloc de notas, 11.2, Microsoft' 'ListItem'), (Fake 'Configuración' 'Button'))
            function Get-ShownDescendants($root,$hwnd,$seconds){ return $script:Fakes }
            $script:NamedCandidates=@()
            $held=@(Find-Named $null @('bloc de notas'))
            $heldCandidates=@($script:NamedCandidates)
            $script:NamedCandidates=@()
            $exact=@(Find-Named $null @('configuracion'))
            [Console]::Out.Write((ConvertTo-Json -Compress @($held.Count, ($heldCandidates -join ';'), ($exact | ForEach-Object { $_.Tag }), $script:NamedCandidates.Count)))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.ToString()), Is.EqualTo(new[]
        {
            "0", "Bloc de notas, 11.2, Microsoft", "Configuración", "0",
        }));
    }

    // Auditoría C9: a box's entry is chosen only by its own name, folded (case, accents, spaces); «125» is not the entry
    // «125% (recomendado)», nor «2» the entry «2,5».
    [Test]
    public void AComboEntryIsChosenOnlyByItsOwnName()
    {
        JsonElement answer = RunWorker("""
            function Entry([string]$name){ return [pscustomobject]@{ Cached=[pscustomobject]@{ Name=$name }; Tag=$name } }
            function Pick($names,[string]$text){
              $chosen=Find-EntryNamed @($names | ForEach-Object { Entry $_ }) $text
              if($null -eq $chosen){ return '' } else { return $chosen.Tag }
            }
            $scale=@('100%','125% (recomendado)','150%','175%')
            [Console]::Out.Write((ConvertTo-Json -Compress @(
              (Pick $scale '125'),
              (Pick $scale '125% (Recomendado)'),
              (Pick $scale ' 150% '),
              (Pick @('1,0','2','2,5') '2'),
              (Pick @('1,0','2,5') '2'),
              (Pick @('Pequeño','Grande') 'pequeno'))))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "",                     // a number is no entry that only holds it
            "125% (recomendado)",   // its own name, folded
            "150%",                 // spaces around are no part of a name
            "2",
            "",                     // «2» is not «2,5»
            "Pequeño",              // accents folded
        }));
    }

    [Test]
    public void TheWorkerCachesTheFallbackSourcesAndEmitsWhereTheNameCameFrom()
    {
        string script = File.ReadAllText(WorkerPath());
        Assert.Multiple(() =>
        {
            foreach (string property in new[] { "$AE::HelpTextProperty", "$AE::AutomationIdProperty", "$AE::LabeledByProperty" })
                Assert.That(script, Does.Contain(property), "read in the same cached call as the other properties");
            Assert.That(script, Does.Contain("nameSource=$shown.source"));
            Assert.That(script, Does.Contain("nameSource=$entry.nameSource"), "emitted with each control");
            Assert.That(script, Does.Contain("nameSource=$focused.nameSource"),
                "the focused control says its name is a fallback: the mind never frees Enter on it (RiskPolicy asks)");
            Assert.That(script, Does.Contain("$AE::ClassNameProperty"), "an id equal to the control's class names nothing");
        });
    }

    [Test]
    public async Task TheViewCarriesWhereAFallbackNameCameFrom()
    {
        // A handle no window has: nothing on the desktop is read or moved.
        const long front = 0x7FFF_0F3A;
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Trabajo\",\"controls\":[" +
            "{\"i\":0,\"kind\":\"Button\",\"name\":\"Ajustes\",\"nameSource\":\"helpText\",\"id\":\"4.1\",\"state\":\"\"," +
            "\"value\":null,\"rect\":null,\"repeated\":0}," +
            "{\"i\":1,\"kind\":\"Button\",\"name\":\"Inicio\",\"nameSource\":\"\",\"id\":\"4.2\",\"state\":\"\"," +
            "\"value\":null,\"rect\":null,\"repeated\":0}],\"controlCount\":2," +
            "\"focused\":{\"kind\":\"Edit\",\"name\":\"main Input\",\"nameSource\":\"automationId\",\"value\":null}}");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, browserWindow: new FixedFront(front));

        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls", JsonDocument.Parse("""{"application":"el navegador"}""").RootElement.Clone(),
            CancellationToken.None);

        JsonElement controls = view.Result!.Value.GetProperty("controls");
        Assert.Multiple(() =>
        {
            Assert.That(view.Verified, Is.True);
            Assert.That(controls[0].GetProperty("name").GetString(), Is.EqualTo("Ajustes"));
            Assert.That(controls[0].GetProperty("nameSource").GetString(), Is.EqualTo("helpText"));
            Assert.That(controls[1].TryGetProperty("nameSource", out _), Is.False, "a control's own Name carries no source");
            Assert.That(view.Result!.Value.GetProperty("window").GetProperty("focused").GetProperty("nameSource").GetString(),
                Is.EqualTo("automationId"), "the focused control keeps where its name came from");
        });
    }

    private static string WorkerPath()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    private static JsonElement RunWorker(string body)
    {
        string script = """
            $ErrorActionPreference='Stop'
            [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_FALLBACK_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Format-Name','Get-Cut','Get-Name','Get-Prop','Get-ReadableId','Get-FallbackName','Get-ShownName',
                      'Test-NameMatch','Get-LabelFolded','Get-Folded','Test-ItemHolds','Test-NameHolds','Find-Named',
                      'Test-SystemMenu','Test-SystemMenuChain','Find-EntryNamed','Get-LookupScope',
                      'Test-OffscreenUsable','Get-Rect')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne $wanted.Count){ throw 'worker functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }

            """ + body;
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        start.Environment["BAXY_FALLBACK_WORKER"] = WorkerPath();
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the worker functions answer");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output).RootElement.Clone();
    }

    private sealed class FixedFront(long handle) : IUserBrowserWindowLocator
    {
        public nint FrontWindow() => (nint)handle;
    }
}
