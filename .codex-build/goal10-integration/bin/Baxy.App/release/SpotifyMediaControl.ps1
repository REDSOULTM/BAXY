param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('play','pause','next','previous','stop','toggle')]
    [string]$Action
)
$ErrorActionPreference='Stop'
$stage='started'
Add-Type -AssemblyName UIAutomationClient
$nativeSource=@'
using System;
using System.Runtime.InteropServices;
public static class BaxySpotifyControlNative
{
    const uint LeftDown=0x0002, LeftUp=0x0004;
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x,int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public static void Click(int x,int y)
    {
        if(!SetCursorPos(x,y))throw new InvalidOperationException("SetCursorPos failed.");
        mouse_event(LeftDown,0,0,0,UIntPtr.Zero);mouse_event(LeftUp,0,0,0,UIntPtr.Zero);
    }
}
'@
Add-Type -TypeDefinition $nativeSource
$effect=$false
function Fold([string]$value){
    $d=$value.Normalize([Text.NormalizationForm]::FormD)
    $b=New-Object Text.StringBuilder
    foreach($c in $d.ToCharArray()){
        if([Globalization.CharUnicodeInfo]::GetUnicodeCategory($c)-ne [Globalization.UnicodeCategory]::NonSpacingMark){
            if([char]::IsLetterOrDigit($c)){[void]$b.Append([char]::ToLowerInvariant($c))}else{[void]$b.Append(' ')}
        }
    }
    return (($b.ToString()-split '\s+'|Where-Object {$_})-join ' ')
}
function VisibleButtons($root){
    $items=@()
    $all=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
    foreach($element in $all){
        try{
            $rect=$element.Current.BoundingRectangle
            if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and -not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0){
                $items+=@([pscustomobject]@{Element=$element;Name=(Fold([string]$element.Current.Name));Rect=$rect})
            }
        }catch{}
    }
    return $items
}
function FindButton($buttons,[string[]]$names){
    return $buttons|Where-Object {$names -contains $_.Name}|Sort-Object {$_.Rect.Top} -Descending|Select-Object -First 1
}
function NearButton($buttons,[string[]]$names,$rect){
    $x=$rect.Left+$rect.Width/2;$y=$rect.Top+$rect.Height/2
    return $buttons|Where-Object {
        $cx=$_.Rect.Left+$_.Rect.Width/2;$cy=$_.Rect.Top+$_.Rect.Height/2
        ($names -contains $_.Name) -and [Math]::Abs($cx-$x)-le 80 -and [Math]::Abs($cy-$y)-le 80
    }|Select-Object -First 1
}
function Wait-BaxyPoll([DateTime]$Deadline,[int]$IntervalMilliseconds){
    $remaining=$Deadline-(Get-Date)
    if($remaining.TotalMilliseconds -le 0){return $false}
    $delay=[Math]::Max(
        1,
        [Math]::Min(
            $IntervalMilliseconds,
            [int][Math]::Ceiling($remaining.TotalMilliseconds)))
    Start-Sleep -Milliseconds $delay
    return $true
}
try {
    $targets=switch($Action){
        'pause' {@('pausar','pause')}
        'play' {@('reproducir','play')}
        'next' {@('siguiente','next')}
        'previous' {@('anterior','previous')}
        'stop' {@('detener','stop')}
        'toggle' {@('pausar','pause','reproducir','play')}
    }
    $opposites=switch($Action){
        'pause' {@('reproducir','play')}
        'play' {@('pausar','pause')}
        'stop' {@('reproducir','play')}
        'toggle' {@('pausar','pause','reproducir','play')}
        default {@()}
    }
    Start-Process 'spotify:'
    $startupDeadline=(Get-Date).AddMilliseconds(1200)
    $process=$null
    $root=$null
    $buttons=@()
    $target=$null
    do {
        try {
            $stage='process'
            $candidateProcess=Get-Process Spotify -ErrorAction SilentlyContinue|Where-Object {$_.MainWindowHandle -ne 0}|Select-Object -First 1
            if($null -ne $candidateProcess){
                $stage='inventory'
                $candidateRoot=[Windows.Automation.AutomationElement]::FromHandle($candidateProcess.MainWindowHandle)
                $candidateButtons=VisibleButtons $candidateRoot
                $candidateTarget=FindButton $candidateButtons $targets
                if($null -ne $candidateTarget){
                    $process=$candidateProcess
                    $root=$candidateRoot
                    $buttons=$candidateButtons
                    $target=$candidateTarget
                }
            }
        } catch {}
    } while($null -eq $target -and (Wait-BaxyPoll $startupDeadline 50))
    if($null -eq $target){
        # Re-run the original terminal observations so failure kinds and
        # spotify_control_not_available remain identical at the 1.2 s horizon.
        $stage='process'
        $process=Get-Process Spotify -ErrorAction Stop|Where-Object {$_.MainWindowHandle -ne 0}|Select-Object -First 1
        if($null -eq $process){throw 'spotify_window_missing'}
        $stage='inventory'
        $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
        $buttons=VisibleButtons $root
        $target=FindButton $buttons $targets
    }
    if($null -eq $target){
        [pscustomobject]@{ok=$false;effectObserved=$false;error='spotify_control_not_available';action=$Action}|ConvertTo-Json -Compress
        exit 2
    }
    $stage='foreground'
    [void][BaxySpotifyControlNative]::SetForegroundWindow($process.MainWindowHandle)
    $foregroundDeadline=(Get-Date).AddMilliseconds(200)
    $foregroundVerified=[BaxySpotifyControlNative]::GetForegroundWindow() -eq $process.MainWindowHandle
    while(-not $foregroundVerified -and (Wait-BaxyPoll $foregroundDeadline 25)){
        $foregroundVerified=[BaxySpotifyControlNative]::GetForegroundWindow() -eq $process.MainWindowHandle
    }
    if(-not $foregroundVerified){throw 'spotify_foreground_not_verified'}
    $stage='inventory'
    $process=Get-Process -Id $process.Id -ErrorAction Stop
    if(
        $process.MainWindowHandle -eq 0 -or
        [BaxySpotifyControlNative]::GetForegroundWindow() -ne $process.MainWindowHandle
    ){throw 'spotify_foreground_not_verified'}
    $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
    $buttons=VisibleButtons $root
    $target=FindButton $buttons $targets
    if($null -eq $target){
        [pscustomobject]@{ok=$false;effectObserved=$false;error='spotify_control_not_available';action=$Action}|ConvertTo-Json -Compress
        exit 2
    }
    $beforeTitle=Fold((Get-Process -Id $process.Id -ErrorAction Stop).MainWindowTitle)
    $rect=$target.Rect
    $stage='click'
    [BaxySpotifyControlNative]::Click([int]($rect.Left+$rect.Width/2),[int]($rect.Top+$rect.Height/2))
    $effect=$true
    $stage='postread'
    $deadline=(Get-Date).AddSeconds(8)
    $verified=$false
    $postreadObservationError=$null
    do {
        try {
            $stage='postread_root'
            $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
            $stage='postread_inventory'
            $afterButtons=VisibleButtons $root
            if($Action -in @('pause','play','stop','toggle')){
                $stage='postread_compare'
                $opposite=$null -ne (NearButton $afterButtons $opposites $rect)
                $original=$null -ne (NearButton $afterButtons $targets $rect)
                $verified=$opposite -and -not $original
            } else {
                $afterTitle=Fold((Get-Process -Id $process.Id -ErrorAction Stop).MainWindowTitle)
                $verified=$afterTitle -ne $beforeTitle
            }
            $postreadObservationError=$null
        } catch {
            $postreadObservationError=$_
            $verified=$false
        }
    } while(-not $verified -and (Wait-BaxyPoll $deadline 100))
    if(-not $verified -and $null -ne $postreadObservationError){
        throw $postreadObservationError
    }
    $status=switch($Action){'pause'{'paused'};'play'{'playing'};'stop'{'stopped'};'toggle'{if($targets -contains 'pause'){'paused'}else{'playing'}};default{'playing'}}
    $failure=if($verified){$null}else{'spotify_control_postread_not_verified'}
    [pscustomobject]@{ok=$verified;effectObserved=$effect;error=$failure;action=$Action;playbackStatus=$status;processId=$process.Id}|ConvertTo-Json -Compress
} catch {
    $kind=($_.Exception.GetType().Name -replace '[^A-Za-z0-9]','').ToLowerInvariant()
    [pscustomobject]@{ok=$false;effectObserved=$effect;error=('spotify_uia_control_failed_'+$stage+'_'+$kind);action=$Action}|ConvertTo-Json -Compress
    exit 2
}
