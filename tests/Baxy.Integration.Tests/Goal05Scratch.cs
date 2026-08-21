namespace Baxy.Integration.Tests;

internal static class Goal05Scratch
{
    private const string DirectoryPath =
        @"C:\Users\usuario\AppData\Local\Temp\grok-goal-317c6834ac48\implementer";

    internal static void Write(string name, string content)
    {
        if (!Directory.Exists(DirectoryPath))
        {
            return;
        }

        File.WriteAllText(Path.Combine(DirectoryPath, name), content);
    }

    internal static void Append(string name, string content)
    {
        if (!Directory.Exists(DirectoryPath))
        {
            return;
        }

        File.AppendAllText(Path.Combine(DirectoryPath, name), content);
    }
}
