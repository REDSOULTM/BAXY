using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Security;
using System.Security.Cryptography;
using System.Text;

namespace Baxy.Security.Windows;

public sealed class WindowsProtectedPayload : IProtectedPayload
{
    public const string WindowsDpapiCurrentUserProtectionMode = "windows-dpapi-current-user";

    private const int AesKeyLength = 32;
    private const int NonceLength = 12;
    private const int TagLength = 16;
    private const int EnvelopeHeaderLength = 16;
    private const int KeyFileHeaderLength = 16;
    private const int SentinelFileLength = 48;
    private const int MaximumPlaintextLength = 16 * 1024 * 1024;
    private const int MaximumPurposeUtf8Length = 1024;
    private const int MaximumKeyFileLength = 64 * 1024;
    private const byte EnvelopeFormatVersion = 1;
    private const byte Aes256GcmAlgorithm = 1;
    private const byte KeyFileFormatVersion = 1;
    private const byte DpapiCurrentUserAlgorithm = 1;
    private const byte SentinelFormatVersion = 1;
    private const byte SentinelSha256Algorithm = 1;
    private const string SentinelSuffix = ".sentinel";

    private static readonly byte[] EnvelopeMagic = "BAXYPAY1"u8.ToArray();
    private static readonly byte[] KeyFileMagic = "BAXYKEY1"u8.ToArray();
    private static readonly byte[] SentinelMagic = "BAXYSNT1"u8.ToArray();
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly ConcurrentDictionary<string, object> KeyLocks =
        new(StringComparer.OrdinalIgnoreCase);
    private readonly object _keyLock;

    public WindowsProtectedPayload(string keyFilePath)
    {
        KeyFilePath = ProtectedPayloadPathPolicy.ValidateAndNormalize(keyFilePath);
        KeySentinelPath = ProtectedPayloadPathPolicy.ValidateAndNormalize(
            string.Concat(KeyFilePath, SentinelSuffix));
        _keyLock = KeyLocks.GetOrAdd(KeyFilePath, static _ => new object());
    }

    public string ProtectionMode => WindowsDpapiCurrentUserProtectionMode;

    public string KeyFilePath { get; }

    internal string KeySentinelPath { get; }

    public byte[] Seal(ReadOnlySpan<byte> plaintext, string purpose)
    {
        if (plaintext.Length > MaximumPlaintextLength)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.PayloadTooLarge);
        }

        byte[] purposeBytes = GetPurposeBytes(purpose);
        byte[]? key = null;
        byte[] nonce = new byte[NonceLength];
        byte[] ciphertext = new byte[plaintext.Length];
        byte[] tag = new byte[TagLength];
        try
        {
            key = LoadOrCreateKey();
            RandomNumberGenerator.Fill(nonce);
            using var aes = new AesGcm(key, TagLength);
            aes.Encrypt(nonce, plaintext, ciphertext, tag, purposeBytes);
            return CreateEnvelope(nonce, tag, ciphertext);
        }
        catch (CryptographicException)
        {
            throw new ProtectedPayloadException(
                ProtectedPayloadErrorCode.CryptographyUnavailable);
        }
        finally
        {
            if (key is not null)
            {
                CryptographicOperations.ZeroMemory(key);
            }

            CryptographicOperations.ZeroMemory(purposeBytes);
            CryptographicOperations.ZeroMemory(ciphertext);
            CryptographicOperations.ZeroMemory(tag);
        }
    }

    public byte[] Open(ReadOnlySpan<byte> envelope, string purpose)
    {
        EnvelopeParts parts = ParseEnvelope(envelope);
        byte[] purposeBytes = GetPurposeBytes(purpose);
        byte[]? key = null;
        byte[] plaintext = new byte[parts.Ciphertext.Length];
        try
        {
            key = LoadExistingKey();
            using var aes = new AesGcm(key, TagLength);
            aes.Decrypt(parts.Nonce, parts.Ciphertext, parts.Tag, plaintext, purposeBytes);
            return plaintext;
        }
        catch (CryptographicException)
        {
            CryptographicOperations.ZeroMemory(plaintext);
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidEnvelope);
        }
        finally
        {
            if (key is not null)
            {
                CryptographicOperations.ZeroMemory(key);
            }

            CryptographicOperations.ZeroMemory(purposeBytes);
        }
    }

    public byte[] SealUtf8(string plaintext, string purpose)
    {
        ArgumentNullException.ThrowIfNull(plaintext);

        byte[] plaintextBytes;
        try
        {
            plaintextBytes = StrictUtf8.GetBytes(plaintext);
        }
        catch (EncoderFallbackException)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidPlaintext);
        }

        try
        {
            return Seal(plaintextBytes, purpose);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plaintextBytes);
        }
    }

    public string OpenUtf8(ReadOnlySpan<byte> envelope, string purpose)
    {
        byte[] plaintext = Open(envelope, purpose);
        try
        {
            return StrictUtf8.GetString(plaintext);
        }
        catch (DecoderFallbackException)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidEnvelope);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plaintext);
        }
    }

    private static byte[] GetPurposeBytes(string purpose)
    {
        if (string.IsNullOrWhiteSpace(purpose)
            || purpose.Any(static character => char.IsControl(character)))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidPurpose);
        }

        try
        {
            int byteCount = StrictUtf8.GetByteCount(purpose);
            if (byteCount > MaximumPurposeUtf8Length)
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidPurpose);
            }

            return StrictUtf8.GetBytes(purpose);
        }
        catch (EncoderFallbackException)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidPurpose);
        }
    }

    private static byte[] CreateEnvelope(
        ReadOnlySpan<byte> nonce,
        ReadOnlySpan<byte> tag,
        ReadOnlySpan<byte> ciphertext)
    {
        int totalLength = checked(EnvelopeHeaderLength + NonceLength + TagLength + ciphertext.Length);
        byte[] envelope = new byte[totalLength];
        EnvelopeMagic.CopyTo(envelope, 0);
        envelope[8] = EnvelopeFormatVersion;
        envelope[9] = Aes256GcmAlgorithm;
        envelope[10] = NonceLength;
        envelope[11] = TagLength;
        BinaryPrimitives.WriteUInt32LittleEndian(
            envelope.AsSpan(12, sizeof(uint)),
            checked((uint)ciphertext.Length));
        nonce.CopyTo(envelope.AsSpan(EnvelopeHeaderLength, NonceLength));
        tag.CopyTo(envelope.AsSpan(EnvelopeHeaderLength + NonceLength, TagLength));
        ciphertext.CopyTo(envelope.AsSpan(EnvelopeHeaderLength + NonceLength + TagLength));
        return envelope;
    }

    private static EnvelopeParts ParseEnvelope(ReadOnlySpan<byte> envelope)
    {
        int minimumLength = EnvelopeHeaderLength + NonceLength + TagLength;
        if (envelope.Length < minimumLength
            || !envelope[..EnvelopeMagic.Length].SequenceEqual(EnvelopeMagic)
            || envelope[8] != EnvelopeFormatVersion
            || envelope[9] != Aes256GcmAlgorithm
            || envelope[10] != NonceLength
            || envelope[11] != TagLength)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidEnvelope);
        }

        uint encodedCiphertextLength = BinaryPrimitives.ReadUInt32LittleEndian(
            envelope.Slice(12, sizeof(uint)));
        if (encodedCiphertextLength > MaximumPlaintextLength)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.PayloadTooLarge);
        }

        int ciphertextLength = checked((int)encodedCiphertextLength);
        int expectedLength = checked(minimumLength + ciphertextLength);
        if (envelope.Length != expectedLength)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidEnvelope);
        }

        return new EnvelopeParts(
            envelope.Slice(EnvelopeHeaderLength, NonceLength),
            envelope.Slice(EnvelopeHeaderLength + NonceLength, TagLength),
            envelope.Slice(EnvelopeHeaderLength + NonceLength + TagLength, ciphertextLength));
    }

    private byte[] LoadOrCreateKey()
    {
        lock (_keyLock)
        {
            return LoadOrCreateKeyUnsafe();
        }
    }

    private byte[] LoadOrCreateKeyUnsafe()
    {
        EnsureKeyDirectory();
        if (PrivateFileExists(KeyFilePath))
        {
            return LoadExistingKey();
        }

        if (PrivateFileExists(KeySentinelPath))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        byte[] key;
        try
        {
            key = RandomNumberGenerator.GetBytes(AesKeyLength);
        }
        catch (CryptographicException)
        {
            throw new ProtectedPayloadException(
                ProtectedPayloadErrorCode.CryptographyUnavailable);
        }
        byte[]? wrappedKey = null;
        byte[]? keyFile = null;
        string? temporaryPath = null;
        try
        {
            wrappedKey = WindowsCurrentUserDpapi.Protect(key);
            keyFile = CreateKeyFile(wrappedKey);
            temporaryPath = CreateTemporaryKeyFilePath();
            if (WriteAndPublishCandidate(temporaryPath, KeyFilePath, keyFile))
            {
                temporaryPath = null;
            }

            CryptographicOperations.ZeroMemory(key);
            return LoadExistingKey();
        }
        catch (ProtectedPayloadException)
        {
            CryptographicOperations.ZeroMemory(key);
            throw;
        }
        catch (Exception exception) when (IsKeyStoreException(exception))
        {
            CryptographicOperations.ZeroMemory(key);
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.KeyStoreUnavailable);
        }
        finally
        {
            if (wrappedKey is not null)
            {
                CryptographicOperations.ZeroMemory(wrappedKey);
            }

            if (keyFile is not null)
            {
                CryptographicOperations.ZeroMemory(keyFile);
            }

            if (temporaryPath is not null)
            {
                TryDeleteTemporaryFile(temporaryPath);
            }
        }
    }

    private byte[] LoadExistingKey()
    {
        lock (_keyLock)
        {
            return LoadExistingKeyUnsafe();
        }
    }

    private byte[] LoadExistingKeyUnsafe()
    {
        byte[]? keyFile = null;
        byte[]? keyFileDigest = null;
        byte[]? key = null;
        try
        {
            keyFile = ReadKeyFile();
            // Reading an existing key must restore the directory's protected
            // DACL too. Only the seal path used to do it, so a store that had
            // been weakened after creation stayed weakened for as long as the
            // workload only read. This repairs after the read succeeds, so a
            // missing store still reports NotFound and nothing is created.
            EnsureKeyDirectory(createMissing: false);
            keyFileDigest = SHA256.HashData(keyFile);
            bool sentinelExists = PrivateFileExists(KeySentinelPath);
            if (sentinelExists)
            {
                ValidateExistingSentinel(keyFileDigest);
            }

            ReadOnlySpan<byte> wrappedKey = ParseKeyFile(keyFile);
            key = WindowsCurrentUserDpapi.Unprotect(wrappedKey);
            if (key.Length != AesKeyLength)
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
            }

            if (!sentinelExists)
            {
                PublishSentinel(keyFileDigest);
            }

            ValidateExistingSentinel(keyFileDigest);
            VerifyKeyFileStillMatches(keyFileDigest);
            byte[] result = key;
            key = null;
            return result;
        }
        catch (ProtectedPayloadException)
        {
            throw;
        }
        catch (Exception exception) when (IsKeyStoreException(exception))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.KeyStoreUnavailable);
        }
        finally
        {
            if (keyFile is not null)
            {
                CryptographicOperations.ZeroMemory(keyFile);
            }

            if (keyFileDigest is not null)
            {
                CryptographicOperations.ZeroMemory(keyFileDigest);
            }

            if (key is not null)
            {
                CryptographicOperations.ZeroMemory(key);
            }
        }
    }

    private byte[] ReadKeyFile()
    {
        string? directory = Path.GetDirectoryName(KeyFilePath);
        if (string.IsNullOrEmpty(directory) || !Directory.Exists(directory))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        if (!WindowsPrivateStorage.TryOpenFile(
                KeyFilePath,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: false,
                out WindowsPrivateFileLease? file))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        using (file)
        {
            FileStream stream = file.Stream;
            long length = stream.Length;
            if (length < KeyFileHeaderLength || length > MaximumKeyFileLength)
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
            }

            byte[] keyFile = new byte[checked((int)length)];
            try
            {
                stream.ReadExactly(keyFile);
                if (stream.ReadByte() != -1)
                {
                    throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
                }

                return keyFile;
            }
            catch
            {
                CryptographicOperations.ZeroMemory(keyFile);
                throw;
            }
        }
    }

    private void PublishSentinel(ReadOnlySpan<byte> keyFileDigest)
    {
        byte[] sentinel = CreateSentinel(keyFileDigest);
        string? temporaryPath = null;
        try
        {
            temporaryPath = CreateTemporarySentinelPath();
            if (WriteAndPublishCandidate(temporaryPath, KeySentinelPath, sentinel))
            {
                temporaryPath = null;
            }

            ValidateExistingSentinel(keyFileDigest);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(sentinel);
            if (temporaryPath is not null)
            {
                TryDeleteTemporaryFile(temporaryPath);
            }
        }
    }

    private static byte[] CreateSentinel(ReadOnlySpan<byte> keyFileDigest)
    {
        if (keyFileDigest.Length != SHA256.HashSizeInBytes)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        byte[] sentinel = new byte[SentinelFileLength];
        SentinelMagic.CopyTo(sentinel, 0);
        sentinel[8] = SentinelFormatVersion;
        sentinel[9] = SentinelSha256Algorithm;
        keyFileDigest.CopyTo(sentinel.AsSpan(16, SHA256.HashSizeInBytes));
        return sentinel;
    }

    private void ValidateExistingSentinel(ReadOnlySpan<byte> expectedKeyFileDigest)
    {
        if (!WindowsPrivateStorage.TryOpenFile(
                KeySentinelPath,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: false,
                out WindowsPrivateFileLease? file))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        byte[] sentinel = new byte[SentinelFileLength];
        try
        {
            using (file)
            {
                FileStream stream = file.Stream;
                if (stream.Length != SentinelFileLength)
                {
                    throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
                }

                stream.ReadExactly(sentinel);
                if (stream.ReadByte() != -1
                    || !sentinel.AsSpan(0, SentinelMagic.Length).SequenceEqual(SentinelMagic)
                    || sentinel[8] != SentinelFormatVersion
                    || sentinel[9] != SentinelSha256Algorithm
                    || sentinel.AsSpan(10, 6).ContainsAnyExcept((byte)0)
                    || !CryptographicOperations.FixedTimeEquals(
                        sentinel.AsSpan(16, SHA256.HashSizeInBytes),
                        expectedKeyFileDigest))
                {
                    throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
                }
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(sentinel);
        }
    }

    private void VerifyKeyFileStillMatches(ReadOnlySpan<byte> expectedDigest)
    {
        byte[] currentKeyFile = ReadKeyFile();
        byte[]? currentDigest = null;
        try
        {
            currentDigest = SHA256.HashData(currentKeyFile);
            if (!CryptographicOperations.FixedTimeEquals(currentDigest, expectedDigest))
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(currentKeyFile);
            if (currentDigest is not null)
            {
                CryptographicOperations.ZeroMemory(currentDigest);
            }
        }
    }

    private void EnsureKeyDirectory(bool createMissing = true)
    {
        try
        {
            string? directory = Path.GetDirectoryName(KeyFilePath);
            if (string.IsNullOrEmpty(directory))
            {
                throw new ProtectedPayloadException(
                    ProtectedPayloadErrorCode.InvalidKeyStorePath);
            }

            using WindowsPrivateDirectoryLease lease = WindowsPrivateStorage.AcquireDirectory(
                directory,
                createMissing,
                protectLeaf: true);
        }
        catch (ProtectedPayloadException)
        {
            throw;
        }
        catch (Exception exception) when (IsKeyStoreException(exception))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.KeyStoreUnavailable);
        }
    }

    private static byte[] CreateKeyFile(ReadOnlySpan<byte> wrappedKey)
    {
        if (wrappedKey.IsEmpty
            || wrappedKey.Length > MaximumKeyFileLength - KeyFileHeaderLength)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        byte[] keyFile = new byte[KeyFileHeaderLength + wrappedKey.Length];
        KeyFileMagic.CopyTo(keyFile, 0);
        keyFile[8] = KeyFileFormatVersion;
        keyFile[9] = DpapiCurrentUserAlgorithm;
        keyFile[10] = 0;
        keyFile[11] = 0;
        BinaryPrimitives.WriteUInt32LittleEndian(
            keyFile.AsSpan(12, sizeof(uint)),
            checked((uint)wrappedKey.Length));
        wrappedKey.CopyTo(keyFile.AsSpan(KeyFileHeaderLength));
        return keyFile;
    }

    private static ReadOnlySpan<byte> ParseKeyFile(ReadOnlySpan<byte> keyFile)
    {
        if (keyFile.Length < KeyFileHeaderLength
            || !keyFile[..KeyFileMagic.Length].SequenceEqual(KeyFileMagic)
            || keyFile[8] != KeyFileFormatVersion
            || keyFile[9] != DpapiCurrentUserAlgorithm
            || keyFile[10] != 0
            || keyFile[11] != 0)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        uint encodedLength = BinaryPrimitives.ReadUInt32LittleEndian(
            keyFile.Slice(12, sizeof(uint)));
        if (encodedLength == 0
            || encodedLength > MaximumKeyFileLength - KeyFileHeaderLength)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        int wrappedLength = checked((int)encodedLength);
        if (keyFile.Length != KeyFileHeaderLength + wrappedLength)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }

        return keyFile.Slice(KeyFileHeaderLength, wrappedLength);
    }

    private string CreateTemporaryKeyFilePath()
    {
        string directory = Path.GetDirectoryName(KeyFilePath)!;
        string fileName = Path.GetFileName(KeyFilePath);
        return Path.Combine(directory, $".{fileName}.{Guid.NewGuid():N}.tmp");
    }

    private string CreateTemporarySentinelPath()
    {
        string directory = Path.GetDirectoryName(KeySentinelPath)!;
        string fileName = Path.GetFileName(KeySentinelPath);
        return Path.Combine(directory, $".{fileName}.{Guid.NewGuid():N}.tmp");
    }

    private static bool WriteAndPublishCandidate(
        string temporaryPath,
        string targetPath,
        ReadOnlySpan<byte> bytes)
    {
        using WindowsPrivateFileLease file = WindowsPrivateStorage.CreateFile(temporaryPath);
        file.Stream.Write(bytes);
        file.Stream.Flush(flushToDisk: true);
        return WindowsPrivateStorage.Rename(
            file,
            Path.GetFileName(targetPath),
            replace: false);
    }

    private static void TryDeleteTemporaryFile(string path)
    {
        try
        {
            if (WindowsPrivateStorage.TryOpenFile(
                    path,
                    FileAccess.Read,
                    FileShare.Read,
                    deleteAccess: true,
                    out WindowsPrivateFileLease? file))
            {
                using (file)
                {
                    WindowsPrivateStorage.Delete(file);
                }
            }
        }
        catch (Exception exception) when (IsKeyStoreException(exception))
        {
            // A complete temporary candidate contains only a DPAPI-wrapped random key.
        }
    }

    private static bool IsKeyStoreException(Exception exception) => exception is IOException
        or UnauthorizedAccessException
        or SecurityException
        or NotSupportedException
        or DllNotFoundException
        or EntryPointNotFoundException;

    private static bool PrivateFileExists(string path)
    {
        if (!WindowsPrivateStorage.TryOpenFile(
                path,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: false,
                out WindowsPrivateFileLease? file))
        {
            return false;
        }

        file.Dispose();
        return true;
    }

    private readonly ref struct EnvelopeParts(
        ReadOnlySpan<byte> nonce,
        ReadOnlySpan<byte> tag,
        ReadOnlySpan<byte> ciphertext)
    {
        public ReadOnlySpan<byte> Nonce { get; } = nonce;

        public ReadOnlySpan<byte> Tag { get; } = tag;

        public ReadOnlySpan<byte> Ciphertext { get; } = ciphertext;
    }
}
