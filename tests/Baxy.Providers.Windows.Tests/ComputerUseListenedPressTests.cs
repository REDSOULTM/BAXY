using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 20b, palanca 7: a press goes by the way the application listens to. A choice whose Select left the place as it
/// was (a Qt row marked selected but not made current, v3-52) gets the posted press next; a toggle whose sibling's mark
/// does not appear for it (v3-53) is no receipt; the controls a name still meets after the lineage count only when they
/// can be pressed (v3-61); and the classic menu bar (HMENU) is read and pressed by WM_COMMAND (v3-49). The worker's own
/// functions are taken by their syntax tree and run over described controls and stand-ins: nothing is read or pressed.
/// </summary>
[TestFixture]
public sealed class ComputerUseListenedPressTests
{
    private static string Worker()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    [Test]
    public void ANativeRowGetsThePostedPressAfterSelectAndAXamlRowDoesNot()
    {
        string answer = Run(Worker(), ["Select-ClickMethods"], """
            $answers=foreach($case in @(
              @{ invoke=$true; select=$true; kind='ListItem'; native=$true },
              @{ select=$true; kind='ListItem'; native=$true },
              @{ invoke=$true; select=$true; kind='ListItem' },
              @{ toggle=$true; kind='CheckBox'; native=$true },
              @{ select=$true; kind='ListItem'; native=$true; selected=$true })){
              $facts=@{ invoke=[bool]$case.invoke; select=[bool]$case.select; toggle=[bool]$case.toggle; expand=$false; kind=[string]$case.kind; value=$false; classic=$false; native=[bool]$case.native; render=$false; selected=[bool]$case.selected }
              (@(Select-ClickMethods $facts) -join ' ')
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "invoke select message", // v3-52: a Qt row, whose Select does not make it current
            "select message",
            "invoke select",         // contracase: a XAML or DirectUI row keeps its ways
            "toggle",                // a toggle keeps its single way here (its next way needs the witness)
            "select",                // an item already chosen keeps its single way
        }));
    }

    // Places as Get-PlaceTrace reads them: the title and each named control by its identity, with its kind and name. The
    // settings window of a Qt application, on «General» or on «Video», with a live status label (review 2, B3).
    private const string Places = """
        function New-Place([string]$title,[string]$cpu,[string[]]$rows){
          $items=@{ '1.10'=@{ kind='ListItem'; name='General' }; '1.11'=@{ kind='ListItem'; name='Video' }; '1.90'=@{ kind='Text'; name=$cpu } }
          $n=20
          foreach($row in $rows){ $items['1.'+$n]=@{ kind='Text'; name=$row }; $n++ }
          return @{ title=$title; items=$items; volatile=@{} }
        }
        $general=New-Place 'Ajustes' 'CPU: 1.4%, 30.00 fps' @('Idioma','Tema')
        $video=New-Place 'Ajustes' 'CPU: 1.4%, 30.00 fps' @('Resolucion base')

        """;

    // The worker's own budgets for the place measure (review 2 of r24b, B1), read from the syntax tree the harness parsed.
    private const string Budgets = """
        foreach($var in @('$script:PlaceWaitMs','$script:PlaceTwiceMs','$script:PlaceCeilingMs','$script:PlaceCostMs')){
          $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq $var },$true))
          if($found.Count -ne 1){ throw ('data missing: '+$var) }
          . ([scriptblock]::Create($found[0].Extent.Text))
        }

        """;

    [Test]
    public void ASelectThatLeftThePlaceAsItWasTriesThePostedPressOnlyInANativeFramework()
    {
        string answer = Run(Worker(), ["Invoke-NamedControl", "Test-PlaceMoved", "Get-SteadyPlace", "Test-PlaceTooDear", "Wait-PlaceMoved", "Get-PressPoint", "Get-CurrentRect", "Get-RenderHosts", "Select-ClickMethods"], Places + """
            $script:PatternMethods=@('invoke','select','toggle','expand','target','render')
            $script:RenderHosts=@()
            $script:Native=$true
            function Get-ClickFacts($el){ return @{ invoke=$false; select=$true; toggle=$false; expand=$false; kind='ListItem'; value=$false; classic=$false; native=$script:Native } }
            function Test-Selected($el){ return $false }
            function Wait-Chosen($el){ return $true }
            $script:Selects=0
            function Select-Element($el){ $script:Selects++ }
            $script:Places=@()
            $script:PlaceReads=0
            # The last place stays once read: the window holds it.
            function Get-PlaceTrace([IntPtr]$top){ $script:PlaceReads++; $next=$script:Places[0]; if($script:Places.Count -gt 1){ $script:Places=@($script:Places | Select-Object -Skip 1) }; return $next }
            $script:Probes=0
            $script:PointIs=$true
            function Test-PointIsElement($el,$point){ $script:Probes++; return $script:PointIs }
            function Get-HolderWindow($el){ return [IntPtr]5 }
            $ticked=New-Place 'Ajustes' 'CPU: 1.5%, 30.00 fps' @('Idioma','Tema')
            $later=New-Place 'Ajustes' 'CPU: 2.1%, 29.97 fps' @('Idioma','Tema')
            $answers=foreach($case in @(@{ native=$true; after=$general }, @{ native=$true; after=$video }, @{ native=$false; after=$general }, @{ native=$true; after=$general; covered=$true }, @{ native=$true; second=$ticked; after=$later }, @{ native=$true; after=$later })){
              $script:Native=$case.native
              $script:PointIs=-not [bool]$case.covered
              $script:Places=@($general,$(if($null -ne $case.second){ $case.second } else { $general }),$case.after)
              $script:Selects=0; $script:Probes=0; $script:PlaceReads=0
              [BaxyUiaWorkerNative]::Posted.Clear()
              $current=New-Object psobject -Property @{ ProcessId=0; NativeWindowHandle=0 }
              $el=New-Object psobject -Property @{ Current=$current }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(60,35)) }
              $done=Invoke-NamedControl $el ([IntPtr]77)
              ([string]$done.method)+'|'+$script:Selects+'|'+[BaxyUiaWorkerNative]::Posted.Count+'|'+$script:PlaceReads+'|'+[string]($null -ne $done.placeBefore)
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "message|1|1|3|True", // v3-52: Select marked the row, the page stayed on General: the posted press follows,
                                  // and its post-read knows the row's mark proves nothing (review of ronda 20b, finding 3);
                                  // the place is read twice before the Select (review 2, B3: what changes alone is learned)
            "select|1|0|3|False", // the page moved to its section: Select was the receipt, no second press
            "select|1|0|3|False", // contracase: a XAML list where Select chooses gets no second way; review 1 of r24b (B2):
                                  // every choice measures the place (two reads before, one after: review 2, B1, the
                                  // read after is bounded by time, and this harness gives it none beyond the first)
            "select|1|0|3|True",  // the person's window over the point: nothing posted, the mark still proves nothing
            "message|1|1|3|True", // review 2 (B3): the status label ticked between the two reads before and again after:
                                  // learned as volatile, it is no move, and the posted press follows
            "message|1|1|3|True", // a label that changes in its place without ticking before is no move either
        }));
    }

    // Review 2 of r24b (B1): the place measure runs on every press that chooses an item, and each read walks the whole
    // tree. Its cost is bounded by the worker's own budgets: the read after the press stops at PlaceWaitMs in total (at
    // least one read), a read dearer than PlaceTwiceMs is not repeated before the press, and a window whose read cost
    // more than PlaceCeilingMs is not measured again (its receipt goes without placeMoved, as before r24b).
    [Test]
    public void ThePlaceMeasureIsBoundedByTimeNotByReads()
    {
        string answer = Run(Worker(), ["Invoke-NamedControl", "Test-PlaceMoved", "Get-SteadyPlace", "Test-PlaceTooDear", "Wait-PlaceMoved", "Get-PressPoint", "Get-CurrentRect", "Get-RenderHosts", "Select-ClickMethods"], Places + Budgets + """
            # The worker's own data (the syntax tree the harness parsed), never a copy of it.
            foreach($var in @('$script:PlaceItemKinds','$script:ContainerKinds')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq $var },$true))
              if($found.Count -ne 1){ throw ('data missing: '+$var) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            $wait=[int]$script:PlaceWaitMs; $twice=[int]$script:PlaceTwiceMs; $ceiling=[int]$script:PlaceCeilingMs
            $script:ReadMs=0
            $script:PlaceReads=0
            function Get-PlaceTrace([IntPtr]$top){ $script:PlaceReads++; if($script:ReadMs -gt 0){ Start-Sleep -Milliseconds $script:ReadMs }; return $general }
            $answers=@()
            # 1. A row that chooses and never moves the place, with cheap reads: the wait after stops at its budget.
            $script:PlaceReads=0; $script:ReadMs=0
            $clock=[System.Diagnostics.Stopwatch]::StartNew()
            $moved=Wait-PlaceMoved $general ([IntPtr]77)
            $answers+=([string]$moved+'|'+[string]($clock.ElapsedMilliseconds -le ($wait+150))+'|'+[string]($script:PlaceReads -ge 2 -and $script:PlaceReads -le 13))
            # 2. A read dearer than the whole wait: exactly one read after the press.
            $script:PlaceReads=0; $script:ReadMs=$wait+50
            [void](Wait-PlaceMoved $general ([IntPtr]77))
            $answers+=[string]$script:PlaceReads
            # 3. Before the press: a read dearer than PlaceTwiceMs is not repeated; contracase: a cheap one is read twice.
            $script:PlaceReads=0; $script:ReadMs=$twice+60
            [void](Get-SteadyPlace ([IntPtr]78))
            $dear=$script:PlaceReads
            $script:PlaceReads=0; $script:ReadMs=0
            [void](Get-SteadyPlace ([IntPtr]79))
            $answers+=([string]$dear+'|'+[string]$script:PlaceReads)
            # 4. A choice in a window whose read passes the ceiling (the harness lowers it to stay fast): one read before,
            # none after, no placeMoved; the next press in that window reads nothing. Contracase: a window under it.
            Add-Type -TypeDefinition @'
            public static class BaxyUiaTimedPress {
              public static int Invoked = 0;
              public static bool InvokeWithin(object el, int ms) { Invoked++; return true; }
            }
            '@
            $script:InvokeWaitMs=1000
            $script:PatternMethods=@('invoke','select','toggle','expand','target','render')
            $script:RenderHosts=@()
            function Get-ClickFacts($el){ return @{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='ListItem'; value=$false; classic=$true; native=$false } }
            function Test-Selected($el){ return $false }
            function Wait-Chosen($el){ return $true }
            function Select-Element($el){}
            function Get-InvokeTrace($el,$top){ return @{ present=$true; enabled=$true; title='' } }
            function Test-InvokeActedAlone($before,$after){ return $false }
            function Test-PointIsElement($el,$point){ return $true }
            function Get-HolderWindow($el){ return [IntPtr]5 }
            # The wait after gets no time beyond its first read here, so the count is exact.
            $script:PlaceWaitMs=0; $script:PlaceTwiceMs=40; $script:PlaceCeilingMs=120; $script:PlaceCostMs=@{}
            $current=New-Object psobject -Property @{ ProcessId=0; NativeWindowHandle=0 }
            $el=New-Object psobject -Property @{ Current=$current }
            $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(60,35)) }
            foreach($case in @(@{ top=81; ms=200 }, @{ top=81; ms=200 }, @{ top=82; ms=60 })){
              $script:PlaceReads=0; $script:ReadMs=$case.ms
              $done=Invoke-NamedControl $el ([IntPtr]$case.top)
              $answers+=(([string]$done.method)+'|'+$script:PlaceReads+'|'+[string]$done.placeMoved)
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "False|True|True", // a place that stays: the wait ends within its budget, after more than one read
            "1",               // a read dearer than the whole wait: one read, never twelve
            "1|2",             // a dear read is not repeated before the press; contracase: a cheap one is (what ticks is learned)
            "invoke|1|",       // a window whose read passed the ceiling: one read before, none after, no placeMoved
            "invoke|0|",       // the next press in that window does not read the place at all
            "invoke|2|False",  // contracase: a window under the ceiling is measured (one dear read before, one after)
        }));
    }

    // Review of ronda 20b (finding 3): the post-read of a choice whose Select was judged worthless asks the place to move,
    // never the row's mark (Select left it marked); a place that stays is no receipt and the press's effect is uncertain.
    [Test]
    public void AChoiceWhoseSelectProvedNothingHoldsOnlyWhenThePlaceMoves()
    {
        string answer = Run(Worker(), ["Do-Postread", "Click-Result", "Wait-PlaceMoved", "Test-PlaceMoved"], Places + Budgets + """
            function Test-Selected($el){ return $true }
            function Get-Toggle($el){ return $null }
            function Test-FieldTook($el,$before){ return $false }
            $script:Places=@()
            $script:Ticking=$false
            $script:Tick=0
            # With nothing queued, the place as it stays: on General, its status label ticking on every read when asked.
            function Get-PlaceTrace([IntPtr]$top){
              if($script:Places.Count -eq 0){
                if(-not $script:Ticking){ return $general }
                $script:Tick++
                return (New-Place 'Ajustes' ('CPU: '+$script:Tick+'.0%, 30.00 fps') @('Idioma','Tema'))
              }
              $next=$script:Places[0]; $script:Places=@($script:Places | Select-Object -Skip 1); return $next
            }
            $current=New-Object psobject -Property @{ IsEnabled=$true; IsOffscreen=$false }
            $el=New-Object psobject -Property @{ Current=$current }
            $answers=foreach($case in @(@{ unproved=$true; places=@() }, @{ unproved=$true; places=@($general,$video) }, @{ unproved=$false; places=@() }, @{ unproved=$true; places=@(); ticking=$true })){
              $script:Places=@($case.places)
              $script:Ticking=[bool]$case.ticking
              $script:Pending=@{ native=$null; element=$el; toggleBefore=$null; lineage=@(); name='Video'; identity='row.3'; kind='ListItem'; method='message'; placeBefore=$(if($case.unproved){ $general } else { $null }); top=[IntPtr]77; topEnabled=$true }
              $read=Do-Postread @{}
              [string]$read.ok+'|'+[string]$read.error+'|'+[string]$read.selected+'|'+[string]([bool]$read.effectUncertain)
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "False|visible_choice_uncorroborated|False|True", // v3-52: the row is marked, the page stayed on General
            "True||True|False",                               // the page moved to «Video»: the choice holds
            "True||True|False",                               // contracase: a choice whose Select was the way keeps its mark
            "False|visible_choice_uncorroborated|False|True", // review 2 (B3): only the live status label changed while
                                                              // the press was read: the place did not move
        }));
    }

    // Ronda 21 (t-menu-2): a context menu or an opening by the control's arrow is not proven by the element's selection,
    // which it may have had before the act (the tree node already chosen): the post-read answers «unchanged» and the
    // adapter's surface and born-popup reads decide. Contracase: a plain click's selection still holds.
    [Test]
    public void AMenuOrAnOpeningIsNotProvenByTheElementsSelection()
    {
        string answer = Run(Worker(), ["Do-Postread", "Click-Result"], """
            function Test-Selected($el){ return $true }
            function Get-Toggle($el){ return $null }
            function Test-FieldTook($el,$before){ return $false }
            $current=New-Object psobject -Property @{ IsEnabled=$true; IsOffscreen=$false }
            $el=New-Object psobject -Property @{ Current=$current }
            $answers=foreach($manner in @('menu','open','double','')){
              $script:Pending=@{ native=$null; element=$el; toggleBefore=$null; lineage=@(); name='M.2 ADATA (D:)'; identity='tree.22'; kind='TreeItem'; method='contextmenu'; manner=$manner; placeBefore=$null; top=[IntPtr]0; topEnabled=$null }
              $read=Do-Postread @{}
              [string]$read.ok+'|'+[string]$read.error+'|'+[string]$read.selected
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "False|visible_button_postread_unchanged|False", // t-menu-2: the node was already selected; no menu was read open
            "False|visible_button_postread_unchanged|False", // an opening by the arrow likewise
            "False|visible_button_postread_unchanged|False", // the double click as before (B3, finding 6)
            "True||True",                                    // contracase: a plain click that selected the row holds
        }));
    }

    // Integration of ronda 21: the mark of another control of the element's same-named lineage (t-drag-4) proves a plain
    // click, never a context menu, an opening by its arrow or a double click (t-menu-2), whose element's own mark proves
    // nothing either: a toggle beside the node is no menu read open.
    [Test]
    public void ALineageToggleProvesAPlainClickButNoMenuOrOpening()
    {
        string answer = Run(Worker(), ["Do-Postread", "Click-Result", "Test-LineageToggled"], """
            function Test-Selected($el){ return $false }
            function Get-Toggle($el){ return [string]$el.Mark }
            function Test-FieldTook($el,$before){ return $false }
            $current=New-Object psobject -Property @{ IsEnabled=$true; IsOffscreen=$false }
            $el=New-Object psobject -Property @{ Current=$current }
            $answers=foreach($manner in @('menu','open','double','')){
              $sibling=New-Object psobject -Property @{ Mark='On' }
              $toggles=@(@{ el=$sibling; before='Off' })
              $script:Pending=@{ native=$null; element=$el; toggleBefore=$null; lineage=@(); lineageToggles=$toggles; name='Linea'; identity='list.4'; kind='ListItem'; method='invoke'; manner=$manner; placeBefore=$null; top=[IntPtr]0; topEnabled=$null }
              $read=Do-Postread @{}
              [string]$read.ok+'|'+[string]$read.error+'|'+[string]$read.toggled
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "False|visible_button_postread_unchanged|False", // a context menu: the lineage's mark is no menu read open
            "False|visible_button_postread_unchanged|False", // an opening by the arrow likewise
            "False|visible_button_postread_unchanged|False", // a double click as before
            "True||True",                                    // contracase: a plain click whose same-named sibling toggled
        }));
    }

    // The mixer of v3-53 as the view read it: «Silenciar 'Mic/Aux'» on with its slider marked, ours off.
    private const string MixerEntries = """
        $mixer=@(
          @{ name="Propiedades para 'Audio del escritorio'"; kind='Button'; toggle='' },
          @{ name="Silenciar 'Audio del escritorio'"; kind='CheckBox'; toggle='Off' },
          @{ name="Deslizador de volumen para 'Audio del escritorio':"; kind='Slider'; toggle='' },
          @{ name="Propiedades para 'Mic/Aux'"; kind='Button'; toggle='' },
          @{ name="Silenciar 'Mic/Aux'"; kind='CheckBox'; toggle='On' },
          @{ name="Deslizador de volumen para 'Mic/Aux': (actualmente silenciado)"; kind='Slider'; toggle='' },
          @{ name='Escena'; kind='ListItem'; toggle='' })
        function Set-Entry($list,[string]$name,[string]$newName,[string]$toggle){
          return @($list | ForEach-Object { if($_.name -eq $name){ @{ name=$newName; kind=$_.kind; toggle=$toggle } } else { $_ } })
        }

        """;

    [Test]
    public void AToggleHoldsOnlyWithTheMarkItsSiblingAlreadyShows()
    {
        string answer = Run(Worker(), ["Get-NameParts", "Get-ToggleWitness", "Test-ToggleWitnessed"], MixerEntries + """
            $witness=Get-ToggleWitness "Silenciar 'Audio del escritorio'" 'CheckBox' 'Off' $mixer
            $boxOnly=Set-Entry $mixer "Silenciar 'Audio del escritorio'" "Silenciar 'Audio del escritorio'" 'On'
            $muted=Set-Entry $boxOnly "Deslizador de volumen para 'Audio del escritorio':" "Deslizador de volumen para 'Audio del escritorio': (actualmente silenciado)" ''
            $answers=@(
              [string]($null -ne $witness),
              [string](Test-ToggleWitnessed $witness $boxOnly),
              [string](Test-ToggleWitnessed $witness $muted))
            [Console]::Out.Write(($answers -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True",  // a sibling of the same kind and template is already where ours goes, and marks its slider
            "False", // v3-53 req 9: the box went on, the slider never gained «(actualmente silenciado)»
            "True",  // the mark appeared for ours: the toggle holds
        }));
    }

    [Test]
    public void AToggleWithoutAnAnalogousSiblingOrWithItsMarkAlreadyEqualNeedsNoWitnessAndUnmutingWaitsForTheMarkToLeave()
    {
        string answer = Run(Worker(), ["Get-NameParts", "Get-ToggleWitness", "Test-ToggleWitnessed"], MixerEntries + """
            $alone=@(@{ name='Ajuste de linea'; kind='CheckBox'; toggle='Off' }, @{ name='Barra de estado'; kind='CheckBox'; toggle='On' })
            $bothOff=Set-Entry $mixer "Silenciar 'Mic/Aux'" "Silenciar 'Mic/Aux'" 'Off'
            $sameMark=Set-Entry $mixer "Deslizador de volumen para 'Audio del escritorio':" "Deslizador de volumen para 'Audio del escritorio': (actualmente silenciado)" ''
            $answers=@(
              [string]($null -eq (Get-ToggleWitness 'Ajuste de linea' 'CheckBox' 'Off' $alone)),
              [string]($null -eq (Get-ToggleWitness "Silenciar 'Audio del escritorio'" 'CheckBox' 'Off' $bothOff)),
              [string]($null -eq (Get-ToggleWitness "Silenciar 'Audio del escritorio'" 'CheckBox' 'Off' $sameMark)),
              [string]($null -eq (Get-ToggleWitness "Silenciar 'Mic/Aux'" 'CheckBox' 'On' $mixer)),
              [string](Test-ToggleWitnessed $null $alone))
            [Console]::Out.Write(($answers -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True",  // a Win32 or WPF check box without an analogous sibling: no extra step
            "True",  // the sibling is not where ours goes: it proves nothing
            "True",  // the sibling's mark is already on ours: nothing to corroborate
            "False", // un-muting Mic/Aux: the sibling already off shows its slider unmarked, so the mark must leave ours
            "True",  // no witness: the box's own change is the receipt, as before
        }));
    }

    [Test]
    public void OfSeveralControlsANameMeetsOnlyTheOneThatPressesCounts()
    {
        string answer = Run(Worker(), ["Select-PressableOne"], """
            $card=@(@{ select=$true; kind='ListItem' }, @{ kind='Group' }, @{ kind='Text' })
            $rows=@(@{ invoke=$true; kind='Button' }, @{ invoke=$true; kind='Button' }, @{ kind='Text' })
            $none=@(@{ kind='Text' }, @{ kind='Group' })
            $search=@(@{ kind='Edit'; value=$true }, @{ invoke=$true; kind='Button' })
            $combo=@(@{ kind='ComboBox' }, @{ invoke=$true; kind='Button' })
            $readOnly=@(@{ kind='Edit'; value=$false }, @{ invoke=$true; kind='Button' })
            [Console]::Out.Write((@((Select-PressableOne $card),(Select-PressableOne $rows),(Select-PressableOne $none),(Select-PressableOne $search),(Select-PressableOne $combo),(Select-PressableOne $readOnly)) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "0",  // v3-61: the card's ListItem, not its Group or Text without a pattern
            "-1", // contracase: two «Eliminar» that press, in different rows, stay ambiguous (the model picks by index)
            "-1", // nothing presses: still ambiguous, never a guess
            "-1", // review of ronda 20b (finding 4): a «Buscar» field and a «Buscar» button are two targets
            "-1", // a combo box is a target too
            "1",  // contracase: a read-only Edit takes no text; the button is the one that presses
        }));
    }

    [Test]
    public void TheClassicMenuBarIsReadAsEntriesAndPressedByItsCommand()
    {
        string answer = Run(Worker(), ["ConvertTo-MenuViewEntries", "Find-MenuCommand", "Test-NameMatch"], """
            function New-Entry([string]$path,[int]$id,[string]$shortcut='',[bool]$checked=$false,[bool]$disabled=$false,[bool]$fills=$false){
              return [pscustomobject]@{ Path=$path; Id=$id; Shortcut=$shortcut; Checked=$checked; Disabled=$disabled; FillsOnOpen=$fills }
            }
            $menu=@(
              (New-Entry ([string]::Concat('Ver ',[char]0x203A,' Iconos grandes')) 28750),
              (New-Entry ([string]::Concat('Ver ',[char]0x203A,' Detalles')) 28747 'Ctrl+Mayús+6' $true),
              (New-Entry ([string]::Concat('Archivo ',[char]0x203A,' Eliminar')) 28689 'Supr'),
              (New-Entry ([string]::Concat('Edición ',[char]0x203A,' Pegar')) 28697 'Ctrl+V' $false $true),
              (New-Entry ([string]::Concat('Archivo ',[char]0x203A,' Recientes')) 0 '' $false $false $true))
            $view=@(ConvertTo-MenuViewEntries $menu)
            $lines=@($view | ForEach-Object { $_.kind+'|'+$_.id+'|'+$_.state+'|'+$_.shortcut })
            $byId=Find-MenuCommand $menu @() 'hmenu.28747'
            $byLabel=Find-MenuCommand $menu @('Detalles') ''
            $byPath=Find-MenuCommand $menu @([string]::Concat('Ver ',[char]0x203A,' Detalles')) ''
            $mismatch=Find-MenuCommand $menu @('Iconos grandes') 'hmenu.28747'
            $staticallyDisabled=Find-MenuCommand $menu @('Pegar') ''
            $absent=Find-MenuCommand @() @('Detalles') ''
            $deleting=Find-MenuCommand $menu @('Eliminar') ''
            $answers=$lines+@([string]$byId.entry.Id,[string]$byLabel.entry.Id,[string]$byPath.entry.Id,[string]$mismatch.error,[string]$staticallyDisabled.entry.Id,[string]$absent.error,[string]$deleting.entry.Path)
            [Console]::Out.Write(($answers -join ';'))
            """);
        Assert.That(answer.Split(';'), Is.EqualTo(new[]
        {
            "MenuItem|hmenu.28750||",
            "MenuItem|hmenu.28747|checkable|Ctrl+Mayús+6", // review of ronda 20b (finding 2): the static check is
                                                        // the last opening's (WM_INITMENUPOPUP), never published as
                                                        // «on»; review 2 (B2): only the neutral fact that it is a setting
            "MenuItem|hmenu.28689||Supr",
            "MenuItem|hmenu.28697||Ctrl+V",             // nor the static «disabled»
            "MenuItem||fills-on-open|",                 // filled when it opens: listed, never pressed by command
            "28747",
            "28747",                                    // v3-49: «Detalles» is the last part of «Ver › Detalles»
            "28747",
            "visible_control_label_mismatch",
            "28697",                                    // a statically disabled entry is sent: the application decides
            "visible_button_not_found",                 // contracase: a window without an HMENU changes nothing
            "Archivo › Eliminar",                       // its whole path reaches the name guards of the mind
        }));
    }

    // Review 2 of ronda 20b (B3): what changes between the two reads before the press is learned as volatile, of any kind
    // (a «REC 00:00:12» button); a text that changes in its place is a label updating itself. What comes or goes, the
    // title, and a renamed control that is not a text still move the place.
    [Test]
    public void ThePlaceMovesOnlyByWhatDoesNotChangeAlone()
    {
        string answer = Run(Worker(), ["Get-SteadyPlace", "Test-PlaceTooDear", "Test-PlaceMoved"], Places + """
            function With-Item($place,[string]$key,[string]$kind,[string]$name){
              $items=@{}; foreach($k in @($place.items.Keys)){ $items[$k]=$place.items[$k] }
              if($kind.Length -eq 0){ $items.Remove($key) } else { $items[$key]=@{ kind=$kind; name=$name } }
              return @{ title=$place.title; items=$items; volatile=@{} }
            }
            $rec1=With-Item $general '1.95' 'Button' 'REC 00:00:12'
            $rec2=With-Item $general '1.95' 'Button' 'REC 00:00:13'
            $rec3=With-Item $general '1.95' 'Button' 'REC 00:00:14'
            $script:Reads=@($rec1,$rec2)
            function Get-PlaceTrace([IntPtr]$top){ $next=$script:Reads[0]; $script:Reads=@($script:Reads | Select-Object -Skip 1); return $next }
            $steady=Get-SteadyPlace ([IntPtr]77)
            $renamedRow=With-Item $rec3 '1.11' 'ListItem' 'Video (2)'
            $newText=With-Item $rec3 '1.41' 'Text' 'Resolucion base'
            $goneRow=With-Item $rec3 '1.11' '' ''
            $retitled=@{ title='Ajustes - Video'; items=$rec3.items; volatile=@{} }
            $answers=@(
              [string]$steady.volatile.ContainsKey('1.95'),
              [string](Test-PlaceMoved $steady $rec3),
              [string](Test-PlaceMoved $steady (With-Item $rec3 '1.90' 'Text' 'CPU: 9.9%, 12.00 fps')),
              [string](Test-PlaceMoved $steady $renamedRow),
              [string](Test-PlaceMoved $steady $newText),
              [string](Test-PlaceMoved $steady $goneRow),
              [string](Test-PlaceMoved $steady $retitled))
            [Console]::Out.Write(($answers -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True",  // the recording counter ticked between the two reads before: learned as volatile
            "False", // it ticks again after: no move
            "False", // the status text changed in its place without ticking before: a label updating itself
            "True",  // contracase: a row renamed (not a text) moves the place
            "True",  // contracase: a section's text came
            "True",  // contracase: a row went
            "True",  // contracase: the title changed
        }));
    }

    // Review 2 of ronda 20b (B1): the entries of a closed menu are not on screen; they go after what the window shows,
    // only in the room the tree leaves below the cap, and only those listed count in the total.
    [Test]
    public void TheClassicMenuNeverPushesOutWhatTheWindowShows()
    {
        // Ronda 21: the cut of a crowded view folds a row's same-named field and orders by structure (its helpers).
        string answer = Run(Worker(), ["Join-ViewControls", "Get-FoldedFields", "Test-WantedName", "Get-Folded", "Test-CenterWithin"], """
            $script:ViewRowKinds=@('ListItem','TreeItem','DataItem');$script:WantedRoom=10
            $primary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 20;$k++){ [void]$primary.Add(@{ kind='Button'; name=('Herramienta '+$k) }) }
            $secondary=New-Object System.Collections.ArrayList
            foreach($name in @('Nombre','Tamaño')){ [void]$secondary.Add(@{ kind='HeaderItem'; name=$name }) }
            [void]$secondary.Add(@{ kind='Text'; name='3 objetos seleccionados' })
            $menu=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 80;$k++){ [void]$menu.Add(@{ kind='MenuItem'; name=([string]::Concat('Archivo ',[char]0x203A,' Orden ',$k)) }) }
            $joined=Join-ViewControls $primary $secondary $menu 60
            $kinds=@($joined.controls | ForEach-Object { $_.kind })
            $full=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 70;$k++){ [void]$full.Add(@{ kind='Button'; name=('B'+$k) }) }
            $crowded=Join-ViewControls $full $secondary $menu 60
            $small=Join-ViewControls $primary $secondary @() 60
            $answers=@(
              [string]$joined.controls.Count,
              [string]$joined.menuListed,
              [string]@($kinds | Where-Object { $_ -eq 'HeaderItem' }).Count,
              [string]@($kinds | Where-Object { $_ -eq 'Text' }).Count,
              [string]$kinds[22],
              [string]$kinds[23],
              [string]$crowded.controls.Count,
              [string]$crowded.menuListed,
              [string]$small.controls.Count)
            [Console]::Out.Write(($answers -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "59",       // the view stays below its cap: a full view still means the tree had more
            "36",       // the menu fills only the room the window's own controls leave
            "2",        // «Nombre» and «Tamaño» are kept
            "1",        // the status text is kept
            "Text",     // what the window shows comes first
            "MenuItem", // then the menu
            "60",       // a tree that fills the cap by itself
            "0",        // leaves no room for the menu
            "23",       // contracase: a window without an HMENU lists what it did
        }));
    }

    // Ronda 24b (banco r23 s04): chosen is not arrived. A tree node or a tab chosen by Invoke whose place stays (Explorer's
    // Win32 navigation tree marked «Downloads» without navigating) gets its Invoke once more (estabilización y5: the
    // posted press never opened that tree's folder live), its receipt saying whether the place moved; a place that moved
    // at once gets no second press; a list row and a toggle keep one press. A bare container is refused before any
    // press (u9).
    [Test]
    public void AChosenPlaceThatDidNotMoveGetsItsInvokeOnceMoreAndABareContainerIsRefused()
    {
        string answer = Run(Worker(), ["Invoke-NamedControl", "Test-PlaceMoved", "Get-SteadyPlace", "Test-PlaceTooDear", "Wait-PlaceMoved", "Get-PressPoint", "Get-CurrentRect", "Get-RenderHosts", "Select-ClickMethods"], Places + """
            # The worker's own data (the syntax tree the harness parsed), never a copy of it.
            foreach($var in @('$script:PlaceItemKinds','$script:ContainerKinds')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq $var },$true))
              if($found.Count -ne 1){ throw ('data missing: '+$var) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            Add-Type -TypeDefinition @'
            public static class BaxyUiaTimedPress {
              public static int Invoked = 0;
              public static bool InvokeWithin(object el, int ms) { Invoked++; return true; }
            }
            '@
            $script:InvokeWaitMs=1000
            $script:PatternMethods=@('invoke','select','toggle','expand','target','render')
            $script:RenderHosts=@()
            $script:Facts=$null
            function Get-ClickFacts($el){ return $script:Facts.Clone() }
            function Test-Selected($el){ return $false }
            function Wait-Chosen($el){ return $true }
            function Get-InvokeTrace($el,$top){ return @{ present=$true; enabled=$true; title='' } }
            function Test-InvokeActedAlone($before,$after){ return $false }
            $script:Selects=0
            function Select-Element($el){ $script:Selects++ }
            $script:PlaceReads=0
            $script:After=$general
            function Get-PlaceTrace([IntPtr]$top){ $script:PlaceReads++; if($script:PlaceReads -le 2){ return $general }; return $script:After }
            function Test-PointIsElement($el,$point){ return $true }
            function Get-HolderWindow($el){ return [IntPtr]5 }
            $answers=foreach($case in @(
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$true; kind='TreeItem'; value=$false; classic=$true; native=$false }; after=$general },
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$true; kind='TreeItem'; value=$false; classic=$true; native=$false }; after=$video },
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='TabItem'; value=$false; classic=$false; native=$false }; after=$general },
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='ListItem'; value=$false; classic=$true; native=$false }; after=$general },
              @{ facts=@{ invoke=$true; select=$true; toggle=$true; expand=$false; kind='TreeItem'; value=$false; classic=$true; native=$false }; after=$general },
              @{ facts=@{ invoke=$false; select=$false; toggle=$false; expand=$false; kind='DataGrid'; value=$false; classic=$false; native=$false }; after=$general },
              @{ facts=@{ invoke=$true; select=$false; toggle=$false; expand=$false; kind='List'; value=$false; classic=$false; native=$false }; after=$general })){
              $script:Facts=$case.facts
              $script:After=$case.after
              $script:Selects=0; $script:PlaceReads=0; [BaxyUiaTimedPress]::Invoked=0
              [BaxyUiaWorkerNative]::Posted.Clear()
              $current=New-Object psobject -Property @{ ProcessId=0; NativeWindowHandle=0 }
              $el=New-Object psobject -Property @{ Current=$current }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(60,35)) }
              $done=Invoke-NamedControl $el ([IntPtr]77)
              ([string]$done.method)+'|'+[BaxyUiaTimedPress]::Invoked+'|'+$script:Selects+'|'+[BaxyUiaWorkerNative]::Posted.Count+'|'+[string]$done.placeMoved+'|'+[string]($null -ne $done.placeBefore)+'|'+[string][bool]$done.chosenAlready
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "invoke|2|0|0|False|False|False", // s04, y5: Invoke chose the node, the place stayed: its Invoke once more
                                              // (never the posted press, never Select), the receipt says it stayed
            "invoke|1|0|0|True|False|False",  // contracase: the node navigated when chosen: no second press
            "invoke|2|0|0|False|False|False", // a tab chosen and still: its Invoke once more, the receipt says it stayed
            "invoke|1|0|0|False|False|False", // contracase: a list row that only chooses keeps its single press; its
                                              // receipt measures the place (review 1, B2: the mind judges the row)
            "invoke|1|0|0||False|False",      // contracase: a toggle never gets a second way
            "container|0|0|0||False|False",   // u9: a grid with neither Invoke nor SelectionItem: nothing is pressed
            "invoke|1|0|0||False|False",      // contracase: a list that has Invoke keeps it
        }));
    }

    // Estabilización y5 (banco h1, «andá a Descargas y después a Imágenes»): the real views. «Imágenes» of Explorer's
    // navigation tree (Win32, Invoke + SelectionItem + ExpandCollapse) chosen by Invoke while the window stayed at
    // «Downloads»; then the posted press, and the folder never opened. Measured on Explorer (redpc 2026-10-11): the
    // node's second Invoke opened it every time (~120 ms). The node gets its Invoke once more and the receipt says
    // whether the window went to the folder; it never gets the posted press. Contracases: the folder opened at the first
    // Invoke (no second one), a node that stays after both (said as stayed), a content row (one press).
    [Test]
    public void AnExplorerNodeChosenWithoutOpeningGetsItsInvokeOnceMoreNeverThePostedPress()
    {
        string answer = Run(Worker(), ["Invoke-NamedControl", "Test-PlaceMoved", "Get-SteadyPlace", "Test-PlaceTooDear", "Wait-PlaceMoved", "Get-PressPoint", "Get-CurrentRect", "Get-RenderHosts", "Select-ClickMethods"], """
            foreach($var in @('$script:PlaceItemKinds','$script:ContainerKinds')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq $var },$true))
              if($found.Count -ne 1){ throw ('data missing: '+$var) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            function New-Folder([string]$title,[string[]]$rows){
              $items=@{ '1.27333024.0.286702528'=@{ kind='TreeItem'; name='Downloads' }; '1.27333024.0.286703088'=@{ kind='TreeItem'; name='Imágenes' } }
              $n=20
              foreach($row in $rows){ $items['42.'+$n]=@{ kind='ListItem'; name=$row }; $n++ }
              return @{ title=$title; items=$items; volatile=@{} }
            }
            $downloads=New-Folder 'Downloads - Explorador de archivos' @('Intelectra_Galactico_Agil_18s','Inte','BAXY-traspaso-2026-09-21')
            $pictures=New-Folder 'Imágenes - Explorador de archivos' @('Capturas de pantalla','Álbum de cámara')
            Add-Type -TypeDefinition @'
            public static class BaxyUiaTimedPress {
              public static int Invoked = 0;
              public static bool InvokeWithin(object el, int ms) { Invoked++; return true; }
            }
            '@
            $script:InvokeWaitMs=1000
            $script:PatternMethods=@('invoke','select','toggle','expand','target','render')
            $script:RenderHosts=@()
            $script:Facts=$null
            function Get-ClickFacts($el){ return $script:Facts.Clone() }
            function Test-Selected($el){ return $false }
            function Wait-Chosen($el){ return $true }
            function Get-InvokeTrace($el,$top){ return @{ present=$true; enabled=$true; title='' } }
            function Test-InvokeActedAlone($before,$after){ return $false }
            $script:Selects=0
            function Select-Element($el){ $script:Selects++ }
            # The folder the window shows after the Invoke number «OpensAt» (0: never).
            $script:OpensAt=0
            function Get-PlaceTrace([IntPtr]$top){
              if($script:OpensAt -gt 0 -and [BaxyUiaTimedPress]::Invoked -ge $script:OpensAt){ return $pictures }
              return $downloads
            }
            function Test-PointIsElement($el,$point){ return $true }
            function Get-HolderWindow($el){ return [IntPtr]5 }
            $node=@{ invoke=$true; select=$true; toggle=$false; expand=$true; kind='TreeItem'; value=$false; classic=$true; native=$false }
            $row=@{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='ListItem'; value=$false; classic=$true; native=$false }
            $answers=foreach($case in @(@{ facts=$node; opens=2 }, @{ facts=$node; opens=1 }, @{ facts=$node; opens=0 }, @{ facts=$row; opens=0 })){
              $script:Facts=$case.facts; $script:OpensAt=$case.opens
              $script:Selects=0; [BaxyUiaTimedPress]::Invoked=0
              [BaxyUiaWorkerNative]::Posted.Clear()
              $current=New-Object psobject -Property @{ ProcessId=0; NativeWindowHandle=0 }
              $el=New-Object psobject -Property @{ Current=$current }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(60,35)) }
              $done=Invoke-NamedControl $el ([IntPtr]77)
              ([string]$done.method)+'|'+[BaxyUiaTimedPress]::Invoked+'|'+$script:Selects+'|'+[BaxyUiaWorkerNative]::Posted.Count+'|'+[string]$done.placeMoved
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "invoke|2|0|0|True",  // y5: chosen at «Downloads», the second Invoke opened «Imágenes»
            "invoke|1|0|0|True",  // contracase: opened at the first Invoke, no second one
            "invoke|2|0|0|False", // a node that stays after both: the receipt says it stayed, nothing posted
            "invoke|1|0|0|False", // contracase: a content row keeps its single press
        }));
    }

    // Ronda 24b: the post-read of the posted press after a choice that held: the place moved is the arrival (placeMoved
    // true); a place that stays leaves the choice true and placeMoved false (the mark is the earlier way's, certain).
    [Test]
    public void ThePostreadOfAChosenPlaceSaysWhetherThePlaceMoved()
    {
        string answer = Run(Worker(), ["Do-Postread", "Click-Result", "Wait-PlaceMoved", "Test-PlaceMoved"], Places + """
            function Test-Selected($el){ return $true }
            function Get-Toggle($el){ return $null }
            function Test-FieldTook($el,$before){ return $false }
            $script:Places=@()
            function Get-PlaceTrace([IntPtr]$top){
              if($script:Places.Count -eq 0){ return $general }
              $next=$script:Places[0]; $script:Places=@($script:Places | Select-Object -Skip 1); return $next
            }
            $current=New-Object psobject -Property @{ IsEnabled=$true; IsOffscreen=$false }
            $el=New-Object psobject -Property @{ Current=$current }
            $answers=foreach($case in @(@{ places=@(); chosen=$true }, @{ places=@($video); chosen=$true }, @{ places=@(); chosen=$false; moved=$false }, @{ places=@(); chosen=$false; moved=$true })){
              $script:Places=@($case.places)
              $before=$(if($case.chosen){ $general } else { $null })
              $script:Pending=@{ native=$null; element=$el; toggleBefore=$null; lineage=@(); name='Downloads'; identity='tree.3'; kind='TreeItem'; method=$(if($case.chosen){ 'message' } else { 'invoke' }); placeBefore=$before; chosenAlready=[bool]$case.chosen; placeMoved=$case.moved; top=[IntPtr]77; topEnabled=$true }
              $read=Do-Postread @{}
              [string]$read.ok+'|'+[string]$read.selected+'|'+[string]$read.placeMoved+'|'+[string]([bool]$read.effectUncertain)
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True|True|False|False", // s04: chosen, the posted press did not move the place: chosen without arriving
            "True|True|True|False",  // the posted press navigated: the arrival
            "True|True|False|False", // the receipt of an Invoke whose place stayed and had no posted way
            "True|True|True|False",  // contracase: the place moved at the first press
        }));
    }

    // Revision 1 of r24b (B2, B3): every way that chooses an item says whether the place moved: the Select that is the
    // last way (WPF, WinUI, Chromium's tree without a posted press), the Invoke that acted alone, a navigation item
    // that is a ListItem; a blocked Invoke leaves the measure to the post-read with the window it needs. Only a node or
    // a tab gets the second press.
    [Test]
    public void EveryWayThatChoosesAnItemSaysWhetherThePlaceMoved()
    {
        string answer = Run(Worker(), ["Invoke-NamedControl", "Test-PlaceMoved", "Get-SteadyPlace", "Test-PlaceTooDear", "Wait-PlaceMoved", "Get-PressPoint", "Get-CurrentRect", "Get-RenderHosts", "Select-ClickMethods"], Places + """
            foreach($var in @('$script:PlaceItemKinds','$script:ContainerKinds')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq $var },$true))
              if($found.Count -ne 1){ throw ('data missing: '+$var) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            Add-Type -TypeDefinition @'
            public static class BaxyUiaTimedPress {
              public static int Invoked = 0;
              public static bool Answers = true;
              public static bool InvokeWithin(object el, int ms) { Invoked++; return Answers; }
            }
            '@
            $script:InvokeWaitMs=1000
            $script:PatternMethods=@('invoke','select','toggle','expand','target','render')
            $script:RenderHosts=@()
            $script:Facts=$null
            $script:Chosen=$true
            $script:ActedAlone=$false
            function Get-ClickFacts($el){ return $script:Facts.Clone() }
            function Test-Selected($el){ return $false }
            function Wait-Chosen($el){ return $script:Chosen }
            function Get-InvokeTrace($el,$top){ return @{ present=$true; enabled=$true; title='' } }
            function Test-InvokeActedAlone($before,$after){ return $script:ActedAlone }
            $script:Selects=0
            function Select-Element($el){ $script:Selects++ }
            $script:PlaceReads=0
            $script:After=$general
            function Get-PlaceTrace([IntPtr]$top){ $script:PlaceReads++; if($script:PlaceReads -le 2){ return $general }; return $script:After }
            function Test-PointIsElement($el,$point){ return $true }
            function Get-HolderWindow($el){ return [IntPtr]5 }
            $answers=foreach($case in @(
              @{ facts=@{ invoke=$false; select=$true; toggle=$false; expand=$false; kind='TabItem'; value=$false; classic=$false; native=$false }; after=$general; chosen=$true; alone=$false; answers=$true },
              @{ facts=@{ invoke=$false; select=$true; toggle=$false; expand=$false; kind='TabItem'; value=$false; classic=$false; native=$false }; after=$video; chosen=$true; alone=$false; answers=$true },
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='TabItem'; value=$false; classic=$false; native=$false }; after=$video; chosen=$false; alone=$true; answers=$true },
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='TreeItem'; value=$false; classic=$false; native=$false }; after=$general; chosen=$false; alone=$true; answers=$true },
              @{ facts=@{ invoke=$false; select=$true; toggle=$false; expand=$false; kind='ListItem'; value=$false; classic=$false; native=$false }; after=$general; chosen=$true; alone=$false; answers=$true },
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='ListItem'; value=$false; classic=$true; native=$false }; after=$general; chosen=$true; alone=$false; answers=$true },
              @{ facts=@{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='TabItem'; value=$false; classic=$false; native=$false }; after=$general; chosen=$true; alone=$false; answers=$false },
              @{ facts=@{ invoke=$true; select=$false; toggle=$false; expand=$false; kind='Button'; value=$false; classic=$false; native=$false }; after=$general; chosen=$true; alone=$false; answers=$true })){
              $script:Facts=$case.facts
              $script:After=$case.after
              $script:Chosen=$case.chosen; $script:ActedAlone=$case.alone; [BaxyUiaTimedPress]::Answers=$case.answers
              $script:Selects=0; $script:PlaceReads=0; [BaxyUiaTimedPress]::Invoked=0
              [BaxyUiaWorkerNative]::Posted.Clear()
              $current=New-Object psobject -Property @{ ProcessId=0; NativeWindowHandle=0 }
              $el=New-Object psobject -Property @{ Current=$current }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(60,35)) }
              $done=Invoke-NamedControl $el ([IntPtr]77)
              ([string]$done.method)+'|'+[BaxyUiaTimedPress]::Invoked+'|'+$script:Selects+'|'+[BaxyUiaWorkerNative]::Posted.Count+'|'+[string]$done.placeMoved+'|'+[string]($null -ne $done.steadyBefore)+'|'+[string]$done.steadyTop
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "select|0|1|0|False|False|",   // B3: a tab whose only way is Select, the place stayed: measured, not left out
            "select|0|1|0|True|False|",    // B3: the same Select changed the tab: the receipt says so (never «sin efecto»)
            "invoke|1|0|0|True|False|",    // B3: the Invoke that acted alone (the title changed) carries the measure
            "invoke|1|0|0|False|False|",   // B3: an Invoke that acted alone and left the place: measured as such
            "select|0|1|0|False|False|",   // B2: a navigation ListItem chosen by Select alone: measured
            "invoke|1|0|0|False|False|",   // B2 contracase: a list row with a posted way never gets a second press
            "invoke|1|0|0||True|77",       // B3: a blocked Invoke: the post-read measures, with the window it needs
            "invoke|1|0|0||False|",        // contracase: a button chooses nothing and is never measured
        }));
    }

    // Revision 1 of r24b (B3): the post-read of a choice whose press had not happened yet when it was chosen (a blocked
    // Invoke, the pointer) measures the place with the window the choice carried, even where the caller (Do-At) set no
    // window of its own.
    [Test]
    public void ThePostreadMeasuresADeferredChoiceWithTheWindowItCarried()
    {
        string answer = Run(Worker(), ["Do-Postread", "Click-Result", "Wait-PlaceMoved", "Test-PlaceMoved"], Places + """
            function Test-Selected($el){ return $true }
            function Get-Toggle($el){ return $null }
            function Test-FieldTook($el,$before){ return $false }
            $script:Next=$general
            function Get-PlaceTrace([IntPtr]$top){ if($top -ne [IntPtr]77){ throw 'wrong window' }; return $script:Next }
            $current=New-Object psobject -Property @{ IsEnabled=$true; IsOffscreen=$false }
            $el=New-Object psobject -Property @{ Current=$current }
            $answers=foreach($after in @($general,$video)){
              $script:Next=$after
              $script:Pending=@{ native=$null; element=$el; toggleBefore=$null; lineage=@(); name='Avanzado'; identity='tab.2'; kind='TabItem'; method='invoke'; blocked=$true; placeBefore=$null; chosenAlready=$false; placeMoved=$null; steadyBefore=$general; steadyTop=[IntPtr]77 }
              $read=Do-Postread @{}
              [string]$read.ok+'|'+[string]$read.placeMoved
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "True|False", "True|True" }));
    }

    // Revision 1 of r24b (B4): at a point (OCR, a tooltip) a container with neither Invoke nor SelectionItem is skipped,
    // never the end: the next holder of the chain is pressed, and with none the point is left to the pointer
    // (visible_point_no_pattern, nothing sent), never a receipt that something may have happened.
    [Test]
    public void AtAPointAContainerIsSkippedNeverTheEnd()
    {
        string answer = Run(Worker(), ["Do-At", "Click-Result", "Get-AskingName"], """
            function Read-RenderHosts($request){ return @() }
            function Get-RenderHosts($top){ return @() }
            function Get-Root([long]$hwnd){ return @{ hwnd=[IntPtr]77; root=(New-Object psobject -Property @{ Current=(New-Object psobject -Property @{ BoundingRectangle=[System.Windows.Rect]::Empty }) }) } }
            function New-Node([string]$name,[string]$kind){
              $type=New-Object psobject -Property @{ ProgrammaticName=('ControlType.'+$kind) }
              $current=New-Object psobject -Property @{ BoundingRectangle=(New-Object System.Windows.Rect(0,0,10,10)); ControlType=$type; Name=$name }
              return (New-Object psobject -Property @{ Current=$current; Label=$name })
            }
            $script:Chain=@()
            function Get-PointChain($root,$x,$y){ return $script:Chain }
            function Get-Name($node){ return [string]$node.Label }
            function Get-Id($node){ return 'id.'+[string]$node.Label }
            function Get-Toggle($node){ return $null }
            function Select-PointHolders($entries,$aliases,$limit){ return @(0..($entries.Count-1)) }
            $script:Tried=@()
            function Invoke-NamedControl($el,$top,[switch]$PatternsOnly){
              $script:Tried+=[string]$el.Label
              if([string]$el.Current.ControlType.ProgrammaticName -eq 'ControlType.Table'){ return @{ method='container' } }
              if([string]$el.Label -eq 'Fila 3'){ return @{ method='invoke' } }
              return $null
            }
            function Pressed-Result($done,$button,$name,$identity,$kind,$toggleBefore,$lineage){ return @{ ok=$false; error='visible_button_postread_pending'; name=$name; method=$done.method } }
            $script:Rendered=0
            function Send-RenderPress($hosts,$x,$y,$owner,$el,$aliases){ $script:Rendered++; return 'none' }
            $answers=foreach($chain in @(
              @((New-Node 'Celda' 'Custom'),(New-Node 'Tabla' 'Table')),
              @((New-Node 'Tabla' 'Table'),(New-Node 'Fila 3' 'DataItem')))){
              $script:Chain=$chain; $script:Tried=@(); $script:Rendered=0
              $read=Do-At @{ hwnd=77; x=5; y=5; aliases=@('Fila 3') }
              [string]$read.error+'|'+[string]$read.name+'|'+(@($script:Tried) -join '+')+'|'+$script:Rendered
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "visible_point_no_pattern||Celda+Tabla|1", // the cell without a way, the table skipped: the render press is
                                                       // tried and the point is left to the pointer, nothing claimed
            "visible_button_postread_pending|Fila 3|Tabla+Fila 3|0", // the next holder after a container is pressed
        }));
    }

    // Runs a body over the worker's named functions with a stand-in for the native calls: posted presses are recorded.
    private static string Run(string worker, string[] functions, string body)
    {
        string script = """
            $ErrorActionPreference='Stop'
            Add-Type -AssemblyName UIAutomationClient
            Add-Type -AssemblyName UIAutomationTypes
            Add-Type -AssemblyName WindowsBase
            Add-Type -TypeDefinition @'
            using System;
            public static class BaxyUiaWorkerNative {
              public static System.Collections.Generic.List<string> Posted = new System.Collections.Generic.List<string>();
              public static bool HostsRender(IntPtr[] hosts, uint process) { return false; }
              public static bool PostClick(IntPtr top, int x, int y) { Posted.Add(x + "," + y); return true; }
              public static bool PostClick(IntPtr top, int x, int y, IntPtr holder) { Posted.Add(x + "," + y + "@" + holder); return true; }
              public static bool IsWindowEnabled(IntPtr hwnd) { return true; }
            }
            '@
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_CLICK_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            foreach($name in ($env:BAXY_CLICK_FUNCTIONS -split ',')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
              if($found.Count -ne 1){ throw ('function missing: '+$name) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }

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
        start.Environment["BAXY_CLICK_WORKER"] = worker;
        start.Environment["BAXY_CLICK_FUNCTIONS"] = string.Join(',', functions);
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
