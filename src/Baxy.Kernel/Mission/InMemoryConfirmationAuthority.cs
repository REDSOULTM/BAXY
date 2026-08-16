using System.Security.Cryptography;
using System.Text;
using Baxy.Contracts;

namespace Baxy.Kernel.Mission;

internal enum ConfirmationAuthorizationStatus
{
    Granted,
    ChallengeRequired,
}

internal sealed record ConfirmationChallenge(
    string Token,
    DateTimeOffset ExpiresAtUtc)
{
    public override string ToString() =>
        $"{nameof(ConfirmationChallenge)} {{ Token = [REDACTED], ExpiresAtUtc = {ExpiresAtUtc:O} }}";
}

internal sealed record ConfirmationAuthorization(
    ConfirmationAuthorizationStatus Status,
    ConfirmationChallenge? Challenge)
{
    internal static ConfirmationAuthorization Granted { get; } =
        new(ConfirmationAuthorizationStatus.Granted, null);

    public override string ToString() =>
        $"{nameof(ConfirmationAuthorization)} {{ Status = {Status}, Challenge = "
        + (Challenge is null ? "null" : "[REDACTED]")
        + " }";
}

internal readonly record struct ConfirmationBinding(
    string InvocationId,
    string MissionId,
    string RequestFingerprint)
{
    internal static ConfirmationBinding Create(
        OperationRequest request,
        string requestFingerprint) =>
        new(request.InvocationId, request.MissionId, requestFingerprint);
}

internal sealed class InMemoryConfirmationAuthority : IDisposable
{
    internal const int DefaultCapacity = 64;
    internal const int MaximumCapacity = 64;
    internal static readonly TimeSpan DefaultLifetime = TimeSpan.FromMinutes(2);
    internal static readonly TimeSpan MaximumLifetime =
        TimeSpan.FromSeconds(ConfirmationChallengeContract.MaximumLifetimeSeconds);

    private const int SecretSize = 32;
    private const int NonceSize = 32;
    private const string DerivationDomain = "baxy.confirmation.v1";

    private readonly object _sync = new();
    private readonly TimeProvider _timeProvider;
    private readonly TimeSpan _lifetime;
    private readonly int _capacity;
    private readonly byte[] _derivationKey = RandomNumberGenerator.GetBytes(SecretSize);
    private readonly Dictionary<ConfirmationBinding, ChallengeEntry> _entries = [];
    private readonly LinkedList<ConfirmationBinding> _issuanceOrder = [];
    private bool _disposed;

    internal InMemoryConfirmationAuthority(
        TimeProvider? timeProvider = null,
        TimeSpan? lifetime = null,
        int capacity = DefaultCapacity)
    {
        if (capacity is <= 0 or > MaximumCapacity)
        {
            throw new ArgumentOutOfRangeException(
                nameof(capacity),
                $"Confirmation capacity must be between 1 and {MaximumCapacity}.");
        }

        TimeSpan effectiveLifetime = lifetime ?? DefaultLifetime;
        if (effectiveLifetime <= TimeSpan.Zero || effectiveLifetime > MaximumLifetime)
        {
            throw new ArgumentOutOfRangeException(
                nameof(lifetime),
                $"Confirmation lifetime must be positive and no longer than {MaximumLifetime}.");
        }

        _timeProvider = timeProvider ?? TimeProvider.System;
        _lifetime = effectiveLifetime;
        _capacity = capacity;
    }

    internal ConfirmationAuthorization AuthorizeOrIssue(
        ConfirmationBinding binding,
        string? presentedToken)
    {
        lock (_sync)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);

            DateTimeOffset now = _timeProvider.GetUtcNow().ToUniversalTime();
            RemoveExpired(now);

            if (_entries.TryGetValue(binding, out ChallengeEntry? existing))
            {
                if (presentedToken is not null && TokenMatches(existing, presentedToken))
                {
                    return ConfirmationAuthorization.Granted;
                }

                return ChallengeRequired(binding, existing);
            }

            if (_entries.Count >= _capacity)
            {
                EvictOldest();
            }

            LinkedListNode<ConfirmationBinding> orderNode = _issuanceOrder.AddLast(binding);
            var entry = new ChallengeEntry(
                RandomNumberGenerator.GetBytes(NonceSize),
                [],
                now.Add(_lifetime),
                orderNode);
            byte[] token = DeriveToken(binding, entry);
            try
            {
                entry.TokenHash = SHA256.HashData(token);
                _entries.Add(binding, entry);
                return new ConfirmationAuthorization(
                    ConfirmationAuthorizationStatus.ChallengeRequired,
                    new ConfirmationChallenge(EncodeBase64Url(token), entry.ExpiresAtUtc));
            }
            finally
            {
                CryptographicOperations.ZeroMemory(token);
            }
        }
    }

    internal void Revoke(ConfirmationBinding binding)
    {
        lock (_sync)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            Remove(binding);
        }
    }

    internal int ActiveChallengeCount
    {
        get
        {
            lock (_sync)
            {
                ObjectDisposedException.ThrowIf(_disposed, this);
                RemoveExpired(_timeProvider.GetUtcNow().ToUniversalTime());
                return _entries.Count;
            }
        }
    }

    public void Dispose()
    {
        lock (_sync)
        {
            if (_disposed)
            {
                return;
            }

            foreach (ChallengeEntry entry in _entries.Values)
            {
                Clear(entry);
            }

            _entries.Clear();
            _issuanceOrder.Clear();
            CryptographicOperations.ZeroMemory(_derivationKey);
            _disposed = true;
        }
    }

    private ConfirmationAuthorization ChallengeRequired(
        ConfirmationBinding binding,
        ChallengeEntry entry)
    {
        byte[] token = DeriveToken(binding, entry);
        try
        {
            return new ConfirmationAuthorization(
                ConfirmationAuthorizationStatus.ChallengeRequired,
                new ConfirmationChallenge(EncodeBase64Url(token), entry.ExpiresAtUtc));
        }
        finally
        {
            CryptographicOperations.ZeroMemory(token);
        }
    }

    private byte[] DeriveToken(ConfirmationBinding binding, ChallengeEntry entry)
    {
        // This reconstructs the active bearer from process-only key material so the
        // authority can reissue a challenge while retaining only its verification hash.
        string materialText = string.Join(
            '\n',
            DerivationDomain,
            binding.InvocationId,
            binding.MissionId,
            binding.RequestFingerprint,
            entry.ExpiresAtUtc.UtcTicks.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Convert.ToHexString(entry.Nonce));
        byte[] material = Encoding.UTF8.GetBytes(materialText);
        try
        {
            return HMACSHA256.HashData(_derivationKey, material);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(material);
        }
    }

    private static bool TokenMatches(ChallengeEntry entry, string presentedToken)
    {
        byte[]? token = DecodeBase64Url(presentedToken);
        if (token is null)
        {
            return false;
        }

        try
        {
            byte[] presentedHash = SHA256.HashData(token);
            try
            {
                return CryptographicOperations.FixedTimeEquals(
                    presentedHash,
                    entry.TokenHash);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(presentedHash);
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(token);
        }
    }

    private static string EncodeBase64Url(ReadOnlySpan<byte> value) =>
        Convert.ToBase64String(value)
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');

    private static byte[]? DecodeBase64Url(string value)
    {
        if (value.Length == 0 || value.Length % 4 == 1)
        {
            return null;
        }

        string padded = (value.Length % 4) switch
        {
            0 => value,
            2 => value + "==",
            3 => value + "=",
            _ => value,
        };

        try
        {
            return Convert.FromBase64String(padded.Replace('-', '+').Replace('_', '/'));
        }
        catch (FormatException)
        {
            return null;
        }
    }

    private void RemoveExpired(DateTimeOffset now)
    {
        foreach (ConfirmationBinding binding in _entries
                     .Where(pair => now >= pair.Value.ExpiresAtUtc)
                     .Select(static pair => pair.Key)
                     .ToArray())
        {
            Remove(binding);
        }
    }

    private void EvictOldest()
    {
        LinkedListNode<ConfirmationBinding>? oldest = _issuanceOrder.First;
        if (oldest is null || !Remove(oldest.Value))
        {
            throw new InvalidOperationException("Confirmation capacity tracking is inconsistent.");
        }
    }

    private bool Remove(ConfirmationBinding binding)
    {
        if (!_entries.Remove(binding, out ChallengeEntry? entry))
        {
            return false;
        }

        _issuanceOrder.Remove(entry.OrderNode);
        Clear(entry);
        return true;
    }

    private static void Clear(ChallengeEntry entry)
    {
        CryptographicOperations.ZeroMemory(entry.Nonce);
        CryptographicOperations.ZeroMemory(entry.TokenHash);
    }

    private sealed class ChallengeEntry(
        byte[] nonce,
        byte[] tokenHash,
        DateTimeOffset expiresAtUtc,
        LinkedListNode<ConfirmationBinding> orderNode)
    {
        internal byte[] Nonce { get; } = nonce;

        internal byte[] TokenHash { get; set; } = tokenHash;

        internal DateTimeOffset ExpiresAtUtc { get; } = expiresAtUtc;

        internal LinkedListNode<ConfirmationBinding> OrderNode { get; } = orderNode;
    }
}
