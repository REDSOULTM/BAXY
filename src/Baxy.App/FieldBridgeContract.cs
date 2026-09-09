using System.Globalization;
using System.Text.Json.Nodes;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>
/// Etapa honesta de progreso visible. Nunca describe una decisión interna, un
/// estado del router ni un éxito anticipado: sólo dice qué está ocurriendo
/// ahora mismo para una persona que espera.
/// </summary>
internal sealed record FieldProgressNotice(string Stage, string? Label)
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

    internal const string AgentNotReadyError = "agent_not_ready";

    internal const int AgentNotReadyStatus = 409;

    private const string StepPrefix = "Ejecutando paso ";

    /// <summary>
    /// Republish the current stage. Must be ≤ 1 s so a 2 s pulse cannot
    /// skip from t=2 (still under budget) to t=4 (first check over 3 s).
    /// </summary>
    internal static readonly TimeSpan ProgressPulse = TimeSpan.FromSeconds(1);

    /// <summary>
    /// When the next formulated hito is due if nothing visible has appeared.
    /// </summary>
    internal static readonly TimeSpan MilestoneDue = FirstSignal.MilestoneDueDelay;

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
            "wake_inactive",
            "speaking",
        };

    private static readonly Dictionary<string, string> DescriptionStages =
        new(StringComparer.Ordinal)
        {
            ["Preparando BAXY"] = FieldProgressNotice.StageStarting,
            ["Comprobando BAXY"] = FieldProgressNotice.StageStarting,
            ["Terminando de iniciar"] = FieldProgressNotice.StageStarting,
            ["understanding"] = FieldProgressNotice.StageUnderstanding,
            ["Preparando los pasos"] = FieldProgressNotice.StagePreparingSteps,
            ["acting"] = FieldProgressNotice.StageActing,
            ["Esperando confirmación de memoria"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando comprobar el audio"] =
                FieldProgressNotice.StageAwaitingReply,
            ["awaiting_mission_resume"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando tu aclaración"] = FieldProgressNotice.StageAwaitingReply,
            ["Esperando comprobar la memoria"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando una comprobación segura"] =
                FieldProgressNotice.StageAwaitingReply,
            ["awaiting_request_recovery"] =
                FieldProgressNotice.StageAwaitingReply,
            ["Esperando tu elección"] = FieldProgressNotice.StageAwaitingReply,
            ["retry_without_close"] =
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
    /// Chat and voice stay closed until the shell has a verified ready
    /// terminal. A rejected turn never starts a mission.
    /// </summary>
    internal static bool TryAcceptTurn(
        bool isInputEnabled,
        string? text,
        out string error,
        out int status)
    {
        if (!isInputEnabled)
        {
            error = AgentNotReadyError;
            status = AgentNotReadyStatus;
            return false;
        }

        if (string.IsNullOrWhiteSpace(text))
        {
            error = "invalid_text";
            status = 400;
            return false;
        }

        error = string.Empty;
        status = 200;
        return true;
    }

    internal static bool TryAcceptVoiceControl(bool isReady, out string error, out int status)
    {
        if (!isReady)
        {
            error = AgentNotReadyError;
            status = AgentNotReadyStatus;
            return false;
        }

        error = string.Empty;
        status = 200;
        return true;
    }

    /// <summary>
    /// Resuelve la indicación honesta que corresponde al estado observable del
    /// shell. Devuelve <c>null</c> cuando no debe verse ninguna: BAXY está
    /// lista y no hay trabajo en curso.
    /// </summary>
    internal static FieldProgressNotice? ResolveProgress(
        bool isReady,
        bool isBusy,
        bool hasStartupError,
        string? statusDescription,
        string? progressLabel = null)
    {
        if (hasStartupError)
        {
            return Create(FieldProgressNotice.StageUnavailable);
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
                && TryReadStep(description, out _, out _))
            {
                return Create(FieldProgressNotice.StageActing, progressLabel);
            }

            if (DescriptionStages.TryGetValue(description, out string? mapped))
            {
                return Create(mapped, progressLabel);
            }
        }

        return Create(
            isReady
                ? FieldProgressNotice.StageWorking
                : FieldProgressNotice.StageStarting,
            progressLabel);
    }

    internal static FieldProgressNotice Create(string stage, string? label = null) =>
        new(
            stage is FieldProgressNotice.StageStarting
                or FieldProgressNotice.StageUnderstanding
                or FieldProgressNotice.StagePreparingSteps
                or FieldProgressNotice.StageActing
                or FieldProgressNotice.StageAwaitingReply
                or FieldProgressNotice.StageUnavailable
                or FieldProgressNotice.StageWorking
                ? stage
                : FieldProgressNotice.StageWorking,
            Label: string.IsNullOrWhiteSpace(label) ? null : label.Trim());

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
    /// que conoce <c>boot_stage</c> consume su estado. FieldCenter presenta
    /// la etiqueta fuera del input para no ocultarla tras el texto del turno.
    /// </summary>
    internal static bool ShouldPulseProgress(
        DateTimeOffset? lastPublishedUtc,
        DateTimeOffset nowUtc) =>
        lastPublishedUtc is null || nowUtc - lastPublishedUtc.Value >= ProgressPulse;

    internal static DateTimeOffset FirstHitoDueAt(DateTimeOffset lastVisibleUtc) =>
        lastVisibleUtc + MilestoneDue;

    /// <summary>
    /// First 1 s pulse tick whose elapsed time is strictly over the 3 s bar.
    /// With a 1 s pulse that is 4 s — why the due timer exists.
    /// </summary>
    internal static DateTimeOffset FirstPulseAfterSilenceBudget(DateTimeOffset lastVisibleUtc)
    {
        TimeSpan elapsed = TimeSpan.Zero;
        while (elapsed.TotalSeconds <= FirstSignal.SilenceBudgetSeconds)
        {
            elapsed += ProgressPulse;
        }

        return lastVisibleUtc + elapsed;
    }

    internal static JsonObject CreateProgressPayload(
        FieldProgressNotice? notice,
        DateTimeOffset? atUtc = null)
    {
        JsonNode? pulse = atUtc is null
            ? null
            : JsonValue.Create(atUtc.Value.ToUnixTimeMilliseconds());
        return notice is null
            ? new JsonObject
            {
                ["type"] = ProgressPayloadType,
                ["stage"] = FieldProgressNotice.StageCleared,
                ["phase"] = "completed",
                ["label"] = null,
                ["progress"] = null,
                ["error"] = null,
                ["t"] = pulse,
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
                ["t"] = pulse,
                ["v"] = TurnProgressRevision,
            };
    }

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
