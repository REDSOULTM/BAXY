using System.Text.Json;

namespace Baxy.Providers.Windows.External;

public sealed record ExternalCapabilityReceipt(
    string Operation,
    bool EffectObserved,
    bool Verified,
    JsonElement? Result,
    string? ErrorCode)
{
    /// <summary>
    /// True when dispatch crossed an effect boundary but post-dispatch evidence was lost.
    /// This is intentionally separate from <see cref="EffectObserved"/>, which still means
    /// that the adapter obtained positive evidence of the effect.
    /// </summary>
    public bool EffectMayHaveOccurred { get; init; }
}

public interface IExternalCapabilityProvider
{
    ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken);
}

public sealed record InstalledGameCatalogEntry(
    string Provider,
    string AppId,
    string Name);

public sealed record InstalledGameCatalogSnapshot(
    bool Verified,
    bool Complete,
    IReadOnlyList<InstalledGameCatalogEntry> Entries);
