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
    // what is drawn: the adapter reads its text unasked, with the OCR lines' authority and the ink marks, and the mission
    // signs its change by that text. The body is never added to such a view (it would make two controls and take the
    // window out of that regime); one already listed is only marked. Contracase: a view that lists more gets it at the
    // end, and a body that came only by the reservation leaves it and goes at the end as always.
    [Test]
    public void TheBodyIsNotAddedToAViewThatListsAtMostOneControl()
    {
        string answer = Run(["Add-ViewBody"], """
            function New-List($entries){ $list=New-Object System.Collections.ArrayList; foreach($e in $entries){ [void]$list.Add($e) }; return ,$list }
            function Show($list){ return ((@($list | ForEach-Object { $_.kind + ':' + [bool]$_.body + ':' + [bool]$_.reserved })) -join ' ') }
            $body=@{ item='el'; kind='Pane'; name='(pane)'; nameSource='kind'; id='9.1'; rect=@{ x=0; y=40; w=800; h=500 }; area=400000 }
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
            "Button:False:False", "0", "Pane:True:False", "0",
            "Button:False:False Button:False:False Pane:True:False", "1",
            "Button:False:False Button:False:False Pane:True:False",
        }));
    }

    private static readonly string[] LineageFunctions =
    [
        "Resolve-ByIdLineage", "Test-ActsByItself", "Get-SameNameLineage", "Test-SameShownName", "Select-LineageOne",
        "Test-Contains", "Test-LineageToggled",
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
        function Get-ShownName($el){ return @{ name=[string]$el.name } }
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
            $body=@{ item='el'; kind='Pane'; name='(pane)'; nameSource='kind'; id='9.9'; rect=@{ x=0; y=40; w=800; h=500 }; area=400000 }
            Add-ViewBody $joined.controls $body @{}
            [Console]::Out.Write((@([string]$script:ViewCap, [string]$script:WantedRoom, [string]($joined.controls.Count-1), [string][bool]$joined.controls[$joined.controls.Count-1].body) -join ','))
            """);
        string[] parts = answer.Split(',');
        int highest = int.Parse(parts[2], System.Globalization.CultureInfo.InvariantCulture);

        Assert.Multiple(() =>
        {
            Assert.That(parts[0], Is.EqualTo(VisibleViewNumbering.Cap.ToString(System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(parts[1], Is.EqualTo(VisibleViewNumbering.WantedRoom.ToString(System.Globalization.CultureInfo.InvariantCulture)));
            Assert.That(parts[3], Is.EqualTo("True"), "the body is the last control of the view");
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

    // The worker hears the goal's words only when the look carries some: a look outside a mission is the old request.
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

    // Encargo IMP3 (imp2 imp-dc-leer: the DM open, the look cut at 60 of 169 with no message in it; measured on redpc the
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
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
