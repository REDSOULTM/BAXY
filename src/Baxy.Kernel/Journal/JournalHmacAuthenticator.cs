using System.Security.Cryptography;

namespace Baxy.Kernel.Journal;

/// <summary>
/// Owns a copy of a 256-bit journal authentication key. The caller should obtain
/// the key from a protected platform store and erase its source buffer after
/// construction.
/// </summary>
public sealed class JournalHmacAuthenticator : IDisposable
{
    public const int KeyLength = 32;
    public const string Algorithm = "hmac-sha256";

    private byte[]? _key;

    public JournalHmacAuthenticator(ReadOnlySpan<byte> key)
    {
        if (key.Length != KeyLength)
        {
            throw new ArgumentException(
                "The journal authentication key must contain exactly 256 bits.",
                nameof(key));
        }

        _key = key.ToArray();
    }

    internal JournalHmacAuthenticator Clone()
    {
        byte[] key = _key ?? throw new ObjectDisposedException(nameof(JournalHmacAuthenticator));
        return new JournalHmacAuthenticator(key);
    }

    internal string ComputeTag(string domain, ReadOnlySpan<byte> canonicalPayload)
    {
        byte[] key = _key ?? throw new ObjectDisposedException(nameof(JournalHmacAuthenticator));
        if (string.IsNullOrEmpty(domain) || !domain.All(static value => value is >= 'a' and <= 'z' or >= '0' and <= '9' or '.'))
        {
            throw new ArgumentException("The journal authentication domain is invalid.", nameof(domain));
        }

        int domainLength = domain.Length;
        byte[] material = GC.AllocateUninitializedArray<byte>(
            checked(domainLength + 1 + canonicalPayload.Length));
        try
        {
            for (int index = 0; index < domainLength; index++)
            {
                material[index] = checked((byte)domain[index]);
            }

            material[domainLength] = 0;
            canonicalPayload.CopyTo(material.AsSpan(domainLength + 1));
            byte[] tag = HMACSHA256.HashData(key, material);
            try
            {
                return Convert.ToHexStringLower(tag);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(tag);
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(material);
        }
    }

    public void Dispose()
    {
        byte[]? key = Interlocked.Exchange(ref _key, null);
        if (key is not null)
        {
            CryptographicOperations.ZeroMemory(key);
        }
    }
}
