using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Review 1 of ronda 21 (finding 4): the worker's search for a control by its name walks what is shown within its own
/// deadline. A walk cut by that deadline proves neither that the control is missing nor that the one it found is the
/// only one with that label (a long list read with all its rows, the row «Windows Update» before the cut and a link with
/// the same label in the detail pane after it): the click answers <c>visible_lookup_timeout</c> before anything is
/// pressed. <c>Do-Click</c> is taken from the script by its syntax tree and run on described elements: no window is
/// read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseLookupDeadlineTests
{
    [Test]
    public void ANameSearchCutByItsDeadlineNeverPressesWhatItFound()
    {
        const string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_FRAME_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Do-Click','Do-ClickJudged','Get-AskingName','Test-NamedLookupCut')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne $wanted.Count){ throw 'rule functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }
            function Read-RenderHosts($request){ return @() }
            function Get-Root([long]$hwnd){ return @{ root=[pscustomobject]@{ Name='Configuracion' }; hwnd=[IntPtr]42 } }
            function Get-Name($el){ return 'Configuracion' }
            function Get-UnfilteredBox($root){ return $null }
            function Get-ClientRootFor($hwnd){ return $null }
            function Test-NameMatch($name,$aliases){ return $true }
            function Test-ItemHolds($el,$aliases){ return $false }
            function Get-ShownName($el){ return @{ name=[string]$el.Name } }
            function Get-Id($el){ return [string]$el.Id }
            # Past the guard the click reads the control's toggle state: the case says it got that far.
            function Get-Toggle($el){ throw 'pressing' }
            function Click-Result($ok,$verified,$code,$name,$identity,$a,$b,$c,$kind){ return @{ error=[string]$code } }
            function Find-Named($root,$aliases,$offscreenBox=$null){ $script:LookupPartial=$script:CutWalk; return $script:NamedHits }
            function Find-ById($root,$controlId){ $script:LookupPartial=$script:CutWalk; return $script:FoundById }
            # Ronda 21 (vista ordenada): the identity's same-named lineage; the row stands alone in it.
            function Resolve-ByIdLineage($byId){ return @{ target=$byId; lineage=@() } }
            $row=[pscustomobject]@{ Id='7.1'; Name='Windows Update'; Current=[pscustomobject]@{ ControlType=[pscustomobject]@{ ProgrammaticName='ControlType.DataItem' } } }
            function Say($request){
              try { return [string](Do-Click $request).error } catch { return [string]$_.Exception.Message }
            }
            $nameRequest=[pscustomobject]@{ aliases=@('Windows Update'); controlId=''; manner=''; hwnd=42 }
            $idRequest=[pscustomobject]@{ aliases=@('Windows Update'); controlId='7.1'; manner=''; hwnd=42 }
            $answers=@()
            # The walk was cut and found one row by that name: no press.
            $script:CutWalk=$true; $script:NamedHits=@($row); $script:FoundById=$null
            $answers+=@(Say $nameRequest)
            # The walk was cut and found nothing: no press either (nor the native search for it).
            $script:NamedHits=@()
            $answers+=@(Say $nameRequest)
            # Counter-case: the whole walk found one row by that name: it is pressed.
            $script:CutWalk=$false; $script:NamedHits=@($row)
            $answers+=@(Say $nameRequest)
            # Counter-case: the identity the view gave is one control, found within a cut walk: it is pressed.
            $script:CutWalk=$true; $script:FoundById=$row
            $answers+=@(Say $idRequest)
            # The identity was not found within a cut walk: the search says it ran out of time, not that it is stale.
            $script:FoundById=$null
            $answers+=@(Say $idRequest)
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = RunScript(script);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "visible_lookup_timeout", "visible_lookup_timeout", "pressing", "pressing", "visible_lookup_timeout",
        }));
    }

    /// <summary>
    /// Integration of ronda 21 kept no second search of the whole tree after a view cut by its deadline: that search,
    /// with no deadline of its own, would eat the margin the deadline keeps before the host kills the worker (the good
    /// view would be lost). Ronda 25 (latency) keeps no second search at all: the instrument that counted tabs offscreen
    /// inside the window is gone (no code read it) and the disabled controls come in the view's one walk. Do-View walks
    /// the tree once, through Get-ShownDescendants with whether it wants the disabled ones, and neither it nor
    /// Get-DisabledShown searches the tree again, cut walk or whole.
    /// </summary>
    [Test]
    public void AViewWalksTheTreeOnce()
    {
        const string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_FRAME_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $functions=@{}
            foreach($node in @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] },$true))){ $functions[$node.Name]=$node }
            if(-not $functions.ContainsKey('Do-View') -or -not $functions.ContainsKey('Get-DisabledShown')){ throw 'rule functions missing' }
            function Searches($function){
              return @($function.FindAll({ param($node) $node -is [System.Management.Automation.Language.InvokeMemberExpressionAst] -and @('FindAll','FindFirst') -contains [string]$node.Member.Value },$true)).Count
            }
            function Calls($function,[string]$name){
              return @($function.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq $name },$true))
            }
            $walks=@(Calls $functions['Do-View'] 'Get-ShownDescendants')
            $handsDimmed=($walks.Count -eq 1 -and @($walks[0].CommandElements | Where-Object { $_ -is [System.Management.Automation.Language.VariableExpressionAst] -and $_.VariablePath.UserPath -eq 'withDimmed' }).Count -eq 1)
            $answers=@(
              [string]$handsDimmed,
              [string](Searches $functions['Do-View']),
              [string](Searches $functions['Get-DisabledShown']),
              [string]@(Calls $functions['Do-View'] 'Get-Descendants').Count,
              [string]$functions.ContainsKey('Measure-OffscreenInside'))
            [Console]::Out.Write(($answers -join '|'))
            """;
        Assert.That(RunScript(script), Is.EqualTo("True|0|0|0|False"));
    }

    private static string RunScript(string script)
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
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the rule answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
