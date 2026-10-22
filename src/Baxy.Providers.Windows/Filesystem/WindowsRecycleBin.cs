using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// Where the previous version of a file BAXY replaces or edits goes first, so the change stays recoverable by the
/// person (Restore in the Recycle Bin) and needs no confirmation.
/// </summary>
internal interface IRecycleBin
{
    /// <summary>
    /// Sends one file or folder to the Recycle Bin. True only when it left its place and the bin of its drive gained an
    /// item; otherwise it is where it was, with the same bytes and attributes, and false is returned.
    /// </summary>
    bool Recycle(string path);
}

/// <summary>
/// The Windows Recycle Bin through the shell (SHFileOperation with undo, no interface). A drive without a bin, or a
/// file too large for it, would be deleted for good instead: a copy is kept beside the file (or the folder) until the
/// bin of the drive is seen to have grown, and put back when it did not.
/// </summary>
internal sealed partial class WindowsRecycleBin : IRecycleBin
{
    internal static readonly WindowsRecycleBin Instance = new(SendToBin, Items);

    private const uint Delete = 0x0003;
    private const ushort Silent = 0x0004;
    private const ushort NoConfirmation = 0x0010;
    private const ushort AllowUndo = 0x0040;
    private const ushort NoConfirmMakeDirectory = 0x0200;
    private const ushort NoErrorInterface = 0x0400;

    private readonly Func<string, int> _sendToBin;
    private readonly Func<string, long> _items;

    // The shell's two calls, replaceable so putting a file back can be checked without the person's bin.
    internal WindowsRecycleBin(Func<string, int> sendToBin, Func<string, long> items)
    {
        _sendToBin = sendToBin;
        _items = items;
    }

    private static void RemovePartialCopy(string keep)
    {
        try
        {
            if (Directory.Exists(keep))
            {
                foreach (string file in Directory.EnumerateFiles(keep, "*", SearchOption.AllDirectories))
                    File.SetAttributes(file, FileAttributes.Normal);
                Directory.Delete(keep, recursive: true);
            }
            else if (File.Exists(keep))
            {
                File.Delete(keep);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
        }
    }

    public bool Recycle(string path)
    {
        string full = Path.GetFullPath(path);
        string? drive = Path.GetPathRoot(full);
        string? directory = Path.GetDirectoryName(full);
        bool folder = Directory.Exists(full);
        if (string.IsNullOrEmpty(drive) || directory is null || (!folder && !File.Exists(full))) return false;
        string keep = Path.Combine(directory, ".baxy-previous-" + Guid.NewGuid().ToString("N") + ".tmp");
        // The copy waits hidden; what goes back carries the attributes the person's file (and each folder inside) had.
        var attributes = new List<(string Relative, FileAttributes Value)> { ("", File.GetAttributes(full)) };
        try
        {
            if (folder) CopyFolder(full, keep, attributes); else File.Copy(full, keep);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // FT/proveedores goal (review of receipts): a copy cut short (one file inside locked) left a visible partial
            // «.baxy-previous-…» beside the person's folder, said by nobody; the original is untouched, so the part
            // copied goes.
            RemovePartialCopy(keep);
            throw;
        }

        bool taken = false;
        try
        {
            File.SetAttributes(keep, File.GetAttributes(keep) | FileAttributes.Hidden);
            long before = _items(drive);
            if (before < 0) return false;
            int status = _sendToBin(full);
            bool gone = folder ? !Directory.Exists(full) : !File.Exists(full);
            if (status == 0 && gone && _items(drive) > before)
            {
                taken = true;
                return true;
            }
            if (gone)
            {
                if (folder) Directory.Move(keep, full); else File.Move(keep, full);
                foreach ((string relative, FileAttributes value) in attributes)
                    File.SetAttributes(Path.Combine(full, relative), value);
            }
            return false;
        }
        finally
        {
            // The copy is the person's file while neither the bin nor its own place holds it (putting it back threw,
            // or the shell's call did): it stays, no longer hidden, instead of being deleted with nothing left.
            if (!taken && !(folder ? Directory.Exists(full) : File.Exists(full)))
            {
                if (Directory.Exists(keep) || File.Exists(keep))
                    File.SetAttributes(keep, File.GetAttributes(keep) & ~FileAttributes.Hidden);
            }
            // The copy keeps a read-only file's attribute, which would refuse the deletion and leave it behind.
            else if (Directory.Exists(keep))
            {
                foreach (string file in Directory.EnumerateFiles(keep, "*", SearchOption.AllDirectories))
                    File.SetAttributes(file, FileAttributes.Normal);
                Directory.Delete(keep, recursive: true);
            }
            else if (File.Exists(keep))
            {
                File.SetAttributes(keep, FileAttributes.Normal);
                File.Delete(keep);
            }
        }
    }

    // The folder's own tree (links are not followed), for putting it back when the bin did not take it. A file copy
    // keeps the file's attributes; a folder made anew does not, so each folder's are noted for the putting back.
    private static void CopyFolder(string source, string destination, List<(string Relative, FileAttributes Value)> attributes)
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = false,
            AttributesToSkip = FileAttributes.ReparsePoint,
        };
        Directory.CreateDirectory(destination);
        foreach (string folder in Directory.EnumerateDirectories(source, "*", options))
        {
            string relative = Path.GetRelativePath(source, folder);
            Directory.CreateDirectory(Path.Combine(destination, relative));
            attributes.Add((relative, File.GetAttributes(folder)));
        }
        foreach (string file in Directory.EnumerateFiles(source, "*", options))
            File.Copy(file, Path.Combine(destination, Path.GetRelativePath(source, file)));
    }

    private static int SendToBin(string path)
    {
        // pFrom is a list ended by two NULs: the string's own terminator and this one.
        nint from = Marshal.StringToHGlobalUni(path + '\0');
        try
        {
            var operation = new FileOperation
            {
                Function = Delete,
                From = from,
                Flags = (ushort)(Silent | NoConfirmation | AllowUndo | NoConfirmMakeDirectory | NoErrorInterface),
            };
            int status = SHFileOperation(ref operation);
            return status == 0 && operation.AnyOperationsAborted != 0 ? -1 : status;
        }
        finally
        {
            Marshal.FreeHGlobal(from);
        }
    }

    private static long Items(string? drive)
    {
        var info = new RecycleBinInfo { Size = Marshal.SizeOf<RecycleBinInfo>() };
        return SHQueryRecycleBin(drive, ref info) == 0 ? info.Items : -1;
    }

    // Renew al máximo (8.3): the items in the bins of every drive (a null root asks for all of them), -1 when unread.
    internal static long AllItems() => Items(null);

    [StructLayout(LayoutKind.Sequential)]
    private struct FileOperation
    {
        public nint Window;
        public uint Function;
        public nint From;
        public nint To;
        public ushort Flags;
        public int AnyOperationsAborted;
        public nint NameMappings;
        public nint ProgressTitle;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct RecycleBinInfo
    {
        public int Size;
        public long Bytes;
        public long Items;
    }

    [LibraryImport("shell32.dll", EntryPoint = "SHFileOperationW")]
    private static partial int SHFileOperation(ref FileOperation operation);

    [LibraryImport("shell32.dll", EntryPoint = "SHQueryRecycleBinW", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int SHQueryRecycleBin(string? rootPath, ref RecycleBinInfo info);
}
