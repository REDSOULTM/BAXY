namespace Baxy.Setup;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            SetupCommand command = SetupCommand.Parse(args);
            if (command.Kind == SetupCommandKind.VerifyEmbedded)
            {
                VerifiedProductPackage verified = EmbeddedPackageSource.Verify();
                EmbeddedPackageSource.WriteVerificationEvidence(command.EvidencePath!, verified);
                return 0;
            }

            CanonicalWindowsPaths paths = command.Kind == SetupCommandKind.Uninstall
                ? CanonicalWindowsPaths.ResolveForUninstall()
                : CanonicalWindowsPaths.Resolve();
            if (command.Kind == SetupCommandKind.Uninstall)
            {
                return SetupUninstallExecutor.CreateProduction(paths).Execute(command);
            }

            if (command.Kind == SetupCommandKind.Launch)
            {
                InstallationEngine engine = new(paths.InstallationRoot);
                _ = new InstalledApplicationLauncher(engine).Launch();
                return 0;
            }

            return SetupProductLifecycleExecutor.CreateProduction(paths).Execute(command.Kind);
        }
        catch (ProductPackageException)
        {
            return 30;
        }
        catch (InstallationSafetyException)
        {
            return 40;
        }
        catch (InstalledApplicationLaunchException)
        {
            return 50;
        }
        catch (ArgumentException)
        {
            return 64;
        }
        catch
        {
            return 70;
        }
    }
}
