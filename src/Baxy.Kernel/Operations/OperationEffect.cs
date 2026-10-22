using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.Kernel.Operations;

/// <summary>
/// One effect a descriptor declares (al máximo 5.1; <see cref="OperationEffects"/>): what its provider does, read from
/// the provider, as a typed fact of the catalog. Without conditions the operation always has it; with them, only a call
/// whose arguments meet one of them (app.open raises a window only with foreground, newDocument or a place).
/// </summary>
public sealed class OperationEffect
{
    private readonly EffectCondition[] _when;

    private OperationEffect(string kind, EffectCondition[] when)
    {
        if (!OperationEffects.IsKnown(kind))
        {
            throw new ArgumentException("The operation effect is not canonical.", nameof(kind));
        }

        Kind = kind;
        _when = when;
    }

    public string Kind { get; }

    internal IReadOnlyList<EffectCondition> When => _when;

    public static OperationEffect Always(string kind) => new(kind, []);

    public static OperationEffect With(string kind, params EffectCondition[] when)
    {
        ArgumentNullException.ThrowIfNull(when);
        if (when.Length == 0)
        {
            throw new ArgumentException("A conditional effect needs a condition.", nameof(when));
        }

        return new(kind, when);
    }

    public bool Applies(JsonElement arguments) =>
        _when.Length == 0 || _when.Any(condition => condition.Holds(arguments));
}

/// <summary>One condition on one argument of the call, as the provider reads it.</summary>
public sealed class EffectCondition
{
    private readonly Func<JsonElement?, bool> _holds;

    private EffectCondition(string argument, Func<JsonElement?, bool> holds)
    {
        Argument = argument;
        _holds = holds;
    }

    public string Argument { get; }

    /// <summary>The argument is the boolean true.</summary>
    public static EffectCondition IsTrue(string argument) =>
        new(argument, static value => value?.ValueKind == JsonValueKind.True);

    /// <summary>The argument is a string with something in it.</summary>
    public static EffectCondition Named(string argument) => new(argument, static value => Text(value) is not null);

    /// <summary>The argument is absent, null or a blank string.</summary>
    public static EffectCondition Unnamed(string argument) => new(argument, static value => Text(value) is null);

    /// <summary>The argument is that string, in any case.</summary>
    public static EffectCondition Is(string argument, string expected) =>
        new(argument, value => string.Equals(Text(value), expected, StringComparison.OrdinalIgnoreCase));

    internal bool Holds(JsonElement arguments) =>
        _holds(arguments.ValueKind == JsonValueKind.Object && arguments.TryGetProperty(Argument, out JsonElement value)
            ? value
            : null);

    private static string? Text(JsonElement? value) =>
        value is { ValueKind: JsonValueKind.String } text && !string.IsNullOrWhiteSpace(text.GetString())
            ? text.GetString()
            : null;
}
