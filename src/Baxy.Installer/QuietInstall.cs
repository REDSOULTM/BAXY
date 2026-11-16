namespace Baxy.Installer;

/// <summary>
/// What --quiet does and the number it answers with, apart from the machine it runs on. A script reads only the number:
/// 0 is BAXY installed and registered, and each way of not getting there that the script can act on has its own
/// (INS-3, INS-5). The log says the same in words.
/// </summary>
internal sealed record QuietInstall(
    GpuSupport Support,
    bool Updating,
    Func<bool> BaxyIsOpen,
    Func<Task> InstallAsync,
    Action Register,
    Action<string> Log)
{
    /// <summary>BAXY's files are in place and it opens; Windows refused its shortcut or its «Installed apps» entry.</summary>
    internal const int NotRegistered = 2;

    /// <summary>
    /// The number Windows Installer gives for it: ERROR_INSTALL_PLATFORM_UNSUPPORTED, «This installation package isn't
    /// supported on this platform» (https://learn.microsoft.com/en-us/windows/win32/msi/error-codes), as
    /// <see cref="CommandLine.InvalidCommandLine"/> is its ERROR_INVALID_COMMAND_LINE.
    /// </summary>
    internal const int NoGraphicsCard = 1633;

    /// <summary>
    /// INS2 (MIN1): less RAM than Windows and BAXY with a model by API take, and nothing downloaded: Windows' own
    /// ERROR_NOT_ENOUGH_MEMORY, «Not enough memory resources are available to process this command»
    /// (https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-), as <see cref="NoGraphicsCard"/> is
    /// Windows Installer's. <c>--force</c> installs anyway.
    /// </summary>
    internal const int TooLittleRam = 8;

    private const int RegisterAttempts = 3;

    internal TimeSpan Pace { get; init; } = TimeSpan.FromMilliseconds(500);

    internal TimeSpan RegisterRetry { get; init; } = TimeSpan.FromSeconds(2);

    /// <summary>INS2: the RAM the log tells with what is told of the machine.</summary>
    internal MachineRam Ram { get; init; } = new(null, null);

    /// <summary>INS2: --force, installing where BAXY does not fit even with a model by API.</summary>
    internal bool Force { get; init; }

    /// <summary>INS2: whether Windows declares integrated the graphics the RAM is told for.</summary>
    internal bool Integrated { get; init; }

    internal async Task<int> RunAsync()
    {
        // The window refuses this same machine and nothing else (MainWindow.WarningScreen): with a card it could not
        // measure, or a small one, it offers «install anyway», and whoever runs --quiet already chose. An update comes
        // from a BAXY that runs on this machine, and the window does not ask it about the card either.
        if (!Updating && Support == GpuSupport.None)
        {
            Log("no NVIDIA, AMD or Intel graphics card in this PC: BAXY does not work here, nothing was downloaded");
            return NoGraphicsCard;
        }

        // INS2 (MIN1): the window says the same and waits for «install anyway»; here --force is that choice. Nothing of the
        // gigabytes is downloaded for a BAXY that would close before saying a word; an update comes from a BAXY already here.
        string ram = string.Create(
            System.Globalization.CultureInfo.InvariantCulture,
            $"{Ram}; BAXY needs {MachineGpu.MinimumApiRamMib} MB with a model by API and {MachineGpu.MinimumRamMib(Integrated)} MB with its own");
        if (!Updating && Support == GpuSupport.TooLittleRamEvenByApi)
        {
            if (!Force)
            {
                Log($"too little RAM: {ram}. BAXY does not fit on this PC even with a model by API: nothing was downloaded (--force installs anyway)");
                return TooLittleRam;
            }

            Log($"too little RAM: {ram}. BAXY does not fit on this PC even with a model by API; installing because of --force");
        }
        else if (Support is GpuSupport.TooLittleRam or GpuSupport.TooLittleRamIntegrated)
        {
            Log($"little RAM: {ram}. BAXY may not start with its own model; with a model by API (Settings, Model) it fits");
        }

        // --update: the BAXY that started this closes itself; it is waited for a minute at most.
        for (int waited = 0; Updating && BaxyIsOpen() && waited < 120; waited++)
        {
            await Task.Delay(Pace).ConfigureAwait(false);
        }

        if (BaxyIsOpen())
        {
            Log("a BAXY is open: close it first");
            return Program.Failure;
        }

        await InstallAsync().ConfigureAwait(false);
        // Nobody is there to press «try again»: the step alone is tried again, never the download.
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                Register();
                Log("installed");
                return 0;
            }
            catch (NotRegisteredException refused) when (attempt < RegisterAttempts)
            {
                Log($"registration refused ({attempt} of {RegisterAttempts}): {refused.Message}");
                await Task.Delay(RegisterRetry).ConfigureAwait(false);
            }
            catch (NotRegisteredException refused)
            {
                Log("installed, but not registered: " + refused);
                return NotRegistered;
            }
        }
    }
}
