using System.Runtime.InteropServices;
using System.Runtime.InteropServices.Marshalling;

namespace Baxy.Installer;

/// <summary>Writes a Windows shortcut through the shell's own COM object, with source-generated interop for NativeAOT.</summary>
internal static unsafe partial class ShellLink
{
    private const uint InProcessServer = 0x1;
    private static readonly Guid ShellLinkClass = new("00021401-0000-0000-C000-000000000046");
    private static readonly Guid ShellLinkInterface = new("000214F9-0000-0000-C000-000000000046");

    internal static void Write(string linkPath, string target, string description)
    {
        Guid classId = ShellLinkClass;
        Guid interfaceId = ShellLinkInterface;
        Marshal.ThrowExceptionForHR(CoCreateInstance(ref classId, 0, InProcessServer, ref interfaceId, out nint created));
        try
        {
            StrategyBasedComWrappers wrappers = new();
            object instance = wrappers.GetOrCreateObjectForComInstance(created, CreateObjectFlags.None);
            IShellLinkW link = (IShellLinkW)instance;
            Marshal.ThrowExceptionForHR(link.SetPath(target));
            Marshal.ThrowExceptionForHR(link.SetWorkingDirectory(Path.GetDirectoryName(target)!));
            Marshal.ThrowExceptionForHR(link.SetDescription(description));
            Marshal.ThrowExceptionForHR(link.SetIconLocation(target, 0));
            Marshal.ThrowExceptionForHR(((IPersistFile)instance).Save(linkPath, remember: true));
        }
        finally
        {
            Marshal.Release(created);
        }
    }

    [LibraryImport("ole32.dll")]
    private static partial int CoCreateInstance(ref Guid classId, nint outer, uint context, ref Guid interfaceId, out nint instance);

    [GeneratedComInterface(StringMarshalling = StringMarshalling.Utf16)]
    [Guid("000214F9-0000-0000-C000-000000000046")]
    internal partial interface IShellLinkW
    {
        [PreserveSig] int GetPath(nint file, int length, nint data, uint flags);
        [PreserveSig] int GetIDList(out nint list);
        [PreserveSig] int SetIDList(nint list);
        [PreserveSig] int GetDescription(nint name, int length);
        [PreserveSig] int SetDescription(string name);
        [PreserveSig] int GetWorkingDirectory(nint directory, int length);
        [PreserveSig] int SetWorkingDirectory(string directory);
        [PreserveSig] int GetArguments(nint arguments, int length);
        [PreserveSig] int SetArguments(string arguments);
        [PreserveSig] int GetHotkey(out ushort hotkey);
        [PreserveSig] int SetHotkey(ushort hotkey);
        [PreserveSig] int GetShowCmd(out int show);
        [PreserveSig] int SetShowCmd(int show);
        [PreserveSig] int GetIconLocation(nint path, int length, out int index);
        [PreserveSig] int SetIconLocation(string path, int index);
        [PreserveSig] int SetRelativePath(string path, uint reserved);
        [PreserveSig] int Resolve(nint window, uint flags);
        [PreserveSig] int SetPath(string file);
    }

    [GeneratedComInterface(StringMarshalling = StringMarshalling.Utf16)]
    [Guid("0000010B-0000-0000-C000-000000000046")]
    internal partial interface IPersistFile
    {
        [PreserveSig] int GetClassID(out Guid classId);
        [PreserveSig] int IsDirty();
        [PreserveSig] int Load(string file, uint mode);
        [PreserveSig] int Save(string file, [MarshalAs(UnmanagedType.Bool)] bool remember);
        [PreserveSig] int SaveCompleted(string file);
        [PreserveSig] int GetCurFile(out nint file);
    }
}
