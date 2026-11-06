using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-108 (campos), on real controls of the test's own: a window with custom UI Automation providers (the pattern of
/// agent-desktop's tests/fixture-app-windows/FixtureProviderHost.cs: a control's window answers WM_GETOBJECT with its own
/// provider) that do what no well-behaved control does on demand (applies the value and then raises, reshapes it, ignores
/// it, lets it go back, a list that does not open), two real RICHEDIT50W, and a WPF list with thousands of virtualized
/// entries. The worker and the adapters run as in the product. Never runs in a suite: Explicit and BAXY_CAMPOS_LIVE=1. It
/// acts only on its own windows, and closes them by process id.
/// </summary>
[TestFixture]
[Explicit("Opens windows on the person's desktop and types into its own.")]
[Category("LiveDesktop")]
[NonParallelizable]
public sealed class CamposLiveCheck : IDisposable
{
    private const string FixtureScript = """
        param([string]$Title,[string]$Log)
        Add-Type -AssemblyName System.Windows.Forms, UIAutomationProvider, UIAutomationTypes, WindowsBase
        Add-Type -ReferencedAssemblies System.Windows.Forms, UIAutomationProvider, UIAutomationTypes, WindowsBase -TypeDefinition @"
        using System;
        using System.Collections.Generic;
        using System.Runtime.InteropServices;
        using System.Threading;
        using System.Windows.Automation;
        using System.Windows.Automation.Provider;
        using System.Windows.Forms;

        public static class BaxyLog {
          public static string Path;
          public static void Say(string line) { lock (typeof(BaxyLog)) { System.IO.File.AppendAllText(Path, line + "\n", new System.Text.UTF8Encoding(false)); } }
        }

        public class BaxyField : Control, IRawElementProviderSimple, IValueProvider {
          string held; string mode; string label; volatile bool has; volatile bool dead; IntPtr own;
          public BaxyField(string label, string mode, string held) { this.label = label; this.mode = mode; this.held = held; TabStop = true; own = Handle; BaxyLog.Say(label + " hwnd " + own.ToInt64()); }
          void Hold(string value) { held = value; BaxyLog.Say(label + " holds " + value); }
          protected override void OnGotFocus(EventArgs e) { has = true; base.OnGotFocus(e); }
          protected override void OnLostFocus(EventArgs e) { has = false; base.OnLostFocus(e); }
          protected override void OnKeyPress(KeyPressEventArgs e) { Hold(held + e.KeyChar); e.Handled = true; }
          protected override void WndProc(ref Message m) {
            if (m.Msg == 0x3D && m.LParam == new IntPtr(-25)) { m.Result = AutomationInteropProvider.ReturnRawElementProvider(m.HWnd, m.WParam, m.LParam, this); return; }
            base.WndProc(ref m);
          }
          ProviderOptions IRawElementProviderSimple.ProviderOptions { get { return ProviderOptions.ServerSideProvider; } }
          IRawElementProviderSimple IRawElementProviderSimple.HostRawElementProvider { get { return AutomationInteropProvider.HostProviderFromHandle(own); } }
          object IRawElementProviderSimple.GetPatternProvider(int id) { return id == ValuePatternIdentifiers.Pattern.Id ? this : null; }
          object IRawElementProviderSimple.GetPropertyValue(int id) {
            if (id == AutomationElementIdentifiers.ControlTypeProperty.Id) return ControlType.Edit.Id;
            if (id == AutomationElementIdentifiers.NameProperty.Id) return label;
            if (id == AutomationElementIdentifiers.IsKeyboardFocusableProperty.Id) return true;
            if (id == AutomationElementIdentifiers.HasKeyboardFocusProperty.Id) return has;
            if (id == AutomationElementIdentifiers.IsPasswordProperty.Id) {
              if (mode == "password") return true;
              if (mode == "passwordRaises") throw new ElementNotAvailableException();
            }
            return null;
          }
          string IValueProvider.Value { get { BaxyLog.Say(label + " read"); if (dead) throw new ElementNotAvailableException(); return held; } }
          bool IValueProvider.IsReadOnly { get { return false; } }
          void IValueProvider.SetValue(string value) {
            BaxyLog.Say(label + " setvalue " + value);
            string was = held;
            switch (mode) {
              case "applyRaises": Hold(value); throw new COMException("applied, then failed", unchecked((int)0x80010105));
              case "applyDies": Hold(value); dead = true; throw new COMException("applied, then gone", unchecked((int)0x80010105));
              case "refuses": throw new COMException("refused", unchecked((int)0x80070005));
              case "ignores": return;
              case "reshapes": Hold(value + ",00 cm"); return;
              case "late": new Thread(delegate() { Thread.Sleep(150); Hold(value); }) { IsBackground = true }.Start(); return;
              case "partial": Hold(value.Substring(0, 1)); new Thread(delegate() { Thread.Sleep(120); Hold(value); }) { IsBackground = true }.Start(); return;
              case "goesBack": Hold(value); new Thread(delegate() { Thread.Sleep(60); Hold(was); }) { IsBackground = true }.Start(); return;
              default: Hold(value); return;
            }
          }
        }

        public class BaxyEntry : IRawElementProviderFragment, ISelectionItemProvider {
          public BaxyList Owner; public string Label; public int At; public bool Chosen;
          public System.Windows.Rect BoundingRectangle { get { return System.Windows.Rect.Empty; } }
          public IRawElementProviderFragmentRoot FragmentRoot { get { return Owner; } }
          public IRawElementProviderSimple[] GetEmbeddedFragmentRoots() { return null; }
          public int[] GetRuntimeId() { return new int[] { AutomationInteropProvider.AppendRuntimeId, At + 1 }; }
          public IRawElementProviderFragment Navigate(NavigateDirection d) {
            if (d == NavigateDirection.Parent) return Owner;
            if (d == NavigateDirection.NextSibling) return At + 1 < Owner.Items.Count ? Owner.Items[At + 1] : null;
            if (d == NavigateDirection.PreviousSibling) return At > 0 ? Owner.Items[At - 1] : null;
            return null;
          }
          public void SetFocus() { }
          public ProviderOptions ProviderOptions { get { return ProviderOptions.ServerSideProvider; } }
          public IRawElementProviderSimple HostRawElementProvider { get { return null; } }
          public object GetPatternProvider(int id) { return id == SelectionItemPatternIdentifiers.Pattern.Id ? this : null; }
          public object GetPropertyValue(int id) {
            if (id == AutomationElementIdentifiers.ControlTypeProperty.Id) return ControlType.ListItem.Id;
            if (id == AutomationElementIdentifiers.NameProperty.Id) return Label;
            return null;
          }
          public void Select() { foreach (BaxyEntry item in Owner.Items) item.Chosen = false; Chosen = true; Owner.Took(Label); }
          public void AddToSelection() { Select(); }
          public void RemoveFromSelection() { Chosen = false; }
          public bool IsSelected { get { Owner.AskedItem(); return Chosen; } }
          public IRawElementProviderSimple SelectionContainer { get { return Owner; } }
        }

        // raises: Expand raises, entries there while closed. noPattern: no ExpandCollapse, entries there. raisesEmpty: Expand
        // raises, no entries. opens: entries only while open. itemsDie: an item asked after the list closed is gone, the box
        // says the entry. boxRefuses: the item says chosen, the box never takes it. empties: opens, no entries ever.
        public class BaxyList : Control, IRawElementProviderFragmentRoot, IExpandCollapseProvider, IValueProvider {
          public List<BaxyEntry> Items = new List<BaxyEntry>();
          string label; string mode; string shown = ""; volatile bool open; IntPtr own;
          public BaxyList(string label, string mode, string[] names) {
            this.label = label; this.mode = mode; own = Handle;
            names = names ?? new string[0];
            if (mode == "boxRefuses") shown = "Rojo";
            for (int k = 0; k < names.Length; k++) Items.Add(new BaxyEntry { Owner = this, Label = names[k], At = k });
            BaxyLog.Say(label + " hwnd " + own.ToInt64());
          }
          public void Took(string entry) { BaxyLog.Say(label + " select " + entry); if (mode != "boxRefuses") shown = entry; }
          public void AskedItem() { if (mode == "itemsDie" && !open) throw new ElementNotAvailableException(); }
          protected override void WndProc(ref Message m) {
            if (m.Msg == 0x3D && m.LParam == new IntPtr(-25)) { m.Result = AutomationInteropProvider.ReturnRawElementProvider(m.HWnd, m.WParam, m.LParam, this); return; }
            base.WndProc(ref m);
          }
          bool Listed { get { return mode == "raises" || mode == "noPattern" || ((mode == "opens" || mode == "itemsDie" || mode == "boxRefuses") && open); } }
          public System.Windows.Rect BoundingRectangle { get { return System.Windows.Rect.Empty; } }
          public IRawElementProviderFragmentRoot FragmentRoot { get { return this; } }
          public IRawElementProviderSimple[] GetEmbeddedFragmentRoots() { return null; }
          public int[] GetRuntimeId() { return null; }
          public IRawElementProviderFragment Navigate(NavigateDirection d) {
            if (!Listed || Items.Count == 0) return null;
            if (d == NavigateDirection.FirstChild) return Items[0];
            if (d == NavigateDirection.LastChild) return Items[Items.Count - 1];
            return null;
          }
          public void SetFocus() { }
          public IRawElementProviderFragment ElementProviderFromPoint(double x, double y) { return null; }
          public IRawElementProviderFragment GetFocus() { return null; }
          public ProviderOptions ProviderOptions { get { return ProviderOptions.ServerSideProvider; } }
          public IRawElementProviderSimple HostRawElementProvider { get { return AutomationInteropProvider.HostProviderFromHandle(own); } }
          public object GetPatternProvider(int id) {
            if (id == ExpandCollapsePatternIdentifiers.Pattern.Id && mode != "noPattern") return this;
            if (id == ValuePatternIdentifiers.Pattern.Id && (mode == "itemsDie" || mode == "boxRefuses")) return this;
            return null;
          }
          public object GetPropertyValue(int id) {
            if (id == AutomationElementIdentifiers.ControlTypeProperty.Id) return ControlType.ComboBox.Id;
            if (id == AutomationElementIdentifiers.NameProperty.Id) return label;
            return null;
          }
          public void Expand() { BaxyLog.Say(label + " expand"); if (mode.StartsWith("raises")) throw new InvalidOperationException("no list"); open = true; }
          public void Collapse() { open = false; BaxyLog.Say(label + " collapse"); }
          public ExpandCollapseState ExpandCollapseState { get { return open ? ExpandCollapseState.Expanded : ExpandCollapseState.Collapsed; } }
          string IValueProvider.Value { get { return shown; } }
          bool IValueProvider.IsReadOnly { get { return true; } }
          void IValueProvider.SetValue(string value) { throw new InvalidOperationException(); }
        }

        public static class BaxyRich {
          [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern IntPtr LoadLibrary(string name);
          [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr CreateWindowEx(int ex, string cls, string title, int style, int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr inst, IntPtr param);
          public static IntPtr Make(IntPtr parent, int y) {
            LoadLibrary("Msftedit.dll");
            return CreateWindowEx(0, "RICHEDIT50W", "", 0x50800000, 10, y, 360, 26, parent, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
          }
        }
        "@
        [BaxyLog]::Path=$Log
        $f=New-Object System.Windows.Forms.Form
        $f.Text=$Title; $f.StartPosition='Manual'; $f.Left=40; $f.Top=40; $f.Width=420; $f.Height=720
        $script:y=10
        function Add-One($control){ $control.Left=10; $control.Top=$script:y; $control.Width=360; $control.Height=24; $control.BackColor=[System.Drawing.Color]::LightYellow; $f.Controls.Add($control); $script:y+=28 }
        foreach($pair in @(@('Aplica y falla','applyRaises'),@('Aplica y falla sin foco','applyRaises'),@('Aplica y muere','applyDies'),@('Rehusa','refuses'),@('Rehusa sin foco','refuses'),@('Ignora','ignores'),@('Reforma','reshapes'),@('Tarda','late'),@('Por partes','partial'),@('Vuelve','goesBack'),@('Normal','plain'),@('Secreto','password'),@('Secreto sin leer','passwordRaises'))){
          Add-One (New-Object BaxyField($pair[0],$pair[1],''))
        }
        foreach($pair in @(@('Lista que falla','raises'),@('Lista sin patron','noPattern'),@('Lista vacia','raisesEmpty'),@('Lista abierta vacia','empties'),@('Lista que abre','opens'),@('Lista cuyas filas mueren','itemsDie'),@('Lista que no toma','boxRefuses'))){
          Add-One (New-Object BaxyList($pair[0],$pair[1],[string[]]$(if($pair[1] -match 'Empty|empties'){ @() } else { @('Rojo','Verde','Azul') })))
        }
        $rich=[BaxyRich]::Make($f.Handle,$script:y)
        [BaxyLog]::Say(('Rico hwnd {0}' -f [long]$rich))
        [System.Windows.Forms.Application]::Run($f)
        """;

    private const string LongListScript = """
        param([string]$Title,[string]$Log)
        Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
        $w=New-Object System.Windows.Window
        $w.Title=$Title; $w.Width=380; $w.Height=260; $w.Left=480; $w.Top=60
        $sp=New-Object System.Windows.Controls.StackPanel
        $cb=New-Object System.Windows.Controls.ComboBox
        [System.Windows.Automation.AutomationProperties]::SetName($cb,'Lista larga')
        $factory=New-Object System.Windows.FrameworkElementFactory([System.Windows.Controls.VirtualizingStackPanel])
        $cb.ItemsPanel=New-Object System.Windows.Controls.ItemsPanelTemplate($factory)
        [System.Windows.Controls.VirtualizingPanel]::SetIsVirtualizing($cb,$true)
        $cb.MaxDropDownHeight=120
        $cb.ItemsSource=[string[]](1..3000 | ForEach-Object { 'Opcion {0:0000}' -f $_ })
        $cb.Add_SelectionChanged({ Add-Content -Path $Log -Value ('elegida {0}' -f $cb.SelectedItem) -Encoding UTF8 })
        [void]$sp.Children.Add($cb)
        $w.Content=$sp
        [void]$w.ShowDialog()
        """;

    private readonly string _tag = Guid.NewGuid().ToString("N")[..6];
    private string _folder = string.Empty;
    private string _title = string.Empty;
    private string _log = string.Empty;
    private string _longTitle = string.Empty;
    private string _longLog = string.Empty;
    private Process? _fixture;
    private Process? _longList;
    private nint _window;
    private nint _longWindow;
    private UiaWorkerHost? _uia;
    private WindowsVisibleControlAdapter? _visible;
    private WindowsDesktopInteractionAdapter? _typing;

    [OneTimeSetUp]
    public async Task OpenTheWindows()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CAMPOS_LIVE") != "1")
            Assert.Ignore("BAXY_CAMPOS_LIVE=1 is needed to touch the desktop.");
        _folder = Path.Combine(Path.GetTempPath(), "baxy-campos-" + _tag);
        Directory.CreateDirectory(_folder);
        _title = "BAXY campos " + _tag;
        _log = Path.Combine(_folder, "campos.log");
        _longTitle = "BAXY lista larga " + _tag;
        _longLog = Path.Combine(_folder, "lista.log");
        File.WriteAllText(_longLog, string.Empty);
        _fixture = Start("campos.ps1", FixtureScript, "-Title", _title, "-Log", _log);
        _longList = Start("lista.ps1", LongListScript, "-Title", _longTitle, "-Log", _longLog);
        _window = await FindAsync(_title);
        _longWindow = await FindAsync(_longTitle);
        Assert.That(new[] { _window, _longWindow }, Has.None.Zero, "the windows appeared");
        _uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        // The windows of this test by the name asked: a process «powershell» names no application.
        _visible = new WindowsVisibleControlAdapter(
            _uia, new WindowsVisibleOcrLocator(), new WindowsVisibleVisionLocator(), new OpenedApplicationFocus(), VisibleClickTiming.Default,
            (application, _) => ValueTask.FromResult(application == _longTitle ? _longWindow : _window));
        _typing = new WindowsDesktopInteractionAdapter(_visible) { Scripts = _uia };
    }

    public void Dispose()
    {
        _uia?.Dispose();
        _visible?.Dispose();
    }

    [OneTimeTearDown]
    public void CloseTheWindows()
    {
        foreach (Process? own in new[] { _fixture, _longList })
        {
            if (own is null)
                continue;
            try
            {
                if (!own.HasExited)
                    own.Kill(entireProcessTree: true);
                own.WaitForExit(5000);
            }
            catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
            {
            }

            own.Dispose();
        }

        try
        {
            if (_folder.Length > 0)
                Directory.Delete(_folder, recursive: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
        }
    }

    // What the provider holds now, as it logged it (never read through the worker under test).
    private string Holds(string label)
    {
        string prefix = label + " holds ";
        return Lines().Where(line => line.StartsWith(prefix, StringComparison.Ordinal))
            .Select(line => line[prefix.Length..]).LastOrDefault() ?? string.Empty;
    }

    private int Count(string line) => Lines().Count(seen => seen == line);

    private string[] Lines()
    {
        using var stream = new FileStream(_log, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream, Encoding.UTF8);
        return reader.ReadToEnd().Split('\n', StringSplitOptions.RemoveEmptyEntries);
    }

    private long Hwnd(string label)
    {
        string prefix = label + " hwnd ";
        return long.Parse(Lines().First(line => line.StartsWith(prefix, StringComparison.Ordinal))[prefix.Length..],
            System.Globalization.CultureInfo.InvariantCulture);
    }

    private async Task<JsonElement> WorkerFieldAsync(long field, string? text, bool replace = false)
    {
        var request = new System.Text.Json.Nodes.JsonObject
        {
            ["cmd"] = "field", ["hwnd"] = (long)_window, ["controlId"] = "42." + field, ["text"] = text, ["replace"] = replace,
        };
        using JsonDocument? answer = await _uia!.SendAsync(request.ToJsonString(), TimeSpan.FromSeconds(20), CancellationToken.None);
        Assert.That(answer, Is.Not.Null);
        JsonElement root = answer!.RootElement.Clone();
        TestContext.Out.WriteLine($"worker: {root}");
        return root;
    }

    // The index of the control the view lists by that name, as a model would take it.
    private async Task<int> IndexAsync(string title, string name)
    {
        for (int attempt = 0; attempt < 3; attempt++)
        {
            ExternalCapabilityReceipt view = await _visible!.InvokeAsync(
                "input.visible.controls",
                JsonDocument.Parse(JsonSerializer.Serialize(new { application = title, limit = 60 })).RootElement,
                CancellationToken.None);
            if (view.Result is { ValueKind: JsonValueKind.Object } seen && seen.TryGetProperty("controls", out JsonElement controls))
            {
                foreach (JsonElement control in controls.EnumerateArray())
                {
                    if (control.GetProperty("name").GetString() == name)
                        return control.GetProperty("i").GetInt32();
                }

                TestContext.Out.WriteLine("view: " + controls);
            }

            TestContext.Out.WriteLine($"view: error={view.ErrorCode} result={view.Result}");
            await Task.Delay(500);
        }

        Assert.Fail("not in the view: " + name);
        return -1;
    }

    private async Task<ExternalCapabilityReceipt> TypeAsync(string name, string text, bool replace = false, bool entry = false, bool focus = false, nint window = 0, string? title = null, bool fronted = false)
    {
        window = window == 0 ? _window : window;
        title ??= _title;
        int index = await IndexAsync(title, name);
        if (focus || fronted)
        {
            bool front = false;
            for (int attempt = 0; attempt < 20 && !front; attempt++)
            {
                front = VisibleControlSurface.BringToFront(window);
                if (!front)
                    await Task.Delay(100);
            }

            Assert.That(front, Is.True, "its own window in front");
        }

        if (focus)
        {
            using JsonDocument? focused = await _uia!.SendAsync(
                JsonSerializer.Serialize(new { cmd = "focus", hwnd = (long)window, controlId = "42." + Hwnd(name) }),
                TimeSpan.FromSeconds(10), CancellationToken.None);
            TestContext.Out.WriteLine($"focus: {focused?.RootElement}");
        }

        Assert.That(VisibleControlSurface.WindowTitle(window), Is.EqualTo(title), "still the test's own window");
        ExternalCapabilityReceipt receipt = await _typing!.InvokeAsync(
            "input.text.type",
            JsonDocument.Parse(JsonSerializer.Serialize(new { text, window = (long)window, index, replace, entry })).RootElement,
            CancellationToken.None);
        TestContext.Out.WriteLine($"{name}: verified={receipt.Verified} error={receipt.ErrorCode} may={receipt.EffectMayHaveOccurred} result={receipt.Result}");
        return receipt;
    }

    // A4: the provider applied the value and then raised. The field's own read said so; it was taken as refused and the
    // keyboard wrote it again: «holahola», verified. Contracase: one that raised and applied nothing takes the keyboard.
    [Test]
    public async Task A4_AValueAppliedBeforeRaisingIsNotTypedAgain()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Aplica y falla", "hola", focus: true);
        await Task.Delay(300);
        Assert.Multiple(() =>
        {
            Assert.That(Holds("Aplica y falla"), Is.EqualTo("hola"), "the text once");
            Assert.That(receipt.Verified, Is.True, "the value read back is the text");
        });
    }

    [Test]
    public async Task A4_AValueAppliedBeforeRaisingIsNotToldUnreached()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Aplica y falla sin foco", "hola");
        Assert.Multiple(() =>
        {
            Assert.That(Holds("Aplica y falla sin foco"), Is.EqualTo("hola"));
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_field_not_reachable"), "it was reached");
            Assert.That(receipt.Verified, Is.True);
        });
    }

    // Review of uso-108, item 1: the field died with the raise. Its reads give nothing: that is no read, not an empty field: it
    // must not be told refused, or another route writes the text again.
    [Test]
    public async Task A4_AFieldThatDiedAfterApplyingIsNotToldRefused()
    {
        JsonElement answer = await WorkerFieldAsync(Hwnd("Aplica y muere"), "hola");
        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("error").GetString(), Is.Not.EqualTo("field_setvalue_refused"));
            Assert.That(answer.GetProperty("ok").GetBoolean(), Is.True);
            Assert.That(answer.GetProperty("method").GetString(), Is.EqualTo("setvalue"));
            Assert.That(answer.GetProperty("delivered").GetBoolean(), Is.False);
            Assert.That(answer.TryGetProperty("fieldUnchanged", out _), Is.False, "nothing was read");
        });
    }

    [Test]
    public async Task A4_Contracase_ARaiseThatAppliedNothingStaysRefused()
    {
        ExternalCapabilityReceipt unfocused = await TypeAsync("Rehusa sin foco", "hola");
        ExternalCapabilityReceipt focused = await TypeAsync("Rehusa", "hola", focus: true);
        await Task.Delay(300);
        Assert.Multiple(() =>
        {
            Assert.That(unfocused.ErrorCode, Is.EqualTo("input_field_not_reachable"));
            Assert.That(Holds("Rehusa sin foco"), Is.Empty);
            Assert.That(Holds("Rehusa"), Is.EqualTo("hola"), "the keyboard wrote it, once");
        });
        TestContext.Out.WriteLine($"focused verified={focused.Verified} error={focused.ErrorCode}");
    }

    // A3 and hondo 11.6, 12.12: a list that does not open is searched anyway (agent-desktop: select.rs:161-178, its A19-7
    // measured WPF's items present while closed); none read has its own code.
    [TestCase("Lista que falla")]
    [TestCase("Lista sin patron")]
    public async Task A3_AListThatDoesNotOpenIsSearchedAnyway(string list)
    {
        ExternalCapabilityReceipt receipt = await TypeAsync(list, "Verde", entry: true);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(Count(list + " select Verde"), Is.EqualTo(1));
        });
    }

    [TestCase("Lista vacia", false)]
    [TestCase("Lista abierta vacia", true)]
    public async Task A3_AListWithNoEntryReadSaysSo(string list, bool opened)
    {
        ExternalCapabilityReceipt receipt = await TypeAsync(list, "Verde", entry: true);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_list_not_read"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.EqualTo(opened));
        });
    }

    [Test]
    public async Task A3_Contracase_AnOpenedListWithoutThatEntryKeepsItsCode()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Lista que abre", "Violeta", entry: true);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_entry_not_found"));
            Assert.That(receipt.Result?.GetProperty("candidates").GetArrayLength(), Is.EqualTo(3));
            Assert.That(Count("Lista que abre collapse"), Is.GreaterThan(0), "closed again");
        });
    }

    [Test]
    public async Task A3_AnEntryOfAVirtualizedListIsFound()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Lista larga", "Opcion 2500", entry: true, window: _longWindow, title: _longTitle, fronted: true);
        await Task.Delay(300);
        string chosen = File.ReadAllText(_longLog);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(chosen, Does.Contain("elegida Opcion 2500"));
        });
    }

    [Test]
    public async Task A3_AVirtualizedListWithoutThatEntryIsToldCut()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Lista larga", "Opcion que no existe", entry: true, window: _longWindow, title: _longTitle, fronted: true);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_entry_not_found"));
            Assert.That(receipt.Result?.GetProperty("truncated").GetBoolean(), Is.True);
        });
    }

    // Hondo 12.1 (agent-desktop: actions/select_tests.rs:190-204): the box's reading outranks the item's.
    [Test]
    public async Task H121_AChoiceTheBoxShowsIsTakenThoughItsItemIsGone()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Lista cuyas filas mueren", "Verde", entry: true);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
        });
    }

    [Test]
    public async Task H121_Contracase_AnItemSelectedTheBoxDidNotTakeIsNot()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Lista que no toma", "Verde", entry: true);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.Result?.GetProperty("fieldNow").GetString(), Is.EqualTo("Rojo"));
        });
    }

    // A11: the read of IsPassword failed and the field was written (SetValue, measured on the base with this provider).
    [Test]
    public async Task A11_AFieldThatDoesNotSayItIsNoPasswordIsNotWritten()
    {
        JsonElement answer = await WorkerFieldAsync(Hwnd("Secreto sin leer"), "clave");
        TestContext.Out.WriteLine("password: " + answer.GetProperty("password"));
        Assert.Multiple(() =>
        {
            Assert.That(Count("Secreto sin leer setvalue clave"), Is.Zero, "SetValue was not called");
            Assert.That(answer.GetProperty("password").GetBoolean(), Is.True);
        });
    }

    // Hondo 12.13: a password is neither written nor its value read for its length.
    [Test]
    public async Task A11_Contracase_APasswordIsNeitherWrittenNorRead()
    {
        JsonElement answer = await WorkerFieldAsync(Hwnd("Secreto"), "clave");
        Assert.Multiple(() =>
        {
            Assert.That(Count("Secreto setvalue clave"), Is.Zero);
            Assert.That(answer.GetProperty("valueLength").GetInt32(), Is.EqualTo(-1), "not even for its length");
            Assert.That(answer.ToString(), Does.Not.Contain("fieldNow"));
        });
    }

    // C7: a real RICHEDIT50W through the worker's field command (a Win32 edit takes the messages' route in the product,
    // so this is the route a rich edit with no window of its own would take).
    [Test]
    public async Task C7_ARichEditsValueIsNotItsFinalMark()
    {
        long rich = Hwnd("Rico");
        JsonElement empty = await WorkerFieldAsync(rich, null);
        JsonElement written = await WorkerFieldAsync(rich, "hola");
        JsonElement again = await WorkerFieldAsync(rich, "hola", replace: true);
        Assert.Multiple(() =>
        {
            Assert.That(empty.GetProperty("valueLength").GetInt32(), Is.Zero, "an empty rich edit is empty");
            Assert.That(written.GetProperty("delivered").GetBoolean(), Is.True);
            Assert.That(again.TryGetProperty("alreadyReached", out JsonElement reached) && reached.GetBoolean(), Is.True);
        });
    }

    // B12 on real answers.
    [Test]
    public async Task B12_AValueIgnoredIsToldUnchanged()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Ignora", "hola");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.Result?.GetProperty("fieldUnchanged").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task B12_AValueReshapedIsToldAsItStayed()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Reforma", "3");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.Result?.GetProperty("fieldNow").GetString(), Is.EqualTo("3,00 cm"));
        });
    }

    [TestCase("Tarda")]
    [TestCase("Por partes")]
    [TestCase("Normal")]
    public async Task B12_Contracase_AValueThatArrivesIsVerified(string name)
    {
        ExternalCapabilityReceipt receipt = await TypeAsync(name, "hola");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.ToString(), Does.Not.Contain("fieldNow"));
        });
    }

    // Hondo 11.1 (agent-desktop PR #565): a value that went back did not hold.
    [Test]
    public async Task H111_AValueThatGoesBackIsNotVerified()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Vuelve", "hola");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.Result?.GetProperty("fieldUnchanged").GetBoolean(), Is.True);
        });
    }

    private Process Start(string name, string script, params string[] arguments)
    {
        string path = Path.Combine(_folder, name);
        File.WriteAllText(path, script, new UTF8Encoding(false));
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", path })
            start.ArgumentList.Add(argument);
        foreach (string argument in arguments)
            start.ArgumentList.Add(argument);
        return Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
    }

    private static async Task<nint> FindAsync(string title)
    {
        for (int attempt = 0; attempt < 300; attempt++)
        {
            nint window = FindWindowW(null, title);
            if (window != 0)
                return window;
            await Task.Delay(100);
        }

        return 0;
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint FindWindowW(string? className, string? windowName);
}

/// <summary>
/// Uso-108 (campos), on a Chromium window of the test's own (a temporary profile, a local page whose fields each say in
/// the title how many <c>input</c> events they heard). C8: an empty contenteditable answers its document range with its
/// accessible name. C9: <c>SetValue</c> on a contenteditable with <c>role=textbox</c> reads back and the page hears nothing,
/// while an <c>input</c> and a <c>textarea</c> hear it (measured on Edge; agent-desktop #395). Explicit and
/// BAXY_CAMPOS_LIVE=1; BAXY_CAMPOS_BROWSER names the browser (Edge by default). Closed by process id.
/// </summary>
[TestFixture]
[Explicit("Opens a browser window on the person's desktop and types into its own page.")]
[Category("LiveDesktop")]
[NonParallelizable]
public sealed class CamposChromiumLiveCheck : IDisposable
{
    private const string PageTitle = "Pizarra campos 8K";

    private const string Page = $$"""
        <!doctype html>
        <html lang="es"><head><meta charset="utf-8"><title>{{PageTitle}}</title></head>
        <body>
        <div id="rico" contenteditable="true" aria-label="Rico vacio" style="border:1px solid #888;min-height:30px;width:400px"></div>
        <div id="rol" role="textbox" contenteditable="true" aria-label="Rol vacio" style="border:1px solid #888;min-height:30px;width:400px"></div>
        <div id="rolp" role="textbox" contenteditable="true" aria-label="Rol parrafo" style="border:1px solid #888;min-height:30px;width:400px"><p><br></p></div>
        <div id="rolb" role="textbox" contenteditable="true" aria-label="Rol salto" style="border:1px solid #888;min-height:30px;width:400px"><br></div>
        <div id="roll" role="textbox" contenteditable="true" aria-label="Rol lleno" style="border:1px solid #888;min-height:30px;width:400px">antes</div>
        <div id="rolf" role="textbox" contenteditable="true" aria-label="Rol foco" style="border:1px solid #888;min-height:30px;width:400px"></div>
        <div id="rols" role="textbox" contenteditable="true" aria-label="Rol sin foco" style="border:1px solid #888;min-height:30px;width:400px"><p><br></p></div>
        <div id="rolr" role="textbox" contenteditable="true" aria-label="Rol reemplazo" style="border:1px solid #888;min-height:30px;width:400px"><p><br></p></div>
        <div id="rolx" role="textbox" contenteditable="true" aria-label="Rol largo" style="border:1px solid #888;min-height:30px;width:400px;max-height:60px;overflow:auto"><p><br></p></div>
        <textarea id="area" aria-label="Area vacia" rows="2" cols="50"></textarea><br>
        <input id="linea" aria-label="Linea vacia" type="text"><br>
        <input id="busca" aria-label="Busqueda" type="search"><br>
        <input id="correo" aria-label="Correo" type="email"><br>
        <input id="llena" aria-label="Linea llena" type="text" value="antes"><br>
        <input id="control" aria-label="Controlada" type="text"><br>
        <script>
        const oido={};
        // As a framework's composer: each event takes a few ms of work.
        document.getElementById('rolx').addEventListener('input',e=>{ const t=Date.now(); while(Date.now()-t<3){} e.target.dataset.n=e.target.innerText.length; });
        const dicho=()=>{ document.title='{{PageTitle}} | '+Object.keys(oido).map(k=>k+'='+oido[k]).join(' '); };
        for(const el of document.querySelectorAll('[aria-label]')){
          el.addEventListener('input',()=>{ oido[el.id]=(oido[el.id]||0)+1; dicho(); });
        }
        // As a framework's controlled input: what it holds is its own state, and only an event changes that state.
        const control=document.getElementById('control');
        let estado='';
        control.addEventListener('input',()=>{ estado=''; setTimeout(()=>{ control.value=estado; },40); });
        </script>
        </body></html>
        """;

    private string _folder = string.Empty;
    private readonly List<int> _own = [];
    private HashSet<int> _before = [];
    private nint _window;
    private UiaWorkerHost? _uia;
    private WindowsVisibleControlAdapter? _visible;
    private WindowsDesktopInteractionAdapter? _typing;

    [OneTimeSetUp]
    public async Task OpenTheBrowser()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CAMPOS_LIVE") != "1")
            Assert.Ignore("BAXY_CAMPOS_LIVE=1 is needed to touch the desktop.");
        string browser = Environment.GetEnvironmentVariable("BAXY_CAMPOS_BROWSER") is { Length: > 0 } named
            ? named
            : @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";
        if (!File.Exists(browser))
            Assert.Ignore("No browser at " + browser);
        _folder = Path.Combine(Path.GetTempPath(), "baxy-campos-web-" + Guid.NewGuid().ToString("N")[..6]);
        string profile = Path.Combine(_folder, "perfil");
        Directory.CreateDirectory(profile);
        string page = Path.Combine(_folder, "pizarra.html");
        await File.WriteAllTextAsync(page, Page);
        _before = Process.GetProcesses().Select(static process =>
        {
            using (process)
                return process.Id;
        }).ToHashSet();
        var start = new ProcessStartInfo(browser)
        {
            ArgumentList = { "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check", "--new-window" },
            UseShellExecute = false,
        };
        if (string.Equals(Path.GetFileName(browser), "msedge.exe", StringComparison.OrdinalIgnoreCase))
            start.ArgumentList.Add("--inprivate");
        if (Environment.GetEnvironmentVariable("BAXY_CAMPOS_BROWSER_ARG") is { Length: > 0 } flag)
            start.ArgumentList.Add(flag);
        start.ArgumentList.Add(new Uri(page).AbsoluteUri);
        using (Process? started = Process.Start(start))
            _own.Add(started?.Id ?? 0);
        (nint window, uint drawn) = await OwnWindowAsync();
        _own.Add(unchecked((int)drawn));
        _window = window;
        Assert.That(_window, Is.Not.EqualTo((nint)0), "the test's own browser window");
        _uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        _visible = new WindowsVisibleControlAdapter(_uia);
        _typing = new WindowsDesktopInteractionAdapter(_visible) { Scripts = _uia };
        await Task.Delay(1500);
    }

    public void Dispose()
    {
        _uia?.Dispose();
        _visible?.Dispose();
    }

    [OneTimeTearDown]
    public async Task CloseTheBrowser()
    {
        foreach (int id in _own.Where(id => id > 0 && !_before.Contains(id)).Distinct())
        {
            try
            {
                using Process process = Process.GetProcessById(id);
                process.Kill(entireProcessTree: true);
            }
            catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
            }
        }

        for (int attempt = 0; attempt < 10 && _folder.Length > 0 && Directory.Exists(_folder); attempt++)
        {
            try
            {
                Directory.Delete(_folder, recursive: true);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                await Task.Delay(500);
            }
        }
    }

    private string Heard(string id)
    {
        string title = VisibleControlSurface.WindowTitle(_window);
        int bar = title.IndexOf(id + "=", StringComparison.Ordinal);
        if (bar < 0)
            return "0";
        string rest = title[(bar + id.Length + 1)..];
        int end = 0;
        while (end < rest.Length && char.IsAsciiDigit(rest[end]))
            end++;
        return rest[..end];
    }

    private async Task<ExternalCapabilityReceipt> TypeAsync(string name, string text, bool focus = false, bool replace = false, Func<Task>? before = null, bool quiet = false)
    {
        ExternalCapabilityReceipt view = default!;
        JsonElement control = default;
        bool listed = false;
        for (int attempt = 0; attempt < 6 && !listed; attempt++)
        {
            view = await _visible!.InvokeAsync(
                "input.visible.controls",
                JsonDocument.Parse(JsonSerializer.Serialize(new { application = PageTitle, limit = 60 })).RootElement,
                CancellationToken.None);
            if (view.Result is { ValueKind: JsonValueKind.Object } seen && seen.TryGetProperty("controls", out JsonElement controls))
            {
                foreach (JsonElement each in controls.EnumerateArray())
                {
                    if (each.GetProperty("name").GetString() == name)
                    {
                        control = each.Clone();
                        listed = true;
                        break;
                    }
                }

                if (!listed)
                    TestContext.Out.WriteLine("view: " + string.Join(" | ", controls.EnumerateArray().Select(each => each.GetProperty("kind") + ":" + each.GetProperty("name"))));
            }

            if (!listed)
                await Task.Delay(500);
        }

        Assert.That(listed, Is.True, "in the view: " + name);
        int index = control.GetProperty("i").GetInt32();
        TestContext.Out.WriteLine($"{name}: kind={control.GetProperty("kind")} state={control.GetProperty("state")} i={index}");
        if (focus)
        {
            bool front = false;
            for (int attempt = 0; attempt < 20 && !front; attempt++)
            {
                front = VisibleControlSurface.BringToFront(_window);
                if (!front)
                    await Task.Delay(100);
            }

            Assert.That(front, Is.True, "its own window in front");
            ExternalCapabilityReceipt click = await _visible!.InvokeAsync(
                "input.visible.click",
                JsonDocument.Parse(JsonSerializer.Serialize(new { label = name, index, window = (long)_window })).RootElement,
                CancellationToken.None);
            TestContext.Out.WriteLine($"click: verified={click.Verified} error={click.ErrorCode}");
            await Task.Delay(300);
            index = await IndexAgainAsync(name) ?? index;
            if (before is not null)
                await before();
        }

        Assert.That(VisibleControlSurface.WindowTitle(_window), Does.StartWith(PageTitle), "still the test's own window");
        ExternalCapabilityReceipt receipt = await _typing!.InvokeAsync(
            "input.text.type",
            JsonDocument.Parse(JsonSerializer.Serialize(new { text, window = (long)_window, index, replace })).RootElement,
            CancellationToken.None);
        TestContext.Out.WriteLine($"{name}: verified={receipt.Verified} error={receipt.ErrorCode} may={receipt.EffectMayHaveOccurred} result={(quiet ? "-" : receipt.Result)}");
        await Task.Delay(400);
        TestContext.Out.WriteLine("title: " + VisibleControlSurface.WindowTitle(_window));
        return receipt;
    }

    private async Task<int?> IndexAgainAsync(string name)
    {
        ExternalCapabilityReceipt view = await _visible!.InvokeAsync(
            "input.visible.controls",
            JsonDocument.Parse(JsonSerializer.Serialize(new { application = PageTitle, limit = 60 })).RootElement,
            CancellationToken.None);
        if (view.Result is { ValueKind: JsonValueKind.Object } seen && seen.TryGetProperty("controls", out JsonElement controls))
        {
            foreach (JsonElement each in controls.EnumerateArray())
            {
                if (each.GetProperty("name").GetString() == name)
                    return each.GetProperty("i").GetInt32();
            }
        }

        return null;
    }

    // C8: the empty contenteditable with the focus: its text as the worker reads it is empty, not its accessible name, and
    // what the keyboard then writes is read back and heard.
    [Test]
    [Order(1)]
    public async Task C8_AnEmptyRichFieldHoldsNoText()
    {
        ExternalCapabilityReceipt typed = await TypeAsync("Rico vacio", "hola", focus: true, before: async () =>
        {
            // The click gave the front back: the focus of a window is read with it in front.
            Assert.That(VisibleControlSurface.BringToFront(_window), Is.True);
            await Task.Delay(200);
            using JsonDocument? read = await _uia!.SendAsync(
                JsonSerializer.Serialize(new { cmd = "focusvalue", hwnd = (long)_window, max = 200 }), TimeSpan.FromSeconds(30), CancellationToken.None);
            TestContext.Out.WriteLine($"focusvalue: {read?.RootElement}");
            Assert.That(read?.RootElement.GetProperty("kind").GetString(), Is.EqualTo("Group"));
            Assert.That(read?.RootElement.GetProperty("text").GetString()?.Trim(), Is.Empty, "not its name");
        });
        Assert.Multiple(() =>
        {
            Assert.That(typed.Verified, Is.True);
            Assert.That(int.Parse(Heard("rico"), System.Globalization.CultureInfo.InvariantCulture), Is.GreaterThanOrEqualTo(4));
        });
    }

    // C9 with the review's item 2: a field whose text lives in child elements goes by the keyboard. Empty and without the focus,
    // UI Automation puts it there inside the keyboard's burst: heard, key by key, and written once.
    [TestCase("Rol sin foco", "rols", false)]
    [TestCase("Rol reemplazo", "rolr", true)]
    [Order(2)]
    public async Task C9_AnEmptyRichFieldIsFocusedTypedAndHeard(string name, string id, bool replace)
    {
        ExternalCapabilityReceipt receipt = await TypeAsync(name, "hola", replace: replace);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(int.Parse(Heard(id), System.Globalization.CultureInfo.InvariantCulture), Is.EqualTo(4), "each key, once");
        });
    }

    // The empty one with no children to tell it (written, erased, typed): the erasing is heard by nobody, the keys are.
    [Test]
    [Order(2)]
    public async Task C9_AnEmptyRichFieldWithNoChildrenIsErasedThenTyped()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Rol vacio", "hola");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(int.Parse(Heard("rol"), System.Globalization.CultureInfo.InvariantCulture), Is.EqualTo(4));
        });
    }

    // A text longer than the keyboard's pace fits, on a Chromium surface: whole, in the budget, heard. Paces measured here.
    [Test]
    [Order(9)]
    public async Task H2c_ALongTextIsTypedWholeAndHeard()
    {
        string text = string.Concat(Enumerable.Range(0, 4000).Select(static at => (char)('a' + (at % 26))));
        Stopwatch clock = Stopwatch.StartNew();
        ExternalCapabilityReceipt receipt = await TypeAsync("Rol largo", text, quiet: true);
        TestContext.Out.WriteLine($"{text.Length} characters in {clock.ElapsedMilliseconds} ms");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True, "read back whole");
            Assert.That(int.Parse(Heard("rolx"), System.Globalization.CultureInfo.InvariantCulture), Is.EqualTo(text.Length));
        });
    }

    // Item 4: the address bar of this browser, as a model would use it: its Edit holding the page's address, the address of
    // a second own page, Enter. What the bar exposes (children or not) decides the route; it must navigate either way.
    [TestCase(true, true)]
    [TestCase(false, true)]
    [TestCase(true, false)]
    [TestCase(false, false)]
    [Order(10)]
    public async Task H4_TheAddressBarNavigates(bool lastNamed, bool front)
    {
        string page = (lastNamed ? "ultima" : "primera") + (front ? "delante" : "detras");
        for (int attempt = 0; front && attempt < 20 && !VisibleControlSurface.BringToFront(_window); attempt++)
            await Task.Delay(100);
        string second = Path.Combine(_folder, page + ".html");
        await File.WriteAllTextAsync(second, "<!doctype html><title>" + PageTitle + " | " + page + "</title><p>ok");
        ExternalCapabilityReceipt view = await _visible!.InvokeAsync(
            "input.visible.controls",
            JsonDocument.Parse(JsonSerializer.Serialize(new { application = PageTitle, limit = 60, wanted = new[] { "direcci" } })).RootElement,
            CancellationToken.None);
        JsonElement bar = default;
        foreach (JsonElement each in view.Result!.Value.GetProperty("controls").EnumerateArray())
        {
            if (each.GetProperty("kind").GetString() == "Edit" && each.GetProperty("name").GetString() is { } named
                && named.Contains("direcci", StringComparison.OrdinalIgnoreCase) && (lastNamed || bar.ValueKind != JsonValueKind.Object))
                bar = each.Clone();
        }

        Assert.That(bar.ValueKind, Is.EqualTo(JsonValueKind.Object), "the bar is in the view");
        string url = new Uri(second).AbsoluteUri;
        ExternalCapabilityReceipt typed = await _typing!.InvokeAsync(
            "input.text.type",
            JsonDocument.Parse(JsonSerializer.Serialize(new { text = url, window = (long)_window, index = bar.GetProperty("i").GetInt32(), replace = true })).RootElement,
            CancellationToken.None);
        TestContext.Out.WriteLine($"bar: verified={typed.Verified} error={typed.ErrorCode} result={typed.Result}");
        Assert.That(typed.Verified, Is.True, "the address is in the bar");
        ExternalCapabilityReceipt enter = await _typing!.InvokeAsync(
            "input.key.press",
            JsonDocument.Parse(JsonSerializer.Serialize(new { key = "enter", window = (long)_window })).RootElement,
            CancellationToken.None);
        TestContext.Out.WriteLine($"enter: verified={enter.Verified} error={enter.ErrorCode}");
        string arrived = PageTitle + " | " + page;
        for (int attempt = 0; attempt < 40 && !VisibleControlSurface.WindowTitle(_window).StartsWith(arrived, StringComparison.Ordinal); attempt++)
            await Task.Delay(200);
        Assert.That(VisibleControlSurface.WindowTitle(_window), Does.StartWith(arrived));
    }

    // Contracase: a native field keeps its value route, behind the person's window too, and the page hears it.
    [TestCase("Area vacia", "area")]
    [TestCase("Linea vacia", "linea")]
    [TestCase("Busqueda", "busca")]
    [TestCase("Correo", "correo")]
    [Order(4)]
    public async Task C9_Contracase_ANativeFieldKeepsItsValueRoute(string name, string id)
    {
        ExternalCapabilityReceipt receipt = await TypeAsync(name, "hola@x.es");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("setvalue"));
            Assert.That(Heard(id), Is.EqualTo("1"), "the page heard it");
        });
    }

    [Test]
    [Order(5)]
    public async Task C9_Contracase_ANativeFieldWithTextIsReplacedByItsValue()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Linea llena", "nuevo", replace: true);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(Heard("llena"), Is.EqualTo("1"));
        });
    }

    // Hondo 11.1 on a page: a controlled input that puts its own state back 40 ms after the event was told written.
    [Test]
    [Order(6)]
    public async Task H111_AControlledInputThatPutsItsStateBackIsNotToldWritten()
    {
        ExternalCapabilityReceipt receipt = await TypeAsync("Controlada", "hola");
        Assert.Multiple(() =>
        {
            Assert.That(Heard("control"), Is.EqualTo("1"), "the page heard it");
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.Result?.GetProperty("fieldUnchanged").GetBoolean(), Is.True);
        });
    }

    private async Task<(nint Window, uint Process)> OwnWindowAsync()
    {
        for (int attempt = 0; attempt < 60; attempt++)
        {
            nint chosen = 0;
            uint owner = 0;
            EnumWindows((window, ignored) =>
            {
                if (!IsWindowVisible(window)
                    || !VisibleControlSurface.WindowTitle(window).StartsWith(PageTitle + " - ", StringComparison.Ordinal))
                    return true;
                _ = GetWindowThreadProcessId(window, out uint process);
                if (_before.Contains(unchecked((int)process)))
                    return true;
                chosen = window;
                owner = process;
                return false;
            }, 0);
            if (chosen != 0)
                return (chosen, owner);
            await Task.Delay(500);
        }

        return (0, 0);
    }

    private delegate bool EnumWindowsProc(nint window, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(nint window);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint process);
}
