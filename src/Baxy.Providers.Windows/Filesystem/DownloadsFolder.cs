using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// FT/proveedores goal (review of receipts): the person's Downloads folder as Windows knows it (FOLDERID_Downloads,
/// SHGetKnownFolderPath), which follows a moved or redirected Downloads; the profile's «Downloads» was assumed, so a
/// moved one was «unavailable», or an old one left behind was read and written as if it were Downloads. Falls back to
/// the profile's when Windows does not answer.
/// </summary>
internal static partial class DownloadsFolder
{
    private static readonly Guid Downloads = new("374de290-123f-4565-9164-39c4925e467b");

    internal static string Path()
    {
        try
        {
            if (SHGetKnownFolderPath(in Downloads, 0, 0, out nint path) == 0)
            {
                try
                {
                    string? known = Marshal.PtrToStringUni(path);
                    if (!string.IsNullOrWhiteSpace(known))
                        return known;
                }
                finally
                {
                    Marshal.FreeCoTaskMem(path);
                }
            }
        }
        catch (Exception exception) when (exception is DllNotFoundException or EntryPointNotFoundException)
        {
        }

        return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads");
    }

    [LibraryImport("shell32.dll")]
    private static partial int SHGetKnownFolderPath(in Guid folderId, uint flags, nint token, out nint path);
}
