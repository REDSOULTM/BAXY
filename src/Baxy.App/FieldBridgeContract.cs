using System.Globalization;
using System.Text.Json.Nodes;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>
/// Etapa honesta de progreso visible. Nunca describe una decisión interna, un
/// estado del router ni un éxito anticipado: sólo dice qué está ocurriendo
/// ahora mismo para una persona que espera.
/// </summary>
internal sealed record FieldProgressNotice(string Stage, string Label)
{
    internal const string StageStarting = "starting";
    internal const string StageUnderstanding = "understanding";
    internal const string StagePreparingSteps = "preparing_steps";
    internal const string StageActing = "acting";
    internal const string StageWorking = "working";
    internal const string StageAwaitingReply = "awaiting_reply";
    internal const string StageUnavailable = "unavailable";

    /// <summary>Etapa terminal que retira cualquier indicación previa.</summary>
    internal const string StageCleared = "ready";
}

/// <summary>
/// Contrato versionado entre <c>field-native-bridge.js</c> y el shell WPF.
///
/// El canal sigue siendo <c>baxy.field.v1</c>. Cada envelope declara ahora
/// <c>minReader</c>: un lector antiguo que no conoce el campo sigue leyendo
/// exactamente los mensajes de la revisión 1, y un lector nuevo descarta de
/// forma explícita cualquier envelope que exija una revisión superior a la
/// suya. Nada se reinterpreta: o se entiende, o se descarta por versión.
///
/// El shell no emite un mensaje de revisión 2 hasta que el lector anuncia su
/// propia revisión con <c>reader_hello</c>.
/// </summary>
internal static class FieldBridgeContract
{
    internal const string Channel = "baxy.field.v1";

    /// <summary>Revisión que implementa este shell nativo.</summary>
    internal const int NativeRevision = 2;

    /// <summary>Revisión asumida mientras el lector no se anuncia.</summary>
    internal const int LegacyReaderRevision = 1;

    /// <summary>Revisión mínima que exige el progreso visible de turno.</summary>
    internal const int TurnProgressRevision = 2;

    internal const int MaximumReaderRevision = 64;

    internal const string ReaderHelloKind = "reader_hello";
    internal const string ContractKind = "contract";
    internal const string MinimumReaderProperty = "minReader";
    internal const string ProgressPayloadType = "boot_stage";

    private const string StartingLabel =
        "Estoy preparando todo para empezar.";
    private const string PreparingStepsLabel =
        "Estoy preparando los pasos que hacen falta.";
    private const string ActingLabel =
        "Estoy realizando la acción que pediste.";
    private const string WorkingLabel =
        "Sigo trabajando en tu petición.";
    private const string AwaitingReplyLabel =
        "Estoy esperando tu respuesta.";
    private const string UnavailableLabel =
        "No pude terminar de prepararme; puedes intentarlo otra vez.";

    private const string StepPrefix = "Ejecutando paso ";

    /// <summary>
    /// Descripciones internas que NO deben producir una indicación visible.
    /// Son estados listos, de voz o de diagnóstico que ya tienen su propio
    /// canal de estado.
    /// </summary>
    private static readonly HashSet<string> SilentDescriptions =
        new(StringComparer.Ordinal)
        {
            "BAXY disponible",
            "Todo listo",
            "Escuchando",
            "Te escucho",
            "Te escucho…",
            "Transcribiendo…",
            "Interrupción detectada",
            "La voz se degradó; el motor sigue disponible",
            "Esperando «Baxy»",
            "Falta activar el modelo de wake; puedes usar el micrófono",
        };

    private static readonly Dictionary<string, string> DescriptionStages =
        new(StringComparer.Ordinal)
        {
            ["Preparando BAXY"] = FieldProgressNotice.StageStarting,
            ["Comprobando BAXY"] = FieldProgressNotice.StageStarting,
            ["Terminando de iniciar"] = FieldProgressNotice.StageStarting,
            ["Entendiendo tu petición"] = FieldProgressNotice.StageUnderstanding,
            ["Preparando los pasos"] = FieldProgressNotice.StagePreparingSteps,
            ["Ejecutando la petición"] = FieldProgressNotice.StageActing,
            ["Esperando confirmación de memoria"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando comprobar el audio"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando reanudar una misión"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando tu aclaración"] = FieldProgressNotice.StageAwaitingReply,
            ["Esperando comprobar la memoria"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando una comprobación segura"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando recuperar una petición"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando tu elección"] = FieldProgressNotice.StageAwaitingReply,
            ["Puedes reintentar sin cerrar BAXY"] =
                FieldProgressNotice.StageUnavailable,
            ["Conexión interrumpida"] = FieldProgressNotice.StageUnavailable,
        };

    /// <summary>Vocabulario cerrado de etapas publicables.</summary>
    internal static readonly string[] ProgressStages =
    [
        FieldProgressNotice.StageStarting,
        FieldProgressNotice.StageUnderstanding,
        FieldProgressNotice.StagePreparingSteps,
        FieldProgressNotice.StageActing,
        FieldProgressNotice.StageWorking,
        FieldProgressNotice.StageAwaitingReply,
        FieldProgressNotice.StageUnavailable,
    ];

    /// <summary>
    /// Resuelve la indicación honesta que corresponde al estado observable del
    /// shell. Devuelve <c>null</c> cuando no debe verse ninguna: BAXY está
    /// lista y no hay trabajo en curso.
    /// </summary>
    internal static FieldProgressNotice? ResolveProgress(
        bool isReady,
        bool isBusy,
        bool hasStartupError,
        string? statusDescription)
    {
        if (hasStartupError)
        {
            return new FieldProgressNotice(
                FieldProgressNotice.StageUnavailable,
                UnavailableLabel);
        }

        if (isReady && !isBusy)
        {
            return null;
        }

        string? description = statusDescription;
        if (!string.IsNullOrWhiteSpace(description))
        {
            if (SilentDescriptions.Contains(description))
            {
                return isReady
                    ? null
                    : Create(FieldProgressNotice.StageStarting);
            }

            if (description.StartsWith(StepPrefix, StringComparison.Ordinal)
                && TryReadStep(description, out int step, out int total))
            {
                return new FieldProgressNotice(
                    FieldProgressNotice.StageActing,
                    string.Format(
                        CultureInfo.InvariantCulture,
                        "Estoy en el paso {0} de {1}.",
                        step,
                        total));
            }

            if (DescriptionStages.TryGetValue(description, out string? mapped))
            {
                return Create(mapped);
            }
        }

        return Create(
            isReady
                ? FieldProgressNotice.StageWorking
                : FieldProgressNotice.StageStarting);
    }

    internal static FieldProgressNotice Create(string stage) => stage switch
    {
        FieldProgressNotice.StageStarting =>
            new FieldProgressNotice(stage, StartingLabel),
        FieldProgressNotice.StageUnderstanding =>
            new FieldProgressNotice(stage, HonestyCorrection.NonAssertingInProgress),
        FieldProgressNotice.StagePreparingSteps =>
            new FieldProgressNotice(stage, PreparingStepsLabel),
        FieldProgressNotice.StageActing =>
            new FieldProgressNotice(stage, ActingLabel),
        FieldProgressNotice.StageAwaitingReply =>
            new FieldProgressNotice(stage, AwaitingReplyLabel),
        FieldProgressNotice.StageUnavailable =>
            new FieldProgressNotice(stage, UnavailableLabel),
        _ => new FieldProgressNotice(FieldProgressNotice.StageWorking, WorkingLabel),
    };

    private static bool TryReadStep(string description, out int step, out int total)
    {
        step = 0;
        total = 0;
        ReadOnlySpan<char> tail = description.AsSpan(StepPrefix.Length);
        int separator = tail.IndexOf(" de ", StringComparison.Ordinal);
        return separator > 0
            && int.TryParse(
                tail[..separator],
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out step)
            && int.TryParse(
                tail[(separator + 4)..],
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out total)
            && step > 0
            && total > 0;
    }

    /// <summary>
    /// Construye el payload de socket de una indicación. Un lector histórico
    /// que ya conoce <c>boot_stage</c> lo muestra como estado; uno que no lo
    /// conoce lo ignora sin cambiar su estado.
    /// </summary>
    internal static JsonObject CreateProgressPayload(FieldProgressNotice? notice) =>
        notice is null
            ? new JsonObject
            {
                ["type"] = ProgressPayloadType,
                ["stage"] = FieldProgressNotice.StageCleared,
                ["phase"] = "completed",
                ["label"] = null,
                ["progress"] = null,
                ["error"] = null,
                ["v"] = TurnProgressRevision,
            }
            : new JsonObject
            {
                ["type"] = ProgressPayloadType,
                ["stage"] = notice.Stage,
                ["phase"] = "active",
                ["label"] = notice.Label,
                ["progress"] = null,
                ["error"] = null,
                ["v"] = TurnProgressRevision,
            };

    /// <summary>
    /// Marca el envelope con la revisión mínima de lector que puede
    /// interpretarlo. La revisión 1 se omite para conservar byte a byte el
    /// contrato histórico.
    /// </summary>
    internal static JsonObject StampEnvelope(JsonObject envelope, int minimumReader)
    {
        ArgumentNullException.ThrowIfNull(envelope);
        if (minimumReader > LegacyReaderRevision)
        {
            envelope[MinimumReaderProperty] = minimumReader;
        }

        return envelope;
    }

    /// <summary>
    /// Regla de compatibilidad del lector: un envelope se entrega sólo si la
    /// revisión declarada del lector alcanza la que exige el mensaje.
    /// </summary>
    internal static bool CanDeliver(int minimumReader, int readerRevision) =>
        minimumReader <= readerRevision;

    /// <summary>
    /// Lee la revisión anunciada por el lector. Un valor ausente, no numérico o
    /// fuera de rango conserva la revisión histórica.
    /// </summary>
    internal static int ReadReaderRevision(JsonObject? message)
    {
        if (message?["revision"] is not JsonValue value
            || !value.TryGetValue(out int revision)
            || revision < LegacyReaderRevision
            || revision > MaximumReaderRevision)
        {
            return LegacyReaderRevision;
        }

        return revision;
    }

    internal static JsonObject CreateContractAnnouncement() => StampEnvelope(
        new JsonObject
        {
            ["channel"] = Channel,
            ["kind"] = ContractKind,
            ["revision"] = NativeRevision,
        },
        LegacyReaderRevision);
}
