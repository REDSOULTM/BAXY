// BAXY Renew: what the speakers really play, for the lip-sync acceptance test (src/Baxy.FieldUi/e2e/lipsync.spec.ts).
// WASAPI loopback: writes "unix_ms,rms" for every 10 ms of captured sound during N seconds.
// Usage: loopcap <seconds> <out.csv> [process name]
//   with a process name, only the sound of that process and its children (Windows 10 2004+ process loopback): BAXY's
//   voice alone, whatever else the PC plays (owner, 2026-10-21: «debe funcionar tanto con o sin sonido del pc»);
//   without it, everything the default output plays.
// Built by scripts/test_field_ui.ps1; nothing is installed or downloaded.
using System; using System.Diagnostics; using System.Globalization; using System.IO; using System.Runtime.InteropServices; using System.Threading;

[ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator { int EnumAudioEndpoints(int a, int b, out IntPtr c); int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice dev); }
[ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice { int Activate(ref Guid iid, int ctx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o); }
[ComImport, Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioClient {
  int Initialize(int mode, int flags, long buf, long period, IntPtr fmt, IntPtr session);
  int GetBufferSize(out uint n); int GetStreamLatency(out long l); int GetCurrentPadding(out uint p);
  int IsFormatSupported(int m, IntPtr f, out IntPtr c); int GetMixFormat(out IntPtr f); int GetDevicePeriod(out long a, out long b);
  int Start(); int Stop(); int Reset(); int SetEventHandle(IntPtr h); int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object o); }
[ComImport, Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioCaptureClient { int GetBuffer(out IntPtr data, out uint frames, out uint flags, out ulong pos, out ulong qpc); int ReleaseBuffer(uint n); int GetNextPacketSize(out uint n); }
[ComImport, Guid("72A22D78-CDE4-431D-B8CC-843A71199B6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IActivateAudioInterfaceAsyncOperation { int GetActivateResult(out int hr, [MarshalAs(UnmanagedType.IUnknown)] out object iface); }
[ComImport, Guid("41D949AB-9862-444A-80F6-C261334DA5EB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IActivateAudioInterfaceCompletionHandler { int ActivateCompleted(IActivateAudioInterfaceAsyncOperation op); }
[ComImport, Guid("94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAgileObject { }

sealed class Done : IActivateAudioInterfaceCompletionHandler, IAgileObject, IDisposable {
  public readonly ManualResetEventSlim Signal = new();
  public int ActivateCompleted(IActivateAudioInterfaceAsyncOperation op) { Signal.Set(); return 0; }
  public void Dispose() => Signal.Dispose();
}

static class P {
  [DllImport("Mmdevapi.dll", ExactSpelling = true)]
  static extern int ActivateAudioInterfaceAsync([MarshalAs(UnmanagedType.LPWStr)] string path, ref Guid riid, IntPtr parameters,
    IActivateAudioInterfaceCompletionHandler handler, out IActivateAudioInterfaceAsyncOperation op);

  static readonly Guid AudioClient = new("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2");

  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  struct ProcessEntry {
    public int Size; public int Usage; public int ProcessId; public IntPtr HeapId; public int ModuleId; public int Threads;
    public int ParentProcessId; public int PriorityClass; public int Flags;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string ExeFile;
  }
  [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr CreateToolhelp32Snapshot(int flags, int pid);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool Process32FirstW(IntPtr snap, ref ProcessEntry e);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool Process32NextW(IntPtr snap, ref ProcessEntry e);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);

  // BAXY's voice plays in its mind (Baxy.exe → python launcher → python): a process loopback includes the children of
  // its target but not their children, so the target is the launcher, the python Baxy.exe started.
  static int VoiceProcess(int app) {
    IntPtr snap = CreateToolhelp32Snapshot(2, 0);
    try {
      var e = new ProcessEntry { Size = Marshal.SizeOf<ProcessEntry>() };
      for (bool ok = Process32FirstW(snap, ref e); ok; ok = Process32NextW(snap, ref e))
        if (e.ParentProcessId == app && e.ExeFile.Equals("python.exe", StringComparison.OrdinalIgnoreCase)) return e.ProcessId;
    } finally { CloseHandle(snap); }
    return app;
  }

  // The process loopback client: AUDIOCLIENT_ACTIVATION_PARAMS (process loopback, include the process tree) in a
  // PROPVARIANT of type VT_BLOB, activated on the virtual device «VAD\Process_Loopback».
  static IAudioClient ProcessClient(int pid) {
    IntPtr prm = Marshal.AllocHGlobal(12), pv = Marshal.AllocHGlobal(24);
    Marshal.WriteInt32(prm, 0, 1); Marshal.WriteInt32(prm, 4, pid); Marshal.WriteInt32(prm, 8, 0);
    for (int i = 0; i < 24; i += 4) Marshal.WriteInt32(pv, i, 0);
    Marshal.WriteInt16(pv, 0, 65); Marshal.WriteInt32(pv, 8, 12); Marshal.WriteIntPtr(pv, 16, prm);
    using var done = new Done(); var iid = AudioClient;
    Marshal.ThrowExceptionForHR(ActivateAudioInterfaceAsync("VAD\\Process_Loopback", ref iid, pv, done, out var op));
    if (!done.Signal.Wait(5000)) throw new TimeoutException("process loopback did not activate");
    Marshal.ThrowExceptionForHR(op.GetActivateResult(out int hr, out object o)); Marshal.ThrowExceptionForHR(hr);
    return (IAudioClient)o;
  }

  [MTAThread]
  static unsafe int Main(string[] a) {
    double secs = double.Parse(a[0], CultureInfo.InvariantCulture); string outp = a[1];
    IAudioClient ac; int rate, ch; bool pcm16;
    using var ev = new AutoResetEvent(false);
    if (a.Length > 2) {
      int pid;
      if (!int.TryParse(a[2], NumberStyles.None, CultureInfo.InvariantCulture, out pid)) {
        var procs = Process.GetProcessesByName(a[2]);
        if (procs.Length == 0) { Console.Error.WriteLine("no process " + a[2]); return 2; }
        pid = VoiceProcess(procs[0].Id);
      }
      ac = ProcessClient(pid);
      // a process loopback has no mix format: 16-bit PCM stereo 48 kHz, converted by the audio engine
      rate = 48000; ch = 2; pcm16 = true;
      IntPtr fmt = Marshal.AllocHGlobal(18);
      Marshal.WriteInt16(fmt, 0, 1); Marshal.WriteInt16(fmt, 2, 2); Marshal.WriteInt32(fmt, 4, rate); Marshal.WriteInt32(fmt, 8, rate * 4);
      Marshal.WriteInt16(fmt, 12, 4); Marshal.WriteInt16(fmt, 14, 16); Marshal.WriteInt16(fmt, 16, 0);
      // loopback | event callback | auto-convert PCM | default-quality resampling
      Marshal.ThrowExceptionForHR(ac.Initialize(0, 0x00020000 | 0x00040000 | unchecked((int)0x80000000) | 0x08000000, 2000000, 0, fmt, IntPtr.Zero));
      Marshal.ThrowExceptionForHR(ac.SetEventHandle(ev.SafeWaitHandle.DangerousGetHandle()));
    } else {
      var en = (IMMDeviceEnumerator)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")));
      Marshal.ThrowExceptionForHR(en.GetDefaultAudioEndpoint(0, 0, out var dev));
      var iid = AudioClient;
      Marshal.ThrowExceptionForHR(dev.Activate(ref iid, 23, IntPtr.Zero, out var o)); ac = (IAudioClient)o;
      Marshal.ThrowExceptionForHR(ac.GetMixFormat(out var fmt));
      ch = Marshal.ReadInt16(fmt, 2); rate = Marshal.ReadInt32(fmt, 4); pcm16 = false;
      Marshal.ThrowExceptionForHR(ac.Initialize(0, 0x00020000, 2000000, 0, fmt, IntPtr.Zero));
    }
    var ciid = new Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317");
    Marshal.ThrowExceptionForHR(ac.GetService(ref ciid, out var co)); var cc = (IAudioCaptureClient)co;
    long qf = Stopwatch.Frequency; long t0q = Stopwatch.GetTimestamp(); double t0ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + (DateTime.UtcNow.Ticks % 10000) / 10000.0;
    Marshal.ThrowExceptionForHR(ac.Start());
    using var w = new StreamWriter(outp); w.WriteLine(FormattableString.Invariant($"# rate={rate} ch={ch} process={(a.Length > 2 ? a[2] : "-")}"));
    int win = rate / 100; double acc = 0; int n = 0; double winStart = -1;
    var end = DateTime.UtcNow.AddSeconds(secs);
    while (DateTime.UtcNow < end) {
      ev.WaitOne(10);
      while (true) {
        cc.GetNextPacketSize(out uint pk); if (pk == 0) break;
        cc.GetBuffer(out var data, out uint fr, out uint fl, out ulong pos, out ulong qpc);
        // qpc is in 100 ns units of the performance counter: when the first frame of the packet was captured
        double pktMs = qpc != 0 ? t0ms + ((double)qpc / 1e4 - (double)t0q * 1000.0 / qf)
          : DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - fr * 1000.0 / rate;
        bool silent = (fl & 2) != 0;
        for (int i = 0; i < fr; i++) {
          if (n == 0) winStart = pktMs + i * 1000.0 / rate;
          double s = 0;
          if (!silent) for (int c = 0; c < ch; c++) { double v = pcm16 ? ((short*)data)[i * ch + c] / 32768.0 : ((float*)data)[i * ch + c]; s += v * v; }
          acc += s / ch; n++;
          if (n == win) { w.WriteLine(FormattableString.Invariant($"{winStart:F1},{Math.Sqrt(acc / n):F5}")); acc = 0; n = 0; }
        }
        cc.ReleaseBuffer(fr);
      }
    }
    ac.Stop(); return 0;
  }
}
