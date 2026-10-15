# Cierra los documentos SIN RUTA (nuevos, de prueba) de Word, Excel y PowerPoint que dejo una tanda, sin guardar, y sale
# de la aplicacion si no queda ninguno. Copia mejorada de %LOCALAPPDATA%\BAXY\cu-v3\cerrar_office.ps1 (encargo EX).
#
# Por que: con un panel o dialogo modal abierto (tanda n5 t4-c06 dejo "Guardar este archivo" sobre "Libro1 - Excel")
# COM rechaza toda llamada (RPC_E_CALL_REJECTED) y el cierre no hacia nada; la tanda siguiente (n6) empezo con Excel
# atascado en ese dialogo. Ahora, antes de COM:
#   1. por cada ventana principal de Office DESHABILITADA (la tiene tomada un modal) cuyo titulo nombra un documento
#      sin ruta (nombre por defecto o "sin titulo": Libro1, Documento2, Presentacion1, Book1, Sin titulo...), se pulsa
#      por UI Automation "Cancelar"/"Cancel" de su modal; un aviso sin "Cancelar" se acepta con "Aceptar"/"OK".
#      Nunca "Guardar", "No guardar" ni nada que guarde o descarte.
#   2. luego COM, con reintentos mientras rechace la llamada: cierra sin guardar cada documento SIN ruta y sale si no
#      queda ninguno.
# Nunca mata el proceso (matar Word con un documento abierto lo deja en recuperacion: medido 2026-10-10, caso n6).
# Nunca toca un documento CON ruta (de la persona): ni su modal ni el documento; solo se informa.
# Solo arnes, nunca producto. ASCII a proposito (PowerShell 5.1 lee los .ps1 sin BOM como ANSI).
$ErrorActionPreference = 'Continue'

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
if (-not ('BaxyCerrarOffice' -as [type])) {
  Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class BaxyCerrarOffice {
  private delegate bool EnumProc(IntPtr hwnd, IntPtr unused);
  [DllImport("user32.dll")] private static extern bool EnumWindows(EnumProc callback, IntPtr unused);
  [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint process);
  [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hwnd, uint command);
  [DllImport("user32.dll")] private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowTextW(IntPtr hwnd, StringBuilder text, int max);
  // The visible top-level windows of a process that own themselves (its main windows, never its dialogs).
  public static IntPtr[] MainWindows(uint process) {
    var found = new List<IntPtr>();
    EnumWindows((hwnd, unused) => {
      uint owner;
      GetWindowThreadProcessId(hwnd, out owner);
      if (owner == process && IsWindowVisible(hwnd) && GetAncestor(hwnd, 3) == hwnd) found.Add(hwnd);
      return true;
    }, IntPtr.Zero);
    return found.ToArray();
  }
  public static string Title(IntPtr hwnd) {
    var text = new StringBuilder(512);
    GetWindowTextW(hwnd, text, text.Capacity);
    return text.ToString();
  }
  // The enabled pop-up a disabled window gives its input to (GW_ENABLEDPOPUP): its modal dialog or pane.
  public static IntPtr ModalOf(IntPtr hwnd) {
    IntPtr popup = GetWindow(hwnd, 6);
    return popup == hwnd ? IntPtr.Zero : popup;
  }
}
'@
}

# A document with no path yet: the name an editor gives a new one, or an untitled one (first segment of the title).
$SinRuta = '^(?:libro|book|documento|document|presentaci.n|presentation|sin t.tulo|untitled)\s*\d{0,3}$'
$Cancelar = @('cancelar', 'cancel')
$Aceptar = @('aceptar', 'ok')
$Office = @{ 'WINWORD' = 'Word'; 'EXCEL' = 'Excel'; 'POWERPNT' = 'PowerPoint' }

function Get-DocumentoDelTitulo([string]$Titulo) {
  # "Libro1 - Excel" -> "libro1"; format characters (Office writes U+202A/U+202C around the name) out.
  $limpio = -join ($Titulo.ToCharArray() | Where-Object { [Globalization.CharUnicodeInfo]::GetUnicodeCategory($_) -ne 'Format' })
  (($limpio -split '\s+[-|]\s+')[0]).Trim().ToLowerInvariant()
}

function Invoke-BotonDelModal([IntPtr]$Modal) {
  # Presses Cancel on the modal; a notice with no Cancel is accepted with OK. Returns the name pressed, or ''.
  try { $raiz = [Windows.Automation.AutomationElement]::FromHandle($Modal) } catch { return '' }
  if ($null -eq $raiz) { return '' }
  $boton = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty, [Windows.Automation.ControlType]::Button)
  $botones = @($raiz.FindAll([Windows.Automation.TreeScope]::Descendants, $boton))
  foreach ($nombres in @($Cancelar, $Aceptar)) {
    if ($nombres -eq $Aceptar -and @($botones | Where-Object { $Cancelar -contains ([string]$_.Current.Name).Trim().ToLowerInvariant() }).Count -gt 0) { continue }
    foreach ($b in $botones) {
      $nombre = ([string]$b.Current.Name).Trim()
      if ($nombres -notcontains $nombre.ToLowerInvariant() -or -not $b.Current.IsEnabled) { continue }
      try {
        ([Windows.Automation.InvokePattern]$b.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)).Invoke()
        return $nombre
      } catch { }
    }
  }
  ''
}

function Close-ModalesSinRuta([string]$Proceso) {
  foreach ($p in @(Get-Process -Name $Proceso -ErrorAction SilentlyContinue)) {
    foreach ($w in [BaxyCerrarOffice]::MainWindows([uint32]$p.Id)) {
      $titulo = [BaxyCerrarOffice]::Title($w)
      $documento = Get-DocumentoDelTitulo $titulo
      for ($vuelta = 0; $vuelta -lt 4 -and -not [BaxyCerrarOffice]::IsWindowEnabled($w); $vuelta++) {
        $modal = [BaxyCerrarOffice]::ModalOf($w)
        if ($modal -eq [IntPtr]::Zero) { break }
        if ($documento -notmatch $SinRuta) { '{0}: modal sobre "{1}" (con ruta o desconocido): no se toca' -f $Office[$Proceso], $titulo; break }
        $pulsado = Invoke-BotonDelModal $modal
        if (-not $pulsado) { '{0}: modal sobre "{1}" sin Cancelar ni Aceptar: queda' -f $Office[$Proceso], $titulo; break }
        '{0}: "{1}" pulsado en el modal de "{2}"' -f $Office[$Proceso], $pulsado, $titulo
        Start-Sleep -Milliseconds 400
      }
    }
  }
}

function Invoke-Com([scriptblock]$Llamada) {
  # COM rejects calls while Office is busy (RPC_E_CALL_REJECTED 0x80010001, RPC_E_SERVERCALL_RETRYLATER 0x8001010A):
  # retried, bounded.
  for ($intento = 0; ; $intento++) {
    try { return & $Llamada } catch {
      $e = $_.Exception; while ($null -ne $e.InnerException) { $e = $e.InnerException }
      $codigo = $e.HResult
      if ($intento -ge 10 -or ($codigo -ne -2147418111 -and $codigo -ne -2147417846)) { throw }
      Start-Sleep -Milliseconds 500
    }
  }
}

foreach ($proceso in 'WINWORD', 'EXCEL', 'POWERPNT') {
  $app = $Office[$proceso]
  if (@(Get-Process -Name $proceso -ErrorAction SilentlyContinue).Count -eq 0) { continue }
  Close-ModalesSinRuta $proceso
  try {
    $o = Invoke-Com { [Runtime.InteropServices.Marshal]::GetActiveObject("$app.Application") }
    $col = Invoke-Com { if ($app -eq 'Word') { $o.Documents } elseif ($app -eq 'Excel') { $o.Workbooks } else { $o.Presentations } }
    foreach ($d in @($col)) {
      $ruta = Invoke-Com { [string]$d.Path }
      $nombre = Invoke-Com { [string]$d.Name }
      if ($ruta) { "{0}: se queda (de la persona): {1}\{2}" -f $app, $ruta, $nombre; continue }
      Invoke-Com { if ($app -eq 'Word') { $d.Close(0) } elseif ($app -eq 'Excel') { $d.Close($false) } else { $d.Saved = -1; $d.Close() } } | Out-Null
      "{0}: cerrado sin guardar {1}" -f $app, $nombre
    }
    $n = Invoke-Com { if ($app -eq 'Word') { $o.Documents.Count } elseif ($app -eq 'Excel') { $o.Workbooks.Count } else { $o.Presentations.Count } }
    if ($n -eq 0) { Invoke-Com { if ($app -eq 'Word') { $o.Quit(0) } else { $o.Quit() } } | Out-Null; "{0}: salio" -f $app }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($o)
  } catch { "{0}: COM no respondio: {1}" -f $app, $_.Exception.Message }
}
