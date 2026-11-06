using System.Diagnostics;
using System.Globalization;
using System.Text;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// A real top-level window of a process of its own whose thread can stop pumping on command, the shape of agent-desktop's
/// StalledFixture (<c>window\window_op_tests.rs:232-252</c>) and <c>P/18-actionability/probe_window.rs</c>: the message loop
/// handles «stall» by blocking in the window procedure, without pumping, until «resume». It has one button («Aceptar») and
/// counts what reached it, so «nothing was sent» can be read back after it resumes. With <c>cell</c> it adjusts its own
/// size to multiples of that many pixels, as a terminal's character cells do: at once in WM_WINDOWPOSCHANGING or, with
/// <c>adjustAfterMs</c>, by itself that long after a move. With <c>visible: false</c> nothing shows, for the suites. Closed
/// by its process id, never by name.
/// </summary>
internal sealed class StallingWindow : IDisposable
{
    private const string Source = """
        using System;
        using System.Runtime.InteropServices;
        using System.Threading;
        public static class StallingWindowHost {
          delegate IntPtr Proc(IntPtr h, uint m, IntPtr w, IntPtr l);
          [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] struct WndClass { public uint style; public Proc proc; public int a; public int b; public IntPtr inst; public IntPtr icon; public IntPtr cursor; public IntPtr bg; public string menu; public string name; }
          [StructLayout(LayoutKind.Sequential)] struct WinPos { public IntPtr hwnd; public IntPtr after; public int x; public int y; public int cx; public int cy; public uint flags; }
          [StructLayout(LayoutKind.Sequential)] struct Msg { public IntPtr h; public uint m; public IntPtr w; public IntPtr l; public uint t; public int x; public int y; }
          [StructLayout(LayoutKind.Sequential)] struct Rc { public int l; public int t; public int r; public int b; }
          [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern ushort RegisterClassW(ref WndClass c);
          [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr CreateWindowExW(uint ex, string cls, string title, uint style, int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr inst, IntPtr p);
          [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr DefWindowProcW(IntPtr h, uint m, IntPtr w, IntPtr l);
          [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetMessageW(out Msg m, IntPtr h, uint a, uint b);
          [DllImport("user32.dll")] static extern bool TranslateMessage(ref Msg m);
          [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr DispatchMessageW(ref Msg m);
          [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern bool PostMessageW(IntPtr h, uint m, IntPtr w, IntPtr l);
          [DllImport("user32.dll")] static extern void PostQuitMessage(int code);
          [DllImport("user32.dll")] static extern IntPtr SetTimer(IntPtr h, IntPtr id, uint ms, IntPtr f);
          [DllImport("user32.dll")] static extern bool KillTimer(IntPtr h, IntPtr id);
          [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out Rc r);
          [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int t, uint flags);
          [DllImport("user32.dll")] static extern bool ReplyMessage(IntPtr result);
          [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern IntPtr GetModuleHandleW(string n);
          const uint Stall=0x8001, Quit=0x8002, WinPosChanging=0x46, WinPosChanged=0x47, Timer=0x113, Destroy=2, Command=0x111, KeyDown=0x100, ButtonDown=0x201;
          static readonly ManualResetEvent Ready=new ManualResetEvent(false), Stalled=new ManualResetEvent(false), Released=new ManualResetEvent(false);
          static Proc keep; static int cell, after, answers=-1; public static IntPtr Handle; public static int Commands, Keys, Presses;
          static int Snap(int v){ return v-v%cell; }
          static IntPtr Wnd(IntPtr h, uint m, IntPtr w, IntPtr l){
            if(m==Stall){ Stalled.Set(); Released.WaitOne(); return IntPtr.Zero; }
            // Answers this many WM_NULL and stops on the next one, having answered it (fixture_hung_after_probe.rs:27-52).
            if(m==0 && answers>=0 && answers--==0){ answers=-1; ReplyMessage(IntPtr.Zero); Stalled.Set(); Released.WaitOne(); return IntPtr.Zero; }
            if(m==Command){ Commands++; return IntPtr.Zero; }
            if(m==WinPosChanging && cell>0 && after==0){
              WinPos p=(WinPos)Marshal.PtrToStructure(l,typeof(WinPos));
              if((p.flags&1)==0){ p.cx=Snap(p.cx); p.cy=Snap(p.cy); Marshal.StructureToPtr(p,l,false); }
            }
            if(m==WinPosChanged && cell>0 && after>0){
              WinPos p=(WinPos)Marshal.PtrToStructure(l,typeof(WinPos));
              if((p.flags&1)==0 && (p.cx%cell!=0 || p.cy%cell!=0)) SetTimer(h,(IntPtr)1,(uint)after,IntPtr.Zero);
            }
            if(m==Timer){
              KillTimer(h,(IntPtr)1); Rc r; GetWindowRect(h,out r);
              SetWindowPos(h,IntPtr.Zero,0,0,Snap(r.r-r.l),Snap(r.b-r.t),0x0002|0x0004|0x0010);
              return IntPtr.Zero;
            }
            if(m==Destroy){ PostQuitMessage(0); return IntPtr.Zero; }
            return DefWindowProcW(h,m,w,l);
          }
          public static void Start(string title,int x,int y,int width,int height,int snapCell,int adjustAfter,bool visible,string windowClass){
            cell=snapCell; after=adjustAfter;
            var thread=new Thread(()=>{
              keep=Wnd; IntPtr inst=GetModuleHandleW(null); string name=windowClass ?? "BaxyStallingWindow"+Guid.NewGuid().ToString("N");
              var c=new WndClass{ proc=keep, inst=inst, bg=(IntPtr)6, name=name }; RegisterClassW(ref c);
              Handle=CreateWindowExW(0,name,title,visible?0x10CF0000u:0x00CF0000u,x,y,width,height,IntPtr.Zero,IntPtr.Zero,inst,IntPtr.Zero);
              CreateWindowExW(0,"BUTTON","Aceptar",0x50010000,20,20,120,36,Handle,IntPtr.Zero,inst,IntPtr.Zero);
              Ready.Set(); Msg msg;
              while(GetMessageW(out msg,IntPtr.Zero,0,0)>0){
                if(msg.m==KeyDown) Keys++;
                if(msg.m==ButtonDown) Presses++;
                TranslateMessage(ref msg); DispatchMessageW(ref msg);
              }
            });
            thread.IsBackground=true; thread.SetApartmentState(ApartmentState.MTA); thread.Start(); Ready.WaitOne();
          }
          public static void StopPumping(){ PostMessageW(Handle,Stall,IntPtr.Zero,IntPtr.Zero); Stalled.WaitOne(); }
          public static void Resume(){ Released.Set(); Stalled.Reset(); Released.Reset(); }
          public static void Close(){ PostMessageW(Handle,0x10,IntPtr.Zero,IntPtr.Zero); }
          // --exit <code> [ms]: ends with that code, after that long. --launcher <args>: starts itself with those args, says
          // the child's process id and ends cleanly, as a launcher does while its child owns the window. Otherwise: the
          // window, then one command per line on stdin (its end ends it; with «hold» as the tenth argument, a while later).
          public static int Main(string[] a){
            if(a.Length>=2 && a[0]=="--exit"){ if(a.Length>2) Thread.Sleep(int.Parse(a[2])); return unchecked((int)Convert.ToUInt32(a[1],16)); }
            if(a.Length>1 && a[0]=="--launcher"){
              var line=new System.Text.StringBuilder();
              for(int i=1;i<a.Length;i++) line.Append('"').Append(a[i]).Append("\" ");
              var info=new System.Diagnostics.ProcessStartInfo(System.Reflection.Assembly.GetEntryAssembly().Location,line.ToString());
              info.UseShellExecute=false; Console.Out.WriteLine(System.Diagnostics.Process.Start(info).Id); Console.Out.Flush(); return 0;
            }
            Start(a[0],int.Parse(a[1]),int.Parse(a[2]),int.Parse(a[3]),int.Parse(a[4]),int.Parse(a[5]),int.Parse(a[6]),a[7]=="1",a.Length>8?a[8]:null);
            Console.Out.WriteLine(Handle.ToInt64()); Console.Out.Flush();
            while(true){
              string s=Console.In.ReadLine();
              if(s==null && a.Length>9 && a[9]=="hold"){ Thread.Sleep(20000); return 0; }
              if(s==null || s=="exit") return 0;
              if(s=="stall") StopPumping(); else if(s=="resume") Resume(); else if(s=="close") Close(); else if(s=="answer0") answers=0;
              Console.Out.WriteLine(Keys+" "+Presses+" "+Commands); Console.Out.Flush();
            }
          }
        }
        """;

    private readonly Process _process;

    private StallingWindow(Process process, nint handle, string title)
    {
        _process = process;
        Handle = handle;
        Title = title;
    }

    internal nint Handle { get; }

    internal string Title { get; }

    internal int ProcessId => _process.Id;

    private static readonly Lazy<string> Program = new(Compile);

    /// <summary>The compiled helper, a program of its own name (a console host's name is a protected window's).</summary>
    internal static string ProgramPath => Program.Value;

    private static string Compile()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-stalling-" + Environment.ProcessId.ToString(CultureInfo.InvariantCulture));
        Directory.CreateDirectory(folder);
        AppDomain.CurrentDomain.ProcessExit += (_, _) =>
        {
            try
            {
                Directory.Delete(folder, recursive: true);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
        };
        string source = Path.Combine(folder, "host.cs");
        string program = Path.Combine(folder, "baxyventanacongelada.exe");
        File.WriteAllText(source, Source, Encoding.UTF8);
        var start = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        foreach (string argument in new[]
        {
            "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
            $"Add-Type -TypeDefinition ([IO.File]::ReadAllText('{source}')) -OutputAssembly '{program}' -OutputType ConsoleApplication",
        })
        {
            start.ArgumentList.Add(argument);
        }

        using Process compiler = Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        Task<string> reading = compiler.StandardError.ReadToEndAsync();
        if (!compiler.WaitForExit(120_000) || !reading.Wait(TimeSpan.FromSeconds(10)))
        {
            compiler.Kill(entireProcessTree: true);
            throw new TimeoutException("the helper's compile did not end");
        }

        string errors = reading.Result;
        return File.Exists(program) ? program : throw new InvalidOperationException($"the helper did not compile: {errors}");
    }

    internal static StallingWindow Open(
        string? title = null, int x = 200, int y = 200, int width = 640, int height = 400, int cell = 0, int adjustAfterMs = 0,
        bool visible = true, string? windowClass = null)
    {
        title ??= "Prueba congelada " + Guid.NewGuid().ToString("N")[..8];
        var start = new ProcessStartInfo(ProgramPath)
        {
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[]
        {
            title, Number(x), Number(y), Number(width), Number(height), Number(cell), Number(adjustAfterMs), visible ? "1" : "0",
        })
        {
            start.ArgumentList.Add(argument);
        }

        if (windowClass is not null)
            start.ArgumentList.Add(windowClass);
        Process process = Process.Start(start) ?? throw new InvalidOperationException("the helper did not start");
        process.ErrorDataReceived += (_, _) => { };
        process.BeginErrorReadLine();
        string? line = process.StandardOutput.ReadLine();
        if (!long.TryParse(line, NumberStyles.Integer, CultureInfo.InvariantCulture, out long handle) || handle == 0)
        {
            process.Kill(entireProcessTree: false);
            process.Dispose();
            throw new InvalidOperationException($"the stalling window did not open: {line}");
        }

        return new StallingWindow(process, (nint)handle, title);
    }

    /// <summary>The window's thread stops pumping; returns once it has.</summary>
    internal void Stall() => _ = Say("stall");

    internal void Resume() => _ = Say("resume");

    /// <summary>The next WM_NULL is answered, and the window stops pumping right after it: the check before an act passes.</summary>
    internal void StallAfterNextProbe() => _ = Say("answer0");

    /// <summary>Ends the program abruptly, by its process id.</summary>
    internal void Kill()
    {
        _process.Kill(entireProcessTree: false);
        _ = _process.WaitForExit(5000);
    }

    /// <summary>What reached the window's thread so far: key downs, mouse presses and commands from its button.</summary>
    internal (int Keys, int Presses, int Commands) Received()
    {
        string[] parts = Say("count").Split(' ');
        return (int.Parse(parts[0], CultureInfo.InvariantCulture), int.Parse(parts[1], CultureInfo.InvariantCulture),
            int.Parse(parts[2], CultureInfo.InvariantCulture));
    }

    private string Say(string line)
    {
        _process.StandardInput.WriteLine(line);
        _process.StandardInput.Flush();
        return _process.StandardOutput.ReadLine() ?? throw new InvalidOperationException("the stalling window's host ended");
    }

    private static string Number(int value) => value.ToString(CultureInfo.InvariantCulture);

    public void Dispose()
    {
        try
        {
            if (!_process.HasExited)
            {
                _process.Kill(entireProcessTree: false);
                _ = _process.WaitForExit(5000);
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
        }
        finally
        {
            _process.Dispose();
        }
    }
}
