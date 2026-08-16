namespace Baxy.Setup;

internal enum SetupCommandKind
{
    Install,
    Launch,
    Rollback,
    Uninstall,
    VerifyEmbedded,
}

internal enum UninstallDataPolicy
{
    KeepData,
    PurgeData,
}

internal sealed record SetupCommand(
    SetupCommandKind Kind,
    UninstallDataPolicy? DataPolicy,
    bool Quiet,
    string? EvidencePath)
{
    internal static SetupCommand Parse(string[] args)
    {
        ArgumentNullException.ThrowIfNull(args);

        if (args.Length == 0)
        {
            return new SetupCommand(
                SetupCommandKind.Install,
                DataPolicy: null,
                Quiet: false,
                EvidencePath: null);
        }

        if (Matches(args, "--launch"))
        {
            return new SetupCommand(
                SetupCommandKind.Launch,
                DataPolicy: null,
                Quiet: false,
                EvidencePath: null);
        }

        if (Matches(args, "--rollback"))
        {
            return new SetupCommand(
                SetupCommandKind.Rollback,
                DataPolicy: null,
                Quiet: false,
                EvidencePath: null);
        }

        if (Matches(args, "--uninstall"))
        {
            return new SetupCommand(
                SetupCommandKind.Uninstall,
                UninstallDataPolicy.KeepData,
                Quiet: false,
                EvidencePath: null);
        }

        if (Matches(args, "--uninstall", "--keep-data", "--quiet"))
        {
            return new SetupCommand(
                SetupCommandKind.Uninstall,
                UninstallDataPolicy.KeepData,
                Quiet: true,
                EvidencePath: null);
        }

        if (Matches(
                args,
                "--uninstall",
                "--purge-data",
                "--confirm-purge-data",
                "--quiet"))
        {
            return new SetupCommand(
                SetupCommandKind.Uninstall,
                UninstallDataPolicy.PurgeData,
                Quiet: true,
                EvidencePath: null);
        }

        if (args.Length == 3 &&
            string.Equals(args[0], "--verify-embedded", StringComparison.Ordinal) &&
            string.Equals(args[1], "--evidence", StringComparison.Ordinal) &&
            !string.IsNullOrWhiteSpace(args[2]))
        {
            return new SetupCommand(
                SetupCommandKind.VerifyEmbedded,
                DataPolicy: null,
                Quiet: false,
                EvidencePath: args[2]);
        }

        throw new ArgumentException("Unsupported Setup arguments.", nameof(args));
    }

    private static bool Matches(string[] args, params string[] expected)
    {
        if (args.Length != expected.Length)
        {
            return false;
        }

        for (int index = 0; index < expected.Length; index++)
        {
            if (!string.Equals(args[index], expected[index], StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }
}
