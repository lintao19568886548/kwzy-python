# Change: implement-payment-collection

## Why
Bill 已交付。需收款登记 Payment 与 Allocation 核销回写账单 paid_amount。

## What
- payments、payment_allocations
- create payment with allocations；reverse payment
- Payment = 收款登记非在线支付

## Out
- 支付网关/退款算法发明
- CollectionCase 催缴产品化（可后置）
- merge main
