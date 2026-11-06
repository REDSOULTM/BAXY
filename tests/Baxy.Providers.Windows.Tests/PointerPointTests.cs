using System.Diagnostics;
using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Rows C5 and C6: what a pointer press of the tree's route checks at its point before the adapter presses. Three answers
/// (agent-desktop crates/core/src/adapter/hit_test.rs): it reaches the control, something else is really there, or it
/// cannot be told; only the second refuses. Measured on windows of our own (status file of uso-108-teclas): WPF, WinForms,
/// XAML and File Explorer. File Explorer's toolbar answers with an ancestor for 60 of 234 controls, so an ancestor is
/// «cannot be told», never «covered».
/// </summary>
[TestFixture]
internal sealed class PointerPointTests
{
    private const string Rig = """
        $script:Parents=@{}; $script:Hits=@{}; $script:Roots=@{}; $script:AtRoot=[IntPtr]100; $script:Iconic=$false; $script:OnScreen=$true; $script:InFront=$true
        function Get-ParentOf($node){ return $script:Parents[[string]$node] }
        function Test-SameElement($a,$b){ return [string]$a -eq [string]$b }
        function Get-ElementAt($point){ $key="$($point.x),$($point.y)"; if($script:Hits.ContainsKey($key)){ return $script:Hits[$key] }; return $script:Hits['*'] }
        function Test-TopIconic([IntPtr]$top){ return $script:Iconic }
        function Test-PointOnScreen($point){ return $script:OnScreen }
        function Get-RootWindowAt($point){ return $script:AtRoot }
        function Get-RootWindowOf($el){ if($script:Roots.ContainsKey([string]$el)){ return $script:Roots[[string]$el] }; return [IntPtr]100 }
        function Test-InFront([IntPtr]$top){ return $script:InFront }
        $rect=@{ x=100; y=200; w=40; h=20 }
        function Say($verdict){ [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @([string]$verdict))) }

        """;

    private const string Inside = "$point=@{ x=120; y=210 }\n";

    [TestCase("$script:Hits['*']='boton'", "reaches", TestName = "the control itself reaches")]
    [TestCase("$script:Hits['*']='texto'; $script:Parents['texto']='a'; $script:Parents['a']='b'; $script:Parents['b']='c'; $script:Parents['c']='d'; $script:Parents['d']='boton'", "reaches", TestName = "something deep inside it reaches, past the old four levels")]
    [TestCase("$script:Hits['*']='ventana'; $script:Parents['boton']='panel'; $script:Parents['panel']='ventana'", "unknown", TestName = "an ancestor of it cannot be told")]
    [TestCase("$script:Hits['*']=$null", "unknown", TestName = "no hit cannot be told")]
    [TestCase("$script:Hits['*']='vecino'", "covered", TestName = "another control of the same window covers")]
    [TestCase("$script:Hits['*']='ajena'; $script:Roots['ajena']=[IntPtr]200; $script:AtRoot=[IntPtr]200", "covered", TestName = "another window in front of a window in front covers when both opinions agree")]
    [TestCase("$script:Hits['*']='ajena'; $script:Roots['ajena']=[IntPtr]200; $script:AtRoot=[IntPtr]200; $script:InFront=$false", "unknown", TestName = "another window over a window behind cannot be told: the lease brings it up and checks again")]
    [TestCase("$script:Hits['*']='ajena'; $script:Roots['ajena']=[IntPtr]200; $script:AtRoot=[IntPtr]300", "unknown", TestName = "three different roots cannot be told")]
    [TestCase("$script:Hits['*']='ajena'; $script:Roots['ajena']=$null", "unknown", TestName = "an unreadable root cannot be told")]
    [TestCase("$script:Hits['*']='vecino'; $script:Iconic=$true", "unknown", TestName = "a minimized window cannot be told")]
    [TestCase("$script:Hits['*']='vecino'; $script:OnScreen=$false", "unknown", TestName = "a point off the screen cannot be told")]
    [TestCase("$script:Hits['*']='vecino'; $point=@{ x=140; y=210 }", "unknown", TestName = "a point on the far edge is outside the control")]
    [TestCase("$script:Hits['*']='vecino'; $point=@{ x=120; y=220 }", "unknown", TestName = "a point on the bottom edge is outside the control")]
    [TestCase("$script:Hits['*']='vecino'; $rect=@{ x=100; y=200; w=0; h=20 }", "unknown", TestName = "a control without area cannot be told")]
    public void ThePointAnswersOneOfThree(string setup, string expected)
    {
        JsonElement answer = Run(Rig + Inside + setup + "\nSay (Get-PointVerdict 'boton' $point $rect ([IntPtr]100))");
        Assert.That(answer[0].GetString(), Is.EqualTo(expected));
    }

    [Test]
    public void AHitReadingThatFailsWhileClimbingCannotBeTold()
    {
        JsonElement answer = Run(Rig + Inside
            + "$script:Hits['*']='texto'\nfunction Get-ParentOf($node){ throw 'gone' }\nSay (Get-PointVerdict 'boton' $point $rect ([IntPtr]100))");
        Assert.That(answer[0].GetString(), Is.EqualTo("unknown"));
    }

    private const string PointerRig = Rig + """
        function Get-CurrentRect($el){ return $script:Box }
        function Get-ClickablePointOf($el){ return $script:Clickable }
        function Get-ScrollViewport($el){ return $script:View }
        $script:Box=@{ x=62; y=190; w=398; h=20 }; $script:Clickable=$null; $script:View=$null
        function Show($press){ [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @{ x=$(if($press.point){ $press.point.x } else { -1 }); y=$(if($press.point){ $press.point.y } else { -1 }); covered=[bool]$press.covered })) }

        """;

    // A18-2's straddler: item 62,190,399,20 in list 60,208,420,140, 2 px visible. The neighbour is at its centre.
    [Test]
    public void ARowCutByItsListLandsOnItsVisiblePart()
    {
        JsonElement answer = Run(PointerRig + """
            $script:View=@{ x=60; y=208; w=420; h=140 }
            $script:Hits['261,200']='vecina'
            $script:Hits['261,209']='fila'
            Show (Get-PointerPoint 'fila' ([IntPtr]100))
            """);
        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("x").GetInt32(), Is.EqualTo(261));
            Assert.That(answer.GetProperty("y").GetInt32(), Is.EqualTo(209));
            Assert.That(answer.GetProperty("covered").GetBoolean(), Is.False);
        });
    }

    // The provider's clickable point, measured right on WPF's cut rows (4 px visible), comes first when it is visible.
    [Test]
    public void TheClickablePointComesFirstWhenItIsInTheVisiblePart()
    {
        JsonElement answer = Run(PointerRig + """
            $script:View=@{ x=60; y=200; w=420; h=140 }
            $script:Clickable=@{ x=300; y=204 }
            $script:Hits['*']='vecina'
            $script:Hits['300,204']='fila'
            Show (Get-PointerPoint 'fila' ([IntPtr]100))
            """);
        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("x").GetInt32(), Is.EqualTo(300));
            Assert.That(answer.GetProperty("y").GetInt32(), Is.EqualTo(204));
        });
    }

    // A clickable point out of the visible part is passed over without asking there.
    [Test]
    public void AClickablePointOutOfTheVisiblePartIsPassedOver()
    {
        JsonElement answer = Run(PointerRig + """
            $script:View=@{ x=60; y=208; w=420; h=140 }
            $script:Clickable=@{ x=261; y=200 }
            $script:Hits['261,200']='vecina'
            $script:Hits['261,209']='fila'
            Show (Get-PointerPoint 'fila' ([IntPtr]100))
            """);
        Assert.That(answer.GetProperty("y").GetInt32(), Is.EqualTo(209));
    }

    // Five points: the centre taken by a child layer of the same window, a quarter point reaches.
    [Test]
    public void AnotherOfTheFivePointsReachesWhenTheCentreIsCovered()
    {
        JsonElement answer = Run(PointerRig + """
            $script:Box=@{ x=100; y=200; w=40; h=20 }
            $script:Hits['120,210']='capa'
            $script:Hits['110,205']='boton'
            Show (Get-PointerPoint 'boton' ([IntPtr]100))
            """);
        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("x").GetInt32(), Is.EqualTo(110));
            Assert.That(answer.GetProperty("y").GetInt32(), Is.EqualTo(205));
            Assert.That(answer.GetProperty("covered").GetBoolean(), Is.False);
        });
    }

    [Test]
    public void AControlReallyCoveredAtEveryPointIsCovered()
    {
        JsonElement answer = Run(PointerRig + """
            $script:Box=@{ x=100; y=200; w=40; h=20 }
            $script:Hits['*']='capa'
            Show (Get-PointerPoint 'boton' ([IntPtr]100))
            """);
        Assert.That(answer.GetProperty("covered").GetBoolean(), Is.True);
    }

    // Unknown blocks only when some other point was really covered (agent-desktop actionability/receives_events.rs).
    [Test]
    public void OneCoveredPointAmongUnknownOnesIsCovered()
    {
        JsonElement answer = Run(PointerRig + """
            $script:Box=@{ x=100; y=200; w=40; h=20 }
            $script:Parents['boton']='ventana'
            $script:Hits['*']='ventana'
            $script:Hits['130,205']='capa'
            Show (Get-PointerPoint 'boton' ([IntPtr]100))
            """);
        Assert.That(answer.GetProperty("covered").GetBoolean(), Is.True);
    }

    // Contracases, what today's press does stays. An ancestor at every point (File Explorer's toolbar, Chromium's render
    // host): the press goes at its first point, as before.
    [Test]
    public void AnAncestorAtEveryPointPressesItsFirstPointAsBefore()
    {
        JsonElement answer = Run(PointerRig + """
            $script:Box=@{ x=100; y=200; w=40; h=20 }
            $script:Parents['boton']='ventana'
            $script:Hits['*']='ventana'
            Show (Get-PointerPoint 'boton' ([IntPtr]100))
            """);
        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("x").GetInt32(), Is.EqualTo(120));
            Assert.That(answer.GetProperty("y").GetInt32(), Is.EqualTo(210));
            Assert.That(answer.GetProperty("covered").GetBoolean(), Is.False);
        });
    }

    // AD shipped this regression (scroll_into_view_tests.rs: reading a missing viewport as hidden "failed every on-screen
    // row in File Explorer's tree"): with no viewport the rectangle counts whole.
    [Test]
    public void WithNoViewportTheRectangleCountsWhole()
    {
        JsonElement answer = Run(PointerRig + """
            $script:Box=@{ x=100; y=200; w=40; h=20 }
            $script:View=$null
            $script:Hits['*']='fila'
            Show (Get-PointerPoint 'fila' ([IntPtr]100))
            """);
        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("x").GetInt32(), Is.EqualTo(120));
            Assert.That(answer.GetProperty("y").GetInt32(), Is.EqualTo(210));
        });
    }

    // A viewport it does not touch says nothing of where the control is (a list read in another place): the rectangle.
    [Test]
    public void AViewportThatDoesNotTouchItIsNotUsed()
    {
        JsonElement answer = Run(PointerRig + """
            $script:Box=@{ x=100; y=200; w=40; h=20 }
            $script:View=@{ x=500; y=500; w=100; h=100 }
            $script:Hits['*']='fila'
            Show (Get-PointerPoint 'fila' ([IntPtr]100))
            """);
        Assert.That(answer.GetProperty("x").GetInt32(), Is.EqualTo(120));
    }

    // Get-PressPoint's own fallback (the message and render routes): the provider has no point, the centre of what shows.
    [Test]
    public void ThePressPointFallsBackToTheCentreOfTheVisiblePart()
    {
        JsonElement answer = Run(PointerRig + """
            $fake=[pscustomobject]@{ Current=[pscustomobject]@{ BoundingRectangle=(New-Object System.Windows.Rect(62,190,398,20)) } }
            $fake | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { throw 'no clickable point' }
            $script:View=@{ x=60; y=208; w=420; h=140 }
            $cut=Get-PressPoint $fake
            $script:View=$null
            $whole=Get-PressPoint $fake
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @($cut.y,$whole.y)))
            """);
        Assert.Multiple(() =>
        {
            Assert.That(answer[0].GetInt32(), Is.EqualTo(209));
            Assert.That(answer[1].GetInt32(), Is.EqualTo(200));
        });
    }

    private static JsonElement Run(string body)
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = """
            $ErrorActionPreference='Stop'
            [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
            Add-Type -AssemblyName WindowsBase
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_WORKER_PATH,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Get-PressPoint','Get-PointVerdict','Get-PointerPoint','Get-VisiblePart','Get-PressCandidates')
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
        start.Environment["BAXY_WORKER_PATH"] = worker;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the worker functions answer");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output).RootElement.Clone();
    }
}
