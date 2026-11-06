using System.Collections;
using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-108: what the comparison with agent-desktop found about what a look and a refused click tell the model. A refusal
/// raised before any press never reads «may have happened», and a fault of the reader never reads as an empty window.
/// </summary>
[TestFixture]
public sealed partial class ComputerUseHonestLookTests
{
    private const string Ambiguous =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_ambiguous\",\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}";

    private const string NotFound =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\",\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}";

    private const string Disabled =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_control_disabled\",\"name\":\"Siguiente\",\"kind\":\"Button\",\"controlIdentity\":\"1.2\",\"absentOrDisabled\":false}";

private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static readonly VisibleClickTiming Quick = VisibleClickTiming.Default with
    {
        SettledLabel = TimeSpan.FromMilliseconds(60),
        Interval = TimeSpan.FromMilliseconds(20),
    };

    private static void RememberView(WindowsVisibleControlAdapter adapter, nint window, params (int Index, string Kind, string Name)[] shown)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        var controls = (IList)Activator.CreateInstance(
            typeof(List<>).MakeGenericType(typeof(WindowsVisibleControlAdapter.ViewControl)))!;
        foreach ((int index, string kind, string name) in shown)
            controls.Add(new WindowsVisibleControlAdapter.ViewControl { Index = index, Kind = kind, Name = name, Id = "1." + index });
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [window, controls], null)!;
        field.SetValue(adapter, view);
    }

    private sealed class CountingLocator : IVisibleControlLocator
    {
        public int Calls { get; private set; }

        public string Stage => "ocr";

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            Calls++;
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
        }
    }

    [Test]
    public void TwoControlsWithTheLabelPressNothingSayItAndNameThem()
    {
        nint window = PumpedWindow.Create("BAXY ambiguous fixture");
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(Ambiguous, Ambiguous);
            var ocr = new CountingLocator();
            var adapter = new WindowsVisibleControlAdapter(worker, ocr, ocr, timing: Quick);
            RememberView(adapter, window, (4, "Button", "Buscar"), (9, "Edit", "Buscar"), (2, "Button", "Otra"));

            ExternalCapabilityReceipt receipt = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Buscar\",\"window\":" + (long)window + "}"), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_ambiguous"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.False, "nothing was pressed: never «pudo o no ocurrir»");
                Assert.That(ocr.Calls, Is.Zero, "no later stage presses one of the twins");
                Assert.That(receipt.Result?.GetProperty("candidates").EnumerateArray().Select(static item => item.GetString()),
                    Is.EqualTo(new[] { "[4] Button «Buscar»", "[9] Edit «Buscar»" }));
            });
        }
        finally
        {
            PumpedWindow.Destroy(window);
        }
    }

    // Seen once with the person's browser in front: a click on a test window answered with `closest` of the other window.
    // What a look read of one window never goes in the receipt of a click on another.
    [TestCase(Ambiguous, "candidates", "[4] Button «Buscar»")]
    [TestCase(NotFound, "closest", "[4] Button «Buscar algo»")]
    public void TheHintsOfARefusedClickComeOnlyFromTheWindowItsLookRead(string answer, string field, string entry)
    {
        nint clicked = PumpedWindow.Create("BAXY clicked fixture");
        nint other = PumpedWindow.Create("BAXY other fixture");
        try
        {
            (int, string, string) shown = (4, "Button", answer == Ambiguous ? "Buscar" : "Buscar algo");

            var elsewhere = new WindowsVisibleControlAdapter(
                new ComputerUsePerceptionTests.ScriptedUiaWorker(answer, answer), new CountingLocator(), new CountingLocator(), timing: Quick);
            RememberView(elsewhere, other, shown);
            ExternalCapabilityReceipt leaked = elsewhere.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Buscar\",\"window\":" + (long)clicked + "}"), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            var here = new WindowsVisibleControlAdapter(
                new ComputerUsePerceptionTests.ScriptedUiaWorker(answer, answer), new CountingLocator(), new CountingLocator(), timing: Quick);
            RememberView(here, clicked, shown);
            ExternalCapabilityReceipt told = here.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Buscar\",\"window\":" + (long)clicked + "}"), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(leaked.Result?.GetRawText() ?? string.Empty, Does.Not.Contain("Buscar"), "nothing of the other window");
                Assert.That(told.Result?.GetProperty(field).EnumerateArray().Select(static item => item.GetString()),
                    Does.Contain(entry), "control: its own window's look still helps");
            });
        }
        finally
        {
            PumpedWindow.Destroy(clicked);
            PumpedWindow.Destroy(other);
        }
    }

    [Test]
    public void ADisabledControlIsToldAsDisabledAndNoStagePressesIt()
    {
        nint window = PumpedWindow.Create("BAXY disabled fixture");
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(Disabled, Disabled);
            var ocr = new CountingLocator();
            var adapter = new WindowsVisibleControlAdapter(worker, ocr, ocr, timing: Quick);
            RememberView(adapter, window);

            ExternalCapabilityReceipt receipt = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Siguiente\",\"window\":" + (long)window + "}"), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_disabled"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.False);
                Assert.That(ocr.Calls, Is.Zero);
            });
        }
        finally
        {
            PumpedWindow.Destroy(window);
        }
    }

    [Test]
    public void ASearchThatRaisedAndFoundNothingIsPartialNotEmpty()
    {
        string answer = RunWorker(["Get-Descendants"], """
            function Get-WalkedDescendants($root){ return ,(New-Object System.Collections.Generic.List[object]) }
            $AE=[System.Windows.Automation.AutomationElement]
            $script:Cache=New-Object System.Windows.Automation.CacheRequest
            $script:Partial=$false
            $script:Until=[DateTime]::UtcNow.AddSeconds(30)
            $raises=[pscustomobject]@{ Calls=0 }
            $raises | Add-Member -MemberType ScriptMethod -Name FindAll -Value { param($scope,$condition) $this.Calls++; throw 'provider fault' }
            $null=Get-Descendants $raises
            $faulted=$script:Partial
            $script:Partial=$false
            $empty=[pscustomobject]@{ Calls=0 }
            $empty | Add-Member -MemberType ScriptMethod -Name FindAll -Value { param($scope,$condition) $this.Calls++; return @() }
            $null=Get-Descendants $empty
            $reallyEmpty=$script:Partial
            $script:Partial=$false
            $script:Until=[DateTime]::UtcNow.AddSeconds(-1)
            $late=[pscustomobject]@{ Calls=0 }
            $late | Add-Member -MemberType ScriptMethod -Name FindAll -Value { param($scope,$condition) $this.Calls++; throw 'provider fault' }
            $null=Get-Descendants $late -Bounded
            [Console]::Out.Write(("$faulted,$reallyEmpty,$($script:Partial),$($late.Calls)"))
            """);
        Assert.That(answer, Is.EqualTo("True,False,True,1"),
            "a fault is partial; an empty window is not; past the deadline the same search is not repeated");
    }

    [Test]
    public void OneNodeThatRaisesCostsThatNodeAndLeavesTheViewPartial()
    {
        string answer = RunWorker(
            ["Do-View", "Test-PrimaryAction", "Test-NamelessHolds", "Get-InertRepeats", "Get-WantedMissing", "Get-LabelFolded", "Test-CenterWithin", "Select-TailControls", "Get-FoldedFields", "Join-ViewControls", "Get-SeenKey", "Test-WantedName", "ConvertTo-MenuViewEntries", "Add-ViewBody", "Select-BodySurface", "Get-BodySurface"], """
            $script:ViewCap=60;$script:ViewSeconds=2.0;$script:ShownUnread=0;$script:Partial=$false;$script:ViewRowKinds=@();$script:BodyKinds=@()
            $Actionable=@('Button')
            function Get-Root($h,[switch]$Front){ return @{ hwnd=[IntPtr]1; root=[pscustomobject]@{} } }
            function Get-WindowBox($h){ return $null }
            function Test-FrameOnlyView($all){ return $false }
            function Get-Name($e){ return 'v' }
            function Get-Rect($e){ return $null }
            function Get-Id($e){ return [string]$e.Tag }
            function Get-Prop($e,$p){ return '' }
            function Get-ShownName($e){ if($e.Tag -eq 'bad'){ throw [InvalidOperationException]::new('odd string') }; return 'Bueno' }
            function Get-State($e){ return @{ state=''; value=$null; valueCut=0 } }
            function Get-ShownDescendants($root,$hwnd,$seconds,$dimmed){ return ,$script:Nodes }
            function Get-DisabledShown($a,$b,$c){ return @() }
            $type=[pscustomobject]@{ ProgrammaticName='ControlType.Button' }
            $cached=[pscustomobject]@{ IsOffscreen=$false; ControlType=$type; IsEnabled=$true; ClassName=''; AcceleratorKey=''; AccessKey=''; ItemType='' }
            $script:Nodes=New-Object System.Collections.Generic.List[object]
            $script:Nodes.Add([pscustomobject]@{ Tag='bad'; Cached=$cached })
            $script:Nodes.Add([pscustomobject]@{ Tag='good'; Cached=$cached })
            $view=Do-View ([pscustomobject]@{ limit=10; hwnd=1; disabled=$false })
            [Console]::Out.Write(("$($view.partial),$(@($view.controls).Count),$(@($view.controls)[0].name)"))
            """);
        Assert.That(answer, Is.EqualTo("True,1,Bueno"));
    }

    private static string WorkerPath()
    {
        string here = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assert.That(File.Exists(here), here);
        return here;
    }

    private static string RunWorker(string[] functions, string body)
    {
        string names = string.Join(",", functions.Select(static name => "'" + name + "'"));
        string script = """
            $ErrorActionPreference='Stop'
            [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
            Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_HONEST_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@(
            """ + names + """
            )
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
        start.Environment["BAXY_HONEST_WORKER"] = WorkerPath();
        using var process = Process.Start(start)!;
        string error = string.Empty;
        process.ErrorDataReceived += (_, line) => error += line.Data + "\n";
        process.BeginErrorReadLine();
        string output = ChildOutput.Read(process);
        process.WaitForExit();
        Assert.That(process.ExitCode, Is.Zero, error);
        return output;
    }
}
