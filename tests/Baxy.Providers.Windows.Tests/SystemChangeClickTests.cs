using System.IO;
using System.Text.Json;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 83: a click that changes a setting of Windows went without asking when its control was a button with words of
/// action and no Toggle (Invoke only, the same shape as a row that navigates): the guard read only switches of one
/// process. The worker's functions are taken by their syntax tree and run over described controls, and the adapter over a
/// worker that answers by command: nothing is pressed.
/// </summary>
[TestFixture]
public sealed class SystemChangeClickTests
{
    // The worker's reading of one described control. powershell.exe, which runs this, lives under the Windows folder: a
    // control with its process id stands on a system surface, and one with this test's process id does not.
    private static string Read(string control)
    {
        string pattern = RiskPolicy.SystemActsPattern.Replace("'", "''", StringComparison.Ordinal);
        string hint = RiskPolicy.FoldHint.Replace("'", "''", StringComparison.Ordinal);
        string confusables = RiskPolicy.Confusables.Replace("'", "''", StringComparison.Ordinal);
        return ComputerUseListenedPressTests.Run(
            ComputerUseListenedPressTests.Worker(),
            ["Get-SystemChange", "Get-PressTaker", "Test-SystemSurface", "Test-Asks", "Get-AskFolded"],
            $$"""
            $own={{Environment.ProcessId}}
            $changes=@{ pattern='{{pattern}}'; hint='{{hint}}'; confusables='{{confusables}}' }
            function Get-Toggle($el){ return $el.Toggle }
            function Test-Selected($el){ return [bool]$el.Chosen }
            function Get-ClickFacts($el){ return @{ invoke=[bool]$el.Invoke } }
            function Get-ParentKind($el){ return [string]$el.Parent }
            function Get-ParentId($el){ return [string]$el.ParentId }
            function Get-SettingName($root){ return 'Panel de prueba' }
            function Test-PressesItself($el){ return ($null -eq $el.Presses -or [bool]$el.Presses) }
            function Get-LineageWalker { return (New-Object psobject | Add-Member -MemberType ScriptMethod -Name GetParent -Value { param($node) return $node.Up } -PassThru) }
            $script:LineageUp=3
            function Get-PressPoint($el){ if($null -ne $el.Hit){ return @{ x=1; y=1; hit=$el.Hit } }; return $null }
            function Get-ElementAt($point){ return $point.hit }
            function New-Control([string]$kind,[string]$id,[int]$process,$toggle=$null,[bool]$invoke=$false,[string]$parent='',[bool]$chosen=$false,[string]$parentId=''){
              $current=New-Object psobject -Property @{ AutomationId=$id; ProcessId=$process }
              return (New-Object psobject -Property @{ Current=$current; Kind=$kind; Toggle=$toggle; Invoke=$invoke; Parent=$parent; Chosen=$chosen; ParentId=$parentId })
            }
            $root=New-Object psobject -Property @{ Current=(New-Object psobject -Property @{ ClassName='VentanaDePrueba' }) }
            {{control}}
            $found=Get-SystemChange $el $name $el.Kind $root $changes
            if($null -eq $found){ [Console]::Out.Write('none') }
            else { [Console]::Out.Write([string]$found.change+'|'+[string]$found.state+'|'+[string]$found.setting) }
            """);
    }

    // The shape measured live: Invoke only, an identity bound to a setting, and no Toggle at all.
    [Test]
    public void AButtonBoundToASettingChangesTheSystem() =>
        Assert.That(Read("""
            $name='Encender ahora'; $el=New-Control 'Button' 'powershell_Panel_Ajuste_Button' $PID -invoke $true
            """), Is.EqualTo("action||Panel de prueba"));

    // A classic panel: its identities are numbers, so its own words tell.
    [TestCase("Activar")]
    [TestCase("Desactivar ahora")]
    [TestCase("Aplicar")]
    [TestCase("Turn on")]
    public void AClassicButtonWithWordsOfChangeChangesTheSystem(string label) =>
        Assert.That(Read($"""
            $name='{label}'; $el=New-Control 'Button' '1021' $PID -invoke $true
            """), Is.EqualTo("action||Panel de prueba"));

    [TestCase("ToggleSwitch", "Off")]
    [TestCase("CheckBox", "On")]
    public void AControlWithAMarkChangesTheSystemAndSaysItsState(string kind, string state) =>
        Assert.That(Read($"""
            $name='Modo de prueba'; $el=New-Control '{kind}' '77' $PID -toggle '{state}'
            """), Is.EqualTo($"switch|{state}|Panel de prueba"));

    [Test]
    public void ARadioButtonChangesTheSystem() =>
        Assert.That(Read("""
            $name='Opcion dos'; $el=New-Control 'RadioButton' '12' $PID -chosen $false
            """), Is.EqualTo("choice|Off|Panel de prueba"));

    [Test]
    public void AnItemOfADropDownChangesTheSystem() =>
        Assert.That(Read("""
            $name='Opcion dos'; $el=New-Control 'ListItem' '' $PID -parent 'ComboBox'
            """), Is.EqualTo("choice|Off|Panel de prueba"));

    // Medido en vivo: the items of a gallery choose a value of the setting their list is bound to; the model tried one on a
    // turn that only asked to look. The items of the panel's own side bar hang from no setting.
    [Test]
    public void AnItemOfAListBoundToASettingChangesTheSystem() =>
        Assert.That(Read("""
            $name='Tono dos'; $el=New-Control 'ListItem' '' $PID -parent 'List' -parentId 'powershell_Panel_Tono_GridView'
            """), Is.EqualTo("choice|Off|Panel de prueba"));

    [Test]
    public void AnItemOfTheSideBarChangesNothing() =>
        Assert.That(Read("""
            $name='Sistema'; $el=New-Control 'ListItem' '' $PID -parent 'Group' -parentId 'ListaDeSecciones'
            """), Is.EqualTo("none"));

    // Medido en vivo: a click named a container of the panel with no way of its own to be pressed, the pointer fell at its
    // centre, on an item of a gallery, and it changed the setting on a turn that only asked to look. What is judged is
    // what takes the press: what lies at the point, up its line.
    [Test]
    public void AContainerIsJudgedByWhatThePointerFallsOn() =>
        Assert.That(Read("""
            $item=New-Control 'ListItem' '' $PID -parent 'List' -parentId 'powershell_Panel_Tono_GridView'
            $item | Add-Member -NotePropertyName Presses -NotePropertyValue $true
            $item.Current | Add-Member -NotePropertyName ControlType -NotePropertyValue (New-Object psobject -Property @{ ProgrammaticName='ControlType.ListItem' })
            $item.Current | Add-Member -NotePropertyName Name -NotePropertyValue 'Tono dos, 4 imagenes'
            $name='Tono actual'; $el=New-Control 'Group' '' $PID
            $el | Add-Member -NotePropertyName Presses -NotePropertyValue $false
            $el | Add-Member -NotePropertyName Hit -NotePropertyValue $item
            """), Is.EqualTo("choice|Off|Panel de prueba"));

    // A row that navigates, under the pointer: no question.
    [Test]
    public void AContainerOverARowThatNavigatesChangesNothing() =>
        Assert.That(Read("""
            $row=New-Control 'Button' 'FilaDeNavegacion' $PID -invoke $true
            $row | Add-Member -NotePropertyName Presses -NotePropertyValue $true
            $row.Current | Add-Member -NotePropertyName ControlType -NotePropertyValue (New-Object psobject -Property @{ ProgrammaticName='ControlType.Button' })
            $row.Current | Add-Member -NotePropertyName Name -NotePropertyValue 'Pantalla'
            $name='Seccion'; $el=New-Control 'Group' '' $PID
            $el | Add-Member -NotePropertyName Presses -NotePropertyValue $false
            $el | Add-Member -NotePropertyName Hit -NotePropertyValue $row
            """), Is.EqualTo("none"));

    // Without a point to read, what takes the press is looked for up its own line (the Text inside an item).
    [Test]
    public void TheTextInsideAnItemIsJudgedAsTheItemThatTakesThePress() =>
        Assert.That(Read("""
            $item=New-Control 'ListItem' '' $PID -parent 'List' -parentId 'powershell_Panel_Tono_GridView'
            $item | Add-Member -NotePropertyName Presses -NotePropertyValue $true
            $item.Current | Add-Member -NotePropertyName ControlType -NotePropertyValue (New-Object psobject -Property @{ ProgrammaticName='ControlType.ListItem' })
            $item.Current | Add-Member -NotePropertyName Name -NotePropertyValue 'Tono dos, 4 imagenes'
            $name='Tono dos'; $el=New-Control 'Text' '' $PID
            $el | Add-Member -NotePropertyName Presses -NotePropertyValue $false
            $el | Add-Member -NotePropertyName Up -NotePropertyValue $item
            """), Is.EqualTo("choice|Off|Panel de prueba"));

    // Medido en vivo: a menu of a system surface runs a command («agregar», «quitar»): one opened a file dialog on a turn
    // that only asked to look.
    [Test]
    public void AnEntryOfAMenuOfASystemSurfaceChangesTheSystem() =>
        Assert.That(Read("""
            $name='Agregar uno'; $el=New-Control 'MenuItem' '' $PID -invoke $true
            """), Is.EqualTo("action||Panel de prueba"));

    // Medido en vivo: on a turn that only asked to look, the model pressed a Hyperlink whose words change a setting three
    // times and said it had. Most links of a panel only inform, so its words tell.
    [Test]
    public void ALinkWithWordsOfChangeChangesTheSystem() =>
        Assert.That(Read("""
            $name='Cambiar a otro tono ahora.'; $el=New-Control 'Hyperlink' '' $PID -invoke $true
            """), Is.EqualTo("action||Panel de prueba"));

    // What only moves around the panel, and what only opens, changes nothing: no question for them.
    [TestCase("'Button' 'FilaDeNavegacion' $PID -invoke $true", "Pantalla")]
    [TestCase("'Button' 'FilaDeNavegacion' $PID -invoke $false", "Mostrar mas")]
    [TestCase("'Hyperlink' '' $PID -invoke $true", "Mas informacion")]
    [TestCase("'ListItem' '' $PID -parent 'List'", "Sistema")]
    [TestCase("'ComboBox' 'powershell_Panel_Modo_ComboBox' $PID", "Elige tu modo")]
    public void WhatOnlyMovesOrOpensChangesNothing(string control, string name) =>
        Assert.That(Read($"""
            $name='{name}'; $el=New-Control {control}
            """), Is.EqualTo("none"));

    // The same controls on a window of no system surface: its own application's business.
    [TestCase("'ToggleSwitch' '77' $own -toggle 'On'", "Modo de prueba")]
    [TestCase("'Button' '12' $own -invoke $true", "Activar")]
    public void TheSameControlsInAnApplicationChangeNothingOfTheSystem(string control, string name) =>
        Assert.That(Read($"""
            $name='{name}'; $el=New-Control {control}
            """), Is.EqualTo("none"));

    // The reading of a click finds the control as the click does and never reaches a press.
    [Test]
    public void TheWorkerReadsAClickBeforeEveryWayToPressIt()
    {
        string worker = File.ReadAllText(ComputerUseListenedPressTests.Worker());
        int read = worker.IndexOf("if($script:ClickOnlyRead){ return (Get-ClickRead", StringComparison.Ordinal);
        int nativePress = worker.IndexOf("[BaxyUiaWorkerNative]::Click($nativeButton)", StringComparison.Ordinal);
        int menuPress = worker.IndexOf("$menuPress=Press-MenuCommand", StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(worker, Does.Contain("if($script:ClickOnlyRead -and $matches.Count -eq 0){"));
            Assert.That(worker, Does.Contain("if($script:ClickOnlyRead){ return (Click-Result $false $false 'visible_no_system_change'"));
            Assert.That(read, Is.GreaterThan(0));
            Assert.That(read, Is.GreaterThan(menuPress), "the read of a found control comes after the ways of one not found");
            Assert.That(nativePress, Is.GreaterThan(0));
        });
    }

    // Encargo 96: in Bypass nobody sees a yes coming, so a switch of Settings is refused before any press, as it was
    // (C02): a Wi-Fi or a Bluetooth turned off by a stray click leaves BAXY without its network or the person's headset.
    private static string Refusal(string control) => ComputerUseListenedPressTests.Run(
        ComputerUseListenedPressTests.Worker(),
        ["Get-SettingsSwitchRefusal", "Get-PressTaker", "Click-Result"],
        $$"""
        function Get-ControlProcessName($el){ return [string]$el.Process }
        function Get-Toggle($el){ return $el.Toggle }
        function Test-PressesItself($el){ return [bool]$el.Presses }
        function Get-Id($el){ return [string]$el.Id }
        function Get-LineageWalker { return (New-Object psobject | Add-Member -MemberType ScriptMethod -Name GetParent -Value { param($node) return $null } -PassThru) }
        $script:LineageUp=3
        function Get-PressPoint($el){ return @{ x=1; y=1; hit=$el.Hit } }
        function Get-ElementAt($point){ return $point.hit }
        function New-Control([string]$process,$toggle,[bool]$presses,[string]$name,$hit=$null){
          $type=New-Object psobject -Property @{ ProgrammaticName='ControlType.Tipo' }
          $current=New-Object psobject -Property @{ ControlType=$type; Name=$name }
          return (New-Object psobject -Property @{ Current=$current; Process=$process; Toggle=$toggle; Presses=$presses; Hit=$hit; Id=('id.'+$name) })
        }
        {{control}}
        $found=Get-SettingsSwitchRefusal $el $el.Current.Name $el.Id 'Tipo'
        if($null -eq $found){ [Console]::Out.Write('none') }
        else { [Console]::Out.Write([string]$found.error+'|'+[string]$found.name+'|'+[string]$found.switchState) }
        """);

    [TestCase("On")]
    [TestCase("Off")]
    public void ASwitchOfSettingsIsRefusedWithItsState(string state) =>
        Assert.That(Refusal($"$el=New-Control 'SystemSettings' '{state}' $true 'Radio de prueba'"),
            Is.EqualTo($"visible_settings_switch_refused|Radio de prueba|{state}"));

    // What takes the press is what is judged: the words beside a switch fall on the switch.
    [Test]
    public void TheWordsOverASwitchOfSettingsAreRefusedAsTheSwitch() =>
        Assert.That(Refusal("""
            $under=New-Control 'SystemSettings' 'On' $true 'Radio de prueba'
            $el=New-Control 'SystemSettings' $null $false 'Texto' $under
            """), Is.EqualTo("visible_settings_switch_refused|Radio de prueba|On"));

    [TestCase("$el=New-Control 'SystemSettings' $null $true 'Encender ahora'", TestName = "ABypassButtonOfSettingsIsNoSwitch")]
    [TestCase("$el=New-Control 'OtraApp' 'On' $true 'Radio de prueba'", TestName = "ABypassSwitchOfAnApplicationIsNoSwitchOfSettings")]
    public void WhatIsNoSwitchOfSettingsGoesAsInTheBase(string control) =>
        Assert.That(Refusal(control), Is.EqualTo("none"));

    // At a point, as by name; and in normal mode the same point still names the control for the kernel's yes.
    [TestCase(true, "'On'", "visible_settings_switch_refused", 0, TestName = "AtAPointBypassRefusesASwitch")]
    [TestCase(true, "$null", "visible_button_postread_pending", 1, TestName = "AtAPointBypassPressesWhatIsNoSwitchAsInTheBase")]
    [TestCase(false, "$null", "visible_control_needs_confirmation", 0, TestName = "AtAPointNormalModeKeepsItForTheYes")]
    public void APointKeepsTheModesApart(bool refuse, string state, string error, int pressed)
    {
        string answer = ComputerUseListenedPressTests.Run(
            ComputerUseListenedPressTests.Worker(),
            ["Do-At", "Click-Result", "Get-AskingName", "Get-SettingsSwitchRefusal"],
            $$"""
            function Read-RenderHosts($request){ return @() }
            function Get-RenderHosts($top){ return @() }
            function Get-Root([long]$hwnd){ return @{ hwnd=[IntPtr]77; root=(New-Object psobject -Property @{ Current=(New-Object psobject -Property @{ BoundingRectangle=[System.Windows.Rect]::Empty }) }) } }
            $type=New-Object psobject -Property @{ ProgrammaticName='ControlType.Button' }
            $current=New-Object psobject -Property @{ BoundingRectangle=(New-Object System.Windows.Rect(0,0,10,10)); ControlType=$type; Name='Control' }
            $script:Control=New-Object psobject -Property @{ Current=$current; Label='Control' }
            function Get-PointChain($root,$x,$y){ return @($script:Control) }
            function Get-Name($node){ return [string]$node.Label }
            function Get-Id($node){ return 'id.'+[string]$node.Label }
            function Get-ControlProcessName($node){ return 'SystemSettings' }
            function Get-PressTaker($node){ return $node }
            function Get-Toggle($node){ return {{state}} }
            function Get-SystemChange($node,$name,$kind,$root,$changes){ return @{ change='action'; state=''; setting='Panel de prueba' } }
            function Select-PointHolders($entries,$aliases,$limit){ return @(0) }
            $script:Tried=0
            function Invoke-NamedControl($el,$top,[switch]$PatternsOnly){ $script:Tried++; return @{ method='invoke' } }
            function Pressed-Result($done,$button,$name,$identity,$kind,$toggleBefore,$lineage){ return @{ ok=$false; error='visible_button_postread_pending'; name=$name } }
            $read=Do-At @{ hwnd=77; x=5; y=5; aliases=@('Control'); refuseSwitches=${{refuse}} }
            [Console]::Out.Write([string]$read.error+'|'+$script:Tried)
            """);

        Assert.That(answer, Is.EqualTo(error + "|" + pressed));
    }

    private const string SwitchRefused =
        """{"version":2,"ok":false,"effectObserved":false,"error":"visible_settings_switch_refused","name":"Radio de prueba","controlIdentity":"id","absentOrDisabled":false,"switchState":"On"}""";

    // The adapter says so to the worker only in Bypass, and the model reads the refusal with the switch's state.
    [Test]
    public async Task InBypassTheClickAsksTheWorkerToRefuseASwitchAndSaysItsState()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(SwitchRefused);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, elevated: static _ => false)
        {
            RefusesSettingsSwitches = static () => true,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Click("""{"label":"Radio de prueba","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(worker.Commands[0], Does.Contain("\"refuseSwitches\":true"));
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.SettingsSwitchRefused));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("name").GetString(), Is.EqualTo("Radio de prueba"));
            Assert.That(receipt.Result?.GetProperty("switch").GetString(), Is.EqualTo("on"));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.StartWith("nothing was pressed"));
        });
    }

    [Test]
    public async Task InNormalModeTheClickDoesNotAskTheWorkerToRefuse()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(SwitchRefused);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, elevated: static _ => false);

        _ = await adapter.InvokeAsync(
            "input.visible.click", Click("""{"label":"Radio de prueba","window":4660}"""), CancellationToken.None);

        Assert.That(worker.Commands[0], Does.Not.Contain("refuseSwitches"));
    }

    // At a point nothing was pressed either: the base said «it may have acted» (visible_point_press_unconfirmed).
    [Test]
    public async Task APointRefusedInBypassSaysNothingWasPressed()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(SwitchRefused);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, elevated: static _ => false)
        {
            RefusesSettingsSwitches = static () => true,
        };

        PointPressed pressed = await adapter.PressAtAsync(4660, 5, 5, "Radio de prueba", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(worker.Commands[0], Does.Contain("\"refuseSwitches\":true"));
            Assert.That(pressed.Outcome, Is.EqualTo(PointPressOutcome.SwitchRefused));
        });
    }

    // The same file the engine rereads at each call decides, at each click: Bypass switched on or off holds at once.
    [Test]
    public void TheRefusalFollowsTheModeTheEngineReads()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-modo-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Func<bool> refuses = WindowsVisibleControlAdapter.InBypass(root);
            bool none = refuses();
            ConfirmationModeStore.Write(root, ConfirmationMode.Bypass);
            bool bypass = refuses();
            ConfirmationModeStore.Write(root, ConfirmationMode.Normal);
            bool normal = refuses();
            Assert.Multiple(() =>
            {
                Assert.That(none, Is.False);
                Assert.That(bypass, Is.True);
                Assert.That(normal, Is.False);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private sealed class ReadingWorker(string? answer) : IUiaWorker
    {
        internal List<string> Commands { get; } = [];

        public ValueTask PrewarmAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Commands.Add(commandJson);
            return ValueTask.FromResult(answer is null ? null : JsonDocument.Parse(answer));
        }
    }

    private static WindowsVisibleControlAdapter Adapter(ReadingWorker worker, bool surface) =>
        new(worker, null, null, elevated: static _ => false) { SystemSurface = _ => surface };

    private static JsonElement Click(string json) => JsonDocument.Parse(json).RootElement;

    // The fault itself: this click did not reach any read, and it ran.
    [Test]
    public void AClickOnASystemSurfaceIsReadBeforeItRuns()
    {
        WindowsVisibleControlAdapter adapter = Adapter(new ReadingWorker(null), surface: true);

        Assert.Multiple(() =>
        {
            Assert.That(adapter.PreflightMayRaise("input.visible.click", Click("""{"label":"Encender ahora"}""")), Is.True);
            Assert.That(adapter.PreflightMayRaise("input.visible.click", Click("""{"label":"Modo","manner":"open"}""")), Is.False,
                "only opening a list changes nothing");
        });
    }

    [Test]
    public void AClickOnAnyOtherWindowIsNotRead() =>
        Assert.That(Adapter(new ReadingWorker(null), surface: false)
            .PreflightMayRaise("input.visible.click", Click("""{"label":"Encender ahora"}""")), Is.False);

    [Test]
    public async Task AControlThatChangesTheSystemNeedsTheYesAndSaysWhatItIs()
    {
        var worker = new ReadingWorker("""
            {"ok":false,"error":"visible_system_change","name":"Encender ahora","change":"action","state":"","setting":"Panel de prueba"}
            """);

        ExternalCapabilityReceipt? read = await Adapter(worker, surface: true).PreflightAsync(
            "input.visible.click", Click("""{"label":"Encender ahora"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read?.NeedsConfirmation, Is.True);
            Assert.That(worker.Commands.Single(), Does.Contain("\"cmd\":\"clickread\""));
            JsonElement change = read!.Result!.Value.GetProperty("systemChange");
            Assert.That(change.GetProperty("control").GetString(), Is.EqualTo("Encender ahora"));
            Assert.That(change.GetProperty("change").GetString(), Is.EqualTo("action"));
            Assert.That(change.GetProperty("setting").GetString(), Is.EqualTo("Panel de prueba"));
        });
    }

    [Test]
    public async Task ASwitchSaysItsStateInTheQuestion()
    {
        var worker = new ReadingWorker("""
            {"ok":false,"error":"visible_system_change","name":"Modo de prueba","change":"switch","state":"Off","setting":"Panel de prueba"}
            """);

        ExternalCapabilityReceipt? read = await Adapter(worker, surface: true).PreflightAsync(
            "input.visible.click", Click("""{"label":"Modo de prueba"}"""), CancellationToken.None);

        Assert.That(read!.Result!.Value.GetProperty("systemChange").GetProperty("state").GetString(), Is.EqualTo("off"));
    }

    // A row that navigates, and a name no control has (that failure is the click's own, with its candidates).
    [TestCase("""{"ok":false,"error":"visible_no_system_change","name":"Pantalla"}""")]
    [TestCase("""{"ok":false,"error":"visible_button_not_found"}""")]
    public async Task WhatChangesNothingAsksNothing(string answer) =>
        Assert.That(await Adapter(new ReadingWorker(answer), surface: true).PreflightAsync(
            "input.visible.click", Click("""{"label":"Pantalla"}"""), CancellationToken.None), Is.Null);

    // Fail-closed, as K-1: a click on a system surface whose control could not be read asks.
    [Test]
    public async Task AControlOfASystemSurfaceThatCouldNotBeReadAsks()
    {
        ExternalCapabilityReceipt? read = await Adapter(new ReadingWorker(null), surface: true).PreflightAsync(
            "input.visible.click", Click("""{"label":"Encender ahora"}"""), CancellationToken.None);

        Assert.That(read?.NeedsConfirmation, Is.True);
    }

    // The receipt says what changed: the facts of the worker's post-read reach the result as they are.
    [Test]
    public void TheWorkerSaysWhatThePressChanged()
    {
        string answer = ComputerUseListenedPressTests.Run(
            ComputerUseListenedPressTests.Worker(), ["Get-SystemChangeReading", "Get-SystemControls"], """
            function New-Row([string]$kind,[string]$name,[string]$id,$toggle=$null){
              $type=New-Object psobject -Property @{ ProgrammaticName=('ControlType.'+$kind) }
              $cached=New-Object psobject -Property @{ ControlType=$type; Name=$name; AutomationId=$id }
              return (New-Object psobject -Property @{ Cached=$cached; Toggle=$toggle })
            }
            $script:Reads=@(
              @((New-Row 'Button' 'Encender ahora' 'proceso_Panel_Si_Button'),(New-Row 'Button' 'Programar' 'proceso_Panel_Hora_ToggleSwitch' 'Off'),(New-Row 'Button' 'Pantalla' 'FilaDeNavegacion')),
              @((New-Row 'Button' 'Apagar ahora' 'proceso_Panel_No_Button'),(New-Row 'Button' 'Programar' 'proceso_Panel_Hora_ToggleSwitch' 'Off'),(New-Row 'Button' 'Pantalla' 'FilaDeNavegacion')))
            $script:At=0
            function Get-Descendants($root){ $now=$script:Reads[[Math]::Min($script:At,1)]; $script:At++; return $now }
            function Get-Toggle($el){ return $el.Toggle }
            function Test-Selected($el){ return $false }
            function Start-Sleep { param($Milliseconds) }
            $before=@(Get-SystemControls $null)
            $took=Get-SystemChangeReading @{ root=$null; before=$before; name='Encender ahora' }
            $script:At=1
            $same=Get-SystemChangeReading @{ root=$null; before=@(Get-SystemControls $null); name='Programar' } 0
            [Console]::Out.Write($before.Count.ToString()+'|'+[string]$took.control+'|'+(@($took.before) -join '+')+'|'+(@($took.after) -join '+')+'|'+[bool]$took.changed+'|'+[bool]$same.changed)
            """);

        Assert.That(answer, Is.EqualTo("2|Encender ahora|Encender ahora|Apagar ahora|True|False"));
    }
}
