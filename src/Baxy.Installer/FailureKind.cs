using System.Net;
using System.Net.Http;
using System.Net.Sockets;

namespace Baxy.Installer;

internal enum FailureKind
{
    Disk,
    Network,
    Open,
    Damaged,
    Windows,
    Unsigned,
    Older,
    Other,
}

internal sealed class PrerequisiteException(string message, Exception? inner = null) : Exception(message, inner);

internal sealed class NotRegisteredException(string message, Exception inner) : Exception(message, inner);

/// <summary>The cause the person is told: said plainly, with what they can do about it.</summary>
internal static partial class Failures
{
    internal static FailureKind Classify(Exception failure, Func<bool> baxyIsOpen) => failure switch
    {
        InstallBlockedException => baxyIsOpen() ? FailureKind.Open : FailureKind.Other,
        UnsignedReleaseException => FailureKind.Unsigned,
        OlderReleaseException => FailureKind.Older,
        PrerequisiteException => FailureKind.Windows,
        InvalidDataException => FailureKind.Damaged,
        HttpRequestException { StatusCode: { } status } when IsRefusal(status) => FailureKind.Other,
        HttpRequestException or OperationCanceledException or HttpIOException => FailureKind.Network,
        IOException { InnerException: SocketException } => FailureKind.Network,
        _ when IsDiskFull(failure) => FailureKind.Disk,
        _ => FailureKind.Other,
    };

    internal static string VoiceLine(FailureKind kind) => kind switch
    {
        FailureKind.Disk => "failDisk",
        FailureKind.Network => "failNetwork",
        FailureKind.Open => "failOpen",
        FailureKind.Damaged => "failDamaged",
        FailureKind.Windows => "failWindows",
        _ => "failOther",
    };
}
