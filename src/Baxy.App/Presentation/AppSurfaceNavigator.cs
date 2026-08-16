namespace Baxy.App.Presentation;

internal interface IAppSurfacePresenter
{
    void ShowField();

    void ShowSurface(AppSurfaceSession session);
}

internal sealed class AppSurfaceNavigator : IAsyncDisposable
{
    private readonly AppSurfaceCatalog _catalog;
    private readonly IAppSurfacePresenter _presenter;
    private readonly SemaphoreSlim _transition = new(1, 1);
    private AppSurfaceSession? _current;
    private string _currentId = AppSurfaceIds.HistoricalField;
    private bool _disposed;

    internal AppSurfaceNavigator(
        AppSurfaceCatalog catalog,
        IAppSurfacePresenter presenter)
    {
        _catalog = catalog ?? throw new ArgumentNullException(nameof(catalog));
        _presenter = presenter ?? throw new ArgumentNullException(nameof(presenter));
    }

    internal string CurrentId => _currentId;

    internal async ValueTask<AppSurfaceSession?> OpenAsync(
        string id,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(id);
        await _transition.WaitAsync(cancellationToken);
        try
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            return await OpenCoreAsync(id);
        }
        finally
        {
            _transition.Release();
        }
    }

    internal async ValueTask<AppSurfaceSession?> OpenFromFieldAsync(
        string id,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(id);
        await _transition.WaitAsync(cancellationToken);
        try
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            if (_currentId != AppSurfaceIds.HistoricalField
                && _currentId != id)
            {
                return null;
            }

            return await OpenCoreAsync(id);
        }
        finally
        {
            _transition.Release();
        }
    }

    internal async ValueTask ReturnToFieldAsync(
        CancellationToken cancellationToken = default)
    {
        await _transition.WaitAsync(cancellationToken);
        try
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            await ReturnToFieldCoreAsync().ConfigureAwait(false);
        }
        finally
        {
            _transition.Release();
        }
    }

    internal async ValueTask<bool> ReturnToFieldIfCurrentAsync(
        AppSurfaceSession expected,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(expected);
        await _transition.WaitAsync(cancellationToken);
        try
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            if (!ReferenceEquals(_current, expected))
            {
                return false;
            }

            await ReturnToFieldCoreAsync().ConfigureAwait(false);
            return true;
        }
        finally
        {
            _transition.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        await _transition.WaitAsync();
        try
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            await ReturnToFieldCoreAsync().ConfigureAwait(false);
        }
        finally
        {
            _transition.Release();
        }
    }

    private async ValueTask<AppSurfaceSession?> OpenCoreAsync(string id)
    {
        if (id == _currentId)
        {
            return _current;
        }

        if (!_catalog.TryCreate(id, out AppSurfaceSession? candidate))
        {
            return null;
        }

        AppSurfaceSession? previous = _current;
        if (previous is not null)
        {
            try
            {
                _presenter.ShowField();
                _current = null;
                _currentId = AppSurfaceIds.HistoricalField;
                await previous.DisposeAsync();
            }
            catch
            {
                await candidate.DisposeAsync().ConfigureAwait(false);
                throw;
            }
        }

        try
        {
            _presenter.ShowSurface(candidate);
        }
        catch
        {
            try
            {
                _presenter.ShowField();
            }
            finally
            {
                await candidate.DisposeAsync();
            }
            throw;
        }

        _current = candidate;
        _currentId = id;
        return candidate;
    }

    private async ValueTask ReturnToFieldCoreAsync()
    {
        if (_current is null)
        {
            return;
        }

        _presenter.ShowField();
        AppSurfaceSession previous = _current;
        _current = null;
        _currentId = AppSurfaceIds.HistoricalField;
        await previous.DisposeAsync().ConfigureAwait(false);
    }
}
