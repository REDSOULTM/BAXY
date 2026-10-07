# Worker UIA persistente del motor de computer use (CONTRATO_VISTA_ACCION.md §1, §2).
#
# Una sola carga de UIAutomationClient y de Add-Type por vida del proceso: la
# herencia (gemma4_agent, uia_fast.py) midio 243 ms de spawn mas 385 ms de
# Add-Type por cada llamada de la ruta anterior (DesktopListVisible.ps1 y
# DesktopClickVisible.ps1, que este worker sustituye). Protocolo: una linea JSON
# por peticion en stdin, una linea JSON por respuesta en stdout; nunca escribe
# otra cosa en stdout. El proceso termina con «exit», con EOF o cuando muere
# su padre.
#
# Comandos:
#   {"cmd":"ping"}
#   {"cmd":"view","hwnd":123,"limit":60}
#   {"cmd":"click","hwnd":123,"aliases":["Biblioteca","Library"],"controlId":"42.1837.4"}
#   {"cmd":"postread"}   (el control del ultimo clic: ausente, seleccionado o conmutado)
#   {"cmd":"scroll","hwnd":123,"controlId":"42.1837.4","direction":"down","amount":3}
#   {"cmd":"find","hwnd":123,"aliases":["Biblioteca"]}
#   {"cmd":"script","script":"...","args":["123"]}   (un guion de UserBrowserScripts, $args como en -Command)
#   {"cmd":"exit"}
#
# -DpiUnaware: el worker de los guiones del navegador conserva la escala que
# tenia el PowerShell de cada llamada al que sustituye (sus coordenadas de
# pestana se convierten en el proceso del producto).
param([switch]$DpiUnaware)
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[System.Text.Encoding]::UTF8
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class BaxyUiaWorkerNative {
  private delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] private static extern bool EnumWindows(EnumProc callback, IntPtr value);
  [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
  [DllImport("user32.dll")] private static extern IntPtr SendMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint procId);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
  [DllImport("user32.dll")] public static extern IntPtr SetProcessDpiAwarenessContext(IntPtr context);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  // Windows PowerShell 5.1 compila Add-Type con C# 5: sin declaraciones «out» en linea (UI1273).
  public static IntPtr[] FindVisibleButtons(IntPtr top, string[] labels) {
    var matches=new List<IntPtr>();
    if(top==IntPtr.Zero) return matches.ToArray();
    EnumChildWindows(top,(child,unusedChild)=>{
      var cls=new StringBuilder(128);GetClassName(child,cls,cls.Capacity);
      if(cls.ToString().IndexOf("BUTTON",StringComparison.OrdinalIgnoreCase)<0
          || !IsWindowVisible(child) || !IsWindowEnabled(child)) return true;
      var name=new StringBuilder(512);GetWindowText(child,name,name.Capacity);
      foreach(string label in labels) if(string.Equals(label,name.ToString(),StringComparison.OrdinalIgnoreCase)) {matches.Add(child);break;}
      return true;
    },IntPtr.Zero);
    return matches.ToArray();
  }
  public static void Click(IntPtr hwnd) { SendMessage(hwnd,0x00F5,IntPtr.Zero,IntPtr.Zero); }
  public static void ClickPoint(int x, int y) { SetCursorPos(x,y); mouse_event(0x0002,0,0,0,UIntPtr.Zero); mouse_event(0x0004,0,0,0,UIntPtr.Zero); }
  public static string Text(IntPtr hwnd) { var text=new StringBuilder(512);GetWindowText(hwnd,text,text.Capacity);return text.ToString(); }
}
'@
# Coordenadas fisicas: la captura con la que se comparan los rectangulos se toma
# en pixeles fisicos (GdiScreenshotPlatform), asi que este proceso no puede ser
# virtualizado por el escalado del monitor. -4 = PER_MONITOR_AWARE_V2.
if(-not $DpiUnaware){ try { [void][BaxyUiaWorkerNative]::SetProcessDpiAwarenessContext([IntPtr](-4)) } catch {} }

$AE=[System.Windows.Automation.AutomationElement]
$Actionable=@('Button','MenuItem','ListItem','TabItem','Hyperlink','CheckBox','RadioButton','Edit','ComboBox','TreeItem','SplitButton','Slider','Document')
$script:LastView=@{ hwnd=[IntPtr]::Zero; elements=@{} }

function Send-Line($object){
  $line=($object | ConvertTo-Json -Compress -Depth 8)
  [Console]::Out.WriteLine($line)
  [Console]::Out.Flush()
}
function Get-Root([long]$hwnd){
  if($hwnd -le 0){ $handle=[BaxyUiaWorkerNative]::GetForegroundWindow() } else { $handle=[IntPtr]$hwnd }
  if($handle -eq [IntPtr]::Zero){ return $null }
  return @{ hwnd=$handle; root=$AE::FromHandle($handle) }
}
function Get-Name($el){
  # Los elementos del arbol vienen con cache; la raiz (FromHandle) no.
  try { $name=$el.Cached.Name } catch { $name=$el.Current.Name }
  if([string]::IsNullOrWhiteSpace($name)){ return '' }
  $name=($name -replace '\s+',' ').Trim()
  # Un nombre largo conserva su principio y su final: el titulo de una pestana
  # termina con el sitio («... - Sitio»), que es por lo que se la nombra.
  if($name.Length -gt 80){ $name=$name.Substring(0,60).TrimEnd()+' ... '+$name.Substring($name.Length-16).TrimStart() }
  return $name
}
function Get-State($el){
  $parts=@()
  $value=$null
  try {
    $pattern=$null
    if($el.TryGetCachedPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
      $state=([System.Windows.Automation.TogglePattern]$pattern).Cached.ToggleState
      if($state -eq [System.Windows.Automation.ToggleState]::On){$parts+='on'} elseif($state -eq [System.Windows.Automation.ToggleState]::Off){$parts+='off'}
    }
    if($el.TryGetCachedPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){
      if(([System.Windows.Automation.SelectionItemPattern]$pattern).Cached.IsSelected){$parts+='selected'}
    }
    if($el.TryGetCachedPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)){
      $state=([System.Windows.Automation.ExpandCollapsePattern]$pattern).Cached.ExpandCollapseState
      if($state -eq [System.Windows.Automation.ExpandCollapseState]::Expanded){$parts+='expanded'} elseif($state -eq [System.Windows.Automation.ExpandCollapseState]::Collapsed){$parts+='collapsed'}
    }
    if($el.TryGetCachedPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){
      $vp=([System.Windows.Automation.ValuePattern]$pattern)
      if($vp.Cached.IsReadOnly){$parts+='readonly'}
      $raw=[string]$vp.Cached.Value
      # An exposed empty value is "" (known empty); a field that exposes none stays null (its content is unknown).
      if(-not [string]::IsNullOrWhiteSpace($raw)){ $raw=($raw -replace '\s+',' ').Trim(); if($raw.Length -gt 120){$raw=$raw.Substring(0,120)}; $value=$raw } else { $value='' }
    } elseif($el.TryGetCachedPattern([System.Windows.Automation.RangeValuePattern]::Pattern,[ref]$pattern)){
      $value=[string]([System.Windows.Automation.RangeValuePattern]$pattern).Cached.Value
    }
    if($el.Cached.IsPassword){$parts+='password'}
    if($el.Cached.HasKeyboardFocus){$parts+='focused'}
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return @{ state=($parts -join ' '); value=$value }
}
function Get-Rect($el){
  try {
    $r=$el.Cached.BoundingRectangle
    if($r.IsEmpty -or [double]::IsInfinity($r.Width) -or [double]::IsNaN($r.X)){ return $null }
    return @{ x=[int][math]::Round($r.X); y=[int][math]::Round($r.Y); w=[int][math]::Round($r.Width); h=[int][math]::Round($r.Height) }
  } catch { return $null }
}
function Get-Id($el){
  try { return (($el.GetRuntimeId() | ForEach-Object { [string]$_ }) -join '.') } catch { return '' }
}
function Test-NameMatch([string]$name,[string[]]$aliases){
  foreach($alias in $aliases){ if([string]::Equals($alias,$name,[StringComparison]::OrdinalIgnoreCase)){ return $true } }
  return $false
}
# Plegado: sin acentos, en minusculas, solo letras y digitos separados por un espacio.
function Get-Folded([string]$text){
  if([string]::IsNullOrWhiteSpace($text)){ return '' }
  $plain=$text.Normalize([Text.NormalizationForm]::FormD) -replace '\p{Mn}',''
  return (($plain.ToLowerInvariant() -replace '[^\p{L}\p{N}]+',' ').Trim())
}
# El nombre lleva la etiqueta como palabras enteras: «Sitio» nombra la pestana
# «Un titulo largo - Sitio». Solo cuenta cuando ningun nombre es igual a la etiqueta.
# A long title names its item by a part of it («... - YouTube»): only items that carry a title (a tab, a list or tree
# row, a link), never a pane or a document whose name is the whole page (measured on a CEF window).
$script:TitledKinds=@('ControlType.TabItem','ControlType.ListItem','ControlType.TreeItem','ControlType.Hyperlink')
function Test-ItemHolds($el,[string[]]$aliases){
  try { if($script:TitledKinds -notcontains $el.Current.ControlType.ProgrammaticName){ return $false } } catch { return $false }
  return (Test-NameHolds (Get-Name $el) $aliases)
}
function Test-NameHolds([string]$name,[string[]]$aliases){
  $words=' '+(Get-Folded $name)+' '
  foreach($alias in $aliases){
    $needle=Get-Folded $alias
    if($needle.Length -gt 0 -and $words.Contains(' '+$needle+' ')){ return $true }
  }
  return $false
}
function Invoke-NamedControl($el){
  $pattern=$null
  if($el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){
    ([System.Windows.Automation.InvokePattern]$pattern).Invoke(); return 'invoke'
  }
  if($el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){
    ([System.Windows.Automation.SelectionItemPattern]$pattern).Select(); return 'select'
  }
  if($el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
    ([System.Windows.Automation.TogglePattern]$pattern).Toggle(); return 'toggle'
  }
  if($el.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)){
    $ec=([System.Windows.Automation.ExpandCollapsePattern]$pattern)
    if($ec.Current.ExpandCollapseState -eq [System.Windows.Automation.ExpandCollapseState]::Expanded){ $ec.Collapse() } else { $ec.Expand() }
    return 'expand'
  }
  # Chromium/Electron items often expose no pattern and no clickable point (measured: a messaging client's server in its
  # sidebar): a person clicks the middle of what they see, so does this.
  $x=$null; $y=$null
  try { $point=$el.GetClickablePoint(); $x=[int]$point.X; $y=[int]$point.Y } catch {
    $box=$el.Current.BoundingRectangle
    if($box.IsEmpty -or $box.Width -le 0 -or $box.Height -le 0){ throw }
    $x=[int]($box.X+$box.Width/2); $y=[int]($box.Y+$box.Height/2)
  }
  [BaxyUiaWorkerNative]::ClickPoint($x,$y)
  return 'click'
}
function Test-Selected($el){
  try {
    $pattern=$null
    if($el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){
      return ([System.Windows.Automation.SelectionItemPattern]$pattern).Current.IsSelected
    }
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return $false
}
function Get-Toggle($el){
  try {
    $pattern=$null
    if($el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
      return [string]([System.Windows.Automation.TogglePattern]$pattern).Current.ToggleState
    }
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return $null
}
# Cada propiedad leida de un elemento es una llamada entre procesos; con un
# CacheRequest el arbol llega con sus propiedades y patrones en una sola
# (medido: VS Code 154 controles 2,2 s -> menos de 1 s).
$script:Cache=New-Object System.Windows.Automation.CacheRequest
foreach($prop in @($AE::NameProperty,$AE::ControlTypeProperty,$AE::IsOffscreenProperty,$AE::BoundingRectangleProperty,
                   $AE::HasKeyboardFocusProperty,$AE::IsPasswordProperty,$AE::IsEnabledProperty,$AE::RuntimeIdProperty,
                   $AE::ItemTypeProperty)){ $script:Cache.Add($prop) }
foreach($pat in @([System.Windows.Automation.TogglePattern]::Pattern,[System.Windows.Automation.SelectionItemPattern]::Pattern,
                  [System.Windows.Automation.ExpandCollapsePattern]::Pattern,[System.Windows.Automation.ValuePattern]::Pattern,
                  [System.Windows.Automation.RangeValuePattern]::Pattern)){ $script:Cache.Add($pat) }
foreach($pp in @([System.Windows.Automation.TogglePattern]::ToggleStateProperty,[System.Windows.Automation.SelectionItemPattern]::IsSelectedProperty,
                 [System.Windows.Automation.ExpandCollapsePattern]::ExpandCollapseStateProperty,[System.Windows.Automation.ValuePattern]::ValueProperty,
                 [System.Windows.Automation.ValuePattern]::IsReadOnlyProperty,[System.Windows.Automation.RangeValuePattern]::ValueProperty)){ $script:Cache.Add($pp) }
$script:Cache.AutomationElementMode=[System.Windows.Automation.AutomationElementMode]::Full
$script:Cache.TreeScope=[System.Windows.Automation.TreeScope]::Element
# Los hijos de un nodo en la vista de control. Un navegador (medido en Opera GX
# tras abrir una pestana nueva) deja un primer hijo muerto: GetFirstChild falla
# alli y FindAll desde la ventana no encuentra nada, mientras los hijos vivos
# siguen alcanzandose desde el ultimo hacia atras (como UserBrowserScripts).
function Get-Children($walker,$node){
  $kids=New-Object System.Collections.Generic.List[object]
  try {
    $child=$walker.GetFirstChild($node,$script:Cache)
    while($null -ne $child -and $kids.Count -lt 400){ $kids.Add($child); $child=$walker.GetNextSibling($child,$script:Cache) }
    return ,$kids
  } catch {}
  $kids.Clear()
  try {
    $child=$walker.GetLastChild($node,$script:Cache)
    while($null -ne $child -and $kids.Count -lt 400){ $kids.Insert(0,$child); $child=$walker.GetPreviousSibling($child,$script:Cache) }
  } catch {}
  return ,$kids
}
# El arbol recorrido nodo a nodo, acotado, cuando FindAll no devuelve nada.
function Get-WalkedDescendants($root){
  $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
  $found=New-Object System.Collections.Generic.List[object]
  $queue=New-Object System.Collections.Generic.Queue[object]
  $queue.Enqueue(@($root,0))
  $visited=0
  while($queue.Count -gt 0 -and $visited -lt 2500){
    $pair=$queue.Dequeue(); $visited++
    foreach($child in (Get-Children $walker $pair[0])){
      try { if($child.Cached.IsEnabled){ $found.Add($child) } } catch {}
      if($pair[1] -lt 26){ $queue.Enqueue(@($child,($pair[1]+1))) }
    }
  }
  return ,$found
}
function Get-Descendants($root){
  $enabled=New-Object System.Windows.Automation.PropertyCondition($AE::IsEnabledProperty,$true)
  $activated=$script:Cache.Activate()
  try {
    $all=$null
    try { $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$enabled) } catch {}
    if($null -eq $all -or $all.Count -eq 0){
      Start-Sleep -Milliseconds 400
      try { $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$enabled) } catch { $all=$null }
    }
    if($null -eq $all -or $all.Count -eq 0){ $all=Get-WalkedDescendants $root }
  } finally { $activated.Dispose() }
  return $all
}
function Do-View($request){
  $limit=[int]$request.limit; if($limit -lt 1){$limit=1}; if($limit -gt 60){$limit=60}
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found' } }
  $root=$target.root
  if($null -eq $root){ return @{ ok=$false; error='visible_controls_root_unavailable' } }
  $all=Get-Descendants $root
  $seen=@{}
  $primary=New-Object System.Collections.ArrayList
  $secondary=New-Object System.Collections.ArrayList
  $elements=@{}
  $focused=$null
  $total=0
  foreach($item in $all){
    try {
      if($item.Cached.IsOffscreen){ continue }
      $name=Get-Name $item
      $kind=$item.Cached.ControlType.ProgrammaticName -replace '^ControlType\.',''
      $stateInfo=Get-State $item
      # Un campo de texto sin nombre sigue siendo accionable: se identifica por su
      # valor o por su clase; el resto sin nombre no informa de nada.
      if([string]::IsNullOrWhiteSpace($name)){
        if($kind -eq 'Edit' -or $kind -eq 'Document'){ $name='(' + $kind.ToLowerInvariant() + ')' } else { continue }
      }
      $rect=Get-Rect $item
      $key=$kind+'|'+$name
      if($seen.ContainsKey($key)){
        $seen[$key].repeated=[int]$seen[$key].repeated+1
        continue
      }
      $total++
      $id=Get-Id $item
      # Lo que la aplicacion dice que es un elemento de lista o arbol (una carpeta, un acceso directo, una aplicacion).
      $itemType=''
      if($kind -eq 'ListItem' -or $kind -eq 'DataItem' -or $kind -eq 'TreeItem'){
        try { $itemType=[string]$item.Cached.ItemType; if($null -eq $itemType){ $itemType='' } else { $itemType=($itemType -replace '\s+',' ').Trim() } } catch { $itemType='' }
      }
      $entry=@{ kind=$kind; name=$name; id=$id; state=$stateInfo.state; value=$stateInfo.value; itemType=$itemType; rect=$rect; repeated=0 }
      $seen[$key]=$entry
      if($Actionable -contains $kind){ [void]$primary.Add($entry) } else { [void]$secondary.Add($entry) }
      if($stateInfo.state -match '\bfocused\b' -and $null -eq $focused){ $focused=$entry }
      if($id.Length -gt 0){ $elements[$id]=$item }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  $controls=New-Object System.Collections.ArrayList
  foreach($entry in $primary){ if($controls.Count -lt $limit){ [void]$controls.Add($entry) } }
  foreach($entry in $secondary){ if($controls.Count -lt $limit){ [void]$controls.Add($entry) } }
  $script:LastView=@{ hwnd=$target.hwnd; elements=$elements }
  $ordered=@()
  $position=0
  foreach($entry in $controls){
    $ordered+=@([pscustomobject]@{ i=$position; kind=$entry.kind; name=$entry.name; id=$entry.id; state=$entry.state; value=$entry.value; itemType=$entry.itemType; rect=$entry.rect; repeated=$entry.repeated })
    $position++
  }
  $focusedOut=$null
  if($null -ne $focused){ $focusedOut=[pscustomobject]@{ kind=$focused.kind; name=$focused.name; value=$focused.value } }
  return @{ ok=$true; error=''; hwnd=[long]$target.hwnd; window=(Get-Name $root); controls=$ordered; controlCount=$total; focused=$focusedOut }
}
function Find-ById($root,[string]$controlId){
  if([string]::IsNullOrWhiteSpace($controlId)){ return $null }
  $cached=$script:LastView.elements[$controlId]
  if($null -ne $cached){
    try { if(-not $cached.Current.IsOffscreen -and $cached.Current.IsEnabled){ return $cached } } catch {}
  }
  foreach($item in (Get-Descendants $root)){
    try { if((Get-Id $item) -eq $controlId -and -not $item.Current.IsOffscreen){ return $item } } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  return $null
}
# Los controles con ese nombre; sin ninguno igual, los que lo llevan como
# palabras (el clic solo sigue si es uno).
function Find-Named($root,[string[]]$aliases){
  $matches=@()
  $holding=@()
  foreach($item in (Get-Descendants $root)){
    try {
      if($item.Current.IsOffscreen){ continue }
      $name=Get-Name $item
      if(Test-NameMatch $name $aliases){ $matches+=@($item) } elseif(Test-ItemHolds $item $aliases){ $holding+=@($item) }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  if($matches.Count -gt 0){ return $matches }
  return $holding
}
function Click-Result([bool]$ok,[bool]$effect,[string]$error,[string]$name,[string]$identity,[bool]$absent,[bool]$selected,[bool]$toggled,[string]$kind){
  return @{ version=2; ok=$ok; effectObserved=$effect; error=$error; name=$name; kind=$kind; controlIdentity=$identity; absentOrDisabled=$absent; selected=$selected; toggled=$toggled; surfaceChanged=$false; cascadeStage='uia'; authority='windows_uia_or_win32_button_postread' }
}
# El clic responde en cuanto invoca («pending»): el adaptador pide «postread»
# cada 50 ms mientras compara la superficie, y se queda con la primera prueba
# (antes: 150 ms de espera previa y 20 x 100 ms de sondeo, 2,6-3,1 s por clic
# en una ventana Electron/CEF que no cambia de estado UIA).
$script:Pending=$null
function Pending-Result($pending){
  $result=Click-Result $false $true 'visible_button_postread_pending' $pending.name $pending.identity $false $false $false $pending.kind
  $result.pending=$true
  return $result
}
function Do-Postread($request){
  $pending=$script:Pending
  if($null -eq $pending){ return (Click-Result $false $false 'visible_click_no_pending' '' '' $false $false $false '') }
  $absent=$false;$selected=$false;$toggled=$false
  if($null -ne $pending.native){
    $handle=$pending.native
    $absent=(-not [BaxyUiaWorkerNative]::IsWindow($handle)) -or (-not [BaxyUiaWorkerNative]::IsWindowVisible($handle)) -or (-not [BaxyUiaWorkerNative]::IsWindowEnabled($handle))
  } else {
    $button=$pending.element
    try {
      if(-not $button.Current.IsEnabled -or $button.Current.IsOffscreen){$absent=$true}
      elseif(Test-Selected $button){$selected=$true}
      elseif($null -ne $pending.toggleBefore){ $after=Get-Toggle $button; if($null -ne $after -and $after -ne $pending.toggleBefore){$toggled=$true} }
    }
    catch [System.Windows.Automation.ElementNotAvailableException] {$absent=$true}
  }
  if(-not $absent -and -not $selected -and -not $toggled){ return (Click-Result $false $true 'visible_button_postread_unchanged' $pending.name $pending.identity $false $false $false $pending.kind) }
  $script:Pending=$null
  return (Click-Result $true $true '' $pending.name $pending.identity $absent $selected $toggled $pending.kind)
}
function Do-Click($request){
  $script:Pending=$null
  $aliases=@($request.aliases | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $controlId=[string]$request.controlId
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return (Click-Result $false $false 'active_window_not_found' '' '' $false $false $false '') }
  $root=$target.root
  $matches=@()
  if(-not [string]::IsNullOrWhiteSpace($controlId)){
    $byId=Find-ById $root $controlId
    if($null -eq $byId){ return (Click-Result $false $false 'visible_control_identity_stale' '' $controlId $false $false $false '') }
    if($aliases.Count -gt 0 -and -not (Test-NameMatch (Get-Name $byId) $aliases) -and -not (Test-ItemHolds $byId $aliases)){
      return (Click-Result $false $false 'visible_control_label_mismatch' (Get-Name $byId) $controlId $false $false $false '')
    }
    $matches=@($byId)
  } elseif($aliases.Count -gt 0) {
    $matches=@(Find-Named $root $aliases)
  } else {
    return (Click-Result $false $false 'visible_click_argument_invalid' '' '' $false $false $false '')
  }
  if($matches.Count -eq 0){
    $native=@([BaxyUiaWorkerNative]::FindVisibleButtons($target.hwnd,[string[]]$aliases))
    if($native.Count -gt 1){ return (Click-Result $false $false 'visible_button_ambiguous' '' '' $false $false $false '') }
    if($native.Count -eq 1){
      $nativeButton=$native[0];$name=[BaxyUiaWorkerNative]::Text($nativeButton);$identity=('hwnd.'+$nativeButton.ToInt64())
      [BaxyUiaWorkerNative]::Click($nativeButton)
      $script:Pending=@{ native=$nativeButton; element=$null; toggleBefore=$null; name=$name; identity=$identity; kind='Button' }
      return (Pending-Result $script:Pending)
    }
    return (Click-Result $false $false 'visible_button_not_found' (Get-Name $root) '' $false $false $false '')
  }
  if($matches.Count -ne 1){ return (Click-Result $false $false 'visible_button_ambiguous' '' '' $false $false $false '') }
  $button=$matches[0];$name=Get-Name $button;$identity=Get-Id $button
  $kind=$button.Current.ControlType.ProgrammaticName -replace '^ControlType\.',''
  $toggleBefore=Get-Toggle $button
  try { Invoke-NamedControl $button | Out-Null }
  catch { return (Click-Result $false $false 'visible_button_not_invokable' $name $identity $false $false $false $kind) }
  $script:Pending=@{ native=$null; element=$button; toggleBefore=$toggleBefore; name=$name; identity=$identity; kind=$kind }
  return (Pending-Result $script:Pending)
}
# input.scroll con «index»: el control de la ultima vista se desplaza por su
# ScrollPattern y la prueba es su porcentaje vertical antes y despues; sin
# patron (o sin desplazamiento vertical) el adaptador usa la rueda en su centro.
function Do-Scroll($request){
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found' } }
  $element=Find-ById $target.root ([string]$request.controlId)
  if($null -eq $element){ return @{ ok=$false; error='visible_control_identity_stale' } }
  $pattern=$null
  if(-not $element.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern,[ref]$pattern)){ return @{ ok=$false; error='scroll_pattern_unavailable' } }
  $scroll=[System.Windows.Automation.ScrollPattern]$pattern
  if(-not $scroll.Current.VerticallyScrollable){ return @{ ok=$false; error='scroll_pattern_unavailable' } }
  $before=[double]$scroll.Current.VerticalScrollPercent
  $step=$(if([string]$request.direction -eq 'up'){[System.Windows.Automation.ScrollAmount]::SmallDecrement}else{[System.Windows.Automation.ScrollAmount]::SmallIncrement})
  $amount=[int]$request.amount; if($amount -lt 1){$amount=1}; if($amount -gt 10){$amount=10}
  # Una muesca de rueda son tres lineas.
  for($i=0;$i -lt $amount*3;$i++){
    try { $scroll.Scroll([System.Windows.Automation.ScrollAmount]::NoAmount,$step) } catch [System.InvalidOperationException] { break }
  }
  $after=[double]$scroll.Current.VerticalScrollPercent
  return @{ ok=$true; error=''; scrolled=($after -ne $before); percentBefore=$before; percentAfter=$after; name=(Get-Name $element) }
}
# Los guiones del navegador (UserBrowserScripts) corren en un runspace propio y
# persistente: su «exit» termina el guion, no el worker, y sus variables no se
# filtran entre llamadas. Antes, un PowerShell nuevo por lectura del marco
# (cierre de pestanas medido: 3,1 s por pestana).
$script:ScriptRunspace=$null
function Do-Script($request){
  if($null -eq $script:ScriptRunspace){
    $script:ScriptRunspace=[runspacefactory]::CreateRunspace()
    $script:ScriptRunspace.ApartmentState='STA'
    $script:ScriptRunspace.Open()
  }
  $shell=[powershell]::Create()
  try {
    $shell.Runspace=$script:ScriptRunspace
    [void]$shell.AddScript([string]$request.script,$true)
    foreach($argument in @($request.args)){ [void]$shell.AddArgument([string]$argument) }
    $line=$null
    foreach($item in $shell.Invoke()){
      $text=([string]$item).Trim()
      if($text.StartsWith('{')){ $line=$text }
    }
    if($null -eq $line){ return @{ ok=$false; error='script_no_receipt' } }
    return @{ ok=$true; error=''; line=$line }
  } finally { $shell.Dispose() }
}
function Do-Find($request){
  $aliases=@($request.aliases | ForEach-Object { [string]$_ })
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found'; count=0 } }
  $matches=@(Find-Named $target.root $aliases)
  $names=@($matches | ForEach-Object { Get-Name $_ })
  return @{ ok=$true; error=''; count=$matches.Count; names=$names }
}

while($true){
  $line=[Console]::In.ReadLine()
  if($null -eq $line){ break }
  if([string]::IsNullOrWhiteSpace($line)){ continue }
  try {
    $request=$line | ConvertFrom-Json
    $cmd=[string]$request.cmd
    if($cmd -eq 'exit'){ Send-Line @{ ok=$true; bye=$true }; break }
    elseif($cmd -eq 'ping'){ Send-Line @{ ok=$true; pid=$PID } }
    elseif($cmd -eq 'view'){ Send-Line (Do-View $request) }
    elseif($cmd -eq 'click'){ Send-Line (Do-Click $request) }
    elseif($cmd -eq 'postread'){ Send-Line (Do-Postread $request) }
    elseif($cmd -eq 'scroll'){ Send-Line (Do-Scroll $request) }
    elseif($cmd -eq 'script'){ Send-Line (Do-Script $request) }
    elseif($cmd -eq 'find'){ Send-Line (Do-Find $request) }
    else { Send-Line @{ ok=$false; error='uia_worker_unknown_command' } }
  } catch {
    $reason=[string]$_.Exception.Message
    if($reason.Length -gt 200){ $reason=$reason.Substring(0,200) }
    Send-Line @{ ok=$false; error='visible_controls_uia_failed'; detail=$reason }
  }
}
