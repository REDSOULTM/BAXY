using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// Decide si una operación necesita que el modelo escriba argumentos. BAXY Renew no los reescribe: lo que antes
/// forzaba la App (primer plano, derechos, alias) está en la descripción de la herramienta.
/// </summary>
internal static class MindArgumentNormalization
{
    internal static bool RequiresExtraction(ProductOperationDescriptor descriptor)
    {
        ArgumentNullException.ThrowIfNull(descriptor);
        return descriptor.ArgumentsSchema.Properties.Count > 0;
    }
}
