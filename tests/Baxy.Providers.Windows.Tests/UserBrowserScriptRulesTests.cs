using System.Diagnostics;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// FT/proveedores goal (E3): the rules of the user-browser scripts that decide whether the tab strip was read whole
/// (<c>StripOf</c>, <c>StripWhole</c>, over the frame walk's <c>Children</c>) and which document is the page
/// (<c>TitledPage</c>, <c>ShownPage</c>) are taken from the scripts by their syntax tree and run on described
/// elements: no browser or window is read or touched.
/// </summary>
[TestFixture]
public sealed class UserBrowserScriptRulesTests
{
    // Described elements: a node answers Current (ControlType, Name) and GetRuntimeId; a dead one throws from every
    // method, as Opera GX's first LiveBackgroundView child does (PowerShell gives $null for its properties).
    private const string Elements = """
        Add-Type -AssemblyName UIAutomationTypes
        $CT = [System.Windows.Automation.ControlType]
        $WalkState = @{ partial = $false }
        $script:nextId = 1
        function MakeNode([string]$name, $type, [bool]$dead = $false) {
          $n = [pscustomobject]@{ name = $name; kids = (New-Object System.Collections.Generic.List[object]); parent = $null; dead = $dead; id = $script:nextId; ctype = $type }
          $script:nextId++
          $n | Add-Member -MemberType ScriptProperty -Name Current -Value { if ($this.dead) { throw 'dead element' }; [pscustomobject]@{ ControlType = $this.ctype; Name = $this.name } }
          $n | Add-Member -MemberType ScriptMethod -Name GetRuntimeId -Value { if ($this.dead) { throw 'dead element' }; return ,([int[]]@(42, $this.id)) }
          return $n
        }
        function Attach($parent, $child) { $parent.kids.Add($child); $child.parent = $parent; return $child }
        $walker = [pscustomobject]@{ deadFirstOf = @{} }
        $walker | Add-Member -MemberType ScriptMethod -Name GetFirstChild -Value { param($n) if ($n.dead -or $this.deadFirstOf.ContainsKey($n.id)) { throw 'dead element' }; if ($n.kids.Count -gt 0) { return $n.kids[0] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetLastChild -Value { param($n) if ($n.dead) { throw 'dead element' }; if ($n.kids.Count -gt 0) { return $n.kids[$n.kids.Count - 1] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetNextSibling -Value { param($n) $p = $n.parent; $i = $p.kids.IndexOf($n); if ($i + 1 -lt $p.kids.Count) { return $p.kids[$i + 1] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetPreviousSibling -Value { param($n) if ($n.dead) { throw 'dead element' }; $p = $n.parent; $i = $p.kids.IndexOf($n); if ($i -gt 0) { return $p.kids[$i - 1] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetParent -Value { param($n) if ($n.dead) { throw 'dead element' }; return $n.parent }
        function Say($value) { if ($null -eq $value) { 'none' } else { [string]$value.name } }
        function Tabs { $list = New-Object System.Collections.Generic.List[object]; foreach ($tab in $args) { $list.Add($tab) }; return ,$list }

        """;

    [Test]
    public void TheTabStripIsReadWholeThoughADeadNodeOutsideItIsNot()
    {
        const string cases = """
            # Opera GX after a Speed Dial: window > LiveBackgroundView > [dead, WindowDecoratorGx > [strip > [T1, T2,
            # island > [T3]], toolbar, page]]; the forward walk of LiveBackgroundView fails at its first child.
            $root = MakeNode 'Window' $CT::Window
            $lbv = Attach $root (MakeNode 'LiveBackgroundView' $CT::Pane)
            $null = Attach $lbv (MakeNode 'dead' $CT::Pane $true)
            $wdg = Attach $lbv (MakeNode 'WindowDecoratorGx' $CT::Pane)
            $strip = Attach $wdg (MakeNode 'TabStrip' $CT::Pane)
            $t1 = Attach $strip (MakeNode 'T1' $CT::TabItem)
            $t2 = Attach $strip (MakeNode 'T2' $CT::TabItem)
            $island = Attach $strip (MakeNode 'Island' $CT::Group)
            $t3 = Attach $island (MakeNode 'T3' $CT::TabItem)
            $null = Attach $wdg (MakeNode 'Toolbar' $CT::ToolBar)
            $null = Attach $wdg (MakeNode 'Page' $CT::Document)
            $walker.deadFirstOf[$lbv.id] = $true
            $answers = @()
            $kids = @(Children $walker $lbv)
            $answers += @([string]$kids.Count + ' ' + [string]$WalkState.partial)
            $found = StripOf $walker $root (Tabs $t1 $t2 $t3)
            $answers += @(Say $found)
            $answers += @([string](StripWhole $walker $found 3))
            $answers += @([string]$WalkState.partial)
            $answers += @([string](StripWhole $walker $found 4))
            $answers += @(Say (StripOf $walker $root (Tabs $t3)))
            # A tab of the strip that cannot be read: the strip is not whole, and a dead tab has no strip.
            $deadTab = Attach $strip (MakeNode 'deadTab' $CT::TabItem $true)
            $answers += @([string](StripWhole $walker $found 3))
            $answers += @(Say (StripOf $walker $root (Tabs $t1 $deadTab)))
            # Tabs in two places of the window: the strip is the node that holds both.
            $other = Attach $wdg (MakeNode 'Pinned' $CT::Pane)
            $t4 = Attach $other (MakeNode 'T4' $CT::TabItem)
            $answers += @(Say (StripOf $walker $root (Tabs $t1 $t4)))
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = Run(UserBrowserScripts.Frame, ["Children", "FrameKey", "StripOf", "StripWhole"], cases);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "2 True", "TabStrip", "True", "False", "False", "Island", "False", "none", "WindowDecoratorGx",
        }));
    }

    [Test]
    public void ThePageIsTheDocumentNamedAsTheWindowTitleBegins()
    {
        const string cases = """
            function Document([string]$name, [bool]$offscreen) {
              return [pscustomobject]@{ name = $name; Current = [pscustomobject]@{ Name = $name; IsOffscreen = $offscreen } }
            }
            $panel = Document 'Discord' $false
            $page = Document 'Curico - Wikipedia' $false
            $hidden = Document 'Speed Dial' $true
            $both = Tabs $panel $page
            $answers = @()
            $answers += @(Say (TitledPage $both 'Curico - Wikipedia - Opera'))
            $answers += @(Say (TitledPage $both 'Otra cosa - Opera'))
            $answers += @(Say (ShownPage (Tabs $hidden $page) $false))
            $answers += @(Say (ShownPage (Tabs $hidden) $true))
            $answers += @(Say (ShownPage (Tabs $hidden) $false))
            [Console]::Out.Write(($answers -join '|'))
            """;
        string page = Run(UserBrowserScripts.PageText, ["TitledPage", "ShownPage"], cases);
        string frame = Run(UserBrowserScripts.Frame, ["TitledPage", "ShownPage"], cases);
        Assert.Multiple(() =>
        {
            Assert.That(page.Split('|'), Is.EqualTo(new[]
            {
                "Curico - Wikipedia", "none", "Curico - Wikipedia", "Speed Dial", "none",
            }));
            Assert.That(frame, Is.EqualTo(page), "the frame read and the page read take the same page");
        });
    }

    private static string Run(string source, string[] functions, string cases)
    {
        string script = """
            $ErrorActionPreference = 'Stop'
            $tokens = $null; $errors = $null
            $ast = [System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_BROWSER_SCRIPT, [ref]$tokens, [ref]$errors)
            if ($errors.Count -gt 0) { throw 'script does not parse' }
            $wanted = @($env:BAXY_BROWSER_FUNCTIONS -split ',')
            $found = @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name }, $true))
            if ($found.Count -ne $wanted.Count) { throw 'rule functions missing' }
            foreach ($definition in $found) { . ([scriptblock]::Create($definition.Extent.Text)) }

            """ + Elements + cases;
        string file = Path.Combine(Path.GetTempPath(), "baxy-browser-script-" + Guid.NewGuid().ToString("N") + ".ps1");
        File.WriteAllText(file, source, new UTF8Encoding(true));
        try
        {
            var start = new ProcessStartInfo("powershell.exe")
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
                start.ArgumentList.Add(argument);
            start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
            start.Environment["BAXY_BROWSER_SCRIPT"] = file;
            start.Environment["BAXY_BROWSER_FUNCTIONS"] = string.Join(',', functions);
            using Process process = Process.Start(start)!;
            Task<string> error = process.StandardError.ReadToEndAsync();
            string output = process.StandardOutput.ReadToEnd();
            Assert.That(process.WaitForExit(60_000), Is.True, "the rule answers");
            Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
            return output.Trim();
        }
        finally
        {
            File.Delete(file);
        }
    }
}
