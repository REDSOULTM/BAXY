[CmdletBinding(DefaultParameterSetName='Key')]
param(
    [Parameter(Mandatory=$true,ParameterSetName='Key',Position=0)]
    [ValidateSet('alt_tab','arrow_down','arrow_left','arrow_right','arrow_up','backspace','context_menu','control','ctrl_l','ctrl_shift_escape','ctrl_v','delete','end','enter','escape','home','page_down','page_up','shift','space','tab','win')]
    [string]$Key,
    [Parameter(Mandatory=$true,ParameterSetName='Pointer')]
    [ValidateSet('click','move_center','scroll_down')]
    [string]$PointerAction,
    [Parameter(Mandatory=$true,ParameterSetName='Text')]
    [string]$TextBase64,
    [Parameter(Mandatory=$true,ParameterSetName='Layout')]
    [ValidateSet('spanish')]
    [string]$Layout,
    [Parameter(Mandatory=$true,ParameterSetName='Keyboard')]
    [switch]$OpenOnScreenKeyboard,
    [Parameter(Mandatory=$true,ParameterSetName='LayoutStatus')]
    [switch]$ReadKeyboardLayout,
    [Parameter(Mandatory=$true,ParameterSetName='Paste')]
    [switch]$PasteClipboard,
    [Parameter(Mandatory=$true,ParameterSetName='Copy')]
    [switch]$CopySelection
)

$ErrorActionPreference='Stop'
$effect=$false
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class BaxyKeyInput {
    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT {
        public uint type;
        public InputUnion data;
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion {
        [FieldOffset(0)] public KEYBDINPUT keyboard;
        [FieldOffset(0)] public MOUSEINPUT mouse;
        [FieldOffset(0)] public HARDWAREINPUT hardware;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT {
        public ushort virtualKey;
        public ushort scanCode;
        public uint flags;
        public uint time;
        public UIntPtr extraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MOUSEINPUT {
        public int dx;
        public int dy;
        public uint mouseData;
        public uint flags;
        public uint time;
        public UIntPtr extraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct HARDWAREINPUT {
        public uint message;
        public ushort parameterLow;
        public ushort parameterHigh;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT {
        public int x;
        public int y;
    }

    [DllImport("user32.dll", SetLastError=true)]
    private static extern uint SendInput(uint count, INPUT[] inputs, int size);

    [DllImport("user32.dll")]
    private static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT point);

    [DllImport("user32.dll")]
    private static extern int GetSystemMetrics(int index);

    public static int InputSize {
        get { return Marshal.SizeOf(typeof(INPUT)); }
    }

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError=true)]
    public static extern uint CountClipboardFormats();

    [DllImport("user32.dll")]
    public static extern uint GetClipboardSequenceNumber();

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);

    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr window, StringBuilder text, int count);

    [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    private static extern IntPtr LoadKeyboardLayout(string layoutId, uint flags);

    [DllImport("user32.dll")]
    private static extern IntPtr GetKeyboardLayout(uint threadId);

    [DllImport("user32.dll", SetLastError=true)]
    private static extern bool PostMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr window);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr window);

    public static uint Press(ushort virtualKey) {
        INPUT[] inputs = new INPUT[2];
        inputs[0].type = 1;
        inputs[0].data.keyboard.virtualKey = virtualKey;
        inputs[1].type = 1;
        inputs[1].data.keyboard.virtualKey = virtualKey;
        inputs[1].data.keyboard.flags = 2;
        return SendInput((uint)inputs.Length, inputs, InputSize);
    }

    public static uint PressChord(ushort[] keys) {
        INPUT[] inputs = new INPUT[keys.Length * 2];
        for (int index = 0; index < keys.Length; index++) {
            inputs[index].type = 1;
            inputs[index].data.keyboard.virtualKey = keys[index];
        }
        for (int index = 0; index < keys.Length; index++) {
            inputs[keys.Length + index].type = 1;
            inputs[keys.Length + index].data.keyboard.virtualKey = keys[keys.Length - index - 1];
            inputs[keys.Length + index].data.keyboard.flags = 2;
        }
        return SendInput((uint)inputs.Length, inputs, InputSize);
    }

    public static bool SetSpanishLayout(IntPtr window, out ushort observedLanguageId) {
        observedLanguageId = 0;
        uint processId;
        uint threadId = GetWindowThreadProcessId(window, out processId);
        if (threadId == 0) return false;
        IntPtr layout = LoadKeyboardLayout("0000080A", 1);
        if (layout == IntPtr.Zero) return false;
        const uint WM_INPUTLANGCHANGEREQUEST = 0x0050;
        if (!PostMessage(window, WM_INPUTLANGCHANGEREQUEST, IntPtr.Zero, layout)) return false;
        for (int attempt = 0; attempt < 20; attempt++) {
            System.Threading.Thread.Sleep(50);
            observedLanguageId = unchecked((ushort)GetKeyboardLayout(threadId).ToInt64());
            if ((observedLanguageId & 0x03ff) == 0x000a) return true;
        }
        return false;
    }

    public static bool ReadKeyboardLayout(IntPtr window, out ushort observedLanguageId) {
        observedLanguageId = 0;
        uint processId;
        uint threadId = GetWindowThreadProcessId(window, out processId);
        if (threadId == 0) return false;
        observedLanguageId = unchecked((ushort)GetKeyboardLayout(threadId).ToInt64());
        return observedLanguageId != 0;
    }

    public static uint TypeText(string text) {
        INPUT[] inputs = new INPUT[text.Length * 2];
        for (int index = 0; index < text.Length; index++) {
            inputs[index * 2].type = 1;
            inputs[index * 2].data.keyboard.scanCode = text[index];
            inputs[index * 2].data.keyboard.flags = 4;
            inputs[index * 2 + 1].type = 1;
            inputs[index * 2 + 1].data.keyboard.scanCode = text[index];
            inputs[index * 2 + 1].data.keyboard.flags = 6;
        }
        return inputs.Length == 0 ? 0 : SendInput((uint)inputs.Length, inputs, InputSize);
    }

    public static bool MoveCenter(out POINT observed) {
        int x = Math.Max(0, GetSystemMetrics(0) / 2);
        int y = Math.Max(0, GetSystemMetrics(1) / 2);
        bool moved = SetCursorPos(x, y);
        bool read = GetCursorPos(out observed);
        return moved && read && Math.Abs(observed.x - x) <= 1 && Math.Abs(observed.y - y) <= 1;
    }

    public static uint MouseAction(bool click) {
        INPUT[] inputs = click ? new INPUT[2] : new INPUT[1];
        inputs[0].type = 0;
        inputs[0].data.mouse.flags = click ? 0x0002u : 0x0800u;
        if (!click) inputs[0].data.mouse.mouseData = unchecked((uint)-120);
        if (click) {
            inputs[1].type = 0;
            inputs[1].data.mouse.flags = 0x0004u;
        }
        return SendInput((uint)inputs.Length, inputs, InputSize);
    }

    public static string WindowTitle(IntPtr window) {
        var text = new StringBuilder(512);
        GetWindowText(window, text, text.Capacity);
        return text.ToString();
    }
}
'@

    $virtualKeys=@{
        arrow_down=0x28; arrow_left=0x25; arrow_right=0x27; arrow_up=0x26
        backspace=0x08; context_menu=0x5D; control=0x11; delete=0x2E; end=0x23
        enter=0x0D; escape=0x1B; home=0x24; page_down=0x22; page_up=0x21
        shift=0x10; space=0x20; tab=0x09; win=0x5B
    }
    $before=[BaxyKeyInput]::GetForegroundWindow()
    if($before -eq [IntPtr]::Zero){throw 'foreground_window_missing'}
    [uint32]$beforeProcess=0
    [void][BaxyKeyInput]::GetWindowThreadProcessId($before,[ref]$beforeProcess)
    $beforeTitle=[BaxyKeyInput]::WindowTitle($before)
    $expectedInputSize=$(if([IntPtr]::Size -eq 8){40}else{28})
    if([BaxyKeyInput]::InputSize -ne $expectedInputSize){throw 'sendinput_layout_invalid'}
    $action=$PSCmdlet.ParameterSetName.ToLowerInvariant()
    $expected=0;$accepted=0;$verified=$false;$textLength=0;$pointerX=$null;$pointerY=$null;$layoutLanguageId=$null;$openedProcessId=$null
    $clipboardFormatCount=$null;$clipboardSequenceBefore=$null;$clipboardSequenceAfter=$null
    if($PSCmdlet.ParameterSetName -eq 'Key') {
        $chords=@{
            alt_tab=[uint16[]]@(0x12,0x09)
            # ctrl_l enfoca la barra de direcciones del navegador de delante.
            ctrl_l=[uint16[]]@(0x11,0x4C)
            ctrl_shift_escape=[uint16[]]@(0x11,0x10,0x1B)
            ctrl_v=[uint16[]]@(0x11,0x56)
        }
        $isChord=$chords.ContainsKey($Key)
        $expected=$(if($isChord){$chords[$Key].Length*2}else{2})
        $accepted=$(if($isChord){[BaxyKeyInput]::PressChord($chords[$Key])}else{[BaxyKeyInput]::Press([uint16]$virtualKeys[$Key])})
        $verified=$accepted -eq $expected
    } elseif($PSCmdlet.ParameterSetName -eq 'Copy') {
        $clipboardSequenceBefore=[BaxyKeyInput]::GetClipboardSequenceNumber()
        $expected=4
        $accepted=[BaxyKeyInput]::PressChord([uint16[]]@(0x11,0x43))
        $verified=$accepted -eq $expected
    } elseif($PSCmdlet.ParameterSetName -eq 'Paste') {
        $clipboardFormatCount=[BaxyKeyInput]::CountClipboardFormats()
        if($clipboardFormatCount -lt 1){throw 'clipboard_empty'}
        $clipboardSequenceBefore=[BaxyKeyInput]::GetClipboardSequenceNumber()
        $expected=4
        $accepted=[BaxyKeyInput]::PressChord([uint16[]]@(0x11,0x56))
        $verified=$accepted -eq $expected
    } elseif($PSCmdlet.ParameterSetName -eq 'Text') {
        $text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TextBase64))
        if([string]::IsNullOrWhiteSpace($text) -or $text.Length -gt 4096){throw 'text_input_invalid'}
        $textLength=$text.Length;$expected=$text.Length*2
        $accepted=[BaxyKeyInput]::TypeText($text)
        $verified=$accepted -eq $expected
    } elseif($PointerAction -eq 'move_center') {
        $point=New-Object BaxyKeyInput+POINT
        $verified=[BaxyKeyInput]::MoveCenter([ref]$point)
        $pointerX=$point.x;$pointerY=$point.y;$accepted=$(if($verified){1}else{0});$expected=1
    } elseif($PSCmdlet.ParameterSetName -eq 'Pointer') {
        $expected=$(if($PointerAction -eq 'click'){2}else{1})
        $accepted=[BaxyKeyInput]::MouseAction($PointerAction -eq 'click')
        $verified=$accepted -eq $expected
    } elseif($PSCmdlet.ParameterSetName -eq 'Layout') {
        [uint16]$observedLayout=0
        $verified=[BaxyKeyInput]::SetSpanishLayout($before,[ref]$observedLayout)
        $layoutLanguageId=('0x{0:x4}' -f $observedLayout)
        $accepted=$(if($verified){1}else{0});$expected=1
    } elseif($PSCmdlet.ParameterSetName -eq 'Keyboard') {
        $oskPath=Join-Path ([Environment]::GetFolderPath('Windows')) 'System32\osk.exe'
        if(-not (Test-Path -LiteralPath $oskPath -PathType Leaf)){throw 'on_screen_keyboard_missing'}
        [void](Start-Process -FilePath $oskPath -PassThru)
        $window=[IntPtr]::Zero
        for($attempt=0;$attempt -lt 50;$attempt++){
            Start-Sleep -Milliseconds 100
            $candidate=Get-Process -Name 'osk' -ErrorAction SilentlyContinue | Where-Object {
                $_.MainWindowHandle -ne [IntPtr]::Zero
            } | Select-Object -First 1
            if($null -ne $candidate){
                $openedProcessId=$candidate.Id
                $window=$candidate.MainWindowHandle
                break
            }
        }
        if($window -ne [IntPtr]::Zero){
            $verified=[BaxyKeyInput]::IsWindowVisible($window)
        }
        $accepted=$(if($verified){1}else{0});$expected=1
    } else {
        [uint16]$observedLayout=0
        $verified=[BaxyKeyInput]::ReadKeyboardLayout($before,[ref]$observedLayout)
        $layoutLanguageId=('0x{0:x4}' -f $observedLayout)
        $accepted=$(if($verified){1}else{0});$expected=1
    }
    $authority=$(if($PSCmdlet.ParameterSetName -eq 'Layout'){
        'win32_foreground_keyboard_layout_postread'
    }elseif($PSCmdlet.ParameterSetName -eq 'Keyboard'){
        'windows_osk_process_window_visible_postread'
    }elseif($PSCmdlet.ParameterSetName -eq 'LayoutStatus'){
        'win32_foreground_keyboard_layout_read'
    }elseif($PSCmdlet.ParameterSetName -eq 'Copy'){
        'win32_foreground_identity_sendinput_clipboard_sequence_postread'
    }elseif($PSCmdlet.ParameterSetName -eq 'Paste'){
        'win32_clipboard_nonempty_foreground_identity_sendinput_acceptance'
    }else{
        'win32_sendinput_return_count'
    })
    $effect=$(if($PSCmdlet.ParameterSetName -eq 'LayoutStatus'){
        $false
    }else{
        ($accepted -gt 0) -or ($openedProcessId -ne $null)
    })
    Start-Sleep -Milliseconds 120
    $after=[BaxyKeyInput]::GetForegroundWindow()
    [uint32]$afterProcess=0
    if($after -ne [IntPtr]::Zero){
        [void][BaxyKeyInput]::GetWindowThreadProcessId($after,[ref]$afterProcess)
    }
    if($PSCmdlet.ParameterSetName -eq 'Copy'){
        $clipboardSequenceAfter=[BaxyKeyInput]::GetClipboardSequenceNumber()
        $clipboardFormatCount=[BaxyKeyInput]::CountClipboardFormats()
        $verified=$verified -and ($after -eq $before) -and
            ($afterProcess -eq $beforeProcess) -and
            ($clipboardSequenceAfter -ne $clipboardSequenceBefore) -and
            ($clipboardFormatCount -gt 0)
    } elseif($PSCmdlet.ParameterSetName -eq 'Paste'){
        $clipboardSequenceAfter=[BaxyKeyInput]::GetClipboardSequenceNumber()
        $verified=$verified -and ($after -eq $before) -and
            ($afterProcess -eq $beforeProcess) -and
            ($clipboardSequenceAfter -eq $clipboardSequenceBefore)
    }
    $lastError=$(if($verified){0}else{[Runtime.InteropServices.Marshal]::GetLastWin32Error()})
    [pscustomobject]@{
        version=1
        ok=$verified
        effectObserved=$effect
        action=$action
        key=$Key
        pointerAction=$PointerAction
        pointerX=$pointerX
        pointerY=$pointerY
        textLength=$textLength
        clipboardFormatCount=$clipboardFormatCount
        clipboardSequenceBefore=$clipboardSequenceBefore
        clipboardSequenceAfter=$clipboardSequenceAfter
        layout=$Layout
        layoutLanguageId=$layoutLanguageId
        language=$(if($null -ne $layoutLanguageId -and ([Convert]::ToUInt16($layoutLanguageId.Substring(2),16) -band 0x03ff) -eq 0x000a){'spanish'}else{'other'})
        openedProcessId=$openedProcessId
        acceptedEvents=$accepted
        expectedEvents=$expected
        inputSize=[BaxyKeyInput]::InputSize
        lastWin32Error=$lastError
        foregroundProcessIdBefore=$beforeProcess
        foregroundProcessIdAfter=$afterProcess
        foregroundTitleBefore=$beforeTitle
        authority=$authority
        error=$(if($verified){$null}else{'input_effect_not_verified'})
    } | ConvertTo-Json -Compress
    if(-not $verified){exit 2}
} catch {
    [pscustomobject]@{
        version=1
        ok=$false
        effectObserved=$effect
        key=$Key
        error=$(if($PSCmdlet.ParameterSetName -eq 'Copy'){'clipboard_copy_sendinput_failed'}elseif($PSCmdlet.ParameterSetName -eq 'Paste'){'clipboard_paste_sendinput_failed'}else{'key_press_sendinput_failed'})
    } | ConvertTo-Json -Compress
    exit 2
}
