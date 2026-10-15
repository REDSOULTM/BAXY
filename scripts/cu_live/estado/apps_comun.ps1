# App helpers for the generic harness states app_abierta / app_cerrada / documento_en_blanco / bloc_con_texto /
# paint_con_lienzo. Dot-source after comun.ps1. Harness only, never product code.
# Rules (goal v3, point 7; owner 2026-10-07):
#  - The harness only ever closes what it opened: every window it opens goes to propios.jsonl (tipo 'app', pid, hwnd,
#    proceso, nombre, nuevo). A process is stopped by its exact PID only when the harness started it (nuevo) and its
#    name is still the recorded one; shared hosts (explorer, ApplicationFrameHost...) are closed by window, never killed.
#  - VS Code and Opera are never touched (Close-WindowExact refuses them; Assert-NoProtegida below).
#  - Opening tries not to keep the foreground: after the window appears, the foreground goes back to where it was.
# These scripts are UTF-8 without BOM (PowerShell 5.1 reads them as ANSI): no non-ASCII literals here.
# Functions here output their items one by one (never ',@(...)'): callers collect them with @(...), because a lone
# PSCustomObject has no .Count in PowerShell 5.1 and a comma-wrapped array piped on is one object, not its items.

. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$global:AppsAprendidasPath=Join-Path $env:LOCALAPPDATA 'BAXY\cu-estado\apps.json'
$global:AppsHosts=@('explorer','ApplicationFrameHost','svchost','dwm','sihost','ShellExperienceHost','StartMenuExperienceHost','SearchHost','TextInputHost','RuntimeBroker')
$global:AppsProhibidos=@('Code','opera','opera_gx','launcher')

function Get-AppsAprendidas(){
  # Start-menu name -> process name, learned the first time the harness opened that app (never written by hand).
  $h=@{}
  if(Test-Path $global:AppsAprendidasPath){
    try{ $o=[IO.File]::ReadAllText($global:AppsAprendidasPath,[Text.Encoding]::UTF8) | ConvertFrom-Json; foreach($p in $o.PSObject.Properties){ $h[$p.Name]=[string]$p.Value } }catch{}
  }
  $h
}
function Set-AppAprendida([string]$Nombre,[string]$Proceso){
  if(-not $Nombre -or -not $Proceso -or $global:AppsHosts -contains $Proceso){ return }
  $h=Get-AppsAprendidas; if($h[$Nombre] -eq $Proceso){ return }
  $h[$Nombre]=$Proceso
  $d=Split-Path $global:AppsAprendidasPath; if(-not (Test-Path $d)){ New-Item -ItemType Directory -Force $d | Out-Null }
  $o=[ordered]@{}; foreach($k in @($h.Keys | Sort-Object)){ $o[$k]=$h[$k] }
  [IO.File]::WriteAllText($global:AppsAprendidasPath,(([pscustomobject]$o | ConvertTo-Json)+"`n"),(New-Object Text.UTF8Encoding $false))
}

# The Start menu read once per script run (Get-StartApps costs ~0.4 s; verificar and apps_del_caso resolved the same
# app three times). Reset every time this file is dot-sourced, so a run never sees an older Start menu.
$global:AppsMenuInicio=$null
function Get-MenuInicio(){
  if($null -eq $global:AppsMenuInicio){ $global:AppsMenuInicio=@(Get-StartApps) }
  $global:AppsMenuInicio
}

function Resolve-StartApp([string]$Nombre){
  # Exact Start-menu name first, then the only name that starts with it ("OBS Studio" -> "OBS Studio (64bit)").
  $all=@(Get-MenuInicio)
  $e=@($all | Where-Object { $_.Name -eq $Nombre })
  if($e.Count -eq 0){ $e=@($all | Where-Object { $_.Name -like "$Nombre*" }) }
  if($e.Count -eq 1){ return $e[0] }
  $null
}

function Resolve-StartAppForProcess([int]$ProcessId){
  # The Start-menu entry a running process belongs to, from its executable path: a packaged app by its package name
  # (AppID "Microsoft.Windows.Photos_8wekyb3d8bbwe!App" <-> ...\WindowsApps\Microsoft.Windows.Photos_...), a desktop
  # app by the end of its AppID path ("{...}\7-Zip\7zFM.exe"). $null when none or several match.
  $path=$null; try{ $path=(Get-Process -Id $ProcessId -ErrorAction Stop).Path }catch{}
  if(-not $path){ return $null }
  $m=@(Get-MenuInicio | Where-Object {
    ($_.AppID -match '^([A-Za-z0-9.]+)_[a-z0-9]{13}!' -and $path -like ('*\WindowsApps\{0}_*' -f $matches[1])) -or
    ($_.AppID -match '^\{[0-9A-Fa-f-]+\}(\\.+\.exe)$' -and $path -like ('*{0}' -f $matches[1]))
  })
  if($m.Count -eq 1){ $m[0] }else{ $null }
}

if(-not ('EstadoToken' -as [type])){
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class EstadoToken {
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  [DllImport("advapi32.dll")] static extern bool OpenProcessToken(IntPtr p, uint access, out IntPtr t);
  [DllImport("advapi32.dll")] static extern bool GetTokenInformation(IntPtr t, int cls, out int info, int len, out int ret);
  // 1 elevated, 0 not, -1 unknown (process gone or token not readable).
  public static int Elevated(int pid){
    IntPtr p=OpenProcess(0x1000,false,pid); if(p==IntPtr.Zero) return -1;
    try{ IntPtr t; if(!OpenProcessToken(p,0x0008,out t)) return -1;
      try{ int v,r; if(!GetTokenInformation(t,20,out v,4,out r)) return -1; return v!=0?1:0; } finally { CloseHandle(t); } }
    finally { CloseHandle(p); }
  }
}
"@
}
if(-not ('EstadoProc' -as [type])){
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public static class EstadoProc {
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern bool QueryFullProcessImageName(IntPtr p, int flags, StringBuilder s, ref int n);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern int GetApplicationUserModelId(IntPtr p, ref int n, StringBuilder s);
  [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
  [DllImport("shlwapi.dll", CharSet=CharSet.Unicode)] static extern uint AssocQueryString(uint flags, uint str, string assoc, string extra, StringBuilder s, ref uint n);
  // Executable path of a process (works on elevated ones too: limited query access). null when gone.
  public static string ImagePath(int pid){
    IntPtr p=OpenProcess(0x1000,false,pid); if(p==IntPtr.Zero) return null;
    try{ var s=new StringBuilder(1024); int n=s.Capacity; return QueryFullProcessImageName(p,0,s,ref n)?s.ToString():null; } finally { CloseHandle(p); }
  }
  // AppUserModelID of a packaged process ("Publisher.App_hash!App"); null for a desktop process.
  public static string Aumid(int pid){
    IntPtr p=OpenProcess(0x1000,false,pid); if(p==IntPtr.Zero) return null;
    try{ var s=new StringBuilder(512); int n=s.Capacity; return GetApplicationUserModelId(p,ref n,s)==0?s.ToString():null; } finally { CloseHandle(p); }
  }
  // Root of a window's owner chain (a dialog -> the window that owns it).
  public static IntPtr OwnerRoot(IntPtr h){ for(int i=0;i<16;i++){ IntPtr o=GetWindow(h,4); if(o==IntPtr.Zero) break; h=o; } return h; }
  // Executable that opens a file extension (".msc" -> mmc.exe); null when none.
  public static string AssocExe(string ext){ var s=new StringBuilder(1024); uint n=(uint)s.Capacity; return AssocQueryString(0,2,ext,null,s,ref n)==0?s.ToString():null; }
}
"@
}

function Get-IdentidadApp($App){
  # What proves that a process IS this Start-menu entry, from the entry itself (never from a window title):
  #   @{ tipo='aumid'; valor=<AppID> }      packaged app: the process's own AppUserModelID equals the AppID
  #   @{ tipo='exe'; valor=<path> }         desktop app: the process's executable is the shortcut's target, or lives
  #                                         under the target's folder when that folder is the app's own (not Windows)
  #   @{ tipo='asociada'; valor=<exe> }     the target is a document (a .msc console): the program that opens it
  #   @{ tipo='host'; valor='' }            a shell place (Control Panel): a window of a shell host process
  #   @{ tipo='desconocida'; valor='' }     nothing proves it: no window is taken as the app's
  if(-not $App){ return @{ tipo='desconocida'; valor='' } }
  if($App.AppID -match '^[A-Za-z0-9.]+_[a-z0-9]{13}!'){ return @{ tipo='aumid'; valor=[string]$App.AppID } }
  $t=$null
  try{ $t=(New-Object -ComObject Shell.Application).NameSpace('shell:AppsFolder').ParseName($App.AppID).ExtendedProperty('System.Link.TargetParsingPath') }catch{}
  if(-not $t){ return @{ tipo='desconocida'; valor='' } }
  if($t -like '::*' -or (Test-Path -LiteralPath $t -PathType Container)){ return @{ tipo='host'; valor='' } }
  $ext=[IO.Path]::GetExtension($t)
  if($ext -eq '.exe'){ return @{ tipo='exe'; valor=[string]$t } }
  $a=[EstadoProc]::AssocExe($ext)
  if($a){ return @{ tipo='asociada'; valor=[string]$a } }
  @{ tipo='desconocida'; valor='' }
}

if(-not ('EstadoManifiesto' -as [type])){
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public static class EstadoManifiesto {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern IntPtr LoadLibraryExW(string p, IntPtr f, uint flags);
  [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr m);
  [DllImport("kernel32.dll")] static extern IntPtr FindResourceW(IntPtr m, IntPtr name, IntPtr type);
  [DllImport("kernel32.dll")] static extern IntPtr LoadResource(IntPtr m, IntPtr r);
  [DllImport("kernel32.dll")] static extern IntPtr LockResource(IntPtr d);
  [DllImport("kernel32.dll")] static extern uint SizeofResource(IntPtr m, IntPtr r);
  [DllImport("shlwapi.dll", CharSet=CharSet.Unicode)] static extern uint AssocQueryString(uint flags, uint str, string assoc, string extra, StringBuilder s, ref uint n);
  // The executable's application manifest (resource type 24) as text; null when it has none.
  public static string Read(string exe){
    IntPtr m=LoadLibraryExW(exe,IntPtr.Zero,0x22); if(m==IntPtr.Zero) return null;
    try{ foreach(int id in new int[]{1,2,3}){ IntPtr r=FindResourceW(m,(IntPtr)id,(IntPtr)24); if(r==IntPtr.Zero) continue;
        IntPtr d=LockResource(LoadResource(m,r)); int n=(int)SizeofResource(m,r); if(d==IntPtr.Zero||n<=0) continue;
        byte[] b=new byte[n]; Marshal.Copy(d,b,0,n); return Encoding.UTF8.GetString(b); }
      return null; } finally { FreeLibrary(m); }
  }
  // The command that opens a file extension (".msc" -> "...mmc.exe "%1" %*"); null when none.
  public static string Command(string ext){ var s=new StringBuilder(2048); uint n=(uint)s.Capacity; return AssocQueryString(0x20,1,ext,"open",s,ref n)==0?s.ToString():null; }
}
"@
}

function Get-LanzamientoComoPersona($App){
  # v3 r5a M5, the same rule as the product (InvokerLaunch.cs): a desktop entry whose program asks Windows to raise it
  # unasked (manifest level highestAvailable, or autoElevate, and not requireAdministrator) is started with the
  # person's own rights: the shortcut's target and arguments, CreateProcess and __COMPAT_LAYER=RunAsInvoker.
  # @{ exe; args; dir } or $null (the shell's path, as before). Read from the manifest, never a list of programs.
  if(-not $App -or $App.AppID -match '!'){ return $null }
  $t=$null; $a=''
  try{
    $it=(New-Object -ComObject Shell.Application).NameSpace('shell:AppsFolder').ParseName($App.AppID)
    $t=$it.ExtendedProperty('System.Link.TargetParsingPath'); $a=[string]$it.ExtendedProperty('System.Link.Arguments')
  }catch{}
  if(-not $t -or -not [IO.Path]::IsPathRooted($t) -or -not (Test-Path -LiteralPath $t -PathType Leaf)){ return $null }
  $ext=[IO.Path]::GetExtension($t)
  if($ext -eq '.exe'){ $exe=$t; $argumentos=$a.Trim() }
  else{
    $cmd=[EstadoManifiesto]::Command($ext); if(-not $cmd){ return $null }
    $cmd=[Environment]::ExpandEnvironmentVariables($cmd.Trim())
    if($cmd -match '^"([^"]+)"(.*)$' -or $cmd -match '^(\S+)(.*)$'){ $exe=$matches[1]; $resto=$matches[2] }else{ return $null }
    $doc=($resto -match '%1|%L')
    $argumentos=($resto.Replace('%1',$t).Replace('%L',$t).Replace('%*',$a.Trim())).Trim()
    if(-not $doc){ $argumentos=('"{0}" {1}' -f $t,$argumentos).Trim() }
  }
  if([IO.Path]::GetExtension($exe) -ne '.exe' -or -not (Test-Path -LiteralPath $exe -PathType Leaf)){ return $null }
  $m=[EstadoManifiesto]::Read($exe)
  $nivel=''; $auto=$false
  if($m -match 'requestedExecutionLevel[^>]*?level\s*=\s*["'']([A-Za-z]+)["'']'){ $nivel=$matches[1] }
  if($m -match '<(?:\w+:)?autoElevate[^>]*>\s*([A-Za-z]+)\s*<'){ $auto=($matches[1] -eq 'true') }
  if($nivel -eq 'requireAdministrator' -or -not ($nivel -eq 'highestAvailable' -or $auto)){ return $null }
  @{ exe=$exe; args=$argumentos; dir=(Split-Path $exe) }
}

function Start-AppComoPersona($App){
  # Starts the entry with the person's own rights when its program would be raised unasked; $false keeps the shell's
  # path (shell:AppsFolder), which the caller then takes.
  $plan=Get-LanzamientoComoPersona $App
  if(-not $plan){ return $false }
  $psi=New-Object Diagnostics.ProcessStartInfo($plan.exe)
  $psi.UseShellExecute=$false; $psi.Arguments=$plan.args; $psi.WorkingDirectory=$plan.dir
  $psi.EnvironmentVariables['__COMPAT_LAYER']='RunAsInvoker'
  $p=[Diagnostics.Process]::Start($psi)
  [bool]$p
}

function Test-IdentidadVentana($W,$Ident,[string]$Nombre){
  # True only when the window's (app) process is proven to be the app (Get-IdentidadApp). Pure apart from reading the
  # process's executable path / AppUserModelID.
  switch($Ident.tipo){
    'aumid' { return ([EstadoProc]::Aumid([int]$W.app_pid) -eq $Ident.valor) }
    'host' { return ($global:AppsHosts -contains $W.app_proceso -and $W.titulo -like "*$Nombre*") }
    'exe' { return (Test-RutaDeApp ([EstadoProc]::ImagePath([int]$W.app_pid)) $Ident.valor $env:windir) }
    'asociada' { $p=[EstadoProc]::ImagePath([int]$W.app_pid); return ($p -and $p -eq $Ident.valor) }
  }
  $false
}

function Test-Elevada([int]$ProcessId){
  # True when the process runs elevated (TokenElevation): UI Automation from this non-elevated harness, and from
  # BAXY, then sees its window only as empty panes. $null when it cannot be told.
  switch([EstadoToken]::Elevated($ProcessId)){ 1 { $true } 0 { $false } default { $null } }
}

function Test-UacSilencioso(){
  # Get-DecisionUacSilencioso (decisiones_comun.ps1) on this PC's UAC policy and this user's token.
  $pol=$null; try{ $pol=Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -ErrorAction Stop }catch{}
  $admin=$false
  # In a filtered (non-elevated) token Administrators is a deny-only SID: Groups leaves it out, Claims keeps it.
  try{ $admin=@([Security.Principal.WindowsIdentity]::GetCurrent().Claims | ForEach-Object { $_.Value }) -contains 'S-1-5-32-544' }catch{}
  Get-DecisionUacSilencioso $(if($pol){ $pol.EnableLUA }else{ $null }) $(if($pol){ $pol.ConsentPromptBehaviorAdmin }else{ $null }) $admin
}

function Stop-ProcesoElevado([int]$ProcessId,[string]$Nombre){
  # An elevated process (Taskmgr, an MMC console, Resource Monitor, an admin console a case left) does not take a
  # close or a Stop-Process from this non-elevated harness (access denied; UIA sees empty panes). On a test PC where
  # UAC elevates an administrator without asking (Test-UacSilencioso), taskkill of that exact PID runs elevated,
  # hidden: first without /F (a normal close: WM_CLOSE to its windows, revision 2026-10-08), and only when it is still
  # running 5 s later with /F. Where UAC would show its prompt nothing is tried (a prompt on the screen would be one more
  # obstacle). Callers pass only processes the batch or the harness is proven to have started.
  # Returns 'salio' | 'cerrada_elevada' | 'detenida_elevada' | 'no_cierra:<why>'.
  if($global:AppsProhibidos -contains $Nombre -or $global:AppsHosts -contains $Nombre){ return 'no_cierra:prohibida' }
  $p=Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
  if(-not $p -or $p.ProcessName -ne $Nombre){ return 'salio' }
  if(-not (Test-UacSilencioso)){ return 'no_cierra:elevada_uac_pregunta' }
  $tk=Join-Path $env:windir 'System32\taskkill.exe'
  foreach($fuerza in @($false,$true)){
    $a=@('/PID',"$ProcessId")+@(if($fuerza){ '/F' })
    try{ Start-Process -FilePath $tk -ArgumentList $a -Verb RunAs -WindowStyle Hidden -Wait -ErrorAction Stop }
    catch{ return "no_cierra:elevada:$($_.Exception.Message)" }
    [void]$p.WaitForExit(5000)
    if($p.HasExited){ return $(if($fuerza){ 'detenida_elevada' }else{ 'cerrada_elevada' }) }
  }
  'no_cierra:elevada_sigue_viva'
}

function Get-TopWindows(){
  # Visible top-level windows with a title: @{ hwnd; pid; proceso; titulo; clase; app_pid; app_proceso }.
  # A UWP frame (ApplicationFrameHost) is reported with the process of the app inside it (its CoreWindow child).
  # A hung window (EstadoColgada) is skipped before its Name is read: that read waited 10 s and came back empty, so it
  # was never listed anyway (its ghost, a dwm window with the same title, still is).
  $out=@()
  foreach($w in [Windows.Automation.AutomationElement]::RootElement.FindAll('Children',[Windows.Automation.Condition]::TrueCondition)){
    try{
      $c=$w.Current; $h=[IntPtr]$c.NativeWindowHandle
      if($h -eq [IntPtr]::Zero -or -not [EstadoW32]::IsWindowVisible($h) -or [EstadoColgada]::IsHungAppWindow($h) -or [string]::IsNullOrWhiteSpace($c.Name)){ continue }
      $pn=(Get-Process -Id $c.ProcessId -ErrorAction SilentlyContinue).ProcessName
      $apid=$c.ProcessId; $apn=$pn
      if($pn -eq 'ApplicationFrameHost'){
        foreach($ch in $w.FindAll('Children',[Windows.Automation.Condition]::TrueCondition)){
          if($ch.Current.ProcessId -ne $c.ProcessId){ $apid=$ch.Current.ProcessId; $apn=(Get-Process -Id $apid -ErrorAction SilentlyContinue).ProcessName; break }
        }
      }
      $out+=[pscustomobject]@{ hwnd=[long]$h; pid=$c.ProcessId; proceso=$pn; titulo=$c.Name; clase=$c.ClassName; app_pid=$apid; app_proceso=$apn }
    }catch{}
  }
  $out
}

function Find-AppWindows([string]$Nombre,[string]$Proceso){
  # Windows of an app: by its process (given or learned) when known, otherwise by its Start-menu name in the title.
  # A process learned for several apps (one console host for many tools) also needs the name in the title.
  # An app whose Start-menu entry proves its process (Get-IdentidadApp) is found by that proof only, so a learned
  # process or a title that merely mentions the app (a browser page about it) never stands for it.
  $ws=@((Get-TopWindows) | Where-Object { $global:AppsProhibidos -notcontains $_.app_proceso })
  if(-not $Proceso){
    $s=Resolve-StartApp $Nombre
    if($s){ $id=Get-IdentidadApp $s; if($id.tipo -in @('aumid','exe','asociada')){ return @($ws | Where-Object { Test-IdentidadVentana $_ $id $s.Name }) } }
  }
  $ap=Get-AppsAprendidas
  if(-not $Proceso){ $Proceso=$ap[$Nombre] }
  if($Proceso){
    $compartido=@($ap.Values | Where-Object { $_ -eq $Proceso }).Count -gt 1
    return @($ws | Where-Object { ($_.app_proceso -eq $Proceso -or $_.proceso -eq $Proceso) -and (-not $compartido -or $_.titulo -like "*$Nombre*") })
  }
  @($ws | Where-Object { $_.titulo -like "*$Nombre*" })
}

function Get-PropiosApp([string]$Clave){
  # Harness-owned app items whose process or Start-menu name is $Clave ('*' = all of them).
  @(Get-Propios | Where-Object { $_.tipo -eq 'app' -and ($Clave -eq '*' -or $_.proceso -eq $Clave -or $_.nombre -eq $Clave) })
}

function Get-VentanasDelPid([int]$ProcessId){
  # Visible top-level windows of a process (a UWP frame counts for the app inside it). A dialog is reported as the
  # root of its owner chain, so a save prompt of a harness window counts as that harness window.
  @((Get-TopWindows) | Where-Object { [int]$_.app_pid -eq $ProcessId -or [int]$_.pid -eq $ProcessId } | ForEach-Object { [long][EstadoProc]::OwnerRoot([IntPtr][long]$_.hwnd) } | Select-Object -Unique)
}

function Get-LibroLote(){
  # The batch ledger (scripts/cu_live/libro_lote.ps1 -Foto) named by CU_LIBRO, or $null outside a batch.
  $p=$env:CU_LIBRO
  if(-not $p -or -not (Test-Path -LiteralPath $p)){ return $null }
  try{ [IO.File]::ReadAllText($p,[Text.Encoding]::UTF8) | ConvertFrom-Json }catch{ $null }
}

function Get-EpochAhora(){ [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0 }

if(-not ('EstadoRegistro' -as [type])){
Add-Type -ReferencedAssemblies System.Web.Extensions @"
using System; using System.Collections; using System.Web.Script.Serialization;
public static class EstadoRegistro {
  public class Fila { public int pid; public int padre; public string nombre; public double nacio; }
  static int FinValor(string s,int i){
    // Index of the last character of the JSON array or object that starts at i; -1 when it never closes.
    int d=0; bool str=false;
    for(;i<s.Length;i++){
      char c=s[i];
      if(str){ if(c=='\\'){ i++; } else if(c=='"'){ str=false; } continue; }
      if(c=='"'){ str=true; } else if(c=='['||c=='{'){ d++; } else if(c==']'||c=='}'){ d--; if(d==0) return i; }
    }
    return -1;
  }
  // The record with its top-level "procesos" array emptied ("procesos": []), and that array's text in lista ("" when
  // the record has none). Strings are skipped whole, so a process name with brackets or quotes never cuts it.
  public static string SinProcesos(string s,out string lista){
    lista=""; int d=0; bool str=false; int ini=-1;
    for(int i=0;i<s.Length;i++){
      char c=s[i];
      if(str){
        if(c=='\\'){ i++; continue; }
        if(c!='"') continue;
        str=false;
        if(d!=1 || ini<0 || s.Substring(ini+1,i-ini-1)!="procesos") continue;
        int j=i+1; while(j<s.Length && Char.IsWhiteSpace(s[j])) j++;
        if(j>=s.Length || s[j]!=':') continue;
        j++; while(j<s.Length && Char.IsWhiteSpace(s[j])) j++;
        if(j>=s.Length || s[j]!='[') continue;
        int f=FinValor(s,j); if(f<0) return s;
        lista=s.Substring(j,f-j+1);
        return s.Substring(0,j)+"[]"+s.Substring(f+1);
      }
      if(c=='"'){ str=true; ini=i; } else if(c=='['||c=='{'){ d++; } else if(c==']'||c=='}'){ d--; }
    }
    return s;
  }
  // pid -> ArrayList of Fila from that array; a row without pid or nacio is left out (its child then has no known parent).
  public static Hashtable Indice(string lista){
    var h=new Hashtable();
    if(String.IsNullOrEmpty(lista)) return h;
    var js=new JavaScriptSerializer(); js.MaxJsonLength=Int32.MaxValue;
    var filas=js.DeserializeObject(lista) as object[]; if(filas==null) return h;
    foreach(object o in filas){
      var x=o as IDictionary; if(x==null || x["pid"]==null || x["nacio"]==null) continue;
      var f=new Fila{ pid=Convert.ToInt32(x["pid"]), padre=x["padre"]==null?0:Convert.ToInt32(x["padre"]), nombre=x["nombre"]==null?"":Convert.ToString(x["nombre"]), nacio=Convert.ToDouble(x["nacio"]) };
      var l=h[f.pid] as ArrayList; if(l==null){ l=new ArrayList(); h[f.pid]=l; }
      l.Add(f);
    }
    return h;
  }
}
"@
}

function Read-RegistroDueno([string]$Ruta,[switch]$ConProcesos){
  # One read of the record. Its "procesos" (every process the recorder saw: ~55 000 rows, 4 MB at the end of a long
  # batch) is only for the ledger's provenance walk; parsed by ConvertFrom-Json it cost 2.8 s each of the many reads a
  # case makes (measured 2026-10-09). It is cut out before parsing and comes back empty; -ConProcesos adds it as
  # indice_procesos (Get-IndiceProcesos form: pid -> rows) for libro_lote.ps1 -Cerrar.
  $lista=''
  $r=[EstadoRegistro]::SinProcesos([IO.File]::ReadAllText($Ruta,[Text.Encoding]::UTF8),[ref]$lista) | ConvertFrom-Json
  if($r -and $ConProcesos){ $r | Add-Member -NotePropertyName indice_procesos -NotePropertyValue ([EstadoRegistro]::Indice($lista)) -Force }
  $r
}

function Get-RegistroDueno([double]$Hasta=0,[switch]$ConProcesos){
  # The owner-input record (scripts/cu_live/registro_dueno.py) named by CU_REGISTRO, or $null. With $Hasta, waits up
  # to 3 s for a write that covers that instant (the recorder writes every 0.5 s); if none comes, the stale record is
  # returned and the coverage checks fail closed on it. A record more than 10 s behind is a recorder that stopped
  # writing (pasada r9: dead from 12:07, every marcos/exploradores/libro call then waited the whole 3 s, ~9 s a case):
  # it is returned at once, the same stale record the wait would end on. Its process list: Read-RegistroDueno.
  $p=$env:CU_REGISTRO
  if(-not $p){ return $null }
  $fin=(Get-Date).AddSeconds(3); $r=$null
  do{
    if(Test-Path -LiteralPath $p){ try{ $r=Read-RegistroDueno $p -ConProcesos:$ConProcesos }catch{} }
    if($r -and ($Hasta -le 0 -or ($null -ne $r.cubierto_hasta -and [double]$r.cubierto_hasta -ge $Hasta))){ return $r }
    if($r -and $null -ne $r.cubierto_hasta -and ($Hasta - [double]$r.cubierto_hasta) -gt 10){ return $r }
    Start-Sleep -Milliseconds 200
  }while((Get-Date) -lt $fin)
  $r
}

function Test-QuietoDesde([double]$Desde){
  # The person gave no input from $Desde (epoch seconds, minus 3 s) until now, and the record covers all of it.
  $h=Get-EpochAhora
  Get-DecisionDuenoQuieto (Get-RegistroDueno $h) $Desde $h
}

if(-not ('EstadoProcesos' -as [type])){
Add-Type @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices;
public static class EstadoProcesos {
  public class Fila { public int Pid; public int Padre; public string Nombre; public long Ticks; }
  [DllImport("ntdll.dll")] static extern int NtQuerySystemInformation(int cls, IntPtr buf, int len, out int ret);
  // Every process from one kernel snapshot (SystemProcessInformation): pid, parent, image name and start. The same
  // CreateTime Win32_Process.CreationDate is made of, which keeps it only to the microsecond: Ticks is cut the same
  // way (UTC ticks, a multiple of 10; 0 when the kernel gives none), so a key matches one taken through CIM.
  // null when the snapshot cannot be read (32-bit host, call refused): the caller falls back to CIM.
  public static List<Fila> Todos(){
    if(IntPtr.Size!=8) return null;
    int len=1<<20;
    for(int intento=0;intento<6;intento++){
      IntPtr buf=Marshal.AllocHGlobal(len);
      try{
        int ret; int st=NtQuerySystemInformation(5,buf,len,out ret);
        if(st==unchecked((int)0xC0000004)){ len=Math.Max(len*2,ret+65536); continue; }
        if(st!=0) return null;
        var l=new List<Fila>(); int off=0;
        while(true){
          IntPtr e=IntPtr.Add(buf,off);
          long ct=Marshal.ReadInt64(e,32);
          int nlen=Marshal.ReadInt16(e,56)&0xFFFF; IntPtr nbuf=Marshal.ReadIntPtr(e,64);
          int pid=(int)Marshal.ReadInt64(e,80); int padre=(int)Marshal.ReadInt64(e,88);
          string nom=(nbuf==IntPtr.Zero||nlen==0)?(pid==0?"System Idle Process":""):Marshal.PtrToStringUni(nbuf,nlen/2);
          long t=0; if(ct>0){ t=DateTime.FromFileTimeUtc(ct).Ticks; t-=t%10; }
          l.Add(new Fila{ Pid=pid, Padre=padre, Nombre=nom, Ticks=t });
          int next=Marshal.ReadInt32(e,0); if(next==0) break; off+=next;
        }
        return l;
      } finally { Marshal.FreeHGlobal(buf); }
    }
    return null;
  }
}
"@
}

if(-not ('EstadoServicio' -as [type])){
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class EstadoServicio {
  [DllImport("advapi32.dll", CharSet=CharSet.Unicode)] static extern IntPtr OpenSCManagerW(string m, string db, uint access);
  [DllImport("advapi32.dll", CharSet=CharSet.Unicode)] static extern IntPtr OpenServiceW(IntPtr scm, string name, uint access);
  [DllImport("advapi32.dll")] static extern bool QueryServiceStatusEx(IntPtr s, int level, int[] buf, int size, out int need);
  [DllImport("advapi32.dll")] static extern bool CloseServiceHandle(IntPtr h);
  // Process id of a running service (SERVICE_STATUS_PROCESS.dwProcessId), 0 when stopped or unreadable.
  public static int Pid(string name){
    IntPtr m=OpenSCManagerW(null,null,1); if(m==IntPtr.Zero) return 0;
    try{ IntPtr s=OpenServiceW(m,name,4); if(s==IntPtr.Zero) return 0;
      try{ int[] b=new int[9]; int need; return QueryServiceStatusEx(s,0,b,36,out need)?b[7]:0; } finally { CloseServiceHandle(s); } }
    finally { CloseServiceHandle(m); }
  }
}
"@
}

function Get-PidServicio([string]$Nombre){
  # The service's process id (Win32_Service.ProcessId) through the service manager: the CIM query took ~2.7 s.
  $s=[EstadoServicio]::Pid($Nombre); if($s -gt 0){ $s }
}

function ConvertTo-FilaProceso([int]$ProcessId,[int]$Padre,[string]$Nombre,[long]$Ticks,[string]$Ruta){
  # The row Get-ProcesosCim gives for one process: parent, executable, start (epoch seconds) and ledger key.
  $n=0.0; if($Ticks -gt 0){ $n=([DateTimeOffset](New-Object DateTime $Ticks,([DateTimeKind]::Utc))).ToUnixTimeMilliseconds()/1000.0 }
  [pscustomobject]@{ pid=$ProcessId; padre=$Padre; nombre=[IO.Path]::GetFileNameWithoutExtension($Nombre); ruta=$Ruta; nacio=$n; clave=(Get-ClaveProceso $ProcessId $Ticks) }
}

function Get-ProcesosCim(){
  # Every process with its parent, executable, start (epoch seconds) and ledger key (Get-ClaveProceso). One kernel
  # snapshot (EstadoProcesos, ~30 ms) instead of Win32_Process (2-3 s a call with the PC loaded, measured 2026-10-09):
  # same keys, parents and names (tests/test_cu_live_arnes_rapido.py compares both on the live process list). The
  # executable comes from QueryFullProcessImageName, as WMI reads it (empty when the process cannot be opened).
  # CU_PROCESOS_CIM=1, or a snapshot that cannot be read, goes back to CIM.
  $filas=$null; if($env:CU_PROCESOS_CIM -ne '1'){ $filas=[EstadoProcesos]::Todos() }
  if($null -ne $filas){
    foreach($f in $filas){ ConvertTo-FilaProceso $f.Pid $f.Padre $f.Nombre $f.Ticks ([string][EstadoProc]::ImagePath($f.Pid)) }
    return
  }
  foreach($c in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)){
    $t=0L; $n=0.0
    if($c.CreationDate){ $u=$c.CreationDate.ToUniversalTime(); $t=$u.Ticks; $n=([DateTimeOffset]$u).ToUnixTimeMilliseconds()/1000.0 }
    [pscustomobject]@{ pid=[int]$c.ProcessId; padre=[int]$c.ParentProcessId; nombre=[IO.Path]::GetFileNameWithoutExtension([string]$c.Name)
      ruta=[string]$c.ExecutablePath; nacio=$n; clave=(Get-ClaveProceso ([int]$c.ProcessId) $t) }
  }
}

if(-not ('EstadoDwm' -as [type])){
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class EstadoDwm {
  [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h, int attr, out int v, int size);
  // DWMWA_CLOAKED=14: a window Windows hides without making it invisible (suspended packaged apps, other desktops).
  public static bool Cloaked(IntPtr h){ int v; return DwmGetWindowAttribute(h,14,out v,4)==0 && v!=0; }
}
"@
}

function Get-VentanasVisibles(){
  # Every visible top-level window, titled or not: @{ hwnd; pid; titulo }. Get-TopWindows skips the untitled ones,
  # which hid the frame PowerPoint left behind with the case's ribbon tab still selected (v3-03). Cloaked and
  # zero-size windows are left out: nobody sees them, and they made background processes look like open apps.
  $l=New-Object Collections.Generic.List[object]
  $cb=[EstadoW32+EnumProc]{ param($h,$x)
    if([EstadoW32]::IsWindowVisible($h) -and -not [EstadoDwm]::Cloaked($h)){
      $r=New-Object EstadoW32+RECT
      if([EstadoW32]::GetWindowRect($h,[ref]$r) -and ($r.Right-$r.Left) -gt 0 -and ($r.Bottom-$r.Top) -gt 0){
        $p=0; [void][EstadoW32]::GetWindowThreadProcessId($h,[ref]$p); $l.Add([pscustomobject]@{ hwnd=[long]$h; pid=[int]$p; titulo=[EstadoW32]::Title($h) })
      }
    }
    $true }
  [void][EstadoW32]::EnumWindows($cb,[IntPtr]::Zero)
  $l.ToArray()
}

function Get-NacioProceso([int]$ProcessId){
  # @{ clave; nacio } of a running process, or $null. From the kernel snapshot (Get-ProcesosCim): the filtered CIM
  # query took ~2 s a call and runs for every window and process the states, marcos and the ledger check.
  $filas=$null; if($env:CU_PROCESOS_CIM -ne '1'){ $filas=[EstadoProcesos]::Todos() }
  if($null -ne $filas){
    foreach($f in $filas){
      if($f.Pid -ne $ProcessId){ continue }
      if($f.Ticks -le 0){ return $null }
      $u=New-Object DateTime $f.Ticks,([DateTimeKind]::Utc)
      return @{ clave=(Get-ClaveProceso $ProcessId $f.Ticks); nacio=([DateTimeOffset]$u).ToUnixTimeMilliseconds()/1000.0 }
    }
    return $null
  }
  $c=@(Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue)[0]
  if(-not $c -or -not $c.CreationDate){ return $null }
  $u=$c.CreationDate.ToUniversalTime()
  @{ clave=(Get-ClaveProceso $ProcessId $u.Ticks); nacio=([DateTimeOffset]$u).ToUnixTimeMilliseconds()/1000.0 }
}

function Read-ColaJournal([string]$Ruta,[long]$MaxBytes=16MB){
  # The last $MaxBytes of BAXY's live mission journal as lines (a case writes far less), read while BAXY may still
  # write it; none when there is no journal. A journal rotated during the case loses its older records: fewer windows
  # are attributed to BAXY (Get-ProcesosDeBaxy), so fewer are closed (fail closed).
  if(-not $Ruta -or -not (Test-Path -LiteralPath $Ruta)){ return }
  $fs=$null
  try{
    $fs=New-Object IO.FileStream($Ruta,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]'ReadWrite, Delete')
    $ini=[Math]::Max(0L,$fs.Length-$MaxBytes); [void]$fs.Seek($ini,[IO.SeekOrigin]::Begin)
    $buf=New-Object byte[] ($fs.Length-$ini); $leidos=0
    while($leidos -lt $buf.Length){ $n=$fs.Read($buf,$leidos,$buf.Length-$leidos); if($n -le 0){ break }; $leidos+=$n }
    $l=@([Text.Encoding]::UTF8.GetString($buf,0,$leidos) -split "`n")
    # A cut in the middle of the file leaves the first line partial: dropped.
    if($ini -gt 0){ $l=@($l | Select-Object -Skip 1) }
    $l | Where-Object { $_.Trim() }
  }catch{ }finally{ if($fs){ $fs.Dispose() } }
}

function Test-ProcesoDelLote([int]$ProcessId,[switch]$ConProtegidos){
  # True when the batch ledger proves this running process was born in a case of the batch with positive provenance (a
  # case's libro_lote.ps1 -Cerrar classed it 'lote': procesos_lote); $false outside a batch, or for anything else.
  # -ConProtegidos also takes a terminal or the Claude app the ledger classed 'lote' but never closes itself
  # (procesos_lote_protegidos): only apps_del_caso.ps1 asks, to close such a window normally, never to stop it.
  $libro=Get-LibroLote; if(-not $libro){ return $false }
  $n=Get-NacioProceso $ProcessId; if(-not $n){ return $false }
  $lista=@($libro.procesos_lote)
  if($ConProtegidos -and $libro.PSObject.Properties['procesos_lote_protegidos']){ $lista+=@($libro.procesos_lote_protegidos) }
  $lista -contains $n.clave -and @($libro.procesos) -notcontains $n.clave -and @($libro.procesos_dueno) -notcontains $n.clave
}

function Get-VentanasLoteDelPid([int]$ProcessId){
  # hwnds of that process the batch positively owns: the ledger's ventanas_lote, plus every window it has now when the
  # person gave no input during the whole life of the process (the record covers it). Never the absence of evidence.
  $libro=Get-LibroLote
  $v=@(if($libro){ $libro.ventanas_lote | ForEach-Object { [long]$_ } })
  $n=Get-NacioProceso $ProcessId
  if($n -and (Test-QuietoDesde $n.nacio)){ $v+=@(Get-VentanasDelPid $ProcessId) }
  @($v | Select-Object -Unique)
}

function Add-VentanasLote([long[]]$Hwnds){
  # Adds windows the batch POSITIVELY owns to the batch ledger's ventanas_lote (CU_LIBRO), so the next case's states
  # retry them (sin_restos) instead of taking them for the person's (app_cerrada). Only a caller with positive
  # provenance for that exact window calls it (exploradores.ps1: BAXY's app.open opened it). Outside a batch: nothing.
  $p=$env:CU_LIBRO
  $nuevas=@(@($Hwnds) | Where-Object { $_ } | ForEach-Object { [long]$_ })
  if(-not $p -or -not (Test-Path -LiteralPath $p) -or -not $nuevas.Count){ return $false }
  try{
    $l=[IO.File]::ReadAllText($p,[Text.Encoding]::UTF8) | ConvertFrom-Json
    if(-not $l.PSObject.Properties['ventanas_lote']){ $l | Add-Member -NotePropertyName 'ventanas_lote' -NotePropertyValue @() }
    $l.ventanas_lote=@(@(@($l.ventanas_lote) | Where-Object { $_ } | ForEach-Object { [long]$_ })+$nuevas | Select-Object -Unique)
    [IO.File]::WriteAllText($p,(($l | ConvertTo-Json -Depth 4 -Compress)+"`n"),(New-Object Text.UTF8Encoding $false))
    $true
  }catch{ $false }
}

function Get-EstadoCierre($I,[bool]$Intentado){
  # The facts Get-DecisionCierre (decisiones_comun.ps1) decides on, read from the desktop now.
  $p=$null; if($I.nuevo -and [int]$I.pid -ne 0){ $p=Get-Process -Id ([int]$I.pid) -ErrorAction SilentlyContinue }
  $vivo=[bool]($p -and $p.ProcessName -eq $I.proceso)
  $lote=[bool]($vivo -and (Test-ProcesoDelLote ([int]$I.pid)))
  @{ intentado=$Intentado; ventana_viva=([long]$I.hwnd -ne 0 -and [EstadoW32]::IsWindow([IntPtr][long]$I.hwnd)); proceso_vivo=$vivo
     nuevo=[bool]$I.nuevo; host=($global:AppsHosts -contains [string]$I.proceso)
     ventanas_del_pid=@(if($vivo){ Get-VentanasDelPid ([int]$I.pid) }); propias=@(@(Get-Propios | ForEach-Object { [long]$_.hwnd })+@([long]$I.hwnd))
     del_lote=$lote; ventanas_lote=@(if($lote){ Get-VentanasLoteDelPid ([int]$I.pid) }); sin_detener=[bool]$I.sin_detener }
}

# Office apps the harness drives through COM (documento_en_blanco): a batch copy is quit through COM with its test
# documents marked saved, so it leaves no recovery pane for the next case. Harness data, never product code.
$global:AppsQuitCom=@{ 'POWERPNT'=@('PowerPoint.Application','Presentations'); 'WINWORD'=@('Word.Application','Documents'); 'EXCEL'=@('Excel.Application','Workbooks') }
# Test fixture folder of the file cases (fixtures_prueba_v3.ps1): a document saved there is the harness's.
$global:AppsRaizFixtures=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'baxy-prueba-v3'
$global:AppsDocumentosPath=Join-Path $env:LOCALAPPDATA 'BAXY\cu-estado\documentos.jsonl'

function Add-DocumentoCreado([int]$ProcessId,[string]$Proceso,[string]$Nombre){
  # A new unsaved document a state created (documento_en_blanco): the only unsaved document a batch quit may discard.
  $d=Split-Path $global:AppsDocumentosPath; if(-not (Test-Path $d)){ New-Item -ItemType Directory -Force $d | Out-Null }
  $n=Get-NacioProceso $ProcessId
  $l=([pscustomobject]@{ clave=$(if($n){ $n.clave }else{ '' }); proceso=$Proceso; nombre=$Nombre } | ConvertTo-Json -Compress)
  [IO.File]::AppendAllText($global:AppsDocumentosPath,$l+"`n",(New-Object Text.UTF8Encoding $false))
}

function Get-DocumentosCreados([int]$ProcessId){
  # Names of the documents a state created in that exact process (pid and start time).
  $n=Get-NacioProceso $ProcessId
  if(-not $n -or -not (Test-Path -LiteralPath $global:AppsDocumentosPath)){ return }
  foreach($l in [IO.File]::ReadAllLines($global:AppsDocumentosPath)){ try{ $o=$l | ConvertFrom-Json; if($o.clave -eq $n.clave){ [string]$o.nombre } }catch{} }
}

function Stop-ProcesoDelLote([int]$ProcessId,[string]$Nombre,[bool]$Quieto=$false){
  # Makes one batch process exit. An Office copy (the only one of its name) is quit through COM, and only when every
  # open document is the harness's (Get-DecisionDocumentos): a file of the person opened in that same instance is
  # never discarded, and without COM nothing is forced. Any other process only when the person gave no input during
  # its whole life ($Quieto): a normal close of its main window, then its exact PID.
  # Returns 'salio' | 'detenida' | 'no_cierra:<why>'.
  if($global:AppsProhibidos -contains $Nombre -or $global:AppsHosts -contains $Nombre){ return 'no_cierra:prohibida' }
  $p=Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
  if(-not $p -or $p.ProcessName -ne $Nombre){ return 'salio' }
  $com=$global:AppsQuitCom[$Nombre]
  if($com){
    if(@(Get-Process -Name $Nombre -ErrorAction SilentlyContinue).Count -ne 1){ return 'no_cierra:office_varias_copias' }
    # A save prompt a case left blocks COM (t-form-4, round 7): it is cancelled first, and the documents decide.
    [void]@(Close-DialogosModales $ProcessId)
    try{
      $o=[Runtime.InteropServices.Marshal]::GetActiveObject($com[0])
      $docs=@(foreach($d in @($o.($com[1]))){ @{ nombre=[string]$d.Name; ruta=$(if([string]$d.Path){ [string]$d.FullName }else{ '' }) } })
      $dec=Get-DecisionDocumentos $docs $global:AppsRaizFixtures $Quieto
      if($dec -ne 'quit'){ [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($o); return $dec }
      foreach($d in @($o.($com[1]))){ try{ $d.Saved=$(if($Nombre -eq 'POWERPNT'){-1}else{$true}) }catch{} }
      $o.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($o); $o=$null
    }catch{ return 'no_cierra:office_sin_com' }
    [void]$p.WaitForExit(8000)
    if($p.HasExited){ return 'salio' }
    # Every document was checked and marked saved: what is left is the batch's copy.
    try{ Stop-Process -Id $ProcessId -Force -ErrorAction Stop; [void]$p.WaitForExit(5000); return 'detenida' }catch{ return "no_cierra:$($_.Exception.Message)" }
  }
  if(-not $Quieto){ return 'no_cierra:dueno_no_quieto' }
  # A dialog left inside one of its windows (Paint's resize dialog) is cancelled first; the exact PID follows anyway.
  foreach($w in @(Get-VentanasDelPid $ProcessId)){ [void]@(Close-DialogosDeVentana ([long]$w) 'cancelar') }
  try{ [void]$p.CloseMainWindow() }catch{}; [void]$p.WaitForExit(3000)
  if($p.HasExited){ return 'salio' }
  try{ Stop-Process -Id $ProcessId -Force -ErrorAction Stop; [void]$p.WaitForExit(5000); 'detenida' }catch{
    # An elevated batch process (BAXY opened Taskmgr or a console elevated) refuses this harness: elevated taskkill.
    if((Test-Elevada $ProcessId) -eq $true){ Stop-ProcesoElevado $ProcessId $Nombre }else{ "no_cierra:$($_.Exception.Message)" }
  }
}

function Close-ProcesosDelLote([string]$Nombre){
  # Inside a batch, the running copies of $Nombre (process name) the batch started (Test-ProcesoDelLote) whose every
  # window the batch positively owns (Get-VentanasLoteDelPid) are made to exit. Outside a batch: nothing.
  if(-not (Get-LibroLote)){ return }
  foreach($p in @(Get-Process -Name $Nombre -ErrorAction SilentlyContinue)){
    if(-not (Test-ProcesoDelLote $p.Id)){ continue }
    $suyas=@(Get-VentanasLoteDelPid $p.Id)
    if(@(Get-VentanasDelPid $p.Id | Where-Object { $suyas -notcontains [long]$_ }).Count -gt 0){ "$($Nombre):$($p.Id):no_cierra:ventanas_ajenas"; continue }
    $n=Get-NacioProceso $p.Id
    "$($Nombre):$($p.Id):$(Stop-ProcesoDelLote $p.Id $Nombre ([bool]($n -and (Test-QuietoDesde $n.nacio))))"
  }
}

# Harness process book (libro de procesos del arnes), persistent across batches and tandas: every process a batch,
# case, state or tanda opened with POSITIVE provenance (libro_lote.ps1 classed it 'lote', or a state launched it), with
# the windows it had then. A batch ledger (CU_LIBRO) only knows its own batch: what an earlier batch or tanda could not
# close was in the next photo and became "the person's" (round 7, 2026-10-08: a Reloj, a OneNote in its File view, a
# Word with its save prompt, an OBS settings dialog sat over 23 cases). One JSON line per sighting:
#   {clave: "pid:start ticks", nombre, ventanas: [hwnd], origen, hora}
# A reused pid is another process (the key holds its start), so a stale line never names a process of the person.
$global:AppsLibroArnesPath=Join-Path $env:LOCALAPPDATA 'BAXY\cu-estado\procesos_arnes.jsonl'

function Add-ProcesoArnes([string]$Clave,[string]$Nombre,[long[]]$Ventanas,[string]$Origen){
  if(-not $Clave -or $Clave -like '*:0'){ return }
  $d=Split-Path $global:AppsLibroArnesPath; if(-not (Test-Path $d)){ New-Item -ItemType Directory -Force $d | Out-Null }
  $l=([pscustomobject][ordered]@{ clave=$Clave; nombre=$Nombre; ventanas=@($Ventanas | Where-Object { $_ } | ForEach-Object { [long]$_ }); origen=$Origen; hora=(Get-Date).ToString('s') } | ConvertTo-Json -Compress)
  [IO.File]::AppendAllText($global:AppsLibroArnesPath,$l+"`n",(New-Object Text.UTF8Encoding $false))
}

function Get-ProcesosArnes(){
  # clave -> @{ nombre; ventanas (every hwnd recorded for it) }, from the book and from the documents a state created
  # (documentos.jsonl: an Office copy the harness started through COM).
  $h=@{}
  foreach($f in @($global:AppsLibroArnesPath,$global:AppsDocumentosPath)){
    if(-not (Test-Path -LiteralPath $f)){ continue }
    foreach($l in [IO.File]::ReadAllLines($f)){
      if(-not $l.Trim()){ continue }
      try{ $o=$l | ConvertFrom-Json }catch{ continue }
      $k=[string]$o.clave; if(-not $k){ continue }
      if(-not $h.ContainsKey($k)){ $h[$k]=@{ nombre=$(if($o.nombre -and $f -eq $global:AppsLibroArnesPath){ [string]$o.nombre }else{ [string]$o.proceso }); ventanas=@() } }
      if($o.PSObject.Properties['ventanas']){ $h[$k].ventanas=@(@($h[$k].ventanas)+@($o.ventanas | ForEach-Object { [long]$_ }) | Select-Object -Unique) }
    }
  }
  $h
}

function Optimize-ProcesosArnes([string[]]$Vivas){
  # Drops the lines of processes no longer running (their key is not in $Vivas), so the book stays small.
  if(-not (Test-Path -LiteralPath $global:AppsLibroArnesPath)){ return }
  $keep=@(foreach($l in [IO.File]::ReadAllLines($global:AppsLibroArnesPath)){ if(-not $l.Trim()){ continue }; try{ $o=$l | ConvertFrom-Json; if($Vivas -contains [string]$o.clave){ $l } }catch{} })
  [IO.File]::WriteAllText($global:AppsLibroArnesPath,$(if($keep.Count){ ($keep -join "`n")+"`n" }else{ '' }),(New-Object Text.UTF8Encoding $false))
}

function Get-DialogosModales([int]$ProcessId){
  # hwnds of the modal dialogs of that process (a visible window whose owner, a window of the same process, is
  # disabled): a save prompt a case left in front of a harness document.
  $suyas=@((Get-TopWindows) | Where-Object { [int]$_.app_pid -eq $ProcessId -or [int]$_.pid -eq $ProcessId } | ForEach-Object {
    $d=[long][EstadoProc]::OwnerRoot([IntPtr][long]$_.hwnd)
    [pscustomobject]@{ hwnd=[long]$_.hwnd; dueno=$(if($d -eq [long]$_.hwnd){0}else{$d}); dueno_habilitado=[EstadoW32]::IsWindowEnabled([IntPtr]$d) } })
  @(Get-DecisionDialogos $suyas)
}

function Close-DialogosModales([int]$ProcessId){
  # Cancels (normal window close = Cancel / Escape) the modal dialogs of a harness process, so its app answers COM
  # again and the document check decides. Cancelling a save prompt never discards anything: the document stays open.
  # Only a dialog over a document of the harness (Get-DecisionDialogoOffice): the person's document opened in that
  # same instance keeps its dialog (their Save As, their own save prompt), and COM then refuses as before.
  $creados=@(Get-DocumentosCreados $ProcessId)
  $fix=@(if(Test-Path -LiteralPath $global:AppsRaizFixtures){ Get-ChildItem -LiteralPath $global:AppsRaizFixtures -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object { $_.Name; $_.BaseName } })
  $hubo=$false
  foreach($h in @(Get-DialogosModales $ProcessId)){
    $doc=([EstadoW32]::Title([EstadoProc]::OwnerRoot([IntPtr][long]$h)) -split ' - ',2)[0]
    if((Get-DecisionDialogoOffice $doc $creados $fix) -ne 'cancelar'){ "dialogo:$($h):no_tocar:documento_ajeno"; continue }
    $hubo=$true
    try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$h)); "dialogo:$($h):cancelado" }catch{ "dialogo:$($h):no_cierra" }
  }
  if($hubo){ Start-Sleep -Milliseconds 600 }
}

# Set by Close-AppPropia when the window it closed was in front: the window Windows activated in its place. A caller
# gives the foreground back only while that window is still the one in front (app_cerrada.ps1).
$global:AppsActivadaTrasCerrar=[IntPtr]::Zero

function Close-AppPropia($I){
  # Closes one harness-owned item (the decision is Get-DecisionCierre, decisiones_comun.ps1). Returns 'cerrada' |
  # 'ya_cerrada' | 'cerrada_proceso_vivo' | 'detenida' | 'no_cierra:<why>'.
  if($global:AppsProhibidos -contains $I.proceso){ return 'no_cierra:prohibida' }
  $d=Get-DecisionCierre (Get-EstadoCierre $I $false)
  # A batch process whose harness window is already gone and that holds no window of the person (the untitled
  # frame, a dialog left by the case) exits whole: it would otherwise make the next case's app 'ajena_abierta'.
  if($d -eq 'salir_sin_ventanas'){ return (Complete-SalidaDelLote $I) }
  if($d -ne 'cerrar'){ return $d }
  $h=[IntPtr][long]$I.hwnd
  $eraPrimerPlano=([EstadoW32]::GetForegroundWindow() -eq $h)
  # A dialog a case left over the harness window (pasada r9: Paint's resize dialog, drawn inside the window) is
  # cancelled first; then the close, whose own confirmation is answered (Close-WindowExact): the save prompt of the
  # harness's test document without saving, except in a window it may share with the person (sin_detener).
  [void]@(Close-DialogosDeVentana ([long]$I.hwnd) 'cancelar')
  try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle($h)) -SinGuardar:(-not $I.sin_detener) }catch{ }
  for($i=0;$i -lt 20 -and [EstadoW32]::IsWindow($h);$i++){ Start-Sleep -Milliseconds 250 }
  if($eraPrimerPlano -and -not [EstadoW32]::IsWindow($h)){ $global:AppsActivadaTrasCerrar=[EstadoW32]::GetForegroundWindow() }
  # Window gone: a process the harness started gets 10 s to exit on its own (it is never stopped then); the result
  # says whether it is still running.
  if($I.nuevo -and -not [EstadoW32]::IsWindow($h)){
    $p=Get-Process -Id ([int]$I.pid) -ErrorAction SilentlyContinue
    if($p -and $p.ProcessName -eq $I.proceso){ [void]$p.WaitForExit(10000) }
  }
  $d=Get-DecisionCierre (Get-EstadoCierre $I $true)
  if($d -eq 'salir_sin_ventanas'){ return (Complete-SalidaDelLote $I) }
  if($d -ne 'detener'){ return $d }
  # The harness window is still there after a normal close (a save prompt of a test document) and every window of
  # its process is the harness's: that exact PID is stopped.
  try{
    Stop-Process -Id ([int]$I.pid) -Force -ErrorAction Stop
    $p=Get-Process -Id ([int]$I.pid) -ErrorAction SilentlyContinue; if($p){ [void]$p.WaitForExit(5000) }
    'detenida'
  }catch{
    if((Test-Elevada ([int]$I.pid)) -eq $true){ Stop-ProcesoElevado ([int]$I.pid) ([string]$I.proceso) }else{ "no_cierra:$($_.Exception.Message)" }
  }
}

function Complete-SalidaDelLote($I){
  # Stop-ProcesoDelLote, then the process is read back (Get-DecisionVerificado): still running is never 'cerrada'.
  $n=Get-NacioProceso ([int]$I.pid)
  $r=Stop-ProcesoDelLote ([int]$I.pid) ([string]$I.proceso) ([bool]($n -and (Test-QuietoDesde $n.nacio)))
  $p=Get-Process -Id ([int]$I.pid) -ErrorAction SilentlyContinue
  if(-not (Get-DecisionVerificado $r $true ([bool]($p -and $p.ProcessName -eq $I.proceso)))){ return $(if($r -like 'no_cierra*'){ $r }else{ 'no_cierra:sigue_vivo' }) }
  "salida_del_lote:$r"
}

function Close-AjenasDelLote($Ventanas){
  # Windows that look like the person's because the harness did not record them, but whose process the batch
  # started (a dialog a case left in a harness PowerPoint, Sticky Notes inside a batch OneNote): their processes exit.
  foreach($n in @(@($Ventanas) | Where-Object { $_ -and (Test-ProcesoDelLote ([int]$_.app_pid)) } | ForEach-Object { [string]$_.app_proceso } | Select-Object -Unique)){ Close-ProcesosDelLote $n }
}

function Close-AppsPropias([string]$Clave){
  # Closes every harness-owned item for $Clave and drops the closed ones from propios.jsonl.
  # An item matches by its process, by its Start-menu name, or by the process learned for that name.
  $res=@()
  $quedan=@()
  # A short name ("OBS Studio") also matches the Start-menu entry it resolves to ("OBS Studio (64bit)").
  $claves=@($Clave)
  if($Clave -ne '*'){ $s=Resolve-StartApp $Clave; if($s -and $s.Name -ne $Clave){ $claves+=$s.Name } }
  $ap=Get-AppsAprendidas
  $aprendidos=@($claves | ForEach-Object { $ap[$_] } | Where-Object { $_ })
  foreach($i in @(Get-Propios)){
    if($i.tipo -eq 'app' -and ($Clave -eq '*' -or $claves -contains $i.proceso -or $claves -contains $i.nombre -or $aprendidos -contains $i.proceso)){
      $r=Close-AppPropia $i; $res+="$($i.proceso):$($i.pid):$r"
      if($r -like 'no_cierra*'){ $quedan+=$i }
    } else { $quedan+=$i }
  }
  Set-Propios $quedan
  $res
}

function Add-PropiosApp($Ventanas,[string]$Nombre,[int[]]$PidsAntes){
  $props=@(Get-Propios)
  foreach($v in @($Ventanas)){
    $nuevo=($PidsAntes -notcontains [int]$v.app_pid -and $global:AppsHosts -notcontains $v.app_proceso)
    $props+=[pscustomobject]@{ tipo='app'; pid=[int]$v.app_pid; hwnd=[long]$v.hwnd; desde=(Get-Date).ToString('s'); proceso=[string]$v.app_proceso; nombre=$Nombre; nuevo=[bool]$nuevo }
    # A process the harness started goes to the persistent book too: a later batch closes it if it is still there.
    if($nuevo){ $n=Get-NacioProceso ([int]$v.app_pid); if($n){ Add-ProcesoArnes $n.clave ([string]$v.app_proceso) @([long]$v.hwnd) "estado:$Nombre" } }
  }
  Set-Propios $props
}

function Wait-NewWindows([long[]]$HwndAntes,[scriptblock]$Filtro,[int]$Segundos=30){
  # New visible top-level windows (not in $HwndAntes) that pass $Filtro; waits for the first, then 1.5 s for siblings
  # (splash screens are replaced by the main window: only the ones still alive are returned).
  $fin=(Get-Date).AddSeconds($Segundos); $nuevas=@()
  while((Get-Date) -lt $fin){
    $nuevas=@((Get-TopWindows) | Where-Object { $HwndAntes -notcontains $_.hwnd } | Where-Object $Filtro)
    if($nuevas.Count -gt 0){ break }
    Start-Sleep -Milliseconds 300
  }
  if($nuevas.Count -eq 0){ return }
  Start-Sleep -Milliseconds 1500
  @((Get-TopWindows) | Where-Object { $HwndAntes -notcontains $_.hwnd } | Where-Object $Filtro)
}

function Get-AjenasDe([string]$Nombre,[string]$Proceso){
  # Windows of the app that the harness did not open (the person's): those are never touched.
  $mias=@(Get-PropiosApp $Nombre | ForEach-Object { [long]$_.hwnd }) + @(if($Proceso){ Get-PropiosApp $Proceso | ForEach-Object { [long]$_.hwnd } })
  $misPids=@(Get-Propios | Where-Object { $_.tipo -eq 'app' -and $_.nuevo } | ForEach-Object { [int]$_.pid })
  @((Find-AppWindows $Nombre $Proceso) | Where-Object { $mias -notcontains $_.hwnd -and $misPids -notcontains [int]$_.app_pid })
}
