using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Al máximo 5.1: the catalog's typed effects (OperationEffects) against the App's lists by name they replaced
/// (NativeTurnLoop.SendsInputToAWindow and ReachesTheNetwork at b6b731f94), every operation with every argument the
/// lists read.
/// </summary>
[TestFixture]
public sealed class CatalogEffectTests
{
    private static readonly HashSet<string> WindowInputAlways =
    [
        "input.visible.click", "input.text.type", "input.key.press", "input.pointer.control", "input.pointer.drag",
        "input.select.all",
        "input.scroll", "input.keyboard.layout", "clipboard.copy", "clipboard.paste", "message.draft", "message.send",
        "client.channel.locate", "browser.control", "calculator.expression.evaluate", "game.launch", "window.focus",
        "window.maximize", "window.minimize.all", "window.move", "window.resize", "window.snap", "file.open",
        "filesystem.file.open.latest", "filesystem.folder.open", "browser.page.read", "browser.tabs.list",
        "game.store.page", "game.store.search", "client.microphone.set", "clipboard.paste.into", "office.format.apply",
    ];

    private static readonly HashSet<string> NetworkAlways =
    [
        "web.search", "web.fetch", "web.download", "weather.current", "network.ping",
        "shell.command.run", "peripheral.print",
        // Al máximo 11.5 (after the lists): the URL a navigation opens leaves the PC too; NetworkEgress reads the fact.
        "browser.navigate", "browser.navigate.named",
        // Auditoría del núcleo 2026-10-23: a search or an address the model wrote for a service leaves the PC too
        // (the lists left them to the heartbeat's risks).
        "media.play.query", "media.play.exact", "media.play.youtube", "streaming.play.named", "streaming.navigate",
        "game.store.search", "game.store.page",
    ];

    [Test]
    public void EveryOperationHasTheEffectsTheAppsListsGaveIt()
    {
        var differences = new List<string>();
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.ToolDescriptors)
        {
            foreach (JsonObject arguments in Variants(descriptor))
            {
                bool window = NativeTurnLoop.Has(descriptor.Name, arguments, OperationEffects.WindowInput);
                bool network = NativeTurnLoop.Has(descriptor.Name, arguments, OperationEffects.Network);
                if (window != WindowInput(descriptor.Name, arguments) || network != Network(descriptor.Name, arguments))
                {
                    differences.Add($"{descriptor.Name} {arguments.ToJsonString()}: window {window}, network {network}");
                }
            }
        }

        Assert.That(differences, Is.Empty);
    }

    [Test]
    public void EveryOperationTheListsNamedIsInTheCatalog()
    {
        string[] names = [.. ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)];
        Assert.That(WindowInputAlways.Union(NetworkAlways), Is.SubsetOf(names));
    }

    // The lists as they were (b6b731f94).
    private static bool WindowInput(string operation, JsonObject arguments) =>
        WindowInputAlways.Contains(operation)
        || (operation == "app.open" && (IsTrue(arguments, "foreground") || IsTrue(arguments, "newDocument")
            || Named(arguments, "place")))
        || (operation == "system.settings.set" && Text(arguments, "setting") == "do_not_disturb")
        || (operation == "input.visible.controls" && Named(arguments, "application"))
        || (operation == "media.control" && !(Named(arguments, "sourceApp")
            && !string.Equals(Text(arguments, "sourceApp"), WindowsExternalCapabilityProvider.YouTubeTabMediaSource,
                StringComparison.OrdinalIgnoreCase)));

    private static bool Network(string operation, JsonObject arguments) =>
        NetworkAlways.Contains(operation) || (operation == "system.time" && Named(arguments, "place"));

    private static string? Text(JsonObject arguments, string name) =>
        arguments[name] is JsonValue value && value.TryGetValue(out string? text) ? text : null;

    private static bool Named(JsonObject arguments, string name) => !string.IsNullOrWhiteSpace(Text(arguments, name));

    private static bool IsTrue(JsonObject arguments, string name) =>
        arguments[name] is JsonValue value && value.TryGetValue(out bool set) && set;

    // No arguments, and each argument alone with each value a list read: true, false, a name, a blank, null, BAXY's
    // YouTube tab in two cases, and every value the schema allows.
    private static IEnumerable<JsonObject> Variants(ProductOperationDescriptor descriptor)
    {
        yield return new JsonObject();
        foreach (OperationArgumentProperty property in descriptor.ArgumentsSchema.Properties)
        {
            string youTube = WindowsExternalCapabilityProvider.YouTubeTabMediaSource;
            JsonNode?[] values =
                [true, false, "x", " ", null, youTube, youTube.ToUpperInvariant(),
                    .. property.AllowedValues.Select(static value => (JsonNode?)value)];
            foreach (JsonNode? value in values)
            {
                yield return new JsonObject { [property.Name] = value?.DeepClone() };
            }
        }
    }
}
