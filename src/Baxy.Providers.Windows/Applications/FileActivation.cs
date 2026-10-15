using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// cu-v3-abrir-archivo: a file goes to an application of the Start catalog the way «Abrir con» hands it one, through
/// the handler Windows lists for the file's type: no dialog, no key, no click. cu-v3-archivo-empaquetado (live v3-15,
/// v3-17, v3-18): IApplicationActivationManager::ActivateForFile refuses every packaged desktop application this PC
/// has (Fotos, Paint, Bloc de notas: 0x80270254, measured 2026-10-08), so a packaged application is handed the file by
/// invoking its listed handler (IAssocHandler::Invoke with the file's data object), which opened prueba.png in Fotos
/// and notas.txt in Bloc de notas on the same PC. The work runs on a thread of its own in a single-threaded apartment,
/// as the shell's own activations do.
/// </summary>
internal static unsafe partial class FileActivation
{
    private static readonly Guid IidShellItem = new("43826d1e-e718-42ee-bc55-a1e261c37bfe");
    private static readonly Guid IidShellItemArray = new("b63ea76d-1f85-456f-a19c-48159efa858b");
    private static readonly Guid IidDataObject = new("0000010e-0000-0000-C000-000000000046");
    private static readonly Guid BhidDataObject = new("B8C0BD9F-ED24-455c-83E6-D5390C4FE8C4");
    private static readonly Guid IidObjectWithAppUserModelId = new("36db0196-9665-46d1-9ba7-d3709eecf9ed");
    private const uint CoinitApartmentThreaded = 0x2;

    // How a file is handed to an application of the Start catalog: by its package's listed handler, by its executable
    // with the path, or not at all.
    internal enum HandOff
    {
        None,
        Package,
        Executable,
    }

    // What became of a file handed to an application: issued (the application opens it, its window decides), not
    // listed (Windows does not list the application for that type of file) or refused (listed, and Windows did not
    // manage to hand it the file).
    internal enum Outcome
    {
        Issued,
        NotListed,
        Refused,
    }

    // A handler Windows lists to open a type of file («Abrir con»): its name (an executable's full path, or the
    // application's own name for some packages), the name it shows and, for a packaged one, its application identity.
    internal sealed record Handler(string Name, string UiName, string? AppUserModelId = null);

    /// <summary>
    /// Review of cu-v3-abrir-archivo, finding 1: the file goes only to an application Windows lists as a handler of its
    /// type. A desktop application is matched by its executable's full path; a packaged one by the identity its handler
    /// reports, a handler inside its package's folder, or a handler named by its identity or its catalog name. Anything
    /// else (an interpreter, an uninstaller, a launcher that drops its shortcut's arguments) gets no file.
    /// </summary>
    internal static HandOff HandOffFor(InstalledApplicationEntry entry, string? executable, IReadOnlyList<Handler> handlers) =>
        Match(entry, executable, handlers).HandOff;

    private static (HandOff HandOff, int Index) Match(
        InstalledApplicationEntry entry, string? executable, IReadOnlyList<Handler> handlers)
    {
        int bang = entry.AppUserModelId.IndexOf('!');
        if (bang > 0)
        {
            string family = entry.AppUserModelId[..bang];
            int split = family.LastIndexOf('_');
            string? package = split > 0 ? family[..split] : null;
            string? publisher = split > 0 ? family[(split + 1)..] : null;
            for (int index = 0; index < handlers.Count; index++)
            {
                Handler handler = handlers[index];
                if (string.Equals(handler.AppUserModelId, entry.AppUserModelId, StringComparison.OrdinalIgnoreCase))
                    return (HandOff.Package, index);
                if (Path.IsPathFullyQualified(handler.Name))
                {
                    if (package is not null && publisher is not null && handler.Name.Split('\\').Any(folder =>
                            folder.StartsWith(package + "_", StringComparison.OrdinalIgnoreCase)
                            && folder.EndsWith("__" + publisher, StringComparison.OrdinalIgnoreCase)))
                        return (HandOff.Package, index);
                }
                else if (string.Equals(handler.Name, entry.AppUserModelId, StringComparison.OrdinalIgnoreCase)
                    || (string.Equals(handler.Name, entry.Name, StringComparison.OrdinalIgnoreCase)
                        && string.Equals(handler.UiName, entry.Name, StringComparison.OrdinalIgnoreCase)))
                {
                    return (HandOff.Package, index);
                }
            }

            return (HandOff.None, -1);
        }

        if (executable is null)
            return (HandOff.None, -1);
        for (int index = 0; index < handlers.Count; index++)
        {
            if (!Path.IsPathFullyQualified(handlers[index].Name))
                continue;
            try
            {
                if (string.Equals(Path.GetFullPath(handlers[index].Name), executable, StringComparison.OrdinalIgnoreCase))
                    return (HandOff.Executable, index);
            }
            catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
            {
            }
        }

        return (HandOff.None, -1);
    }

    /// <summary>
    /// The handler Windows lists for the file's type that is the entry's (HandOffFor): a packaged one is invoked with
    /// the file here (Package, and whether Windows took it); a desktop one is left to the caller (Executable), which
    /// starts its executable with the path. None: Windows lists no handler of the entry for that type.
    /// </summary>
    internal static (HandOff HandOff, bool Invoked) HandTo(InstalledApplicationEntry entry, string? executable, string filePath)
    {
        string extension = Path.GetExtension(filePath);
        if (string.IsNullOrWhiteSpace(extension))
            return (HandOff.None, false);
        var state = new HandingState();
        var thread = new Thread(() => HandOnThisThread(entry, executable, filePath, extension, state))
        {
            IsBackground = true,
            Name = "baxy-file-activation",
        };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (thread.Join(TimeSpan.FromSeconds(15)))
            return (state.HandOff, state.Invoked);
        // Review of cu-v3-abrir-archivo, finding 8: an invocation still running when the wait ends may yet open the
        // application, so it is taken as issued (never «nothing happened»): the window looked for afterwards decides.
        // One not begun is given up for good (the thread never invokes after this answer): refused, never «Windows
        // does not list it».
        return (HandOff.Package,
            Interlocked.CompareExchange(ref state.Phase, HandingState.GivenUp, HandingState.Deciding) == HandingState.Invoking);
    }

    private sealed class HandingState
    {
        internal const int Deciding = 0;
        internal const int Invoking = 1;
        internal const int GivenUp = 2;
        public int Phase;
        public volatile HandOff HandOff;
        public volatile bool Invoked;
    }

    private static void HandOnThisThread(
        InstalledApplicationEntry entry, string? executable, string filePath, string extension, HandingState state)
    {
        int initialized = CoInitializeEx(0, CoinitApartmentThreaded);
        nint enumerator = 0, item = 0, items = 0, dataObject = 0;
        var listed = new List<nint>();
        try
        {
            if (SHAssocEnumHandlers(extension, 0, out enumerator) < 0 || enumerator == 0)
                return;
            var handlers = new List<Handler>();
            // IEnumAssocHandlers: IUnknown (3), Next. IAssocHandler: IUnknown (3), GetName, GetUIName.
            var next = (delegate* unmanaged[Stdcall]<nint, uint, nint*, uint*, int>)(*(nint**)enumerator)[3];
            for (int read = 0; read < 256; read++)
            {
                nint handler = 0;
                uint fetched = 0;
                if (next(enumerator, 1, &handler, &fetched) != 0 || fetched != 1 || handler == 0)
                    break;
                // Kept in the order read (the match's index is the handler invoked); a handler without a name matches
                // no path nor name.
                listed.Add(handler);
                handlers.Add(new Handler(
                    HandlerText(handler, 3) ?? string.Empty, HandlerText(handler, 4) ?? string.Empty, AppIdOf(handler)));
            }

            (HandOff handOff, int index) = Match(entry, executable, handlers);
            state.HandOff = handOff;
            if (handOff != HandOff.Package)
                return;
            // The file as the shell hands it to «Abrir con»: one shell item, its data object.
            if (SHCreateItemFromParsingName(filePath, 0, in IidShellItem, out item) < 0 || item == 0)
                return;
            if (SHCreateShellItemArrayFromShellItem(item, in IidShellItemArray, out items) < 0 || items == 0)
                return;
            // IShellItemArray: IUnknown (3), BindToHandler.
            var bind = (delegate* unmanaged[Stdcall]<nint, nint, Guid*, Guid*, nint*, int>)(*(nint**)items)[3];
            Guid bhid = BhidDataObject, iid = IidDataObject;
            if (bind(items, 0, &bhid, &iid, &dataObject) < 0 || dataObject == 0)
                return;
            // IAssocHandler: IUnknown (3), GetName, GetUIName, GetIconLocation, IsRecommended, MakeDefault, Invoke.
            nint chosen = listed[index];
            var invoke = (delegate* unmanaged[Stdcall]<nint, nint, int>)(*(nint**)chosen)[8];
            if (Interlocked.CompareExchange(ref state.Phase, HandingState.Invoking, HandingState.Deciding) != HandingState.Deciding)
                return;
            state.Invoked = invoke(chosen, dataObject) >= 0;
        }
        finally
        {
            Release(dataObject);
            Release(items);
            Release(item);
            foreach (nint handler in listed)
                Release(handler);
            Release(enumerator);
            if (initialized >= 0)
                CoUninitialize();
        }
    }

    // The application identity a packaged handler reports (IObjectWithAppUserModelID::GetAppID); null for any other.
    private static string? AppIdOf(nint handler)
    {
        nint withId = 0;
        Guid iid = IidObjectWithAppUserModelId;
        var query = (delegate* unmanaged[Stdcall]<nint, Guid*, nint*, int>)(*(nint**)handler)[0];
        if (query(handler, &iid, &withId) < 0 || withId == 0)
            return null;
        try
        {
            // IObjectWithAppUserModelID: IUnknown (3), SetAppID, GetAppID.
            return HandlerText(withId, 4);
        }
        finally
        {
            Release(withId);
        }
    }

    private static string? HandlerText(nint handler, int slot)
    {
        nint text = 0;
        var get = (delegate* unmanaged[Stdcall]<nint, nint*, int>)(*(nint**)handler)[slot];
        if (get(handler, &text) < 0 || text == 0)
            return null;
        try
        {
            return Marshal.PtrToStringUni(text);
        }
        finally
        {
            Marshal.FreeCoTaskMem(text);
        }
    }

    private static void Release(nint pointer)
    {
        if (pointer != 0)
            _ = ((delegate* unmanaged[Stdcall]<nint, uint>)(*(nint**)pointer)[2])(pointer);
    }

    [LibraryImport("ole32.dll")]
    private static partial int CoInitializeEx(nint reserved, uint coInit);

    [LibraryImport("ole32.dll")]
    private static partial void CoUninitialize();

    [LibraryImport("shell32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int SHCreateItemFromParsingName(string path, nint bindContext, in Guid interfaceId, out nint item);

    [LibraryImport("shell32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int SHAssocEnumHandlers(string extension, int filter, out nint enumerator);

    [LibraryImport("shell32.dll")]
    private static partial int SHCreateShellItemArrayFromShellItem(nint item, in Guid interfaceId, out nint items);
}
