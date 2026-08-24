namespace Baxy.App;

/// <summary>
/// La X y el close del Field cierran la ventana, no el proceso: BAXY vive
/// en la bandeja. Sólo el menú «Salir» pide apagar de verdad.
/// </summary>
internal static class PresencePolicy
{
    internal static bool HideInsteadOfQuit(bool productHostOwnsLifetime, bool quitRequested) =>
        productHostOwnsLifetime && !quitRequested;
}
