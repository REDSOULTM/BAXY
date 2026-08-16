using System.Collections.Frozen;
using System.Diagnostics.CodeAnalysis;
using System.Windows;

namespace Baxy.App.Presentation;

internal static class AppSurfaceIds
{
    internal const string HistoricalField = "field";
    internal const string FieldLoading = "field.loading";
}

internal sealed record AppSurfaceDescriptor(
    string Id,
    Func<AppSurfaceSession> Create);

internal sealed class AppSurfaceSession : IAsyncDisposable
{
    private IAsyncDisposable? _lifetime;

    internal AppSurfaceSession(
        FrameworkElement content,
        IAsyncDisposable? lifetime = null)
    {
        Content = content ?? throw new ArgumentNullException(nameof(content));
        _lifetime = lifetime;
    }

    internal FrameworkElement Content { get; }

    public async ValueTask DisposeAsync()
    {
        IAsyncDisposable? lifetime = Interlocked.Exchange(ref _lifetime, null);
        if (lifetime is not null)
        {
            await lifetime.DisposeAsync().ConfigureAwait(false);
        }
    }
}

internal sealed class AppSurfaceCatalog
{
    private const int MaximumSurfaceIdLength = 80;
    private readonly FrozenDictionary<string, AppSurfaceDescriptor> _descriptors;

    internal AppSurfaceCatalog(IEnumerable<AppSurfaceDescriptor> descriptors)
    {
        ArgumentNullException.ThrowIfNull(descriptors);
        var byId = new Dictionary<string, AppSurfaceDescriptor>(
            StringComparer.Ordinal);
        foreach (AppSurfaceDescriptor descriptor in descriptors)
        {
            ArgumentNullException.ThrowIfNull(descriptor);
            ArgumentNullException.ThrowIfNull(descriptor.Create);
            if (!IsValidId(descriptor.Id))
            {
                throw new ArgumentException(
                    $"Invalid application surface id '{descriptor.Id}'.",
                    nameof(descriptors));
            }

            if (descriptor.Id == AppSurfaceIds.HistoricalField)
            {
                throw new ArgumentException(
                    "The historical field id is reserved for the default surface.",
                    nameof(descriptors));
            }

            if (!byId.TryAdd(descriptor.Id, descriptor))
            {
                throw new ArgumentException(
                    $"Duplicate application surface id '{descriptor.Id}'.",
                    nameof(descriptors));
            }
        }

        _descriptors = byId.ToFrozenDictionary(StringComparer.Ordinal);
    }

    internal IReadOnlyCollection<string> Ids => _descriptors.Keys;

    internal static AppSurfaceCatalog CreateDefault() =>
        new(
        [
            new AppSurfaceDescriptor(
                AppSurfaceIds.FieldLoading,
                static () => new AppSurfaceSession(new FieldLoadingSurface())),
        ]);

    internal bool TryCreate(
        string id,
        [NotNullWhen(true)] out AppSurfaceSession? session)
    {
        session = null;
        if (!_descriptors.TryGetValue(id, out AppSurfaceDescriptor? descriptor))
        {
            return false;
        }

        session = descriptor.Create()
            ?? throw new InvalidOperationException(
                $"Application surface factory '{id}' returned no session.");
        return true;
    }

    private static bool IsValidId(string id)
    {
        if (string.IsNullOrWhiteSpace(id)
            || id.Length > MaximumSurfaceIdLength
            || !IsLowerAsciiLetter(id[0])
            || id[^1] is '.' or '-')
        {
            return false;
        }

        bool previousWasSeparator = false;
        foreach (char character in id)
        {
            bool separator = character is '.' or '-';
            if (!(IsLowerAsciiLetter(character)
                    || char.IsAsciiDigit(character)
                    || separator)
                || separator && previousWasSeparator)
            {
                return false;
            }

            previousWasSeparator = separator;
        }

        return true;
    }

    private static bool IsLowerAsciiLetter(char value) =>
        value is >= 'a' and <= 'z';
}
