// Kiểm thử công thức phí ship theo các mốc khoảng cách quan trọng.
using NUnit.Framework;

namespace FoodOrder.Tests;

[TestFixture]
public sealed class ShippingFeeTests
{
    private OrderCalculator _calculator = null!;

    [SetUp]
    public void SetUp()
    {
        _calculator = new OrderCalculator();
    }

    [Test]
    public void CalculateShippingFee_2Km_Returns17000()
    {
        var fee = _calculator.CalculateShippingFee(2);

        Assert.That(fee, Is.EqualTo(17000m));
    }

    [Test]
    public void CalculateShippingFee_4Km_Returns22500()
    {
        var fee = _calculator.CalculateShippingFee(4);

        Assert.That(fee, Is.EqualTo(22500m));
    }

    [Test]
    public void CalculateShippingFee_6Km_Returns28500()
    {
        var fee = _calculator.CalculateShippingFee(6);

        Assert.That(fee, Is.EqualTo(28500m));
    }

    [Test]
    public void CalculateShippingFee_11Km_Returns57000()
    {
        var fee = _calculator.CalculateShippingFee(11);

        Assert.That(fee, Is.EqualTo(57000m));
    }
}
