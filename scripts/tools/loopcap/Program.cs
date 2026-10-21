// BAXY Renew: what the speakers really play, for the lip-sync acceptance test (src/Baxy.FieldUi/e2e/lipsync.spec.ts).
// WASAPI loopback of the default render device: writes "unix_ms,rms" for every 10 ms of captured sound during N seconds.
// Usage: loopcap <seconds> <out.csv>. Built by scripts/test_field_ui.ps1; nothing is installed or downloaded.
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

static class P {
  static unsafe int Main(string[] a) {
    double secs = double.Parse(a[0], CultureInfo.InvariantCulture); string outp = a[1];
    var en = (IMMDeviceEnumerator)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")));
    Marshal.ThrowExceptionForHR(en.GetDefaultAudioEndpoint(0, 0, out var dev));
    var iid = new Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2");
    Marshal.ThrowExceptionForHR(dev.Activate(ref iid, 23, IntPtr.Zero, out var o)); var ac = (IAudioClient)o;
    Marshal.ThrowExceptionForHR(ac.GetMixFormat(out var fmt));
    short ch = Marshal.ReadInt16(fmt, 2); int rate = Marshal.ReadInt32(fmt, 4); short bits = Marshal.ReadInt16(fmt, 14);
    Marshal.ThrowExceptionForHR(ac.Initialize(0, 0x00020000, 2000000, 0, fmt, IntPtr.Zero));
    var ciid = new Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317");
    Marshal.ThrowExceptionForHR(ac.GetService(ref ciid, out var co)); var cc = (IAudioCaptureClient)co;
    long qf = Stopwatch.Frequency; long t0q = Stopwatch.GetTimestamp(); double t0ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + (DateTime.UtcNow.Ticks % 10000) / 10000.0;
    Marshal.ThrowExceptionForHR(ac.Start());
    using var w = new StreamWriter(outp); w.WriteLine(FormattableString.Invariant($"# rate={rate} ch={ch} bits={bits}"));
    int win = rate / 100; double acc = 0; int n = 0; double winStart = -1;
    var end = DateTime.UtcNow.AddSeconds(secs);
    while (DateTime.UtcNow < end) {
      Thread.Sleep(5);
      while (true) {
        cc.GetNextPacketSize(out uint pk); if (pk == 0) break;
        cc.GetBuffer(out var data, out uint fr, out uint fl, out ulong pos, out ulong qpc);
        // qpc is in 100 ns units of the performance counter: when the first frame of the packet was captured
        double pktMs = t0ms + ((double)qpc / 1e4 - (double)t0q * 1000.0 / qf);
        float* f = (float*)data; bool silent = (fl & 2) != 0;
        for (int i = 0; i < fr; i++) {
          if (n == 0) winStart = pktMs + i * 1000.0 / rate;
          double s = 0; if (!silent) for (int c = 0; c < ch; c++) { double v = f[i * ch + c]; s += v * v; } acc += s / ch; n++;
          if (n == win) { w.WriteLine(FormattableString.Invariant($"{winStart:F1},{Math.Sqrt(acc / n):F5}")); acc = 0; n = 0; }
        }
        cc.ReleaseBuffer(fr);
      }
    }
    ac.Stop(); return 0;
  }
}
