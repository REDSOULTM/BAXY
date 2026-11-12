using System.IO;
using System.Net;

namespace Baxy.Installer;

/// <summary>What a download cannot wait out (PartFetcher), shared with the App's download of the tuned model.</summary>
internal static partial class Failures
{
    private const int DiskFull = 112;
    private const int HandleDiskFull = 39;

    internal static bool IsDiskFull(Exception failure) =>
        failure is IOException && (failure.HResult & 0xFFFF) is DiskFull or HandleDiskFull;

    /// <summary>The server answered, and no: not a line that went down. A timeout and «too many» do pass with time.</summary>
    internal static bool IsRefusal(HttpStatusCode status) =>
        (int)status is >= 400 and < 500 && status is not (HttpStatusCode.RequestTimeout or HttpStatusCode.TooManyRequests);
}
