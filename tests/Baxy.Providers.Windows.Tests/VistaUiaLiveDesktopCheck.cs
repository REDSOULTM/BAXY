using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-108-vista: one WPF window of the test's own, read and pressed by the real worker: what a look newly says (B6, B7, B9,
/// B10, B13, B15) on a real UI Automation tree, which the described controls of the other tests cannot show. It shows without
/// activating and closes by its process id. Never runs in a suite: Explicit and BAXY_TRAMPAS_LIVE_CHECK=1.
/// </summary>
[TestFixture]
[Explicit("Opens a window on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class VistaUiaLiveDesktopCheck
{
    private const string Form = """
        Add-Type -AssemblyName PresentationFramework,PresentationCore,WindowsBase
        [xml]$xaml=@'
        <Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="Vista de BAXY" Width="520" Height="360"
                WindowStartupLocation="Manual" Left="80" Top="80" ShowActivated="False">
          <StackPanel>
            <CheckBox Content="Todos" IsThreeState="True" IsChecked="{x:Null}" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"/>
            <StackPanel Orientation="Horizontal"><CheckBox/><TextBlock Text="Comprar pan" Margin="4,0,0,0"/></StackPanel>
            <CheckBox IsChecked="True" Margin="0,30,0,0"/>
            <Slider AutomationProperties.Name="Zoom" Minimum="0" Maximum="100" Value="30" Width="200" HorizontalAlignment="Left"/>
            <TextBox AutomationProperties.Name="Correo" AutomationProperties.IsRequiredForForm="True" Width="200" HorizontalAlignment="Left"/>
            <TextBlock Text="Enviar"/>
            <Button Content="Enviar" Width="80" HorizontalAlignment="Left"/>
          </StackPanel>
        </Window>
        '@
        $form=[Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $xaml))
        $form.Add_ContentRendered({ [Console]::Out.WriteLine((New-Object System.Windows.Interop.WindowInteropHelper $form).Handle.ToInt64()) })
        [void]$form.ShowDialog()
        """;

    [Test]
    public async Task ARealTreeSaysWhatTheLookNowReads()
    {
        if (Environment.GetEnvironmentVariable("BAXY_TRAMPAS_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_TRAMPAS_LIVE_CHECK=1 is needed to touch the desktop.");
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-STA", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(Form)));
        using Process form = Process.Start(start)!;
        try
        {
            string? line = await form.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(30));
            Assert.That(long.TryParse(line, out long window), line);
            await Task.Delay(800);

            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            async Task<JsonElement> Ask(object command)
            {
                using JsonDocument? answer = await uia.SendAsync(
                    JsonSerializer.Serialize(command), TimeSpan.FromSeconds(20), CancellationToken.None);
                Assert.That(answer, Is.Not.Null);
                return answer!.RootElement.Clone();
            }

            JsonElement view = await Ask(new { cmd = "view", hwnd = window, limit = 60 });
            TestContext.Out.WriteLine(view.GetRawText());
            JsonElement[] controls = [.. view.GetProperty("controls").EnumerateArray()];
            JsonElement Named(string name) => controls.First(c => c.GetProperty("name").GetString() == name && c.GetProperty("kind").GetString() != "Text");
            string StateOf(string name) => Named(name).GetProperty("state").GetString() ?? string.Empty;

            Assert.Multiple(() =>
            {
                Assert.That(StateOf("Todos"), Does.Contain("indeterminate"), "B9");
                Assert.That(StateOf("Comprar pan"), Does.Contain("off"), "B7: the nameless check box takes the text on its right");
                Assert.That(Named("Comprar pan").GetProperty("kind").GetString(), Is.EqualTo("CheckBox"));
                Assert.That(StateOf("(checkbox)"), Does.Contain("on"), "B7: with no text beside it, its kind");
                Assert.That(Named("Zoom").GetProperty("rangeMin").GetDouble(), Is.EqualTo(0), "B10");
                Assert.That(Named("Zoom").GetProperty("rangeMax").GetDouble(), Is.EqualTo(100), "B10");
                Assert.That(StateOf("Correo"), Does.Contain("required"), "B13");
                Assert.That(controls.Count(c => c.GetProperty("name").GetString() == "Todos"), Is.EqualTo(1), "B6: the caption inside its check box leaves");
                Assert.That(controls.Count(c => c.GetProperty("name").GetString() == "Enviar"), Is.EqualTo(2), "B6: a Text elsewhere with a button's name stays");
            });

            JsonElement cut = await Ask(new { cmd = "view", hwnd = window, limit = 2, wanted = new[] { "inexistente", "zoom" } });
            TestContext.Out.WriteLine("cortada: " + cut.GetProperty("wantedMissing").GetRawText());
            Assert.That(cut.GetProperty("wantedMissing").EnumerateArray().Select(w => w.GetString()), Is.EqualTo(new[] { "inexistente" }), "B15");

            string zoom = Named("Zoom").GetProperty("id").GetString()!;
            JsonElement set = await Ask(new { cmd = "field", hwnd = window, controlId = zoom, text = "80" });
            JsonElement far = await Ask(new { cmd = "field", hwnd = window, controlId = zoom, text = "300" });
            TestContext.Out.WriteLine(set.GetRawText() + "\n" + far.GetRawText());
            string todos = Named("Todos").GetProperty("id").GetString()!;
            JsonElement click = await Ask(new { cmd = "click", hwnd = window, aliases = new[] { "Todos" }, controlId = todos });
            JsonElement read = await Ask(new { cmd = "postread" });
            TestContext.Out.WriteLine(click.GetRawText() + "\n" + read.GetRawText());
            string pan = Named("Comprar pan").GetProperty("id").GetString()!;
            JsonElement byNearName = await Ask(new { cmd = "click", hwnd = window, aliases = new[] { "Comprar pan" }, controlId = pan });
            JsonElement panRead = await Ask(new { cmd = "postread" });
            TestContext.Out.WriteLine(byNearName.GetRawText() + "\n" + panRead.GetRawText());

            Assert.Multiple(() =>
            {
                Assert.That(set.GetProperty("method").GetString(), Is.EqualTo("setvalue"), "B10");
                Assert.That(set.GetProperty("delivered").GetBoolean(), Is.True, "B10");
                Assert.That(far.GetProperty("error").GetString(), Is.EqualTo("input_value_out_of_range"), "B10");
                Assert.That(far.GetProperty("maximum").GetDouble(), Is.EqualTo(100), "B10");
                Assert.That(read.GetProperty("toggled").GetBoolean(), Is.True, "B9");
                Assert.That(read.GetProperty("nowState").GetString(), Is.EqualTo("off"), "B9: a press on a mixed box gives off");
                Assert.That(byNearName.GetProperty("error").GetString(), Is.Not.EqualTo("visible_control_label_mismatch"), "B7");
                Assert.That(panRead.GetProperty("nowState").GetString(), Is.EqualTo("on"), "B7");
            });
        }
        finally
        {
            if (!form.HasExited)
                form.Kill();
        }
    }
}
