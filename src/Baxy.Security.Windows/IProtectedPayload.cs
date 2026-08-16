namespace Baxy.Security.Windows;

public interface IProtectedPayload
{
    string ProtectionMode { get; }

    byte[] Seal(ReadOnlySpan<byte> plaintext, string purpose);

    byte[] Open(ReadOnlySpan<byte> envelope, string purpose);

    byte[] SealUtf8(string plaintext, string purpose);

    string OpenUtf8(ReadOnlySpan<byte> envelope, string purpose);
}

public enum ProtectedPayloadErrorCode
{
    InvalidKeyStorePath,
    InvalidPurpose,
    InvalidPlaintext,
    PayloadTooLarge,
    InvalidEnvelope,
    InvalidKeyStore,
    KeyStoreUnavailable,
    CryptographyUnavailable,
}

public sealed class ProtectedPayloadException : Exception
{
    internal ProtectedPayloadException(ProtectedPayloadErrorCode errorCode)
        : base(GetMessage(errorCode))
    {
        ErrorCode = errorCode;
    }

    public ProtectedPayloadErrorCode ErrorCode { get; }

    private static string GetMessage(ProtectedPayloadErrorCode errorCode) => errorCode switch
    {
        ProtectedPayloadErrorCode.InvalidKeyStorePath =>
            "The protected-payload key path is not a safe local path.",
        ProtectedPayloadErrorCode.InvalidPurpose =>
            "The protected-payload purpose is invalid.",
        ProtectedPayloadErrorCode.InvalidPlaintext =>
            "The protected-payload plaintext is invalid.",
        ProtectedPayloadErrorCode.PayloadTooLarge =>
            "The protected payload exceeds its configured size limit.",
        ProtectedPayloadErrorCode.InvalidEnvelope =>
            "The protected-payload envelope is invalid or cannot be authenticated.",
        ProtectedPayloadErrorCode.InvalidKeyStore =>
            "The protected-payload key store is invalid.",
        ProtectedPayloadErrorCode.KeyStoreUnavailable =>
            "The protected-payload key store is unavailable.",
        ProtectedPayloadErrorCode.CryptographyUnavailable =>
            "The protected-payload cryptography is unavailable.",
        _ => "The protected-payload operation failed.",
    };
}
