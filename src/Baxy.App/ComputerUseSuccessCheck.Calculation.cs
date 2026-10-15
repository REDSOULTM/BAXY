using System.Globalization;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

// The «result:» atom: the value of a calculation shown on screen, never only its operands.
internal static partial class ComputerUseSuccessCheck
{
    /// <summary>
    /// The folded parts a look shows, one per line: the window's title first, then each control's name (with its value
    /// after a tab when it has one) and each written line. The sub-goal's first look is kept so (<see cref="ShowsAnew"/>).
    /// </summary>
    /// <summary>
    /// Check atom «result:&lt;expression&gt;» (live y7: «calculá 9 por 9» passed on the Enter alone while the display read
    /// 0): a calculation is done only when the screen shows its value. The expression is evaluated (digits, a decimal
    /// comma or point, + - × x * ÷ / : ^ and parentheses) and some number on the view (a control's name or value, or the
    /// read text), read with either decimal mark, equals it. One that cannot be evaluated holds only when the view shows
    /// a number the sub-goal's first look did not (the display changed to another number); with no first look, never.
    /// </summary>
    internal static bool ResultShows(string expression, JsonObject view)
    {
        HashSet<double> shown = ShownNumbers(LookText(view));
        double[] values = CalculationValues(expression);
        if (values.Length > 0)
        {
            return values.Any(value =>
            {
                double tolerance = 1e-9 * Math.Max(1, Math.Abs(value));
                return shown.Any(number => Math.Abs(number - value) <= tolerance);
            });
        }

        if ((string?)view["subgoalFirstText"] is not { Length: > 0 } first)
        {
            return false;
        }

        HashSet<double> before = ShownNumbers(first);
        return shown.Any(number => !before.Contains(number));
    }

    private static readonly System.Text.RegularExpressions.Regex ShownNumber = new(
        @"(?<![\p{L}\d])(?<mantissa>[-−]?\d+(?:[.,]\d+)*)(?:[eE](?<exponent>[-+−]?\d+)(?![\p{L}\d]))?",
        System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    // Every number of a text, read with a decimal point and with a decimal comma (the other mark groups thousands). A
    // number in exponent notation («1,219326311126353e+17», «8,1e-12», as a display shows a value too long for it) is
    // one number, its mantissa scaled by the exponent, never the mantissa and the exponent apart.
    private static HashSet<double> ShownNumbers(string text)
    {
        var numbers = new HashSet<double>();
        foreach (System.Text.RegularExpressions.Match match in ShownNumber.Matches(text))
        {
            string token = match.Groups["mantissa"].Value.Replace('−', '-');
            string exponent = match.Groups["exponent"].Success ? "e" + match.Groups["exponent"].Value.Replace('−', '-') : string.Empty;
            foreach (string read in new[] { token.Replace(",", string.Empty, StringComparison.Ordinal), token.Replace(".", string.Empty, StringComparison.Ordinal).Replace(',', '.') })
            {
                // A read with more than one decimal mark left is no number.
                if (read.Count(character => character == '.') <= 1
                    && double.TryParse(read + exponent, NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint | NumberStyles.AllowExponent, CultureInfo.InvariantCulture, out double number)
                    && double.IsFinite(number))
                {
                    _ = numbers.Add(number);
                }
            }
        }

        return numbers;
    }

    // A number whose marks all group three digits each («10.000», «1.500», «1,000», «1.000.000»): a person, and a
    // Spanish transcription above all, writes thousands so, while the same mark alone is also a decimal one («1.5»).
    private static readonly Regex GroupedNumber = new(
        @"(?<![\d.,])\d{1,3}(?<mark>[.,])\d{3}(?:\k<mark>\d{3})*(?![\d.,])", RegexOptions.CultureInvariant);

    /// <summary>
    /// Revisión 3 of ronda 23 («calculá 10.000-1» planned «result:10.000-1», the display showed 9.999 and the lone mark
    /// read as decimal gave 9, so the done was refused): every value an arithmetic expression may have as a person writes
    /// it. A number whose marks each group exactly three digits is read both ways, with its mark as the decimal one
    /// (<see cref="CalculationValue"/>) and as thousands grouped; empty when the expression is none.
    /// </summary>
    internal static double[] CalculationValues(string expression)
    {
        Match[] grouped = [.. GroupedNumber.Matches(expression).Take(6)];
        var values = new List<double>();
        for (int mask = 0; mask < 1 << grouped.Length; mask++)
        {
            var text = new StringBuilder(expression);
            for (int index = grouped.Length - 1; index >= 0; index--)
            {
                if ((mask & (1 << index)) != 0)
                {
                    Match match = grouped[index];
                    _ = text.Remove(match.Index, match.Length)
                        .Insert(match.Index, match.Value.Replace(match.Groups["mark"].Value, string.Empty, StringComparison.Ordinal));
                }
            }

            if (CalculationValue(text.ToString()) is double value && !values.Contains(value))
            {
                values.Add(value);
            }
        }

        return [.. values];
    }

    /// <summary>The value of an arithmetic expression as a person writes it, or null when it is not one.</summary>
    internal static double? CalculationValue(string expression)
    {
        string text = expression.Trim().TrimEnd('=').Trim();
        int position = 0;
        double? value = Sum();
        Skip();
        return value is double result && position == text.Length && double.IsFinite(result) ? result : null;

        void Skip()
        {
            while (position < text.Length && char.IsWhiteSpace(text[position]))
            {
                position++;
            }
        }

        double? Sum()
        {
            double? left = Product();
            while (left is not null)
            {
                Skip();
                if (position >= text.Length || text[position] is not ('+' or '-' or '−'))
                {
                    break;
                }

                char sign = text[position++];
                double? right = Product();
                left = right is null ? null : sign == '+' ? left + right : left - right;
            }

            return left;
        }

        double? Product()
        {
            double? left = Power();
            while (left is not null)
            {
                Skip();
                if (position >= text.Length || text[position] is not ('×' or 'x' or 'X' or '*' or '÷' or '/' or ':'))
                {
                    break;
                }

                char sign = text[position++];
                double? right = Power();
                left = right is null || (sign is '÷' or '/' or ':' && right == 0)
                    ? null
                    : sign is '÷' or '/' or ':' ? left / right : left * right;
            }

            return left;
        }

        double? Power()
        {
            double? left = Operand();
            Skip();
            if (left is not null && position < text.Length && text[position] == '^')
            {
                position++;
                double? right = Power();
                return right is null ? null : Math.Pow(left.Value, right.Value);
            }

            return left;
        }

        double? Operand()
        {
            Skip();
            if (position >= text.Length)
            {
                return null;
            }

            if (text[position] is '-' or '−')
            {
                position++;
                return -Operand();
            }

            if (text[position] == '(')
            {
                position++;
                double? inner = Sum();
                Skip();
                if (inner is null || position >= text.Length || text[position] != ')')
                {
                    return null;
                }

                position++;
                return inner;
            }

            int start = position;
            while (position < text.Length && (char.IsAsciiDigit(text[position]) || text[position] is '.' or ','))
            {
                position++;
            }

            string number = text[start..position];
            if (number.Length == 0 || !char.IsAsciiDigit(number[0]))
            {
                return null;
            }

            // One mark alone is the decimal one (12,5 or 12.5); with both, the last one is, and the other groups thousands.
            int lastMark = Math.Max(number.LastIndexOf('.'), number.LastIndexOf(','));
            string normal = lastMark < 0
                ? number
                : number[..lastMark].Replace(".", string.Empty, StringComparison.Ordinal).Replace(",", string.Empty, StringComparison.Ordinal)
                    + "." + number[(lastMark + 1)..];
            return double.TryParse(normal, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out double parsed)
                ? parsed
                : null;
        }
    }

}
