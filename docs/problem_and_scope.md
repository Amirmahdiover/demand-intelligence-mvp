# Demand Intelligence MVP — Problem and Scope

## 1. Problem

The factory's problem is not just sales forecasting. The deeper problem is that real customer demand becomes visible too late for production planning, raw material purchasing, and delivery decisions.

In custom textile manufacturing, demand often appears before an official order is placed. Sales calls, negotiations, quote requests, informal customer messages, follow-ups, and early buying signals can all indicate future demand. Today, these signals are usually stored as scattered notes, remembered by individual salespeople, or left inside unstructured conversations.

Because these signals are not captured in a structured way, the company may react only after official orders arrive. By that time, production capacity and PET Chips availability may already be constrained. This creates a planning gap between what customers are likely to need and what the factory is preparing to supply.

PET Chips are especially important because they carry supply risk, long lead time, currency dependency, and inventory cost. Underestimating demand can lead to shortage, delayed delivery, and lost customers. Overestimating demand can lock capital in slow-moving raw material inventory.

## 2. Users

The likely users of the MVP are:

### Sales Manager

This user sees early demand signals from customer calls, negotiations, quotes, follow-ups, and informal requests before official orders are placed. The MVP helps them capture these signals as structured sales notes and possible future demand. Useful outputs include customer-level demand signals, likely upcoming orders, and notes that have not yet become official orders.

### Production Manager

This user needs to understand which products may require more production in the coming weeks. The MVP helps them compare baseline demand with adjusted demand by product. Useful outputs include short-term product forecasts, changes in expected demand, and products that may need production attention.

### Supply / Procurement Manager

This user needs to decide how much PET Chips may be required and whether there is shortage or surplus risk. The MVP helps by translating the adjusted demand forecast into PET requirement and inventory risk. Useful outputs include PET requirement estimates, shortage alerts, surplus warnings, and material planning signals.

### Planning Manager

This user connects sales, production, and procurement decisions. The MVP helps by combining historical orders, sales signals, market factors, forecast, and material risk into one planning view. Useful outputs include combined demand views, forecast adjustments, material impact, and planning risks across departments.

### CEO / Operations Manager

This user needs a high-level view of business risk, such as shortage, delayed delivery, lost customers, or excess inventory. The MVP helps by showing key risk alerts and decision-support insights. Useful outputs include management-level risk summaries, shortage or surplus alerts, and clear explanations of what decisions may be needed.

## 3. Main Decisions

The MVP should help the company make better short-term planning decisions before demand becomes urgent.

### 1. How much should we produce in the next few weeks?

Production needs early visibility into expected product demand so capacity can be planned before orders become urgent. This matters because late visibility can create delayed delivery, rushed production, or missed customer commitments. The MVP helps by showing a baseline forecast and an adjusted forecast by product.

### 2. How much PET Chips should we prepare or purchase?

PET Chips have lead time, supply risk, currency dependency, and inventory cost. This matters because buying too little can create shortage, while buying too much can lock capital in slow-moving inventory. The MVP helps by converting adjusted product demand into required PET quantity.

### 3. Which product has shortage risk?

Not all products have the same demand volatility or material impact. This matters because a small demand increase in one product may create a larger raw material risk than expected. The MVP helps by comparing required PET with available inventory and safety stock.

### 4. Which customer is likely to place an order soon?

Sales notes may reveal future demand before official orders are placed. This matters because early customer intent can help sales, production, and procurement prepare sooner. The MVP helps by extracting structured signals such as expected quantity, expected period, and intent probability.

### 5. Which sales signals have not yet become official orders?

Some demand signals are lost because they stay inside calls, messages, or salesperson memory. This matters because the factory may miss demand that is already forming but not yet visible in order data. The MVP helps by making those signals visible and trackable.

### 6. If demand increases or decreases, what is the effect on raw material needs?

Managers need scenario analysis before committing to purchasing or production decisions. This matters because even a moderate change in demand can affect PET requirement, inventory exposure, and shortage risk. The MVP helps by showing how demand changes affect PET requirement and shortage or surplus risk.

## 4. MVP Goal

The goal of the MVP is to prove that early demand signals can be converted into practical planning insight.

The MVP should combine:

- Historical sales orders
- Sales notes and informal demand signals
- External market factors such as USD rate, PET price, export condition, and season
- Product material requirements
- Current PET Chips inventory and safety stock

The MVP should produce:

- A baseline demand forecast
- Structured sales signals extracted from sales notes
- An adjusted demand forecast
- Estimated PET Chips requirement
- Shortage or surplus risk
- A simple dashboard or report for decision support

The MVP should answer one main question:

"Can we detect demand and material risk earlier than waiting for official orders?"

This first version should prove a small value loop from demand signal to forecast, adjusted forecast, PET Chips requirement, risk alert, and decision-support insight. It should stay practical and realistic, without claiming highly accurate industrial forecasts or trying to become a full enterprise planning system.

## 5. Out of Scope

The first MVP will intentionally not include:

- Real ERP integration
- Real CRM integration
- Speech-to-text for phone calls
- Complex forecasting models such as LSTM or Transformer
- Full enterprise multi-user system
- Authentication and user management
- Automatic purchasing decisions
- Full production optimization
- Professional UI design
- Fine-tuning language models
- Docker/Kubernetes or production deployment

These items are excluded to keep the first version focused on proving the core value loop: early demand signals, short-term forecast adjustment, PET Chips requirement, shortage or surplus risk, and decision support.

## 6. Success Criteria

The MVP is successful if a simple demo can show:

- A clear data structure for orders, customers, products, sales notes, market factors, and inventory
- A simple baseline demand forecast
- A way to extract structured demand signals from sales notes
- An adjusted forecast using sales signals
- PET Chips requirement calculation
- Shortage or surplus risk detection
- A simple dashboard or report that supports planning decisions
- Clear limitations and next steps

The MVP should be judged by whether it proves the decision-support loop, not by whether it reaches industrial forecasting accuracy in the first version.
