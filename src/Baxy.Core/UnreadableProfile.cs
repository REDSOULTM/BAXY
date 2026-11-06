using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;

namespace Baxy.Core;

/// <summary>
/// Uso 85 (notebook, Steam session): a data profile of another version, or keys this Windows account cannot open,
/// stopped the core at every start (MemoryStoreCorruptException, ProtectedPayloadException) and the App took each stop
/// for a passing crash: it relaunched core and mind for ever and the person heard nothing. A local store that cannot be
/// read or authenticated is the profile's state, not a crash: the core ends with <see cref="CoreExitCodes.ProfileUnreadable"/>,
/// which the App treats as terminal. Only while Windows data protection works in this session: when it does not (the
/// notebook saw it over SSH), nothing the profile holds could be opened and the profile is not to blame.
/// </summary>
internal static class UnreadableProfile
{
    /// <summary>Any other stop (sysexits EX_SOFTWARE), as the core ended before.</summary>
    internal const int StoppedSafely = 70;

    /// <summary>Whether <paramref name="exception"/>, or one it wraps, says a local store cannot be read or trusted.</summary>
    internal static bool Is(Exception exception)
    {
        for (Exception? current = exception; current is not null; current = current.InnerException)
        {
            if (current is MemoryStoreCorruptException or JournalIntegrityException
                || current is ProtectedPayloadException
                {
                    ErrorCode: ProtectedPayloadErrorCode.InvalidKeyStore or ProtectedPayloadErrorCode.InvalidEnvelope,
                })
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>The exit code of a start a local store stopped (<see cref="Is"/>).</summary>
    internal static int ExitCode(Func<bool> protectionWorks) =>
        protectionWorks() ? CoreExitCodes.ProfileUnreadable : StoppedSafely;
}
