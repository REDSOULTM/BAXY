using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Infrastructure;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Providers.Windows.Applications;

internal interface IWindowsApplicationPlatform
{
    DateTimeOffset UtcNow { get; }

    NotepadLaunchTarget ResolveNotepadLaunchTarget();

    IReadOnlyList<IWindowsApplicationProcess> EnumerateNotepadProcesses();

    IWindowsApplicationProcess CreateProcess(
        string executablePath,
        uint creationFlags,
        bool inheritHandles,
        string? commandLine);

    IWindowsApplicationProcess? OpenProcess(int processId);

    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}

internal interface IWindowsApplicationProcess : IDisposable
{
    int ProcessId { get; }

    ApplicationProcessObservation Observe();

    void RequestForeground(nint windowHandle);
}

internal sealed class WindowsApplicationPlatform : IWindowsApplicationPlatform
{
    private const uint ProcessQueryLimitedInformation = 0x00001000;
    private const uint Synchronize = 0x00100000;
    private const int ErrorAccessDenied = 5;
    private const int ErrorInvalidParameter = 87;
    private const int ErrorNotFound = 1168;

    public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;

    public NotepadLaunchTarget ResolveNotepadLaunchTarget()
    {
        string windowsDirectory = Path.GetFullPath(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows));
        string programFilesDirectory = Path.GetFullPath(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles));
        string bootstrapPath = SafePathPolicy.NormalizeAndValidateExistingFile(
            Path.Combine(windowsDirectory, "System32", "notepad.exe"));

        return new NotepadLaunchTarget(
            bootstrapPath,
            programFilesDirectory,
            SystemApplicationPathTrust.Instance);
    }

    public IReadOnlyList<IWindowsApplicationProcess> EnumerateNotepadProcesses()
    {
        Process[] processes;
        try
        {
            processes = Process.GetProcessesByName("notepad");
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException
            or NotSupportedException)
        {
            throw new ApplicationInventoryException(
                "The Notepad process inventory could not be enumerated.",
                exception);
        }

        List<IWindowsApplicationProcess> observations = new(processes.Length);
        try
        {
            foreach (Process process in processes)
            {
                int processId;
                try
                {
                    processId = process.Id;
                }
                finally
                {
                    process.Dispose();
                }

                IWindowsApplicationProcess? opened = OpenProcessCore(
                    processId,
                    missingIsFailure: false);
                if (opened is not null)
                {
                    observations.Add(opened);
                }
            }

            return observations;
        }
        catch
        {
            foreach (IWindowsApplicationProcess observation in observations)
            {
                observation.Dispose();
            }

            throw;
        }
    }

    public IWindowsApplicationProcess CreateProcess(
        string executablePath,
        uint creationFlags,
        bool inheritHandles,
        string? commandLine)
    {
        if (commandLine is not null)
        {
            throw new ArgumentException("Free-form command lines are forbidden.", nameof(commandLine));
        }

        NativeMethods.StartupInfo startupInfo = new()
        {
            Size = checked((uint)Marshal.SizeOf<NativeMethods.StartupInfo>()),
        };

        bool created = NativeMethods.CreateProcess(
            executablePath,
            commandLine: 0,
            processAttributes: 0,
            threadAttributes: 0,
            inheritHandles,
            creationFlags,
            environment: 0,
            Path.GetDirectoryName(executablePath)!,
            ref startupInfo,
            out NativeMethods.ProcessInformation processInformation);

        if (!created)
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        SafeProcessHandle processHandle = new(processInformation.ProcessHandle, ownsHandle: true);
        using SafeWaitHandle threadHandle = new(
            processInformation.ThreadHandle,
            ownsHandle: true);

        try
        {
            return new WindowsApplicationProcess(
                checked((int)processInformation.ProcessId),
                processHandle);
        }
        catch
        {
            processHandle.Dispose();
            throw;
        }
    }

    public IWindowsApplicationProcess? OpenProcess(int processId) =>
        OpenProcessCore(processId, missingIsFailure: false);

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    private static WindowsApplicationProcess? OpenProcessCore(
        int processId,
        bool missingIsFailure)
    {
        SafeProcessHandle handle = NativeMethods.OpenProcess(
            ProcessQueryLimitedInformation | Synchronize,
            inheritHandle: false,
            checked((uint)processId));
        if (!handle.IsInvalid)
        {
            try
            {
                return new WindowsApplicationProcess(processId, handle);
            }
            catch (ApplicationProcessExitedException) when (!missingIsFailure)
            {
                handle.Dispose();
                return null;
            }
            catch
            {
                handle.Dispose();
                throw;
            }
        }

        int error = Marshal.GetLastWin32Error();
        handle.Dispose();
        if (!missingIsFailure && error is ErrorInvalidParameter or ErrorNotFound)
        {
            return null;
        }

        string detail = error == ErrorAccessDenied
            ? "Access to a Notepad candidate was denied."
            : "A Notepad candidate could not be opened safely.";
        throw new ApplicationInventoryException(detail, new Win32Exception(error));
    }
}

internal sealed class WindowsApplicationProcess : IWindowsApplicationProcess
{
    private const uint WaitTimeout = 0x00000102;
    private const int RestoreWindow = 9;
    private const int MaximumIdentityCharacters = 32_768;
    private const int AppModelErrorNoPackage = 15700;
    private const int ErrorInsufficientBuffer = 122;

    private readonly int _processId;
    private readonly SafeProcessHandle _processHandle;
    private readonly long _creationTimeUtcTicks;
    private bool _disposed;

    public WindowsApplicationProcess(int processId, SafeProcessHandle processHandle)
    {
        _processId = processId;
        _processHandle = processHandle;
        _creationTimeUtcTicks = QueryCreationTimeUtcTicks();
    }

    public int ProcessId => _processId;

    public ApplicationProcessObservation Observe()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        EnsureOriginalProcessRunning();

        string executablePath = QueryExecutablePath();
        (string? packageFamilyName, string? packageFullName) = QueryPackageIdentity();
        nint windowHandle = QueryMainWindowHandle();
        bool windowVisible = windowHandle != 0
            && NativeMethods.IsWindowVisible(windowHandle);
        bool foreground = windowVisible
            && NativeMethods.GetForegroundWindow() == windowHandle;

        EnsureOriginalProcessRunning();
        return new ApplicationProcessObservation(
            _processId,
            _creationTimeUtcTicks,
            executablePath,
            packageFamilyName,
            packageFullName,
            windowHandle,
            windowVisible,
            foreground);
    }

    public void RequestForeground(nint windowHandle)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        EnsureWindowOwnedByOriginalProcess(windowHandle);

        _ = NativeMethods.AllowSetForegroundWindow(checked((uint)_processId));
        _ = NativeMethods.ShowWindowAsync(windowHandle, RestoreWindow);
        _ = NativeMethods.SetForegroundWindow(windowHandle);
        EnsureOriginalProcessRunning();
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _processHandle.Dispose();
    }

    private long QueryCreationTimeUtcTicks()
    {
        EnsureOriginalProcessRunning();
        if (!NativeMethods.GetProcessTimes(
                _processHandle,
                out NativeMethods.FileTime creationTime,
                out _,
                out _,
                out _))
        {
            ThrowObservationFailure("The process creation time could not be queried.");
        }

        long fileTime = creationTime.ToInt64();
        try
        {
            return DateTime.FromFileTimeUtc(fileTime).Ticks;
        }
        catch (ArgumentOutOfRangeException exception)
        {
            throw new ApplicationInventoryException(
                "The process creation time is invalid.",
                exception);
        }
    }

    private string QueryExecutablePath()
    {
        nint buffer = Marshal.AllocHGlobal(checked(MaximumIdentityCharacters * sizeof(char)));
        try
        {
            uint length = MaximumIdentityCharacters;
            if (!NativeMethods.QueryFullProcessImageName(
                    _processHandle,
                    flags: 0,
                    buffer,
                    ref length)
                || length == 0
                || length >= MaximumIdentityCharacters)
            {
                ThrowObservationFailure("The process executable path could not be queried.");
            }

            string path = Marshal.PtrToStringUni(buffer, checked((int)length));
            return Path.GetFullPath(path);
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private (string? FamilyName, string? FullName) QueryPackageIdentity()
    {
        string? familyName = QueryPackageString(NativeMethods.GetPackageFamilyName);
        string? fullName = QueryPackageString(NativeMethods.GetPackageFullName);
        if ((familyName is null) != (fullName is null))
        {
            throw new ApplicationInventoryException(
                "The process package identity is internally inconsistent.");
        }

        return (familyName, fullName);
    }

    private string? QueryPackageString(PackageQuery query)
    {
        uint length = 0;
        int firstResult = query(_processHandle, ref length, 0);
        if (firstResult == AppModelErrorNoPackage)
        {
            return null;
        }

        if (firstResult != ErrorInsufficientBuffer
            || length is 0 or > MaximumIdentityCharacters)
        {
            ThrowObservationFailure("The process package identity could not be sized.");
        }

        nint buffer = Marshal.AllocHGlobal(checked((int)length * sizeof(char)));
        try
        {
            int secondResult = query(_processHandle, ref length, buffer);
            if (secondResult != 0 || length is 0 or > MaximumIdentityCharacters)
            {
                ThrowObservationFailure("The process package identity could not be queried.");
            }

            string? value = Marshal.PtrToStringUni(buffer);
            if (string.IsNullOrWhiteSpace(value))
            {
                throw new ApplicationInventoryException(
                    "The process package identity is empty.");
            }

            return value;
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private nint QueryMainWindowHandle()
    {
        EnsureOriginalProcessRunning();
        try
        {
            using Process process = Process.GetProcessById(_processId);
            process.Refresh();
            nint windowHandle = process.MainWindowHandle;
            if (windowHandle != 0 && NativeMethods.IsWindowVisible(windowHandle))
            {
                EnsureWindowOwnedByOriginalProcess(windowHandle);
                return windowHandle;
            }

            // Store / WinUI Notepad often has MainWindowHandle == 0 while a
            // visible top-level HWND still belongs to the same PID. Installed
            // app.open already enumerates owned windows; notepad must too.
            nint ownedVisible = LargestOwnedVisibleWindow();
            if (ownedVisible != 0)
            {
                EnsureWindowOwnedByOriginalProcess(ownedVisible);
                return ownedVisible;
            }

            // WinUI Notepad's visible chrome lives on ApplicationFrameHost
            // (same pattern as Calculator). Bind that titled HWND.
            nint chrome = FindNotepadChromeWindow();
            EnsureOriginalProcessRunning();
            return chrome;
        }
        catch (ArgumentException)
        {
            throw new ApplicationProcessExitedException();
        }
        catch (InvalidOperationException)
        {
            throw new ApplicationProcessExitedException();
        }
        catch (Win32Exception exception)
        {
            ThrowObservationFailure("The process window could not be observed.", exception);
            return 0;
        }
    }

    private nint LargestOwnedVisibleWindow()
    {
        EnsureOriginalProcessRunning();
        var windows = new List<NotepadIdentityPolicy.ObservedTopLevelWindow>();
        NativeMethods.EnumWindowsProc callback = (window, _) =>
        {
            uint threadId = NativeMethods.GetWindowThreadProcessId(window, out uint owner);
            if (threadId == 0)
            {
                return true;
            }
            bool visible = NativeMethods.IsWindow(window)
                && NativeMethods.IsWindowVisible(window);
            int width = 0;
            int height = 0;
            if (NativeMethods.GetWindowRect(window, out NativeMethods.Rect rect))
            {
                width = Math.Max(0, rect.Right - rect.Left);
                height = Math.Max(0, rect.Bottom - rect.Top);
            }

            windows.Add(new NotepadIdentityPolicy.ObservedTopLevelWindow(
                window,
                owner,
                visible,
                width,
                height));
            return true;
        };
        _ = NativeMethods.EnumWindows(callback, 0);
        EnsureOriginalProcessRunning();
        return NotepadIdentityPolicy.LargestVisibleOwnedWindow(_processId, windows);
    }

    private static string ReadWindowTitle(nint windowHandle)
    {
        int length = NativeMethods.GetWindowTextLength(windowHandle);
        if (length <= 0)
        {
            return string.Empty;
        }

        nint buffer = Marshal.AllocHGlobal(checked((length + 1) * sizeof(char)));
        try
        {
            int written = NativeMethods.GetWindowText(windowHandle, buffer, length + 1);
            return written > 0
                ? Marshal.PtrToStringUni(buffer, written) ?? string.Empty
                : string.Empty;
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private nint FindNotepadChromeWindow()
    {
        EnsureOriginalProcessRunning();
        nint best = 0;
        long bestArea = 0;
        NativeMethods.EnumWindowsProc callback = (window, _) =>
        {
            if (!NativeMethods.IsWindow(window) || !NativeMethods.IsWindowVisible(window))
            {
                return true;
            }

            if (!NotepadIdentityPolicy.IsNotepadWindowTitle(ReadWindowTitle(window)))
            {
                return true;
            }

            int width = 0;
            int height = 0;
            if (NativeMethods.GetWindowRect(window, out NativeMethods.Rect rect))
            {
                width = Math.Max(0, rect.Right - rect.Left);
                height = Math.Max(0, rect.Bottom - rect.Top);
            }

            long area = (long)width * height;
            if (area > bestArea)
            {
                bestArea = area;
                best = window;
            }

            return true;
        };
        _ = NativeMethods.EnumWindows(callback, 0);
        EnsureOriginalProcessRunning();
        return best;
    }

    private void EnsureWindowOwnedByOriginalProcess(nint windowHandle)
    {
        EnsureOriginalProcessRunning();
        if (windowHandle == 0 || !NativeMethods.IsWindow(windowHandle))
        {
            throw new ApplicationInventoryException("The process window is invalid.");
        }

        uint threadId = NativeMethods.GetWindowThreadProcessId(windowHandle, out uint ownerProcessId);
        if (threadId == 0)
        {
            throw new ApplicationInventoryException("The process window is invalid.");
        }

        if (ownerProcessId == unchecked((uint)_processId))
        {
            EnsureOriginalProcessRunning();
            return;
        }

        // ApplicationFrameHost hosts the visible WinUI Notepad chrome.
        if (!NativeMethods.IsWindowVisible(windowHandle)
            || !NotepadIdentityPolicy.IsNotepadWindowTitle(ReadWindowTitle(windowHandle)))
        {
            throw new ApplicationInventoryException(
                "The process window belongs to a different process.");
        }

        EnsureOriginalProcessRunning();
    }

    private void EnsureOriginalProcessRunning()
    {
        if (_disposed
            || _processHandle.IsInvalid
            || _processHandle.IsClosed
            || NativeMethods.WaitForSingleObject(_processHandle, 0) != WaitTimeout)
        {
            throw new ApplicationProcessExitedException();
        }
    }

    private void ThrowObservationFailure(string message, Exception? innerException = null)
    {
        try
        {
            EnsureOriginalProcessRunning();
        }
        catch (ApplicationProcessExitedException)
        {
            throw;
        }

        throw innerException is null
            ? new ApplicationInventoryException(message)
            : new ApplicationInventoryException(message, innerException);
    }

    private delegate int PackageQuery(
        SafeProcessHandle processHandle,
        ref uint packageNameLength,
        nint packageName);
}

internal static class NativeMethods
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct StartupInfo
    {
        internal uint Size;
        internal nint Reserved;
        internal nint Desktop;
        internal nint Title;
        internal uint X;
        internal uint Y;
        internal uint XSize;
        internal uint YSize;
        internal uint XCountChars;
        internal uint YCountChars;
        internal uint FillAttribute;
        internal uint Flags;
        internal ushort ShowWindow;
        internal ushort Reserved2Size;
        internal nint Reserved2;
        internal nint StandardInput;
        internal nint StandardOutput;
        internal nint StandardError;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct ProcessInformation
    {
        internal nint ProcessHandle;
        internal nint ThreadHandle;
        internal uint ProcessId;
        internal uint ThreadId;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct FileTime
    {
        internal uint LowDateTime;
        internal uint HighDateTime;

        internal readonly long ToInt64() =>
            unchecked((long)(((ulong)HighDateTime << 32) | LowDateTime));
    }

    [DllImport("kernel32.dll", EntryPoint = "CreateProcessW", SetLastError = true,
        CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool CreateProcess(
        string applicationName,
        nint commandLine,
        nint processAttributes,
        nint threadAttributes,
        [MarshalAs(UnmanagedType.Bool)] bool inheritHandles,
        uint creationFlags,
        nint environment,
        string currentDirectory,
        ref StartupInfo startupInfo,
        out ProcessInformation processInformation);

    [DllImport("kernel32.dll", SetLastError = true)]
    internal static extern SafeProcessHandle OpenProcess(
        uint desiredAccess,
        [MarshalAs(UnmanagedType.Bool)] bool inheritHandle,
        uint processId);

    [DllImport("kernel32.dll", EntryPoint = "QueryFullProcessImageNameW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool QueryFullProcessImageName(
        SafeProcessHandle processHandle,
        uint flags,
        nint executablePath,
        ref uint size);

    [DllImport("kernel32.dll")]
    internal static extern uint WaitForSingleObject(
        SafeProcessHandle handle,
        uint milliseconds);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool GetProcessTimes(
        SafeProcessHandle processHandle,
        out FileTime creationTime,
        out FileTime exitTime,
        out FileTime kernelTime,
        out FileTime userTime);

    [DllImport("kernel32.dll")]
    internal static extern int GetPackageFamilyName(
        SafeProcessHandle processHandle,
        ref uint packageFamilyNameLength,
        nint packageFamilyName);

    [DllImport("kernel32.dll")]
    internal static extern int GetPackageFullName(
        SafeProcessHandle processHandle,
        ref uint packageFullNameLength,
        nint packageFullName);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool IsWindow(nint windowHandle);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool IsWindowVisible(nint windowHandle);

    [DllImport("user32.dll")]
    internal static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool AllowSetForegroundWindow(uint processId);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool ShowWindowAsync(nint windowHandle, int command);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool SetForegroundWindow(nint windowHandle);

    [DllImport("user32.dll")]
    internal static extern uint GetWindowThreadProcessId(
        nint windowHandle,
        out uint processId);

    [StructLayout(LayoutKind.Sequential)]
    internal struct Rect
    {
        internal int Left;
        internal int Top;
        internal int Right;
        internal int Bottom;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    internal delegate bool EnumWindowsProc(nint windowHandle, nint lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool GetWindowRect(nint windowHandle, out Rect rect);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, EntryPoint = "GetWindowTextW")]
    internal static extern int GetWindowText(
        nint windowHandle,
        nint text,
        int maxCount);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, EntryPoint = "GetWindowTextLengthW")]
    internal static extern int GetWindowTextLength(nint windowHandle);
}
