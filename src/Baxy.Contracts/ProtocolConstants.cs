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
    public const string SessionDisruption = "session_disruption";
    public const string WorkLoss = "work_loss";
    public const string Monetary = "monetary";
    public const string ForbiddenDestructive = "forbidden_destructive";

    public static bool IsKnown(string? value) =>
        value is ReadOnly
            or LowReversible
            or RecoverableDelete
            or PrivacySensitive
            or Installation
            or ExternalCommunication
            or SessionDisruption
            or WorkLoss
            or Monetary
            or ForbiddenDestructive;
}
