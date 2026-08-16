using System.Collections.Concurrent;
using System.Security;
using System.Security.Cryptography;

namespace Baxy.Security.Windows;

/// <summary>
/// Persists a dedicated 256-bit journal HMAC key inside an authenticated
/// protected-payload envelope. With <see cref="WindowsProtectedPayload"/>, the
/// wrapping key is bound to DPAPI CurrentUser; the HMAC key never rests in clear.
/// </summary>
public sealed class WindowsJournalAuthenticationKeyStore
{
    public const int KeyLength = 32;

    private const int MaximumEnvelopeBytes = 4096;
    private const string Purpose = "journal.hmac-key.v2";
    private static readonly ConcurrentDictionary<string, object> KeyLocks =
        new(StringComparer.OrdinalIgnoreCase);

    private readonly string _path;
    private readonly IProtectedPayload _protector;
    private readonly object _keyLock;

    public WindowsJournalAuthenticationKeyStore(
        string path,
        IProtectedPayload protector)
    {
        ArgumentNullException.ThrowIfNull(protector);
        _path = ProtectedPayloadPathPolicy.ValidateAndNormalize(path);
        _protector = protector;
        _keyLock = KeyLocks.GetOrAdd(_path, static _ => new object());
    }

    public string Path => _path;

    public byte[] LoadOrCreate(bool allowCreate)
    {
        lock (_keyLock)
        {
            EnsureDirectory();
            if (PrivateFileExists(_path))
            {
                return LoadExisting();
            }

            if (!allowCreate)
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
            }

            byte[] key;
            try
            {
                key = RandomNumberGenerator.GetBytes(KeyLength);
            }
            catch (CryptographicException)
            {
                throw new ProtectedPayloadException(
                    ProtectedPayloadErrorCode.CryptographyUnavailable);
            }

            byte[]? envelope = null;
            string? temporaryPath = null;
            try
            {
                envelope = _protector.Seal(key, Purpose);
                if (envelope.Length is < 1 or > MaximumEnvelopeBytes)
                {
                    throw new ProtectedPayloadException(
                        ProtectedPayloadErrorCode.InvalidKeyStore);
                }

                temporaryPath = string.Concat(
                    _path,
                    ".",
                    Guid.NewGuid().ToString("N"),
                    ".tmp");
                using (WindowsPrivateFileLease candidate =
                       WindowsPrivateStorage.CreateFile(temporaryPath))
                {
                    candidate.Stream.Write(envelope);
                    candidate.Stream.Flush(flushToDisk: true);
                    if (WindowsPrivateStorage.Rename(
                            candidate,
                            System.IO.Path.GetFileName(_path),
                            replace: false))
                    {
                        temporaryPath = null;
                    }
                }

                CryptographicOperations.ZeroMemory(key);
                return LoadExisting();
            }
            catch (ProtectedPayloadException)
            {
                throw;
            }
            catch (CryptographicException)
            {
                throw new ProtectedPayloadException(
                    ProtectedPayloadErrorCode.CryptographyUnavailable);
            }
            catch (Exception exception) when (IsStorageFailure(exception))
            {
                throw new ProtectedPayloadException(
                    ProtectedPayloadErrorCode.KeyStoreUnavailable);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(key);
                if (envelope is not null)
                {
                    CryptographicOperations.ZeroMemory(envelope);
                }

                if (temporaryPath is not null)
                {
                    TryDelete(temporaryPath);
                }
            }
        }
    }

    private byte[] LoadExisting()
    {
        byte[] envelope = ReadEnvelope();
        byte[]? key = null;
        try
        {
            key = _protector.Open(envelope, Purpose);
            if (key.Length != KeyLength)
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
            }

            byte[] result = key;
            key = null;
            return result;
        }
        catch (ProtectedPayloadException)
        {
            throw;
        }
        catch (CryptographicException)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
        }
        catch (Exception exception) when (IsStorageFailure(exception))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.KeyStoreUnavailable);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(envelope);
            if (key is not null)
            {
                CryptographicOperations.ZeroMemory(key);
            }
        }
    }

    private byte[] ReadEnvelope()
    {
        if (!WindowsPrivateStorage.TryOpenFile(
                _path,
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
            if (stream.Length is < 1 or > MaximumEnvelopeBytes)
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
            }

            byte[] bytes = GC.AllocateUninitializedArray<byte>(checked((int)stream.Length));
            try
            {
                stream.ReadExactly(bytes);
                if (stream.ReadByte() != -1)
                {
                    throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStore);
                }

                return bytes;
            }
            catch
            {
                CryptographicOperations.ZeroMemory(bytes);
                throw;
            }
        }
    }

    private void EnsureDirectory()
    {
        string? directory = System.IO.Path.GetDirectoryName(_path);
        if (string.IsNullOrEmpty(directory))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidKeyStorePath);
        }

        try
        {
            using WindowsPrivateDirectoryLease lease = WindowsPrivateStorage.AcquireDirectory(
                directory,
                createMissing: true,
                protectLeaf: true);
            lease.Validate();
        }
        catch (Exception exception) when (IsStorageFailure(exception))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.KeyStoreUnavailable);
        }
    }

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

    private static void TryDelete(string path)
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
        catch (Exception exception) when (IsStorageFailure(exception))
        {
            // The candidate contains only an authenticated ciphertext envelope.
        }
    }

    private static bool IsStorageFailure(Exception exception) => exception is IOException
        or UnauthorizedAccessException
        or SecurityException
        or NotSupportedException
        or DllNotFoundException
        or EntryPointNotFoundException;
}
