// Kiểm thử công thức tổng tiền: foodPrice * quantity + shippingFee.
using NUnit.Framework;

namespace FoodOrder.Tests;

[TestFixture]
public sealed class TotalPriceTests
{
    private OrderCalculator _calculator = null!;

    [SetUp]
    public void SetUp()
    {
        _calculator = new OrderCalculator();
    }

    [Test]
    public void CalculateTotal_49000x2_With4KmShipping_Returns120500()
    {
        var total = _calculator.CalculateTotal(foodPrice: 49000m, quantity: 2, distanceKm: 4);

        Assert.That(total, Is.EqualTo(120500m));
    }
}
