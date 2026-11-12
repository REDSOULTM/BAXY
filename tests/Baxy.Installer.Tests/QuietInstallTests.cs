using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// INS-3 and INS-5: what --quiet answers to the script that ran it. 0 only when BAXY is installed and registered; a
/// machine without a graphics card BAXY can use is told so with a code of its own before anything is downloaded; a BAXY
/// that is installed but could not be registered is not «could not install».
/// </summary>
[TestFixture]
internal sealed class QuietInstallTests
{
    private readonly List<string> log = [];
    private int installed;
    private int registered;

    [SetUp]
    public void SetUp()
    {
        log.Clear();
        installed = 0;
        registered = 0;
    }

    [Test]
    public async Task A_machine_without_a_graphics_card_gets_its_own_code_and_downloads_nothing()
    {
        int code = await Quiet(GpuSupport.None).RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That(code, Is.EqualTo(QuietInstall.NoGraphicsCard));
            Assert.That(code, Is.EqualTo(1633), "ERROR_INSTALL_PLATFORM_UNSUPPORTED");
            Assert.That(installed, Is.Zero);
            Assert.That(registered, Is.Zero);
            Assert.That(log, Has.Some.Contain("graphics card"));
        });
    }

    // The window refuses only a machine with no card of the three makers; with one it could not measure, or a small
    // one, it offers «install anyway». A script already chose.
    [TestCase(GpuSupport.Measured)]
    [TestCase(GpuSupport.NotMeasured)]
    [TestCase(GpuSupport.TooLittleMemory)]
    public async Task A_machine_with_a_card_of_the_three_makers_installs(GpuSupport support)
    {
        int code = await Quiet(support).RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That(code, Is.Zero);
            Assert.That(installed, Is.EqualTo(1));
            Assert.That(registered, Is.EqualTo(1));
            Assert.That(log, Has.Some.EqualTo("installed"));
        });
    }

    // An update comes from a BAXY that already runs on this machine: the window does not ask it about the card either.
    [Test]
    public async Task An_update_is_not_refused_for_the_card()
    {
        int code = await (Quiet(GpuSupport.None) with { Updating = true }).RunAsync();

        Assert.That(code, Is.Zero);
        Assert.That(installed, Is.EqualTo(1));
    }

    [Test]
    public async Task An_open_BAXY_stops_it_before_anything_is_installed()
    {
        int code = await (Quiet(GpuSupport.Measured) with { BaxyIsOpen = () => true }).RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That(code, Is.EqualTo(Program.Failure));
            Assert.That(installed, Is.Zero);
        });
    }

    [Test]
    public async Task An_update_waits_for_the_BAXY_that_started_it_to_close()
    {
        int asked = 0;
        QuietInstall quiet = Quiet(GpuSupport.Measured) with { Updating = true, BaxyIsOpen = () => ++asked < 4 };

        Assert.That(await quiet.RunAsync(), Is.Zero);
        Assert.That(installed, Is.EqualTo(1));
    }

    [Test]
    public async Task Installed_but_not_registered_is_a_code_of_its_own_that_says_BAXY_is_there()
    {
        QuietInstall quiet = Quiet(GpuSupport.Measured) with { Register = () => Refuse() };

        int code = await quiet.RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That(code, Is.EqualTo(QuietInstall.NotRegistered));
            Assert.That(code, Is.Not.Zero.And.Not.EqualTo(Program.Failure));
            Assert.That(installed, Is.EqualTo(1), "only the registration is tried again");
            Assert.That(registered, Is.EqualTo(3));
            Assert.That(log, Has.Some.Contain("installed, but not registered"));
            Assert.That(log, Has.None.EqualTo("installed"));
        });
    }

    [Test]
    public async Task A_registration_refused_once_is_tried_again_alone()
    {
        QuietInstall quiet = Quiet(GpuSupport.Measured) with
        {
            Register = () =>
            {
                if (registered == 0)
                {
                    Refuse();
                }

                registered++;
            },
        };

        int code = await quiet.RunAsync();

        Assert.Multiple(() =>
        {
            Assert.That(code, Is.Zero);
            Assert.That(installed, Is.EqualTo(1));
            Assert.That(registered, Is.EqualTo(2));
        });
    }

    [Test]
    public void A_failed_install_is_not_reported_as_a_registration()
    {
        QuietInstall quiet = Quiet(GpuSupport.Measured) with
        {
            InstallAsync = () => Task.FromException(new InvalidDataException("damaged")),
        };

        Assert.ThrowsAsync<InvalidDataException>(quiet.RunAsync);
        Assert.That(registered, Is.Zero);
    }

    private void Refuse()
    {
        registered++;
        throw new NotRegisteredException("refused", new UnauthorizedAccessException());
    }

    private QuietInstall Quiet(GpuSupport support) =>
        new(
            support,
            Updating: false,
            BaxyIsOpen: () => false,
            InstallAsync: () =>
            {
                installed++;
                return Task.CompletedTask;
            },
            Register: () => registered++,
            Log: log.Add)
        {
            Pace = TimeSpan.Zero,
            RegisterRetry = TimeSpan.Zero,
        };
}
