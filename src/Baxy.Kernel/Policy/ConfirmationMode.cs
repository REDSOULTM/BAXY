namespace Baxy.Kernel.Policy;

/// <summary>
/// Un ajuste, dos valores, el mismo camino de autorización.
/// Normal confirma sólo destrucción de datos. Bypass no confirma nada.
/// Ninguno relaja efectos no pedidos ni éxitos no verificados.
/// </summary>
public enum ConfirmationMode
{
    Normal,
    Bypass,
}
