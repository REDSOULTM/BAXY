using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 21 (vista ordenada por objetivo y estructura): when what a window shows does not fit the view's cap, the cut is
/// no longer the tree's order. A row's same-named field folds into its row, a bounded room goes to the controls the
/// goal's words name («wanted»), then the controls that are no rows (headers, tabs, bars, menus), then the rows, then
/// the rest; and the window's content surface (its «body») is always listed. The worker's own functions are taken by
/// their syntax tree and run over described controls (the shapes of the r18 views): no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseViewOrderTests
{
    private static readonly string[] JoinFunctions =
        ["Join-ViewControls", "Get-FoldedFields", "Test-WantedName", "Get-Folded", "Test-CenterWithin"];

    private const string Prelude = """
        $script:ViewRowKinds=@('ListItem','TreeItem','DataItem');$script:WantedRoom=10
        function New-Entry([string]$kind,[string]$name,$rect=$null){ return @{ kind=$kind; name=$name; rect=$rect; systemMenu=$false } }
        function Get-Names($joined,[string]$kind){ return @($joined.controls | Where-Object { $_.kind -eq $kind } | ForEach-Object { $_.name }) }
        function Get-Base($joined){ return @($joined.controls | Where-Object { -not [bool]$_.reserved } | ForEach-Object { $_.kind + '|' + $_.name }) }

        """;

    private static string Worker()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    // v3-64 (a services console): rows and their same-named cells filled the cap and the column header «Tipo de inicio»
    // never entered the view. Headers act now and come before the rows; the cells fold into their rows.
    [Test]
    public void AColumnHeaderEntersACrowdedViewAndRowCellsFoldIntoTheirRows()
    {
        string answer = Run(JoinFunctions, Prelude + """
            $primary=New-Object System.Collections.ArrayList
            foreach($name in @('Acción','Ver','Ayuda','Actualizar')){ [void]$primary.Add((New-Entry 'Button' $name)) }
            for($k=0;$k -lt 100;$k++){
              $y=200+$k*20
              [void]$primary.Add((New-Entry 'ListItem' ('Servicio '+$k) @{ x=10; y=$y; w=900; h=20 }))
              [void]$primary.Add((New-Entry 'Edit' ('Servicio '+$k) @{ x=12; y=$y; w=200; h=20 }))
            }
            foreach($name in @('Nombre','Descripción','Estado','Tipo de inicio')){ [void]$primary.Add((New-Entry 'HeaderItem' $name)) }
            $secondary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 10;$k++){ [void]$secondary.Add((New-Entry 'Text' ('Detalle '+$k))) }
            $joined=Join-ViewControls $primary $secondary @() 60
            [Console]::Out.Write((@(
              [string]$joined.controls.Count,
              [string](Get-Names $joined 'HeaderItem').Count,
              [string]((Get-Names $joined 'HeaderItem') -contains 'Tipo de inicio'),
              [string](Get-Names $joined 'Edit').Count,
              [string](Get-Names $joined 'ListItem').Count,
              [string](Get-Names $joined 'Button').Count) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "60", "4", "True", "0", "52", "4" }));
    }

    // Uso-108 (B8; review 16, M6): only a Group or a Custom enters the cut by its pattern; a Text, an Image or a Pane with
    // Invoke do not (Chromium reports Invoke on whatever has a handler).
    [Test]
    public void OnlyAGroupOrACustomEntersTheCutByItsPattern()
    {
        string answer = Run(["Test-PrimaryAction"], """
            Add-Type -AssemblyName UIAutomationClient
            $el=[pscustomobject]@{}
            $el | Add-Member -MemberType ScriptMethod -Name TryGetCachedPattern -Value { param($pattern,$out) return ($pattern -eq [System.Windows.Automation.InvokePattern]::Pattern) }
            [Console]::Out.Write((@((Test-PrimaryAction $el 'Group'),(Test-PrimaryAction $el 'Custom'),(Test-PrimaryAction $el 'Text'),(Test-PrimaryAction $el 'Image'),(Test-PrimaryAction $el 'Pane')) -join ','))
            """);
        Assert.That(answer, Is.EqualTo("True,True,False,False,False"));
    }

    // Uso-108 (B9; review 16, M4): what a press left: the pressed control's own state when that changed; nothing when it
    // reads empty or stayed as it was (the toggle seen was a sibling's, Test-LineageToggled).
    [Test]
    public void NowStateIsThePressedControlsOwnChangeOnly()
    {
        string answer = Run(["Get-NowState"], """
            function Get-Toggle($el){ return $el }
            [Console]::Out.Write((@((Get-NowState 'Off' 'Indeterminate'),(Get-NowState 'On' 'On'),(Get-NowState '' 'On'),(Get-NowState $null 'On'),(Get-NowState 'On' $null)) -join ','))
            """);
        Assert.That(answer, Is.EqualTo("off,,,,on"));
    }

    // Uso-108 (B7): a nameless control is listed only if it holds a state or a value and has an area; a Group, a bare
    // ComboBox or a 0×0 CheckBox are not.
    [Test]
    public void ANamelessControlIsListedOnlyWhenItHoldsSomethingAndHasAnArea()
    {
        string answer = Run(["Test-NamelessHolds"], """
            $box=@{ x=1; y=1; w=16; h=16 };$flat=@{ x=1; y=1; w=0; h=0 }
            [Console]::Out.Write((@(
              (Test-NamelessHolds 'CheckBox' 'off' $null $box),
              (Test-NamelessHolds 'CheckBox' 'indeterminate focused' $null $box),
              (Test-NamelessHolds 'ComboBox' '' 'Arial' $box),
              (Test-NamelessHolds 'CheckBox' 'off' $null $flat),
              (Test-NamelessHolds 'CheckBox' 'off' $null $null),
              (Test-NamelessHolds 'ComboBox' 'collapsed' $null $box),
              (Test-NamelessHolds 'RadioButton' '' $null $box),
              (Test-NamelessHolds 'RadioButton' '' $null $flat),
              (Test-NamelessHolds 'Group' 'on' 'x' $box)) -join ','))
            """);
        // Review 16, M5: an unselected radio has no state and is still one of the options to press.
        Assert.That(answer, Is.EqualTo("True,True,True,False,False,False,True,False,False"));
    }

    // Uso-108 (B7): a check box's text is on its right; a field keeps its label on the left or above.
    [Test]
    public void ACheckBoxTakesTheTextOnItsRightAndAFieldTheOneOnItsLeft()
    {
        string answer = Run(["Get-NearLabel", "Get-Name"], """
            function Get-Prop($e,$p){ return $null }
            function Format-Name([string]$n){ return $n }
            function New-Box([double]$x,[double]$y,[double]$w,[double]$h){ return [pscustomobject]@{ IsEmpty=$false; Left=$x; Top=$y; Right=$x+$w; Bottom=$y+$h; X=$x; Y=$y; Width=$w; Height=$h } }
            function New-Node([string]$kind,[string]$name,$box){ return [pscustomobject]@{ Cached=[pscustomobject]@{ Name=$name; IsOffscreen=$false; BoundingRectangle=$box; ControlType=[pscustomobject]@{ ProgrammaticName=('ControlType.'+$kind) } } } }
            $check=New-Node 'CheckBox' '' (New-Box 100 100 16 16)
            $all=@((New-Node 'Text' 'Grupo' (New-Box 20 100 70 16)),(New-Node 'Text' 'Comprar pan' (New-Box 120 100 90 16)),(New-Node 'Text' 'Lejos abajo' (New-Box 120 300 90 16)))
            $above=New-Node 'Text' 'Titulo' (New-Box 100 70 90 16)
            [Console]::Out.Write((@((Get-NearLabel $check $all $true),(Get-NearLabel $check $all),(Get-NearLabel $check @($all[2]) $true),(Get-NearLabel $check @($above) $true),(Get-NearLabel $check @($above))) -join '|'))
            """);
        Assert.That(answer, Is.EqualTo("Comprar pan|Grupo|||Titulo"));
    }

    // Uso-108 (B15): only a cut view whose walk was whole says the words no control has; a found word, a whole list or a
    // partial walk say nothing.
    [Test]
    public void AWantedWordNoControlHasIsOnlySaidOfACutWholeWalk()
    {
        string answer = Run(["Get-WantedMissing", "Test-WantedName", "Get-Folded"], Prelude + """
            $primary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 70;$k++){ [void]$primary.Add((New-Entry 'Button' ('Boton '+$k))) }
            [void]$primary.Add((New-Entry 'Button' 'Plantillas de correo'))
            $few=@((New-Entry 'Button' 'Uno'))
            [Console]::Out.Write((@(
              ((Get-WantedMissing $primary @() @() @('firmas','plantillas') 60 $true) -join '+'),
              ((Get-WantedMissing $primary @() @() @('firmas') 60 $false) -join '+'),
              ((Get-WantedMissing $few @() @() @('firmas') 60 $true) -join '+'),
              ((Get-WantedMissing $primary @() @() @() 60 $true) -join '+'),
              ((Get-WantedMissing $primary @() @() @('plantilla') 60 $true) -join '+')) -join ','))
            """);
        // Review 16, I3: part of a word in a name is no «nothing has it», though wanted matches whole words.
        Assert.That(answer, Is.EqualTo("firmas,,,,"));
    }

    // Uso-108 (B8): at the cut a control that says it is pressed (a Group with Invoke) enters with the actionable, before
    // text, and in the tree's order after them; a Group with no such pattern stays last. A view with room is not reordered.
    [Test]
    public void AGroupThatPressesEntersACutViewBeforeText()
    {
        string answer = Run(JoinFunctions, Prelude + """
            function New-Group([string]$name,[bool]$presses){ $e=New-Entry 'Group' $name; $e.presses=$presses; return $e }
            $primary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 40;$k++){ [void]$primary.Add((New-Entry 'Button' ('Boton '+$k))) }
            $secondary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 30;$k++){ [void]$secondary.Add((New-Entry 'Text' ('Texto '+$k))) }
            [void]$secondary.Add((New-Group 'Panel mudo' $false))
            [void]$secondary.Add((New-Group 'Abrir informes' $true))
            $cut=Join-ViewControls $primary $secondary @() 60
            $room=Join-ViewControls @((New-Entry 'Button' 'Uno')) @((New-Entry 'Text' 'Dos'),(New-Group 'Tres' $true)) @() 60
            [Console]::Out.Write((@(
              [string]((Get-Names $cut 'Group') -contains 'Abrir informes'),
              [string]((Get-Names $cut 'Group') -contains 'Panel mudo'),
              [string](Get-Names $cut 'Text').Count,
              ((@($room.controls | ForEach-Object { $_.name })) -join '+')) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "True", "False", "19", "Uno+Dos+Tres" }));
    }

    // Uso-108 (B6; review 16, I2): only a Text inside the actionable of its name, with nothing of its own, leaves the view: it
    // is that control's caption. A Text of another name, one with a value or a state, a Group of that name, and above all a
    // Text elsewhere (a calculator's display «5» beside its Button «5») stay: that one is data.
    [Test]
    public void OnlyATextInsideTheActionableOfItsNameLeavesTheView()
    {
        string answer = Run(["Get-InertRepeats", "Get-LabelFolded", "Test-CenterWithin"], Prelude + """
            function New-Line([string]$kind,[string]$name,$rect,[string]$state='',$value=$null){ return @{ kind=$kind; name=$name; rect=$rect; state=$state; value=$value } }
            function Box([int]$x,[int]$y){ return @{ x=$x; y=$y; w=80; h=20 } }
            function In([int]$x,[int]$y){ return @{ x=$x+10; y=$y+2; w=40; h=16 } }
            $primary=New-Object System.Collections.ArrayList
            [void]$primary.Add((New-Line 'Button' 'Enviar' (Box 100 100)))
            [void]$primary.Add((New-Line 'Button' 'Guardar cámbios' (Box 200 100)))
            [void]$primary.Add((New-Line 'Button' 'Ana' (Box 300 100)))
            [void]$primary.Add((New-Line 'Button' '5' (Box 400 100)))
            $secondary=New-Object System.Collections.ArrayList
            foreach($text in @((New-Line 'Text' 'Enviar' (In 100 100)),(New-Line 'Text' 'guardar  CAMBIOS' (In 200 100)),(New-Line 'Text' 'Enviar mensaje' (In 100 100)),
                               (New-Line 'Text' 'Ana' (In 300 100) 'focused'),(New-Line 'Text' 'Ana' (In 300 100) '' '3'),(New-Line 'Group' 'Enviar' (In 100 100)),
                               (New-Line 'Text' '5' (In 400 10)),(New-Line 'Text' 'Ana' $null))){ [void]$secondary.Add($text) }
            # As Do-View takes them out (the first version removed nothing: the function gave its list as one object).
            foreach($entry in @(Get-InertRepeats $primary $secondary)){ [void]$secondary.Remove($entry) }
            [Console]::Out.Write((@($secondary | ForEach-Object { $_.name }) -join '|'))
            """);
        Assert.That(answer, Is.EqualTo("Enviar mensaje|Ana|Ana|Enviar|5|Ana"));
    }

    // v3-24: the view cut 60 of 540 in tree order and the row «Aplicación» that led to the place stayed out; with the
    // goal's words it is listed, after the 60 of the cut and marked «reserved» (revision 1). v3-65: long rows pushed
    // the tabs out of the cap; the tab «Estándar» is listed.
    [Test]
    public void TheGoalsWordsAndTheTabsSurviveTheCut()
    {
        string answer = Run(JoinFunctions, Prelude + """
            $primary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 300;$k++){ [void]$primary.Add((New-Entry 'TreeItem' ('Rama '+$k))) }
            [void]$primary.Add((New-Entry 'TreeItem' 'Aplicación'))
            for($k=0;$k -lt 200;$k++){ [void]$primary.Add((New-Entry 'TreeItem' ('Hoja '+$k))) }
            $secondary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 39;$k++){ [void]$secondary.Add((New-Entry 'Text' ('Valor '+$k))) }
            $before=Join-ViewControls $primary $secondary @() 60
            $after=Join-ViewControls $primary $secondary @() 60 @('aplicacion','application')
            $long=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 70;$k++){ [void]$long.Add((New-Entry 'ListItem' ('Una fila muy larga del historial número '+$k))) }
            [void]$long.Add((New-Entry 'TabItem' 'Estándar'))
            [void]$long.Add((New-Entry 'TabItem' 'Científica'))
            [void]$long.Add((New-Entry 'MenuItem' 'Abrir navegación'))
            $tabs=Join-ViewControls $long @() @() 60
            [Console]::Out.Write((@(
              [string]((Get-Names $before 'TreeItem') -contains 'Aplicación'),
              [string]((Get-Names $after 'TreeItem') -contains 'Aplicación'),
              [string]$after.controls.Count,
              [string]$after.reserved,
              [string][bool]$after.controls[60].reserved,
              [string]((Get-Names $tabs 'TabItem') -contains 'Estándar'),
              [string]((Get-Names $tabs 'MenuItem') -contains 'Abrir navegación'),
              [string](Get-Names $tabs 'ListItem').Count) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "False", "True", "61", "1", "True", "True", "True", "57" }));
    }

    // Contracases: Explorer in details with 200 files and «abrí informe.txt» keeps the rows behind its headers (the
    // named one too); a goal's word common to every file keeps its room bounded and leaves navigation and menus in.
    [Test]
    public void RowsStayBehindTheHeadersAndACommonWordKeepsItsRoomBounded()
    {
        string answer = Run(JoinFunctions, Prelude + """
            $primary=New-Object System.Collections.ArrayList
            foreach($name in @('Atrás','Adelante','Arriba','Nuevo','Ordenar','Ver')){ [void]$primary.Add((New-Entry 'Button' $name)) }
            foreach($name in @('Nombre','Fecha de modificación','Tipo','Tamaño')){ [void]$primary.Add((New-Entry 'HeaderItem' $name)) }
            for($k=0;$k -lt 200;$k++){
              $name=$(if($k -eq 150){ 'informe.txt' } else { 'archivo '+$k+'.txt' })
              [void]$primary.Add((New-Entry 'ListItem' $name @{ x=10; y=(200+$k*20); w=900; h=20 }))
              [void]$primary.Add((New-Entry 'Edit' $name @{ x=40; y=(200+$k*20); w=300; h=20 }))
            }
            for($k=0;$k -lt 12;$k++){ [void]$primary.Add((New-Entry 'MenuItem' ('Menú '+$k))) }
            $named=Join-ViewControls $primary @() @() 60 @('informe')
            $common=Join-ViewControls $primary @() @() 60 @('archivo')
            [Console]::Out.Write((@(
              [string]((Get-Names $named 'ListItem') -contains 'informe.txt'),
              [string](Get-Names $named 'HeaderItem').Count,
              [string](Get-Names $named 'ListItem').Count,
              [string](Get-Names $common 'ListItem').Count,
              [string](Get-Names $common 'Button').Count,
              [string](Get-Names $common 'MenuItem').Count,
              [string](Get-Names $common 'HeaderItem').Count) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True", // the file the goal names, though its row lay past the cut
            "4",    // the headers
            "39",   // the rows still fill the rest of the view, and the named one comes after them
            "48",   // a word in every file: the rows after the window's own controls and at most 10 more
            "6",    // navigation stays
            "12",   // menus stay
            "4",
        }));
    }

    // Revision 1: the cut does not depend on the goal's words. Explorer in a folder of 200 entries: the look before
    // the sub-goal's first act (no words) and the one after it (with «informes») list the same 60, and the second only
    // adds, marked, the rows that name the words and lay past the cut («Informes 2023.xlsx», «Informes viejos»); the row
    // «Informes» inside the cut is not reserved. Without a cut no word adds anything.
    [Test]
    public void TheGoalsWordsOnlyAddMarkedRowsOnTopOfTheSameCut()
    {
        string answer = Run(JoinFunctions, Prelude + """
            $primary=New-Object System.Collections.ArrayList
            foreach($name in @('Atrás','Adelante','Arriba','Nuevo','Ordenar','Ver')){ [void]$primary.Add((New-Entry 'Button' $name)) }
            foreach($name in @('Nombre','Fecha de modificación','Tipo','Tamaño')){ [void]$primary.Add((New-Entry 'HeaderItem' $name)) }
            for($k=0;$k -lt 200;$k++){
              $name=$(if($k -eq 20){ 'Informes' } elseif($k -eq 120){ 'Informes 2023.xlsx' } elseif($k -eq 160){ 'Informes viejos' } else { 'archivo '+$k+'.txt' })
              [void]$primary.Add((New-Entry 'ListItem' $name))
            }
            $plain=Join-ViewControls $primary @() @() 60
            $primary2=New-Object System.Collections.ArrayList
            foreach($entry in $primary){ [void]$primary2.Add((New-Entry ([string]$entry.kind) ([string]$entry.name))) }
            $worded=Join-ViewControls $primary2 @() @() 60 @('informes')
            $small=New-Object System.Collections.ArrayList
            foreach($name in @('Informes','Informes viejos','Ver')){ [void]$small.Add((New-Entry 'ListItem' $name)) }
            $few=Join-ViewControls $small @() @() 60 @('informes')
            $marked=@($worded.controls | Where-Object { [bool]$_.reserved } | ForEach-Object { $_.name })
            [Console]::Out.Write((@(
              [string]((Get-Base $plain) -join ';' -ceq ((Get-Base $worded) -join ';')),
              [string](Get-Base $worded).Count,
              ($marked -join '+'),
              [string][bool](@($worded.controls | Where-Object { $_.name -eq 'Informes' })[0].reserved),
              [string]$few.controls.Count,
              [string]$few.reserved) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True", "60", "Informes 2023.xlsx+Informes viejos", "False", "3", "0",
        }));
    }

    // t-drag-4: the canvas never entered the view. The body is the largest content surface holding no control that
    // acts; the pane that wraps the ribbon and the canvas holds buttons and is not it; a files view (its pane holds the
    // rows) has none.
    [Test]
    public void TheBodyIsTheLargestSurfaceThatHoldsNoControl()
    {
        string answer = Run(["Select-BodySurface", "Test-CenterWithin"], """
            $buttons=@(
              @{ kind='Button'; name='Lápiz'; id='1.1'; rect=@{ x=20; y=40; w=30; h=30 } },
              @{ kind='ListItem'; name='Línea'; id='1.2'; rect=@{ x=60; y=40; w=30; h=30 } })
            $surfaces=@(
              @{ kind='Pane'; name='(pane)'; id='9.1'; rect=@{ x=0; y=0; w=1200; h=800 }; area=960000 },
              @{ kind='Pane'; name='(pane)'; id='9.2'; rect=@{ x=100; y=200; w=900; h=500 }; area=450000 },
              @{ kind='Image'; name='(image)'; id='9.3'; rect=@{ x=100; y=200; w=300; h=200 }; area=60000 })
            $body=Select-BodySurface $surfaces $buttons
            $rows=@(@{ kind='ListItem'; name='informe.txt'; id='2.1'; rect=@{ x=120; y=220; w=600; h=20 } })
            $none=Select-BodySurface @(@{ kind='Pane'; name='(pane)'; id='9.4'; rect=@{ x=100; y=200; w=900; h=500 }; area=450000 }) $rows
            [Console]::Out.Write((@([string]$body.id, [string]($null -eq $none)) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "9.2", "True" }));
    }

    // Revision 2: a window whose tree lists at most one control (CEF, a canvas: one host Pane or one Button) is read by
    // what is drawn: the adapter reads its text unasked, with the OCR lines' authority. The body is never added to such
    // a view (it would make two controls and take the window out of that regime); one already listed stays where it is.
    // Contracase: a view that lists more gets it at the end, and a body that came only by the reservation leaves it and
    // goes at the end as always.
    [Test]
    public void TheBodyIsNotAddedToAViewThatListsAtMostOneControl()
    {
        string answer = Run(["Add-ViewBody"], """
            function New-List($entries){ $list=New-Object System.Collections.ArrayList; foreach($e in $entries){ [void]$list.Add($e) }; return ,$list }
            function Show($list){ return ((@($list | ForEach-Object { $_.kind + ':' + $_.id + ':' + [bool]$_.reserved })) -join ' ') }
            $body=@{ item='el'; kind='Pane'; name='(pane)'; id='9.1'; rect=@{ x=0; y=40; w=800; h=500 }; area=400000 }
            $elements=@{}
            $one=New-List @(@{ kind='Button'; name='Jugar'; id='1.1' })
            Add-ViewBody $one $body $elements
            $none=New-List @()
            Add-ViewBody $none $body $elements
            $frame=New-List @(@{ kind='Pane'; name='Chrome Legacy Window'; id='9.1' })
            Add-ViewBody $frame $body $elements
            $before=$elements.Count
            $many=New-List @(@{ kind='Button'; name='Jugar'; id='1.1' }, @{ kind='Button'; name='Tienda'; id='1.2' })
            Add-ViewBody $many $body $elements
            $cut=New-List @(@{ kind='Button'; name='Jugar'; id='1.1' }, @{ kind='Button'; name='Tienda'; id='1.2' }, @{ kind='Pane'; name='(pane)'; id='9.1'; reserved=$true })
            Add-ViewBody $cut $body @{}
            [Console]::Out.Write((@((Show $one), [string]$none.Count, (Show $frame), [string]$before, (Show $many), [string]$elements.Count, (Show $cut)) -join '|'))
            """);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "Button:1.1:False", "0", "Pane:9.1:False", "0",
            "Button:1.1:False Button:1.2:False Pane:9.1:False", "1",
            "Button:1.1:False Button:1.2:False Pane:9.1:False",
        }));
    }

    private static readonly string[] LineageFunctions =
    [
        "Resolve-ByIdLineage", "Test-ActsByItself", "Get-SameNameLineage", "Test-SameShownName", "Select-LineageOne",
        "Test-Contains", "Test-LineageToggled", "Test-ToggleHeld",
    ];

    // Described UI Automation elements: a node has a name, a kind, its patterns and its children; the walker, the shown
    // name, the lineage entry and the toggle state are read from the description (the worker's own readers stay out).
    private const string LineagePrelude = """
        $script:LineageUp=3;$script:LineageDown=2;$script:LineageNodes=40
        $script:Keys=0
        function New-Node([string]$kind,[string]$name,[string[]]$patterns=@(),$children=@()){
          $script:Keys++
          $node=@{ kind=$kind; name=$name; key=('k'+$script:Keys); parent=$null; children=@($children); toggle=$null
            invoke=($patterns -contains 'invoke'); select=($patterns -contains 'select'); toggles=($patterns -contains 'toggle'); expand=($patterns -contains 'expand') }
          if($node.toggles){ $node.toggle='Off' }
          foreach($child in $node.children){ $child.parent=$node }
          return $node
        }
        $script:Walker=New-Object psobject
        $script:Walker | Add-Member ScriptMethod GetParent { param($n) return $n.parent }
        $script:Walker | Add-Member ScriptMethod GetFirstChild { param($n) if(@($n.children).Count -gt 0){ return $n.children[0] }; return $null }
        $script:Walker | Add-Member ScriptMethod GetNextSibling { param($n)
          if($null -eq $n.parent){ return $null }
          $siblings=@($n.parent.children)
          for($k=0;$k -lt $siblings.Count-1;$k++){ if([object]::ReferenceEquals($siblings[$k],$n)){ return $siblings[$k+1] } }
          return $null }
        function Get-LineageWalker(){ return $script:Walker }
        function Get-ShownName($el){ return [string]$el.name }
        function Get-Toggle($el){ return $el.toggle }
        function Get-LineageEntry($el){
          $ancestors=@(); $up=$el.parent
          while($null -ne $up){ $ancestors+=@($up.key); $up=$up.parent }
          return @{ name=$el.name; key=$el.key; ancestors=$ancestors; rect=$null; invoke=$el.invoke; select=$el.select; toggle=$el.toggles; expand=$el.expand; edit=($el.kind -eq 'Edit'); kind=$el.kind }
        }
        function Show-Resolved($resolved){ return ([string]$resolved.target.kind + ':' + @($resolved.lineage).Count) }

        """;

    // Revision 1 (finding 2): a click by identity on a control that toggles (a CheckBox, a ToggleSwitch), invokes or
    // expands stays on it, whatever its same-named lineage holds: the CheckBox «Recordatorio» inside its row
    // «Recordatorio» (the row only selects) and the switch «Bluetooth» inside its card Button «Bluetooth» (the card
    // invokes and would navigate). The gallery entry of t-drag-4 (a ListItem that only selects, its same-named Button
    // inside) still resolves to the Button, with the ListItem as its lineage.
    [Test]
    public void AClickByIdentityStaysOnAControlThatTogglesInvokesOrExpands()
    {
        string answer = Run(LineageFunctions, LineagePrelude + """
            $check=New-Node 'CheckBox' 'Recordatorio' @('toggle')
            $row=New-Node 'ListItem' 'Recordatorio' @('select') @($check, (New-Node 'Button' 'Eliminar' @('invoke')))
            $toggleSwitch=New-Node 'Button' 'Bluetooth' @('toggle')
            $card=New-Node 'Button' 'Bluetooth' @('invoke') @($toggleSwitch)
            $inner=New-Node 'Button' 'Línea' @('invoke')
            $entry=New-Node 'ListItem' 'Línea' @('select') @($inner)
            $menu=New-Node 'MenuItem' 'Vista' @('expand')
            $holder=New-Node 'Group' 'Vista' @() @($menu)
            [Console]::Out.Write((@(
              (Show-Resolved (Resolve-ByIdLineage $check)),
              (Show-Resolved (Resolve-ByIdLineage $toggleSwitch)),
              (Show-Resolved (Resolve-ByIdLineage $entry)),
              (Show-Resolved (Resolve-ByIdLineage $menu)),
              [string][object]::ReferenceEquals((Resolve-ByIdLineage $entry).lineage[0],$entry)) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "CheckBox:0", "Button:0", "Button:1", "MenuItem:0", "True" }));
    }

    // Contracases of the lineage: a child of another name never joins (the row «Documento» with its Button «Eliminar» is
    // the row alone, and a click on it stays there); the same name joins up and down; a toggled one of the lineage
    // proves the click and an untouched one does not.
    [Test]
    public void TheLineageJoinsOnlyTheSameNameAndItsToggleProvesTheClick()
    {
        string answer = Run(LineageFunctions, LineagePrelude + """
            $delete=New-Node 'Button' 'Eliminar' @('invoke')
            $document=New-Node 'ListItem' 'Documento' @('select') @($delete)
            $inner=New-Node 'Button' 'Línea' @('invoke')
            $entry=New-Node 'ListItem' 'Línea' @('select') @($inner)
            $group=New-Node 'Group' 'Línea' @() @($entry)
            $toggles=@(@{ el=$inner; before='Off' })
            $inner.toggle='Off'
            $still=Test-LineageToggled $toggles
            $inner.toggle='On'
            $moved=Test-LineageToggled $toggles
            [Console]::Out.Write((@(
              [string]@(Get-SameNameLineage $document).Count,
              (Show-Resolved (Resolve-ByIdLineage $document)),
              [string]@(Get-SameNameLineage $entry).Count,
              [string]$still,
              [string]$moved) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[] { "1", "ListItem:0", "3", "False", "True" }));
    }

    // Ronda 23 (índices de vista y esquema, t-menu-2 r21): the worker numbered 61 controls (the cap, then the body) and
    // the catalog took indexes 0..59, so a rule's click on the 61st ended the mission. The worker's own constants and
    // its own join over a full view with the goal's words and a body number up to the kernel's highest index, and the
    // real catalog takes that index on every act on a control of the look (and refuses the next one).
    // BAXY Renew cu (C11, Excel): the ribbon filled the cap and no row of the sheet came into the look. Without words the
    // reserved room takes the rows, by turns between the item types the window gives them (a column header, a row
    // header, a cell...), so a maximized sheet's many column headers no longer leave row «1» out. Contracases: a look
    // whose base already has a row adds none, and a look with words keeps their room.
    [Test]
    public void WithNoRowInTheCutTheReservedRoomTakesTheRowsByTurnsOfTheirType()
    {
        string answer = Run(["Join-ViewControls", "Get-FoldedFields", "Test-WantedName", "Get-Folded", "Test-CenterWithin"], """
            foreach($assignment in @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and @('$script:ViewCap','$script:WantedRoom','$script:ViewRowKinds') -contains $node.Left.Extent.Text },$false))){
              . ([scriptblock]::Create($assignment.Extent.Text))
            }
            $primary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 70;$k++){ [void]$primary.Add(@{ kind='Button'; name=('Cinta '+$k); systemMenu=$false }) }
            $secondary=New-Object System.Collections.ArrayList
            foreach($c in @('A','B','C','D','E','F','G','H','I','J','K','L')){ [void]$secondary.Add(@{ kind='DataItem'; name=$c; itemType='Encabezado de columna'; systemMenu=$false }) }
            foreach($r in 1..3){
              [void]$secondary.Add(@{ kind='DataItem'; name=[string]$r; itemType='Encabezado de fila'; systemMenu=$false })
              foreach($c in @('A','B')){ [void]$secondary.Add(@{ kind='DataItem'; name=($c+$r); itemType='Celda'; systemMenu=$false }) }
            }
            $sheet=Join-ViewControls $primary $secondary @() 60
            $worded=Join-ViewControls $primary $secondary @() 60 @('cinta')
            $rowed=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 55;$k++){ [void]$rowed.Add(@{ kind='Button'; name=('Cinta '+$k); systemMenu=$false }) }
            [void]$rowed.Add(@{ kind='ListItem'; name='Fila vista'; systemMenu=$false })
            $texts=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 15;$k++){ [void]$texts.Add(@{ kind='Text'; name=('Texto '+$k); systemMenu=$false }) }
            [void]$texts.Add(@{ kind='DataItem'; name='Otra fila'; systemMenu=$false })
            $base=Join-ViewControls $rowed $texts @() 60
            [Console]::Out.Write((@(
              (@($sheet.controls | Select-Object -Skip 60 | ForEach-Object { [string]$_.name }) -join ' '),
              [string]$worded.controls.Count,
              [string]$base.controls.Count) -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "A 1 A1 B 2 B1 C 3 A2 D", // a column header, a row header, a cell, by turns; rows past the base, reserved
            "70",                      // contracase: the goal's words keep their room (ten «Cinta» past the cap)
            "60",                      // contracase: a base that already shows a row adds none
        }));
    }

    [Test]
    public void TheHighestIndexAFullViewNumbersIsTheOneTheCatalogTakes()
    {
        string answer = Run(["Join-ViewControls", "Get-FoldedFields", "Test-WantedName", "Get-Folded", "Test-CenterWithin", "Add-ViewBody"], """
            foreach($assignment in @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and @('$script:ViewCap','$script:WantedRoom','$script:ViewRowKinds') -contains $node.Left.Extent.Text },$false))){
              . ([scriptblock]::Create($assignment.Extent.Text))
            }
            $primary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 120;$k++){
              $name=$(if($k -lt 90){ 'Boton '+$k } else { 'Objetivo '+$k })
              [void]$primary.Add(@{ kind='Button'; name=$name; id=('1.'+$k); rect=@{ x=$k; y=0; w=10; h=10 }; systemMenu=$false })
            }
            $joined=Join-ViewControls $primary @() @() $script:ViewCap @('objetivo')
            $body=@{ item='el'; kind='Pane'; name='(pane)'; id='9.9'; rect=@{ x=0; y=40; w=800; h=500 }; area=400000 }
            Add-ViewBody $joined.controls $body @{}
            [Console]::Out.Write((@([string]$script:ViewCap, [string]$script:WantedRoom, [string]($joined.controls.Count-1), [string]$joined.controls[$joined.controls.Count-1].id) -join ','))
            """);
        string[] parts = answer.Split(',');
        int highest = int.Parse(parts[2], System.Globalization.CultureInfo.InvariantCulture);

        Assert.Multiple(() =>
        {
            Assert.That(parts[0], Is.EqualTo(VisibleViewNumbering.Cap.ToString(System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(parts[1], Is.EqualTo(VisibleViewNumbering.WantedRoom.ToString(System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(parts[3], Is.EqualTo("9.9"), "the body is the last control of the view");
            Assert.That(highest, Is.EqualTo(VisibleViewNumbering.HighestIndex));
            foreach ((string operation, string argument, string rest) in new[]
            {
                ("input.visible.click", "index", "\"label\":\"(pane)\""),
                ("input.scroll", "index", "\"amount\":1,\"direction\":\"down\""),
                ("input.text.type", "index", "\"text\":\"hola\""),
            })
            {
                OperationArgumentsSchema schema = ProductCatalog.GetRequired(operation).ArgumentsSchema;
                using JsonDocument taken = JsonDocument.Parse($"{{\"{argument}\":{highest},{rest}}}");
                using JsonDocument past = JsonDocument.Parse($"{{\"{argument}\":{highest + 1},{rest}}}");
                Assert.That(OperationArgumentValidator.IsValid(taken.RootElement, schema), Is.True, $"{operation} {argument}={highest}");
                Assert.That(OperationArgumentValidator.IsValid(past.RootElement, schema), Is.False, $"{operation} {argument}={highest + 1}");
            }
        });
    }

    // The worker hears the goal's words only when the look carries some: without them the view is the usual one.
    [Test]
    public void TheViewRequestCarriesTheGoalsWordsOnlyWhenGiven()
    {
        using JsonDocument given = JsonDocument.Parse("""{"limit":60,"wanted":["aplicacion"," ",3,"application"]}""");
        using JsonDocument none = JsonDocument.Parse("""{"limit":60}""");

        IReadOnlyList<string> words = WindowsVisibleControlAdapter.WantedWords(given.RootElement);

        Assert.Multiple(() =>
        {
            Assert.That(words, Is.EqualTo(new[] { "aplicacion", "application" }));
            Assert.That(WindowsVisibleControlAdapter.WantedWords(none.RootElement), Is.Empty);
            Assert.That(WindowsVisibleControlAdapter.ViewCommand(7, 60, words),
                Is.EqualTo("""{"cmd":"view","hwnd":7,"limit":60,"wanted":["aplicacion","application"]}"""));
            Assert.That(WindowsVisibleControlAdapter.ViewCommand(7, 60, []), Is.EqualTo("""{"cmd":"view","hwnd":7,"limit":60}"""));
        });
    }

    // Encargo IMP3 (imp2 imp-dc-leer: the DM open, the look cut at 60 of 169 with no message in it; measured on the development PC the
    // last 60 of 177 entries hold the ten newest messages): «tail» keeps the tree's last entries, in their order, whatever
    // their kind; without it, or with no cut, the view is the one it always was.
    [Test]
    public void TheTailKeepsTheTreesLastEntriesInOrder()
    {
        string answer = Run([.. JoinFunctions, "Select-TailControls"], Prelude + """
            $primary=New-Object System.Collections.ArrayList
            $secondary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 100;$k++){
              $entry=(New-Entry 'Hyperlink' ('Enlace '+$k)); $entry.seq=$k*2
              [void]$primary.Add($entry)
              $group=(New-Entry 'Group' ('RED , mensaje '+$k+' , 12:'+$k)); $group.seq=$k*2+1
              [void]$secondary.Add($group)
            }
            $tail=Join-ViewControls $primary $secondary @() 60 @() $true
            $plain=Join-ViewControls $primary $secondary @() 60
            $few=Join-ViewControls @($primary[0]) @($secondary[0]) @() 60 @() $true
            [Console]::Out.Write((@(
              [string]$tail.controls.Count,
              [string](Get-Names $tail 'Group').Count,
              [string]$tail.controls[59].name,
              [string]$tail.controls[0].name,
              [string](Get-Names $plain 'Group').Count,
              [string]$few.controls.Count) -join '|'))
            """);
        Assert.That(answer.Split('|'), Is.EqualTo(new[] { "60", "30", "RED , mensaje 99 , 12:99", "Enlace 70", "0", "2" }));
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.ViewCommand(7, 60, [], tail: true),
                Is.EqualTo("""{"cmd":"view","hwnd":7,"limit":60,"tail":true}"""));
            Assert.That(WindowsVisibleControlAdapter.ViewCommand(7, 60, []), Is.EqualTo("""{"cmd":"view","hwnd":7,"limit":60}"""));
        });
    }

    // Ajuste c3 (F09, M5, live on the notebook): the Clock's three «Iniciar», one for each timer, were one entry of the
    // view («Button «Iniciar» ×3») with one index, so the second and the third could not be pressed. A copy that can be
    // pressed, has an identity of its own and lies elsewhere gets its own entry (and index); a copy inside an earlier
    // one (the same control said twice), one with no identity, and the copies of what does not act stay one entry ×N.
    [Test]
    public void ACopyOfAnActionableControlElsewhereGetsItsOwnEntry()
    {
        string answer = Run(["Get-SeenKey", "Test-CenterWithin", "Test-PrimaryAction", "Test-NamelessHolds"], """
            # The walk of Do-View itself (the foreach that keys what it saw), the worker's own $Actionable, and its
            # Test-CopyApart when it has one.
            $copyApart=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Test-CopyApart' },$true))
            if($copyApart.Count -eq 1){ . ([scriptblock]::Create($copyApart[0].Extent.Text)) }
            $actionable=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$Actionable' },$true))
            if($actionable.Count -ne 1){ throw 'data missing: $Actionable' }
            . ([scriptblock]::Create($actionable[0].Extent.Text))
            $view=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Do-View' },$true))
            $walk=@($view[0].Body.FindAll({ param($node) $node -is [System.Management.Automation.Language.ForEachStatementAst] -and $node.Extent.Text -match 'Get-SeenKey' },$true))
            if($walk.Count -ne 1){ throw 'the walk of Do-View is missing' }
            function Get-ShownName($el){ return [string]$el.Shown }
            function Get-State($el){ return @{ state=''; value=$null } }
            function Get-Rect($el){ return $el.Rect }
            function Get-Id($el){ return [string]$el.Id }
            function New-Control([string]$kind,[string]$name,[string]$id,$rect){
              $type=New-Object psobject -Property @{ ProgrammaticName=('ControlType.'+$kind) }
              $cached=New-Object psobject -Property @{ IsOffscreen=$false; ControlType=$type; ClassName=''; AcceleratorKey=''; AccessKey=''; ItemType='' }
              return (New-Object psobject -Property @{ Cached=$cached; Shown=$name; Id=$id; Rect=$rect })
            }
            $script:BodyKinds=@(); $keepOffscreen=$false; $titleBars=@(); $box=$null
            $seen=@{}; $copyRects=@{}; $elements=@{}; $focused=$null; $total=0
            $primary=New-Object System.Collections.ArrayList; $secondary=New-Object System.Collections.ArrayList
            $surfaces=New-Object System.Collections.ArrayList
            $all=@(
              (New-Control 'Button' 'Iniciar' '1.1' @{ x=600; y=100; w=40; h=40 }),
              (New-Control 'Button' 'Iniciar' '1.2' @{ x=600; y=300; w=40; h=40 }),
              (New-Control 'Button' 'Iniciar' '1.3' @{ x=900; y=300; w=40; h=40 }),
              (New-Control 'Button' 'Iniciar' '1.4' @{ x=605; y=105; w=30; h=30 }),
              (New-Control 'Text' 'min' '2.1' @{ x=10; y=10; w=20; h=10 }),
              (New-Control 'Text' 'min' '2.2' @{ x=10; y=50; w=20; h=10 }),
              (New-Control 'Button' 'Expandir' '3.1' @{ x=10; y=500; w=20; h=20 }),
              (New-Control 'Button' 'Expandir' '' @{ x=50; y=500; w=20; h=20 }))
            . ([scriptblock]::Create($walk[0].Extent.Text))
            [Console]::Out.Write((@(@($primary)+@($secondary) | ForEach-Object { $_.kind+'|'+$_.name+'|'+$_.id+'|'+[int]$_.repeated }) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "Button|Iniciar|1.1|1", // the first, with the copy drawn inside it counted
            "Button|Iniciar|1.2|0", // the second timer's, its own entry
            "Button|Iniciar|1.3|0", // the third's
            "Button|Expandir|3.1|1", // a copy with no identity cannot be pressed apart: counted
            "Text|min|2.1|1",       // what does not act stays one entry ×N
        }));
    }

    // Encargo 18 (banco de uso, U45: «ver» run in a terminal, whose look gave only its control and an OCR that misread
    // it): a look that asks for the text reads what the focused control that is no field shows (a console's output) by
    // its visible ranges, each line without the console's row padding and blank lines left out, the last characters kept
    // past the bound and said cut; never a field's (its value is in the view), a password's, nor a Document outside a
    // console window. Only a look that asks for the text asks the worker for it.
    [Test]
    public void TheFocusedConsoleShowsItsVisibleTextOnlyWhenTheLookAsksForText()
    {
        string answer = Run(["Get-FocusShownText"], """
            Add-Type -AssemblyName UIAutomationClient
            $script:FocusShownMax=60
            function New-Holder([string]$text,[bool]$password=$false){
              $range=[pscustomobject]@{ t=$text }
              $range | Add-Member ScriptMethod GetText { param($most) $this.t }
              $pattern=[pscustomobject]@{ r=$range }
              $pattern | Add-Member ScriptMethod GetVisibleRanges { ,@($this.r) }
              $el=[pscustomobject]@{ Current=[pscustomobject]@{ IsPassword=$password }; p=$pattern }
              $el | Add-Member ScriptMethod TryGetCurrentPattern { param($which,$out) $out.Value=$this.p; $true }
              return $el
            }
            function New-Root([string]$class){ return [pscustomobject]@{ Current=[pscustomobject]@{ ClassName=$class } } }
            function Say($shown){ if($null -eq $shown){ return 'none' }; return (([string]$shown.text) -replace "`n",'/') + '#' + [string]$shown.cut }
            $pad=' ' * 50
            $screen="C:\carpeta>ver$pad`r`n$pad`r`nMicrosoft Windows [Version 10.0]$pad`r`n$pad`r`nC:\carpeta>$pad`r`n"
            $long=(@(1..20 | ForEach-Object { 'linea ' + $_ + $pad }) -join "`r`n")
            $terminal=New-Root 'TerminalHost'
            [Console]::Out.Write((@(
              (Say (Get-FocusShownText (New-Holder $screen) 'Text' $terminal)),
              (Say (Get-FocusShownText (New-Holder $screen) 'Document' (New-Root 'ConsoleWindowClass'))),
              (Say (Get-FocusShownText (New-Holder $long) 'Text' $terminal)),
              (Say (Get-FocusShownText (New-Holder $screen) 'Document' (New-Root 'DocumentHost'))),
              (Say (Get-FocusShownText (New-Holder $screen) 'Edit' $terminal)),
              (Say (Get-FocusShownText (New-Holder $screen $true) 'Text' $terminal)),
              (Say (Get-FocusShownText $null 'Text' $terminal))) -join '|'))
            """);
        string screen = @"C:\carpeta>ver/Microsoft Windows [Version 10.0]/C:\carpeta>#False";
        string last = string.Join('/', Enumerable.Range(1, 20).Select(line => "linea " + line))[^60..] + "#True";
        Assert.Multiple(() =>
        {
            Assert.That(answer.Split('|'), Is.EqualTo(new[] { screen, screen, last, "none", "none", "none", "none" }));
            Assert.That(WindowsVisibleControlAdapter.ViewCommand(7, 60, [], focusText: true),
                Is.EqualTo("""{"cmd":"view","hwnd":7,"limit":60,"focusText":true}"""));
        });
    }

    private static string Run(string[] functions, string body)
    {
        string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_VIEW_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            foreach($name in ($env:BAXY_VIEW_FUNCTIONS -split ',')){
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
        start.Environment["BAXY_VIEW_WORKER"] = Worker();
        start.Environment["BAXY_VIEW_FUNCTIONS"] = string.Join(',', functions);
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
