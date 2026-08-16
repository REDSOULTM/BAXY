using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace Baxy.Security.Windows;

internal static partial class WindowsCurrentUserDpapi
{
    private const uint CryptProtectUiForbidden = 0x1;
    private const uint MaximumDpapiOutputLength = 64 * 1024;

    public static byte[] Protect(ReadOnlySpan<byte> plaintext) =>
        Invoke(plaintext, protect: true);

    public static byte[] Unprotect(ReadOnlySpan<byte> protectedData) =>
        Invoke(protectedData, protect: false);

    private static unsafe byte[] Invoke(ReadOnlySpan<byte> input, bool protect)
    {
        if (!OperatingSystem.IsWindows() || input.IsEmpty)
        {
            throw new ProtectedPayloadException(
                ProtectedPayloadErrorCode.CryptographyUnavailable);
        }

        fixed (byte* inputPointer = input)
        {
            var inputBlob = new NativeDataBlob(
                checked((uint)input.Length),
                (nint)inputPointer);
            int result;
            NativeDataBlob outputBlob;
            try
            {
                result = protect
                    ? CryptProtectData(
                        in inputBlob,
                        0,
                        0,
                        0,
                        0,
                        CryptProtectUiForbidden,
                        out outputBlob)
                    : CryptUnprotectData(
                        in inputBlob,
                        0,
                        0,
                        0,
                        0,
                        CryptProtectUiForbidden,
                        out outputBlob);
            }
            catch (Exception exception) when (exception is DllNotFoundException
                or EntryPointNotFoundException)
            {
                throw new ProtectedPayloadException(
                    ProtectedPayloadErrorCode.CryptographyUnavailable);
            }

            if (result == 0 || outputBlob.Data == 0 || outputBlob.Length == 0)
            {
                if (outputBlob.Data != 0)
                {
                    if (protect)
                    {
                        _ = LocalFree(outputBlob.Data);
                    }
                    else
                    {
                        ZeroAndFree(outputBlob);
                    }
                }

                throw new ProtectedPayloadException(
                    protect
                        ? ProtectedPayloadErrorCode.CryptographyUnavailable
                        : ProtectedPayloadErrorCode.InvalidKeyStore);
            }

            if (outputBlob.Length > MaximumDpapiOutputLength)
            {
                ZeroAndFree(outputBlob);
                throw new ProtectedPayloadException(
                    ProtectedPayloadErrorCode.CryptographyUnavailable);
            }

            byte[] output = new byte[checked((int)outputBlob.Length)];
            try
            {
                Marshal.Copy(outputBlob.Data, output, 0, output.Length);
                return output;
            }
            finally
            {
                if (!protect)
                {
                    ZeroAndFree(outputBlob);
                }
                else
                {
                    _ = LocalFree(outputBlob.Data);
                }
            }
        }
    }

    private static unsafe void ZeroAndFree(NativeDataBlob blob)
    {
        if (blob.Data == 0)
        {
            return;
        }

        if (blob.Length <= int.MaxValue)
        {
            CryptographicOperations.ZeroMemory(
                new Span<byte>((void*)blob.Data, checked((int)blob.Length)));
        }

        _ = LocalFree(blob.Data);
    }

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct NativeDataBlob(uint length, nint data)
    {
        public readonly uint Length = length;
        public readonly nint Data = data;
    }

    [LibraryImport("crypt32.dll", SetLastError = true)]
    private static partial int CryptProtectData(
        in NativeDataBlob dataIn,
        nint dataDescription,
        nint optionalEntropy,
        nint reserved,
        nint promptStructure,
        uint flags,
        out NativeDataBlob dataOut);

    [LibraryImport("crypt32.dll", SetLastError = true)]
    private static partial int CryptUnprotectData(
        in NativeDataBlob dataIn,
        nint dataDescription,
        nint optionalEntropy,
        nint reserved,
        nint promptStructure,
        uint flags,
        out NativeDataBlob dataOut);

    [LibraryImport("kernel32.dll")]
    private static partial nint LocalFree(nint memory);
}
