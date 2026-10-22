using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    // Renew al máximo (guarda diálogo destructivo): falsedades F013, the model pressed «Sí» in «Confirmar Guardar como:
    // prueba.txt ya existe. ¿Quieres reemplazarlo?» and a file was written over without asking; RiskPolicy judges only
    // the label, and «Sí» says nothing by itself. A dialog whose own words ask about replacing, overwriting, deleting,
    // discarding, not saving or losing changes makes its affirmative button an act that cannot be undone. Told by verbs,
    // in Spanish and English, folded (FoldTitle); never by an application's name. Saving destroys nothing.

    /// <summary>
    /// The window is a dialog: Windows' dialog class, or a window another one owns (a modal dialog over its owner).
    /// </summary>
    internal static bool IsDialogWindow(nint window) =>
        window != 0 && (string.Equals(ClassName(window), "#32770", StringComparison.Ordinal) || GetWindow(window, 4) != 0);

    /// <summary>A button that says yes to what its dialog asks (Sí, Yes, Aceptar, OK, Reemplazar, Eliminar, No guardar…).</summary>
    internal static bool AffirmativeAnswer(string? label) => AffirmativeLabel().IsMatch(FoldTitle(label));

    /// <summary>
    /// What a dialog says (its title and the texts it shows, never its buttons) asks about destroying something: a
    /// file replaced or overwritten, something deleted, erased or sent to the bin, changes discarded, not saved or lost.
    /// </summary>
    internal static bool AsksToDestroy(IEnumerable<string?> said) =>
        said.Any(text => DestructiveQuestion().IsMatch(FoldTitle(text)));

    // Folded: lower case, no accents. A trailing access key («Sí (S)», «Yes (Y)») is part of the button's name.
    [GeneratedRegex(
        @"^(?:(?:si|yes|aceptar|ok|okay)|(?:reemplaz\w*|replace|sobre?scrib\w*|overwrite|elimin\w*|delete|borrar|borra|descart\w*|discard|no\s+guardar|no\s+guardes|don'?t\s+save|do\s+not\s+save)(?:\s+\S+){0,4})(?:\s*\(\w\))?$",
        RegexOptions.CultureInvariant)]
    private static partial Regex AffirmativeLabel();

    // The verb forms only: «borrador» (a draft) or «descargar» do not count.
    [GeneratedRegex(
        @"\b(?:reemplaz\w*|sobre?scrib\w*|elimin\w*|borr(?:ar|arlo|arla|arlos|arlas|a|an|ara|aran|ado|ada|ados|adas|e|en)\b|descart\w*|no\s+guard\w*|sin\s+guardar|perd(?:er|era|eran|eras|eremos|ido|ida|idos|idas)\b|papelera|replac\w*|overwrit\w*|delet\w*|eras(?:e|ed|ing)\b|discard\w*|don'?t\s+save|without\s+saving|los(?:e|t|ing)\b|recycle\s+bin|trash)",
        RegexOptions.CultureInvariant)]
    private static partial Regex DestructiveQuestion();
}
