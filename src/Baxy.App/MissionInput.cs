namespace Baxy.App;

internal enum MissionInputSource
{
    Text,
    VoiceTranscript,
}

internal sealed record MissionInput(
    string Text,
    MissionInputSource Source)
{
    public override string ToString() =>
        $"{nameof(MissionInput)} {{ Source = {Source}, Text = [REDACTED] }}";
}

internal enum MissionInputRejectionReason
{
    Empty,
    ContainsNull,
    MalformedUtf16,
    TooLarge,
    UnsupportedSource,
}

internal sealed class MissionInputRejectedException : ArgumentException
{
    internal MissionInputRejectedException(MissionInputRejectionReason reason)
        : base(MessageFor(reason), nameof(MissionInput.Text))
    {
        Reason = reason;
    }

    internal MissionInputRejectionReason Reason { get; }

    private static string MessageFor(MissionInputRejectionReason reason) => reason switch
    {
        MissionInputRejectionReason.Empty =>
            "La entrada de misi\u00f3n est\u00e1 vac\u00eda.",
        MissionInputRejectionReason.ContainsNull =>
            "La entrada de misi\u00f3n contiene un car\u00e1cter nulo.",
        MissionInputRejectionReason.MalformedUtf16 =>
            "La entrada de misi\u00f3n no es texto UTF-16 bien formado.",
        MissionInputRejectionReason.TooLarge =>
            "La entrada de misi\u00f3n supera el l\u00edmite de caracteres.",
        MissionInputRejectionReason.UnsupportedSource =>
            "La fuente de entrada de misi\u00f3n no est\u00e1 admitida.",
        _ => "La entrada de misi\u00f3n no es v\u00e1lida.",
    };
}

internal static class MissionInputContract
{
    // This is the existing WPF composer MaxLength, not the memory parser's
    // narrower UTF-8 limit. It preserves the text-entry contract for every route.
    internal const int MaximumCharacters = 4096;

    internal static string ValidateAndTrim(MissionInput? input)
    {
        if (!TryValidate(
                input,
                out string text,
                out MissionInputRejectionReason rejection))
        {
            throw new MissionInputRejectedException(rejection);
        }

        return text;
    }

    private static bool TryValidate(
        MissionInput? input,
        out string text,
        out MissionInputRejectionReason rejection)
    {
        text = string.Empty;
        if (input?.Text is { Length: > MaximumCharacters })
        {
            rejection = MissionInputRejectionReason.TooLarge;
            return false;
        }

        if (input is null || string.IsNullOrWhiteSpace(input.Text))
        {
            rejection = MissionInputRejectionReason.Empty;
            return false;
        }

        if (!Enum.IsDefined(input.Source))
        {
            rejection = MissionInputRejectionReason.UnsupportedSource;
            return false;
        }

        text = input.Text.Trim();
        if (text.Contains('\0'))
        {
            rejection = MissionInputRejectionReason.ContainsNull;
            return false;
        }

        if (!IsWellFormedUtf16(text))
        {
            rejection = MissionInputRejectionReason.MalformedUtf16;
            return false;
        }

        if (text.Length > MaximumCharacters)
        {
            rejection = MissionInputRejectionReason.TooLarge;
            return false;
        }

        rejection = default;
        return true;
    }

    private static bool IsWellFormedUtf16(string value)
    {
        for (int index = 0; index < value.Length; index++)
        {
            char character = value[index];
            if (char.IsHighSurrogate(character))
            {
                if (index + 1 >= value.Length || !char.IsLowSurrogate(value[index + 1]))
                {
                    return false;
                }

                index++;
            }
            else if (char.IsLowSurrogate(character))
            {
                return false;
            }
        }

        return true;
    }
}
