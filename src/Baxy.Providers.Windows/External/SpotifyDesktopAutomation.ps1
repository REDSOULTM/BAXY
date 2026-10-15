param(
    [Parameter(Mandatory=$true)][string]$TitleBase64,
    [ValidateSet('exact','query')][string]$Mode='exact',
    # Query mode: the function words, medium words and purpose markers (data query_function_words.v1.json, embedded in
    # the provider and passed by SpotifyDesktopAdapter) the query is compared with.
    [string]$QueryWordsBase64='',
    # SP2 (tandas n3 del notebook: three searches killed at the adapter's 65 s with nothing said, «spotify_uia_adapter_failed»):
    # the adapter's budget for this run less its margin, in ms (0: none). Every wait ends by it, nothing is searched or
    # pressed after it, and a run it stops says its stage and the time of each stage instead of dying unheard.
    [int]$DeadlineMs=0
)
$ErrorActionPreference='Stop'
# MUSIC1769: the adapter decodes stdout as UTF-8; PowerShell 5.1 otherwise writes the console code page and
# non-ASCII titles arrive as U+FFFD.
[Console]::OutputEncoding=[Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient
$nativeSource=@'
using System;
using System.Runtime.InteropServices;
public static class BaxySpotifyNative
{
    const uint LeftDown=0x0002, LeftUp=0x0004;
    // BAXY's input mark (BaxyInputMark.cs): the pause detector and the live harness tell BAXY's input by it.
    static readonly UIntPtr Mark=new UIntPtr(0x42415859u);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x,int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr handle);
    public static void Click(int x,int y)
    {
        if(!SetCursorPos(x,y))throw new InvalidOperationException("SetCursorPos failed.");
        mouse_event(LeftDown,0,0,0,Mark);mouse_event(LeftUp,0,0,0,Mark);
    }
    [StructLayout(LayoutKind.Sequential)] public struct Box { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr handle,out Box box);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr handle,uint command);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr handle);
    [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr handle,int index);
    [DllImport("user32.dll")] static extern bool GetLayeredWindowAttributes(IntPtr handle,out uint key,out byte alpha,out uint flags);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr handle,out uint process);
    [DllImport("user32.dll")] static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr handle,int attribute,out int value,int size);
    [DllImport("dwmapi.dll",EntryPoint="DwmGetWindowAttribute")] static extern int DwmGetWindowFrame(IntPtr handle,int attribute,out Box value,int size);
    [DllImport("user32.dll")] static extern int GetSystemMetrics(int index);
    // What a window draws: its frame without the invisible resize borders (a maximized window's rectangle reaches 8 px
    // past the screen, redpc), cut to the screens.
    static bool Frame(IntPtr handle,out Box box)
    {
        if(DwmGetWindowFrame(handle,9,out box,16)!=0&&!GetWindowRect(handle,out box))return false;
        int left=GetSystemMetrics(76), top=GetSystemMetrics(77);
        box=new Box{Left=Math.Max(box.Left,left),Top=Math.Max(box.Top,top),Right=Math.Min(box.Right,left+GetSystemMetrics(78)),Bottom=Math.Min(box.Bottom,top+GetSystemMetrics(79))};
        return box.Right>box.Left&&box.Bottom>box.Top;
    }
    // TZ-SP (tandas z1/z2 del notebook; redpc): the client draws its page only while some part of its window shows. A
    // window above it that covers all of it is told apart from one the search did not reach. Pure over rectangles.
    public static bool Covers(Box window,Box[] above)
    {
        var rest=new System.Collections.Generic.List<Box>{window};
        foreach(Box cover in above)
        {
            var next=new System.Collections.Generic.List<Box>();
            foreach(Box part in rest)
            {
                if(cover.Right<=part.Left||cover.Left>=part.Right||cover.Bottom<=part.Top||cover.Top>=part.Bottom){next.Add(part);continue;}
                if(cover.Top>part.Top)next.Add(new Box{Left=part.Left,Top=part.Top,Right=part.Right,Bottom=cover.Top});
                if(cover.Bottom<part.Bottom)next.Add(new Box{Left=part.Left,Top=cover.Bottom,Right=part.Right,Bottom=part.Bottom});
                int top=Math.Max(part.Top,cover.Top), bottom=Math.Min(part.Bottom,cover.Bottom);
                if(cover.Left>part.Left)next.Add(new Box{Left=part.Left,Top=top,Right=cover.Left,Bottom=bottom});
                if(cover.Right<part.Right)next.Add(new Box{Left=cover.Right,Top=top,Right=part.Right,Bottom=bottom});
            }
            rest=next;
            if(rest.Count==0)return true;
        }
        return false;
    }
    // The processes of the shown, opaque windows above the window that together cover all of it, or "" when some part
    // of it shows. Read in physical pixels; a layered window that is not fully opaque never covers.
    public static string CoveredBy(IntPtr handle)
    {
        IntPtr previous=SetThreadDpiAwarenessContext(new IntPtr(-4));
        try
        {
            Box window;
            if(!Frame(handle,out window))return "";
            var above=new System.Collections.Generic.List<Box>();
            var names=new System.Collections.Generic.List<string>();
            uint own;GetWindowThreadProcessId(handle,out own);
            for(IntPtr other=GetWindow(handle,3);other!=IntPtr.Zero;other=GetWindow(other,3))
            {
                int cloaked;Box box;uint process;
                if(!IsWindowVisible(other)||IsIconic(other)||!Frame(other,out box))continue;
                if(box.Right<=window.Left||box.Left>=window.Right||box.Bottom<=window.Top||box.Top>=window.Bottom)continue;
                if(GetWindowThreadProcessId(other,out process)==0||process==own)continue;
                if(DwmGetWindowAttribute(other,14,out cloaked,4)==0&&cloaked!=0)continue;
                if((GetWindowLong(other,-20)&0x80000)!=0){uint key,flags;byte alpha;if(!GetLayeredWindowAttributes(other,out key,out alpha,out flags)||(flags&1)!=0||((flags&2)!=0&&alpha<255))continue;}
                above.Add(box);
                string name="";try{name=System.Diagnostics.Process.GetProcessById((int)process).ProcessName;}catch{}
                if(name!=""&&!names.Contains(name))names.Add(name);
            }
            return Covers(window,above.ToArray())?(names.Count>0?string.Join("+",names):"?"):"";
        }
        finally{if(previous!=IntPtr.Zero)SetThreadDpiAwarenessContext(previous);}
    }
}
'@
Add-Type -TypeDefinition $nativeSource
$title=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TitleBase64))
$effect=$false
$stage='started'
$startedAt=Get-Date
$hardEnd=if($DeadlineMs -gt 0){$startedAt.AddMilliseconds($DeadlineMs)}else{[DateTime]::MaxValue}
$timings=''
function Add-BaxySpotifyMark([string]$Label=$script:stage){$script:timings+=('{0}={1};' -f $Label,[int]((Get-Date)-$startedAt).TotalMilliseconds)}
function InvokeElement([Windows.Automation.AutomationElement]$element){
    # SP (redpc, cold client, «lo-fi para estudiar»: two clicks at the centre of «Reproducir Lo-Fi Focus…» left no
    # trace in 15 s, twice; the control's InvokePattern played it at once, 4 of 4 with cold and warm clients): the
    # control's own action first, which also leaves the person's pointer where it was, and a click at its centre only
    # for a control that has none. SP2: never a press after the deadline.
    if((Get-Date) -ge $hardEnd){throw 'spotify_deadline_reached'}
    $pattern=$null
    if($element.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){
        ([Windows.Automation.InvokePattern]$pattern).Invoke()
        return
    }
    $rect=$element.Current.BoundingRectangle
    if(-not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0){
        [BaxySpotifyNative]::Click([int]($rect.Left+$rect.Width/2),[int]($rect.Top+$rect.Height/2))
        return
    }
    throw 'spotify_element_not_actionable'
}
function Wait-BaxyPoll([DateTime]$Deadline,[int]$IntervalMilliseconds){
    if($hardEnd -lt $Deadline){$Deadline=$hardEnd}
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
function Confirm-BaxySpotifyForeground([IntPtr]$Handle){
    # A press is a physical click at the control's screen coordinates: it must
    # land on Spotify, never on whatever window came to the front meanwhile.
    if([BaxySpotifyNative]::GetForegroundWindow() -eq $Handle){return $true}
    [void][BaxySpotifyNative]::SetForegroundWindow($Handle)
    $foregroundDeadline=(Get-Date).AddMilliseconds(250)
    do {
        if([BaxySpotifyNative]::GetForegroundWindow() -eq $Handle){return $true}
    } while((Wait-BaxyPoll $foregroundDeadline 25))
    return $false
}
# BEGIN playback-evidence (pure; exercised with plain data by
# tests/test_spotify_desktop_automation_latency.py)
function Fold([string]$value){
    # Lower case, accents dropped, every run of what is not a letter or a digit one space («Lo-Fi» is «lo fi»). Two
    # regular expressions over the string: the former loop of PowerShell over each character, run for every element
    # of every poll, was most of the time of a poll (revisión 2 de la ronda 24).
    if(-not $value){return ''}
    $bare=[regex]::Replace($value.Normalize([Text.NormalizationForm]::FormD),'\p{Mn}','')
    return ([regex]::Replace($bare,'[^\p{L}\p{Nd}]+',' ')).Trim().ToLowerInvariant()
}
function Get-BaxySpotifyPauseName([string]$PlayName){
    # Spotify relabels a play control while its context plays: «reproducir X»
    # becomes «pausar X» (and «play X» «pause X»).
    foreach($pair in @(@('reproducir','pausar'),@('play','pause'))){
        if($PlayName -eq $pair[0]){return $pair[1]}
        if($PlayName.StartsWith($pair[0]+' ')){return $pair[1]+$PlayName.Substring($pair[0].Length)}
    }
    return ''
}
function Test-BaxySpotifyNear($Rect,$Anchor){
    return [Math]::Abs(($Rect.Left+$Rect.Width/2)-($Anchor.Left+$Anchor.Width/2)) -le 48 -and [Math]::Abs(($Rect.Top+$Rect.Height/2)-($Anchor.Top+$Anchor.Height/2)) -le 48
}
function Test-BaxySpotifyPlaybackVerified([string]$Mode,[bool]$Pause,[bool]$IdentityMatches,[string]$Observed,[string]$Before,[bool]$PauseBefore,[bool]$SelectedFlipped){
    if($Mode -ne 'query'){return $IdentityMatches -and $Pause}
    if(-not $Pause -or $Observed -eq ''){return $false}
    # Heldout t17 (v3i/v3j): a client restored paused on the very track the
    # chosen result starts with. «Now playing changed» alone can never hold
    # there, so two other observations also prove this press started playback:
    # the pressed control now reads as its pause label, or the client showed a
    # loaded track with no Pause control before the press and shows Pause now.
    return $Observed -ne $Before -or $SelectedFlipped -or ($Before -ne '' -and -not $PauseBefore)
}
function Get-BaxySpotifyPressedResult([string]$PressedName,[string]$Card){
    # The search result the press chose, folded: the name after the play word of a named control («reproducir
    # reggaeton mix» -> «reggaeton mix»), and the result card a bare «reproducir» stands in (its name and its link).
    $name=''
    foreach($word in @('reproducir','play')){
        if($PressedName.StartsWith($word+' ')){$name=$PressedName.Substring($word.Length+1);break}
    }
    return (@($name,$Card)|Where-Object {$_})-join ' '
}
function Test-BaxySpotifyPlayingRelatesTo([string]$Pressed,[string[]]$Seen){
    # Whether what plays (the now-playing line or the window title, folded) shares a word with the result that was
    # pressed: a word of four letters or more of the result as a word of what plays or the start of one
    # («prisionero» in «prisioneros»); a result with no such word, all of its words («ac dc», «u2»). Nothing pressed
    # or nothing seen relates to nothing.
    $resultWords=@(($Pressed -split ' ')|Where-Object {$_})
    $seenWords=@(foreach($line in @($Seen|Where-Object {$_})){($line -split ' ')|Where-Object {$_}})
    if($resultWords.Count -eq 0 -or $seenWords.Count -eq 0){return $false}
    $long=@($resultWords|Where-Object {$_.Length -ge 4})
    if($long.Count -gt 0){
        foreach($term in $long){foreach($word in $seenWords){if($word.StartsWith($term)){return $true}}}
        return $false
    }
    foreach($term in $resultWords){if($term -notin $seenWords){return $false}}
    return $true
}
function Get-BaxySpotifyQueryEvidence([bool]$Pause,[string]$Observed,[string]$Before,[bool]$PauseBefore,[bool]$SelectedFlipped,[string]$Pressed,[string[]]$Seen){
    # Ronda 19 (t2-c01 T1 «pone los bunkers en spotify pa estudiar»: the client had a lo-fi track loaded in pause, the
    # press only resumed it and that was told as the search played). What a query-mode press proves:
    # «none»: nothing plays by this press yet.
    # «started»: something new plays (now playing moved, or the pressed control reads as its pause label), or what
    # resumed is related to the pressed result (heldout t17: a client restored paused on the very track the chosen
    # result starts with).
    # «resumed»: the only evidence is that the track the client already had loaded plays again, and nothing ties it
    # to the pressed result: it cannot be told apart from a press that missed the result, so it is not confirmed.
    if(-not (Test-BaxySpotifyPlaybackVerified 'query' $Pause $false $Observed $Before $PauseBefore $SelectedFlipped)){return 'none'}
    if($Observed -ne $Before -or $SelectedFlipped){return 'started'}
    if(Test-BaxySpotifyPlayingRelatesTo $Pressed $Seen){return 'started'}
    return 'resumed'
}
function Test-BaxySpotifyRepress([int]$Presses,[double]$SincePressMilliseconds,[bool]$Pause,[bool]$PauseBefore,[string]$Observed,[string]$Before,[bool]$SelectedFlipped,[bool]$ControlStillPlayable){
    # One bounded re-press, only when the first press left no trace at all: the
    # same control still offers play at the same place, the pause state and the
    # now-playing identity are exactly as before the press.
    return $Presses -eq 1 -and $SincePressMilliseconds -ge 5000 -and $ControlStillPlayable -and -not $SelectedFlipped -and $Pause -eq $PauseBefore -and $Observed -eq $Before
}
function Test-BaxySpotifyPressIgnored([int]$Presses,[double]$SinceRepressMilliseconds,[bool]$Pause,[bool]$PauseBefore,[string]$Observed,[string]$Before,[bool]$SelectedFlipped){
    # Tanda t4-r6 «cumbia mientras»: 15 s of postread for a press the client
    # never took. Once the bounded re-press is spent and four more seconds show
    # no trace at all (the pause state, the now-playing identity and the pressed
    # control exactly as before the first press), the wait ends as unverified
    # instead of running out the horizon. Any trace keeps the full horizon.
    return $Presses -ge 2 -and $SinceRepressMilliseconds -ge 4000 -and -not $SelectedFlipped -and $Pause -eq $PauseBefore -and $Observed -eq $Before
}
# M169 (v5a-devG/devI «salsa», «Soda Stereo», «reggaetón», «música para cocinar»:
# 19 of 43 searches ended in spotify_exact_result_not_found after the whole 12 s
# with not one playable control on the page). A client whose accessibility tree
# is still being built exposes the top bar (the search combo) seconds before the
# page under it: the cold traces read 25-340 elements and no «Reproducir…» for
# 4-6 s, then about 1 000.
function Test-BaxySpotifyContentExposed([bool]$ColdStart,[bool]$PlayableSeen){
    # Discovery may end on the combo alone only for a client that was already
    # up; a client this request launched also waits (inside the same discovery
    # horizon) for its page to expose a playable control before searching.
    return -not $ColdStart -or $PlayableSeen
}
function Get-BaxySpotifySearchPageSeconds([bool]$SnapshotReady){
    # A page that already shows a result or a play control keeps the 12 s
    # horizon; one that shows nothing playable at all is still being built (or
    # its search did not land) and gets 20 s.
    if($SnapshotReady){return 12}
    return 20
}
function Test-BaxySpotifyResearch([int]$Searches,[double]$SinceSearchMilliseconds,[bool]$SnapshotReady){
    # One bounded re-issue of the same search URI, only when eight seconds after
    # the first one the page still shows nothing to play. Nothing was pressed
    # yet, so re-navigating can never repeat an effect.
    return $Searches -eq 1 -and $SinceSearchMilliseconds -ge 8000 -and -not $SnapshotReady
}
function Test-BaxySpotifyTermIn([string]$Term,[string[]]$Words){
    # A folded word of the query found among folded words: the same word, whatever its length («rap», «fi»); for a
    # term and a word of four letters or more, one the start of the other («prisionero» in «prisioneros»); or two
    # adjacent words written together («lofi» against «lo fi»).
    if(-not $Term){return $false}
    for($i=0;$i -lt $Words.Count;$i++){
        $word=$Words[$i]
        if($word -eq $Term){return $true}
        if($Term.Length -ge 4 -and $word.Length -ge 4 -and ($word.StartsWith($Term) -or $Term.StartsWith($word))){return $true}
        if($i+1 -lt $Words.Count -and ($word+$Words[$i+1]) -eq $Term){return $true}
    }
    return $false
}
function Get-BaxySpotifyQueryCoverage([string]$Query,[string]$Text,[string[]]$FunctionWords,[string[]]$PurposeMarkers){
    # Ronda 24, revisión 2 («rap para entrenar» answered by «Rock para entrenar», «lo fi para estudiar» by «Piano
    # para estudiar»): which content words of the query (folded) a text names. The function words (data:
    # query_function_words.v1.json, passed as -QueryWordsBase64) never count, whatever their length; every other word
    # counts, whatever its length («rap», «pop», «fi»). Two adjacent words of the query written together in the text
    # are one unit («lo fi» in «lofi»), checked before the function words are set aside. The words after a purpose
    # marker («para estudiar», «pa entrenar») are the modifier; the ones before it the core, what was asked for. A
    # query with no core has its modifier as core («musica para estudiar»: «musica» names only the medium).
    $q=@(($Query -split ' ')|Where-Object {$_})
    $t=@(($Text -split ' ')|Where-Object {$_})
    $cut=$q.Count
    for($i=1;$i -lt $q.Count;$i++){if($q[$i] -in $PurposeMarkers){$cut=$i;break}}
    $units=New-Object 'System.Collections.Generic.List[object]'
    $i=0
    while($i -lt $q.Count){
        if($i+1 -lt $q.Count -and $i+1 -ne $cut -and (Test-BaxySpotifyTermIn ($q[$i]+$q[$i+1]) $t)){
            $units.Add([pscustomobject]@{Core=$i -lt $cut;Found=$true})
            $i+=2
            continue
        }
        $word=$q[$i]
        if($word -notin $FunctionWords -and $word -notin $PurposeMarkers){$units.Add([pscustomobject]@{Core=$i -lt $cut;Found=(Test-BaxySpotifyTermIn $word $t)})}
        $i++
    }
    $core=@($units|Where-Object {$_.Core})
    $modifier=@($units|Where-Object {-not $_.Core})
    if($core.Count -eq 0){$core=$modifier;$modifier=@()}
    return [pscustomobject]@{Core=@($core|Where-Object {$_.Found}).Count;CoreTotal=$core.Count;Modifier=@($modifier|Where-Object {$_.Found}).Count}
}
function Get-BaxySpotifyQueryOverlap([string]$Query,[string]$Result,[string[]]$FunctionWords,[string[]]$PurposeMarkers){
    # Ronda 23 (t2-c01 «pone los bunkers en spotify pa estudiar»: the first «Reproducir ...» control by position was
    # pressed, unrelated to the query, and «Fother Muckers» played). The rank of a result name for the query: the
    # core it names first, the modifier only between equal cores (Get-BaxySpotifyQueryCoverage). Zero when it names
    # nothing; position decides between equal ranks.
    $coverage=Get-BaxySpotifyQueryCoverage $Query $Result $FunctionWords $PurposeMarkers
    return 100*$coverage.Core+$coverage.Modifier
}
function Test-BaxySpotifyCoversQuery([string]$Query,[string]$Text,[string[]]$FunctionWords,[string[]]$PurposeMarkers){
    # A text names the whole core of the query («rap chileno» for «rap para entrenar»; never «rock para entrenar»).
    $coverage=Get-BaxySpotifyQueryCoverage $Query $Text $FunctionWords $PurposeMarkers
    return $coverage.CoreTotal -gt 0 -and $coverage.Core -eq $coverage.CoreTotal
}
function Test-BaxySpotifyMatchesQuery([string]$Query,[string]$Pressed,[bool]$SelectedFlipped,[string[]]$Seen,[string[]]$FunctionWords,[string[]]$PurposeMarkers){
    # The fact the receipt carries as matchesQuery: what plays names the core of the query (the now-playing line or
    # the window title, each on its own), or the pressed result names it and its own control now reads as its pause
    # label (that very result plays: a «lofi beats» playlist whose track is «snowman»). A result that shares only the
    # modifier or the function words («rock para entrenar» for «rap para entrenar») says false: something plays, not
    # shown to be what was asked for.
    foreach($line in @($Seen|Where-Object {$_})){if(Test-BaxySpotifyCoversQuery $Query $line $FunctionWords $PurposeMarkers){return $true}}
    return $SelectedFlipped -and (Test-BaxySpotifyCoversQuery $Query $Pressed $FunctionWords $PurposeMarkers)
}
function Get-BaxySpotifyRowKey($Row){
    # X3 (tandas n1/n2 del notebook, t1-c07, t2-c01, t4-c01: 7 of 8 searches «spotify_exact_result_not_found» after
    # the whole 20 s and a re-issued search; the only success, by its timing, read no page before: its box held the query,
    # so nothing was set aside): Spotify keeps an element across searches and changes it (redpc pr8/pr9: the filter
    # chips keep their runtime ids on the next search, in another order), so a runtime id alone set aside the
    # results of this search drawn on reused elements. What an element of the page before is: the same element
    # still showing the same name.
    return [string]$Row.Id+'|'+[string]$Row.Fold
}
function Get-BaxySpotifyPageBefore([string]$ValueBefore,[string]$Query,[string[]]$Keys){
    # SP (tandas fin1/fin2, t1-c07 «pon lo-fi para estudiar en spotify plis», t2-c01 «pone los bunkers en spotify pa
    # estudiar», cold client): the search box holds the query about 1.3 s after the search URI while the page under it
    # is still the one shown before (Home, «reproducir descubrimiento semanal»); the search page replaces it 2-4 s
    # later. fin2 pressed a control of that page as it was torn down (spotify_element_not_actionable, «no pude
    # confirmar si se hizo»); fin1 looked a moment later and played the result. The elements of the page shown before
    # the search, as they showed then (Get-BaxySpotifyRowKey), are never a result of it, unless that page already was
    # this search: its box already held the query.
    $set=New-Object 'System.Collections.Generic.HashSet[string]'
    if($ValueBefore -ne $Query){foreach($key in $Keys){if($key -and -not $key.StartsWith('|')){[void]$set.Add($key)}}}
    return ,$set
}
function Select-BaxySpotifySearchResult($Rows,$PageBefore,[string]$Mode,[string]$Title,[string]$ExpectedPlay,$SearchRect,$WindowRect,[string[]]$FunctionWords,[string[]]$PurposeMarkers){
    # What one snapshot of the search page offers (rows of Get-BaxySpotifySnapshot, names folded): the play control,
    # the card titled as the query with its identity link, and whether the search answered. Rows of the page shown
    # before the search (Get-BaxySpotifyPageBefore) are never a result.
    $results=@(foreach($row in $Rows){if(-not $PageBefore.Contains((Get-BaxySpotifyRowKey $row))){$row}})
    $button=[Windows.Automation.ControlType]::Button
    $playCandidate=$null
    $playCandidateLeft=[double]::PositiveInfinity
    # Ronda 23: in query mode the controls are ranked by the words their result shares with the query
    # (Get-BaxySpotifyQueryOverlap), position only between equals; the exact mode has no rank (always 0).
    $playCandidateOverlap=-1
    # SP3: how many play controls of this search passed those filters (the detail of a search that picked nothing).
    $shown=0
    foreach($element in $results){try{
        if($element.Type -ne $button -or $element.Offscreen){continue}
        $rect=$element.Rect
        $name=$element.Fold
        $matches=if($Mode -eq 'query'){$name.StartsWith('reproducir ') -or $name.StartsWith('play ')}else{$name -eq $ExpectedPlay -or $name.StartsWith($ExpectedPlay+' ')}
        if(-not ($rect.Width -gt 0 -and $rect.Height -gt 0 -and $matches -and $rect.Top -gt ($SearchRect.Top+20) -and $rect.Top -lt ($SearchRect.Top+600) -and $rect.Left -ge $WindowRect.Left -and $rect.Right -le $WindowRect.Right)){continue}
        # Ranked only once a control passed the type, name and place filters: a handful per page, not the tree.
        $shown++
        $overlap=if($Mode -eq 'query'){Get-BaxySpotifyQueryOverlap $Title (Get-BaxySpotifyPressedResult $name '') $FunctionWords $PurposeMarkers}else{0}
        if($overlap -gt $playCandidateOverlap -or ($overlap -eq $playCandidateOverlap -and $rect.Left -lt $playCandidateLeft)){$playCandidate=$element;$playCandidateLeft=$rect.Left;$playCandidateOverlap=$overlap}
    }catch{}}
    $candidate=$null
    $candidateTop=[double]::PositiveInfinity
    $candidateIdentity=''
    # Results span the client content width independently of the centered
    # search box.  Bound candidates to the visible window instead of an old
    # search-box-relative column, which rejected valid results on wide layouts.
    foreach($element in $results){try{$rect=$element.Rect;$name=$element.Fold;if(-not $element.Offscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and $name -eq $Title -and $rect.Top -gt ($SearchRect.Top+20) -and $rect.Top -lt ($SearchRect.Top+600) -and $rect.Left -ge $WindowRect.Left -and $rect.Right -le $WindowRect.Right -and $rect.Top -lt $candidateTop){$candidate=$element;$candidateTop=$rect.Top}}catch{}}
    if($null -ne $candidate){
        # The leading result card labels its play button only as "Play" /
        # "Reproducir".  Bind that generic button to the exact-title card by
        # containment and prefer it over same-title covers in the song list.
        # X3: the card titled as the query is of this search, and so is what it
        # contains, even an element Spotify reused with the same name (its bare
        # «reproducir»).
        $candidateRect=$candidate.Rect
        foreach($element in $Rows){try{$rect=$element.Rect;$name=$element.Fold;if($element.Type -eq [Windows.Automation.ControlType]::Hyperlink -and $name -and $name -ne $Title -and $rect.Left -ge $candidateRect.Left -and $rect.Right -le $candidateRect.Right -and $rect.Top -ge $candidateRect.Top -and $rect.Bottom -le $candidateRect.Bottom){$candidateIdentity=$name;break}}catch{}}
        foreach($element in $Rows){try{$rect=$element.Rect;$name=$element.Fold;if($element.Type -eq $button -and -not $element.Offscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and $name -in @('reproducir','play') -and $rect.Left -ge $candidateRect.Left -and $rect.Right -le $candidateRect.Right -and $rect.Top -ge $candidateRect.Top -and $rect.Bottom -le $candidateRect.Bottom){$playCandidate=$element;break}}catch{}}
    }
    # SP (fin2 t1-c07/t2-c01; redpc, cold client: the box held the query while the Home page and the library rows,
    # drawn after the page before was read, still showed «reproducir descubrimiento semanal», «reproducir 00s rock
    # anthems»): a query search answered when it shows the card titled as the query or a result that names the
    # query (overlap above zero). This replaces the former proof by the box's value, which the URI sets seconds
    # before the page changes. A page of results none of which names the query is taken at the horizon.
    $answered=($null -ne $playCandidate -or $null -ne $candidate) -and ($Mode -ne 'query' -or $null -ne $candidate -or $playCandidateOverlap -gt 0)
    return [pscustomobject]@{Play=$playCandidate;Overlap=$playCandidateOverlap;Card=$candidate;Identity=$candidateIdentity;Answered=$answered;Shown=$shown}
}
function Get-BaxySpotifyNotFoundDetail($Rows,$PageBefore,[int]$Shown,[int]$Searches,[bool]$ColdStart,[bool]$BoxHoldsQuery,[bool]$Iconic,[bool]$Front,[string]$CoveredBy){
    # SP3 (tandas n9/n10 del notebook, t1-c07 and t2-c01: played in n9, «spotify_exact_result_not_found» after 24 s in
    # n10 with no stage, detail or times): what the last look of the search page showed, private codes for the log.
    # rows: named elements; before: of them, the page before the search; plays: play controls («reproducir …»);
    # fresh: of them, not of the page before; shown: those Select-BaxySpotifySearchResult kept (on screen, in the
    # result band); box: the search box holds the query; iconic: the window is minimized.
    # TZ-SP (tandas z2 del notebook, t2-c01 and t4-c01: twice every element as before and the box never the query, the
    # call after found the results already drawn): front: the client's window is the one in front; covered: the
    # processes whose windows above it cover all of it (BaxySpotifyNative.CoveredBy), 0 when some part of it shows.
    $before=@(foreach($row in $Rows){if($PageBefore.Contains((Get-BaxySpotifyRowKey $row))){$row}})
    $plays=@(foreach($row in $Rows){if($row.Type -eq [Windows.Automation.ControlType]::Button -and ($row.Fold.StartsWith('reproducir ') -or $row.Fold.StartsWith('play '))){$row}})
    $fresh=@(foreach($row in $plays){if(-not $PageBefore.Contains((Get-BaxySpotifyRowKey $row))){$row}})
    return "spotify_exact_result_not_found;searches=$Searches;cold=$([int]$ColdStart);rows=$($Rows.Count);before=$($before.Count);plays=$($plays.Count);fresh=$($fresh.Count);shown=$Shown;box=$([int]$BoxHoldsQuery);iconic=$([int]$Iconic);front=$([int]$Front);covered=$(if($CoveredBy){$CoveredBy}else{0})"
}
# END playback-evidence
function Get-BaxySpotifySnapshot([Windows.Automation.AutomationElement]$Root,[Windows.Automation.Condition]$Condition=$null){
    # Ronda 23 (t1-c07 «pon lo-fi para estudiar en spotify plis», 34 s inside the search): every phase walked the
    # whole tree with TrueCondition and then read Name, ControlType, BoundingRectangle and IsOffscreen of each element
    # across the process boundary, loop after loop. One FindAll now brings only the named elements (every control
    # this script looks at has a name) with those four properties cached in the same call; the loops read the copy,
    # each name folded once. A phase that looks for one kind of control passes its own condition (discovery: the
    # search combo, and the play buttons while a cold client builds its page).
    $cache=New-Object Windows.Automation.CacheRequest
    $cache.AutomationElementMode=[Windows.Automation.AutomationElementMode]::Full
    $cache.TreeScope=[Windows.Automation.TreeScope]::Element
    $cache.Add([Windows.Automation.AutomationElement]::NameProperty)
    $cache.Add([Windows.Automation.AutomationElement]::ControlTypeProperty)
    $cache.Add([Windows.Automation.AutomationElement]::BoundingRectangleProperty)
    $cache.Add([Windows.Automation.AutomationElement]::IsOffscreenProperty)
    $cache.Add([Windows.Automation.AutomationElement]::RuntimeIdProperty)
    $named=if($null -ne $Condition){$Condition}else{[Windows.Automation.NotCondition]::new([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,''))}
    $activation=$cache.Activate()
    try {
        $found=$Root.FindAll([Windows.Automation.TreeScope]::Descendants,$named)
    } finally {
        $activation.Dispose()
    }
    $rows=New-Object 'System.Collections.Generic.List[object]'
    foreach($element in $found){
        try {
            $name=[string]$element.Cached.Name
            $id=(@($element.GetCachedPropertyValue([Windows.Automation.AutomationElement]::RuntimeIdProperty))-join '.')
            $rows.Add([pscustomobject]@{Element=$element;Id=$id;Name=$name;Fold=(Fold $name);Type=$element.Cached.ControlType;Rect=$element.Cached.BoundingRectangle;Offscreen=$element.Cached.IsOffscreen})
        } catch {}
    }
    return ,$rows
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
    # M169: a client with no window yet, or whose process started under a
    # minute ago, is launching now: its accessibility tree is still partial.
    $settledSince=(Get-Date).AddSeconds(-60)
    $coldStart=$null -eq (Get-Process Spotify -ErrorAction SilentlyContinue|Where-Object {$_.MainWindowHandle -ne 0 -and $(try{$_.StartTime -lt $settledSince}catch{$true})}|Select-Object -First 1)
    Start-Process 'spotify:'
    $process=$null
    $search=$null
    $playableSeen=$false
    # The former 500 ms blind startup pause plus 12 s discovery window are
    # retained as one 12.5 s terminal horizon. Observe immediately so a warm
    # client does not pay either pause.
    $searchDeadline=(Get-Date).AddMilliseconds(12500)
    # Discovery looks for the search combo (and, for a client still building its page, a play button): it asks UIA
    # for those control types only instead of every named element.
    $discoveryCombos=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::ComboBox)
    $discoveryCombosAndButtons=[Windows.Automation.OrCondition]::new($discoveryCombos,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button))
    do {
        $process=Get-Process Spotify -ErrorAction SilentlyContinue|Where-Object {$_.MainWindowHandle -ne 0}|Select-Object -First 1
        if($null -ne $process){
            try {
                $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
                $all=Get-BaxySpotifySnapshot $root $(if($coldStart -and -not $playableSeen){$discoveryCombosAndButtons}else{$discoveryCombos})
                foreach($element in $all){try{$name=$element.Fold;$type=$element.Type;if($null -eq $search -and $type -eq [Windows.Automation.ControlType]::ComboBox -and ($name -like '*reproducir*' -or $name -like '*play*')){$search=$element.Element};if($type -eq [Windows.Automation.ControlType]::Button -and ($name.StartsWith('reproducir ') -or $name.StartsWith('play '))){$playableSeen=$true};if($null -ne $search -and (Test-BaxySpotifyContentExposed $coldStart $playableSeen)){break}}catch{}}
            } catch {}
        }
        if($null -ne $search -and (Test-BaxySpotifyContentExposed $coldStart $playableSeen)){break}
    } while((Wait-BaxyPoll $searchDeadline 300))
    if($null -eq $process){throw 'spotify_window_missing'}
    if($null -eq $search){throw 'spotify_search_box_missing'}
    if(-not (Confirm-BaxySpotifyForeground $process.MainWindowHandle)){throw 'spotify_foreground_not_verified'}
    # Spotify's search combo displays a transient suggestion overlay.  UIA may
    # still expose controls from the page behind that overlay, so clicking one
    # is not a verified selection.  Navigate to the canonical desktop search
    # URI instead and only inspect controls from the resulting page: the page
    # shown before it (behind an overlay or not) is read once here, and none of
    # its elements is ever a result (Get-BaxySpotifyPageBefore).
    $foldTitle=Fold($title)
    $valueBefore=Read-BaxySpotifySearchValue $search
    $keysBefore=if($valueBefore -ne $foldTitle){@((Get-BaxySpotifySnapshot ([Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)))|ForEach-Object {Get-BaxySpotifyRowKey $_})}else{@()}
    $pageBefore=Get-BaxySpotifyPageBefore $valueBefore $foldTitle $keysBefore
    $searchUri='spotify:search:'+[Uri]::EscapeDataString($title)
    if((Get-Date) -ge $hardEnd){throw 'spotify_deadline_reached'}
    Start-Process $searchUri
    $searchedAt=Get-Date
    $searches=1
    Add-BaxySpotifyMark;$stage='searched'
    # The desktop client can take several seconds to replace the previous
    # page after resolving a spotify:search URI: the first observation that
    # shows a result of this search ends the wait, never a blind sleep.
    # The function words and purpose markers the query is compared with (data passed by the adapter).
    $queryFunctionWords=@()
    $queryPurposeMarkers=@()
    if($Mode -eq 'query'){
        if(-not $QueryWordsBase64){throw 'spotify_query_words_missing'}
        $queryWords=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($QueryWordsBase64))|ConvertFrom-Json
        $queryFunctionWords=@($queryWords.function_words)+@($queryWords.medium_words)
        $queryPurposeMarkers=@($queryWords.purpose_markers)
    }
    $expectedPlay=Fold('Reproducir '+$title)
    $prefix=Fold(('Est'+[char]0x00E1+'s escuchando:'))
    # MUSIC1753: a client launched seconds earlier renders its search page late;
    # the bounded wait is 12 s. M169: a page that shows nothing playable at all
    # gets 20 s and one re-issued search (the adapter budget of 65 s covers
    # 12.5 + 20 + 12 + 15).
    $searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $true))
    $searchPageReady=$false
    $searchSnapshotReady=$false
    $searchObservationError=$null
    do {
        try {
            $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
            $all=Get-BaxySpotifySnapshot $root
            $searchRect=$search.Current.BoundingRectangle
            $windowRect=$root.Current.BoundingRectangle
            $alreadyPausedControl=$false
            foreach($element in $all){try{if($element.Type -eq [Windows.Automation.ControlType]::Button -and $element.Fold -in @('pausar','pause')){$alreadyPausedControl=$true;break}}catch{}}
            $beforeNowPlaying=''
            foreach($element in $all){try{$name=$element.Fold;if($name.StartsWith($prefix+' ')){$beforeNowPlaying=$name.Substring($prefix.Length+1);break}}catch{}}
            $choice=Select-BaxySpotifySearchResult $all $pageBefore $Mode $foldTitle $expectedPlay $searchRect $windowRect $queryFunctionWords $queryPurposeMarkers
            $playCandidate=$choice.Play
            $playCandidateOverlap=$choice.Overlap
            $candidate=$choice.Card
            $candidateIdentity=$choice.Identity
            $candidateAlreadyPlaying=$null -ne $candidate -and $beforeNowPlaying.StartsWith($foldTitle+' ') -and $candidateIdentity -and $beforeNowPlaying.Contains(' de '+$candidateIdentity)
            if($Mode -eq 'exact' -and $candidateAlreadyPlaying -and $alreadyPausedControl){[pscustomobject]@{ok=$true;effectObserved=$effect;error=$null;title=$title;processId=$process.Id}|ConvertTo-Json -Compress;exit 0}
            $searchSnapshotReady=$null -ne $playCandidate -or $null -ne $candidate
            $searchPageReady=$choice.Answered
            $searchObservationError=$null
        } catch {
            $searchPageReady=$false
            $searchSnapshotReady=$false
            $searchObservationError=$_
        }
        if($searchPageReady){break}
        if($null -eq $searchObservationError){
            $searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $searchSnapshotReady))
            if(Test-BaxySpotifyResearch $searches (((Get-Date)-$searchedAt).TotalMilliseconds) $searchSnapshotReady){
                $searches=2
                Start-Process $searchUri
                Add-BaxySpotifyMark 'researched'
            }
        }
    } while((Wait-BaxyPoll $searchPageDeadline 500))
    # At the horizon the last observation is taken as it is (a page of results none of which names the query).
    if(-not $searchPageReady -and $searchSnapshotReady -and $null -eq $searchObservationError){$searchPageReady=$true}
    if(-not $searchPageReady -and $null -ne $searchObservationError){throw $searchObservationError}
    if($null -eq $playCandidate){
        if($null -eq $candidate){
            # SP3: like every other failure, where it stopped (stage), what the last look showed (detail) and when.
            Add-BaxySpotifyMark
            $detail=Get-BaxySpotifyNotFoundDetail $(if($null -ne $all){$all}else{@()}) $pageBefore $(if($null -ne $choice){$choice.Shown}else{0}) $searches $coldStart ((Read-BaxySpotifySearchValue $search) -eq $foldTitle) ([BaxySpotifyNative]::IsIconic($process.MainWindowHandle)) ([BaxySpotifyNative]::GetForegroundWindow() -eq $process.MainWindowHandle) ([BaxySpotifyNative]::CoveredBy($process.MainWindowHandle))
            [pscustomobject]@{ok=$false;effectObserved=$effect;error='spotify_exact_result_not_found';stage=$stage;detail=$detail;timings=$timings}|ConvertTo-Json -Compress;exit 2
        }
        if($null -eq $playCandidate){
            Add-BaxySpotifyMark;$stage='candidate'
            if(-not (Confirm-BaxySpotifyForeground $process.MainWindowHandle)){throw 'spotify_foreground_not_verified'}
            InvokeElement $candidate.Element
            Add-BaxySpotifyMark;$stage='result'
            $detailDeadline=(Get-Date).AddSeconds(12)
            $detailObservationError=$null
            do {
                try {
                    $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
                    $all=Get-BaxySpotifySnapshot $root
                    foreach($element in $all){try{
                        $rect=$element.Rect
                        $name=$element.Fold
                        $matches=if($Mode -eq 'query'){
                            $name -in @('reproducir','play') -or $name.StartsWith('reproducir ') -or $name.StartsWith('play ')
                        }else{
                            $name -eq $expectedPlay -or $name.StartsWith($expectedPlay+' ')
                        }
                        if($element.Type -eq [Windows.Automation.ControlType]::Button -and -not $element.Offscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and $matches -and $rect.Top -gt ($searchRect.Top+20) -and $rect.Left -ge $windowRect.Left -and $rect.Right -le $windowRect.Right){
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
    if($null -eq $playCandidate){foreach($element in $all){try{$rect=$element.Rect;$name=$element.Fold;if($element.Type -eq [Windows.Automation.ControlType]::Button -and -not $element.Offscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and ($name -eq $expectedPlay -or $name.StartsWith($expectedPlay+' '))){$playCandidate=$element;break}}catch{}}}
    foreach($element in $all){try{$name=$element.Fold;if($element.Type -eq [Windows.Automation.ControlType]::Button -and $name -in @('pausar','pause')){$pauseAlready=$true;break}}catch{}}
    if($null -eq $playCandidate){
        [pscustomobject]@{ok=$false;effectObserved=$effect;error='spotify_exact_play_control_not_found'}|ConvertTo-Json -Compress;exit 2
    }
    $selectedControlName=[string]$playCandidate.Name
    $selectedFold=Fold($selectedControlName)
    $selectedRect=$playCandidate.Rect
    $selectedPauseName=Get-BaxySpotifyPauseName $selectedFold
    $pressedResult=Get-BaxySpotifyPressedResult $selectedFold $(if($null -ne $candidate){(@($foldTitle,$candidateIdentity)|Where-Object {$_})-join ' '}else{''})
    $pressedOverlap=Get-BaxySpotifyQueryOverlap $foldTitle $pressedResult $queryFunctionWords $queryPurposeMarkers
    $matchesQuery=$false
    # A same-named context that was already playing is not this press's doing.
    $flipBefore=$false
    foreach($element in $all){try{if($element.Type -eq [Windows.Automation.ControlType]::Button -and $selectedPauseName -and $element.Fold -eq $selectedPauseName -and ($selectedPauseName -notin @('pausar','pause') -or (Test-BaxySpotifyNear $element.Rect $selectedRect))){$flipBefore=$true;break}}catch{}}
    if(-not (Confirm-BaxySpotifyForeground $process.MainWindowHandle)){throw 'spotify_foreground_not_verified'}
    if((Get-Date) -ge $hardEnd){throw 'spotify_deadline_reached'}
    $effect=$true
    InvokeElement $playCandidate.Element
    $presses=1
    $repressedAt=$null
    $pressIgnored=$false
    $pressedAt=Get-Date
    Add-BaxySpotifyMark;$stage='play_clicked'
    $deadline=(Get-Date).AddSeconds(15)
    $verified=$false
    $resumedOnly=$false
    $playObservationError=$null
    do {
        try {
            $root=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
            $all=Get-BaxySpotifySnapshot $root
            $nowPlaying=$false
            $pause=$false
            $selectedFlipped=$false
            $replayControl=$null
            $prefix=Fold(('Est'+[char]0x00E1+'s escuchando:'))
            foreach($element in $all){try{$name=$element.Fold;if($name.StartsWith($prefix+' ')){$playingIdentity=$name.Substring($prefix.Length+1);$titleMatches=$playingIdentity -eq $foldTitle -or $playingIdentity.StartsWith($foldTitle+' de ');$identityMatches=-not $candidateIdentity -or $playingIdentity.Contains(' de '+$candidateIdentity);if($titleMatches -and $identityMatches){$nowPlaying=$true}};if($element.Type -eq [Windows.Automation.ControlType]::Button -and $name -in @('pausar','pause')){$pause=$true}}catch{}}
            foreach($element in $all){try{
                if($element.Type -eq [Windows.Automation.ControlType]::Button){
                    $name=$element.Fold
                    $rect=$element.Rect
                    # A bare «pausar» is also the player bar's own control: only
                    # the one standing where the pressed control stood counts.
                    if(-not $flipBefore -and $selectedPauseName -and $name -eq $selectedPauseName -and ($name -notin @('pausar','pause') -or (Test-BaxySpotifyNear $rect $selectedRect))){$selectedFlipped=$true}
                    if($name -eq $selectedFold -and -not $element.Offscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0 -and (Test-BaxySpotifyNear $rect $selectedRect)){$replayControl=$element}
                }
            }catch{}}
            $observedNowPlaying=''
            foreach($element in $all){try{$name=$element.Fold;if($name.StartsWith($prefix+' ')){$observedNowPlaying=$name.Substring($prefix.Length+1);break}}catch{}}
            if($Mode -eq 'query'){
                $windowNow=Fold((Get-Process -Id $process.Id -ErrorAction Stop).MainWindowTitle)
                $evidence=Get-BaxySpotifyQueryEvidence $pause $observedNowPlaying $beforeNowPlaying $pauseAlready $selectedFlipped $pressedResult @($observedNowPlaying,$windowNow)
                $verified=$evidence -eq 'started'
                $matchesQuery=Test-BaxySpotifyMatchesQuery $foldTitle $pressedResult $selectedFlipped @($observedNowPlaying,$windowNow) $queryFunctionWords $queryPurposeMarkers
                # Only the loaded track resumed: the wait goes on to its end (the line or the control may still move
                # to the result), and only a wait that never saw more ends unconfirmed.
                if($evidence -eq 'resumed'){$resumedOnly=$true}
            }else{
                $verified=Test-BaxySpotifyPlaybackVerified $Mode $pause $nowPlaying $observedNowPlaying $beforeNowPlaying $pauseAlready $selectedFlipped
            }
            $playObservationError=$null
            if(-not $verified -and (Test-BaxySpotifyRepress $presses (((Get-Date)-$pressedAt).TotalMilliseconds) $pause $pauseAlready $observedNowPlaying $beforeNowPlaying $selectedFlipped ($null -ne $replayControl))){
                # The first press landed before the client took it (a client
                # restored seconds earlier). Counted before pressing: never twice.
                $presses=2
                $repressedAt=Get-Date
                if(Confirm-BaxySpotifyForeground $process.MainWindowHandle){InvokeElement $replayControl.Element}
            }
            elseif(-not $verified -and $null -ne $repressedAt -and (Test-BaxySpotifyPressIgnored $presses (((Get-Date)-$repressedAt).TotalMilliseconds) $pause $pauseAlready $observedNowPlaying $beforeNowPlaying $selectedFlipped)){
                $pressIgnored=$true
            }
        } catch {
            $verified=$false
            $playObservationError=$_
        }
        if($verified -or $pressIgnored){break}
    } while((Wait-BaxyPoll $deadline 500))
    if(-not $verified -and $null -ne $playObservationError){throw $playObservationError}
    $failure=if($verified){$null}elseif($resumedOnly){'spotify_query_result_not_confirmed'}else{'spotify_'+$stage+'_not_verified'}
    $observedTitle=(Get-Process -Id $process.Id -ErrorAction Stop).MainWindowTitle
    [pscustomobject]@{ok=$verified;effectObserved=$effect;error=$failure;title=$observedTitle;selectedControl=$selectedControlName;beforeNowPlaying=$beforeNowPlaying;observedNowPlaying=$observedNowPlaying;pauseBefore=$pauseAlready;selectedFlipped=$selectedFlipped;matchesQuery=$(if($Mode -eq 'query'){$matchesQuery}else{$null});pressedOverlap=$pressedOverlap;presses=$presses;pressIgnored=$pressIgnored;searches=$searches;coldStart=$coldStart;processId=$process.Id}|ConvertTo-Json -Compress
} catch {
    Add-BaxySpotifyMark
    [pscustomobject]@{ok=$false;effectObserved=$effect;error='spotify_uia_failed';stage=$stage;detail=$_.Exception.Message;timings=$timings}|ConvertTo-Json -Compress
    exit 2
}
