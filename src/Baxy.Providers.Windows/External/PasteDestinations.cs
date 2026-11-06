using Baxy.Providers.Windows.Applications;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Encargo 94: where a paste named goes. <see cref="Window"/>: the window open under that name, as it is. Otherwise a new
/// document of <see cref="Application"/>: the application named or, with a browser named and not open
/// (<see cref="InsteadOfBrowser"/>), the PC's text editor; null then when it has none. <see cref="TextEditor"/>: the editor to
/// offer when the name answers to nothing.
/// </summary>
public sealed record PasteDestination(long Window, string? Application, bool InsteadOfBrowser, string? TextEditor)
{
    public static PasteDestination OpenWindow(long window) => new(window, null, false, null);

    public static PasteDestination NewDocument(string application, string? textEditor = null) =>
        new(0, application, false, textEditor);

    public static PasteDestination EditorForBrowser(string? textEditor) => new(0, textEditor, true, textEditor);
}

/// <summary>
/// Encargo 94 (verificación en vivo 84, F2 and F3): a paste named went only to installed applications, so a window in view
/// «was not open» (0 of 6), and a browser's name opened the person's real browser, with their session. The windows open come
/// first, by the rule of the window operations (<see cref="VisibleControlSurface.ResolveTitledWindowAsync"/>: process and
/// title), and only with none does the installed application count. An application's own name keeps its new document even
/// with its windows open: «un bloc de notas nuevo» once went into the person's open note (cu-v3-documento-nuevo), and the
/// call says nothing else that tells the two apart. No browser is launched for a paste.
/// </summary>
public sealed class PasteDestinations
{
    private readonly Func<string, bool, CancellationToken, ValueTask<long>> _namedWindow;
    private readonly Func<string, CancellationToken, ValueTask<InstalledApplicationFacts?>> _installed;
    private readonly Func<CancellationToken, ValueTask<string?>> _textEditor;

    internal PasteDestinations(
        Func<string, bool, CancellationToken, ValueTask<long>> namedWindow,
        Func<string, CancellationToken, ValueTask<InstalledApplicationFacts?>> installed,
        Func<CancellationToken, ValueTask<string?>> textEditor)
    {
        _namedWindow = namedWindow;
        _installed = installed;
        _textEditor = textEditor;
    }

    public PasteDestinations(IApplicationOpenProvider applications)
        : this(
            async (name, documents, token) =>
                await VisibleControlSurface.ResolveTitledWindowAsync(name, documents, token).ConfigureAwait(false),
            applications.InstalledFactsAsync,
            applications.PlainTextEditorAsync)
    {
    }

    public async ValueTask<PasteDestination> ResolveAsync(string name, CancellationToken cancellationToken)
    {
        InstalledApplicationFacts? installed = await _installed(name, cancellationToken).ConfigureAwait(false);
        // A document's title in any program may be the name only when no installed application bears it: «Steam - Bloc de
        // notas» is no window of Steam.
        long window = await _namedWindow(name, installed is null, cancellationToken).ConfigureAwait(false);
        if (window != 0 && (installed is null || installed.IsBrowser
            || (installed.Windows is { } itsOwn && !itsOwn.Contains(window))))
        {
            return PasteDestination.OpenWindow(window);
        }

        if (installed is { IsBrowser: true })
            return PasteDestination.EditorForBrowser(await _textEditor(cancellationToken).ConfigureAwait(false));
        return installed is not null
            ? PasteDestination.NewDocument(name)
            : PasteDestination.NewDocument(name, await _textEditor(cancellationToken).ConfigureAwait(false));
    }
}
