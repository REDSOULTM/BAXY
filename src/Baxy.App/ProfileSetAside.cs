using System.Globalization;
using System.IO;

namespace Baxy.App;

/// <summary>
/// Uso 85: a data profile the core cannot read or authenticate (CoreExitCodes.ProfileUnreadable) is the person's memory,
/// never deleted (00_IDENTIDAD: memoria y privacidad). With their Sí the whole folder is renamed beside itself with the
/// date (<c>1.respaldo-2026-11-04-153012</c>, as the notebook's Steam session did by hand) and a new profile starts in
/// its place; what was there stays readable by whoever can, exactly as it was.
/// </summary>
internal static class ProfileSetAside
{
    internal const string Marker = ".respaldo-";
    private const int Attempts = 3;
    private static readonly TimeSpan BetweenAttempts = TimeSpan.FromMilliseconds(300);

    /// <summary>Renames <paramref name="dataRoot"/> to a free sibling named by <paramref name="now"/> and returns it. A
    /// folder something still holds (an antivirus scan, an Explorer window inside it) is tried again briefly, then the
    /// failure is the caller's to say: nothing was moved.</summary>
    internal static string SetAside(string dataRoot, DateTimeOffset now)
    {
        string root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(dataRoot));
        if (!Directory.Exists(root))
        {
            throw new DirectoryNotFoundException("The data profile to set aside is missing.");
        }

        string stem = root + Marker + now.ToString("yyyy-MM-dd-HHmmss", CultureInfo.InvariantCulture);
        string target = stem;
        for (int n = 2; Directory.Exists(target) || File.Exists(target); n++)
        {
            target = stem + "-" + n.ToString(CultureInfo.InvariantCulture);
        }

        for (int attempt = 1; ; attempt++)
        {
            try
            {
                Directory.Move(root, target);
                return target;
            }
            catch (IOException) when (attempt < Attempts)
            {
                Thread.Sleep(BetweenAttempts);
            }
        }
    }
}
