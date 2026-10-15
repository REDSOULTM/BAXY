using System.Diagnostics;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3 point 0 (r4a M1): the UI Automation client injects an unmarked key (VK 0xB9) to win the foreground
/// permission it then hands to the application a pattern acts on, so a window behind came to the front and the key
/// landed in the person's window. The worker takes SendInput (and the hotkey registration the client waits on) out of
/// UIAutomationCore's import table: its input is dropped, and the hotkey message the client waits for after it is
/// posted instead (no 2 s wait). The class is taken from the worker's text and run in a PowerShell of its own with the
/// client loaded; no window is read, shown or touched, and nothing reaches the screen.
/// </summary>
[TestFixture]
public sealed class UiaQuietInputTests
{
    private const string Prelude = """
        $ErrorActionPreference='Stop'
        $text=[IO.File]::ReadAllText($env:BAXY_QUIET_WORKER)
        $start=$text.IndexOf('# BEGIN BaxyUiaQuietInput'); $end=$text.IndexOf('# END BaxyUiaQuietInput')
        if($start -lt 0 -or $end -lt $start){ throw 'quiet input block missing' }
        $block=$text.Substring($start,$end-$start)
        $code=$block.Substring($block.IndexOf("@'")+3); $code=$code.Substring(0,$code.LastIndexOf("'@"))
        Add-Type -TypeDefinition $code
        Add-Type -AssemblyName UIAutomationClient
        $null=[System.Windows.Automation.AutomationElement]::RootElement
        Add-Type -TypeDefinition @'
        using System; using System.Runtime.InteropServices;
        public static class QuietProbe {
          [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr GetModuleHandle(string name);
          [StructLayout(LayoutKind.Sequential)] public struct LastInput { public uint Size; public uint Tick; }
          [DllImport("user32.dll")] private static extern bool GetLastInputInfo(ref LastInput info);
          [StructLayout(LayoutKind.Sequential)] public struct Msg { public IntPtr Hwnd; public uint Message; public IntPtr WParam; public IntPtr LParam; public uint Time; public int X; public int Y; }
          [DllImport("user32.dll")] public static extern bool PeekMessage(out Msg msg, IntPtr hwnd, uint first, uint last, uint remove);
          // The slots hold the worker's own delegates: .NET Framework hands back the delegate of its own type.
          public static Type SendType; public static Type RegisterType; public static Type UnregisterType;
          private static object Call(IntPtr slot, Type type, params object[] values) {
            return Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(slot),type).DynamicInvoke(values);
          }
          public static uint LastInputTick() { LastInput info=new LastInput(); info.Size=8; GetLastInputInfo(ref info); return info.Tick; }
          // One key (down or up) as the client sends it: INPUT_KEYBOARD, no mark.
          public static uint SendKey(IntPtr slot, ushort key, bool up) {
            IntPtr input=Marshal.AllocHGlobal(40);
            try {
              for(int i=0;i<40;i++) Marshal.WriteByte(input,i,0);
              Marshal.WriteInt32(input,0,1); Marshal.WriteInt16(input,8,(short)key); Marshal.WriteInt32(input,12,up?2:0);
              return (uint)Call(slot,SendType,(uint)1,input,40);
            } finally { Marshal.FreeHGlobal(input); }
          }
          // A whole call of several inputs: type 0 is a mouse event, type 1 a key down. The mouse event is a one-pixel move
          // with the test's own dwExtraInfo (0x51554945): low-level hooks never see a zero move, and the mark tells it from
          // another program's mouse. The client's net refuses any mouse event whole.
          public static uint SendMany(IntPtr slot, uint[] types, ushort[] keys) {
            IntPtr input=Marshal.AllocHGlobal(40*types.Length);
            try {
              for(int i=0;i<40*types.Length;i++) Marshal.WriteByte(input,i,0);
              for(int k=0;k<types.Length;k++){
                Marshal.WriteInt32(input,40*k,(int)types[k]);
                if(types[k]==1) Marshal.WriteInt16(input,40*k+8,(short)keys[k]);
                else { Marshal.WriteInt32(input,40*k+8,1); Marshal.WriteInt32(input,40*k+20,1); Marshal.WriteInt64(input,40*k+32,0x51554945); }
              }
              return (uint)Call(slot,SendType,(uint)types.Length,input,40);
            } finally { Marshal.FreeHGlobal(input); }
          }
          public static bool RegisterThrough(IntPtr slot, int id, uint modifiers, uint key) {
            return (bool)Call(slot,RegisterType,IntPtr.Zero,id,modifiers,key);
          }
          public static Type WaitType; public static Type GetMessageType;
          public static uint WaitThrough(IntPtr slot, uint milliseconds, uint mask) {
            return (uint)Call(slot,WaitType,(uint)0,IntPtr.Zero,false,milliseconds,mask);
          }
          // Only when a message is owed: the real GetMessage would block.
          public static string GetThrough(IntPtr slot) {
            IntPtr msg=Marshal.AllocHGlobal(48);
            try {
              int got=(int)Call(slot,GetMessageType,msg,IntPtr.Zero,(uint)0,(uint)0);
              if(got!=1) return "none";
              return Marshal.ReadInt32(msg,8).ToString("X")+":"+Marshal.ReadInt64(msg,16).ToString("X");
            } finally { Marshal.FreeHGlobal(msg); }
          }
          public static bool UnregisterThrough(IntPtr slot, int id) {
            return (bool)Call(slot,UnregisterType,IntPtr.Zero,id);
          }
        }
        '@
        $core=[QuietProbe]::GetModuleHandle('UIAutomationCore.dll')
        [QuietProbe]::SendType=[BaxyUiaQuietInput+SendInputCall]
        [QuietProbe]::RegisterType=[BaxyUiaQuietInput+RegisterHotKeyCall]
        [QuietProbe]::UnregisterType=[BaxyUiaQuietInput+UnregisterHotKeyCall]
        [QuietProbe]::WaitType=[BaxyUiaQuietInput+MsgWaitCall]
        [QuietProbe]::GetMessageType=[BaxyUiaQuietInput+GetMessageCall]

        """;

    // The session's input as it reaches the system, seen by low-level hooks on a thread of their own: a key of the
    // test's reserved codes or a mouse event carrying the test's dwExtraInfo is the test's (Ours); anything else is
    // another source.
    private const string Watch = """
        Add-Type -TypeDefinition @'
        using System; using System.Runtime.InteropServices; using System.Threading;
        public static class QuietWatch {
          private delegate IntPtr HookProc(int code, IntPtr w, IntPtr l);
          [DllImport("user32.dll", SetLastError=true)] private static extern IntPtr SetWindowsHookEx(int id, HookProc proc, IntPtr module, uint thread);
          [DllImport("user32.dll")] private static extern bool UnhookWindowsHookEx(IntPtr hook);
          [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr w, IntPtr l);
          [StructLayout(LayoutKind.Sequential)] private struct Msg { public IntPtr Hwnd; public uint Message; public IntPtr WParam; public IntPtr LParam; public uint Time; public int X; public int Y; }
          [DllImport("user32.dll")] private static extern int GetMessage(out Msg msg, IntPtr hwnd, uint first, uint last);
          [DllImport("user32.dll")] private static extern bool PostThreadMessage(uint thread, uint msg, IntPtr w, IntPtr l);
          [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
          [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] private static extern IntPtr GetModuleHandle(string name);
          public static int Ours; public static int Others; public static int OursMouse;
          private static HookProc keys; private static HookProc mouse; private static uint hookThread; private static Thread loop;
          private static IntPtr Key(int code, IntPtr w, IntPtr l) {
            if(code>=0){ int vk=Marshal.ReadInt32(l,0); if(vk==0xB8||vk==0xB9) Interlocked.Increment(ref Ours); else Interlocked.Increment(ref Others); }
            return CallNextHookEx(IntPtr.Zero,code,w,l);
          }
          private static IntPtr Mouse(int code, IntPtr w, IntPtr l) {
            if(code>=0){ if(Marshal.ReadInt64(l,24)==0x51554945){ Interlocked.Increment(ref Ours); Interlocked.Increment(ref OursMouse); } else Interlocked.Increment(ref Others); }
            return CallNextHookEx(IntPtr.Zero,code,w,l);
          }
          public static bool Start() {
            bool installed=false; ManualResetEvent ready=new ManualResetEvent(false);
            keys=Key; mouse=Mouse;
            loop=new Thread(() => {
              hookThread=GetCurrentThreadId();
              IntPtr module=GetModuleHandle(null);
              IntPtr k=SetWindowsHookEx(13,keys,module,0); IntPtr m=SetWindowsHookEx(14,mouse,module,0);
              installed=(k!=IntPtr.Zero && m!=IntPtr.Zero); ready.Set();
              Msg msg; while(installed && GetMessage(out msg,IntPtr.Zero,0,0)>0) { }
              if(k!=IntPtr.Zero) UnhookWindowsHookEx(k); if(m!=IntPtr.Zero) UnhookWindowsHookEx(m);
            });
            loop.IsBackground=true; loop.Start(); ready.WaitOne(5000);
            return installed;
          }
          public static void Stop() { PostThreadMessage(hookThread,0x12,IntPtr.Zero,IntPtr.Zero); loop.Join(5000); }
        }
        '@

        """;

    [Test]
    public void TheClientsSendInputIsTakenAndGivenBack()
    {
        string answer = Run("""
            $slots=@([BaxyUiaQuietInput]::FindSlots($core,'SendInput'))
            $before=@($slots | ForEach-Object { [BaxyUiaQuietInput]::Read($_) })
            $state=[BaxyUiaQuietInput]::Install('UIAutomationCore.dll')
            $again=[BaxyUiaQuietInput]::Install('UIAutomationCore.dll')
            $during=@($slots | ForEach-Object { [BaxyUiaQuietInput]::Read($_) })
            [BaxyUiaQuietInput]::Restore()
            $after=@($slots | ForEach-Object { [BaxyUiaQuietInput]::Read($_) })
            $changed=@(0..($slots.Count-1) | Where-Object { $before[$_] -ne $during[$_] }).Count
            $restored=@(0..($slots.Count-1) | Where-Object { $before[$_] -eq $after[$_] }).Count
            [Console]::Out.Write(('{0}|{1}|{2}|{3}|{4}|{5}' -f ($slots.Count -gt 0),$state,$again,($changed -eq $slots.Count),($restored -eq $slots.Count),[BaxyUiaQuietInput]::State))
            """);
        Assert.That(answer, Is.EqualTo("True|on|on|True|True|off"),
            "found in the client's imports, replaced once, every slot back after Restore");
    }

    [Test]
    public void AModuleThatIsNotLoadedIsLeftAlone()
    {
        // Counter-case: before the client is loaded there is nothing to take, and nothing else is touched.
        string answer = Run("""
            $state=[BaxyUiaQuietInput]::Install('BaxyNoSuchModule.dll')
            [Console]::Out.Write(('{0}|{1}' -f $state,@([BaxyUiaQuietInput]::FindSlots([IntPtr]::Zero,'SendInput')).Count))
            """);
        Assert.That(answer, Is.EqualTo("absent|0"));
    }

    [Test]
    public void TheClientsKeyNeverReachesTheScreenAndItsWaitIsAnswered()
    {
        // Through the client's own slots: a hotkey registered by it, then its unmarked key. The key is dropped (the
        // system's last-input tick does not move); the client's wait for the hotkey ends at once and its read gets the
        // WM_HOTKEY (measured live: a message posted to the queue behind an older one was read late, a 2 s wait).
        // Counter-cases (review of 1b9b736e7): only that measured key is dropped as sent. A key the client never
        // registered, a key after unregistering, a mouse event, or a call that mixes the hotkey's key with another
        // input is refused whole: nothing is sent, the call answers 0 (the caller sees the failure, never a press that
        // did not happen), nothing is owed and the wait times out. Ctrl+Alt+Shift keeps a real press of the key on the
        // desktop out of this thread.
        // Full of 6d554a246 on redpc: a person using the PC moves the last-input tick too, so an unchanged tick alone
        // failed the test with nothing of it on the screen. Low-level hooks of the session's input (a thread of their
        // own) tell the sources apart: the test's input is a key of the two reserved codes (0xB8, 0xB9) or a mouse
        // event with the test's dwExtraInfo, and none may arrive; a tick that moved passes only when the hooks saw input
        // of another source (counter-case: a moved tick nothing explains still fails).
        string answer = Run(Watch + """
            if(-not [QuietWatch]::Start()){ throw 'input hooks not installed' }
            [void][BaxyUiaQuietInput]::Install('UIAutomationCore.dll')
            $send=@([BaxyUiaQuietInput]::FindSlots($core,'SendInput'))[0]
            $register=@([BaxyUiaQuietInput]::FindSlots($core,'RegisterHotKey'))[0]
            $unregister=@([BaxyUiaQuietInput]::FindSlots($core,'UnregisterHotKey'))[0]
            $wait=@([BaxyUiaQuietInput]::FindSlots($core,'MsgWaitForMultipleObjects'))[0]
            $get=@([BaxyUiaQuietInput]::FindSlots($core,'GetMessageW'))[0]
            $tick=[QuietProbe]::LastInputTick()
            $other=[QuietProbe]::SendKey($send,0xB8,$false)
            $none=[QuietProbe]::WaitThrough($wait,50,0x80)
            $registered=[QuietProbe]::RegisterThrough($register,0x4242,0x7,0xB9)
            $down=[QuietProbe]::SendKey($send,0xB9,$false)
            $up=[QuietProbe]::SendKey($send,0xB9,$true)
            $clock=[Diagnostics.Stopwatch]::StartNew()
            $woke=[QuietProbe]::WaitThrough($wait,2000,0x1cff)
            $fast=($clock.ElapsedMilliseconds -lt 500)
            $read=[QuietProbe]::GetThrough($get)
            $again=[QuietProbe]::WaitThrough($wait,50,0x80)
            [void][QuietProbe]::UnregisterThrough($unregister,0x4242)
            $mouse=[QuietProbe]::SendMany($send,[uint32[]]@(0),[uint16[]]@(0))
            $mixed=[QuietProbe]::SendMany($send,[uint32[]]@(1,1),[uint16[]]@(0xB9,0xB8))
            $mixedWait=[QuietProbe]::WaitThrough($wait,50,0x80)
            [void][QuietProbe]::UnregisterThrough($unregister,0x4242)
            $afterUnregister=[QuietProbe]::SendKey($send,0xB9,$false)
            $late=[QuietProbe]::WaitThrough($wait,50,0x80)
            Start-Sleep -Milliseconds 150
            $moved=([QuietProbe]::LastInputTick() -ne $tick)
            [QuietWatch]::Stop()
            $still=(([QuietWatch]::Ours -eq 0) -and ((-not $moved) -or ([QuietWatch]::Others -gt 0)))
            [BaxyUiaQuietInput]::Restore()
            [Console]::Error.Write(('moved={0} ours={1} (mouse {2}) others={3}' -f $moved,[QuietWatch]::Ours,[QuietWatch]::OursMouse,[QuietWatch]::Others))
            [Console]::Out.Write(('{0}|{1:X}|{2}|{3}{4}|{5}|{6}|{7}|{8:X}|{9}{10}{11:X}|{12}{13:X}|{14}|{15}|{16}|{17}' -f $other,$none,$registered,$down,$up,$woke,$fast,$read,$again,$mouse,$mixed,$mixedWait,$afterUnregister,$late,$still,[BaxyUiaQuietInput]::Dropped,[BaxyUiaQuietInput]::Refused,[BaxyUiaQuietInput]::Answered))
            """);
        Assert.That(answer, Is.EqualTo("0|102|True|11|0|True|312:4242|102|00102|0102|True|2|4|1"),
            "the hotkey's keys dropped, the wait answered at once and the hotkey read once; anything else refused whole");
    }

    [Test]
    public void OnlyTheTargetsFamilyTakingThePersonsFrontIsGivenBack()
    {
        // Fix c: the net acts on the target's window, a window it owns or a process of its family (an application
        // hosted in a frame of another process); never when the target was already in front, when nothing was, or
        // when the front goes to a stranger or back to the person (counter-cases).
        string answer = Run("""
            $person=[IntPtr]100; $top=[IntPtr]200; $family=[uint32[]]@(7,9)
            $cases=@(
              @($person,$top,$family,[IntPtr]200,[uint32]7,[IntPtr]::Zero),
              @($person,$top,$family,[IntPtr]300,[uint32]9,[IntPtr]::Zero),
              @($person,$top,$family,[IntPtr]301,[uint32]5,$top),
              @($person,$top,$family,[IntPtr]302,[uint32]5,[IntPtr]::Zero),
              @($person,$top,$family,$person,[uint32]7,[IntPtr]::Zero),
              @($top,$top,$family,[IntPtr]200,[uint32]7,[IntPtr]::Zero),
              @([IntPtr]::Zero,$top,$family,[IntPtr]200,[uint32]7,[IntPtr]::Zero),
              @($person,[IntPtr]::Zero,$family,[IntPtr]200,[uint32]7,[IntPtr]::Zero)
            )
            $answers=foreach($c in $cases){ [BaxyFrontKeeper]::IsTheft($c[0],$c[1],$c[2],$c[3],$c[4],$c[5]) }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer, Is.EqualTo("True,True,True,False,False,False,False,False"));
    }

    [Test]
    public void TheTargetGoesBelowThePersonOnlyWhenTheFrontIsTheirsAgain()
    {
        // Review of 1b9b736e7: a return that failed left the target active (it has the keyboard) but drawn under the
        // person's window, so their typing went to a window they could not see. The order changes only when the front
        // read after the return is the person's window or a child of it (counter-cases: still the target, nothing,
        // nobody to return to).
        string answer = Run("""
            $person=[IntPtr]100; $target=[IntPtr]200
            $cases=@(
              @($person,$person,$person),
              @($person,[IntPtr]101,$person),
              @($person,$target,$target),
              @($person,[IntPtr]::Zero,[IntPtr]::Zero),
              @([IntPtr]::Zero,[IntPtr]::Zero,[IntPtr]::Zero)
            )
            $answers=foreach($c in $cases){ [BaxyFrontKeeper]::MayLower($c[0],$c[1],$c[2]) }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer, Is.EqualTo("True,True,False,False,False"));
    }

    [Test]
    public void APersonsClickOrFrontKeyIsTheirsAndTypingIsNot()
    {
        // Review of 1b9b736e7: the net must never take back a front the person moved themselves (a click on the target,
        // Alt+Tab, Win, Esc, Enter, a function key). Counter-cases: typing a letter, a key released, a mouse move, and
        // the same click or key carrying BAXY's mark are not the person moving the front.
        string answer = Run("""
            $mark=[uint32]0x42415859
            $cases=@(
              @($true,[uint16]0x0001,[uint16]0,[uint16]0,[uint32]0),
              @($true,[uint16]0x0004,[uint16]0,[uint16]0,[uint32]0x53494D55),
              @($false,[uint16]0,[uint16]0x12,[uint16]0,[uint32]0),
              @($false,[uint16]0,[uint16]0x09,[uint16]0,[uint32]0),
              @($false,[uint16]0,[uint16]0x5B,[uint16]0,[uint32]0),
              @($false,[uint16]0,[uint16]0x73,[uint16]0,[uint32]0),
              @($false,[uint16]0,[uint16]0x41,[uint16]0,[uint32]0),
              @($false,[uint16]0,[uint16]0x12,[uint16]1,[uint32]0),
              @($true,[uint16]0x0002,[uint16]0,[uint16]0,[uint32]0),
              @($true,[uint16]0,[uint16]0,[uint16]0,[uint32]0),
              @($true,[uint16]0x0001,[uint16]0,[uint16]0,$mark),
              @($false,[uint16]0,[uint16]0x12,[uint16]0,$mark)
            )
            $answers=foreach($c in $cases){ [BaxyFrontKeeper]::IsPersonsMove($c[0],$c[1],$c[2],$c[3],$c[4]) }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer, Is.EqualTo("True,True,True,True,True,True,False,False,False,False,False,False"));
    }

    [Test]
    public void AFrontBaxysOwnLeaseBroughtUpIsNotFought()
    {
        // Review of 1b9b736e7: inside the tail, the adapter's lease brings the target up on purpose (pointer, wheel or
        // keyboard) and the net took it back, so the lease's input fell in the person's window. The lease says which
        // window it brings up and when (LeaseFrontSignal); that front, said recently, is never fought. Counter-cases:
        // nothing said, said long ago, another window.
        string answer = Run("""
            $target=[IntPtr]200; $child=[IntPtr]201; $other=[IntPtr]300
            $cases=@(
              @($target,[long]10,$target,$target,$target),
              @($child,[long]10,$target,$target,$target),
              @($target,[long]10,$target,$other,$target),
              @([IntPtr]::Zero,[long]10,[IntPtr]::Zero,$target,$target),
              @($target,[long]5000,$target,$target,$target),
              @($other,[long]10,$other,$target,[IntPtr]400)
            )
            $answers=foreach($c in $cases){ [BaxyFrontKeeper]::IsLeaseFront($c[0],$c[1],$c[2],$c[3],$c[4]) }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer, Is.EqualTo("True,True,True,False,False,False"));
    }

    [Test]
    public void TheLeaseWritesWhatTheNetReads()
    {
        string text = File.ReadAllText(WorkerPath());
        LeaseFrontSignal.Mark(0x1234);
        using var block = System.IO.MemoryMappedFiles.MemoryMappedFile.OpenExisting(LeaseFrontSignal.Name);
        using var view = block.CreateViewAccessor(0, 16);
        long age = Environment.TickCount64 - view.ReadInt64(8);
        Assert.Multiple(() =>
        {
            Assert.That(text, Does.Contain("public const string LeaseBlock = @\"" + LeaseFrontSignal.Name + "\";"), "same block");
            Assert.That(view.ReadInt64(0), Is.EqualTo(0x1234), "the window first");
            Assert.That(age, Is.InRange(0, 1000), "then when, on the same clock");
        });
    }

    [Test]
    public void TheNetHoldsItsBidKeyWithEveryModifier()
    {
        // The net wins the right to give the front back as the client does: a marked press of a hotkey of its own thread
        // (UiaSinFrenteLiveCheck: neither the person's window nor the target's gets a keyboard message). Here only the
        // registration is checked, nothing is pressed: once the net's thread runs, its key is one with no keyboard, and
        // another thread can no longer take it, bare or with a modifier the person might hold (Shift, Ctrl+Alt, Win).
        // Counter-case: a key of the list the net did not take is still free.
        string answer = Run("""
            Add-Type -TypeDefinition @'
            using System; using System.Runtime.InteropServices;
            public static class BidProbe {
              [DllImport("user32.dll")] public static extern bool RegisterHotKey(IntPtr hwnd, int id, uint modifiers, uint key);
              [DllImport("user32.dll")] public static extern bool UnregisterHotKey(IntPtr hwnd, int id);
            }
            '@
            [BaxyFrontKeeper]::Begin([IntPtr]::Zero)
            [BaxyFrontKeeper]::End($false)
            $key=[BaxyFrontKeeper]::BidKey
            $listed=@([BaxyFrontKeeper]::BidKeys) -contains $key
            $taken=foreach($m in 0,4,3,8){ [BidProbe]::RegisterHotKey([IntPtr]::Zero,0x0101+$m,$m,$key) }
            $free=[uint32]@([BaxyFrontKeeper]::BidKeys | Where-Object { $_ -ne $key })[-1]
            $other=[BidProbe]::RegisterHotKey([IntPtr]::Zero,0x0200,0,$free)
            if($other){ [void][BidProbe]::UnregisterHotKey([IntPtr]::Zero,0x0200) }
            [Console]::Out.Write(('{0}|{1}|{2}' -f $listed,(@($taken) -join ','),$other))
            """);
        Assert.That(answer, Is.EqualTo("True|False,False,False,False|True"));
    }

    [Test]
    public void TheTailFollowsOnlyAPatternThatActed()
    {
        // Review of 1b9b736e7: a tail after an answer that acted on nothing collided with the adapter's fallback (the
        // pointer, the wheel, the keyboard), whose lease takes the front on purpose and was fought back. The tail is
        // armed only after a press, a choice, a toggle, a value written, a scroll that moved or an element revealed.
        // Counter-cases: no pattern at a point, no ScrollPattern, SetValue refused, a click that needs the pointer, an
        // expand (its menu closes when the window loses the activation), a scroll that did not move, «already» seen.
        string answer = Run(Functions + """
            $cases=@(
              @{ method='invoke' }, @{ method='select' }, @{ method='toggle' }, @{ method='legacy' }, @{ method='message' },
              @{ method='setvalue'; delivered=$true }, @{ ok=$true; scrolled=$true }, @{ ok=$true; method='scroll'; revealed=$true },
              @{ ok=$false; error='visible_point_no_pattern' }, @{ ok=$false; error='scroll_pattern_unavailable' },
              @{ ok=$false; error='field_setvalue_refused'; method='' }, @{ method='pointer' }, @{ method='expand' },
              @{ ok=$true; scrolled=$false }, @{ ok=$true; method='already'; revealed=$false }, $null
            )
            $answers=foreach($c in $cases){ Test-ActedByPattern $c }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer, Is.EqualTo(
            "True,True,True,True,True,True,True,True,False,False,False,False,False,False,False,False"));
    }

    [Test]
    public void EachCommandCarriesWhatTheNetSawForTheAnnoyanceMeter()
    {
        // Review of 1b9b736e7: the returns were global counters only the ping told, so a front taken and given back
        // (or never given back) counted as zero annoyance. The command under the watch carries its own report: a front
        // returned is still a change, a failed return is a change not restored. Counter-case: nothing taken, nothing
        // added.
        string answer = Run(Functions + """
            [BaxyFrontKeeper]::WatchTaken=0
            $quiet=Add-FrontReport @{ ok=$true }
            [BaxyFrontKeeper]::WatchTaken=1; [BaxyFrontKeeper]::WatchFailed=0; [BaxyFrontKeeper]::WatchLongestMs=4
            $back=Add-FrontReport @{ ok=$true }
            [BaxyFrontKeeper]::WatchTaken=2; [BaxyFrontKeeper]::WatchFailed=1
            $kept=Add-FrontReport @{ ok=$true }
            [Console]::Out.Write(('{0}|{1}{2}{3}{4}|{5}{6}{7}' -f $quiet.ContainsKey('frontChanged'),$back.frontChanged,$back.frontRestored,$back.frontReturnFailed,$back.frontReturnMs,$kept.frontChanged,$kept.frontRestored,$kept.frontReturnFailed))
            """);
        Assert.That(answer, Is.EqualTo("False|TrueTrue04|TrueFalse1"));
    }

    [Test]
    public void TheCommandsThatActRunUnderTheNet()
    {
        string text = File.ReadAllText(WorkerPath());
        Assert.Multiple(() =>
        {
            foreach (string command in new[] { "Do-Click", "Do-At", "Do-Scroll", "Do-Field", "Do-Focus", "Do-Reveal" })
                Assert.That(text, Does.Contain("Invoke-Kept $request { param($r) " + command + " $r }"), command);
            Assert.That(text, Does.Contain("Send-Line (Add-FrontReport (Do-Postread $request))"),
                "the post-read carries the watch's report too: the tail ends after the command's answer");
            Assert.That(text, Does.Not.Contain("Invoke-Kept $request { param($r) Do-View"), "a view never acts");
        });
    }

    // The worker's own functions for the tail and the report, taken from its text (they use the keeper's statics).
    private const string Functions = """
        $start=$text.IndexOf('$script:KeptMethods='); $end=$text.IndexOf('function Invoke-Kept(')
        if($start -lt 0 -or $end -lt $start){ throw 'tail functions missing' }
        Invoke-Expression $text.Substring($start,$end-$start)

        """;

    [Test]
    public void TheWorkerTakesTheClientsInputOnceTheClientIsLoaded()
    {
        string worker = WorkerPath();
        string text = File.ReadAllText(worker);
        int loaded = text.IndexOf("$null=$AE::RootElement", StringComparison.Ordinal);
        int install = text.IndexOf("[BaxyUiaQuietInput]::Install('UIAutomationCore.dll')", StringComparison.Ordinal);
        int loop = text.IndexOf("while($true){", StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(loaded, Is.GreaterThan(0));
            Assert.That(install, Is.GreaterThan(loaded), "installed after the client is loaded (before, it is absent)");
            Assert.That(install, Is.LessThan(loop), "installed before the first command");
            Assert.That(text, Does.Contain("quietInput=$script:QuietInput"), "the ping says whether it is on");
        });
    }

    private static string WorkerPath()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    private static string Run(string body)
    {
        string worker = WorkerPath();
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(Prelude + body)));
        start.Environment["BAXY_QUIET_WORKER"] = worker;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        if (error.Result.Length > 0)
            TestContext.Out.WriteLine(error.Result);
        return output.Trim();
    }
}
