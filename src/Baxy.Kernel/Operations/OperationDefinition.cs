namespace Baxy.Kernel.Operations;

public sealed class OperationDefinition
{
    public OperationDefinition(
        string name,
        OperationRisk risk,
        string description)
    {
        Name = name;
        Risk = risk;
        Description = description;
    }

    public OperationDefinition(ProductOperationDescriptor descriptor)
    {
        ProductDescriptor = descriptor ?? throw new ArgumentNullException(nameof(descriptor));
        Name = descriptor.Name;
        Risk = ProductCatalog.ToPolicyRisk(descriptor.Risk);
        Description = descriptor.Description;
    }

    public string Name { get; }

    public OperationRisk Risk { get; }

    public string Description { get; }

    public ProductOperationDescriptor? ProductDescriptor { get; }
}
