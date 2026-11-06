$ErrorActionPreference='Stop'
# The runner reads stdout as UTF-8 (PowerShellCommand); PowerShell 5.1 otherwise writes the console's code page.
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$effect=$false
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
# Encargo 94 (verificacion en vivo 84, 0 de 14): Ctrl+A belongs to the application, and its language binds it: Windows 11's
# Notepad in Spanish opens "Abrir" with it (and selects all with Ctrl+E), leaving a dialog over the person's document;
# Microsoft recommends localizing accelerators (Keyboard accelerators: "in the Spanish version of Windows, Ctrl+N is used
# for bold"). The selection is therefore asked of the control itself (ITextRangeProvider::Select on its DocumentRange:
# "Selects the span of text that corresponds to this text range, and removes any previous selection") and read back; the
# keys are the last resort, for a control that refuses it. A window they raise that was not there is said, and closed when
# it is someone's dialog (owned), since BAXY opened it: a dialog takes WM_CLOSE as its Cancel (Dialog Box Default Message
# Processing: "Posts the BN_CLICKED notification message to the dialog box, specifying IDCANCEL").
function Select-BaxyWholeText([scriptblock]$Select,[scriptblock]$Covered,[scriptblock]$SendKeys,[scriptblock]$Windows,[scriptblock]$Close,[int]$KeysWait=1500){
    $answer=@{verified=$false;selectedBy=$null;effect=$false;accepted=$null;expected=$null;dialog=$null;error=$null}
    $asked=$false
    try {
        & $Select | Out-Null
        $asked=$true
        $answer.effect=$true
    } catch {}
    if($asked){
        $deadline=(Get-Date).AddMilliseconds(300)
        do {
            if(& $Covered){
                $answer.verified=$true
                $answer.selectedBy='ui_automation'
                return $answer
            }
        } while((Wait-BaxyPoll $deadline 25))
    }
    $before=@(& $Windows | ForEach-Object { $_.handle })
    $answer.accepted=[uint32](& $SendKeys)
    $answer.expected=4
    if($answer.accepted -gt 0){$answer.effect=$true}
    if($answer.accepted -ne $answer.expected){
        $answer.error='select_all_input_not_accepted'
        return $answer
    }
    $raised=@()
    $deadline=(Get-Date).AddMilliseconds($KeysWait)
    do {
        if(& $Covered){
            $answer.verified=$true
            $answer.selectedBy='keyboard'
            return $answer
        }
        $raised=@(& $Windows | Where-Object { $before -notcontains $_.handle })
        if($raised.Count -gt 0){break}
    } while((Wait-BaxyPoll $deadline 50))
    if($raised.Count -eq 0){
        $answer.error='select_all_postcondition_not_verified'
        return $answer
    }
    $closed=$false
    if($raised[0].owned){$closed=[bool](& $Close $raised[0].handle)}
    $answer.dialog=@{title=[string]$raised[0].title;closed=$closed}
    $answer.error='select_all_opened_dialog'
    return $answer
}
try {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class BaxyDesktopSelectAllNative
{
    private const uint InputKeyboard = 1;
    private const uint KeyEventKeyUp = 0x0002;
    private const ushort VirtualKeyControl = 0x11;
    private const ushort VirtualKeyA = 0x41;
    private const uint EmGetSel = 0x00B0;
    private const uint EmSetSel = 0x00B1;
    private const uint EmGetTextLength = 0x000E;
    private const uint WindowMessageClose = 0x0010;
    private const uint GetWindowOwner = 4;

    private delegate bool EnumWindowsCallback(IntPtr window, IntPtr parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsCallback callback, IntPtr parameter);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(IntPtr window);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindow(IntPtr window);

    [DllImport("user32.dll")]
    private static extern IntPtr GetWindow(IntPtr window, uint command);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextW(IntPtr window, System.Text.StringBuilder text, int count);

    [DllImport("user32.dll", EntryPoint = "PostMessageW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);

    public static long[] VisibleWindowsOf(int processId)
    {
        var windows = new System.Collections.Generic.List<long>();
        EnumWindowsCallback callback = (window, parameter) =>
        {
            uint owner;
            GetWindowThreadProcessId(window, out owner);
            if (owner == (uint)processId && IsWindowVisible(window))
                windows.Add(window.ToInt64());
            return true;
        };
        EnumWindows(callback, IntPtr.Zero);
        GC.KeepAlive(callback);
        return windows.ToArray();
    }

    public static string TitleOf(long window)
    {
        var text = new System.Text.StringBuilder(512);
        GetWindowTextW(new IntPtr(window), text, text.Capacity);
        return text.ToString();
    }

    public static bool IsOwned(long window)
    {
        return GetWindow(new IntPtr(window), GetWindowOwner) != IntPtr.Zero;
    }

    public static bool IsOpen(long window)
    {
        return IsWindow(new IntPtr(window));
    }

    public static bool AskToClose(long window)
    {
        return PostMessage(new IntPtr(window), WindowMessageClose, IntPtr.Zero, IntPtr.Zero);
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        public uint Type;
        public InputUnion Data;
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)] public KeyboardInput Keyboard;
        [FieldOffset(0)] public MouseInput Mouse;
        [FieldOffset(0)] public HardwareInput Hardware;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public UIntPtr ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MouseInput
    {
        public int X;
        public int Y;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public UIntPtr ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct HardwareInput
    {
        public uint Message;
        public ushort ParameterLow;
        public ushort ParameterHigh;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(
        uint count,
        Input[] inputs,
        int size);

    [DllImport("user32.dll", EntryPoint = "SendMessageW")]
    private static extern IntPtr SendMessageSelection(
        IntPtr window,
        uint message,
        out uint start,
        out uint end);

    [DllImport("user32.dll", EntryPoint = "SendMessageW")]
    private static extern IntPtr SendMessageValue(
        IntPtr window,
        uint message,
        IntPtr wParam,
        IntPtr lParam);

    public static uint SendControlA()
    {
        Input[] inputs =
        {
            Key(VirtualKeyControl, 0),
            Key(VirtualKeyA, 0),
            Key(VirtualKeyA, KeyEventKeyUp),
            Key(VirtualKeyControl, KeyEventKeyUp),
        };
        return SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>());
    }

    public static int ReadTextLength(IntPtr window)
    {
        return checked((int)SendMessageValue(
            window,
            EmGetTextLength,
            IntPtr.Zero,
            IntPtr.Zero));
    }

    public static void ReadSelection(IntPtr window, out uint start, out uint end)
    {
        SendMessageSelection(window, EmGetSel, out start, out end);
    }

    public static void SelectAll(IntPtr window)
    {
        SendMessageValue(
            window,
            EmSetSel,
            IntPtr.Zero,
            new IntPtr(-1));
    }

    private static Input Key(ushort virtualKey, uint flags)
    {
        return new Input
        {
            Type = InputKeyboard,
            Data = new InputUnion
            {
                Keyboard = new KeyboardInput
                {
                    VirtualKey = virtualKey,
                    Flags = flags,
                    // BAXY's input mark (BaxyInputMark.cs).
                    ExtraInfo = new UIntPtr(0x42415859u),
                },
            },
        };
    }
}
'@
    $focused=[Windows.Automation.AutomationElement]::FocusedElement
    if($null -eq $focused){throw 'focused_element_missing'}
    $processId=[int]$focused.Current.ProcessId
    $nativeHandle=[IntPtr]$focused.Current.NativeWindowHandle
    $pattern=$null
    $hasTextPattern=$focused.TryGetCurrentPattern(
        [Windows.Automation.TextPattern]::Pattern,
        [ref]$pattern)
    $text=if($hasTextPattern){[Windows.Automation.TextPattern]$pattern}else{$null}
    # Ronda final: everything already selected, read before anything is sent, is the state reached (changed:false).
    $alreadyAll=$false
    try {
        if($hasTextPattern){
            $before=@($text.GetSelection())
            $alreadyAll=$before.Count -eq 1 -and
                ([string]$text.DocumentRange.GetText(1)).Length -gt 0 -and
                $before[0].CompareEndpoints(
                    [Windows.Automation.Text.TextPatternRangeEndpoint]::Start,
                    $text.DocumentRange,
                    [Windows.Automation.Text.TextPatternRangeEndpoint]::Start) -eq 0 -and
                $before[0].CompareEndpoints(
                    [Windows.Automation.Text.TextPatternRangeEndpoint]::End,
                    $text.DocumentRange,
                    [Windows.Automation.Text.TextPatternRangeEndpoint]::End) -eq 0
        } elseif($nativeHandle -ne [IntPtr]::Zero){
            $lengthBefore=[BaxyDesktopSelectAllNative]::ReadTextLength($nativeHandle)
            [uint32]$startBefore=0
            [uint32]$endBefore=0
            [BaxyDesktopSelectAllNative]::ReadSelection($nativeHandle,[ref]$startBefore,[ref]$endBefore)
            $alreadyAll=$lengthBefore -gt 0 -and $startBefore -eq 0 -and $endBefore -eq [uint32]$lengthBefore
        }
    } catch { $alreadyAll=$false }
    if($alreadyAll){
        [pscustomobject]@{
            version=1
            ok=$true
            effectObserved=$false
            alreadyReached=$true
            processId=$processId
            authority='selection_preread'
            error=$null
        }|ConvertTo-Json -Compress
        exit 0
    }
    if($hasTextPattern){
        $focusStayed={
            $focusedNow=[Windows.Automation.AutomationElement]::FocusedElement
            $null -ne $focusedNow -and [int]$focusedNow.Current.ProcessId -eq $processId
        }
        $selected=Select-BaxyWholeText `
            -Select { $text.DocumentRange.Select() } `
            -Covered {
                try {
                    if(-not (& $focusStayed)){return $false}
                    $selection=@($text.GetSelection())
                    $selection.Count -eq 1 -and
                        $selection[0].CompareEndpoints(
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::Start,
                            $text.DocumentRange,
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::Start) -eq 0 -and
                        $selection[0].CompareEndpoints(
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::End,
                            $text.DocumentRange,
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::End) -eq 0
                } catch { $false }
            } `
            -SendKeys {
                # The keys go to the window in front: with the focus gone to another program, they would be its keys.
                if(-not (& $focusStayed)){throw 'focused_element_changed'}
                [BaxyDesktopSelectAllNative]::SendControlA()
            } `
            -Windows {
                foreach($window in [BaxyDesktopSelectAllNative]::VisibleWindowsOf($processId)){
                    @{handle=$window;title=[BaxyDesktopSelectAllNative]::TitleOf($window);owned=[BaxyDesktopSelectAllNative]::IsOwned($window)}
                }
            } `
            -Close {
                param($handle)
                if(-not [BaxyDesktopSelectAllNative]::AskToClose($handle)){return $false}
                $closing=(Get-Date).AddMilliseconds(1500)
                do {
                    if(-not [BaxyDesktopSelectAllNative]::IsOpen($handle)){return $true}
                } while((Wait-BaxyPoll $closing 50))
                $false
            }
        $effect=$selected.effect
        $receipt=[ordered]@{
            version=1
            ok=$selected.verified
            effectObserved=$effect
            processId=$processId
            authority='uia_textpattern_selection_postread'
            selectedBy=$selected.selectedBy
            error=$selected.error
        }
        if($null -ne $selected.accepted){
            $receipt.acceptedEvents=$selected.accepted
            $receipt.expectedEvents=$selected.expected
        }
        if($null -ne $selected.dialog){$receipt.dialogOpened=$selected.dialog}
        [pscustomobject]$receipt|ConvertTo-Json -Compress
        if(-not $selected.verified){exit 2}
        exit 0
    }

    if($nativeHandle -eq [IntPtr]::Zero){
        throw 'focused_control_selection_unverifiable'
    }
    [BaxyDesktopSelectAllNative]::SelectAll($nativeHandle)
    $effect=$true

    $deadline=(Get-Date).AddMilliseconds(250)
    $authority=$null
    $verified=$false
    $focusChanged=$false
    $controlUnverifiable=$false
    $observationError=$null
    do {
        try {
            $focusedAfter=[Windows.Automation.AutomationElement]::FocusedElement
            $focusChanged=$null -eq $focusedAfter -or
                [int]$focusedAfter.Current.ProcessId -ne $processId
            $controlUnverifiable=$false
            if(-not $focusChanged){
                $afterHandle=[IntPtr]$focusedAfter.Current.NativeWindowHandle
                $controlUnverifiable=$nativeHandle -eq [IntPtr]::Zero -or
                    $afterHandle -ne $nativeHandle
                if(-not $controlUnverifiable){
                    $textLength=[BaxyDesktopSelectAllNative]::ReadTextLength($nativeHandle)
                    [uint32]$selectionStart=0
                    [uint32]$selectionEnd=0
                    [BaxyDesktopSelectAllNative]::ReadSelection(
                        $nativeHandle,
                        [ref]$selectionStart,
                        [ref]$selectionEnd)
                    $verified=$textLength -gt 0 -and
                        $selectionStart -eq 0 -and
                        $selectionEnd -eq [uint32]$textLength
                    $authority='win32_edit_selection_postread'
                } else {
                    $verified=$false
                }
            } else {
                $verified=$false
            }
            $observationError=$null
        } catch {
            $verified=$false
            $observationError=$_
        }
        if($verified){break}
    } while((Wait-BaxyPoll $deadline 25))
    if(-not $verified -and $null -ne $observationError){throw $observationError}
    if(-not $verified -and $focusChanged){throw 'focused_element_changed'}
    if(-not $verified -and $controlUnverifiable){
        [pscustomobject]@{
            version=1
            ok=$false
            effectObserved=$effect
            processId=$processId
            error='focused_control_selection_unverifiable'
        }|ConvertTo-Json -Compress
        exit 2
    }

    [pscustomobject]@{
        version=1
        ok=$verified
        effectObserved=$effect
        processId=$processId
        authority=$authority
        error=$(if($verified){$null}else{'select_all_postcondition_not_verified'})
    }|ConvertTo-Json -Compress
    if(-not $verified){exit 2}
} catch {
    [pscustomobject]@{version=1;ok=$false;effectObserved=$effect;error='select_all_uia_failed'}|ConvertTo-Json -Compress
    exit 2
}
