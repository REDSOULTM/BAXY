using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Tests;

internal static class WindowsPathAttackTestSupport
{
    public static bool TryCreateHardLink(string linkPath, string targetPath) =>
        CreateHardLink(linkPath, targetPath, 0);

#pragma warning disable SYSLIB1054
    [DllImport("kernel32.dll", EntryPoint = "CreateHardLinkW", SetLastError = true,
        CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateHardLink(
        string fileName,
        string existingFileName,
        nint securityAttributes);
#pragma warning restore SYSLIB1054
}
