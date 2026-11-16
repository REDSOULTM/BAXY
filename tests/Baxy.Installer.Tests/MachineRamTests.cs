using System.Globalization;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// INS2 (MIN1): on an HP 15 with a Ryzen's Radeon and 4 GB of RAM the installer said «your card has less than 4 GB»,
/// installed 4.8 GB with --quiet and BAXY with no model of its own then took all its RAM before saying a word. The
/// installer tells what the RAM gives, integrated graphics are what Windows declares whatever their maker, and below what
/// BAXY with a model by API takes it downloads nothing unless the person insists. The machines that work today see what
/// they saw.
/// </summary>
[TestFixture]
internal sealed class MachineRamTests
{
    private const long Mib = 1024 * 1024;

    // MIN1's HP 15 (Ryzen 3 4300U: PCI\VEN_1002&DEV_1636, 512 MB set aside, 4,096 MB installed, 454 free).
    private static readonly GpuAdapter RyzenRadeon = new(@"PCI\VEN_1002&DEV_1636", 512 * Mib, Integrated: true);
    private static readonly GpuAdapter IntelGraphics = new(@"PCI\VEN_8086&DEV_9A49", 128 * Mib, Integrated: true);
    private static readonly GpuAdapter Nvidia4 = new(@"PCI\VEN_10DE&DEV_1F82", 4096 * Mib, Integrated: false);
    private static readonly GpuAdapter Radeon8 = new(@"PCI\VEN_1002&DEV_7480", 8176 * Mib, Integrated: false);

    // This PC (RTX 4060 Ti 16 GB beside Intel UHD, 32 GB) and the notebook (RTX 3060 Laptop 6 GB beside a Ryzen's Radeon, 16 GB).
    private static readonly GpuAdapter[] ThisPc =
        [new(@"PCI\VEN_10DE&DEV_2803", 16_380 * Mib, false), new(@"PCI\VEN_8086&DEV_4688", 128 * Mib, true)];

    private static readonly GpuAdapter[] Notebook =
        [new(@"PCI\VEN_1002&DEV_1638", 512 * Mib, true), new(@"PCI\VEN_10DE&DEV_2520", 6_000 * Mib, false)];

    private static IEnumerable<TestCaseData> Machines()
    {
        yield return new TestCaseData(new[] { RyzenRadeon }, 4096L, GpuSupport.TooLittleRamEvenByApi).SetName("HP 15, Radeon integrada 0,5 GB, 4 GB de RAM");
        yield return new TestCaseData(new[] { IntelGraphics }, 8192L, GpuSupport.TooLittleRamIntegrated).SetName("Intel integrada, 8 GB");
        yield return new TestCaseData(new[] { IntelGraphics }, 16384L, GpuSupport.Integrated).SetName("Intel integrada, 16 GB");
        yield return new TestCaseData(new[] { RyzenRadeon }, 16384L, GpuSupport.Integrated).SetName("Radeon integrada, 16 GB");
        yield return new TestCaseData(new[] { Nvidia4 }, 8192L, GpuSupport.Measured).SetName("NVIDIA 4 GB, 8 GB");
        yield return new TestCaseData(new[] { Nvidia4 }, 16384L, GpuSupport.Measured).SetName("NVIDIA 4 GB, 16 GB");
        yield return new TestCaseData(new[] { Nvidia4 }, 6400L, GpuSupport.TooLittleRam).SetName("NVIDIA 4 GB, 6,25 GB");
        yield return new TestCaseData(new[] { Nvidia4 }, 4096L, GpuSupport.TooLittleRamEvenByApi).SetName("NVIDIA 4 GB, 4 GB");
        yield return new TestCaseData(new[] { Radeon8 }, 16384L, GpuSupport.Measured).SetName("Radeon RX 7600 8 GB, 16 GB");
        yield return new TestCaseData(ThisPc, 32768L, GpuSupport.Measured).SetName("Este PC");
        yield return new TestCaseData(Notebook, 16384L, GpuSupport.Measured).SetName("Notebook RTX 3060 6 GB, 16 GB");
    }

    [TestCaseSource(nameof(Machines))]
    public void Each_machine_is_told_what_its_ram_and_graphics_give(GpuAdapter[] adapters, long ram, GpuSupport told) =>
        Assert.That(MachineGpu.WithRam(adapters, ram), Is.EqualTo(told));

    // Where the figures come from: Windows 11's 4 GB, BAXY's tree with its voice (3,748 MiB, AUD1 §2), the server on
    // integrated graphics (3,579, VRAM5) and BAXY with no model of its own (777 private, the least of MIN1 §2, + 1,222 of
    // voice, AUD1 F10): a PC of 6 GB is short, not refused.
    [Test]
    public void The_thresholds_are_the_measured_figures()
    {
        Assert.That(MachineGpu.MinimumApiRamMib, Is.EqualTo(4096 + 777 + 1222));
        Assert.That(MachineGpu.WithRam([Nvidia4], 6144), Is.EqualTo(GpuSupport.TooLittleRam));
        Assert.That(MachineGpu.MinimumRamMib(integrated: false), Is.EqualTo(4096 + 3748));
        Assert.That(MachineGpu.MinimumRamMib(integrated: true), Is.EqualTo(4096 + 3748 + 3579));
    }

    [Test]
    public void A_card_beside_integrated_graphics_of_its_own_maker_is_the_one_told()
    {
        GpuAdapter[] ryzenWithRadeon = [RyzenRadeon, Radeon8];

        Assert.That(MachineGpu.WithRam(ryzenWithRadeon, 16384), Is.EqualTo(GpuSupport.Measured));
        Assert.That(MachineGpu.Integrated(ryzenWithRadeon), Is.False);
    }

    [Test]
    public void Graphics_nobody_declared_are_told_as_before()
    {
        Assert.That(MachineGpu.WithRam([RyzenRadeon with { Integrated = null }], 16384), Is.EqualTo(GpuSupport.TooLittleMemory));
        Assert.That(MachineGpu.WithRam([IntelGraphics with { Integrated = null }], 16384), Is.EqualTo(GpuSupport.NotMeasured));
        Assert.That(MachineGpu.WithRam([RyzenRadeon], null), Is.EqualTo(GpuSupport.Integrated));
    }

    [Test]
    public async Task Quiet_on_the_hp_15_downloads_nothing_tells_why_and_exits_with_its_code()
    {
        List<string> log = [];
        int installed = 0;

        int code = await Quiet(GpuSupport.TooLittleRamEvenByApi, log, () => installed++).RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That(code, Is.EqualTo(QuietInstall.TooLittleRam));
            Assert.That(installed, Is.Zero);
            Assert.That(log, Has.One.Contain("RAM 4096 MB, 454 free").And.Contain("6095 MB with a model by API")
                .And.Contain("11423 MB with its own").And.Contain("nothing was downloaded").And.Contain("--force"));
        });
    }

    [Test]
    public async Task Quiet_with_force_installs_and_says_so()
    {
        List<string> log = [];
        int installed = 0;

        int code = await (Quiet(GpuSupport.TooLittleRamEvenByApi, log, () => installed++) with { Force = true }).RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That(code, Is.Zero);
            Assert.That(installed, Is.EqualTo(1));
            Assert.That(log, Has.Some.Contain("because of --force"));
        });
    }

    [Test]
    public async Task An_update_from_a_baxy_already_here_is_not_held()
    {
        int installed = 0;

        int code = await (Quiet(GpuSupport.TooLittleRamEvenByApi, [], () => installed++) with { Updating = true }).RunAsync();

        Assert.That((code, installed), Is.EqualTo((0, 1)));
    }

    [TestCase(GpuSupport.TooLittleRam)]
    [TestCase(GpuSupport.TooLittleRamIntegrated)]
    public async Task Quiet_with_ram_only_for_a_model_by_api_installs_and_says_it(GpuSupport support)
    {
        List<string> log = [];
        int installed = 0;

        int code = await Quiet(support, log, () => installed++).RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That((code, installed), Is.EqualTo((0, 1)));
            Assert.That(log, Has.One.Contain("little RAM").And.Contain("with a model by API"));
        });
    }

    [TestCase(GpuSupport.Measured)]
    [TestCase(GpuSupport.NotMeasured)]
    [TestCase(GpuSupport.TooLittleMemory)]
    public async Task The_machines_that_install_today_log_and_answer_as_before(GpuSupport support)
    {
        List<string> log = [];

        int code = await Quiet(support, log, () => { }).RunAsync();

        Assert.That((code, string.Join("|", log)), Is.EqualTo((0, "installed")));
    }

    [TestCase("es")]
    [TestCase("en")]
    public void The_window_says_the_hp_15_figures_and_what_it_would_take(string language)
    {
        Texts texts = language == "es" ? Texts.Spanish : Texts.English;
        object[] hp15 = [4096 / 1024d, 11423 / 1024d, 454 / 1024d, 6095 / 1024d, 4.8];

        string body = string.Format(CultureInfo.InvariantCulture, texts.WarningRamEvenByApi, hp15);
        string help = string.Format(CultureInfo.InvariantCulture, texts.WarningRamEvenByApiHelp, hp15);

        Assert.Multiple(() =>
        {
            Assert.That(body, Does.Contain(" 4 GB").And.Contain("0.4").And.Contain(" 6 GB").And.Contain("11.2").And.Contain("API"));
            Assert.That(help, Does.Contain(" 6 GB").And.Contain("4.8"));
            Assert.That(texts.NoRoomTitle, Is.Not.Empty);
            // MIN1: «use another model» is no way out where BAXY with no model of its own does not fit.
            Assert.That(body + help, Does.Not.Contain(language == "es" ? "Ajustes" : "Settings"));
            Assert.That(texts.WarningIntegrated, Does.Not.Contain("Intel"));
            Assert.That(texts.WarningRamHelp, Does.Contain(language == "es" ? "de palabra" : "by voice"));
        });
    }

    [TestCase("es")]
    [TestCase("en")]
    public void The_help_says_the_ram_exit_code_and_force(string language)
    {
        string[] help = CommandLine.HelpText(language, @"C:\BAXY-App").Split('\n');

        Assert.That(help, Has.Some.Contain($" {QuietInstall.TooLittleRam} ").And.Contain("API"));
        Assert.That(help, Has.Some.Contain("--force"));
    }

    [Test]
    public void Force_goes_with_quiet_to_install()
    {
        Assert.That(CommandLine.Parse(["--quiet", "--force"]).Force, Is.True);
        Assert.That(CommandLine.Parse(["--force"]).Error, Is.Not.Null);
        Assert.That(CommandLine.Parse(["--quiet", "--uninstall", "--force"]).Error, Is.Not.Null);
    }

    [Test]
    public void A_faked_machine_is_read_as_the_real_one_would_be() =>
        Assert.That(
            MachineGpu.Faked("1002:1636:512:integrated, 10de:2520:6000"),
            Is.EqualTo(new[] { RyzenRadeon, Notebook[1] with { Integrated = null } }));

    // On this PC (a Windows 11 with DXCore): every graphics device DXGI lists gets an answer from Windows. DXGI can list one
    // card twice (this PC's RTX 4060 Ti, once more under a LUID DXCore does not know): that one is unread, and told as before.
    [Test]
    public void On_this_machine_windows_declares_each_device_integrated_or_not()
    {
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();

        Assert.That(
            adapters.GroupBy(static adapter => adapter.DeviceId).Where(static device => device.All(static adapter => adapter.Integrated is null)),
            Is.Empty,
            string.Join(", ", adapters));
    }

    private static QuietInstall Quiet(GpuSupport support, List<string> log, Action install) =>
        new(
            support,
            Updating: false,
            BaxyIsOpen: () => false,
            InstallAsync: () =>
            {
                install();
                return Task.CompletedTask;
            },
            Register: () => { },
            Log: log.Add)
        {
            Pace = TimeSpan.Zero,
            RegisterRetry = TimeSpan.Zero,
            Ram = new MachineRam(4096, 454),
            Integrated = true,
        };
}
