namespace Baxy.Contracts;

public static class ProtocolVersion
{
    public const string Current = "baxy.local.v1";
}

public static class ProtocolLimits
{
    // Decoded .NET string length (UTF-16 code units), independent of JSON wire bytes.
    public const int MaximumOperationResponseMessageChars = 48_000;
}

/// <summary>
/// How a core that ended before its hello says why, for the App to tell a passing failure from a terminal one.
/// </summary>
public static class CoreExitCodes
{
    /// <summary>
    /// Uso 85: the local data profile cannot be read or authenticated by this Windows account (a profile of another
    /// version, keys protected by another account or machine, a store left incomplete). Starting again cannot change
    /// that: the App stops relaunching and asks the person (sysexits EX_DATAERR).
    /// </summary>
    public const int ProfileUnreadable = 65;
}

/// <summary>
/// The hello is the core's only startup message, and the App gives up on a
/// core that does not send it within <see cref="HelloTimeout"/>. Everything the
/// core waits for before the hello fits inside that budget: the installed
/// application catalog is read from the core's first instant, beside the
/// journal check, and the hello waits for it at most <see cref="HelloCatalogWait"/>
/// from the core's start. A slower catalog leaves the hello's catalog marked
/// unverified and incomplete instead of failing the whole start. The journal
/// check is waited for at most <see cref="HelloJournalWait"/> from the start: a
/// journal that fails sooner stops the core before its hello, and one still
/// being validated then lets the hello go while every request waits for it.
/// </summary>
public static class CoreStartupBudget
{
    public static readonly TimeSpan HelloTimeout = TimeSpan.FromSeconds(10);
    public static readonly TimeSpan HelloCatalogWait = TimeSpan.FromSeconds(6);
    public static readonly TimeSpan HelloJournalWait = TimeSpan.FromSeconds(6);
}

public static class ProtocolTypes
{
    public const string Hello = "hello";
    public const string OperationRequest = "operation.request";
    public const string OperationResponse = "operation.response";
    public const string ProtocolError = "protocol.error";

    // Ajuste c3: the installed applications the core read after its hello, sent once they say other names.
    public const string ApplicationCatalogUpdate = "catalog.applications";
}

public static class OperationStatuses
{
    public const string Completed = "completed";
    public const string Failed = "failed";
    public const string Pending = "pending";
    public const string Rejected = "rejected";

    public static bool IsKnown(string? value) =>
        value is Completed or Failed or Pending or Rejected;

    public static bool IsTerminal(string? value) =>
        value is Completed or Failed or Rejected;
}

public static class ConfirmationChallengeContract
{
    public const int CurrentVersion = 1;
    public const int MaximumLifetimeSeconds = 300;
    public const string RequiredErrorCode = "confirmation_required";
}

public static class OperationRisks
{
    public const string ReadOnly = "read_only";
    public const string LowReversible = "low_reversible";
    public const string RecoverableDelete = "recoverable_delete";
    public const string PrivacySensitive = "privacy_sensitive";
    public const string Installation = "installation";
    public const string ExternalCommunication = "external_communication";
    public const string WorkLoss = "work_loss";

    public static bool IsKnown(string? value) =>
        value is ReadOnly
            or LowReversible
            or RecoverableDelete
            or PrivacySensitive
            or Installation
            or ExternalCommunication
            or WorkLoss;
}

/// <summary>
/// Where an operation's effect lands besides its risk (al máximo 5.1): <see cref="WindowInput"/> sends keys, clicks,
/// window commands or a script to a window that may be the person's; <see cref="Network"/> sends what the model wrote
/// (a query, an address, a host, a place, a title) out of the PC; <see cref="System"/> (R10.1) changes how the PC
/// connects or what it shows: a radio, a network connection or a pairing, airplane mode, the display mode. A heartbeat
/// holds them and «corrige» never fills them.
/// </summary>
public static class OperationEffects
{
    public const string WindowInput = "window_input";
    public const string Network = "network";
    public const string System = "system";

    public static bool IsKnown(string? value) => value is WindowInput or Network or System;
}
