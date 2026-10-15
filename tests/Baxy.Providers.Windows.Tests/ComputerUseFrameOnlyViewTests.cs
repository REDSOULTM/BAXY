using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 20b, palanca 8 (pasada r18): a look that brings only the window's frame is no window. v3-51: the modal dialog
/// «Añadir escena» of a Qt application was read with its TitleBar and «Cerrar» alone; its content hung from the owner
/// window's tree. v3-62: a packaged application was read with its frame (three caption buttons named «Minimizar
/// Seguridad de Windows»…, its title as Text and Window, and the system menu chain) before its content came. The
/// worker's rules (<c>Test-FrameOnly</c>, which decides the reread, and <c>Measure-ClientPieces</c>, which decides
/// whether a reread brought content inside the dialog) are taken from the script by its syntax tree and run on
/// described controls: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseFrameOnlyViewTests
{
    // A title bar 600 px wide at the top of a dialog at (100,100) 600×400.
    private const string Bar = """{"kind":"TitleBar","rect":{"x":100,"y":100,"w":600,"h":30}}""";

    [Test]
    public void AViewOfTheFrameAloneIsReadAgainAndOneWithContentIsNot()
    {
        string cases = "[" + string.Join(",",
            // v3-51, as read: the dialog's title bar and its close button.
            $$$"""[{{{Bar}}},{"kind":"Button","rect":{"x":660,"y":102,"w":36,"h":26}}]""",
            // v3-62, as read: three caption buttons, the title as Text, two Windows, the system menu bar and its item.
            $$$"""[{{{Bar}}},{"kind":"Button","rect":{"x":580,"y":100,"w":40,"h":30}},{"kind":"Button","rect":{"x":620,"y":100,"w":40,"h":30}},{"kind":"Button","rect":{"x":660,"y":100,"w":40,"h":30}},{"kind":"Text","rect":{"x":130,"y":105,"w":150,"h":20}},{"kind":"Window","rect":{"x":100,"y":100,"w":600,"h":400}},{"kind":"Window","rect":{"x":100,"y":100,"w":600,"h":400}},{"kind":"MenuBar","rect":{"x":100,"y":100,"w":28,"h":28}},{"kind":"MenuItem","rect":{"x":100,"y":100,"w":28,"h":28}}]""",
            // A really empty window (a game's canvas): the frame and a pane; it is read again once, then as today.
            $$$"""[{{{Bar}}},{"kind":"Button","rect":{"x":660,"y":102,"w":36,"h":26}},{"kind":"Pane","rect":{"x":100,"y":130,"w":600,"h":370}}]""",
            // A «Save as» dialog whose tree brings its client: never read again.
            $$$"""[{{{Bar}}},{"kind":"Button","rect":{"x":660,"y":102,"w":36,"h":26}},{"kind":"Edit","rect":{"x":200,"y":400,"w":300,"h":24}},{"kind":"Button","rect":{"x":500,"y":450,"w":80,"h":24}}]""",
            // A message box: its text and its button below the title bar.
            $$$"""[{{{Bar}}},{"kind":"Text","rect":{"x":150,"y":200,"w":300,"h":20}},{"kind":"Button","rect":{"x":500,"y":450,"w":80,"h":24}}]""",
            // A window with no title bar exposed (a custom frame): nothing tells its frame apart.
            """[{"kind":"Button","rect":{"x":660,"y":102,"w":36,"h":26}}]""",
            // An application's own menu bar below the title bar (a notepad): content.
            $$$"""[{{{Bar}}},{"kind":"MenuBar","rect":{"x":100,"y":130,"w":600,"h":20}},{"kind":"MenuItem","rect":{"x":100,"y":130,"w":50,"h":20}}]""",
            // An empty look: no frame to judge.
            "[]") + "]";
        string answer = Run("Test-FrameOnly", cases, string.Empty);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "True", "True", "True", "False", "False", "False", "False", "False" }));
    }

    [Test]
    public void AReadUnderTheOwnerCountsOnlyWhatLiesInsideTheDialog()
    {
        const string box = """{"x":100,"y":100,"w":600,"h":400}""";
        string cases = "[" + string.Join(",",
            // v3-51 under the owner: the scene's name field and the dialog's buttons, inside the dialog.
            """[{"kind":"Edit","rect":{"x":150,"y":200,"w":400,"h":24}},{"kind":"Button","rect":{"x":450,"y":450,"w":80,"h":24}},{"kind":"Button","rect":{"x":550,"y":450,"w":80,"h":24}}]""",
            // The main window's controls around the dialog: none of them counts.
            """[{"kind":"Button","rect":{"x":10,"y":10,"w":80,"h":24}},{"kind":"ListItem","rect":{"x":720,"y":300,"w":100,"h":20}},{"kind":"Button","rect":{"x":650,"y":480,"w":100,"h":40}}]""",
            // Only the dialog's frame and a pane again: no content.
            $$$"""[{{{Bar}}},{"kind":"Button","rect":{"x":660,"y":102,"w":36,"h":26}},{"kind":"Pane","rect":{"x":100,"y":130,"w":600,"h":370}}]""") + "]";
        string answer = Run("Measure-ClientPieces", cases, box);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "3", "0", "0" }));
    }

    // Review of palanca 8 (finding 3): the reread «same root without the IsOffscreen filter» offered controls the tree
    // marks offscreen (v3-62: a packaged application marking its content offscreen while it draws it). Find-ById (the
    // way of the click by id, the field, the scroll and the locate) and the click by name take them when the last view
    // of that window came from that reread and the control lies inside the window's box. Contracases: a view read with
    // the filter, a control outside the box, the last view of another window. Run on described elements.
    [Test]
    public void AControlOfferedFromTheUnfilteredRereadCanBeActedOn()
    {
        const string script = """
            $ErrorActionPreference='Stop'
            Add-Type -AssemblyName UIAutomationClient
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_FRAME_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Test-RectWithin','Test-OffscreenUsable','Get-UnfilteredBox','Find-ById','Find-Named','Test-NameMatch','Get-LookupScope')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne $wanted.Count){ throw 'rule functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }
            function Get-WindowBox([IntPtr]$hwnd){ return @{ x=100; y=100; w=600; h=400 } }
            function Get-Id($el){ return [string]$el.Id }
            function Get-Rect($el){ return $el.Rect }
            function Get-CurrentRect($el){ return $el.Rect }
            function Get-Descendants($root){ return $script:Items }
            # Ronda 21: without the unfiltered box the search walks what is shown within its deadline (here, whole).
            function Get-ShownDescendants($root,[long]$hwnd=0,[double]$seconds=0){ return $script:Items }
            function Get-ShownName($el){ return @{ name=[string]$el.Name } }
            function Test-SystemMenu($el){ return $false }
            function Test-ItemHolds($el,$aliases){ return $false }
            function Merge-SharedViews($m){ return $m }
            function New-Item2($id,$name,$offscreen,$rect){
              return [pscustomobject]@{ Id=$id; Name=$name; Rect=$rect; Cached=@{ IsOffscreen=$offscreen }; Current=@{ IsOffscreen=$offscreen; IsEnabled=$true } }
            }
            $inside=@{ x=150; y=200; w=300; h=40 }
            $outside=@{ x=900; y=200; w=300; h=40 }
            $firewall=New-Item2 '1.2.3' 'Firewall y proteccion de red' $true $inside
            $walked=New-Item2 '1.2.4' 'Proteccion contra virus' $true $inside
            $away=New-Item2 '1.2.5' 'Fuera' $true $outside
            $script:Items=@($walked,$away)
            $root=[pscustomobject]@{ Current=@{ NativeWindowHandle=42 } }
            $answers=@()
            function Say($value){ if($null -eq $value){ 'none' } else { [string]$value.Name } }
            $script:LastView=@{ hwnd=[IntPtr]42; elements=@{ '1.2.3'=$firewall }; client=$null; unfiltered=$true }
            $answers+=@(Say (Find-ById $root '1.2.3'))
            $answers+=@(Say (Find-ById $root '1.2.4'))
            $answers+=@(Say (Find-ById $root '1.2.5'))
            $answers+=@(Say (@(Find-Named $root @('Proteccion contra virus') (Get-UnfilteredBox $root)) | Select-Object -First 1))
            $answers+=@(Say (@(Find-Named $root @('Proteccion contra virus')) | Select-Object -First 1))
            $script:LastView=@{ hwnd=[IntPtr]42; elements=@{ '1.2.3'=$firewall }; client=$null; unfiltered=$false }
            $answers+=@(Say (Find-ById $root '1.2.3'))
            $answers+=@(Say (Find-ById $root '1.2.4'))
            $script:LastView=@{ hwnd=[IntPtr]77; elements=@{ '1.2.3'=$firewall }; client=$null; unfiltered=$true }
            $answers+=@(Say (Find-ById $root '1.2.3'))
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = RunScript(script, new Dictionary<string, string>());
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "Firewall y proteccion de red", "Proteccion contra virus", "none",
            "Proteccion contra virus", "none",
            "none", "none",
            "none",
        }));
    }

    private static string Run(string rule, string cases, string box)
    {
        const string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_FRAME_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Test-RectWithin','Test-CenterWithin','Test-FramePiece','Test-FrameOnly','Measure-ClientPieces')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne $wanted.Count){ throw 'rule functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }
            $cases=[System.IO.File]::ReadAllText($env:BAXY_FRAME_CASES,[System.Text.Encoding]::UTF8) | ConvertFrom-Json
            $box=$null; if($env:BAXY_FRAME_BOX){ $box=$env:BAXY_FRAME_BOX | ConvertFrom-Json }
            $answers=@()
            foreach($case in $cases){
              $pieces=@($case | ForEach-Object { $_ })
              if($env:BAXY_FRAME_RULE -eq 'Test-FrameOnly'){ $answers+=@([string](Test-FrameOnly $pieces)) }
              else { $answers+=@([string](Measure-ClientPieces $pieces $box)) }
            }
            [Console]::Out.Write(($answers -join ','))
            """;
        string casesFile = Path.Combine(Path.GetTempPath(), "baxy-frame-" + Guid.NewGuid().ToString("N") + ".json");
        File.WriteAllText(casesFile, cases, new UTF8Encoding(false));
        try
        {
            return RunScript(script, new Dictionary<string, string>
            {
                ["BAXY_FRAME_CASES"] = casesFile,
                ["BAXY_FRAME_RULE"] = rule,
                ["BAXY_FRAME_BOX"] = box,
            });
        }
        finally
        {
            File.Delete(casesFile);
        }
    }

    private static string RunScript(string script, Dictionary<string, string> environment)
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
        {
            start.ArgumentList.Add(argument);
        }

        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        start.Environment["BAXY_FRAME_WORKER"] = worker;
        foreach ((string key, string value) in environment)
        {
            start.Environment[key] = value;
        }

        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the rule answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
