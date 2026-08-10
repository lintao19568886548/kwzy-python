# Design: implement-payment-collection

sum(allocations) <= payment.amount；累计核销 <= bill.total_amount。  
CONFIRMED 可 reverse 回冲核销。  
revision down_revision e5c13d4a6b32。
