// Logic nghiệp vụ tính giá cốt lõi, dùng cho NUnit và kiểm tra cầu nối UI-runtime.
namespace FoodOrder.Tests;

public sealed class OrderCalculator
{
    public decimal CalculateShippingFee(double distanceKm)
    {
        // Chặn input không hợp lệ từ sớm để công thức luôn an toàn.
        if (distanceKm < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(distanceKm), "Distance must be non-negative.");
        }

        // Áp bậc phí ship theo km đã làm tròn lên.
        var roundedDistance = (int)Math.Ceiling(distanceKm);

        if (roundedDistance <= 3)
        {
            return 17000m;
        }

        if (roundedDistance <= 5)
        {
            return 17000m + (roundedDistance - 3) * 5500m;
        }

        if (roundedDistance <= 10)
        {
            return 28500m + (roundedDistance - 6) * 6000m;
        }

        return 57000m + (roundedDistance - 11) * 5500m;
    }

    public decimal CalculateTotal(decimal foodPrice, int quantity, double distanceKm)
    {
        // Kiểm tra dữ liệu đầu vào trước khi tính tiền.
        if (foodPrice < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(foodPrice), "Food price must be non-negative.");
        }

        if (quantity <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(quantity), "Quantity must be greater than zero.");
        }

        // Tổng tiền = tiền món * số lượng + phí ship.
        var shippingFee = CalculateShippingFee(distanceKm);
        return foodPrice * quantity + shippingFee;
    }
}
