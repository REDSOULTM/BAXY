using System.Text;
using Baxy.Security.Windows;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Text over the byte API of <see cref="IProtectedPayload"/>, for the tests only: the product seals bytes (the memory
/// store's snapshots and the bound JSON envelopes), so the protector has no text members of its own (auditoría final 2,
/// fila 18).
/// </summary>
internal static class ProtectedPayloadText
{
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    internal static byte[] SealUtf8(this IProtectedPayload protector, string plaintext, string purpose) =>
        protector.Seal(StrictUtf8.GetBytes(plaintext), purpose);

    internal static string OpenUtf8(this IProtectedPayload protector, ReadOnlySpan<byte> envelope, string purpose) =>
        StrictUtf8.GetString(protector.Open(envelope, purpose));
}
