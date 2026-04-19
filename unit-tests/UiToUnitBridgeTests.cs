// Cầu nối dữ liệu runtime từ Appium sang assert nghiệp vụ ở unit test.
using System.Text.Json;
using NUnit.Framework;

namespace FoodOrder.Tests;

[TestFixture]
public sealed class UiToUnitBridgeTests
{
    [Test]
    public void CalculateTotal_FromUiRuntimeData_MatchesDisplayedValues()
    {
        var runtimeFile = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "runtime", "ui_result.json"));

        if (!File.Exists(runtimeFile))
        {
            Assert.Ignore("UI runtime data not found. Run ui-tests/push_result_to_unit_tests.py first.");
            return;
        }

        var json = File.ReadAllText(runtimeFile);
        var uiResult = JsonSerializer.Deserialize<UiOrderResult>(
            json,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            }
        );
        Assert.That(uiResult, Is.Not.Null, "Invalid runtime JSON format.");

        var calculator = new OrderCalculator();
        var shipping = calculator.CalculateShippingFee(uiResult!.DistanceKm);
        var total = calculator.CalculateTotal(uiResult.FoodPrice, uiResult.Quantity, uiResult.DistanceKm);

        Assert.That(shipping, Is.EqualTo(uiResult.DisplayedShippingFee));
        Assert.That(total, Is.EqualTo(uiResult.DisplayedTotal));
    }

    private sealed class UiOrderResult
    {
        public decimal FoodPrice { get; set; }

        public int Quantity { get; set; }

        public double DistanceKm { get; set; }

        public decimal DisplayedShippingFee { get; set; }

        public decimal DisplayedTotal { get; set; }
    }
}
