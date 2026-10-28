using System.Text;
using Baxy.GuardOracle;

// One JSON request per line on stdin, one JSON answer per line on stdout (GuardOracle).
var oracle = new GuardOracle();
var encoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
using var input = new StreamReader(Console.OpenStandardInput(), encoding);
using var output = new StreamWriter(Console.OpenStandardOutput(), encoding) { AutoFlush = true, NewLine = "\n" };
while (await input.ReadLineAsync().ConfigureAwait(false) is { } line)
{
    if (line.Trim().Length > 0)
    {
        await output.WriteLineAsync(oracle.Answer(line)).ConfigureAwait(false);
    }
}
