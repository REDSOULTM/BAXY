param(
    [Parameter(Mandatory=$true)][string]$TitleBase64,
    [ValidateSet('exact','query')][string]$Mode='exact'
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
$nativeSource=@'
using System;
using System.Runtime.InteropServices;
public static class BaxySpotifyNative
{
    const int InputKeyboard=1;
    const uint KeyUp=0x0002, Unicode=0x0004, LeftDown=0x0002, LeftUp=0x0004;
    const byte Control=0x11, A=0x41, Back=0x08;
    [StructLayout(LayoutKind.Sequential)] struct Input { public int Type; public InputUnion Data; }
    [StructLayout(LayoutKind.Explicit)] struct InputUnion { [FieldOffset(0)] public KeyboardInput Keyboard; [FieldOffset(0)] public MouseInput Mouse; }
    [StructLayout(LayoutKind.Sequential)] struct KeyboardInput { public ushort VirtualKey, Scan; public uint Flags, Time; public UIntPtr Extra; }
    [StructLayout(LayoutKind.Sequential)] struct MouseInput { public int X, Y; public uint Data, Flags, Time; public UIntPtr Extra; }
    [DllImport("user32.dll",SetLastError=true)] static extern uint SendInput(uint count,Input[] inputs,int size);
    [DllImport("user32.dll")] static extern void keybd_event(byte key,byte scan,uint flags,UIntPtr extra);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x,int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public static void ReplaceFocusedText(string value)
    {
        keybd_event(Control,0,0,UIntPtr.Zero);keybd_event(A,0,0,UIntPtr.Zero);
        keybd_event(A,0,KeyUp,UIntPtr.Zero);keybd_event(Control,0,KeyUp,UIntPtr.Zero);
        for(int index=0;index<256;index++){keybd_event(Back,0,0,UIntPtr.Zero);keybd_event(Back,0,KeyUp,UIntPtr.Zero);}
        foreach(char character in value)
        {
            var inputs=new Input[2];
            inputs[0].Type=InputKeyboard;inputs[0].Data.Keyboard.Scan=character;inputs[0].Data.Keyboard.Flags=Unicode;
            inputs[1].Type=InputKeyboard;inputs[1].Data.Keyboard.Scan=character;inputs[1].Data.Keyboard.Flags=Unicode|KeyUp;
            if(SendInput(2,inputs,Marshal.SizeOf(typeof(Input)))!=2)throw new InvalidOperationException("SendInput failed.");
        }
    }
    public static void Click(int x,int y)
    {
        if(!SetCursorPos(x,y))throw new InvalidOperationException("SetCursorPos failed.");
        mouse_event(LeftDown,0,0,0,UIntPtr.Zero);mouse_event(LeftUp,0,0,0,UIntPtr.Zero);
    }
}
'@
Add-Type -TypeDefinition $nativeSource
$title=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TitleBase64))
$effect=$false
$stage='started'
function Fold([string]$value){$d=$value.Normalize([Text.NormalizationForm]::FormD);$b=New-Object Text.StringBuilder;foreach($c in $d.ToCharArray()){if([Globalization.CharUnicodeInfo]::GetUnicodeCategory($c)-ne [Globalization.UnicodeCategory]::NonSpacingMark){if([char]::IsLetterOrDigit($c)){[void]$b.Append([char]::ToLowerInvariant($c))}else{[void]$b.Append(' ')}}};return (($b.ToString()-split '\s+'|Where-Object {$_})-join ' ')}
function InvokeElement([Windows.Automation.AutomationElement]$element){
    $rect=$element.Current.BoundingRectangle
    if(-not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0){
        [BaxySpotifyNative]::Click([int]($rect.Left+$rect.Width/2),[int]($rect.Top+$rect.Height/2))
        return
    }
    $pattern=$null
    if($element.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){
        ([Windows.Automation.InvokePattern]$pattern).Invoke()
        return
    }
    throw 'spotify_element_not_actionable'
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
function Read-BaxySpotifySearchValue([Windows.Automation.AutomationElement]$searchElement){
    $controls=@($searchElement)
    try {
        $editCondition=[Windows.Automation.PropertyCondition]::new(
            [Windows.Automation.AutomationElement]::ControlTypeProperty,
            [Windows.Automation.ControlType]::Edit)
        $edit=$searchElement.FindFirst(
            [Windows.Automation.TreeScope]::Descendants,
            $editCondition)
        if($null -ne $edit){$controls+=@($edit)}
    } catch {}
    foreach($control in $controls){
        try {
            $valuePattern=$null
            if($control.TryGetCurrentPattern(
                [Windows.Automation.ValuePattern]::Pattern,
                [ref]$valuePattern)){
                $value=Fold([string]([Windows.Automation.ValuePattern]$valuePattern).Current.Value)
                if($value){return $value}
            }
        } catch {}
    }
    return $null
}
try {
    Start-Process 'spotify:'
    $process=$null
    $search=$null
    # The former 500 ms blind startup pause plus 12 s discovery window are
    # retained as one 12.5 s terminal horizon. Observe immediately so a warm
    # client does not pay either pause.
    $searchDeadline=(Get-Date).AddMilliseconds(12500)
    do {
        $process=Get-Process Spotify -ErrorAction SilentlyContinue|Where-Object {$_.MainWindowHandle -ne 0}|Select-Object -First 1
        if($null -ne $process){
            try {
                $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
                $all=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
                foreach($element in $all){try{$name=Fold([string]$element.Current.Name);if($element.Current.ControlType -eq [Windows.Automation.ControlType]::ComboBox -and ($name -like '*reproducir*' -or $name -like '*play*')){$search=$element;break}}catch{}}
            } catch {}
        }
        if($null -ne $search){break}
    } while((Wait-BaxyPoll $searchDeadline 300))
    if($null -eq $process){throw 'spotify_window_missing'}
    if($null -eq $search){throw 'spotify_search_box_missing'}
    [void][BaxySpotifyNative]::SetForegroundWindow($process.MainWindowHandle)
    $foregroundDeadline=(Get-Date).AddMilliseconds(250)
    $foregroundVerified=$false
    do {
        $foregroundVerified=[BaxySpotifyNative]::GetForegroundWindow() -eq $process.MainWindowHandle
        if($foregroundVerified){break}
    } while((Wait-BaxyPoll $foregroundDeadline 25))
    if(-not $foregroundVerified){throw 'spotify_foreground_not_verified'}
    # Spotify's search combo displays a transient suggestion overlay.  UIA may
    # still expose controls from the page behind that overlay, so clicking one
    # is not a verified selection.  Navigate to the canonical desktop search
    # URI instead and only inspect controls from the resulting page.
    Start-Process ('spotify:search:'+[Uri]::EscapeDataString($title))
    $stage='searched'
    # The desktop client can take several seconds to replace the previous
    # search page after resolving a spotify:search URI. Keep the original 6 s
    # terminal horizon, but accept the first observation that satisfies the
    # same exact result/play predicates instead of sleeping blindly.
    $foldTitle=Fold($title)
    $expectedPlay=Fold('Reproducir '+$title)
    $prefix=Fold(('Est'+[char]0x00E1+'s escuchando:'))
    # MUSIC1753: a client launched seconds earlier renders its search page late;
    # the bounded wait is 12 s (the adapter budget of 55 s still covers 12.5 + 12 + 12 + 15).
    $searchPageDeadline=(Get-Date).AddSeconds(12)
    $searchPageReady=$false
    $searchSnapshotReady=$false
    $searchObservationError=$null
    do {
        try {
            $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
            $all=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
            $searchRect=$search.Current.BoundingRectangle
            $querySearchValue=Read-BaxySpotifySearchValue $search
            $querySearchValueMatches=$querySearchValue -eq $foldTitle
            $windowRect=$root.Current.BoundingRectangle
            $alreadyPlaying=$false
            $alreadyPausedControl=$false
            foreach($element in $all){try{$name=Fold([string]$element.Current.Name);if($name.StartsWith($prefix+' ') -and ($name.Substring($prefix.Length+1) -eq $foldTitle -or $name.Substring($prefix.Length+1).StartsWith($foldTitle+' de '))){$alreadyPlaying=$true};if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and $name -in @('pausar','pause')){$alreadyPausedControl=$true}}catch{}}
            $beforeNowPlaying=''
            foreach($element in $all){try{$name=Fold([string]$element.Current.Name);if($name.StartsWith($prefix+' ')){$beforeNowPlaying=$name.Substring($prefix.Length+1);break}}catch{}}
            $windowTitle=Fold((Get-Process -Id $process.Id -ErrorAction Stop).MainWindowTitle)
            $windowMatch=$windowTitle -eq $foldTitle -or $windowTitle.EndsWith(' '+$foldTitle) -or $windowTitle.StartsWith($foldTitle+' ')
            $playCandidate=$null
            $playCandidateTop=[double]::PositiveInfinity
            $playCandidateLeft=[double]::PositiveInfinity
            foreach($element in $all){try{$rect=$element.Current.BoundingRectangle;$name=Fold([string]$element.Current.Name);$matches=if($Mode -eq 'query'){$name.StartsWith('reproducir ') -or $name.StartsWith('play ')}else{$name -eq $expectedPlay -or $name.StartsWith($expectedPlay+' ')};if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and -not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and $matches -and $rect.Top -gt ($searchRect.Top+20) -and $rect.Top -lt ($searchRect.Top+600) -and $rect.Left -ge $windowRect.Left -and $rect.Right -le $windowRect.Right -and $rect.Left -lt $playCandidateLeft){$playCandidate=$element;$playCandidateTop=$rect.Top;$playCandidateLeft=$rect.Left}}catch{}}
            $candidate=$null
            $candidateTop=[double]::PositiveInfinity
            $candidateIdentity=''
            # Results span the client content width independently of the centered
            # search box.  Bound candidates to the visible window instead of an old
            # search-box-relative column, which rejected valid results on wide layouts.
            foreach($element in $all){try{$rect=$element.Current.BoundingRectangle;$name=Fold([string]$element.Current.Name);if(-not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and $name -eq $foldTitle -and $rect.Top -gt ($searchRect.Top+20) -and $rect.Top -lt ($searchRect.Top+600) -and $rect.Left -ge $windowRect.Left -and $rect.Right -le $windowRect.Right -and $rect.Top -lt $candidateTop){$candidate=$element;$candidateTop=$rect.Top}}catch{}}
            if($null -ne $candidate){
                # The leading result card labels its play button only as "Play" /
                # "Reproducir".  Bind that generic button to the exact-title card by
                # containment and prefer it over same-title covers in the song list.
                $candidateRect=$candidate.Current.BoundingRectangle
                foreach($element in $all){try{$rect=$element.Current.BoundingRectangle;$name=Fold([string]$element.Current.Name);if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Hyperlink -and $name -and $name -ne $foldTitle -and $rect.Left -ge $candidateRect.Left -and $rect.Right -le $candidateRect.Right -and $rect.Top -ge $candidateRect.Top -and $rect.Bottom -le $candidateRect.Bottom){$candidateIdentity=$name;break}}catch{}}
                $candidateAlreadyPlaying=$beforeNowPlaying.StartsWith($foldTitle+' ') -and $candidateIdentity -and $beforeNowPlaying.Contains(' de '+$candidateIdentity)
                if($Mode -eq 'exact' -and $candidateAlreadyPlaying -and $alreadyPausedControl){[pscustomobject]@{ok=$true;effectObserved=$effect;error=$null;title=$title;processId=$process.Id}|ConvertTo-Json -Compress;exit 0}
                foreach($element in $all){try{$rect=$element.Current.BoundingRectangle;$name=Fold([string]$element.Current.Name);if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and -not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and $name -in @('reproducir','play') -and $rect.Left -ge $candidateRect.Left -and $rect.Right -le $candidateRect.Right -and $rect.Top -ge $candidateRect.Top -and $rect.Bottom -le $candidateRect.Bottom){$playCandidate=$element;break}}catch{}}
            }
            $searchSnapshotReady=$null -ne $playCandidate -or $null -ne $candidate
            # A generic Play control can belong to the page behind Spotify's
            # transient search overlay. In query mode it may end the wait early
            # only when UIA proves the ComboBox/Edit contains this query.
            $searchPageReady=$searchSnapshotReady -and (
                $Mode -ne 'query' -or $querySearchValueMatches)
            $searchObservationError=$null
        } catch {
            $searchPageReady=$false
            $searchSnapshotReady=$false
            $searchObservationError=$_
        }
        if($searchPageReady){break}
    } while((Wait-BaxyPoll $searchPageDeadline 500))
    if(-not $searchPageReady -and $Mode -eq 'query' -and $searchSnapshotReady -and $null -eq $searchObservationError){
        # Reaching this point means the bounded poll exhausted the original
        # 6 s horizon. Preserve the former terminal behavior when ValuePattern
        # is absent or never converges: evaluate that final snapshot normally.
        $searchPageReady=$true
    }
    if(-not $searchPageReady -and $null -ne $searchObservationError){throw $searchObservationError}
    if($null -eq $playCandidate){
        if($null -eq $candidate){[pscustomobject]@{ok=$false;effectObserved=$effect;error='spotify_exact_result_not_found'}|ConvertTo-Json -Compress;exit 2}
        if($null -eq $playCandidate){
            $stage='candidate'
            InvokeElement $candidate
            $stage='result'
            $detailDeadline=(Get-Date).AddSeconds(12)
            $detailObservationError=$null
            do {
                try {
                    $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
                    $all=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
                    foreach($element in $all){try{
                        $rect=$element.Current.BoundingRectangle
                        $name=Fold([string]$element.Current.Name)
                        $matches=if($Mode -eq 'query'){
                            $name -in @('reproducir','play') -or $name.StartsWith('reproducir ') -or $name.StartsWith('play ')
                        }else{
                            $name -eq $expectedPlay -or $name.StartsWith($expectedPlay+' ')
                        }
                        if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and -not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and $matches -and $rect.Top -gt ($searchRect.Top+20) -and $rect.Left -ge $windowRect.Left -and $rect.Right -le $windowRect.Right){
                            $playCandidate=$element
                            break
                        }
                    }catch{}}
                    $detailObservationError=$null
                } catch {
                    $detailObservationError=$_
                }
                if($null -ne $playCandidate){break}
            } while((Wait-BaxyPoll $detailDeadline 500))
            if($null -eq $playCandidate -and $null -ne $detailObservationError){throw $detailObservationError}
        }
    }
    $pauseAlready=$false
    if($null -eq $playCandidate){foreach($element in $all){try{$rect=$element.Current.BoundingRectangle;$name=Fold([string]$element.Current.Name);if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and -not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and ($name -eq $expectedPlay -or $name.StartsWith($expectedPlay+' '))){$playCandidate=$element;break}}catch{}}}
    foreach($element in $all){try{$name=Fold([string]$element.Current.Name);if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and $name -in @('pausar','pause')){$pauseAlready=$true;break}}catch{}}
    if($null -eq $playCandidate){
        [pscustomobject]@{ok=$false;effectObserved=$effect;error='spotify_exact_play_control_not_found'}|ConvertTo-Json -Compress;exit 2
    }
    $selectedControlName=[string]$playCandidate.Current.Name
    $effect=$true
    InvokeElement $playCandidate
    $stage='play_clicked'
    $deadline=(Get-Date).AddSeconds(15)
    $verified=$false
    $playObservationError=$null
    do {
        try {
            $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
            $all=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
            $nowPlaying=$false
            $pause=$false
            $prefix=Fold(('Est'+[char]0x00E1+'s escuchando:'))
            foreach($element in $all){try{$name=Fold([string]$element.Current.Name);if($name.StartsWith($prefix+' ')){$playingIdentity=$name.Substring($prefix.Length+1);$titleMatches=$playingIdentity -eq $foldTitle -or $playingIdentity.StartsWith($foldTitle+' de ');$identityMatches=-not $candidateIdentity -or $playingIdentity.Contains(' de '+$candidateIdentity);if($titleMatches -and $identityMatches){$nowPlaying=$true}};if($element.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and $name -in @('pausar','pause')){$pause=$true}}catch{}}
            $observedNowPlaying=''
            foreach($element in $all){try{$name=Fold([string]$element.Current.Name);if($name.StartsWith($prefix+' ')){$observedNowPlaying=$name.Substring($prefix.Length+1);break}}catch{}}
            $windowTitle=Fold((Get-Process -Id $process.Id -ErrorAction Stop).MainWindowTitle)
            $windowMatch=$windowTitle -eq $foldTitle -or $windowTitle.EndsWith(' '+$foldTitle) -or $windowTitle.StartsWith($foldTitle+' ')
            $verified=if($Mode -eq 'query'){$pause -and $observedNowPlaying -ne '' -and $observedNowPlaying -ne $beforeNowPlaying}else{$nowPlaying -and $pause}
            $playObservationError=$null
        } catch {
            $verified=$false
            $playObservationError=$_
        }
        if($verified){break}
    } while((Wait-BaxyPoll $deadline 500))
    if(-not $verified -and $null -ne $playObservationError){throw $playObservationError}
    $failure=if($verified){$null}else{'spotify_'+$stage+'_not_verified'}
    $observedTitle=(Get-Process -Id $process.Id -ErrorAction Stop).MainWindowTitle
    [pscustomobject]@{ok=$verified;effectObserved=$effect;error=$failure;title=$observedTitle;selectedControl=$selectedControlName;beforeNowPlaying=$beforeNowPlaying;observedNowPlaying=$observedNowPlaying;processId=$process.Id}|ConvertTo-Json -Compress
} catch {
    [pscustomobject]@{ok=$false;effectObserved=$effect;error='spotify_uia_failed';stage=$stage;detail=$_.Exception.Message}|ConvertTo-Json -Compress
    exit 2
}
