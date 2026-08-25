$ErrorActionPreference='Stop'
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
    $accepted=$null
    $expected=$null
    if($hasTextPattern){
        $accepted=[BaxyDesktopSelectAllNative]::SendControlA()
        $expected=4
        $effect=$accepted -gt 0
        if($accepted -ne $expected){
            [pscustomobject]@{
                version=1
                ok=$false
                effectObserved=$effect
                processId=$processId
                acceptedEvents=$accepted
                expectedEvents=$expected
                error='select_all_input_not_accepted'
            }|ConvertTo-Json -Compress
            exit 2
        }
    } else {
        if($nativeHandle -eq [IntPtr]::Zero){
            throw 'focused_control_selection_unverifiable'
        }
        [BaxyDesktopSelectAllNative]::SelectAll($nativeHandle)
        $effect=$true
    }

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
                if($hasTextPattern){
                    $selection=@($text.GetSelection())
                    $verified=$selection.Count -eq 1 -and
                        $selection[0].CompareEndpoints(
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::Start,
                            $text.DocumentRange,
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::Start) -eq 0 -and
                        $selection[0].CompareEndpoints(
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::End,
                            $text.DocumentRange,
                            [Windows.Automation.Text.TextPatternRangeEndpoint]::End) -eq 0
                    $authority='uia_textpattern_selection_postread'
                } else {
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
        acceptedEvents=$accepted
        expectedEvents=$expected
        authority=$authority
        error=$(if($verified){$null}else{'select_all_postcondition_not_verified'})
    }|ConvertTo-Json -Compress
    if(-not $verified){exit 2}
} catch {
    [pscustomobject]@{version=1;ok=$false;effectObserved=$effect;error='select_all_uia_failed'}|ConvertTo-Json -Compress
    exit 2
}
