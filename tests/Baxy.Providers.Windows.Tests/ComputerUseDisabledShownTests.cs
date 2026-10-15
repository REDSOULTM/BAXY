using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 24 (pasada r23 v3-27): the list of the actionables a window shows disabled («Copiar» of a character map waiting
/// for text) always reached the mind empty. Do-View wrapped the function's answer in <c>@()</c> while the function
/// returned its list wrapped by the comma, so the line went out as <c>"disabled":[[{…}]]</c> and the adapter, which
/// skips what is no object, kept nothing. Ronda 25 (latency): the disabled controls come in the view's one walk of the
/// tree and Do-View sets them apart; Get-DisabledShown searches nothing of its own. These tests run the worker's own
/// code, taken by its syntax tree: the real statement of Do-View that splits the walk, the real Get-DisabledShown, the
/// real statement of Do-View that fills <c>$disabled</c> and the real Send-Line that serializes the answer; the line it
/// writes is what the adapter parses. No window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseDisabledShownTests
{
    // The worker's helpers the function reads, described: the view's walk, one enabled «Aceptar» before the disabled
    // controls described by kind and name. Asked to search the tree itself, a control throws: nothing searches again.
    private const string Prelude = """
        Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
        $script:DisabledShownTree=150;$script:DisabledShownMax=12
        $Actionable=@('Button','MenuItem','ListItem','Edit','Document')
        $script:Cache=New-Object psobject
        $script:Cache | Add-Member -MemberType ScriptMethod -Name Activate -Value { $done=New-Object psobject; $done | Add-Member -MemberType ScriptMethod -Name Dispose -Value {}; return $done }
        function Get-ShownName($item){ return @{ name=$item.Shown } }
        function Get-Rect($item){ return @{ x=10; y=20; w=80; h=24 } }
        function New-Control($kind,$name,$enabled){
          $control=[pscustomobject]@{ Shown=$name; Cached=[pscustomobject]@{ IsEnabled=$enabled; ControlType=[pscustomobject]@{ ProgrammaticName=('ControlType.'+$kind) } } }
          $control | Add-Member -MemberType ScriptMethod -Name FindAll -Value { param($scope,$condition) throw 'a second search of the tree' }
          return $control
        }
        function New-Walk($described){
          $walk=New-Object System.Collections.Generic.List[object]
          $walk.Add((New-Control 'Button' 'Aceptar' $true))
          foreach($pair in $described){ $walk.Add((New-Control $pair[0] $pair[1] $false)) }
          return ,$walk
        }

        """;

    [Test]
    public void OneDisabledButtonReachesTheAdapterAsAControl()
    {
        List<string> names = Disabled("""@(,@('Button','Copiar'))""", requested: true, out List<string> enabled);
        Assert.That(names, Is.EqualTo(new[] { "Button|Copiar" }));
        // The rest of the view reads only the enabled controls of the same walk, as before.
        Assert.That(enabled, Is.EqualTo(new[] { "Aceptar" }));
    }

    [Test]
    public void SeveralDisabledControlsReachTheAdapterFlat()
    {
        List<string> names = Disabled("""@(@('Button','Copiar'),@('Button','Buscar'),@('Edit','Campo'))""", requested: true, out _);
        // A field is no actionable that waits: the function leaves it out, as before.
        Assert.That(names, Is.EqualTo(new[] { "Button|Copiar", "Button|Buscar" }));
    }

    // Contracase: a look that does not ask for them (a burst with the front lent) and a tree with none send an empty list.
    [Test]
    public void ALookThatDoesNotAskOrATreeWithNoneSendsNothing()
    {
        Assert.That(Disabled("""@(,@('Button','Copiar'))""", requested: false, out _), Is.Empty);
        Assert.That(Disabled("@()", requested: true, out List<string> enabled), Is.Empty);
        Assert.That(enabled, Is.EqualTo(new[] { "Aceptar" }));
    }

    private static List<string> Disabled(string described, bool requested, out List<string> enabled)
    {
        string line = Run(Prelude + $$"""
            $all=New-Walk {{described}}
            $seen=@{}
            $withDimmed=${{(requested ? "true" : "false")}}
            $dimmed=New-Object System.Collections.Generic.List[object]
            . ([scriptblock]::Create($env:BAXY_SPLIT_STATEMENT))
            $disabled=@()
            . ([scriptblock]::Create($env:BAXY_DISABLED_STATEMENT))
            Send-Line @{ ok=$true; error=''; controls=@(); disabled=$disabled; enabled=@($all | ForEach-Object { [string]$_.Shown }) }
            """);
        using JsonDocument answer = JsonDocument.Parse(line);
        enabled = answer.RootElement.GetProperty("enabled").EnumerateArray().Select(name => name.GetString() ?? "").ToList();
        return WindowsVisibleControlAdapter.ParseControls(answer.RootElement, "disabled")
            .Select(control => control.Kind + "|" + control.Name)
            .ToList();
    }

    private static string Worker()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    private static string Run(string body)
    {
        // The functions by name, and Do-View's own statements that split the walk and fill $disabled.
        string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_VIEW_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            foreach($name in @('Get-DisabledShown','Send-Line')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
              if($found.Count -ne 1){ throw ('function missing: '+$name) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            $view=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Do-View' },$true))
            if($view.Count -ne 1){ throw 'Do-View missing' }
            $statement=@($view[0].Body.FindAll({ param($node) $node -is [System.Management.Automation.Language.IfStatementAst] -and $node.Extent.Text -match 'Get-DisabledShown' },$true))
            if($statement.Count -ne 1){ throw 'the statement that fills disabled is missing' }
            $env:BAXY_DISABLED_STATEMENT=$statement[0].Extent.Text
            $split=@($view[0].Body.FindAll({ param($node) $node -is [System.Management.Automation.Language.IfStatementAst] -and $node.Extent.Text -match '\$lit=New-Object' },$true))
            if($split.Count -ne 1){ throw 'the statement that splits the walk is missing' }
            $env:BAXY_SPLIT_STATEMENT=$split[0].Extent.Text

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
        {
            start.ArgumentList.Add(argument);
        }

        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8\n" + script)));
        start.Environment["BAXY_VIEW_WORKER"] = Worker();
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
