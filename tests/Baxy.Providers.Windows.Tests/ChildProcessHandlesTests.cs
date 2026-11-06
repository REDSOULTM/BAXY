using System.ComponentModel;
using System.Diagnostics;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// N3 (Providers hung with no CPU, 2026-11-04 18:22 and 2026-11-05 04:45, in a test reading baxy-core's stdout): the core
/// exits while a helper's Add-Type has just created csc.exe, which .NET Framework's compiler host starts suspended. The
/// helper dies with the core's job, nobody resumes the compiler, and it stays for ever, holding the stdout it inherited.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class ChildProcessHandlesTests
{
    private const int StdOutput = -11;
    private const uint CreateSuspended = 0x4;
    private const uint CreateNoWindow = 0x08000000;

    private static string Compiler() => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Microsoft.NET", "Framework64", "v4.0.30319", "csc.exe");

    [Test]
    public void AChildDoesNotHoldTheOutputOfTheProcessThatStartedIt()
    {
        using var server = new AnonymousPipeServerStream(PipeDirection.In, HandleInheritability.Inheritable);
        IntPtr before = GetStdHandle(StdOutput);
        Process? child = null;
        try
        {
            Assert.That(SetStdHandle(StdOutput, server.ClientSafePipeHandle.DangerousGetHandle()), Is.True);
            ChildProcessHandles.KeepOutputFromChildren();
            child = Process.Start(new ProcessStartInfo("powershell.exe", "-NoProfile -NonInteractive -Command Start-Sleep -Seconds 12")
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardError = true,
                RedirectStandardInput = true,
            })!;
        }
        finally
        {
            _ = SetStdHandle(StdOutput, before);
        }

        try
        {
            server.DisposeLocalCopyOfClientHandle();
            Task<int> read = server.ReadAsync(new byte[16]).AsTask();

            Assert.That(read.Wait(TimeSpan.FromSeconds(4)), Is.True, "the pipe's only other holder is a child still running");
            Assert.That(child.HasExited, Is.False, "the child outlived the read");
        }
        finally
        {
            child.Kill(entireProcessTree: true);
            child.Dispose();
        }
    }

    // The orphan as it happens: a process creates the compiler suspended and dies before resuming it.
    [Test]
    public void ASuspendedCompilerWhoseParentIsGoneIsReaped()
    {
        if (!File.Exists(Compiler()))
            Assert.Inconclusive("This Windows has no .NET Framework compiler.");
        string script = "Add-Type -TypeDefinition '"
            + "using System; using System.Runtime.InteropServices;"
            + "public static class N3 {"
            + "[StructLayout(LayoutKind.Sequential)] public struct PI { public IntPtr p, t; public int pid, tid; }"
            + "[StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] public struct SI { public int cb; public string a, b, c;"
            + " public int d, e, f, g, h, i, j, k; public short l, m; public IntPtr n, o, q, r; }"
            + "[DllImport(\"kernel32.dll\", CharSet=CharSet.Unicode)] public static extern bool CreateProcessW(string a, string b, IntPtr c, IntPtr d,"
            + " bool e, uint f, IntPtr g, string h, ref SI i, out PI j);"
            + "public static int Go(string path) { var s = new SI(); s.cb = Marshal.SizeOf(typeof(SI)); PI p;"
            + " if (!CreateProcessW(path, null, IntPtr.Zero, IntPtr.Zero, false, 0x08000004, IntPtr.Zero, null, ref s, out p)) return -1; return p.pid; } }';"
            + "[N3]::Go('" + Compiler() + "')";
        var start = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        int orphan;
        using (Process parent = Process.Start(start)!)
        {
            Task<string> error = parent.StandardError.ReadToEndAsync();
            string output = ChildOutput.Read(parent);
            Assert.That(parent.WaitForExit(60_000), Is.True);
            Assert.That(int.TryParse(output.Trim(), out orphan) && orphan > 0, Is.True, output + error.Result);
        }

        using Process compiler = Process.GetProcessById(orphan);
        try
        {
            Assert.That(ChildProcessHandles.ReapOrphanedCompilers(), Is.GreaterThanOrEqualTo(1));
            Assert.That(compiler.WaitForExit(5_000), Is.True, "the orphan is gone");
        }
        finally
        {
            if (!compiler.HasExited)
                compiler.Kill();
        }
    }

    // A compiler whose parent lives may be resumed at any moment: it is that process's, whatever it looks like now.
    [Test]
    public void ASuspendedCompilerWhoseParentLivesIsLeftAlone()
    {
        if (!File.Exists(Compiler()))
            Assert.Inconclusive("This Windows has no .NET Framework compiler.");
        var startup = new StartupInfo { Size = Marshal.SizeOf<StartupInfo>() };
        if (!CreateProcessW(Compiler(), null, 0, 0, false, CreateSuspended | CreateNoWindow, 0, null, ref startup, out ProcessInformation created))
            throw new Win32Exception();
        using Process compiler = Process.GetProcessById(created.ProcessId);
        try
        {
            _ = ChildProcessHandles.ReapOrphanedCompilers();

            Assert.That(compiler.HasExited, Is.False);
        }
        finally
        {
            compiler.Kill();
            _ = CloseHandle(created.Process);
            _ = CloseHandle(created.Thread);
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        public IntPtr Process;
        public IntPtr Thread;
        public int ProcessId;
        public int ThreadId;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct StartupInfo
    {
        public int Size;
        public IntPtr Reserved;
        public IntPtr Desktop;
        public IntPtr Title;
        public int X, Y, Width, Height, CharsWide, CharsHigh, FillAttribute, Flags;
        public short ShowWindow, Reserved2;
        public IntPtr Reserved3, Input, Output, Error;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateProcessW(
        string application, string? commandLine, IntPtr process, IntPtr thread, [MarshalAs(UnmanagedType.Bool)] bool inherit,
        uint flags, IntPtr environment, string? directory, ref StartupInfo startup, out ProcessInformation information);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetStdHandle(int which);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetStdHandle(int which, IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr handle);
}
