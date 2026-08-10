# Design: implement-bill-master

## 状态机
DRAFT → ISSUED → PARTIALLY_PAID → PAID；ISSUED void→VOID（paid=0）；DRAFT discard→DISCARDED。  
is_overdue = status in ISSUED|PARTIALLY_PAID and due_date < today and open_amount > 0。

## 金额
total_amount = sum(lines.amount)；行 amount 可由 quantity*unit_price 计算（2 位小数 HALF_UP）。  
不发明税率/滞纳金。

## 权限
bill:read / bill:write / bill:issue

## 迁移
revision down_revision = d4b02c3f5a21
