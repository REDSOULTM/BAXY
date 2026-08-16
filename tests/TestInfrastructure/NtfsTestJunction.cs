using System.Buffers.Binary;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Tests;

internal static class NtfsTestJunction
{
    private const uint IoReparseTagMountPoint = 0xA0000003;
    private const uint GenericWrite = 0x40000000;
    private const uint FileShareRead = 0x00000001;
    private const uint FileShareWrite = 0x00000002;
    private const uint FileShareDelete = 0x00000004;
    private const uint OpenExisting = 3;
    private const uint FileFlagBackupSemantics = 0x02000000;
    private const uint FileFlagOpenReparsePoint = 0x00200000;
    private const uint FsctlSetReparsePoint = 0x000900A4;

    public static DirectoryInfo Create(string linkPath, string targetPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(linkPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(targetPath);

        if (!OperatingSystem.IsWindows())
        {
            _ = Directory.CreateSymbolicLink(linkPath, targetPath);
            return new DirectoryInfo(linkPath);
        }

        string fullLink = Path.GetFullPath(linkPath);
        string fullTarget = Path.TrimEndingDirectorySeparator(Path.GetFullPath(targetPath));
        if (!Directory.Exists(fullTarget))
        {
            throw new DirectoryNotFoundException(fullTarget);
        }

        Directory.CreateDirectory(fullLink);
        try
        {
            SetMountPoint(fullLink, fullTarget);
            FileAttributes attributes = File.GetAttributes(fullLink);
            if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) !=
                (FileAttributes.Directory | FileAttributes.ReparsePoint))
            {
                throw new IOException("The test junction was not materialized as a directory reparse point.");
            }

            return new DirectoryInfo(fullLink);
        }
        catch
        {
            Directory.Delete(fullLink);
            throw;
        }
    }

    private static void SetMountPoint(string linkPath, string targetPath)
    {
        string substituteName = @"\??\" + targetPath;
        byte[] substituteBytes = Encoding.Unicode.GetBytes(substituteName);
        byte[] printBytes = Encoding.Unicode.GetBytes(targetPath);
        byte[] buffer = new byte[16 + substituteBytes.Length + 2 + printBytes.Length + 2];

        BinaryPrimitives.WriteUInt32LittleEndian(buffer.AsSpan(0, 4), IoReparseTagMountPoint);
        BinaryPrimitives.WriteUInt16LittleEndian(buffer.AsSpan(4, 2), checked((ushort)(buffer.Length - 8)));
        BinaryPrimitives.WriteUInt16LittleEndian(buffer.AsSpan(8, 2), 0);
        BinaryPrimitives.WriteUInt16LittleEndian(buffer.AsSpan(10, 2), checked((ushort)substituteBytes.Length));
        BinaryPrimitives.WriteUInt16LittleEndian(
            buffer.AsSpan(12, 2),
            checked((ushort)(substituteBytes.Length + 2)));
        BinaryPrimitives.WriteUInt16LittleEndian(buffer.AsSpan(14, 2), checked((ushort)printBytes.Length));
        substituteBytes.CopyTo(buffer, 16);
        printBytes.CopyTo(buffer, 16 + substituteBytes.Length + 2);

        using SafeFileHandle handle = CreateFile(
            linkPath,
            GenericWrite,
            FileShareRead | FileShareWrite | FileShareDelete,
            IntPtr.Zero,
            OpenExisting,
            FileFlagBackupSemantics | FileFlagOpenReparsePoint,
            IntPtr.Zero);
        if (handle.IsInvalid)
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not open the test junction leaf.");
        }

        if (!DeviceIoControl(
                handle,
                FsctlSetReparsePoint,
                buffer,
                checked((uint)buffer.Length),
                IntPtr.Zero,
                0,
                out _,
                IntPtr.Zero))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not create the NTFS test junction.");
        }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DeviceIoControl(
        SafeFileHandle device,
        uint ioControlCode,
        byte[] inputBuffer,
        uint inputBufferSize,
        IntPtr outputBuffer,
        uint outputBufferSize,
        out uint bytesReturned,
        IntPtr overlapped);
}
