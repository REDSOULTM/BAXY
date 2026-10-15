using System.Diagnostics;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 29 and encargo V (banco e2, c7): RiskPolicy judges the label of an invocation, and the UIA worker resolves the
/// control it presses. A label that names its control only by a part of its name («Transmisión» for «Iniciar
/// Transmisión»; «cotele» for «Cotele!!!😎, Canal de voz, Choche», an item the view never listed that the worker found
/// because its name holds the word) was judged harmless while the control pressed goes out to the world. The worker
/// refuses that press before any effect wherever it resolves the control (by its identity, in its manner, by its label,
/// at a point), with RiskPolicy's own pattern (<see cref="RiskPolicy.AsksPattern"/>), and names it; a label that is the
/// control's own name, or that already asks, is pressed as before. Ronda 29 judged only the controls of the last view in
/// the adapter: c7's channel was not among them. The worker's functions are taken from the script by its syntax tree
/// and run on names: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUsePressedNameTests
{
    // name pressed, label of the click, refused
    private static readonly (string Name, string Label, bool Refused)[] Cases =
    [
        // c7 (banco e2): the channel the worker found by a word of its name; the step that names it is pressed.
        ("Cotele!!!😎, Canal de voz, Choche", "cotele", true),
        ("Cotele!!!😎, Canal de voz, Choche", "Cotele!!!😎, Canal de voz, Choche", false),
        ("General (canal de voz)", "General", true),
        ("Cotele!!!😎 (canal de voz)", "Cotele", true),
        // Contracase: a text channel goes nowhere.
        ("general (canal de texto)", "general", false),
        ("cancion🎶 (canal de texto)", "cancion", false),
        // v3-53 (OBS), by their real names.
        ("Iniciar Transmisión", "Transmisión", true),
        ("Iniciar Transmisión", "Iniciar", true),
        ("Iniciar Transmisión", "Iniciar Transmisión", false),
        ("Iniciar Transmisión (Ctrl+T)", "Iniciar Transmisión", false),
        ("Iniciar Grabación", "Grabación", false),
        ("Abrir filtros de la escena", "filtros", false),
        // A removal named by its object; a sentence that only mentions emptying is no button.
        ("Eliminar pruebas", "pruebas", true),
        ("Vaciar la papelera cuando el disco se llena de archivos viejos", "papelera", false),
        // The data's exception, a label that already asks, a format character inside the verb.
        ("Enviar búsqueda", "búsqueda", false),
        ("Enviar a Ron92", "Enviar", false),
        ("En\u200Bviar mensaje", "mensaje", true),
        ("Un título largo - Sitio", "Sitio", false),
    ];

    [Test]
    public void TheWorkerRefusesWhatAsksMoreThanItsLabelAsRiskPolicyDoes()
    {
        string cases = JsonSerializer.Serialize(Cases.Select(item => new { name = item.Name, label = item.Label }));
        JsonElement answer = RunWorker(
            """
            $asks=$env:BAXY_ASKS | ConvertFrom-Json
            $cases=$env:BAXY_CASES | ConvertFrom-Json
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @($cases | ForEach-Object { [bool](Test-AsksMore ([string]$_.name) @([string]$_.label) $asks) })))
            """,
            cases);

        bool[] refused = [.. answer.EnumerateArray().Select(item => item.GetBoolean())];
        Assert.Multiple(() =>
        {
            for (int k = 0; k < Cases.Length; k++)
            {
                (string name, string label, bool expected) = Cases[k];
                Assert.That(refused[k], Is.EqualTo(expected), $"worker: «{label}» → «{name}»");
                Assert.That(RiskPolicy.PressedNameAsksMoreThanItsLabel(label, name), Is.EqualTo(expected), $"policy: «{label}» → «{name}»");
            }
        });
    }

    // Contracase: a request without RiskPolicy's pattern (a command of another kind) presses as before.
    [Test]
    public void WithoutThePatternNothingIsRefused()
    {
        JsonElement answer = RunWorker(
            """
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @([bool](Test-AsksMore 'General (canal de voz)' @('General') $null))))
            """,
            "[]");
        Assert.That(answer[0].GetBoolean(), Is.False);
    }

    // The worker judges what it found before it answers or presses anything: by the label alone, any control of any kind
    // that holds the label and asks (H4) before an ambiguity, a cut lookup, the native buttons or the classic menu; the
    // control found, by its identity, its manner or its label (Do-ClickJudged), and at a point (Do-At), before any
    // pattern or pointer. The native buttons are found by an equal name only, which the label already is.
    [Test]
    public void EveryPressOfTheWorkerIsJudgedFirst()
    {
        string script = File.ReadAllText(WorkerPath());
        string wrapper = Function(script, "Do-Click");
        string click = Function(script, "Do-ClickJudged");
        string at = Function(script, "Do-At");
        int candidates = click.IndexOf("$script:AskingName.Length -gt 0", StringComparison.Ordinal);
        int found = click.IndexOf("Get-AskingName $button $name $aliases $request.asks", StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(wrapper, Does.Contain("$script:AskSearch=$request.asks"));
            Assert.That(candidates, Is.GreaterThan(0));
            foreach (string before in new[] { "visible_lookup_timeout' (Get-Name", "FindVisibleButtons", "Press-MenuCommand $target $aliases ''", "visible_button_ambiguous" })
                Assert.That(candidates, Is.LessThan(click.IndexOf(before, StringComparison.Ordinal)), before);
            Assert.That(found, Is.GreaterThan(0).And.LessThan(click.IndexOf("Invoke-MannerControl", StringComparison.Ordinal)));
            Assert.That(found, Is.LessThan(click.IndexOf("Invoke-NamedControl", StringComparison.Ordinal)));
            Assert.That(at.IndexOf("Get-AskingName $button $name $aliases $request.asks", StringComparison.Ordinal),
                Is.GreaterThan(0).And.LessThan(at.IndexOf("Invoke-NamedControl", StringComparison.Ordinal)));
        });
    }

    // Review of V, H2 and H3: what receives the press. Its whole name (the view's is cut at 80 characters, and a long
    // voice channel lost «Canal de voz» in the cut), and, when it does not press itself (the Text inside a link, whose
    // press lands on the link), its ancestors up to the first that does. Contracases: a text channel, a button that
    // presses itself inside a group that names a voice channel, and a label that is the whole name.
    [Test]
    public void WhatReceivesThePressIsJudgedByItsWholeName()
    {
        const string Long = "Sala de música y charla de los viernes por la noche, Canal de voz, Los Amigos de Siempre";
        JsonElement answer = RunWorker(
            """
            Add-Type -AssemblyName UIAutomationClient
            $asks=$env:BAXY_ASKS | ConvertFrom-Json
            $script:LineageUp=3
            function Node([string]$name,[bool]$presses,$parent){
              $node=[pscustomobject]@{ Current=[pscustomobject]@{ Name=$name }; Parent=$parent; Presses=$presses }
              $node | Add-Member ScriptMethod TryGetCurrentPattern { param($kind,$found) return $this.Presses }
              return $node
            }
            function Get-LineageWalker(){
              $walker=[pscustomobject]@{}
              $walker | Add-Member ScriptMethod GetParent { param($node) return $node.Parent }
              return $walker
            }
            $long=Node $env:BAXY_LONG $true $null
            $link=Node $env:BAXY_LINK $true (Node 'Servidor' $false $null)
            $text=Node $env:BAXY_TEXT $false $link
            $textItem=Node 'general (canal de texto)' $true $null
            $plain=Node 'General' $false $textItem
            $button=Node 'Cotele' $true (Node 'Canal de voz Cotele' $false $null)
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @(
              (Get-AskingName $long (Format-Name $env:BAXY_LONG) @('sala de musica') $asks),
              (Get-AskingName $text $env:BAXY_TEXT @('cotele') $asks),
              (Get-AskingName $plain 'General' @('general') $asks),
              (Get-AskingName $button 'Cotele' @('Cotele') $asks),
              (Get-AskingName $link $env:BAXY_LINK @($env:BAXY_LINK) $asks),
              (Get-AskingName $long (Format-Name $env:BAXY_LONG) @($env:BAXY_LONG) $asks),
              [bool](Test-NameMatch (Format-Name $env:BAXY_LONG) @($env:BAXY_LONG)))))
            """,
            "[]",
            ("BAXY_LONG", Long), ("BAXY_LINK", "Cotele!!!😎 (canal de voz), RED"), ("BAXY_TEXT", "Cotele!!!😎"));

        Assert.Multiple(() =>
        {
            Assert.That(answer[0].GetString(), Is.EqualTo(Long), "the whole name, not the cut one");
            Assert.That(answer[1].GetString(), Is.EqualTo("Cotele!!!😎 (canal de voz), RED"), "the link the text's press lands on");
            Assert.That(answer[2].GetString(), Is.Empty, "a text channel");
            Assert.That(answer[3].GetString(), Is.Empty, "a button pressed by itself");
            Assert.That(answer[4].GetString(), Is.Empty, "the label is the whole name: the policy asked");
            Assert.That(answer[5].GetString(), Is.Empty, "the whole long name as the label: the policy asked");
            Assert.That(answer[6].GetBoolean(), Is.True, "the whole long name names its cut view name");
        });
    }

    // Review of V, H4: by the label alone, a control of any kind (a Button is never resolved by holding the label) that
    // holds the label as words and asks more is noted while the tree is walked, and the click answers it. Contracases:
    // a control of exactly that name is the one pressed (AControlOfExactlyThatNameIsTheOnePressed of ronda 29), a word
    // that is only part of another word, a label that already asks, and a click without RiskPolicy's pattern.
    [Test]
    public void ByTheLabelAloneAControlThatHoldsItAndAsksIsNoted()
    {
        JsonElement answer = RunWorker(
            """
            Add-Type -AssemblyName UIAutomationClient
            $asks=$env:BAXY_ASKS | ConvertFrom-Json
            $Actionable=@('Button','MenuItem','ListItem','Edit')
            $script:TitledKinds=@('ControlType.TabItem','ControlType.ListItem','ControlType.TreeItem','ControlType.Hyperlink')
            function Fake([string]$name,[string]$kind){
              $props=[pscustomobject]@{ Name=$name; ControlType=[pscustomobject]@{ ProgrammaticName=('ControlType.'+$kind) };
                                        HelpText=''; AutomationId=''; LabeledBy=$null; IsOffscreen=$false }
              return [pscustomobject]@{ Cached=$props; Current=$props }
            }
            function Get-Descendants($root){ return $script:Fakes }
            function Get-ShownDescendants($root,$hwnd,$seconds){ return $script:Fakes }
            function Look([string]$label,$search){
              $script:AskSearch=$search; $script:AskingName=''
              $found=@(Find-Named $null @($label))
              return ([string]$found.Count)+'|'+$script:AskingName
            }
            $live=$env:BAXY_LIVE; $part=$env:BAXY_PART
            $script:Fakes=@((Fake 'Abrir filtros de la escena' 'Button'), (Fake $live 'Button'), (Fake 'Transmisiones recientes' 'Text'))
            $first=Look $part $asks
            $second=Look $live $asks
            $third=Look $part $null
            $fourth=Look 'escena' $asks
            $script:Fakes=@((Fake $live 'Button'), (Fake $part 'Button'))
            $fifth=Look $part $asks
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @($first,$second,$third,$fourth,$fifth)))
            """,
            "[]",
            ("BAXY_LIVE", "Iniciar Transmisión"), ("BAXY_PART", "Transmisión"));

        Assert.Multiple(() =>
        {
            Assert.That(answer[0].GetString(), Is.EqualTo("0|Iniciar Transmisión"), "a Button that holds the label and goes live");
            Assert.That(answer[1].GetString(), Is.EqualTo("1|"), "the label already asks: found as before");
            Assert.That(answer[2].GetString(), Is.EqualTo("0|"), "no pattern, no judgement");
            Assert.That(answer[3].GetString(), Is.EqualTo("0|"), "an ordinary control holds the label");
            Assert.That(answer[4].GetString(), Does.StartWith("1|"), "a control of exactly that name is the one pressed");
        });
    }

    // At a point the refusal is no «nothing there»: the pointer does not press it either.
    [Test]
    public void AtAPointTheRefusalStopsThePointer()
    {
        using JsonDocument answer = JsonDocument.Parse(
            """{"ok":false,"effectObserved":false,"error":"visible_control_needs_confirmation","name":"General (canal de voz)"}""");
        Assert.That(WindowsVisibleControlAdapter.PointPressFrom(answer.RootElement), Is.SameAs(PointPressed.Refused));
    }

    // The receipt says nothing was pressed and names the control, for the step that names it.
    [Test]
    public void TheReceiptNamesTheControlAndNoEffect()
    {
        MethodInfo receiptFrom = typeof(WindowsVisibleControlAdapter).GetMethod(
            "ReceiptFromWorker", BindingFlags.NonPublic | BindingFlags.Static)!;
        using JsonDocument answer = JsonDocument.Parse(
            """{"ok":false,"effectObserved":false,"error":"visible_control_needs_confirmation","name":"Cotele!!!😎, Canal de voz, Choche","kind":"ListItem"}""");
        var boundary = new ExternalEffectBoundary();
        boundary.Cross(CancellationToken.None);

        var receipt = (ExternalCapabilityReceipt)receiptFrom.Invoke(null, ["input.visible.click", answer.RootElement, boundary])!;

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_needs_confirmation"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False, "refused before the press: nothing may have happened");
            Assert.That(receipt.Result?.GetProperty("name").GetString(), Is.EqualTo("Cotele!!!😎, Canal de voz, Choche"));
        });
    }

    private static string Function(string script, string name)
    {
        int start = script.IndexOf("function " + name + "(", StringComparison.Ordinal);
        Assert.That(start, Is.GreaterThanOrEqualTo(0), name);
        int end = script.IndexOf("\nfunction ", start + 10, StringComparison.Ordinal);
        return script[start..(end < 0 ? script.Length : end)];
    }

    private static string WorkerPath()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    private static JsonElement RunWorker(string body, string cases, params (string Name, string Value)[] more)
    {
        string script = """
            $ErrorActionPreference='Stop'
            [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_PRESSED_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Get-AskFolded','Test-AsksMore','Test-Asks','Get-AskAliases','Note-AskingName','Get-AskingName',
                      'Test-PressesItself','Format-Name','Get-Cut','Get-Name','Get-Prop','Get-ReadableId','Get-FallbackName',
                      'Get-ShownName','Test-NameMatch','Get-LabelFolded','Get-Folded','Test-ItemHolds','Test-NameHolds','Find-Named',
                      'Test-SystemMenu','Test-SystemMenuChain','Get-LookupScope','Test-OffscreenUsable','Get-Rect')
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
        start.Environment["BAXY_PRESSED_WORKER"] = WorkerPath();
        start.Environment["BAXY_ASKS"] = JsonSerializer.Serialize(new { pattern = RiskPolicy.AsksPattern, hint = RiskPolicy.FoldHint });
        start.Environment["BAXY_CASES"] = cases;
        foreach ((string name, string value) in more)
            start.Environment[name] = value;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the worker functions answer");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output).RootElement.Clone();
    }
}
