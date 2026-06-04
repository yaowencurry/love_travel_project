---
name: ticket_booking
description: Prepare ticket and attraction booking options with confirmation gates.
---
triggers: quote_transport, quote_attractions, ask_user_confirmation, mock_booking

# 票务预订 Skill

车票、门票、酒店预订都必须在用户明确确认后才能进入下单节点。V1 只允许模拟订单，不允许真实支付、出票、扣费、改签或取消。

